# Lab notebook — 2026-08-29 (Saturday)

Two sessions: morning PC-side 32-ch prep (all sim gates green, committed
`9358d0b`+`2c61c4d`, NNController `cd28165`, all pushed), evening suite session
(G0–G2 banked; a Synapse rig incident found, recovered, and root-caused; the
full 32-channel acquisition chain proven end to end, dry).

## Morning (PC only) — summarized

Width guard in the loop (FATAL on request>stream, warn on request<stream,
`channelMode=` in banner+Summary), the ny_feat warm-width fix
(`4_mpc_server -FeatureCount`; the old 8-wide warm silently capped
`-FeatureChannel` at 8 even on the 16-ch rig), `0_preflight -InputChannels`,
`assess_artifact --own-pair {legacy,none}`, `extract_nthw_templates
--n-channels`, `check_nnw_mode --expect-input`, 8u×32y fixtures + full offline
chain verified on them (planted ch 23 recovered; 32-sweep 1.5 s on 3k ticks).
Bench 22→24 checks. Details in the 08-29 commit messages and
`RIG_DAY_2026-08-29.md`.

## Evening (suite) — G0–G2

**G0 PASS** (~19:00): PO8e card Status OK on the PCI bus (no transport
recurrence); preflight dropped=0 `channelMode=exact(in=16 card=16)`; net_diag
PASS; live probe `Streaming. numChannels=16 sampleBytes=4 (float32)`, window
6/6/0, clean stim-zero shutdown. Both repos pushed before touching anything.

**G0b**: experiment Save-As snapshot made and reload-verified before any edit.

### The Detect incident (and why it will never bite again)

Running Rig Editor **Detect** to pick up the 32-ch headstage REPLACED the rig:
the amp re-detected (mislabeled "PZ5" — Synapse cannot detect amp model on a
fiber port and defaults the icon; the physical amp is a **PZ2-256**) and the
**PO8e(1) entry vanished**, so the snapshot experiment failed to load
(PO8e(1): Rig ???, Status Missing). Attempted fixes that DON'T work, verified
tonight + against TDT docs:

- **History → "Use Starting/Ending State" restores runtime control values
  only** — never the rig, never the processing tree.
- The PO8e is not addable from the PC node or the RZ2 node's right-click menu
  (those offer RXn/RZn/Legacy/PA5 and RAn/UDPRecv/UDPSend/Cam/BNn). Per TDT
  docs it is added by right-clicking the RZ2's **optical quad-DSP card node**
  (our port "8a" = slot 8 port a) — Synapse cannot detect what is on a quad
  card's fiber.
- "Find Network Devices" only finds Ethernet devices (RS4) — never a PO8e.

**The recovery that worked: `C:\TDT\Synapse\Backups` on the Synapse PC holds
automatic backups — a zip from 18:33 (pre-Detect) contained the last-used rig
as a `.synrig`. Edit Rig → Import → that file restored PO8e(1) + amp entry
exactly; the snapshot experiment then loaded clean.**

Standing rules from this:
1. **Never run Detect on this rig** unless forced; if forced, keep the
   **"Merge Previously Saved Configuration"** checkbox CHECKED (unchecking is
   what wipes hardware config).
2. **Export the rig to a dated `.synrig` before ANY rig work** (Edit Rig →
   Export). The Backups zip saved us tonight by luck of timing.
3. The rig is global and unversioned — experiment snapshots do not protect it.

### 32-ch bring-up: the chain, the zeros, the root cause

With the restored rig + manual channel-count edits (NO Detect): stream came up
**32-wide immediately** — probe banner `numChannels=32 sampleBytes=4
(float32)`, `channelMode=exact(in=32 card=32)`, window 6/6/0, dropped=0. The
new guard got its first hardware exercise (16-on-32 run printed the loud
truncate warning correctly).

**But channels 17–32 were EXACT ZEROS** in Wav1 AND Wav2 (dry-bench recording;
1–16 carried the expected floating-headstage line noise, ~99.8% 60 Hz — array
deliberately not in the bath yet). Systematic isolation:

- Tail swap between the 1–16 and 17–32 connectors: zeros stayed on 17–32 →
  both tails good, suspicion on connector/bank.
- PZ2-256 mechanics (TDT manual): banks power up ONLY on headstage-detect
  (HSD pins 4/6/18/19 of each DB26); channel range is fixed per connector;
  Synapse's PZ2 "Channels" is reader width only (nothing is pushed to the
  amp); the RZ2 LCD pop-up mirrors per-bank channel LEDs (red = near-clip,
  green = spike, gray = quiet).
- **Widen-to-64 test (software only): ALL 32 channels went live (1–32), both
  stores.** Banks fine, label honest, amp healthy.
- Set back to 32: **still all 32 live.**

**Root cause: a stale apply.** The original "Channels: 32" edit never reached
the running circuit; cycling the width (32→64→32, with rebuilds) applied it.
Not a hardware fault, not a config-location fault. **Rule: after ANY rig/HAL
channel edit, force a rebuild and verify with the probe banner + a
disk-store width check before concluding anything.**

### State at close (~22:50)

- **G0, G0b, G1, G2 BANKED.** Full chain proven at 32 (dry): PZ2-256 both
  banks → fiber → RZ2 → Wav1/Wav2 (32, T) live 1–32 → PO8e tap 32-wide,
  float32, frame-integrity clean.
- Synapse left in the 32-ch configuration; snapshot + imported `.synrig` +
  the 18:33 Backups zip all exist for reversion.
- NOT yet done: G3 (bath quiet capture + blacklist), G4–G9. Array never
  entered the bath (deliberate — setup validated dry first).
- Format note for the record: PO8e streams float32; Wav1/Wav2 store int16
  with scale factors — both ends already validated (loop 08-15 fix; tdt
  reader returns scaled units, 08-26 floors came from this exact path).

## Sunday plan: the fast ladder (target ≤ 2.5 h)

See `RIG_DAY_2026-08-29.md` § SUNDAY FAST PATH. Key compression: the G4 soak
is DELETED as a separate gate — the G5 delivery run (28k ticks, ~4.6 min,
`-InputChannels 32`) IS the soak and banks the same evidence; G6/G9 analysis
runs while G7/G8 hardware runs. Stimulator goes on charge FIRST thing.
