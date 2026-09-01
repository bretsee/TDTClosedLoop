"""Verify units, template match, arm-event alignment, and rnd1 UDP1 structure."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import spat_common as sc

np.set_printoptions(precision=3, suppress=True)

print("=== 1) Touch block P3: units + template match ===")
blk = sc.read_block(sc.TOUCH_BLOCKS["P3"])
print("stores:", list(blk.streams.keys()), "| epocs:", list(blk.epocs.keys()) if hasattr(blk, "epocs") else None)
d, fs, t0s = sc.wav1_uv(blk)
print(f"Wav1 shape {d.shape} fs {fs:.4f} start {t0s} dtype-orig {blk.streams.Wav1.data.dtype}")
print(f"Wav1 abs p50/p99/max: {np.percentile(np.abs(d),50):.2f} / {np.percentile(np.abs(d),99):.2f} / {np.abs(d).max():.2f}")
on = sc.rising_edges_stream(blk.streams.nThw)
print(f"nThw onsets: {len(on)}, first {on[0]:.3f}s last {on[-1]:.3f}s")
tr, n_pre, kept = sc.epoch(d, fs, t0s, on)
print(f"epoched {tr.shape}, n_pre {n_pre}, kept {kept.sum()}")
tr_bs = sc.baseline_subtract(tr, n_pre)
mean_post = tr_bs[:, :, n_pre:].mean(axis=0)  # 32 x 122
tpl = sc.load_template("P3")
T = np.asarray(tpl["template"])
print(f"template shape {T.shape} fs {float(tpl['fs']):.3f} n_touches {int(tpl['n_touches'])}")
c = np.corrcoef(mean_post.ravel(), T.ravel())[0, 1]
scale = np.dot(mean_post.ravel(), T.ravel()) / np.dot(T.ravel(), T.ravel())
print(f"re-extracted mean vs template: corr {c:.4f}, scale {scale:.4f}")
print(f"peaks: re-extracted {np.abs(mean_post).max():.1f} uV, template {np.abs(T).max():.1f} uV")

print("\n=== 2) Arm block MPC_r1b: UDP1 + alignment ===")
blk2 = sc.read_block(sc.ARM_BLOCKS["MPC_r1b"][0])
print("streams:", list(blk2.streams.keys()))
print("epocs:", list(blk2.epocs.keys()))
if hasattr(blk2, "scalars"):
    print("scalars:", list(blk2.scalars.keys()))
for name in ("UDP1",):
    for grp in ("scalars", "streams", "epocs"):
        g = getattr(blk2, grp, None)
        if g is not None and name in g:
            st = g[name]
            print(f"UDP1 in {grp}: keys {list(st.keys()) if hasattr(st,'keys') else dir(st)}")
            if hasattr(st, "ts") and st.ts is not None:
                ts = np.asarray(st.ts).ravel()
                print(f"  ts n={ts.size} range {ts[0]:.3f}..{ts[-1]:.3f} median dt {np.median(np.diff(ts))*1000:.3f} ms")
            if hasattr(st, "data") and st.data is not None:
                dd = np.asarray(st.data)
                print(f"  data shape {dd.shape} dtype {dd.dtype} uniq[:12] {np.unique(dd)[:12]}")
# Scle
if "Scle" in blk2.epocs:
    sc_on = np.asarray(blk2.epocs.Scle.onset)
    print(f"Scle epoc onsets: {len(sc_on)} first {sc_on[0]:.3f} last {sc_on[-1]:.3f}")
elif "Scle" in blk2.streams:
    sc_on = sc.rising_edges_stream(blk2.streams.Scle)
    print(f"Scle stream onsets: {len(sc_on)} first {sc_on[0]:.3f} last {sc_on[-1]:.3f}")

print("\n=== 3) rnd1 block: UDP1 structure ===")
blk3 = sc.read_block(sc.RND1_BLOCK)
print("streams:", list(blk3.streams.keys()))
print("epocs:", list(blk3.epocs.keys()))
if hasattr(blk3, "scalars"):
    print("scalars:", list(blk3.scalars.keys()))
for grp in ("scalars", "streams", "epocs"):
    g = getattr(blk3, grp, None)
    if g is not None and "UDP1" in g:
        st = g["UDP1"]
        if hasattr(st, "data") and st.data is not None:
            dd = np.asarray(st.data).ravel()
            print(f"UDP1 in {grp}: data n={dd.size} dtype {dd.dtype} uniq {np.unique(dd)[:40]}")
        if hasattr(st, "ts") and st.ts is not None:
            ts = np.asarray(st.ts).ravel()
            print(f"  ts n={ts.size} range {ts[0]:.2f}..{ts[-1]:.2f}")
        if hasattr(st, "fs"):
            print(f"  fs {st.fs}")
        if hasattr(st, "onset"):
            print(f"  onset n={len(st.onset)} data {np.asarray(st.data)[:20]}")
