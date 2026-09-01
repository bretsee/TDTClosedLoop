"""Sanity check: one raw event (MPC r1, event 1, site P2, onset 203) target vs achieved."""
import numpy as np
import sci_common as C

plt = C.style()

sched = C.load_schedule("r1")
ref = C.load_ref("r1")
y8 = C.load_y8("MPC", "r1")
ev = sched["events"][0]
onset = ev["onset_tick"]
i0, i1 = onset - C.PRE - 1, onset + C.POST - 1
t = np.arange(-C.PRE, C.POST)

fig, ax = plt.subplots(figsize=(9, 3.5))
ax.plot(t, ref[i0:i1] * 1e3, color=C.COL["grey"], lw=1.5, label="target (ref r1)")
ax.plot(t, y8[i0:i1] * 1e3, color=C.COL["green"], lw=1.0, label="achieved y8 (raw)")
ax.axvline(0, color=C.COL["amber"], lw=0.8, ls="--")
ax.set_xlabel("ticks relative to onset")
ax.set_ylabel("feature (mV)")
ax.set_title(f"Alignment check: MPC r1 event {ev['event']} ({ev['site']}, onset tick {onset})")
ax.legend()
fig.tight_layout()
fig.savefig(f"{C.OUT}/scripts/_verify_alignment.png")

# lag scan on whole record for confirmation
dref = ref - C.BASELINE_REF
n = min(len(ref), len(y8))
for lag in range(-2, 6):
    a = y8[lag:n] if lag >= 0 else y8[:n + lag]
    b = dref[:n - lag] if lag >= 0 else dref[-lag:n]
    m = min(len(a), len(b))
    r = np.corrcoef(a[:m] - a[:m].mean(), b[:m])[0, 1]
    print(f"lag {lag:+d}: global r = {r:.4f}")

# raw stats
print("y8 mean/max:", y8.mean(), y8.max(), " ref mean/max:", ref.mean(), ref.max())
print("event window ref peak:", ref[i0:i1].max(), " y8 peak:", y8[i0:i1].max())
