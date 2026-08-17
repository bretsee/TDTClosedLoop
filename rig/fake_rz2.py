#!/usr/bin/env python3
"""A faithful stand-in for the RZ2's UDP interface, so the whole send path can be
tested with no hardware.

Speaks the exact protocol in TDTUDP.h:
    byte 0   0x55            HEADER_0
    byte 1   0xAA            HEADER_1
    byte 2   command         0=DATA 1=GET_VERSION 2=SET_REMOTE_IP 3=FORGET_REMOTE_IP
    byte 3   count           number of float32 words (0 for commands)
    byte 4+  count * float32 BIG-ENDIAN (htonl of the float's bit pattern)

Behaviour that matters for the tests:
  * GET_VERSION      -> replies by echoing bytes 0..2 and putting PROTOCOL_VERSION
                        in the count byte. This is exactly what checkRZ() validates,
                        so `--test-udp` will print "checkRZ: ACK received."
  * SET_REMOTE_IP    -> no reply (matches the real RZ2 and setRemoteIp()'s comment).
  * DATA_PACKET      -> decoded, counted, optionally written to CSV.

Exit code is 0 only if at least --expect-packets data packets arrived, so this can
be used as a pass/fail gate in a script rather than something a human has to read.

Usage:
    python rig/fake_rz2.py                          # listen on 0.0.0.0:22022
    python rig/fake_rz2.py --bind 127.0.0.1
    python rig/fake_rz2.py --seconds 20 --csv rx.csv --expect-packets 100
    python rig/fake_rz2.py --quiet                  # summary only

Stdlib only, so it runs under any Python on the rig PC.
"""
from __future__ import annotations

import argparse
import csv
import socket
import struct
import sys
import time

HEADER_0 = 0x55
HEADER_1 = 0xAA
DATA_PACKET = 0
GET_VERSION = 1
SET_REMOTE_IP = 2
FORGET_REMOTE_IP = 3
RESET_TO_DEFAULTS = 0xFF
HEADER_BYTES = 4
MAX_SAMPLES = 244
PROTOCOL_VERSION = 1

CMD_NAME = {DATA_PACKET: "DATA", GET_VERSION: "GET_VERSION",
            SET_REMOTE_IP: "SET_REMOTE_IP", FORGET_REMOTE_IP: "FORGET_REMOTE_IP",
            RESET_TO_DEFAULTS: "RESET_TO_DEFAULTS"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bind", default="0.0.0.0",
                    help="local address to listen on (default 0.0.0.0 = every interface)")
    ap.add_argument("--port", type=int, default=22022)
    ap.add_argument("--seconds", type=float, default=30.0,
                    help="how long to listen before summarising (default 30)")
    ap.add_argument("--csv", default=None, help="write every decoded data packet here")
    ap.add_argument("--expect-packets", type=int, default=1,
                    help="exit non-zero if fewer than this many DATA packets arrive")
    ap.add_argument("--quiet", action="store_true", help="summary only, no per-packet lines")
    ap.add_argument("--max-print", type=int, default=12,
                    help="stop printing per-packet lines after this many (default 12)")
    ap.add_argument("--no-ack", action="store_true",
                    help="do NOT answer GET_VERSION (simulates an RZ2 that is not listening)")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((args.bind, args.port))
    except OSError as exc:
        print(f"FAIL: cannot bind {args.bind}:{args.port} -- {exc}")
        print("      Something else is already listening, or the address is not on "
              "this machine.")
        return 2
    sock.settimeout(0.25)

    print(f"fake RZ2 listening on {args.bind}:{args.port} for {args.seconds:g} s "
          f"(Ctrl-C to stop early)")

    writer = None
    fh = None
    if args.csv:
        fh = open(args.csv, "w", newline="", encoding="utf-8")
        writer = csv.writer(fh)
        writer.writerow(["t_rx_s", "src_ip", "src_port", "count"] +
                        [f"ch{i+1}" for i in range(MAX_SAMPLES)])

    counts = {"DATA": 0, "GET_VERSION": 0, "SET_REMOTE_IP": 0, "FORGET_REMOTE_IP": 0,
              "OTHER": 0, "MALFORMED": 0}
    senders: dict[str, int] = {}
    printed = 0
    first_t = None
    last_t = None
    t0 = time.perf_counter()
    deadline = t0 + args.seconds

    try:
        while time.perf_counter() < deadline:
            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            now = time.perf_counter() - t0
            senders[addr[0]] = senders.get(addr[0], 0) + 1

            if len(data) < HEADER_BYTES or data[0] != HEADER_0 or data[1] != HEADER_1:
                counts["MALFORMED"] += 1
                if not args.quiet and printed < args.max_print:
                    print(f"  [{now:7.3f}] {addr[0]}:{addr[1]} MALFORMED "
                          f"{len(data)} bytes: {data[:8].hex(' ')}")
                    printed += 1
                continue

            cmd = data[2]
            count = data[3]
            name = CMD_NAME.get(cmd, "OTHER")

            if cmd == GET_VERSION:
                counts["GET_VERSION"] += 1
                if not args.no_ack:
                    # checkRZ() requires: same length as the request (HEADER_BYTES),
                    # first three bytes echoed, PROTOCOL_VERSION in the count byte.
                    ack = bytes([HEADER_0, HEADER_1, GET_VERSION, PROTOCOL_VERSION])
                    sock.sendto(ack, addr)
                if not args.quiet:
                    print(f"  [{now:7.3f}] {addr[0]}:{addr[1]} GET_VERSION -> "
                          f"{'ACK sent' if not args.no_ack else 'IGNORED (--no-ack)'}")
                continue

            if cmd in (SET_REMOTE_IP, FORGET_REMOTE_IP):
                counts[name] += 1
                if not args.quiet:
                    print(f"  [{now:7.3f}] {addr[0]}:{addr[1]} {name} (no reply, "
                          f"matches real RZ2)")
                continue

            if cmd != DATA_PACKET:
                counts["OTHER"] += 1
                continue

            expect = HEADER_BYTES + count * 4
            if count > MAX_SAMPLES or len(data) < expect:
                counts["MALFORMED"] += 1
                if not args.quiet and printed < args.max_print:
                    print(f"  [{now:7.3f}] {addr[0]}:{addr[1]} DATA count={count} but "
                          f"only {len(data)} bytes (need {expect})")
                    printed += 1
                continue

            vals = list(struct.unpack(f">{count}f", data[HEADER_BYTES:expect]))
            counts["DATA"] += 1
            if first_t is None:
                first_t = now
            last_t = now
            if writer:
                writer.writerow([f"{now:.6f}", addr[0], addr[1], count] +
                                [f"{v:.6f}" for v in vals])
            if not args.quiet and printed < args.max_print:
                shown = ", ".join(f"{v:.3f}" for v in vals[:8])
                more = f", ... (+{count-8})" if count > 8 else ""
                print(f"  [{now:7.3f}] {addr[0]}:{addr[1]} DATA n={count} [{shown}{more}]")
                printed += 1
                if printed == args.max_print:
                    print("  ... further packets counted but not printed "
                          "(raise --max-print to see more)")
    except KeyboardInterrupt:
        print("\n  stopped by user")
    finally:
        sock.close()
        if fh:
            fh.close()

    print("\n=== fake RZ2 summary ===")
    for k in ("DATA", "GET_VERSION", "SET_REMOTE_IP", "FORGET_REMOTE_IP", "OTHER",
              "MALFORMED"):
        print(f"  {k:18s} {counts[k]}")
    if senders:
        print("  source addresses:")
        for ip, n in sorted(senders.items(), key=lambda kv: -kv[1]):
            print(f"    {ip:16s} {n} packet(s)")
    else:
        print("  source addresses:  NONE -- nothing arrived at all")
    if counts["DATA"] >= 2 and first_t is not None and last_t > first_t:
        rate = (counts["DATA"] - 1) / (last_t - first_t)
        print(f"  data packet rate:  {rate:.1f} Hz over {last_t-first_t:.2f} s")
    if args.csv:
        print(f"  wrote {args.csv}")

    if counts["DATA"] < args.expect_packets:
        print(f"\nFAIL: expected at least {args.expect_packets} DATA packet(s), "
              f"got {counts['DATA']}.")
        return 1
    print(f"\nPASS: {counts['DATA']} DATA packet(s) received and decoded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
