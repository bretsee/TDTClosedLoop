# Literature base for the closed-loop thalamic-stimulation program (built 2026-09-18)

Three annotated bibliographies, ~200 entries, each entry with citation, DOI/URL, a
method-and-findings summary and a one-line "relevance to our project". Starred entries
are must-reads. Each file ends with a synthesis section written for our methods.

| file | scope | entries | starred | synthesis section |
|---|---|---|---|---|
| `LIT_A_feedback_control_of_neural_activity.md` | MPC / LQR / optimal & adaptive control of neural circuits; closed-loop DBS & seizure control; Bayesian-opt & RL stim tuning; network controllability & rank; artifact suppression in the loop; drifting plants | 62 | 11 | "Themes and methods we should adopt" (16 bullets) |
| `LIT_B_biomimetic_sensory_stimulation.md` | Francis-lab lineage & thalamic prostheses (Choi 2016 methods verified); biomimetic ICMS encoding (Bensmaia, Micera); microstim physiology limiting selectivity/rank (Histed, Butovas, Millard/Stanley, thalamocortical depression); anesthesia; VPL somatotopy & electrode geometry; fidelity metrics | 75 | 12 | "Themes and methods we should adopt" (15 bullets) |
| `LIT_C_datadriven_NN_control.md` | NN forward models of stim responses; inverse/learned-policy control (distal teacher, RL, Koopman, GP-BO); system ID at low SNR/rank/drift (PSID, DFINE, adaptive); linear-vs-nonlinear comparisons; real-time deployment & data budgets | 60 | 11 | "Diagnosis and recommendations for our NN methodology" (19 bullets) |

## How to use these for methods (short version)

* **Rank collapse under tonic drive is expected and documented**: thalamocortical
  short-term depression (Chung, Li & Nelson 2002), post-ICMS inhibition (Butovas & Schwarz
  2003), burst vs tonic VPm transmission (Whitmire 2016; Swadlow & Gusev 2001), and the
  control-theoretic result that common continuous drive to a homogeneous ensemble only
  buys synchrony (Ching & Ritt 2013). Prescription = intermittent bursts with ≥ 100 ms
  recovery and a plant fitted on sparse-burst data (Millard 2013; Choi 2016 itself fit on
  sparse 3-18 Hz Poisson probing, not 100 Hz tonic). Implemented: `rig/design_burst_probe.py`.
* **Closest architectural analogue**: Bolus et al. 2021 (state-space feedback control of
  optogenetically driven activity) and Bolus 2018 (loop-rate/latency design space).
  Yang et al. 2021 (Nat Biomed Eng) shows the low-rank stim→network operator and uses
  amplitude AND frequency as inputs.
* **Non-negativity**: sit at a nonzero operating point and modulate (Gorzelic 2013 found
  integral bias the winning term); keep u ≥ 0 as a QP constraint, never post-hoc clipping.
* **Charge benchmarks** for feedback vs open loop: Little 2013 (56 %), Cagnan 2017 (< 50 %),
  Velisar 2019 (< 57 %). Our 29.5 % (acute #1) is modest; acute #2 reversed it via hold.
  Report charge above hold.
* **NN**: direct supervised inverse learning on a many-to-one rank-1 plant is the
  textbook distal-teacher failure (Jordan & Rumelhart 1992). Working recipes in the field:
  forward model + optimisation (Moure 2026; Bryan 2025; Steffen & Cannon 2025), residual on
  a linear controller, GP-BO for the outer pair/gain problem (Bonizzato 2023), ≥ 15-20 min
  of ID data per acute, adaptive/recursive fitting for drift (Yang, Ahmadipour & Shanechi
  2021), and validation by k-step forward prediction + interleaved closed-loop A/B.
* **Selectivity** is a placement/fibre-recruitment problem (Histed 2009; Kumaravelu 2022),
  not an amplitude one — consistent with our footprint analysis (all 8 pairs peak on ch64).

## Caveats
Each agent's web-search budget ran out near the end; entries flagged *[unverified]* or
"(indexed)" were cited from memory or resolved via doi.org only. A handful of author-lab
attributions were corrected in-file (Daly 2012 = Oweiss lab; Overstreet 2013 = Helms Tillery
lab; Bonizzato 2023 is Cell Reports Medicine). Weekend review: start with the starred
entries and the three synthesis sections.
