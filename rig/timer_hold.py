"""timer_hold.py -- hold the Windows multimedia timer at 1 ms while the loop runs.

    python rig/timer_hold.py            # prints the resolution before/after and holds until killed

Why (2026-10-22 23:05, run burst30): MpcPo8eUdpClosedLoop.exe never calls timeBeginPeriod. Its 10 ms
tick is kept only while SOME process on the PC holds the system timer at 1 ms. When that process went
idle at 69 s into burst30 the timer fell back to 15.62 ms and every other tick fired ~5.6 ms late
(lateUs 5300-5800 = 15.62 - 10) -> droppedControlTicks=8811/28917. The three 91 s gate runs earlier in
the evening happened to run while the timer was held, hence 0 drops. drive_live_run.py starts this
holder before terminal A and leaves it running for the whole run.
"""
import ctypes
import sys
import time


def query():
    mi = ctypes.c_ulong(); ma = ctypes.c_ulong(); cu = ctypes.c_ulong()
    ctypes.windll.ntdll.NtQueryTimerResolution(ctypes.byref(mi), ctypes.byref(ma), ctypes.byref(cu))
    return mi.value / 1e4, ma.value / 1e4, cu.value / 1e4


def main():
    before = query()
    rc = ctypes.windll.winmm.timeBeginPeriod(1)
    after = query()
    print("timer_hold: timeBeginPeriod(1) rc=%d | current %.2f ms -> %.2f ms (min %.2f, max %.2f)"
          % (rc, before[2], after[2], after[0], after[1]), flush=True)
    if after[2] > 1.1:
        print("timer_hold: WARN resolution did not drop to 1 ms", flush=True)
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        ctypes.windll.winmm.timeEndPeriod(1)


if __name__ == "__main__":
    main()
