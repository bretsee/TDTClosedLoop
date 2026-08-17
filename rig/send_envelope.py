#!/usr/bin/env python3
"""send_envelope.py -- play a KNOWN pulse-amplitude envelope to the RZ2 over UDP.

Purpose: answer the single question "does a command I send actually come out of
the stimulator, at the amplitude and on the channel I asked for?" -- with no
PO8e card, no MATLAB, no controller and no model in the path. It is the
open-loop half of the closed loop, isolated.

The envelope is the same quantity the MPC commands: ONE pulse amplitude per
100 Hz control point, in engineering units where 40 is the stimulator's physical
ceiling (see RIG_DAY_2026-07-30.md B-setup). This tool does not know anything
about tissue safety -- set --umax from known-safe limits for the preparation.

Wire format is byte-identical to the live loop's sendUDPPacketWords()
(TDTUDP.cpp): a 4-byte header {0x55, 0xAA, DATA_PACKET=0x00, count} followed by
`count` float32 words in NETWORK byte order, to UDP port 22022. Same
SET_REMOTE_IP handshake, same socket connect(). If stim comes out under this
tool but not under MpcPo8eUdpClosedLoop.exe, the fault is upstream of the wire.

Why Python and not MATLAB: MATLAB's write()/pause() are both bound by the
~15.6 ms Windows timer quantum, which cannot hold a 10 ms tick without the
running-timer hack. This uses timeBeginPeriod(1) plus an absolute-deadline
schedule with a short spin, and reports the jitter it actually achieved.

Default shape is a slow sawtooth: it sweeps every amplitude between umin and
umax, so a single record shows monotonic tracking, saturation and dead zones at
once, and its ramp/reset edge makes lag unambiguous in sSig.

USAGE
    python rig/send_envelope.py --preview                       # draw it, send nothing
    python rig/send_envelope.py --rz2 10.1.0.100 --channels 3 --umax 10
    python rig/send_envelope.py --rz2 10.1.0.100 --channels 1,5,9 --stagger

Then verify at the TDT end: record the block, and run
    python rig/check_envelope.py --sent <log.csv> --block <tdt_block_dir>
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import socket
import struct
import sys
import time

# --- TDT UDP protocol (mirrors TDTUDP.h) ---------------------------------
LISTEN_PORT = 22022
HEADER_0 = 0x55
HEADER_1 = 0xAA
DATA_PACKET = 0x00
GET_VERSION = 0x01
SET_REMOTE_IP = 0x02
FORGET_REMOTE_IP = 0x03
PROTOCOL_VERSION = 1
MAX_SAMPLES = 244

# The stimulator's physical amplitude ceiling. Refuse to exceed it without an
# explicit override: this is a charge/compliance limit, not a style preference.
HARD_MAX_AMPLITUDE = 40.0

CONTROL_RATE_HZ = 100.0


# =========================================================================
# Envelope shapes. Each returns a value in [0, 1] for phase p in [0, 1).
# =========================================================================

def _shape_value(shape: str, p: float, levels: int, duty: float) -> float:
    if shape == "saw":
        return p
    if shape == "revsaw":
        return 1.0 - p
    if shape == "tri":
        return 2.0 * p if p < 0.5 else 2.0 * (1.0 - p)
    if shape == "sine":
        return 0.5 - 0.5 * math.cos(2.0 * math.pi * p)
    if shape == "staircase":
        # Up-then-down ladder over `levels` distinct amplitudes. Easiest shape
        # to read by eye in a raw sSig trace, and each level is held long
        # enough to average over.
        ladder = list(range(levels)) + list(range(levels - 2, 0, -1))
        idx = min(len(ladder) - 1, int(p * len(ladder)))
        return ladder[idx] / max(1, levels - 1)
    if shape == "pulse":
        return 1.0 if p < duty else 0.0
    if shape == "const":
        return 1.0
    raise ValueError("unknown shape %r" % shape)


def build_schedule(args) -> list:
    """Return a list of per-tick amplitude vectors, length `count` each.

    Built entirely up front so that --preview, the CSV log and what actually
    goes on the wire cannot disagree: the send loop only indexes this list.
    """
    dt = 1.0 / args.rate
    n_lead = int(round(args.lead_secs * args.rate))
    n_body = int(round(args.secs * args.rate))
    n_tail = int(round(args.tail_secs * args.rate))
    active = args.channels
    span = args.umax - args.umin

    rows = []
    zero = [0.0] * args.count
    rows.extend([list(zero) for _ in range(n_lead)])

    for k in range(n_body):
        t = k * dt
        vec = [0.0] * args.count
        for i, ch in enumerate(active):
            # Staggering phases makes each channel individually identifiable in
            # sSig, so one record validates channel ROUTING as well as
            # amplitude tracking.
            phase_off = (i / len(active)) if (args.stagger and len(active) > 1) else 0.0
            p = ((t / args.period) + phase_off) % 1.0
            vec[ch - 1] = args.umin + span * _shape_value(args.shape, p, args.levels, args.duty)
        rows.append(vec)

    rows.extend([list(zero) for _ in range(n_tail)])
    return rows


def ascii_preview(rows: list, channels: list, rate: float, umin: float, umax: float,
                  width: int = 76, height: int = 14) -> str:
    """Crude plot of the first active channel, so the operator can eyeball the
    pattern BEFORE any current is delivered."""
    ch = channels[0]
    series = [r[ch - 1] for r in rows]
    if not series:
        return "(empty schedule)"
    cols = []
    for c in range(width):
        a = int(c * len(series) / width)
        b = max(a + 1, int((c + 1) * len(series) / width))
        cols.append(max(series[a:b]))
    lo, hi = min(umin, 0.0), max(umax, 1e-9)
    out = []
    for row in range(height, 0, -1):
        thresh = lo + (hi - lo) * (row - 0.5) / height
        line = "".join("#" if v >= thresh else " " for v in cols)
        out.append("%6.1f |%s" % (lo + (hi - lo) * row / height, line))
    out.append("%6s +%s" % ("0", "-" * width))
    out.append("%6s  %-*s%s" % ("", width - 10, " 0 s", "%.1f s" % (len(series) / rate)))
    return "\n".join(out)


# =========================================================================
# UDP
# =========================================================================

def open_socket(host: str) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    # connect() (not sendto) to match openSocket() in TDTUDP.cpp -- the RZ2
    # registers the sender, so the source socket must be stable.
    sock.connect((host, LISTEN_PORT))
    return sock


def command_packet(cmd: int) -> bytes:
    return bytes([HEADER_0, HEADER_1, cmd, 0])


def check_rz(sock: socket.socket, timeout_s: float = 1.0) -> bool:
    """GET_VERSION handshake. The live loop leaves this disabled to avoid
    blocking; here it is worth doing, because a missing ACK is the cheapest
    possible early warning that the RZ2 UDP gizmo is not listening."""
    req = command_packet(GET_VERSION)
    sock.settimeout(timeout_s)
    try:
        sock.send(req)
        resp = sock.recv(1024)
    except (socket.timeout, OSError):
        return False
    finally:
        sock.settimeout(None)
    return len(resp) == 4 and resp[:3] == req[:3] and resp[3] == PROTOCOL_VERSION


def data_packet(values) -> bytes:
    n = len(values)
    if n > MAX_SAMPLES:
        raise ValueError("count %d exceeds MAX_SAMPLES %d" % (n, MAX_SAMPLES))
    return bytes([HEADER_0, HEADER_1, DATA_PACKET, n]) + struct.pack(">%df" % n, *values)


# =========================================================================
# Main
# =========================================================================

def parse_channels(text: str, count: int) -> list:
    chans = []
    for part in text.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part[1:]:
            a, b = part.split("-", 1)
            chans.extend(range(int(a), int(b) + 1))
        else:
            chans.append(int(part))
    chans = sorted(set(chans))
    bad = [c for c in chans if c < 1 or c > count]
    if bad or not chans:
        raise SystemExit("FAIL: channels must be within 1..%d; got %s" % (count, chans))
    return chans


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rz2", default="10.1.0.100", help="RZ2 IP (default 10.1.0.100)")
    ap.add_argument("--shape", default="saw",
                    choices=["saw", "revsaw", "tri", "sine", "staircase", "pulse", "const"])
    ap.add_argument("--period", type=float, default=2.0, help="seconds per cycle (default 2)")
    ap.add_argument("--secs", type=float, default=20.0, help="seconds of pattern (default 20)")
    ap.add_argument("--rate", type=float, default=CONTROL_RATE_HZ, help="tick rate Hz (default 100)")
    ap.add_argument("--umin", type=float, default=0.0)
    ap.add_argument("--umax", type=float, default=10.0,
                    help="peak pulse amplitude, engineering units (default 10, ceiling 40)")
    ap.add_argument("--channels", default="3",
                    help="1-based BIPOLAR STIM PAIRS, e.g. 3 or 1,5,7 or 1-8 (8 pairs = 16 electrodes)")
    ap.add_argument("--count", type=int, default=8,
                    help="float words per packet (default 8 = the RZ2 gizmo's width)")
    ap.add_argument("--stagger", action="store_true",
                    help="offset each active channel's phase so channels are separable in sSig")
    ap.add_argument("--levels", type=int, default=5, help="staircase levels (default 5)")
    ap.add_argument("--duty", type=float, default=0.5, help="pulse duty cycle 0-1 (default 0.5)")
    ap.add_argument("--lead-secs", type=float, default=1.0, help="leading zeros (default 1)")
    ap.add_argument("--tail-secs", type=float, default=1.0, help="trailing zeros (default 1)")
    ap.add_argument("--log", default=None, help="sent-command CSV (default envelope_sent_<shape>.csv)")
    ap.add_argument("--preview", action="store_true", help="draw the envelope and exit, no socket")
    ap.add_argument("--dry-run", action="store_true",
                    help="run the full timing loop but open no socket and send nothing")
    ap.add_argument("--yes", action="store_true", help="skip the interactive 'go' confirmation")
    ap.add_argument("--allow-above-40", action="store_true",
                    help="permit --umax above the 40-unit physical ceiling (you must mean it)")
    args = ap.parse_args(argv)

    if args.count < 1 or args.count > MAX_SAMPLES:
        raise SystemExit("FAIL: --count must be 1..%d" % MAX_SAMPLES)
    args.channels = parse_channels(args.channels, args.count)
    if args.umin < 0.0:
        raise SystemExit("FAIL: --umin must be >= 0 (amplitude, not signed command)")
    if args.umax < args.umin:
        raise SystemExit("FAIL: --umax must be >= --umin")
    if args.umax > HARD_MAX_AMPLITUDE and not args.allow_above_40:
        raise SystemExit("FAIL: --umax %g exceeds the %g-unit physical ceiling. "
                         "Pass --allow-above-40 only if that is genuinely correct here."
                         % (args.umax, HARD_MAX_AMPLITUDE))

    rows = build_schedule(args)
    dt = 1.0 / args.rate
    total_s = len(rows) * dt

    print("=" * 70)
    print("Envelope: %s  period=%.3f s  u=[%g, %g]  rate=%g Hz" %
          (args.shape, args.period, args.umin, args.umax, args.rate))
    print("Channels: %s of %d  (all others held at 0)%s" %
          (args.channels, args.count, "  [staggered phase]" if args.stagger else ""))
    print("Duration: %.1f s = %d ticks  (%.1f lead + %.1f body + %.1f tail)" %
          (total_s, len(rows), args.lead_secs, args.secs, args.tail_secs))
    print("Target:   %s:%d" % (args.rz2, LISTEN_PORT))
    print("=" * 70)
    print(ascii_preview(rows, args.channels, args.rate, args.umin, args.umax))
    print("=" * 70)

    if args.preview:
        print("--preview: nothing was sent.")
        return 0

    if not args.dry_run and not args.yes:
        print("*** LIVE: this delivers real stim to %s ***" % args.rz2)
        if input("Type 'go' to deliver stim: ").strip() != "go":
            print("Aborted. Nothing was sent.")
            return 1

    # Ask Windows for a 1 ms timer so sleep() can land near a 10 ms tick. The
    # spin below covers the remainder; without this, sleeps quantise to ~15.6 ms
    # and every tick overruns.
    winmm = None
    try:
        import ctypes
        winmm = ctypes.WinDLL("winmm")
        winmm.timeBeginPeriod(1)
    except Exception:
        winmm = None
        print("Note: could not raise timer resolution; jitter will be larger.")

    sock = None
    sent_rows = []
    sent_packets = 0
    send_fail = 0
    try:
        if not args.dry_run:
            sock = open_socket(args.rz2)
            print("Socket connected to %s:%d" % (args.rz2, LISTEN_PORT))
            print("checkRZ: %s" % ("ACK received" if check_rz(sock)
                                   else "NO ACK -- RZ2 UDP gizmo may not be running (continuing)"))
            sock.send(command_packet(SET_REMOTE_IP))
            print("Sent SET_REMOTE_IP.")
            sock.send(data_packet([0.0] * args.count))  # known-zero starting state

        print("Playing %d ticks... (Ctrl+C stops and zeroes the output)" % len(rows))
        t0 = time.perf_counter()
        wall0 = time.time()
        for k, vec in enumerate(rows):
            deadline = t0 + k * dt
            slack = deadline - time.perf_counter()
            if slack > 0.0020:
                time.sleep(slack - 0.0020)
            while time.perf_counter() < deadline:
                pass  # short spin: the last ~2 ms, where sleep() is not trustworthy

            if sock is not None:
                try:
                    sock.send(data_packet(vec))
                except OSError:
                    send_fail += 1
            t_send = time.perf_counter()
            sent_packets += 1
            sent_rows.append((k, t_send - t0, wall0 + (t_send - t0),
                              (t_send - deadline) * 1000.0, vec))
    except KeyboardInterrupt:
        print("\nInterrupted at tick %d." % sent_packets)
    finally:
        # Always leave the stimulator commanded to zero, whatever happened.
        if sock is not None:
            try:
                for _ in range(5):
                    sock.send(data_packet([0.0] * args.count))
                    time.sleep(0.01)
                sock.send(command_packet(FORGET_REMOTE_IP))
                print("Output zeroed (5 zero packets) and FORGET_REMOTE_IP sent.")
            except OSError as exc:
                print("WARNING: failed to send zero/disconnect packets: %s" % exc)
            finally:
                sock.close()
        if winmm is not None:
            winmm.timeEndPeriod(1)

    log_path = args.log or ("envelope_sent_%s.csv" % args.shape)
    with open(log_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["tick", "t_rel_s", "t_unix_s", "sched_err_ms"] +
                   ["ch%02d" % (i + 1) for i in range(args.count)])
        for k, t_rel, t_unix, err_ms, vec in sent_rows:
            w.writerow(["%d" % k, "%.6f" % t_rel, "%.6f" % t_unix, "%.3f" % err_ms] +
                       ["%.4f" % v for v in vec])
    print("Wrote %d rows to %s" % (len(sent_rows), os.path.abspath(log_path)))

    if sent_rows:
        errs = sorted(abs(r[3]) for r in sent_rows)
        n = len(errs)
        print("Tick timing |error| vs ideal %g ms grid: median %.3f ms  p99 %.3f ms  max %.3f ms"
              % (dt * 1000.0, errs[n // 2], errs[min(n - 1, int(0.99 * n))], errs[-1]))
        print("Packets sent: %d   send failures: %d" % (sent_packets, send_fail))
        if args.dry_run:
            print("DRY RUN: no socket was opened and no stim was delivered.")
    print("Next: confirm at the TDT end --")
    print("  python rig/check_envelope.py --sent %s --block <tdt_block_dir> --channels %s"
          % (log_path, ",".join(str(c) for c in args.channels)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
