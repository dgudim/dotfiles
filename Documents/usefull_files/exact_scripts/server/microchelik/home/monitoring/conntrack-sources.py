#!/usr/bin/env python3
"""Push conntrack traffic to VictoriaMetrics and VictoriaLogs.

Every flow between this server and a peer outside it is rolled up by country and protocol as
the bytes seen since the previous run. Remote addresses are written to VictoriaLogs, with a
reverse DNS name when one exists.

The same bytes are also rolled up by the app on this server that owns the flow's socket: the
process name, "docker" for anything running in a container (the per-container panels cover
those), or "nfs"/"kernel" for connections the kernel holds itself. Finding the owner needs the host's PID namespace (pid: host) and CAP_SYS_PTRACE to read
other processes' file descriptors. A socket that is already gone (a connection closed before the
run) can't be traced and counts as "unknown".

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
CONTAINER_RE = re.compile(r"docker[-/][0-9a-f]{64}")
TCP_ESTABLISHED = "01"
TCP_LISTEN = "0A"
NFS_PORT = 2049
IMPORT_URL = "http://127.0.0.1:8428/api/v1/import/prometheus"
LOG_URL = (
    "http://127.0.0.1:9428/insert/jsonline"
    "?_stream_fields=src&_time_field=ts&_msg_field=message"
)
GEOIP_PATH = "/mnt/sata_500/vector/geoip/GeoLite2-Country.mmdb"
# Only there with net.netfilter.nf_conntrack_timestamp=1
AGE_RE = re.compile(r"delta-time=(\d+)")
# /proc/net/nf_conntrack can skip entries while the table changes. A flow missing from one read
# keeps its byte counts this long, so it isn't counted from zero (its whole lifetime) when it's
# listed again.
FLOW_GRACE = 900
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


def local_ips(net_dir="/proc/net"):
    found = {ipaddress.ip_address("127.0.0.1"), ipaddress.ip_address("::1")}
    lines = open(f"{net_dir}/fib_trie", encoding="utf-8", errors="replace").read().splitlines()
    for index, line in enumerate(lines):
        if "host LOCAL" not in line or index == 0:
            continue
        token = lines[index - 1].strip().split()[-1]
        try:
            found.add(ipaddress.ip_address(token))
        except ValueError:
            continue
    try:
        for line in open(f"{net_dir}/if_inet6", encoding="utf-8", errors="replace"):
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
            age = AGE_RE.search(line)
            flows[key] = (
                proto,
                original[0],
                original[1],
                int(original[4]),
                reply[0],
                int(reply[4]),
                int(original[2]) if original[2] else None,
                int(reply[2]) if reply[2] else None,
                int(age.group(1)) if age else None,  # seconds since the flow started
            )
    return flows


def decode_socket_ip(text):
    """An address from /proc/net/{tcp,udp}[6]: little-endian 32-bit words in hex."""
    raw = bytes.fromhex(text)
    raw = b"".join(raw[i:i + 4][::-1] for i in range(0, len(raw), 4))
    addr = ipaddress.ip_address(raw)
    if addr.version == 6 and addr.ipv4_mapped is not None:
        return addr.ipv4_mapped
    return addr


def read_sockets(path):
    """(local address, port, remote port, TCP state, inode) for every socket in one /proc/net table.

    Inode 0 means no process holds the socket: a closing connection, or one the kernel opened
    itself (an NFS mount).
    """
    found = []
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            next(handle, None)
            for line in handle:
                parts = line.split()
                if len(parts) < 10:
                    continue
                ip_hex, port_hex = parts[1].split(":")
                try:
                    addr = decode_socket_ip(ip_hex)
                except ValueError:
                    continue
                remote_port = int(parts[2].rsplit(":", 1)[1], 16)
                found.append((addr, int(port_hex, 16), remote_port, parts[3], parts[9]))
    except OSError:
        pass
    return found


class SocketOwners:
    """Which app owns a local address and port, in any network namespace on the host."""

    def __init__(self, proc="/proc"):
        self.proc = proc
        self.host_ns = os.readlink(f"{proc}/self/ns/net")
        self.inode_pid = {}
        self.ns_pid = {}
        self.ns_of_ip = {}
        self.exact = {}
        self.wild = {}
        self.kernel = {}
        self.app_cache = {}
        self._scan_processes()
        self._scan_sockets()

    def _scan_processes(self):
        for entry in os.scandir(self.proc):
            if not entry.name.isdigit():
                continue
            pid = entry.name
            try:
                ns = os.readlink(f"{self.proc}/{pid}/ns/net")
            except OSError:
                continue
            self.ns_pid.setdefault(ns, pid)
            try:
                fds = os.listdir(f"{self.proc}/{pid}/fd")
            except OSError:
                continue
            for fd in fds:
                try:
                    target = os.readlink(f"{self.proc}/{pid}/fd/{fd}")
                except OSError:
                    continue
                if target.startswith("socket:["):
                    self.inode_pid.setdefault(target[8:-1], pid)

    def _scan_sockets(self):
        for ns, pid in self.ns_pid.items():
            net_dir = f"{self.proc}/{pid}/net"
            if ns != self.host_ns:
                try:
                    for addr in local_ips(net_dir):
                        if not addr.is_loopback:
                            self.ns_of_ip[addr] = ns
                except OSError:
                    pass
            for proto, files in (("tcp", ("tcp", "tcp6")), ("udp", ("udp", "udp6"))):
                for name in files:
                    for addr, port, remote_port, state, inode in read_sockets(f"{net_dir}/{name}"):
                        if inode == "0":
                            # an open connection that no process holds was made by the kernel
                            if proto == "tcp" and state == TCP_ESTABLISHED:
                                nfs = NFS_PORT in (port, remote_port)
                                self.kernel[(ns, proto, addr, port)] = "nfs" if nfs else "kernel"
                            continue
                        listening = proto == "udp" or state == TCP_LISTEN
                        key = (ns, proto, addr, port)
                        # a connected socket beats a listener on the same address and port
                        if key not in self.exact or not listening:
                            self.exact[key] = inode
                        if listening and addr.is_unspecified:
                            self.wild.setdefault((ns, proto, port), inode)

    def _app_of(self, pid):
        cached = self.app_cache.get(pid)
        if cached is not None:
            return cached
        name = ""
        try:
            with open(f"{self.proc}/{pid}/cgroup", encoding="utf-8", errors="replace") as handle:
                if CONTAINER_RE.search(handle.read()):
                    name = "docker"
        except OSError:
            pass
        if not name:
            try:
                with open(f"{self.proc}/{pid}/comm", encoding="utf-8", errors="replace") as handle:
                    name = handle.read().strip()
            except OSError:
                name = ""
        self.app_cache[pid] = name or "unknown"
        return self.app_cache[pid]

    def app_for(self, proto, addr, port):
        if port is None:
            return "kernel"  # ICMP and friends: answered by the kernel, no socket
        if proto not in ("tcp", "udp"):
            return "unknown"
        ns = self.ns_of_ip.get(addr, self.host_ns)
        inode = self.exact.get((ns, proto, addr, port)) or self.wild.get((ns, proto, port))
        pid = self.inode_pid.get(inode) if inode else None
        if pid:
            return self._app_of(pid)
        return self.kernel.get((ns, proto, addr, port), "unknown")


def label_value(text):
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


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


def note_ip(ip_bytes, cache, reader, addr, proto, app, received, sent):
    if received + sent <= 0:
        return
    country_of(addr, cache, reader)
    totals = ip_bytes[(addr, proto, app)]
    totals[0] += received
    totals[1] += sent


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


def attribute(flow, orig_bytes, reply_bytes, local, docker_nets, countries, cache, reader, ip_bytes,
              owners, apps, untraced):
    proto, orig_src, orig_dst, _, reply_src, _, orig_sport, reply_sport = flow[:8]
    try:
        addrs = [ipaddress.ip_address(addr) for addr in (orig_src, orig_dst, reply_src)]
    except ValueError:
        return
    found = flow_peer(*addrs, local, docker_nets)
    if found is None:
        return
    peer, outbound = found
    sent, received = (orig_bytes, reply_bytes) if outbound else (reply_bytes, orig_bytes)
    # The server's end of the flow: where it dialled from, or where a dialled-in flow landed
    # (after DNAT, that's the container's address and port).
    server, port = (addrs[0], orig_sport) if outbound else (addrs[2], reply_sport)
    app = owners.app_for(proto, server, port) if owners is not None else "unknown"
    if sent > 0:
        apps[(app, "tx")] += sent
    if received > 0:
        apps[(app, "rx")] += received
    if app == "unknown":
        untraced[(proto, "out" if outbound else "in", port)] += sent + received
    peer = str(peer)
    add_country(countries, cache, reader, peer, proto, "tx", sent)
    add_country(countries, cache, reader, peer, proto, "rx", received)
    note_ip(ip_bytes, cache, reader, peer, proto, app, received, sent)


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
    apps = defaultdict(int)
    untraced = defaultdict(int)
    ip_bytes = defaultdict(lambda: [0, 0])  # received, sent
    cache = {}
    domains = state.get("domains")
    if not isinstance(domains, dict):
        domains = {}
    reader = load_geoip()
    owners = None
    missed = 0
    try:
        if previous_ts:
            try:
                owners = SocketOwners()
            except OSError as error:
                print(f"can't map sockets to apps: {error}")
            elapsed = now - previous_ts
            for key, flow in flows.items():
                orig_bytes, reply_bytes, age = flow[3], flow[5], flow[8]
                old = previous.get(key)
                if old and orig_bytes >= old[0] and reply_bytes >= old[1]:
                    orig_bytes -= old[0]
                    reply_bytes -= old[1]
                elif old is None and age is not None and age > elapsed + 5:
                    # it was already open at the last run, which didn't see it: there's nothing
                    # to subtract, so start counting from now instead of counting its lifetime
                    missed += 1
                    continue
                # otherwise the flow is new since the last run (or a new connection reused the
                # same addresses and ports), so all of it counts
                attribute(
                    flow, orig_bytes, reply_bytes, local, docker_nets, countries, cache, reader,
                    ip_bytes, owners, apps, untraced,
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
    for (app, direction), amount in sorted(apps.items()):
        samples.append(
            f'conntrack_app_bytes{{app="{label_value(app)}",direction="{direction}"}} {amount}'
        )
    push(samples)
    logged_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
    logs = []
    for (addr, proto, app), (received, sent) in sorted(ip_bytes.items()):
        src = cache.get(addr, "unknown")
        if received + sent <= 0:
            continue
        row = {
            "client_ip": addr,
            "src": src,
            "proto": proto,
            "app": app,
            "bytes": received + sent,
            "rx_bytes": received,  # downloaded by this server
            "tx_bytes": sent,  # uploaded by this server
            "ts": logged_at,
            "message": "conntrack",
        }
        host = lookup_domain(addr, domains)
        if host:
            row["domain"] = host
        logs.append(row)
    push_logs(logs)
    kept = {key: [value[3], value[5], now] for key, value in flows.items()}
    for key, old in previous.items():
        last_seen = old[2] if len(old) > 2 else previous_ts
        if key not in kept and last_seen and now - last_seen < FLOW_GRACE:
            kept[key] = [old[0], old[1], last_seen]
    save_state({"ts": now, "flows": kept, "domains": domains})
    total = sum(apps.values())
    unknown = apps.get(("unknown", "rx"), 0) + apps.get(("unknown", "tx"), 0)
    traced = f"{100 * (total - unknown) / total:.0f}%" if total else "n/a"
    sockets = f"{len(owners.inode_pid)} sockets" if owners is not None else "no sockets"
    print(
        f"flows {len(flows)} (kept {len(kept) - len(flows)} missing, skipped {missed} unseen old) "
        f"local {len(local)} countries {len(countries)} "
        f"samples {len(samples)} logs {len(logs)} apps {len(apps)} ({sockets}, "
        f"{traced} of bytes traced to an app)"
    )
    top = sorted((item for item in untraced.items() if item[1] > 0), key=lambda item: -item[1])[:5]
    if top:
        print("untraced: " + ", ".join(
            f"{proto} {way} port {port}: {amount} B" for (proto, way, port), amount in top
        ))


if __name__ == "__main__":
    main()
