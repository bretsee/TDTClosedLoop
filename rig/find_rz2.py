#!/usr/bin/env python3
"""Find the RZ2 on the wire by asking every candidate address "what version are you?".

The repo currently disagrees with itself about the RZ2's address -- RZ2UdpBarebones.cpp
defaults to 10.1.0.1 while UDPExample.cpp, MpcPo8eUdpClosedLoop.cpp and the rig scripts
default to 10.1.0.100. Rather than guess, this sweeps the subnet with the protocol's own
GET_VERSION command and reports whoever sends a valid ACK back.

This is more reliable than ping: TDT's UDP interface commonly ignores ICMP but always
answers GET_VERSION, because that is what checkRZ() depends on.

    python rig/find_rz2.py                      # sweep 10.1.0.0/24
    python rig/find_rz2.py --subnet 10.1.0      # same thing, explicit
    python rig/find_rz2.py --hosts 10.1.0.1,10.1.0.100

Requires this PC to already hold an address on that subnet -- run rig/net_diag.ps1 first.
Stdlib only.
"""
from __future__ import annotations

import argparse
import socket
import struct
import sys
import time

HEADER_0 = 0x55
HEADER_1 = 0xAA
GET_VERSION = 1
HEADER_BYTES = 4
PROTOCOL_VERSION = 1
PORT = 22022


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subnet", default="10.1.0", help="first three octets (default 10.1.0)")
    ap.add_argument("--hosts", default=None,
                    help="comma-separated addresses to probe instead of a full sweep")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--wait", type=float, default=2.0,
                    help="seconds to wait for replies after the sweep (default 2)")
    args = ap.parse_args()

    if args.hosts:
        targets = [h.strip() for h in args.hosts.split(",") if h.strip()]
    else:
        targets = [f"{args.subnet}.{i}" for i in range(1, 255)]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(0.2)

    # Windows turns an inbound ICMP "port unreachable" into ConnectionResetError on the
    # NEXT recvfrom of a UDP socket. Sweeping a /24 hits ~253 dead hosts, so without this
    # the scan dies on the first silent address -- often before the RZ2's reply is read.
    if hasattr(socket, "SIO_UDP_CONNRESET"):
        try:
            sock.ioctl(socket.SIO_UDP_CONNRESET, False)
        except OSError:
            pass  # non-Windows or unsupported; the except below still covers it

    # Bind explicitly so we can report which local address the probe leaves from --
    # if this is not on the RZ2's subnet, nothing will ever answer.
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect((targets[0], args.port))
        local_ip = probe.getsockname()[0]
        probe.close()
    except OSError as exc:
        print(f"FAIL: cannot even set up a route to {targets[0]} -- {exc}")
        return 2

    print(f"probing {len(targets)} address(es) on port {args.port}")
    print(f"source address for these probes: {local_ip}")
    if not local_ip.startswith(args.subnet + ".") and not args.hosts:
        print(f"WARNING: source {local_ip} is NOT on {args.subnet}.0/24.")
        print("         Probes are leaving via the wrong interface and cannot be")
        print("         answered. Fix the network first (rig/net_diag.ps1).")
    print()

    req = bytes([HEADER_0, HEADER_1, GET_VERSION, 0])
    for t in targets:
        try:
            sock.sendto(req, (t, args.port))
        except OSError:
            pass
        time.sleep(0.002)

    found = []
    deadline = time.perf_counter() + args.wait
    while time.perf_counter() < deadline:
        try:
            data, addr = sock.recvfrom(4096)
        except socket.timeout:
            continue
        except ConnectionResetError:
            continue  # ICMP port-unreachable from a dead address; keep listening
        ok = (len(data) == HEADER_BYTES and data[0] == HEADER_0 and
              data[1] == HEADER_1 and data[2] == GET_VERSION)
        ver = data[3] if len(data) >= 4 else None
        tag = "VALID ACK" if ok else "reply, but not a valid ACK"
        print(f"  {addr[0]}:{addr[1]}  {tag}  protocol_version={ver}  raw={data[:8].hex(' ')}")
        if ok:
            found.append((addr[0], ver))
    sock.close()

    print()
    if not found:
        print("No RZ2 answered GET_VERSION.")
        print("  Possible causes, in order of likelihood:")
        print("   1. this PC has no address on the RZ2's subnet (run rig/net_diag.ps1)")
        print("   2. the cable is not in the RZ2's gigabit UDP port, or link is down")
        print("   3. the RZ2 is powered off, or its UDP gizmo is not running in Synapse")
        print("   4. the RZ2 is on a different subnet entirely")
        return 1

    print(f"Found {len(found)} device(s) speaking the TDT UDP protocol:")
    for ip, ver in found:
        note = "" if ver == PROTOCOL_VERSION else \
               f"  <-- protocol {ver}, code expects {PROTOCOL_VERSION}"
        print(f"  {ip}   protocol_version={ver}{note}")
    print()
    print("Use this address everywhere:")
    print(f"  .\\rig\\2_loop.ps1 -Run 1 -RZ2 {found[0][0]}")
    print(f"  .\\rig\\5_envelope.ps1 -RZ2 {found[0][0]} -Channels 3")
    print(f"  MpcPo8eUdpClosedLoop.exe {found[0][0]} ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
