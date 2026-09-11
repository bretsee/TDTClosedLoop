# Control-Theoretic Novelty & Prior-Art Research Report
**Date:** 2026-09-09 (prepared for acute #2, 2026-09-10)
**Scope:** Choi 2016 identification; 2016–2026 landscape of model-based/closed-loop neurostimulation; novelty assessment of our real-time MPC biomimetic-template tracking demonstration; theory to invoke; field metrics to log tomorrow.
**Verification convention:** Every citation below was confirmed via web search/fetch on 2026-09-09 unless tagged **[STANDARD — cite from memory, verify DOI before submission]** or **UNVERIFIED**.

---

## 1. Choi 2016 — precise identification

**The paper is unambiguous. One candidate, confirmed by full-text fetch:**

> **Choi JS, Brockmeier AJ, McNiel DB, von Kraus LM, Príncipe JC, Francis JT (2016). "Eliciting naturalistic cortical responses with a sensory prosthesis via optimized microstimulation."** *Journal of Neural Engineering* 13(5):056007. DOI: [10.1088/1741-2560/13/5/056007](https://iopscience.iop.org/article/10.1088/1741-2560/13/5/056007)

**Method (verified from full text):**
- **Prep:** 9 female Long-Evans rats, urethane anesthesia, acute arrays in VPL thalamus (stim) and S1 (record). Same species/prep/pathway as ours.
- **Plant model:** discrete-time **linear state-space model identified by subspace ID** (~50 states), with a static nonlinear "gate" on each input channel to model per-channel stimulation thresholds. (Our ARX-at-tonic-bias approach linearizes around the same threshold phenomenon they gated.)
- **Stimulation:** symmetric biphasic pulses, 200 µs/phase, 8–16 bipolar configurations, 7–40 µA, amplitude-modulated envelope; signals at 610 Hz sample rate. (Our 610.35 Hz feature rate is the direct inheritance.)
- **Feedback signal:** S1 **LFP**, band-passed 5–200 Hz, 610 Hz — same output modality as ours.
- **Controller/optimization:** finite-horizon trajectory optimization posed as a **convex QP** with input non-negativity, amplitude bounds, quadratic input cost, and a low-pass-filtered-input penalty to suppress sustained stimulation. Horizon = touch hold duration + 50 ms (~200–300 ms). **This is MPC-style machinery, but it is NOT receding-horizon and NOT feedback:** the optimal input was computed **offline per touch condition** and then "applied through the VPL array" **open-loop**. Direct quote from the paper: *"Initially, the optimal control input was found for each touch condition (site, amplitude, duration) offline."* The paper does not use the terms MPC/receding horizon.
- **Claims/metrics:** natural-vs-evoked LFP correlation **r = 0.78 ± 0.05** overall, **0.90 ± 0.03** within 100 ms of touch onset; model VAF 39.0 ± 16.8% (400 ms post-stimulus); spatial reproduction 0.72 ± 0.22; touch-parameter classification of evoked responses 56–61% (vs natural); mutual information ≈ 4 bits, ~5.2 bits/s.

**Implication for us:** Choi 2016 = *offline model-based trajectory optimization, open-loop delivery, single-shot per condition*. Our system closes the loop in real time (receding-horizon QP at 100 Hz on live LFP features with a Kalman observer). That is exactly the gap the 2016 paper leaves open, and our "Choi-style tape" comparison arm is a faithful modernization of their approach — a strong paper structure ("we implement the lineage method as our baseline and beat it on stability/charge, tie on shape").

**Lineage papers (same lab, cite for continuity):**
- Choi JS et al. (2012). "An electric field model for prediction of somatosensory (S1) cortical field potentials induced by ventral posterior lateral (VPL) thalamic microstimulation." *IEEE TNSRE* (PubMed [22203725](https://pubmed.ncbi.nlm.nih.gov/22203725/)) — forward model precursor.
- Brockmeier AJ et al. (2011). "Optimizing microstimulation using a reinforcement learning framework." *IEEE EMBC* (PubMed [22254498](https://pubmed.ncbi.nlm.nih.gov/22254498/)) — early input-optimization attempt in the same program.
- Francis JT, Rozenboym A, von Kraus L, Xu S, Chhatbar P, Semework M, Hawley E, Chapin J (2022). "Similarities Between Somatosensory Cortical Responses Induced via Natural Touch and Microstimulation in the Ventral Posterior Lateral Thalamus in Macaques." *Front. Neurosci.* 16:812837. DOI: [10.3389/fnins.2022.812837](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2022.812837/full) — open-loop VPL MiSt vs touch in macaque; PSTHs highly correlated across modalities. Shows the lineage moved to NHP but stayed **open-loop** — strengthens our novelty claim.
- Related patents: "Biomimetic multichannel neurostimulation" US 9,974,957 / US 10,384,064 (Francis lineage). Worth checking claims before publication. **UNVERIFIED (titles only, from USPTO search hits).**

---

## 2. Landscape 2016–2026

### 2a. MPC / optimal control in neurostimulation (DBS, seizures)
- Tian Y, Saradhi S, Bello E, Johnson MD, D'Eleuterio G, Popovic MR, Lankarany M (2024). "Model-based closed-loop control of thalamic deep brain stimulation." *Frontiers in Network Physiology* 4:1356653. DOI: [10.3389/fnetp.2024.1356653](https://pmc.ncbi.nlm.nih.gov/articles/PMC11033853/) — **simulation-only** PID tracking of EMG power via Vim-DBS frequency; not real-time, not MPC.
- Fleming JE et al. "Model predictive control for closed-loop deep brain stimulation" ([Oxford ORA entry](https://ora.ox.ac.uk/objects/pubs:2024488)) and the follow-on **deep-learning MPC for DBS**: [arXiv:2504.00618](https://arxiv.org/html/2504.00618) (2025) — input-convex-network multi-step predictor + MPC on beta power; **simulation**; explicitly notes in-vivo closed-loop DBS to date has used only P/PI-type controllers.
- Chang & al., "Model Predictive Control for Seizure Suppression Based on Nonlinear Auto-Regressive Moving-Average Volterra Model." *IEEE TNSRE* 2020. ([IEEE](https://ieeexplore.ieee.org/iel7/7333/9216637/09162059.pdf), PubMed [32763855](https://pubmed.ncbi.nlm.nih.gov/32763855/)) — NARMA-Volterra plant + MPC; **simulation** on neural-mass models.
- Little S et al. (2013). "Adaptive deep brain stimulation in advanced Parkinson disease." *Ann Neurol* 74:449–457 **[STANDARD]** — the landmark in-vivo closed-loop stim, but threshold on/off logic, not model-based.
- Medtronic **BrainSense aDBS FDA approval, Feb 2025** (ADAPT-PD trial): first commercial adaptive DBS ([Medtronic press release](https://news.medtronic.com/2025-02-24-Medtronic-earns-U-S-FDA-approval-for-the-worlds-first-Adaptive-deep-brain-stimulation-system-for-people-with-Parkinsons)) — clinically deployed closed-loop is still simple LFP-band feedback, not MPC.
- **Cluster takeaway:** MPC in neurostimulation is nearly all *in silico*; deployed closed-loop systems use threshold/PI logic on band power. A real-time constrained QP MPC running in vivo on evoked LFP is ahead of this cluster.

### 2b. Biomimetic microstimulation for sensory feedback (Bensmaia/Pitt/Chicago lineage)
- Flesher SN et al. (2016). "Intracortical microstimulation of human somatosensory cortex." *Sci Transl Med* 8(361):361ra141. DOI: [10.1126/scitranslmed.aaf8083](https://www.science.org/doi/10.1126/scitranslmed.aaf8083) — human ICMS percepts; amplitude↔intensity mapping.
- Tabot GA et al. (2013). "Restoring the sense of touch with a prosthetic hand through a brain interface." *PNAS* 110(45):18279–84 **[STANDARD]** — psychometrically matched encoding in NHP.
- Bensmaia SJ & Miller LE (2014). "Restoring sensorimotor function through intracortical interfaces: progress and looming challenges." *Nat Rev Neurosci* 15:313–325 **[STANDARD]** — articulates the biomimetic-encoding program.
- Valle G et al. (2018). "Biomimetic intraneural sensory feedback enhances sensation naturalness, tactile sensitivity, and manual dexterity in a bidirectional prosthesis." *Neuron* 100(1):37–45. ([Cell Press](https://www.cell.com/neuron/fulltext/S0896-6273(18)30738-4)) — biomimetic > non-biomimetic on naturalness/dexterity (peripheral).
- George JA et al. (2019). "Biomimetic sensory feedback through peripheral nerve stimulation improves dexterous use of a bionic hand." *Sci Robotics* 4(32):eaax2352. DOI: [10.1126/scirobotics.aax2352](https://www.science.org/doi/10.1126/scirobotics.aax2352).
- Greenspon CM et al. (2024). "Evoking stable and precise tactile sensations via multi-electrode intracortical microstimulation of the somatosensory cortex." *Nat Biomed Eng*. DOI: [10.1038/s41551-024-01299-z](https://www.nature.com/articles/s41551-024-01299-z); and "Tactile edges and motion via patterned microstimulation of the human somatosensory cortex." *Science* (2025). DOI: [10.1126/science.adq5978](https://www.science.org/doi/10.1126/science.adq5978) — state of the art in *spatial patterning*, still open-loop encoders.
- Recent review worth citing: "Optimization frameworks for bespoke sensory encoding in neuroprosthetics" (2025; PubMed [40401149](https://pubmed.ncbi.nlm.nih.gov/40401149/)).
- **Cluster takeaway:** the entire biomimetic-encoding program — including 2024–2025 human work — is **feed-forward**: encoder maps sensor → stim, no neural-response feedback during delivery. Nobody in this cluster measures whether the *evoked cortical response* actually matches the biomimetic target on-line.

### 2c. Thalamic sensory microstimulation / thalamocortical prosthesis
- Daly J, Liu J, Aghagolzadeh M, Oweiss K (2012). "Optimal space-time precoding of artificial sensory feedback through mutichannel microstimulation in bi-directional brain machine interfaces." *J Neural Eng* 9(6):065004. DOI: [10.1088/1741-2560/9/6/065004](https://pmc.ncbi.nlm.nih.gov/articles/PMC5988221) — information-theoretic MIMO precoder (water-filling) for thalamic stim; **simulation, open-loop**. The closest *conceptual* MIMO precursor for tomorrow's experiment.
- Francis et al. 2022 macaque VPL study (see §1).
- Swan BD / Heming E / Kiss ZH-type human thalamic percept studies: "Sensory percepts induced by microwire array and DBS microstimulation in human sensory thalamus." *Brain Stimulation* 2018. ([PMC5803348](https://pmc.ncbi.nlm.nih.gov/articles/PMC5803348/)) — human VC thalamus percepts are focal and amplitude-modulated; supports clinical relevance of the thalamic target.
- Kumaravelu/Weber DRG work (pre-2016) established microstimulation of primary afferents as the peripheral analog **[STANDARD — lineage context only]**.
- **Cluster takeaway:** thalamic sensory stimulation is a recognized but sparsely-populated alternative to ICMS; nobody besides the Choi/Francis lineage optimizes it against recorded cortical templates, and nobody closes a loop on it.

### 2d. Closed-loop control of neural population activity (the control-engineering cluster)
- Bolus MF, Willats AA, Rozell CJ, Stanley GB (2021). "State-space optimal feedback control of optogenetically driven neural activity." *J Neural Eng* 18:036006. DOI: [10.1088/1741-2552/abb89c](https://iopscience.iop.org/article/10.1088/1741-2552/abb89c) — LDS plant + LQ integral control + **parameter-adaptive Kalman filter**, real-time control of thalamic firing rate in awake mice. The best methodological sibling to our system — but **optogenetic input, scalar firing-rate reference, regulation not template tracking**.
- Bolus MF et al. (2018). "Design strategies for dynamic closed-loop optogenetic neurocontrol in vivo." *J Neural Eng* 15:026011. ([IOP](https://iopscience.iop.org/article/10.1088/1741-2552/aaa506)).
- Newman JP et al. (2015). "Optogenetic feedback control of neural activity." *eLife* 4:e07192. ([eLife](https://elifesciences.org/articles/07192)).
- Yang Y, Qiao S, Sani OG, ... Shanechi MM (2021). "Modelling and prediction of the dynamic responses of large-scale brain networks during direct electrical stimulation." *Nat Biomed Eng* 5:324–345. DOI: [10.1038/s41551-020-00666-w](https://www.nature.com/articles/s41551-020-00666-w) — MIMO LSSM of stim→LFP network dynamics in awake macaques; **prediction only, no closed loop**; the standard citation legitimizing linear MIMO stim→LFP plants.
- Tafazoli S, MacDowell CJ, Che Z, Letai KC, Steinhardt CR, Buschman TJ (2020). "Learning to control the brain through adaptive closed-loop patterned stimulation." *J Neural Eng* 17:056007. DOI: [10.1088/1741-2552/abb860](https://iopscience.iop.org/article/10.1088/1741-2552/abb860) — **model-free** iterative (trial-to-trial) learning of multi-site electrical stim patterns to reproduce visually evoked population responses in awake mouse V1; converges in ~15 min. Closed-loop *across trials*, not within-trial feedback control.
- **Barzon G, De A, Moran I, Carnahan C, Mazzucato L, Kiani R (2026). "Control of cortical population activity with patterned microstimulation" (REACH-Ctrl).** bioRxiv, posted 2026-03-04 *(sic — server-listed date; treat the date with caution)*. DOI: [10.64898/2026.03.02.709018](https://www.biorxiv.org/content/10.64898/2026.03.02.709018v1); PubMed [41867762](https://pubmed.ncbi.nlm.nih.gov/41867762/) — data-driven (Willems' Fundamental Lemma) controllability map for patterned microstimulation of awake macaque prefrontal populations; minimum-energy inputs steer spiking toward **static target states** over short horizons (T≈3 pulses, 15 µA); accuracy r = 0.735 ± 0.017 vs 0.35 shuffled. Test-block sequences are **pre-computed** (controller designed online after training, but delivery is open-loop) and authors state limits: "short horizons, weak perturbations, resting states."
- Muldoon SF et al. (2016). "Stimulation-Based Control of Dynamic Brain Networks." *PLOS Comput Biol* 12:e1005076. ([PLOS](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005076)); Gu S et al. (2015). "Controllability of structural brain networks." *Nat Commun* 6:8414. ([Nature](https://www.nature.com/articles/ncomms9414)) — network-controllability/Gramian framing (see §4).
- **Cluster takeaway:** real-time within-trial feedback control of brain activity in vivo exists (Bolus — optogenetics, scalar rate), and pattern-reproduction via electrical stim exists (Tafazoli — model-free trial-iterative; REACH-Ctrl — static targets, precomputed inputs). **Nobody combines: electrical microstimulation input + within-trial LFP feedback + receding-horizon MPC + time-varying biomimetic template reference.**

### 2e. Current steering & selectivity
- Bonham & Litvak (2008). "Current focusing and steering: modeling, physiology, and psychophysics." *Hear Res* (cochlear). ([PMC2562351](https://pmc.ncbi.nlm.nih.gov/articles/PMC2562351/)).
- Butson & McIntyre (2008). "Current steering to control the volume of tissue activated during deep brain stimulation." *Brain Stimul* 1:7–15 **[STANDARD — confirmed via ResearchGate hit]**.
- "Improved focalization of electrical microstimulation using microelectrode arrays: a modeling study." *PLOS ONE* 2009. ([PLOS](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0004828)) — multipolar return-current field shaping.
- "Leveraging current steering and the biophysics of spike generation for cellular-resolution electrical stimulation" (bioRxiv 2025, [PDF](https://www.biorxiv.org/content/10.1101/2025.03.14.643392.full.pdf)) and "Intracortical bipolar stimulation allows selective activation of neuronal populations" (bioRxiv 2025, [PDF](https://www.biorxiv.org/content/10.1101/2025.03.21.644593.full.pdf)) — current state of the art on selectivity via electrode-level field shaping.
- **Cluster takeaway:** selectivity in the literature is attacked at the *electrode/field* level, not at the *controller* level. Our rank-3 finding says the plant, not the controller, caps selectivity — consistent with this cluster's premise that you must change the input geometry (more/steered pairs) to buy rank. That is precisely the MIMO upgrade tomorrow.

---

## 3. Novelty assessment

**Question 1: Has anyone demonstrated real-time *feedback* MPC tracking of biomimetic cortical response templates via thalamic microstimulation in vivo?**
**Answer: No — not that this search could find.** The closest items each miss at least one pillar. Ranked closest prior art:

| Rank | Work | What it shares | What it lacks vs ours |
|---|---|---|---|
| 1 | **Choi et al. 2016** (J Neural Eng) | Same pathway (VPL→S1, rat), same output (S1 LFP @610 Hz), same objective (match natural-touch templates), QP with input constraints | **Open-loop**: offline finite-horizon optimization, single-shot playback; no observer, no receding horizon, no disturbance rejection; no drift/charge analysis |
| 2 | **Bolus et al. 2021** (J Neural Eng) | Real-time in-vivo state-space feedback control with Kalman estimation, adaptive to model mismatch | Optogenetic (no stim artifact problem, no charge constraint), scalar firing-rate **regulation** (set-point, not time-varying biomimetic template), LQ not constrained MPC, thalamus is the *output* not the input |
| 3 | **Tafazoli et al. 2020** (J Neural Eng) | Electrical multi-site stim reproducing naturally evoked population patterns, closed-loop adaptation | Model-free, **trial-to-trial** iteration (~15 min convergence) — no within-trial feedback, no dynamics model, no predictive control, spiking not LFP |
| 4 | **Barzon/Kiani REACH-Ctrl 2026** (bioRxiv) | Patterned microstimulation steering cortical population activity; minimum-energy optimal inputs; data-driven linear control | **Static targets**, horizon ≈ 3 pulses, delivery pre-computed (no within-trial feedback), prefrontal spiking, no biomimetic/sensory objective. Being 2026 and high-profile, cite it prominently and differentiate carefully |
| 5 | **Yang et al. 2021** (Nat Biomed Eng) | MIMO LTI modeling of electrical stim → multiregional LFP in awake NHP | Prediction/system-ID only; no control loop closed |
| 6 | **Daly/Oweiss 2012** (J Neural Eng) | MIMO optimal precoding of thalamic stim for cortical response shaping | Simulation only; information-theoretic open-loop precoder |
| 7 | DBS-MPC cluster (Tian 2024; arXiv 2504.00618; NARMA-Volterra MPC 2020) | MPC formalism on neural feedback signals | All simulation; regulation of band power, not template tracking; therapeutic not sensory objective |

**Question 2: Has anyone done the MIMO version (multi-site stim → multi-channel cortical targets, feedback)?**
**Answer: No feedback version found.** MIMO *modeling* exists (Yang 2021), MIMO *open-loop input design* exists (Daly 2012 in silico; Choi 2016 used 8–16 bipolar inputs but optimized open-loop; REACH-Ctrl steers multi-channel spiking with precomputed multi-electrode pulse patterns; Greenspon/Valle 2024–25 pattern multiple ICMS electrodes feed-forward). A within-trial vector-reference MPC over p=2–4 cortical outputs and up to 8 stim pairs would, on this evidence, be first-in-class. **If tomorrow yields even 2×2 tracking, claim it as the first MIMO feedback-controlled biomimetic sensory stimulation in vivo.**

**Honest weaknesses in the novelty claim:**
1. "MPC for neurostimulation" as a phrase is not new — the DBS/seizure literature has used it (in simulation) for a decade, and Choi 2016's QP is essentially one iteration of MPC. The defensible claim is the *combination*: **real-time, in vivo, receding-horizon, constrained, output-feedback, time-varying biomimetic reference, electrical sensory pathway**. State it exactly that way.
2. Tracking r≈0.71 does not beat Choi's reported 0.78 open-loop correlation (different metric conditions; theirs was natural-vs-evoked over selected windows). Do not lead with raw r; lead with **tie-on-shape + wins on drift, latency stability, and 29.5% charge** — the things feedback uniquely buys.
3. Tafazoli and REACH-Ctrl both "control cortical patterns with electrical stimulation"; a hostile reviewer will conflate. Pre-empt with the within-trial-feedback vs across-trial/precomputed distinction, and with the sensory-template objective.
4. The no-selectivity negative result is anticipated by the field-shaping literature — frame it as a *quantified control-theoretic* explanation (rank-1 SISO ceiling, rank-3 plant) rather than a surprise.

---

## 4. Optimality & theory to invoke

### Framing (paper-level)
- **Constrained-MPC optimality:** receding-horizon QP with hard input constraints (0 ≤ u ≤ 30 µA) is the *correct* formalism because the binding constraint in this plant is non-negativity (your prior finding). Cite standard MPC texts (Rawlings, Mayne & Diehl, *Model Predictive Control*, 2017) **[STANDARD]** and note that saturation makes LQR suboptimal — MPC's constraint handling is not cosmetic here.
- **Charge-minimal stimulation:** the input-energy term in the QP is a per-sample charge penalty; connect to Wongsarnpigoon & Grill (2010), "Energy-efficient waveform shapes for neural stimulation revealed with a genetic algorithm," *J Neural Eng* 7:046009. DOI: [10.1088/1741-2560/7/4/046009](https://iopscience.iop.org/article/10.1088/1741-2560/7/4/046009); and safety limits per Shannon (1992), *IEEE TBME* 39:424–426 **[STANDARD]**. Your 29.5% charge saving is the closed-loop analog of their waveform-level efficiency: feedback stops paying for output the plant is already producing.
- **Selectivity as output controllability:** with m inputs, an LTI plant's steady-state achievable output set has rank ≤ rank of the DC gain matrix; SISO ⇒ rank 1, explaining the selectivity null exactly. Frame measured rank ~3 as the **output-controllability Gramian's effective rank** (participation of output directions reachable at bounded input energy). Cite Gu et al. 2015 *Nat Commun* ([10.1038/ncomms9414](https://www.nature.com/articles/ncomms9414)) and Muldoon et al. 2016 *PLOS Comput Biol* ([10.1371/journal.pcbi.1005076](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005076)) for brain-network Gramian framing; REACH-Ctrl's "reachable manifold" is the same object estimated data-driven — useful convergent language.
- **Preview control:** your references are known in advance (templates), so the MPC is really *preview* MPC — the horizon sees the future reference. This is a legitimate structural advantage over reactive controllers; cite standard preview-control literature (Tomizuka 1975) **[STANDARD]**. Reference governors (Garone, Di Cairano, Kolmanovsky 2017, *Automatica* survey) **[STANDARD]** are the right cite if you later add safety supervision (charge/amplitude governor wrapping the MPC).
- **Adaptive/learning MPC for nonstationary preps:** Bolus 2021's parameter-adaptive Kalman filter is the in-vivo precedent for handling drift inside the observer rather than the model; robust adaptive MPC with persistent excitation ([arXiv:2211.09275](https://arxiv.org/pdf/2211.09275)) is the control-theory anchor; the deep-learning DBS MPC ([arXiv:2504.00618](https://arxiv.org/html/2504.00618)) is the neuro-flavored version. Your observed open-loop decay (−0.13 r / 100 events) vs zero closed-loop decay is *empirical evidence that output feedback substitutes for model adaptation over acute timescales* — a clean, quotable claim.

### (a) Implementable before tomorrow (existing C++ MPC, no new algorithms)
1. **Log the QP telemetry needed for optimality claims:** per-solve cost value, constraint-active flags (which samples hit 0 or 30 µA), OSQP iterations/solve time, predicted-vs-realized output error at horizon head. Active-set fraction is the evidence that constrained MPC (not LQR) was necessary.
2. **Charge accounting per run:** cumulative Σ|u|·pulse-width per channel, per trial and per run, for MPC vs tape arms. This is your headline efficiency metric; make sure it's computed identically for both arms.
3. **Drift instrumentation:** timestamp every event; log per-event tracking r in a sliding window so the decay-slope comparison (r per 100 events) is automatic. Also log baseline LFP feature mean/variance between trials (prep-state covariate).
4. **MIMO conditioning check at setup time:** after fitting the block-diagonal MIMO ARX, compute and log the DC gain matrix G(1) and its singular values. σ1/σp tells you immediately whether the p output channels are independently steerable with your chosen stim pairs — if effective rank < p, re-select output channels *before* burning trials. This operationalizes the rank-3 result.
5. **Weight/horizon hygiene:** keep the output-weight matrix Q diagonal but normalized per-channel by baseline feature variance (so no channel dominates the vector reference); keep the same λ (input penalty) across SISO and MIMO arms so charge comparisons stay interpretable; horizon ≥ plant settling time (your ARX impulse response length) + preview of the template's fastest transient.
6. **Per-arm identical references:** for the MPC-vs-tape comparison, feed both from the same template file and log the template ID/hash per trial.
7. **Latency logging:** hardware timestamps for feature-ready → QP-solved → DAC-updated, every cycle. The field reports loop latency; you already have ~20 ms — log its distribution, not just the mean.

### (b) Paper-framing / future work
- Observer/plant adaptation: RLS or interacting-multiple-model re-fit of ARX gain online (Bolus-style adaptive noise estimation first — cheapest).
- Formal output-controllability analysis: compute the finite-horizon output reachability Gramian of the fitted MIMO model; report its eigenspectrum against the measured rank ~3; predict achievable selectivity as a function of number of stim pairs.
- Economic/charge-optimal MPC: move charge from a quadratic penalty to an explicit ℓ1 term or a constraint (charge budget per 100 ms), connecting to Shannon-limit safety framing.
- Reference governor for safety supervision when moving toward chronic/awake preps.
- Nonlinearity: Choi's threshold "gate" suggests a Hammerstein extension (static input nonlinearity + your LTI core) as the obvious next model class; cite Choi 2016 as motivation.

---

## 5. Field metrics — what to log tomorrow so comparisons are publishable

From the clusters above, published quantitative vocabulary:

| Metric family | Field usage | What we should log |
|---|---|---|
| **Tracking/shape fidelity** | Choi 2016: r natural-vs-evoked (0.78 overall, 0.90 first 100 ms), VAF 39%, spatial reproduction 0.72; Tafazoli 2020: pattern-similarity convergence; REACH-Ctrl: target-vs-evoked r = 0.735 ± 0.017 vs shuffled 0.35 | Per-trial r at zero lag AND at best lag (report both), VAF, per-channel r for MIMO, shuffled-template null distribution (REACH-Ctrl's control — adopt it) |
| **Decoding evoked vs natural** | Choi 2016: touch-site/parameter classification 56–61%, MI ≈ 4 bits, 5.2 bits/s; Francis 2022: PSTH correlations across modalities | Off-line decode of touch site from evoked multichannel responses (this is the selectivity test — rank story lives here); report classifier accuracy + confusion matrix + MI |
| **Charge/energy** | Wongsarnpigoon & Grill: energy per activation; ICMS human work reports µA amplitude and charge/phase vs safety limits; REACH-Ctrl: minimum-energy inputs at 15 µA | Total charge per trial, charge per unit tracking (nC per unit r or per event), % time at constraint bounds, charge/phase vs Shannon k-value |
| **Latency** | Closed-loop field reports loop delay (Bolus: ms-scale actuation; aDBS: seconds-scale) | Full loop-latency distribution (feature→DAC), controller jitter, and tracking-lag (best-lag offset) per run — our latency *stability* win needs a distribution, not a mean |
| **Stability/drift** | Rarely quantified — our decay-slope metric (Δr per 100 events) appears to be novel; aDBS papers report within-session consistency; Greenspon 2024 reports percept stability across sessions | Decay slope per arm, per run; baseline LFP drift covariates; observer innovation magnitude over time (evidence the Kalman is absorbing drift) |
| **Naturalness (perceptual)** | Valle 2018 / George 2019 / Flesher 2021-era: naturalness ratings, task performance | N/A in anesthetized prep — but note in paper that template-tracking is the physiological proxy for perceptual naturalness (cite Bensmaia & Miller 2014 for the premise) |

**One adoption worth making tonight:** REACH-Ctrl's *shuffled-target null* (evaluate tracking r against mismatched templates) — cheap to compute offline, and it converts "r = 0.71" into "r = 0.71 vs 0.3x null," which is how 2026 reviewers will want it.

---

## Actionable for 2026-09-10

**Before first stim:**
- [ ] After MIMO ARX fit: log DC-gain matrix singular values; if effective rank < p, swap output channels before proceeding (§4a-4).
- [ ] Confirm Q normalization per-channel by baseline feature variance; same λ across arms (§4a-5).
- [ ] Confirm horizon ≥ ARX settling + template-transient preview.

**Logging (verify each is on before the first tracked trial):**
- [ ] Per-cycle: feature timestamp, QP solve time, OSQP iters, cost, active-constraint mask, u vector, predicted output.
- [ ] Per-trial: template ID/hash, per-channel r (zero-lag and best-lag), VAF, total charge per channel, event index + wall clock.
- [ ] Per-run: baseline LFP feature stats between trials; observer innovations.
- [ ] Both arms (MPC + Choi-style tape) driven from identical template files.

**Design points that buy claims:**
- [ ] At least one MIMO run with p ≥ 2 independent templates on the two output channels (distinct time courses) — this is the "vector-reference tracking" figure, and the first-in-class MIMO claim (§3 Q2).
- [ ] One run with deliberately mismatched (shuffled) templates for the null distribution (§5).
- [ ] Repeat one condition early and late in the session — powers the drift-slope comparison.
- [ ] If time permits: vary number of active stim pairs (2 vs 4 vs 8) on the same template set — the rank-vs-inputs curve is the selectivity story's positive counterpart.

**Post-hoc (this week):**
- [ ] Compute output-reachability Gramian spectrum of the fitted MIMO model; compare to measured rank ~3.
- [ ] Decode touch site from MIMO evoked responses (selectivity re-test with p > 1).
- [ ] Read REACH-Ctrl (Barzon et al., bioRxiv 2026) and Tafazoli 2020 in full before writing — they are the two citations a reviewer will raise.
- [ ] Check claims of Francis-lineage patents US 9,974,957 / US 10,384,064 (UNVERIFIED beyond titles).
