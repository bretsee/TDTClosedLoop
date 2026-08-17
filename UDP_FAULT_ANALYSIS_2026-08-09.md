# Why the RZ2 stopped receiving UDP — analysis, 2026-08-09

Question asked: the rig used to receive UDP packets before the modeling/closed-loop work.
Did that work break it? Change history was reviewed back to the first commit, the IP
addressing was audited, and the send path was tested end-to-end with no hardware.

**Answer: the code did not break it. The PC has no IP address on the RZ2's subnet, so
RZ2-bound packets are being handed to the Wi-Fi default gateway and discarded.**

---

## 1. The code is not the regression

`TDTUDP.cpp` / `TDTUDP.h` hold the entire RZ2 transport (`openSocket`, `sendUDPPacket`,
`checkRZ`, `setRemoteIp`, `disconnectRZ`). Diffing every commit that touched them since
they were added (`c801345`):

```
git diff c801345 -- TDTUDP.cpp TDTUDP.h
```

The **only** change in the file's history is the *addition* of `sendUDPPacketWords()`
plus its header declaration. Nothing was modified, nothing was removed, no address,
port, byte order, or socket option was touched. `UDPExample.cpp` and
`RZ2UdpBarebones.cpp` are byte-identical to when they were added.

The uncommitted working-tree diff to `MpcPo8eUdpClosedLoop.cpp` (106 lines) contains no
change to the RZ2 socket path — the only network-adjacent line is an indentation change
around `PO8e::connectToCard`.

### One long-standing property, not a regression

`MpcPo8eUdpClosedLoop.cpp:1075` has the RZ2 handshake commented out in the main
closed-loop path:

```cpp
// if (!checkRZ(rzSock)) std::printf("Warning: RZ UDP version check failed.\n");
```

This has been commented out **since the first commit that added the file** — it is not
something the recent work disabled. The reason is defensible: `checkRZ()` uses a blocking
`recv()` with no timeout, so on a dead link it would hang forever. The `--test-udp` path
sets `SO_RCVTIMEO` first and then calls it, which is the right pattern.

The consequence, though, is that **the production loop has no positive confirmation that
the RZ2 exists**. See the recommendation in §5.

---

## 2. The addressing is inconsistent in the repo

Two different RZ2 addresses are hard-coded:

| Location | Address |
| --- | --- |
| `RZ2UdpBarebones.cpp:161` (default host) | `10.1.0.1` |
| `MpcPo8eUdpClosedLoop.cpp:557` (usage comment) | `10.1.0.1` |
| `UDPExample.cpp:13` `RZ_IP` | `10.1.0.100` |
| `MpcPo8eUdpClosedLoop.cpp:560,627,667,747` | `10.1.0.100` |
| `rig/2_loop.ps1`, `rig/5_envelope.ps1`, `rig/send_envelope.py` | `10.1.0.100` |

The 2026-07-30 rig day used `10.1.0.100`. If `10.1.0.1` was **this PC's** static address
and `10.1.0.100` the RZ2, everything is consistent. If `10.1.0.1` was the **RZ2's**
address, then every default in the tree is wrong.

Resolve it empirically rather than from memory — `rig/find_rz2.py` sweeps the subnet with
the protocol's own `GET_VERSION` and reports whoever returns a valid ACK. That works even
though TDT UDP interfaces commonly ignore ping.

---

## 3. The actual fault: no route to the RZ2 subnet

Measured on this PC on 2026-08-09:

| Check | Result |
| --- | --- |
| Ethernet adapter (Realtek PCIe) | **Disconnected**, 0 bps — link is down |
| Ethernet IPv4 config | **DHCP enabled, no static address** |
| Ethernet current address | `169.254.62.78/16` (APIPA — DHCP found no server) |
| Registry `DhcpIPAddress` for that NIC | `0.0.0.0` — it has never held a lease |
| Any interface ever assigned `10.1.0.x` | **none**, on any adapter, in the registry |
| Route for `10.1.0.100` | source `172.17.36.92`, egress **Wi-Fi**, via `0.0.0.0/0` → `172.17.255.254` |

So packets addressed to the RZ2 leave over Wi-Fi toward the internet router, which drops
them. `openSocket()` uses `connect()` + `send()` with no explicit local bind, so Windows
picks that route silently and `send()` returns the full byte count.

This is why nothing upstream ever reported an error, and it is consistent with rig day 1
(3000/3000 ticks, `droppedControlTicks=0`, and a biological null).

### Why the physical change caused it

Previously the PC reached the rig through a **network switch**; the segment either had a
DHCP server handing out `10.1.0.x`, or the PC carried a static `10.1.0.1/24` on a prior
install or a different adapter. Now the PC is **wired directly to the RZ2** with Wi-Fi for
internet. A direct cable has no DHCP server, so the NIC falls back to APIPA `169.254.x.x`,
which is not on `10.1.0.0/24` and cannot reach the RZ2.

`255.255.255.0` (/24) is correct for `10.1.0.x`. The subnet mask was never the problem —
the problem is that the address is absent entirely.

Good news: the two networks do not overlap (`172.17.0.0/16` vs `10.1.0.0/24`), and the
Ethernet interface metric (5) beats Wi-Fi (45). A static address on Ethernet with **no
default gateway** fixes the rig path and leaves Wi-Fi internet untouched.

---

## 4. Local proof that the send path works

`rig/6_udp_selftest.ps1` runs the real binaries against `rig/fake_rz2.py`, an emulator
implementing the exact `TDTUDP.h` protocol (including the `GET_VERSION` ACK that
`checkRZ()` validates). Result on 2026-08-09 — all pass:

| Test | Exercises | Result |
| --- | --- | --- |
| A | emulator decodes a hand-built packet | PASS |
| B1 | `.exe --test-udp-once` → `openSocket`+`setRemoteIp`+`sendUDPPacket` | PASS, 1 packet, value exact |
| B2 | `.exe --test-udp` → adds the `checkRZ` handshake | PASS, **"checkRZ: ACK received"**, 176 packets @ 48.9 Hz |
| B3 | `.exe --test-udp-words` → production `sendUDPPacketWords` | PASS, 71 packets @ 19.8 Hz, all 16 words exact |
| C | `rig/send_envelope.py` | PASS, 506 packets @ 100.4 Hz, tick jitter median 0.026 ms |
| D | send to an unreachable target | `send()` **returns 8 bytes — reports success** |

Test D is the point: the transport cannot tell you the destination is unreachable.

Note for future scripting: only `--test-udp-once` returns. `--test-udp` and
`--test-udp-words` are `while(true)` loops ("Press Ctrl+C to stop") and must be started
detached and killed on a timer.

---

## 5. What to do, in order

1. **Plug the Ethernet cable into the RZ2's gigabit UDP port and power the RZ2.**
   `rig/net_diag.ps1` reports FAIL on link until this is true.
2. **Give this PC a static address on the rig subnet** (Administrator PowerShell):
   ```powershell
   .\rig\set_rig_ip.ps1                  # dry run, shows the plan
   .\rig\set_rig_ip.ps1 -Apply           # sets Ethernet to 10.1.0.1/24, no gateway
   ```
   Use `-IP 10.1.0.2` instead if the RZ2 turns out to be `10.1.0.1`.
3. **Confirm the path:** `.\rig\net_diag.ps1 -RZ2 10.1.0.100` — must reach
   "PASS: on-link via Ethernet, no gateway involved."
4. **Confirm the RZ2's real address:** `python rig\find_rz2.py`. Whatever ACKs is the
   RZ2. Update the defaults in the tree to match, so the two addresses stop competing.
5. **Confirm end to end:** `.\rig\6_udp_selftest.ps1 -RZ2 <address>` — test E runs the
   diagnosis then does a live `--test-udp` and looks for the ACK.
6. **Then** re-run the envelope check (`rig/5_envelope.ps1`) and verify `sSig` at the TDT
   end with `rig/check_envelope.py`. That closes rig-day open question (1), "was stim
   actually delivered".

### Recommended code change (not yet made)

Re-enable the RZ2 handshake in the main loop, with the timeout the test path already
uses, so a dead link fails loudly at startup instead of running green for an entire
session:

```cpp
DWORD t = 1000;
setsockopt(rzSock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&t, sizeof t);
if (!checkRZ(rzSock))
    std::printf("WARNING: RZ2 did not ACK GET_VERSION — nothing may be receiving.\n");
```

This is a behaviour change to the production path, so it is left for explicit approval
rather than made silently. It would have caught this fault on day one.

---

## 6. RESOLVED — 2026-08-10

Static `10.1.0.1/24` applied to Ethernet (no gateway). Full re-test:

| Check | Result |
| --- | --- |
| Ethernet link | Up, Connected, **10 Mbps** |
| Ethernet address | `10.1.0.1/24` Manual |
| Route to `10.1.0.100` | on-link via Ethernet, next hop `0.0.0.0` |
| ICMP | `10.1.0.100` answers |
| ARP | `10.1.0.100` → `00-04-A3-00-00-00` |
| `find_rz2.py` full /24 sweep | exactly one device: **`10.1.0.100`, protocol_version=1** |
| `6_udp_selftest.ps1 -RZ2 10.1.0.100` | A, B1, B2, B3, C, D, E1 all PASS |

### The addressing question is settled

The RZ2 is at **`10.1.0.100`** and this PC is **`10.1.0.1`** — exactly the address
remembered from the working setup. `10.1.0.1` in `RZ2UdpBarebones.cpp:161` and in the
`--test-udp` usage comment is the PC's own address in a destination field. Those two
defaults are wrong and should be changed to `10.1.0.100` to stop the ambiguity recurring.

### Open hardware concern: the link negotiated 10 Mbps

The RZ2's UDP interface is on a gigabit port; 10 Mbps means only two pairs are usable —
a damaged or very old cable, or a marginal port. It is **not** a functional problem for
control traffic (100 Hz × 68 B ≈ 54 kbps, four orders of magnitude of headroom), so it
does not block anything. Worth swapping the cable opportunistically, and worth
re-checking if data streaming back from the RZ2 is ever added.

### Two bugs fixed in the new tooling during this session

* `find_rz2.py` died with `ConnectionResetError` mid-sweep. On Windows an inbound ICMP
  port-unreachable surfaces as a reset on the *next* `recvfrom` of a UDP socket, so a /24
  sweep across ~253 dead addresses killed the scan — sometimes before the RZ2's reply was
  read. Fixed with `SIO_UDP_CONNRESET = False` plus an explicit `except`.
* `6_udp_selftest.ps1` test E called `--test-udp` directly, which never returns, and sent
  a nonzero value to live hardware unprompted. Test E is now split: **E1** is
  `GET_VERSION` only (no data packet, safe with an animal connected) and runs by default;
  **E2** sends one data packet and is gated behind `-LiveStim` with a default value of 0.

### Next

`rig/5_envelope.ps1 -RZ2 10.1.0.100 -Channels 3`, then verify `sSig` at the TDT end with
`rig/check_envelope.py`. That closes rig-day open question (1) — "was stim actually
delivered" — which is now answerable for the first time, because until today the packets
were not leaving the PC's Wi-Fi interface.

---

## 7. 2026-08-11 — UDP transport PROVEN; fault moves into the Synapse circuit

Live 22 s saw envelope on channel 3, `10.1.0.100`, recorded to block
`ClosedLoopTest_LD-260811-181302`. Note the block nests one level:
`...\ClosedLoopTest_LD-260811-181302\ClosedLoopTest_LD-260811-181302\`.

### The RZ2 received every packet, bit-exact

`UDP1` is the UDP-receive gizmo's own record of what arrived — a more direct witness
than `sSig`:

| Measure | Result |
| --- | --- |
| Samples captured | 2206 (2200 body + 5 zero tail + 1) |
| Nonzero word | **word 3 only** — matches `--channels 3` exactly |
| Value range received | `0.000 … 9.950` = commanded range exactly |
| Mean inter-sample interval | 9.992 ms (commanded 10.000) |
| Correlation after alignment | **1.000000** |
| Max abs difference | **0.000000** |
| RMS difference | **0.000000** |
| Alignment lag | exactly **1 tick (10 ms)** |

Every one of the 2200 commanded values arrived at the RZ2 with zero error, on the right
channel, at the right rate. The transport question is closed. The 1-tick lag is the known
structural localhost-path delay and confirms `inputDelayTicks = 1` empirically.

### But no stim was generated

| Store | State |
| --- | --- |
| `UDP1` | **live, correct** (above) |
| `Scle` (StimGen scale) | all zero |
| `Plse` (StimGen pulse) | all zero |
| `sSig` (`~StimGen.StimSig`) | all zero |

The value reaches `UDP1` and stops there. **The UDP receive gizmo's output is not wired
into the StimGen's amplitude/scale input in the Synapse circuit.** This is a circuit
wiring problem, not code and not network — nothing in this repo can cause or fix it.

What to check in Synapse, in order:
1. Open the experiment and follow the link from `UDPRecv(1)` output to `StimGen`. The
   scale/amplitude parameter is almost certainly unconnected or driven by a constant.
2. Confirm `StimGen` is enabled and armed — `Plse` being all-zero means it never fired
   at all, not merely that it fired at zero amplitude.
3. Check whether the circuit expects a different word index. `UDP1` word 3 is populated;
   if the circuit reads word 1, send on `--channels 1` to test that hypothesis in one run.

### Newly discovered constraint: UDP1 holds 8 words, the controller sends 16

`UDP1` is `(8, 2206)` — the receive gizmo captures **8 float words per packet**. Both
`send_envelope.py` (`--count`, default 16) and `MpcPo8eUdpClosedLoop.cpp` (`mpcInputCount`,
default 16) send **16**. Words 9–16 are silently discarded by the RZ2.

Channel 3 is inside 8, so this did not affect today's test, but it means **any command on
channels 9–16 would never arrive** and nothing would report an error. Either widen the
gizmo to 16 words in the circuit, or constrain the controller to 8 outputs. Until that is
settled, keep test channels in 1–8.
