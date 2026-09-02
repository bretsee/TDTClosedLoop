"""Merge the four ctl_* question JSONs into analysis/ctl_summary.json."""
import json
import os

import ctl_common as X

q = {}
for i in range(1, 5):
    with open(os.path.join(X.SCR, f"_ctl_q{i}.json")) as f:
        q[i] = json.load(f)

findings = [
    # Q1
    "BAD: amplitude transfer is absent in artifact-cleaned windows. Achieved y8 peak "
    "does not scale with the site's target peak: pooled slope MPC 0.12 [-0.08, 0.32], "
    "Choi 0.04 [-0.13, 0.28] (identity would be 1.0). Cleaned achieved peaks (~0.17-0.25 mV "
    "intercept) sit at the Hold noise floor (0.21 +/- 0.15 mV): the epoch-max statistic is "
    "mostly a noise max. Only weak positive signal: MPC Spearman rho=0.16 (p=0.045); Choi none.",
    "IMPORTANT reinterpretation: the overnight peak_ratio ~3x 'overshoot' was artifact-inflated "
    "- with ticks 0-2 excluded, achieved peaks drop to roughly target scale but are no longer "
    "target-dependent.",
    # Q2
    "GOOD: no order effects / adaptation. Same-site-predecessor vs different-site comparison "
    "is null in all 5 arm-runs (all p>=0.14, but underpowered: only 2-3 same-site transitions "
    "per run). The powered test - lag-1 autocorrelation of site-mean-removed peak residuals - "
    "is null in all 5 arm-runs (|ac|<=0.13, all p>=0.26 vs 1000x order-shuffle null), "
    "Hold included. Events are statistically independent; the paired analyses are safe.",
    # Q3
    "BAD (for selectivity): intent is NOT decodable from the y8 time course alone. LOO "
    "nearest-centroid 5-way accuracy: MPC 23% (p=0.24), Choi 19% (p=0.62), Hold 14% (p=0.91) "
    "vs ~20% chance; shape-only (correlation-distance) variant equally null. This does NOT "
    "rescue the 32-ch Mahalanobis negative - selectivity is absent in amplitude/time course "
    "too, consistent with Q1's flat amplitude transfer.",
    # Q4
    "MIXED: the overnight 'tie at best lag' does NOT fully survive window cleaning. With "
    "artifact ticks 0-2 excluded and per-event best lag (0..6), MPC leads: pooled dr=+0.079 "
    "[0.046, 0.112], p<1e-4, 65% win rate (n=161 pairs). The advantage is entirely r1 "
    "(dr=+0.163 [0.115, 0.209]); r2 remains a tie (dr=-0.006 [-0.041, 0.029]). The fixed-lag "
    "masked control (MPC +2, Choi r1 +1/r2 +2) still shows MPC ahead in r1 (+0.071 "
    "[0.026, 0.113]) - so the flip is caused by removing the artifact ticks, not by lag "
    "freedom: Choi r1's apparent parity was partly carried by artifact samples.",
    "Hold noise floor for best-lag masked r is 0.06 [0.03, 0.10] - the ~0.5-0.6 mean per-event "
    "r of both arms is far above selection optimism, so tracking itself is real in both arms.",
]

out = dict(
    workstream="B4 extended control analyses, 2026-08-31 acute data",
    conventions=dict(
        artifact_exclusion="relative ticks 0-2 post-onset removed from achieved y8 metrics",
        epoch="-30..+190 ticks re onset; baseline = first 25 pre ticks",
        best_lags={"MPC": 2, "Choi_r1": 1, "Choi_r2": 2},
        hold_control="capture_mpc_20260831_204354.csv scored against schedule/ref r1"),
    q1_amplitude_transfer=q[1],
    q2_order_effects=q[2],
    q3_intent_decoding=q[3],
    q4_paired_clean=q[4],
    findings=findings,
)
with open(os.path.join(X.SCR, "..", "ctl_summary.json"), "w") as f:
    json.dump(out, f, indent=1)
print("wrote ctl_summary.json;", len(findings), "findings")
