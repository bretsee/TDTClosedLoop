# Session state — 2026-08-11 evening (read this first tomorrow)

Written before a PC restart. Everything below is on disk and survives the reboot.

---

## TL;DR

The UDP network fault is **fixed and proven**. Commands now reach the RZ2 bit-exact.
**One blocker remains and it is not in this repo: the Synapse circuit never routes the
received value into the stimulator.**

---

## Survives the restart

| Thing | State |
| --- | --- |
| Ethernet static IP | **Persistent.** Registry: `EnableDHCP=0`, `IPAddress={10.1.0.1}`, `SubnetMask={255.255.255.0}`, no gateway. Comes back automatically. |
| All rig tooling in `rig/` | On disk |
| `UDP_FAULT_ANALYSIS_2026-08-09.md` | On disk, full analysis + resolution |
| `envelope_sent_saw.csv`, `envelope_check.png` | On disk (today's 22 s run) |
| Recorded block | `C:\Users\brets\Desktop\Data\ClosedLoopTest_LD-260811-181302` |

## Does NOT survive the restart

* **PowerShell execution policy.** `Set-ExecutionPolicy -Scope Process Bypass` is per-shell.
  Re-run it in every new Administrator shell, or make it permanent once with
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (not done — it is a system setting,
  left for an explicit decision).
* **MATLAB runtime on PATH.** Set per-shell by `rig\0_preflight.ps1`. Without it the `.exe`
  exits **code 53 printing nothing at all**, which reads exactly like a hang.

## Expected on first boot

`Get-NetIPAddress` will show `10.1.0.1` as **Deprecated** or **Tentative** while the
Ethernet link is down. That is normal, not a regression — it becomes `Preferred` once the
cable is live and the RZ2 is powered. As of shutdown the link was **Disconnected**
(RZ2 off or cable out) and `10.1.0.100` did not answer.

---

## Getting back to a verified state (~2 min)

```powershell
# Administrator PowerShell
cd C:\Users\brets\Documents\Repositories\TDTClosedLoop
Set-ExecutionPolicy -Scope Process Bypass -Force
.\rig\net_diag.ps1 -RZ2 10.1.0.100
```

Expect all five sections PASS. If section 1 fails, it is cable or RZ2 power — the IP
config itself is persistent and should need no action.

Then confirm the RZ2 is speaking:

```powershell
C:\Users\brets\Documents\Repositories\PythonIntanAnalysis\.venv\Scripts\python.exe rig\find_rz2.py
```

Expect exactly one device: `10.1.0.100, protocol_version=1`.

---

## OPEN ISSUE 1 (blocker) — Synapse circuit does not drive StimGen

**Status: confirmed, root cause localised, fix is in Synapse not in code.**

Today's 22 s saw envelope on channel 3 was received perfectly and produced no stim:

| Store | State |
| --- | --- |
| `UDP1` (UDP receive gizmo) | **word 3 only, 0.000–9.950, corr 1.000000 vs commanded, max diff 0.000000, lag exactly 1 tick** |
| `Scle` (StimGen scale) | all zero |
| `Plse` (StimGen pulse) | all zero |
| `sSig` (`~StimGen.StimSig`) | all zero |

`Plse` all-zero means StimGen **never fired at all** — not that it fired at zero
amplitude. So this is a missing connection or a disarmed gizmo, not a scaling bug.

To check tomorrow, in order:
1. Follow the link from `UDPRecv(1)` output to `StimGen` in the experiment. The
   scale/amplitude parameter is likely unconnected or driven by a constant.
2. Confirm `StimGen` is enabled and armed.
3. If it looks wired, the circuit may read a **different word index**. `UDP1` word 3 is
   populated; re-running with `--channels 1` settles that in one pass.

## OPEN ISSUE 2 — the RZ2 only accepts 8 words, we send 16

`UDP1` is shaped `(8, N)`. The receive gizmo captures **8 float words per packet**, but
`send_envelope.py --count` and `MpcPo8eUdpClosedLoop.cpp mpcInputCount` both default to
**16**. Words 9–16 are silently discarded, with no error anywhere.

Channel 3 is inside 8, so today's test was unaffected. **Keep all test channels in 1–8**
until either the gizmo is widened to 16 or the controller is constrained to 8.

## OPEN ISSUE 3 — feature window, untested (input side)

Unrelated to today's work and still the leading hypothesis for the rig-day-1 biological
null. `PREPROCESS_WINDOW_US = 10000` at `MpcPo8eUdpClosedLoop.cpp:1123` is 10 ms of sample
**arrival** time, not signal time. On real hardware the window held **3 to 5,439 samples**
(vs a steady ~250 in simulation), which at the top end averages ~200 ms and would wash out
a 15–28 ms evoked response. Needs a C++ rebuild to change. Only becomes testable once
Issue 1 is fixed and stim is actually being delivered.

## OPEN ISSUE 4 — two stale `10.1.0.1` defaults

Settled today: **RZ2 = `10.1.0.100`, this PC = `10.1.0.1`.** Two places still use the PC's
own address as a destination and should be changed to `10.1.0.100`:
* `RZ2UdpBarebones.cpp:161`
* `MpcPo8eUdpClosedLoop.cpp:557` (the `--test-udp` usage comment)

## SUGGESTED, NOT DONE — re-enable the RZ2 handshake in the main loop

`MpcPo8eUdpClosedLoop.cpp:1075` has `checkRZ` commented out — since the first commit, so
not a regression, but it means the production loop has no confirmation the RZ2 exists.
This would have caught the network fault on day one:

```cpp
DWORD t = 1000;
setsockopt(rzSock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&t, sizeof t);
if (!checkRZ(rzSock))
    std::printf("WARNING: RZ2 did not ACK GET_VERSION - nothing may be receiving.\n");
```

Left unmade: it changes production startup behaviour and needs a rebuild.

## SUGGESTED, NOT DONE — teach `check_envelope.py` to read `UDP1`

Today it reported `FAIL, corr -2.000` against `sSig` — correct but uninformative
(`-2.0` is its "no signal" sentinel). `UDP1` is what localised the fault. Adding it would
let the script distinguish **"never arrived"** from **"arrived but was not used"**
automatically, which is exactly the distinction that mattered today.

---

## Reference — verified tooling in `rig/`

| Script | Purpose |
| --- | --- |
| `net_diag.ps1` | Read-only PC→RZ2 path diagnosis with a verdict |
| `set_rig_ip.ps1` | Static IP on/off; dry-run unless `-Apply`; needs admin |
| `find_rz2.py` | `GET_VERSION` subnet sweep; finds the RZ2 where ping cannot |
| `fake_rz2.py` | Faithful `TDTUDP.h` emulator; ACKs `GET_VERSION` so `checkRZ` passes |
| `6_udp_selftest.ps1` | 7 tests, all pass. `-RZ2 <ip>` adds live checks. E2 (real data packet) gated behind `-LiveStim`, default value 0 |

**Gotcha:** only `--test-udp-once` returns. `--test-udp` and `--test-udp-words` are
`while(true)` loops — start detached and kill on a timer.

---

## Note: everything here is uncommitted

`git status` shows all of the new tooling, `cpp_controller/`, the analysis docs and this
file as untracked, plus modifications to `MpcPo8eUdpClosedLoop.cpp`,
`matlab_controller_server.m` and `mpc_test.m`. Nothing is lost by a reboot — these are
ordinary files on disk — but none of it is under version control yet. Worth a commit when
convenient.
