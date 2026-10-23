"""battery_sites.py -- per-site touch responses, raw vs median re-referenced (10-14 thwack battery)."""
import json, os, sys, numpy as np
sys.path.insert(0, r"C:\Users\brets\Documents\Repositories\TDTClosedLoop\rig")
import placement_gate as pg
OUT = r"C:\Users\brets\Documents\Repositories\TDTClosedLoop\day_2026-10-14\analysis"
R = r"C:\Users\brets\Desktop\Data\Acute_101426"
SITES = [("D1", "BSCL20260909BU-261014-204658"), ("P1", "BSCL20260909BU-261014-215545"), ("MP", "BSCL20260909BU-261014-220050"),
         ("LP", "BSCL20260909BU-261014-220623"), ("P3", "BSCL20260909BU-261014-221014"), ("SHAM", "BSCL20260909BU-261014-221419")]
P = pg.CORT
out = {}
for site, b in SITES:
    blk = pg.read_block(os.path.join(R, b, b), ("Wav1", "nThw"))
    d, fs, t0 = pg.wav1_uv(blk, 0); on = pg.thwack_onsets(blk)
    i0, n_pre, n_post = pg.epoch_idx(d.shape[1], fs, t0, on, P["pre_ms"], P["post_ms"])
    live = np.ones(64, bool); live[19] = False
    rng = np.random.default_rng(0)
    def score(x):
        m, tr = pg.mean_response(x, i0, n_pre, n_post)
        peak, lat = pg.peak_in_window(m, n_pre, fs, P["win_ms"])
        nm, ns = pg.shuffled_null(x, len(i0), n_pre, n_post, fs, P["win_ms"], rng)
        return peak, lat, (np.abs(peak) - nm) / ns, m
    pr, lr, zr, mr = score(d)
    car = d - np.median(d[live], axis=0)[None, :]; car[19] = 0
    pc, lc, zc, mc = score(car)
    row5 = [32, 33, 34, 35, 36, 37]   # ch33-38 (0-based)
    out[site] = dict(block=b, n_thwacks=int(len(i0)),
                     raw_ch47_uv=float(pr[46]), raw_ch47_lat_ms=float(lr[46]), raw_ch47_z=float(zr[46]),
                     common_mode_uv=float(np.median(np.abs(pr[live]))),
                     car_ch47_uv=float(pc[46]), car_ch47_lat_ms=float(lc[46]), car_ch47_z=float(zc[46]),
                     car_row5_uv=float(np.mean(pc[row5])), car_row5_z=float(np.mean(zc[row5])),
                     car_footprint=int(((zc >= P["foot_z"]) & (np.abs(pc) >= 0.5 * np.abs(pc[np.argmax(zc)]))).sum()),
                     t_ms=[float(v) for v in (np.arange(mc.shape[1]) - n_pre) / fs * 1000.0],
                     car_ch47_trace=[float(v) for v in mc[46]], raw_ch47_trace=[float(v) for v in mr[46]])
    print("%-4s n=%3d raw ch47 %+6.0f uV z %5.1f | CM %5.0f uV | CAR ch47 %+6.0f uV @%4.1f ms z %5.1f | row5 %+5.1f uV z %4.1f | fp %d" %
          (site, len(i0), pr[46], zr[46], out[site]["common_mode_uv"], pc[46], lc[46], zc[46], out[site]["car_row5_uv"], out[site]["car_row5_z"], out[site]["car_footprint"]))
json.dump(out, open(os.path.join(OUT, "battery_sites.json"), "w"))
print("wrote battery_sites.json")
