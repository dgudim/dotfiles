#!/usr/bin/env python3
"""Push conntrack traffic to VictoriaMetrics and VictoriaLogs.

Every flow between this server and a peer outside it is rolled up by country and protocol as
the bytes seen since the previous run. Remote addresses are written to VictoriaLogs, with a
reverse DNS name when one exists.

A flow that opens and closes between two runs is only counted if conntrack still lists it
(closed TCP connections stay in TIME_WAIT for 2 minutes), so run this every minute or so.
"""

import fcntl
import ipaddress
import json
import os
import re
import socket
import struct
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


def docker_networks():
    """Subnets of the Docker bridges (docker0, br-*), from the host routing table."""
    found = []
    try:
        for line in open("/proc/net/route", encoding="utf-8").read().splitlines()[1:]:
            parts = line.split()
            if len(parts) > 7 and (parts[0] == "docker0" or parts[0].startswith("br-")):
                dest = socket.inet_ntoa(struct.pack("<I", int(parts[1], 16)))
                mask = socket.inet_ntoa(struct.pack("<I", int(parts[7], 16)))
                found.append(ipaddress.ip_network(f"{dest}/{mask}", strict=False))
    except OSError:
        pass
    try:
        for line in open("/proc/net/ipv6_route", encoding="utf-8"):
            parts = line.split()
            if len(parts) == 10 and (parts[9] == "docker0" or parts[9].startswith("br-")):
                net = ipaddress.ip_network((ipaddress.IPv6Address(int(parts[0], 16)), int(parts[1], 16)), strict=False)
                if net.prefixlen > 0 and not net.is_link_local and not net.is_multicast:
                    found.append(net)
    except OSError:
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
                original[1],
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


def is_server(addr, local, docker_nets):
    return addr in local or any(addr in net for net in docker_nets)


def flow_peer(orig_src, orig_dst, reply_src, local, docker_nets):
    """The peer outside this server, and whether the server opened the flow.

    The server is its own addresses plus its Docker networks, so the hops between Caddy, the
    containers and their databases are left out. A connection to a published port is DNATed
    to a container, so its reply comes from the container instead of the dialled address.
    None for internal and forwarded flows.
    """
    if is_server(orig_src, local, docker_nets):
        if is_server(orig_dst, local, docker_nets):
            return None
        peer, outbound = orig_dst, True
    elif is_server(reply_src, local, docker_nets):
        peer, outbound = orig_src, False
    else:
        return None
    if is_skipped(peer):
        return None
    return peer, outbound


def attribute(flow, orig_bytes, reply_bytes, local, docker_nets, countries, cache, reader, ip_bytes):
    proto, orig_src, orig_dst, _, reply_src, _ = flow
    try:
        addrs = [ipaddress.ip_address(addr) for addr in (orig_src, orig_dst, reply_src)]
    except ValueError:
        return
    found = flow_peer(*addrs, local, docker_nets)
    if found is None:
        return
    peer, outbound = found
    sent, received = (orig_bytes, reply_bytes) if outbound else (reply_bytes, orig_bytes)
    peer = str(peer)
    add_country(countries, cache, reader, peer, proto, "tx", sent)
    add_country(countries, cache, reader, peer, proto, "rx", received)
    note_ip(ip_bytes, cache, reader, peer, proto, sent + received)


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
    docker_nets = docker_networks()
    flows = read_flows()
    state = load_state()
    previous = state.get("flows") or {}
    previous_ts = state.get("ts")
    countries = defaultdict(int)
    ip_bytes = defaultdict(int)
    cache = {}
    domains = state.get("domains")
    if not isinstance(domains, dict):
        domains = {}
    reader = load_geoip()
    try:
        if previous_ts:
            for key, flow in flows.items():
                orig_bytes, reply_bytes = flow[3], flow[5]
                old = previous.get(key)
                if old and orig_bytes >= old[0] and reply_bytes >= old[1]:
                    orig_bytes -= old[0]
                    reply_bytes -= old[1]
                # otherwise the flow is new since the last run (or a new connection reused the
                # same addresses and ports), so all of it counts
                attribute(flow, orig_bytes, reply_bytes, local, docker_nets, countries, cache, reader, ip_bytes)
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
        if amount <= 0:
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
        "flows": {key: [value[3], value[5]] for key, value in flows.items()},
        "domains": domains,
    })
    print(
        f"flows {len(flows)} local {len(local)} countries {len(countries)} "
        f"samples {len(samples)} logs {len(logs)}"
    )


if __name__ == "__main__":
    main()
