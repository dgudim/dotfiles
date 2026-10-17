#!/usr/bin/env python3
"""Push conntrack traffic to VictoriaMetrics and VictoriaLogs.

Every flow is rolled up by country and protocol as the bytes seen since the previous run.
Remote addresses are written to VictoriaLogs, with a reverse DNS name when one exists.
"""

import fcntl
import ipaddress
import json
import re
import socket
import time
import urllib.request
from collections import defaultdict

import maxminddb

STATE_PATH = "/tmp/conntrack-sources.state"
LOCK_PATH = "/tmp/conntrack-sources.lock"
IMPORT_URL = "http://127.0.0.1:8428/api/v1/import/prometheus"
LOG_URL = (
    "http://127.0.0.1:9428/insert/jsonline"
    "?_stream_fields=src&_time_field=ts&_msg_field=message"
)
GEOIP_PATH = "/mnt/sata_500/vector/geoip/GeoLite2-Country.mmdb"
FLOW_RE = re.compile(
    r"src=(\S+) dst=(\S+)(?: sport=(\d+) dport=(\d+))? packets=\d+ bytes=(\d+)"
)
LOCAL_NETS = tuple(
    ipaddress.ip_network(cidr)
    for cidr in (
        "10.0.0.0/8",
        "127.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "100.64.0.0/10",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    )
)


def local_ips():
    found = {ipaddress.ip_address("127.0.0.1"), ipaddress.ip_address("::1")}
    lines = open("/proc/net/fib_trie", encoding="utf-8", errors="replace").read().splitlines()
    for index, line in enumerate(lines):
        if "host LOCAL" not in line or index == 0:
            continue
        token = lines[index - 1].strip().split()[-1]
        try:
            found.add(ipaddress.ip_address(token))
        except ValueError:
            continue
    try:
        for line in open("/proc/net/if_inet6", encoding="utf-8", errors="replace"):
            parts = line.split()
            if not parts or len(parts[0]) != 32:
                continue
            found.add(ipaddress.IPv6Address(int(parts[0], 16)))
    except FileNotFoundError:
        pass
    return found


def is_skipped(addr):
    return (
        addr.is_loopback
        or addr.is_multicast
        or addr.is_unspecified
        or addr.is_link_local
    )


def is_local(addr):
    return any(addr in net for net in LOCAL_NETS)


def clean_proto(proto):
    kept = "".join(ch for ch in proto.lower() if ch.isalnum())
    return kept or "unknown"


def load_geoip():
    try:
        return maxminddb.open_database(GEOIP_PATH)
    except OSError:
        return None


def country_of(addr_text, cache, reader):
    cached = cache.get(addr_text)
    if cached is not None:
        return cached
    try:
        addr = ipaddress.ip_address(addr_text)
    except ValueError:
        cache[addr_text] = "unknown"
        return "unknown"
    if is_local(addr) or is_skipped(addr):
        cache[addr_text] = "local"
        return "local"
    code = None
    if reader is not None:
        record = reader.get(addr_text) or {}
        code = (record.get("country") or {}).get("iso_code")
        if not code:
            code = (record.get("registered_country") or {}).get("iso_code")
    cache[addr_text] = code or "unknown"
    return cache[addr_text]


def read_flows():
    path = "/proc/net/nf_conntrack"
    flows = {}
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            matches = FLOW_RE.findall(line)
            if len(matches) < 2:
                continue
            proto = clean_proto(line.split(None, 3)[2])
            original, reply = matches[0], matches[1]
            key = "|".join((proto, original[0], original[1], original[2] or "", original[3] or ""))
            flows[key] = (
                proto,
                original[0],
                int(original[4]),
                reply[0],
                int(reply[4]),
            )
    return flows


def load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"ts": None, "flows": {}}


def save_state(state):
    import os
    temporary = STATE_PATH + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(state, handle, separators=(",", ":"))
    os.replace(temporary, STATE_PATH)


def add_country(buckets, cache, reader, addr, proto, direction, nbytes):
    if nbytes <= 0:
        return
    buckets[(country_of(addr, cache, reader), proto, direction)] += nbytes


def note_ip(ip_bytes, cache, reader, addr, proto, nbytes):
    if nbytes <= 0:
        return
    country_of(addr, cache, reader)
    ip_bytes[(addr, proto)] += nbytes


def attribute(origin_src, origin_bytes, reply_src, reply_bytes, proto, local, received, sent, countries, cache, reader, ip_bytes):
    try:
        origin = ipaddress.ip_address(origin_src)
        reply = ipaddress.ip_address(reply_src)
    except ValueError:
        return
    origin_local = origin in local
    reply_local = reply in local
    if origin_local and not reply_local and not is_skipped(reply):
        sent[reply_src] += origin_bytes
        received[reply_src] += reply_bytes
        add_country(countries, cache, reader, reply_src, proto, "tx", origin_bytes)
        add_country(countries, cache, reader, reply_src, proto, "rx", reply_bytes)
        note_ip(ip_bytes, cache, reader, reply_src, proto, origin_bytes + reply_bytes)
    elif reply_local and not origin_local and not is_skipped(origin):
        received[origin_src] += origin_bytes
        sent[origin_src] += reply_bytes
        add_country(countries, cache, reader, origin_src, proto, "rx", origin_bytes)
        add_country(countries, cache, reader, origin_src, proto, "tx", reply_bytes)
        note_ip(ip_bytes, cache, reader, origin_src, proto, origin_bytes + reply_bytes)
    elif not origin_local and not reply_local:
        if not is_skipped(origin):
            received[origin_src] += origin_bytes
            add_country(countries, cache, reader, origin_src, proto, "rx", origin_bytes)
            note_ip(ip_bytes, cache, reader, origin_src, proto, origin_bytes)
        if not is_skipped(reply):
            received[reply_src] += reply_bytes
            add_country(countries, cache, reader, reply_src, proto, "rx", reply_bytes)
            note_ip(ip_bytes, cache, reader, reply_src, proto, reply_bytes)



def lookup_domain(addr, cache):
    cached = cache.get(addr)
    if cached is not None:
        return cached
    previous = socket.getdefaulttimeout()
    socket.setdefaulttimeout(1)
    try:
        host = socket.gethostbyaddr(addr)[0].rstrip(".")
    except OSError:
        host = ""
    finally:
        socket.setdefaulttimeout(previous)
    if host == addr:
        host = ""
    cache[addr] = host
    return host


def push(samples):
    if not samples:
        return
    body = ("\n".join(samples) + "\n").encode()
    request = urllib.request.Request(IMPORT_URL, data=body, method="POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        response.read()


def push_logs(rows):
    if not rows:
        return
    body = "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows).encode()
    request = urllib.request.Request(LOG_URL, data=body, method="POST")
    request.add_header("Content-Type", "application/stream+json")
    with urllib.request.urlopen(request, timeout=20) as response:
        response.read()


def main():
    lock = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    now = time.time()
    local = local_ips()
    flows = read_flows()
    state = load_state()
    previous = state.get("flows") or {}
    previous_ts = state.get("ts")
    received = defaultdict(int)
    sent = defaultdict(int)
    countries = defaultdict(int)
    ip_bytes = defaultdict(int)
    cache = {}
    domains = state.get("domains")
    if not isinstance(domains, dict):
        domains = {}
    reader = load_geoip()
    try:
        if previous_ts:
            for _key, (proto, origin_src, origin_bytes, reply_src, reply_bytes) in flows.items():
                old = previous.get(_key)
                if not old:
                    continue
                attribute(
                    origin_src,
                    max(0, origin_bytes - old[0]),
                    reply_src,
                    max(0, reply_bytes - old[1]),
                    proto,
                    local,
                    received,
                    sent,
                    countries,
                    cache,
                    reader,
                    ip_bytes,
                )
    finally:
        if reader is not None:
            reader.close()
    samples = []
    for (src, proto, direction), amount in sorted(countries.items()):
        if amount <= 0:
            continue
        samples.append(
            f'conntrack_bytes{{src="{src}",proto="{proto}",direction="{direction}"}} {amount}'
        )
    push(samples)
    logged_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
    logs = []
    for (addr, proto), amount in sorted(ip_bytes.items()):
        src = cache.get(addr, "unknown")
        if src == "local" or amount <= 0:
            continue
        row = {
            "client_ip": addr,
            "src": src,
            "proto": proto,
            "bytes": amount,
            "ts": logged_at,
            "message": "conntrack",
        }
        host = lookup_domain(addr, domains)
        if host:
            row["domain"] = host
        logs.append(row)
    push_logs(logs)
    save_state({
        "ts": now,
        "flows": {key: [value[2], value[4]] for key, value in flows.items()},
        "domains": domains,
    })
    print(
        f"flows {len(flows)} local {len(local)} countries {len(countries)} "
        f"samples {len(samples)} logs {len(logs)}"
    )


if __name__ == "__main__":
    main()
