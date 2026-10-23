"""array_health.py -- per-block cortical-array health metrics (post-hoc, 2026-10-16).
Question: was the 64-ch cortical array electrically broken, and from when?
Metrics per block (Wav1, 610 Hz): per-channel RMS, median pairwise inter-channel correlation,
PC1 variance fraction (common-mode share), per-channel corr with the median trace, 60 Hz share,
and a 10-s sliding window of the same to catch an abrupt change inside a block.
"""
import json, os, sys, numpy as np
sys.path.insert(0, r"C:\Users\brets\Documents\Repositories\TDTClosedLoop\rig")
import placement_gate as pg
OUT = r"C:\Users\brets\Documents\Repositories\TDTClosedLoop\day_2026-10-14\analysis"
D = r"C:\Users\brets\Desktop\Data"
BLOCKS = [
 ("acute2 D1 thwack GO (09-10 18:55)", D + r"\BSCL20260909BU-260910-185534"),
 ("acute2 stim probe GO (09-10 20:04)", D + r"\BSCL20260909BU-260910-200410"),
 ("acute2 later block (09-10 21:07)", D + r"\BSCL20260909BU-260910-210727"),
 ("10-13 bench test (19:56)", D + r"\Acute_101426\BSCL20260909BU-261013-195629"),
] + [(lab, D + r"\Acute_101426\%s\%s" % (b, b)) for lab, b in [
 ("10-14 D1 gate 1 (20:07)", "BSCL20260909BU-261014-200749"),
 ("10-14 D1 gate 2 (20:34)", "BSCL20260909BU-261014-203459"),
 ("10-14 D1 gate 3 +600um (20:46)", "BSCL20260909BU-261014-204658"),
 ("10-14 thal gate depth1 (21:15)", "BSCL20260909BU-261014-211506"),
 ("10-14 thal re-probe VOID (21:36)", "BSCL20260909BU-261014-213610"),
 ("10-14 thal re-probe 2 (21:45)", "BSCL20260909BU-261014-214559"),
 ("10-14 P1 (21:55)", "BSCL20260909BU-261014-215545"),
 ("10-14 MP (22:00)", "BSCL20260909BU-261014-220050"),
 ("10-14 LP (22:06)", "BSCL20260909BU-261014-220623"),
 ("10-14 P3 (22:10)", "BSCL20260909BU-261014-221014"),
 ("10-14 SHAM (22:14)", "BSCL20260909BU-261014-221419"),
]]
def metrics(x, fs):
    """x: [ch, t] uV. returns dict."""
    live = np.std(x, axis=1) > 1e-6
    xl = x[live]
    rms = np.sqrt(np.mean(x**2, axis=1))
    C = np.corrcoef(xl); iu = np.triu_indices(len(xl), 1)
    med_corr = float(np.median(C[iu]))
    # PC1 share on z-scored channels
    z = (xl - xl.mean(1, keepdims=True)) / (xl.std(1, keepdims=True) + 1e-12)
    s = np.linalg.svd(z, compute_uv=False); pc1 = float(s[0]**2 / np.sum(s**2))
    med = np.median(xl, axis=0)
    cm = np.array([np.corrcoef(c, med)[0, 1] for c in xl])
    resid = xl - med[None, :]
    resid_rms = float(np.median(np.sqrt(np.mean(resid**2, axis=1))))
    # 60 Hz share of power (Welch-lite on the median trace)
    n = min(len(med), int(fs*60)); seg = med[:n] - med[:n].mean()
    f = np.fft.rfftfreq(n, 1/fs); P = np.abs(np.fft.rfft(seg))**2
    band = (f > 58) & (f < 62); p60 = float(P[band].sum() / P[(f > 1)].sum())
    return dict(n_live=int(live.sum()), rms_median=float(np.median(rms[live])), rms_min=float(rms[live].min()),
                rms_max=float(rms[live].max()), dead=[int(i)+1 for i in np.flatnonzero(~live)],
                med_pair_corr=med_corr, pc1_share=pc1, corr_with_median_min=float(cm.min()),
                corr_with_median_median=float(np.median(cm)), resid_rms_median=resid_rms,
                p60_share=p60, cm_per_ch=[float(v) for v in np.interp(np.arange(x.shape[0]), np.flatnonzero(live), cm)])
res = []
for lab, path in BLOCKS:
    try:
        blk = pg.read_block(path, ("Wav1",))
        x, fs, t0 = pg.wav1_uv(blk, 0)
    except Exception as e:
        print("%-40s SKIP %s" % (lab, e)); res.append(dict(label=lab, path=path, error=str(e))); continue
    m = metrics(x, fs); m.update(label=lab, path=path, fs=fs, dur_s=float(x.shape[1]/fs))
    # sliding 10 s windows
    w = int(10*fs); nwin = x.shape[1] // w
    sw = []
    for k in range(nwin):
        seg = x[:, k*w:(k+1)*w]
        if np.std(seg) < 1e-9: sw.append(dict(t=k*10, med_pair_corr=None, pc1=None, resid_rms=None)); continue
        mm = metrics(seg, fs); sw.append(dict(t=k*10, med_pair_corr=mm["med_pair_corr"], pc1=mm["pc1_share"], resid_rms=mm["resid_rms_median"]))
    m["windows"] = sw
    res.append(m)
    print("%-40s live %2d  rms med %6.1f (min %5.1f max %7.1f)  pair-corr %.3f  PC1 %.3f  resid %5.1f uV  60Hz %.2f  dead %s" %
          (lab, m["n_live"], m["rms_median"], m["rms_min"], m["rms_max"], m["med_pair_corr"], m["pc1_share"], m["resid_rms_median"], m["p60_share"], m["dead"]))
json.dump(res, open(os.path.join(OUT, "array_health.json"), "w"), indent=1)
print("wrote array_health.json")
