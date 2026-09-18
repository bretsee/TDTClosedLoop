# Literature Review A — Feedback / Closed-Loop / Optimal / Adaptive Control of Brain Activity

**Compiled:** 2026-09-18
**Scope:** Control-theoretic paradigms applied to brain activity, prioritized 2015–2026 plus foundational works.
**Project context:** VPL thalamic microstimulation (8 bipolar pairs, 100 Hz carrier, amplitude-modulated at ~100 Hz control ticks) driving S1 cortex (64-ch planar LFP) in anesthetized rat, with a real-time condensed-QP linear MPC (Luenberger/Kalman observer, ARX-identified LTI plant) benchmarked against the lab's prior open-loop QP-optimized stimulation (Choi et al. 2016) and NN inverse controllers.

**Entry count: 62.** Must-reads flagged with ★ (11 flagged).

**Verification note.** Every DOI below was either resolved through doi.org (confirming the DOI string maps to the stated publisher record) or retrieved from the publisher / Europe PMC. Where a landing page was paywalled or bot-blocked, the DOI resolution still confirms the identifier; in the few cases where an exact page range or author ordering could not be confirmed from a fetched record, the entry says so explicitly rather than guessing. Items marked *(preprint)* have not been confirmed as journal-published.

---

## Category 1 — MPC, LQR/LQG, optimal control and system identification of neural circuits under electrical/optogenetic stimulation

### ★ 1.1 Bolus, Willats, Rozell & Stanley (2021)
*State-space optimal feedback control of optogenetically driven neural activity.* **Journal of Neural Engineering** 18(3):036006.
DOI: [10.1088/1741-2552/abb89c](https://doi.org/10.1088/1741-2552/abb89c) · Preprint: [bioRxiv 2020.06.25.171785](https://www.biorxiv.org/content/10.1101/2020.06.25.171785v1)

Fits state-space (linear dynamical system) models of single- and multi-neuron firing-rate responses to optogenetic drive in awake mouse thalamocortical circuit, then closes the loop with a Kalman-filter-plus-LQ-optimal controller running in real time. This is the first experimental application of state-space *model-based* feedback control to optogenetic stimulation, as opposed to PI/threshold heuristics. Demonstrates tracking of time-varying firing-rate targets and explicitly analyzes how model mismatch and observer tuning limit closed-loop performance.

**Relevance:** This is the closest published analogue to our architecture (identified LTI plant + observer + optimal feedback on a stimulated sensory circuit), and is the single best template for how to report MPC-vs-open-loop comparisons. Borrow their observer-tuning methodology and their framing of "how much of the residual error is model mismatch vs. process noise."

### ★ 1.2 Bolus, Willats, Whitmire, Rozell & Stanley (2018)
*Design strategies for dynamic closed-loop optogenetic neurocontrol in vivo.* **Journal of Neural Engineering** 15(2):026011.
DOI: [10.1088/1741-2552/aaa506](https://doi.org/10.1088/1741-2552/aaa506)

The design-space companion to 1.1: systematically compares controller structures (PI vs. model-based), feature/observation choices, loop rates, and the effect of latency and measurement noise on closed-loop optogenetic firing-rate control in vivo. Provides concrete guidance on how much the control rate and smoothing of the feedback signal matter relative to the plant's own time constants.

**Relevance:** Directly informs our 100 Hz tick-rate and LFP feature-smoothing choices; their latency/filtering trade-off analysis is the argument we should reproduce for why a 100 Hz loop is (or is not) fast enough given the S1 LFP response time constants.

### ★ 1.3 Yang, Qiao, Sani, Sedillo, Ferrentino, Pesaran & Shanechi (2021)
*Modelling and prediction of the dynamic responses of large-scale brain networks during direct electrical stimulation.* **Nature Biomedical Engineering** 5(4):324–345.
DOI: [10.1038/s41551-020-00666-w](https://doi.org/10.1038/s41551-020-00666-w)

Builds linear dynamic input–output (state-space) models mapping stimulation amplitude and frequency to multiregional LFP network activity in two awake macaques. Shows responses are modulated by both amplitude and frequency and exhibit damping and oscillatory dynamics that a low-order linear model predicts well; critically, the identified input-output maps are **low-rank / low-dimensional** relative to the number of recording sites.

**Relevance:** The central external precedent for our rank collapse observation — they too find the stim→network operator is low-dimensional. Borrow their input-design (amplitude *and* frequency modulation, not amplitude alone) as a lever for recovering response diversity, and their model-order selection procedure.

### ★ 1.4 Yang, Connolly & Shanechi (2018)
*A control-theoretic system identification framework and a real-time closed-loop clinical simulation testbed for electrical brain stimulation.* **Journal of Neural Engineering** 15(6):066007.
DOI: [10.1088/1741-2552/aad1a8](https://doi.org/10.1088/1741-2552/aad1a8)

Develops a data-driven linear state-space sysID framework for electrical brain stimulation and — the key methodological contribution — designs an input waveform consisting of a **pulse train modulated by stochastic binary noise**, which is near-optimal for informative identification while respecting clinical safety/charge constraints. Pairs this with a real-time closed-loop simulation testbed.

**Relevance:** The stochastic-binary-modulated pulse train is exactly the excitation design we should adopt for ARX identification under a unipolar, charge-limited command — it solves the "how do I get persistent excitation when I can only push charge one way" problem directly.

### 1.5 Yang & Shanechi (2016)
*An adaptive and generalizable closed-loop system for control of medically induced coma and other states of anesthesia.* **Journal of Neural Engineering** 13(6):066019.
DOI: [10.1088/1741-2560/13/6/066019](https://doi.org/10.1088/1741-2560/13/6/066019)

Removes the need for a separate offline identification experiment by estimating model parameters adaptively *during* closed-loop control, with stability/performance guarantees. Motivated explicitly by the fact that offline-estimated models are biased by non-stationarity and time-variation of the plant.

**Relevance:** This is the recipe for handling our ~30 min gain drift without stopping to re-identify: adapt the plant parameters inside the loop rather than re-running a separate sysID block.

### 1.6 Yang, Lee, Guidera, Vlasov, Pei, Brown, Solt & Shanechi (2019)
*Developing a personalized closed-loop controller of medically-induced coma in a rodent model.* **Journal of Neural Engineering** 16(3):036022.
DOI: [10.1088/1741-2552/ab0ea4](https://doi.org/10.1088/1741-2552/ab0ea4)

Real-time adaptive control of EEG burst suppression in rats, tracking individual and *within-session* variation in brain responsiveness to the input. Tracking these variations reduced control error by more than 70% relative to a non-adaptive controller.

**Relevance:** A rodent, within-session, drifting-gain demonstration with a headline number (>70% error reduction from adaptation) that we can cite as the expected payoff from making our MPC gain-adaptive.

### 1.7 Shanechi, Chemali, Liberman, Solt & Brown (2013)
*A brain-machine interface for control of medically-induced coma.* **PLoS Computational Biology** 9(10):e1003284.
DOI: [10.1371/journal.pcbi.1003284](https://doi.org/10.1371/journal.pcbi.1003284)

Derives a recursive Bayesian binary filter to estimate burst-suppression probability from EEG, then compares **LQR and model-predictive control** strategies driving drug infusion in individual rodents, achieving median performance error 3.6% across dynamic target trajectories.

**Relevance:** One of the few papers that puts LQR and MPC head-to-head on the same neural plant with the same observer — a direct model for our MPC-vs-alternatives comparison table.

### 1.8 Sani, Abbaspourazad, Wong, Pesaran & Shanechi (2021)
*Modeling behaviorally relevant neural dynamics enabled by preferential subspace identification (PSID).* **Nature Neuroscience** 24:140–149.
DOI: [10.1038/s41593-020-00733-0](https://doi.org/10.1038/s41593-020-00733-0) · Code: [github.com/ShanechiLab/PyPSID](https://github.com/ShanechiLab/PyPSID)

Subspace identification that explicitly *prioritizes* the dynamics relevant to a target signal rather than those that merely dominate neural variance. Finds behaviorally relevant dynamics are far lower-dimensional than variance-based methods imply.

**Relevance:** Our plant should be identified to predict the **touch-response subspace**, not the dominant LFP variance (which stimulation artifact and tonic drive will dominate). PSID is the right tool for fitting a plant whose output target is "the natural touch response," and directly addresses why a rank-1 variance-dominant mode may be the wrong thing to control.

### 1.9 Abbaspourazad, Erturk, Pesaran & Shanechi (2024)
*Dynamical flexible inference of nonlinear latent factors and structures in neural population activity (DFINE).* **Nature Biomedical Engineering** 8:85–108.
DOI: [10.1038/s41551-023-01106-1](https://doi.org/10.1038/s41551-023-01106-1)

Learns nonlinear latent manifold structure while retaining a *linear* dynamical model on the manifold, so that Kalman-style recursive (and flexible/missing-data) inference remains available in real time.

**Relevance:** The principled escape hatch if our LTI plant proves inadequate under tonic saturation — keeps real-time observer tractability while allowing a nonlinear (saturating) output map, which is precisely the tonic-saturation nonlinearity we measured.

### 1.10 Millard, Wang, Gollnick & Stanley (2013)
*System identification of the nonlinear dynamics in the thalamocortical circuit in response to patterned thalamic microstimulation in vivo.* **Journal of Neural Engineering** 10(6):066011.
DOI: [10.1088/1741-2560/10/6/066011](https://doi.org/10.1088/1741-2560/10/6/066011)

Nonlinear (Wiener/Volterra-style) system identification of the cortical response to *patterned* single-electrode VPm microstimulation in rodent, with voltage-sensitive dye imaging of S1. Characterizes strong adaptation/saturation of the cortical response to sustained stimulus trains.

**Relevance:** The most direct methodological precedent for our exact preparation (thalamic microstim → rodent S1). Their adaptation nonlinearity is very likely the same mechanism as our tonic-drive rank collapse; their model structure is the natural first nonlinear extension of our ARX plant.

### 1.11 Schiff & Sauer (2008)
*Kalman filter control of a model of spatiotemporal cortical dynamics.* **Journal of Neural Engineering** 5(1):1–8.
DOI: [10.1088/1741-2560/5/1/001](https://doi.org/10.1088/1741-2560/5/1/001)

Uses unscented Kalman filtering to observe state and estimate parameters in a spatiotemporal excitable cortical model, then computes control signals delivered via applied electric fields to control wave frequency or quench patterns while minimizing control energy.

**Relevance:** Foundational statement of "observer first, then minimum-energy control" for a spatially distributed cortical plant — the conceptual ancestor of our observer + charge-penalized QP.

### ★ 1.12 Schiff, S.J. (2012)
*Neural Control Engineering: The Emerging Intersection between Control Theory and Neuroscience.* **MIT Press**, Computational Neuroscience series. ISBN 9780262015370 (reissue 9780262546713).
URL: [mitpress.mit.edu/9780262546713](https://mitpress.mit.edu/9780262546713/neural-control-engineering/)

Book-length treatment: linear and nonlinear Kalman filtering, observability/controllability for neural models, Hodgkin–Huxley and neural-field plants, and worked control applications to Parkinson's disease and epilepsy including control via electric fields.

**Relevance:** The standard reference to cite for observer design and for the "why a linear observer on a nonlinear neural plant is defensible" argument. Chapters on ensemble Kalman filtering are the reference for our Luenberger-vs-Kalman choice.

### 1.13 Ritt & Ching (2015)
*Neurocontrol: Methods, models and technologies for manipulating dynamics in the brain.* **Proc. American Control Conference (ACC) 2015**, pp. 3765–3780.
DOI: [10.1109/ACC.2015.7171915](https://doi.org/10.1109/ACC.2015.7171915)

Tutorial survey of the control-engineering/neuroscience boundary. Frames the core difficulty as **severe underactuation** — controlling a large neural population through one or a few input channels — compounded by unknown nonlinear dynamics.

**Relevance:** The canonical citation for our central problem statement: 8 stimulation channels driving a 64-channel cortical output whose reachable set collapses to rank ~1. Use their underactuation framing in the paper's introduction.

### 1.14 Ching & Ritt (2013)
*Control strategies for underactuated neural ensembles driven by optogenetic stimulation.* **Frontiers in Neural Circuits** 7:54.
DOI: [10.3389/fncir.2013.00054](https://doi.org/10.3389/fncir.2013.00054)

Analyzes spike control for ensembles of uncoupled neurons sharing a *common* input. Key result: **parameter heterogeneity across neurons is constructive** — it is precisely the heterogeneity that lets a single common drive produce non-synchronous, differentiated responses; a homogeneous ensemble under common drive can only be driven synchronously.

**Relevance:** A theoretical explanation for our rank-1 collapse and a prescription: under continuous common drive the ensemble synchronizes and diversity vanishes. Recovering rank requires exploiting heterogeneity in the *temporal* domain (bursts, offsets, per-channel phase) rather than more amplitude.

### 1.15 Nandi, Kafashan & Ching (2018)
*Control analysis and design for statistical models of spiking networks.* **IEEE Transactions on Control of Network Systems** 5(4):1146–1156.
DOI: [10.1109/TCNS.2017.2687824](https://doi.org/10.1109/TCNS.2017.2687824)

Develops controllability analysis for point-process GLM network models, quantifying how easy or hard it is to induce a desired spiking pattern with an extrinsic input, and turns that into neurostimulation design.

**Relevance:** Gives a formal way to compute "which target cortical patterns are reachable given our 8 inputs" — a quantitative version of our rank/coverage analysis that accounts for the statistical (not just linear-algebraic) structure.

### 1.16 Iolov, Ditlevsen & Longtin (2014)
*Stochastic optimal control of single neuron spike trains.* **Journal of Neural Engineering** 11(4):046004.
DOI: [10.1088/1741-2560/11/4/046004](https://doi.org/10.1088/1741-2560/11/4/046004)

Formulates control of spike timing in a noisy (stochastic differential equation) neuron as an optimal control problem, deriving minimum-energy stimulus waveforms that achieve target spike times.

**Relevance:** Provides the stochastic-optimal-control formalism for the "minimum charge for a target response" objective — the theoretical counterpart to our empirical charge-reduction result.

### 1.17 Ahmadian, Packer, Yuste & Paninski (2011)
*Designing optimal stimuli to control neuronal spike timing.* **Journal of Neurophysiology** 106(2):1038–1053.
DOI: [10.1152/jn.00427.2010](https://doi.org/10.1152/jn.00427.2010)

Solves for the stimulus that drives a neuron to a target spike train with optimal precision **subject to explicit physiological constraints** on the stimulus (amplitude bounds, power limits), using convex optimization on a GLM-based model.

**Relevance:** The foundational "constrained optimal stimulus design" paper, and notable because constrained convex optimization is exactly our condensed-QP structure. Their treatment of hard input constraints is the template for our non-negativity handling.

### 1.18 Acharya, Ruf & Nozari (2022)
*Brain modeling for control: A review.* **Frontiers in Control Engineering** 3:1046764.
DOI: [10.3389/fcteg.2022.1046764](https://doi.org/10.3389/fcteg.2022.1046764)

Reviews models of brain response to five neurostimulation modalities (DBS, TMS, direct electrical stimulation, transcranial electrical stimulation, optogenetics), organizing them into biophysical, stimulus-response, and data-driven dynamical-system classes. Argues data-driven dynamical-system models are the class that actually enables control-theoretic methods.

**Relevance:** The right review to cite when justifying an ARX/LTI data-driven plant over a biophysical model for real-time control.

### 1.19 Marks, vanRheede, Karantonis, Esteller, Dinsmoor, Fleming, Larson, Desborough, Single, Raike, DHaese, Englot, Lempka, North, Poree, Bikson & Denison (2025)
*Principles of physiological closed-loop controllers in neuromodulation.* **arXiv:2508.11422** *(preprint; submitted Aug 2025, revised Dec 2025)*.
URL: [arxiv.org/abs/2508.11422](https://arxiv.org/abs/2508.11422)

Unifying framework and standardized nomenclature for physiological closed-loop controllers (PCLC) in neurostimulation devices, integrating FDA guidance with control-systems theory. Classifies feedback signals as **reactive vs. predictive biomarkers** and lays out risk-management considerations.

**Relevance:** The reactive/predictive biomarker distinction is a useful lens on our LFP feature choice; also the right citation for controller taxonomy and terminology in the paper's framing.

### 1.20 Bryan, Schwock, Yazdan-Shahmorad & Rao (2025)
*Temporal basis function models for closed-loop neural stimulation.* **arXiv:2507.15274** *(preprint; submitted Jul 2025)*.
URL: [arxiv.org/abs/2507.15274](https://arxiv.org/abs/2507.15274)

Introduces temporal basis function models (TBFMs) — deliberately simple, fast-to-fit predictors of the LFP response to stimulation. Evaluated on optogenetic stimulation in two NHPs; achieves competitive accuracy with 2–4 minute training and **0.2 ms inference latency**, and in simulation steers activity toward target patterns.

**Relevance:** A strong argument that a low-complexity model with fast refit beats a heavy model for closed-loop use. The 2–4 min refit time is the right order for re-identifying our plant mid-session against 30-min drift.

---

## Category 2 — Closed-loop DBS, adaptive DBS control theory, and closed-loop seizure control

### ★ 2.1 Little, Pogosyan, Neal, Zavala, Zrinzo, Hariz & Brown (2013)
*Adaptive deep brain stimulation in advanced Parkinson disease.* **Annals of Neurology** 74(3):449–457.
DOI: [10.1002/ana.23951](https://doi.org/10.1002/ana.23951)

The landmark first-in-human demonstration that beta-LFP-triggered adaptive DBS beats continuous open-loop DBS: motor scores improved 66% (unblinded) / 50% (blinded), i.e. 29% and 27% *better than* conventional DBS, while delivering 56% less stimulation time and correspondingly less energy.

**Relevance:** The canonical "feedback beats open-loop, and with less charge" result — the exact claim structure of our MPC-vs-Choi comparison. Their effect-size-plus-charge-savings reporting format is what we should mirror.

### 2.2 Priori, Foffani, Rossi & Marceglia (2013)
*Adaptive deep brain stimulation (aDBS) controlled by local field potential oscillations.* **Experimental Neurology** 245:77–86.
DOI: [10.1016/j.expneurol.2012.09.013](https://doi.org/10.1016/j.expneurol.2012.09.013)

Foundational statement of the aDBS concept: use LFPs recorded from the stimulating electrodes themselves as the control feedback signal, with the signal-processing and hardware constraints that entails.

**Relevance:** Establishes the LFP-as-feedback-signal precedent and is honest about the same-electrode sensing/stimulation conflict we face with artifact contamination.

### 2.3 Santaniello, Fiengo, Glielmo & Grill (2011)
*Closed-loop control of deep brain stimulation: a simulation study.* **IEEE Transactions on Neural Systems and Rehabilitation Engineering** 19(1):15–24.
DOI: [10.1109/TNSRE.2010.2081377](https://doi.org/10.1109/TNSRE.2010.2081377)

Model-based closed-loop controller that automatically adjusts stimulation parameters using LFPs recorded from the same stimulation electrode, evaluated in a basal-ganglia network simulation.

**Relevance:** Early and clean example of model-based (not threshold-based) DBS control; useful for the literature framing of "why model-based rather than bang-bang."

### 2.4 Gorzelic, Schiff & Sinha (2013)
*Model-based rational feedback controller design for closed-loop deep brain stimulation of Parkinson's disease.* **Journal of Neural Engineering** 10(2):026016.
DOI: [10.1088/1741-2560/10/2/026016](https://doi.org/10.1088/1741-2560/10/2/026016)

Systematically compares classical feedback structures (P, PD, PID with integral bias) on a computational basal-ganglia model. Best performance came from amplitude-proportional control with derivative action **and integral bias** — the integral term mattering specifically because the command is effectively offset-constrained.

**Relevance:** The integral-bias finding is directly applicable: with a unipolar/non-negative command, an integral bias term is what lets the controller sit at a nonzero operating point and modulate bidirectionally around it. This is the classical-control version of our non-negativity workaround.

### 2.5 Fleming, Dunn & Lowery (2020)
*Simulation of closed-loop deep brain stimulation control schemes for suppression of pathological beta oscillations in Parkinson's disease.* **Frontiers in Neuroscience** 14:166.
DOI: [10.3389/fnins.2020.00166](https://doi.org/10.3389/fnins.2020.00166)

Compares clinically viable control schemes (on-off, proportional, PI) on a cortico-basal-ganglia network model, quantifying symptom suppression against power consumption.

**Relevance:** A template for the controller-comparison figure — several controllers, one plant, error and charge on the same axes.

### 2.6 Fleming, Orłowski, Lowery & Chaillet (2020)
*Self-tuning deep brain stimulation controller for suppression of beta oscillations: analytical derivation and numerical validation.* **Frontiers in Neuroscience** 14:639.
DOI: [10.3389/fnins.2020.00639](https://doi.org/10.3389/fnins.2020.00639)

Most closed-loop DBS methods hold controller *parameters* fixed for all time; this work derives a self-tuning controller that tracks fluctuations in the feedback band over time and retunes the control law accordingly, with analytical justification plus simulation validation.

**Relevance:** Gain-scheduling against a drifting plant, derived rather than heuristic — the structure to adopt for our 30-min gain drift if full parameter adaptation proves too aggressive.

### 2.7 Fleming, Senneff & Lowery (2023)
*Multivariable closed-loop control of deep brain stimulation for Parkinson's disease.* **Journal of Neural Engineering** 20(5), art. 056029 (DOI-confirmed; issue/article number from Europe PMC record).
DOI: [10.1088/1741-2552/acfbfa](https://doi.org/10.1088/1741-2552/acfbfa)

Controls **two** stimulation parameters simultaneously (pulse amplitude and pulse duration) against two biomarkers (rest tremor and beta activity). Achieves good control of both with reduced power versus conventional open-loop stimulation, and the dual-parameter structure automatically prevents overstimulation.

**Relevance:** Precedent for treating pulse *shape/width* as a second control degree of freedom rather than modulating amplitude only — a cheap way to add input dimensionality to a rank-limited plant without adding electrodes.

### 2.8 Su, Kumaravelu, Wang & Grill (2019)
*Model-based evaluation of closed-loop deep brain stimulation controller to adapt to dynamic changes in reference signal.* **Frontiers in Neuroscience** 13:956.
DOI: [10.3389/fnins.2019.00956](https://doi.org/10.3389/fnins.2019.00956)

Designs a PI controller whose gains are tuned by coupling a linear controlled auto-regressive (CAR) model with Routh–Hurwitz stability analysis, then shows it tracks dynamically changing reference signals on a basal-ganglia network model.

**Relevance:** A principled ARX-model-based gain-tuning + stability-margin procedure — directly transferable to certifying stability margins for our ARX-identified plant.

### 2.9 Grado, Johnson & Netoff (2018)
*Bayesian adaptive dual control of deep brain stimulation in a computational model of Parkinson's disease.* **PLoS Computational Biology** 14(12):e1006606.
DOI: [10.1371/journal.pcbi.1006606](https://doi.org/10.1371/journal.pcbi.1006606)

Two-timescale **dual controller**: an inner fast loop delivering phase/power-dependent stimulation, and an outer slow loop using Bayesian optimization to retune the inner loop's parameters to minimize beta power. Outperforms alternative optimizers and is explicitly framed as feedback-signal- and disease-agnostic.

**Relevance:** The cleanest architectural answer to "fast MPC + slow adaptation": keep the 100 Hz MPC as the inner loop and add a slow outer Bayesian loop retuning weights/operating point against drift. Strongly recommended as our drift architecture.

### 2.10 Holt, Wilson, Shinn, Moehlis & Netoff (2016)
*Phasic burst stimulation: a closed-loop approach to tuning deep brain stimulation parameters for Parkinson's disease.* **PLoS Computational Biology** 12(7):e1005011.
DOI: [10.1371/journal.pcbi.1005011](https://doi.org/10.1371/journal.pcbi.1005011)

Delivers a **burst** of pulses over a range of phases predicted to disrupt pathological oscillation, with burst parameters optimized from patient-specific phase response curves (PRCs) rather than from amplitude titration.

**Relevance:** Explicit precedent that *bursts*, parameterized by phase and burst structure, do control work that steady tonic amplitude cannot — the DBS-side analogue of our burst-probing lever for rank recovery.

### 2.11 Holt, Kormann, Gulberti, Pötter-Nerger, McNamara, Cagnan, et al. (2019)
*Phase-dependent suppression of beta oscillations in Parkinson's disease patients.* **Journal of Neuroscience** 39(6):1119–1134.
DOI: [10.1523/JNEUROSCI.1913-18.2018](https://doi.org/10.1523/JNEUROSCI.1913-18.2018)
*(Author ordering beyond the first several names not independently confirmed from a fetched record.)*

Human intraoperative demonstration that there is a **patient-specific phase** of the STN beta LFP at which consecutive stimulation pulses suppress oscillation amplitude by up to 40%, without changing overall excitability, with effects extending to STN output and cortico-subthalamic synchrony.

**Relevance:** Shows that *when* you stimulate within an ongoing rhythm changes the response sign/magnitude at fixed charge — i.e. timing is a control input independent of amplitude. Relevant to whether our 100 Hz carrier should be phase-referenced to ongoing S1 activity.

### ★ 2.12 Cagnan, Pedrosa, Little, Pogosyan, et al. (2017)
*Stimulating at the right time: phase-specific deep brain stimulation.* **Brain** 140(1):132–145.
DOI: [10.1093/brain/aww286](https://doi.org/10.1093/brain/aww286)

Uses accelerometry of the trembling limb to trigger thalamic stimulation at a specific phase of the tremor cycle. Achieves clinically significant tremor relief while delivering **less than half the energy** of conventional DBS.

**Relevance:** The strongest published statement of the charge-efficiency payoff from correctly timed rather than continuous stimulation — the headline comparison we are making with our 29.5% charge win, and a target to beat.

### 2.13 Tass (2003)
*A model of desynchronizing deep brain stimulation with a demand-controlled coordinated reset of neural subpopulations.* **Biological Cybernetics** 89(2):81–88.
DOI: [10.1007/s00422-003-0425-7](https://doi.org/10.1007/s00422-003-0425-7)

Coordinated reset (CR): short high-frequency pulse trains delivered at *different sites in a coordinated, staggered way*, with demand-controlled timing/length, desynchronizes a population that continuous stimulation would entrain.

**Relevance:** The foundational multi-site, temporally staggered stimulation design. With 8 bipolar pairs we can implement a CR-like stagger to deliberately *break* the synchrony that collapses our operator to rank 1 — arguably the highest-value idea in this review for the rank problem.

### 2.14 Velisar, Syrkin-Nikolau, Blumenfeld, Trager, Afzal, Prabhakar & Bronte-Stewart (2019)
*Dual threshold neural closed loop deep brain stimulation in Parkinson disease patients.* **Brain Stimulation** 12(4):868–876.
DOI: [10.1016/j.brs.2019.02.020](https://doi.org/10.1016/j.brs.2019.02.020)

A dual-threshold algorithm increases, decreases, or holds DBS amplitude as the measured beta LFP sits above, below, or within a target range. Improved tremor and bradykinesia while delivering <57% of open-loop DBS energy, and remained feasible 22 months post-implant.

**Relevance:** The simple-baseline controller our MPC must beat. A dual-threshold/deadband scheme is trivially implementable on our rig and makes an honest low-complexity comparator alongside the Choi open-loop arm.

### 2.15 Oehrn, Cernera, Hammer, Starr, Little, et al. (2024)
*Chronic adaptive deep brain stimulation versus conventional stimulation in Parkinson's disease: a blinded randomized feasibility trial.* **Nature Medicine** 30:3345–3356.
DOI: [10.1038/s41591-024-03196-z](https://doi.org/10.1038/s41591-024-03196-z)

Blinded randomized cross-over trial of chronic adaptive vs. continuous DBS in four patients. Identified stimulation-entrained gamma oscillations as the optimal marker of dopaminergic state, and found adaptive DBS significantly improved motor symptoms and quality of life over conventional DBS.

**Relevance:** Current state of the art for "feedback beats open-loop" evidence quality (blinded, randomized, chronic). Note the feature choice: a **stimulation-entrained** oscillation — a signal created by the stimulation itself — used as feedback, which is a constructive way to think about our artifact-adjacent features.

### 2.16 Stanslaski, Afshar, Cong, Giftakis, Stypulkowski, Carlson, Linde, Ullestad, Avestruz & Denison (2012)
*Design and validation of a fully implantable, chronic, closed-loop neuromodulation device with concurrent sensing and stimulation.* **IEEE Transactions on Neural Systems and Rehabilitation Engineering** 20(4):410–421.
DOI: [10.1109/TNSRE.2012.2183617](https://doi.org/10.1109/TNSRE.2012.2183617)

Describes systematic mitigation of stimulation's effect on concurrent sensing through a *combination* of sensing hardware design, deliberate stimulation-parameter selection, and classifier algorithms robust to residual disturbance.

**Relevance:** Makes the key architectural point that artifact is managed jointly across hardware, stimulus parameter choice, and algorithm — not by any single filter. Relevant to our PZ2-off incident and y-liveness rule.

### 2.17 Berényi, Belluscio, Mao & Buzsáki (2012)
*Closed-loop control of epilepsy by transcranial electrical stimulation.* **Science** 337(6095):735–737.
DOI: [10.1126/science.1223154](https://doi.org/10.1126/science.1223154)

Seizure-triggered feedback transcranial electrical stimulation dramatically reduced spike-and-wave episodes in a rodent model of generalized epilepsy, in real time and in freely moving animals.

**Relevance:** Foundational rodent closed-loop demonstration; useful precedent for real-time detection-plus-actuation latency budgets in a rodent rig.

### 2.18 Ehrens, Sritharan & Sarma (2015)
*Closed-loop control of a fragile network: application to seizure-like dynamics of an epilepsy model.* **Frontiers in Neuroscience** 9:58.
DOI: [10.3389/fnins.2015.00058](https://doi.org/10.3389/fnins.2015.00058)

Frames the epileptic cortex as a "fragile" network destabilized by small synaptic perturbations. The controller detects instability with a 2-state hidden Markov model on firing rates of the most fragile node, then stimulates to restabilize.

**Relevance:** Example of a *state-detection-driven* switched controller rather than continuous regulation, and of choosing the feedback channel by a network-fragility criterion rather than by signal strength — a possible principled rule for choosing which of our 64 channels to feed back.

### 2.19 Ullah & Schiff (2010)
*Assimilating seizure dynamics.* **PLoS Computational Biology** 6(5):e1000776.
DOI: [10.1371/journal.pcbi.1000776](https://doi.org/10.1371/journal.pcbi.1000776)

Applies data-assimilation (Kalman-family) techniques to a computational model of excitatory/inhibitory interplay during seizures, showing that incorporating slower metabolic (potassium) dynamics is essential for state-estimation accuracy.

**Relevance:** Cautionary result for observer design: if a slow state (here metabolic; for us, adaptation/saturation state) is omitted from the model, the observer's estimates degrade. Argues for augmenting our plant with a slow adaptation state.

### 2.20 Tian, Saradhi, Bello, Johnson, D'Eleuterio, Popovic & Lankarany (2024)
*Model-based closed-loop control of thalamic deep brain stimulation.* **Frontiers in Network Physiology** 4:1356653.
DOI: [10.3389/fnetp.2024.1356653](https://doi.org/10.3389/fnetp.2024.1356653)

Closed-loop control of thalamic (Vim) DBS for essential tremor, with an encoding model that preserves synaptic-plasticity dynamics, a data-driven decoding model mapping neural activity to a behavioral signal (EMG), and a controller closing the loop. Explicitly criticizes existing closed-loop DBS for ignoring the physiological mechanisms by which DBS modulates dynamics.

**Relevance:** Thalamic stimulation target, model-based loop, and a short-term-plasticity-aware plant — the closest DBS-side analogue to our thalamic preparation, and an argument for representing synaptic depression (our tonic saturation) explicitly in the plant.

### 2.21 Steffen, Cannon, Tan & Debarros (2024)
*Model predictive control for closed-loop deep brain stimulation.* **Proc. 63rd IEEE Conference on Decision and Control (CDC 2024)**, Milan.
DOI: [10.1109/CDC56724.2024.10885888](https://doi.org/10.1109/CDC56724.2024.10885888)

An MPC algorithm for DBS built on a model of beta-band population activity, using system identification plus **Kalman filtering for state estimation**. In simulation it matches the symptom tracking of bang-bang and PI control while requiring less stimulation input.

**Relevance:** The closest published sibling to our controller — MPC + Kalman observer + identified beta-band plant, compared against bang-bang and PI baselines, with the win reported as *equal tracking at lower input*. That is precisely our charge-win framing, and a direct citation for it.

---

## Category 3 — Adaptive and learning control of neural stimulation

### ★ 3.1 Bonizzato, Guay-Hottin, Côté, Massai, Choinière, Macar, Laferrière, Sirpal, Quessy, Lajoie, Martinez & Dancause (2023)
*Autonomous optimization of neuroprosthetic stimulation parameters that drive the motor cortex and spinal cord outputs in rats and monkeys.* **Cell Reports Medicine** 4(4):101008.
DOI: [10.1016/j.xcrm.2023.101008](https://doi.org/10.1016/j.xcrm.2023.101008)
*(Note: this is Cell Reports Medicine, not Nature Biomed Eng as sometimes cited.)*

Gaussian-process Bayesian optimization autonomously explores the stimulation parameter space and selects parameters evoking target movements in real time, in both rats and monkeys. GP-BO converges after testing only a small fraction of possible parameter combinations, outperforming alternative search strategies.

**Relevance:** The reference implementation for automatically choosing *which* of our 8 channels and what amplitudes to use, with a sample budget small enough for an acute session. Directly addresses our site-selectivity search problem.

### 3.2 Laferrière, Bonizzato, Côté, Dancause & Lajoie (2020)
*Hierarchical Bayesian optimization of spatiotemporal neurostimulations for targeted motor outputs.* **IEEE Transactions on Neural Systems and Rehabilitation Engineering** 28(6):1452–1460.
DOI: [10.1109/TNSRE.2020.2987001](https://doi.org/10.1109/TNSRE.2020.2987001)

Runs Bayesian optimization over a **hierarchy of increasingly complex signal spaces**, so that simple (single-site, single-amplitude) solutions are found first and used to warm-start search over complex spatiotemporal multi-channel patterns.

**Relevance:** The right way to search our 8-channel spatiotemporal command space without combinatorial blowup — start with single-pair responses (which we have) and bootstrap to multi-pair burst patterns.

### 3.3 Fleming, Pont Sanchis, Lemmens, Denison, Denison-Smith, West, Aziz, Antoniades, Cagnan (2023)
*From dawn till dusk: time-adaptive Bayesian optimization for neurostimulation.* **PLoS Computational Biology** 19(12):e1011674.
DOI: [10.1371/journal.pcbi.1011674](https://doi.org/10.1371/journal.pcbi.1011674)

Time-varying Bayesian optimization (TV-BayesOpt) tracks a *moving* optimum by combining gradual "forgetting" with periodic covariance kernels, motivated by disease progression and biological rhythmicity. Outperforms time-invariant BayesOpt whenever the optimal settings drift.

**Relevance:** The precise tool for our 30-min gain drift at the outer-loop level: a forgetting kernel makes old stimulus-response samples decay rather than anchoring the optimizer to a stale operating point.

### 3.4 Aiello, Valle & Raspopovic (2023)
*Recalibration of neuromodulation parameters in neural implants with adaptive Bayesian optimization.* **Journal of Neural Engineering** 20(2):026037.
DOI: [10.1088/1741-2552/acc975](https://doi.org/10.1088/1741-2552/acc975)

Uses adaptive Bayesian methods to *predict* over-time changes in the neuromodulation parameters needed for stable sensory feedback, rather than re-running full recalibration.

**Relevance:** Treats drift as predictable rather than as noise — if our gain drift has consistent structure across sessions, we can feed-forward-correct it instead of waiting for feedback to catch up.

### 3.5 Sarikhani, Ferleger, Mitchell, Kokkoni, Gunduz, Miocinovic & Mahmoudi (2022)
*Automated deep brain stimulation programming with safety constraints for tremor suppression in patients with Parkinson's disease and essential tremor.* **Journal of Neural Engineering** 19(4):046042.
DOI: [10.1088/1741-2552/ac86a2](https://doi.org/10.1088/1741-2552/ac86a2)

Bayesian optimization over DBS settings in 15 patients (9 PD, 6 ET). Tremor suppression at the best automated settings was statistically comparable to established clinical settings, with convergence after roughly **15–18 tested settings**.

**Relevance:** Gives a concrete sample budget (~15–20 evaluations) for automated parameter search in a live subject — directly sizing how much of an acute session a search arm would cost us.

### 3.6 Cole, Connolly, Ghetiya, Sendi, Kashlan, Eggers & Gross (2024)
*SAFE-OPT: a Bayesian optimization algorithm for learning optimal deep brain stimulation parameters with safety constraints.* **Journal of Neural Engineering** 21(4):046054.
DOI: [10.1088/1741-2552/ad6cf3](https://doi.org/10.1088/1741-2552/ad6cf3)

Bayesian optimization that finds effective stimulation parameters **without ever selecting amplitudes exceeding the subject's safety threshold**, validated in animal experiments and simulation.

**Relevance:** The safe-exploration formalism we need if we let an optimizer drive charge on live tissue — it keeps parameter search inside a charge-density safety envelope by construction.

### 3.7 Losanno, Badi, Roussinova, Bogaard, Delacombaz, Borgognon, Vachicouras, Dominguez, Berger, Rouiller, Lacour & Micera (2021)
*Bayesian optimization of peripheral intraneural stimulation protocols to evoke distal limb movements.* **Journal of Neural Engineering** 18(6):066046.
DOI: [10.1088/1741-2552/ac3f6c](https://doi.org/10.1088/1741-2552/ac3f6c)

Bayesian optimization of intraneural stimulation to elicit ankle movements in rats and grasping in macaques; converged using evaluations equal to about **20% of the search-space size** in both species.

**Relevance:** A second independent sample-efficiency benchmark (~20% of the grid) for stimulation-parameter BayesOpt in rodent, useful for planning our acute search budget.

### 3.8 Connolly, Opri, Miocinovic & Devergnas (2022)
*Meta-Bayesian optimization for deep brain stimulation.* **Proc. IEEE EMBC 2022**, pp. 1729–1733.
DOI: [10.1109/EMBC48229.2022.9871279](https://doi.org/10.1109/EMBC48229.2022.9871279)

Learns a prior across *multiple subjects* so that optimization in a new subject starts warm. On NHP data achieved cumulative reward 8.93±0.70 vs. 7.17±1.64 for classical BayesOpt (~24.6% better), and generalized to objective functions unseen in training.

**Relevance:** We have 275 acute blocks of prior stim-response data. Meta-BayesOpt is how that archive becomes a prior that makes each *new* acute session's search converge faster.

### ★ 3.9 Tafazoli, MacDowell, Che, Letai, Steinhardt & Buschman (2020)
*Learning to control the brain through adaptive closed-loop patterned stimulation.* **Journal of Neural Engineering** 17(5):056007.
DOI: [10.1088/1741-2552/abb860](https://doi.org/10.1088/1741-2552/abb860)

Adaptive closed-loop stimulation (ACLS) uses patterned multi-site electrical stimulation and iteratively updates the stimulation pattern to minimize the difference between the observed population response and a target firing-rate pattern — **without** a model relating stimulation to response. Learns target patterns in ~15 minutes, is robust to noise and drift, and in mouse visual cortex learned stimulation patterns producing responses similar to those evoked by natural visual stimuli.

**Relevance:** This is our exact goal — patterned multi-site stimulation reproducing a *naturally evoked* cortical response — solved by iterative learning rather than a model-based controller. It is both the strongest comparator to our MPC and a fallback if plant identification keeps failing under tonic saturation. Their explicit robustness-to-drift claim is directly on point.

### ★ 3.10 Minai, Soldado-Magraner, Smith & Yu (2024)
*MiSO: Optimizing brain stimulation to create neural population activity states.* **Advances in Neural Information Processing Systems (NeurIPS) 2024.**
URL: [proceedings.neurips.cc/paper_files/paper/2024/file/2af641762dc02035c31a9314b2d090b6-Paper-Conference.pdf](https://proceedings.neurips.cc/paper_files/paper/2024/file/2af641762dc02035c31a9314b2d090b6-Paper-Conference.pdf) · [NeurIPS poster page](https://neurips.cc/virtual/2024/poster/95894)

Closed-loop microstimulation framework driving neural *population* activity toward specified states over a large parameter space (notably: which subset of electrodes to stimulate). Three components: (1) a neural-activity **alignment method merging stimulation-response samples across sessions**, (2) a statistical model predicting responses to untested configurations, (3) online optimization adaptively updating the configuration. Validated in closed-loop microstimulation of NHP prefrontal cortex, searching thousands of configurations.

**Relevance:** Solves two of our hardest problems at once — electrode-subset selection over a combinatorial space, and pooling stim-response data *across sessions* despite drift/realignment. The cross-session alignment step is exactly what would let our 275-block archive train one predictive model.

### 3.11 Pineau, Guez, Vincent, Panuccio & Avoli (2009)
*Treating epilepsy via adaptive neurostimulation: a reinforcement learning approach.* **International Journal of Neural Systems** 19(4):227–240.
DOI: [10.1142/S0129065709001987](https://doi.org/10.1142/S0129065709001987)

Formalizes adaptive neurostimulation as a reinforcement-learning problem and learns a stimulation policy directly from labeled data acquired in animal models (batch/offline RL from recorded episodes).

**Relevance:** Foundational RL-for-stimulation reference, and notable for *batch* learning from previously recorded data — the setting that matches our offline archive better than online RL does.

### 3.12 Krylov, Tachet des Combes, Laroche, Rosenblum & Dylov (2020)
*Reinforcement learning framework for deep brain stimulation study.* **Proc. IJCAI-2020**, Yokohama, pp. 2847–2854.
URL: [ijcai.org/proceedings/2020/394](https://www.ijcai.org/proceedings/2020/394)

First RL "gym" environment emulating collective neuronal behavior for learning suppression policies; suppresses synchrony across three pathological regimes with PPO agents, characterizes noise robustness, and uses multiple agents to remove residual oscillations.

**Relevance:** Useful if we want a simulation testbed to pre-train or stress-test controllers before rig time; the multi-agent-per-oscillation structure loosely parallels per-channel controllers.

### 3.13 Brockmeier, Choi, DiStasio, Francis & Príncipe (2011)
*Optimizing microstimulation using a reinforcement learning framework.* **Proc. IEEE EMBC 2011**, pp. 1069–1072.
DOI: [10.1109/IEMBS.2011.6090249](https://doi.org/10.1109/IEMBS.2011.6090249)

Uses RL to balance exploration of the microstimulation parameter space against exploitation of promising parameters, in the somatosensory-feedback-for-neuroprosthetics setting.

**Relevance:** Direct lab lineage — same group and problem as Choi 2016. Establishes that the exploration/exploitation framing predates the current BayesOpt wave in this exact preparation.

### 3.14 Choi, Brockmeier, McNiel, von Kraus, Príncipe & Francis (2016)
*Eliciting naturalistic cortical responses with a sensory prosthesis via optimized microstimulation.* **Journal of Neural Engineering** 13(5):056007.
DOI: [10.1088/1741-2560/13/5/056007](https://doi.org/10.1088/1741-2560/13/5/056007)

The lab's prior open-loop benchmark: QP-optimized microstimulation patterns designed offline to elicit cortical responses matching those evoked by natural touch.

**Relevance:** Our designated open-loop comparator arm. Included here so the MPC-vs-open-loop comparison is anchored to the literature entry it is actually being compared against.

### 3.15 Moure, Granley, Grani, Soo, Lozano, López-Peco, Villamarin-Ortiz, Soto-Sanchez, Liu, Beyeler & Fernández (2025)
*Deep learning-based control of electrically evoked activity in human visual cortex.* **bioRxiv** 2025.09.24.678361 *(preprint; PubMed 41279945)*.
DOI: [10.1101/2025.09.24.678361](https://doi.org/10.1101/2025.09.24.678361)

Trains a deep network to optimize multi-electrode stimulation patterns on a 96-channel occipital implant in a blind participant, significantly outperforming conventional methods by requiring **lower currents** and producing **more stable** percepts.

**Relevance:** The most recent NN-inverse-controller result on human cortical microstimulation, and a useful honest comparator for our own NN-inverse negative result — note that their win was in charge and stability, not raw accuracy, matching the pattern we observed.

### 3.16 Freeman, Rogers, Hughes, Burridge & Meadmore (2012)
*Iterative learning control in health care: electrical stimulation and robotic-assisted upper-limb stroke rehabilitation.* **IEEE Control Systems Magazine** 32(1):18–43.
DOI: [10.1109/MCS.2011.2173261](https://doi.org/10.1109/MCS.2011.2173261)

Tutorial treatment of iterative learning control (ILC) applied to electrical stimulation: ILC uses the error recorded on previous repetitions of the *same* task to update the input for the next repetition, converging to near-perfect tracking of a repeated reference even with a poorly known plant.

**Relevance:** Our touch-response target is a **repeated trial-structured reference** — the ideal ILC setting. Run-to-run ILC across trials, layered under the within-trial MPC, would let us converge on the touch waveform without needing the plant model to be exactly right.

### 3.17 Meadmore, Hughes, Freeman, Cai, Tong, Burridge & Rogers (2012)
*Functional electrical stimulation mediated by iterative learning control and 3D robotics reduces motor impairment in chronic stroke.* **Journal of NeuroEngineering and Rehabilitation** 9:32.
DOI: [10.1186/1743-0003-9-32](https://doi.org/10.1186/1743-0003-9-32)

Clinical demonstration that ILC-mediated electrical stimulation precisely controls assistance across repeated goal-oriented task attempts, reducing impairment.

**Relevance:** Evidence that run-to-run learning works in a real, noisy, biological stimulation loop — supporting evidence for 3.16's proposal rather than a method we would copy directly.

---

## Category 4 — Controllability, rank, and dimensionality of stimulation→response maps

### 4.1 Gu, Pasqualetti, Cieslak, Telesford, Yu, Kahn, Medaglia, Vettel, Miller, Grafton & Bassett (2015)
*Controllability of structural brain networks.* **Nature Communications** 6:8414.
DOI: [10.1038/ncomms9414](https://doi.org/10.1038/ncomms9414)

Applies linear network control theory to white-matter connectomes, computing average/modal/boundary controllability per region. Finds densely connected areas facilitate transitions to easily reachable states, weakly connected areas facilitate hard-to-reach states, and boundary regions facilitate integration/segregation.

**Relevance:** Foundational framing that *which* node you inject into determines *which* states are reachable — the network-level statement of our site-selectivity problem. The average-vs-modal controllability distinction suggests our 8 sites may all be high-average-controllability (easy, similar states) and none modal (diverse, hard states).

### ★ 4.2 Stiso, Khambhati, Menara, Kahn, Stein, Das, Gorniak, Tracy, Litt, Davis, Pasqualetti, Lucas & Bassett (2019)
*White matter network architecture guides direct electrical stimulation through optimal state transitions.* **Cell Reports** 28(10):2554–2566.
DOI: [10.1016/j.celrep.2019.08.008](https://doi.org/10.1016/j.celrep.2019.08.008)

Uses network control theory to predict, from structural connectivity, how direct electrical stimulation propagates through the human brain and drives spatially distributed activity changes — validated against actual intracranial stimulation data.

**Relevance:** The best worked example of predicting the *spatial* reach of stimulation from anatomy, and of the optimal-control energy formulation applied to real stimulation data. Bears on whether our lack of site selectivity is anatomy-determined (thalamocortical convergence) rather than a controller deficiency.

### 4.3 Tang & Bassett (2018)
*Colloquium: Control of dynamics in brain networks.* **Reviews of Modern Physics** 90(3):031003.
DOI: [10.1103/RevModPhys.90.031003](https://doi.org/10.1103/RevModPhys.90.031003)

Comprehensive review of control and dynamical-systems tools for brain networks, spanning development, cognition, anesthesia, seizure suppression, and DBS.

**Relevance:** The standard review citation for network control theory framing; useful for positioning our rank/controllability analysis within the broader literature.

### 4.4 Muldoon, Pasqualetti, Gu, Cieslak, Grafton, Vettel & Bassett (2016)
*Stimulation-based control of dynamic brain networks.* **PLoS Computational Biology** 12(9):e1005076.
DOI: [10.1371/journal.pcbi.1005076](https://doi.org/10.1371/journal.pcbi.1005076)

Builds nonlinear (Wilson–Cowan) models on individual structural connectomes and asks how single-region stimulation affects large-scale dynamics. Network control theory predicts whether stimulation effects stay **focal or spread globally**, with structural connectivity differentially constraining regional effects.

**Relevance:** Directly relevant to selectivity: it provides a criterion for which injection sites produce focal vs. global responses. Our uniformly global (non-selective) responses may be diagnosable with their focality metric.

### 4.5 Keller, Honey, Entz, Bickel, Groppe, Toth, Ulbert, Lado & Mehta (2014)
*Corticocortical evoked potentials reveal projectors and integrators in human brain networks.* **Journal of Neuroscience** 34(27):9152–9163.
DOI: [10.1523/JNEUROSCI.4289-13.2014](https://doi.org/10.1523/JNEUROSCI.4289-13.2014)

Single-pulse electrical stimulation with CCEP mapping reveals a functional taxonomy of sites: "projectors" that broadcast strongly to distant sites vs. "integrators" that receive broadly.

**Relevance:** A data-driven, stimulation-derived way to classify our 8 sites by their input-output role — and a reminder that pulse-evoked (not tonic) responses are the right probe for characterizing the map, consistent with our finding that pulse responses are rank ~5 while tonic is rank ~1.

### 4.6 Keller, Huang, Herrero, Fini, Du, Lado, Honey & Mehta (2018)
*Induction and quantification of excitability changes in human cortical networks.* **Journal of Neuroscience** 38(23):5384–5398.
DOI: [10.1523/JNEUROSCI.1088-17.2018](https://doi.org/10.1523/JNEUROSCI.1088-17.2018)

Uses repetitive stimulation to induce, and single-pulse CCEPs to quantify, changes in cortical excitability — i.e. tracks how the stimulation→response operator itself changes as a consequence of stimulation.

**Relevance:** Evidence that the plant's gain is *changed by the act of stimulating*, not just by time. Our 30-min drift may be partly stimulation-induced rather than purely exogenous — which argues for interleaving low-charge probe pulses to track it.

### 4.7 Basu, Yousefi, Crocker, Zelmann, Paulk, Peled, Ellard, Weisholtz, Cosgrove, Deckersbach, Eden, Eskandar, Dougherty, Cash & Widge (2023)
*Closed-loop enhancement and neural decoding of cognitive control in humans.* **Nature Biomedical Engineering** 7:576–588. (Published online Nov 2021.)
DOI: [10.1038/s41551-021-00804-y](https://doi.org/10.1038/s41551-021-00804-y)

Closed-loop stimulation of internal capsule/striatum triggered on decoded lapses in cognitive control. **Closed-loop stimulation produced larger behavioral changes than open-loop stimulation**, and single-trial performance was decodable from a small number of electrodes.

**Relevance:** A rigorous head-to-head closed-loop vs. open-loop comparison in humans with the closed-loop arm winning — plus the practical finding that few electrodes suffice for the feedback feature, relevant to reducing our 64-channel feature vector.

### 4.8 Basu, Robertson, Crocker, Peled, Farnes, Frank, Cash, Eskandar, Eden & Widge (2018)
*A neural mass model to predict electrical stimulation evoked responses in human and non-human primate brain.* **Journal of Neural Engineering** 15(6):066012.
DOI: [10.1088/1741-2552/aae136](https://doi.org/10.1088/1741-2552/aae136)

Reproduces cortical and subcortical stimulation-evoked responses with a neural-mass population model that can be trained on limited stimulation-response data, then used to explore stimulation settings safely in silico.

**Relevance:** A middle path between our black-box ARX plant and a full biophysical model — trainable from limited data, but with parameters that carry physiological meaning (useful for explaining saturation).

### 4.9 Ezzyat, Wanda, Levy, Kadel, Aka, Pedisich, Sperling, Sharan, Lega, Burks, Gross, Inman, Jobst, Gorenstein, Davis, Worrell, Kucewicz, Stein, Gorniak, Das, Rizzuto & Kahana (2018)
*Closed-loop stimulation of temporal cortex rescues functional networks and improves memory.* **Nature Communications** 9:365.
DOI: [10.1038/s41467-017-02753-0](https://doi.org/10.1038/s41467-017-02753-0)

Decodes memory-encoding state from intracranial recordings in real time and stimulates lateral temporal cortex only during predicted-poor encoding, improving recall by ~15%.

**Relevance:** Large-scale demonstration that *state-triggered* (closed-loop) delivery beats untriggered delivery of the identical stimulation — the cleanest "timing, not dose" argument in the human literature.

### 4.10 Solomon, Lega, Sperling, Worrell, Davis, Inman, Das, Stein, Rizzuto & Kahana (2018)
*Medial temporal lobe functional connectivity predicts stimulation-induced theta power.* **Nature Communications** 9:4437.
DOI: [10.1038/s41467-018-06876-w](https://doi.org/10.1038/s41467-018-06876-w)

Low-frequency spectral coherence networks predict which stimulation sites will evoke theta power increases, especially for stimulation in or near white matter.

**Relevance:** Shows baseline (pre-stimulation) functional connectivity predicts stimulation efficacy — a cheap screening signal for choosing among our 8 pairs without exhaustively testing each.

### 4.11 O'Shea, Duncker, Goo, Sun, Vyas, Trautmann, Diester, Ramakrishnan, Deisseroth, Sahani & Shenoy (2022)
*Direct neural perturbations reveal a dynamical mechanism for robust computation.* **bioRxiv** 2022.12.16.520768 *(preprint)*.
DOI: [10.1101/2022.12.16.520768](https://doi.org/10.1101/2022.12.16.520768)

Delivers optogenetic and electrical microstimulation perturbations to primate motor cortex during reaching and develops analysis relating the measured perturbation responses to tractable dynamical models of excitatory/inhibitory populations.

**Relevance:** State of the art in treating stimulation as a *system-identification perturbation* of a recurrent cortical network, and in showing that recurrent dynamics actively resist (correct) injected perturbations — a candidate mechanism for why our injected patterns collapse toward a stereotyped response.

### 4.12 Whitmire, Waiblinger, Schwarz & Stanley (2016)
*Information coding through adaptive gating of synchronized thalamic bursting.* **Cell Reports** 14(4):795–807.
DOI: [10.1016/j.celrep.2015.12.068](https://doi.org/10.1016/j.celrep.2015.12.068)

In rat VPm, the degree of bottom-up adaptation modulates thalamic burst/tonic firing and the *synchrony* of bursting across the thalamic population along a continuum whose extremes favor either detection or discrimination of sensory inputs.

**Relevance:** ★-adjacent for us: it is the physiological account of exactly the burst-vs-tonic axis we are trying to exploit, in our exact nucleus and species. Burst mode and tonic mode transmit *different* information to cortex — strong biological justification that duty-cycled/burst stimulation should recover response diversity that tonic drive destroys.

---

## Category 5 — Stimulation artifact suppression relevant to closed-loop LFP control

### 5.1 Wagenaar & Potter (2002)
*Real-time multi-channel stimulus artifact suppression by local curve fitting (SALPA).* **Journal of Neuroscience Methods** 120(2):113–120.
DOI: [10.1016/S0165-0270(02)00149-8](https://doi.org/10.1016/S0165-0270(02)00149-8)

Models the artifact as a locally fitted cubic polynomial and subtracts it, yielding a flat baseline suitable for threshold-based spike detection. Explicitly an **online** method permitting continuous recording during sustained microstimulation.

**Relevance:** The foundational real-time (not post-hoc) artifact suppressor. Its "fit a smooth local model and subtract" structure is cheap enough to run inside our 100 Hz control tick.

### 5.2 Wichmann (2000)
*A digital averaging method for removal of stimulus artifacts in neurophysiologic experiments.* **Journal of Neuroscience Methods** 98(1):57–62.
DOI: [10.1016/S0165-0270(00)00190-4](https://doi.org/10.1016/S0165-0270(00)00190-4)

Estimates the average stimulus artifact from multiple stimulations at the same site and subtracts that template.

**Relevance:** The baseline template-subtraction method; the right comparator when we quantify how much artifact our approach removes.

### 5.3 Hashimoto, Elder & Vitek (2002)
*A template subtraction method for stimulus artifact removal in high-frequency deep brain stimulation.* **Journal of Neuroscience Methods** 113(2):181–186.
DOI: [10.1016/S0165-0270(01)00491-5](https://doi.org/10.1016/S0165-0270(01)00491-5)

Builds an artifact template by averaging onset-triggered artifact signals and subtracts it from individual triggered traces, validated for high-frequency DBS in NHP.

**Relevance:** Establishes template subtraction under *high-frequency continuous* stimulation, which is our regime (100 Hz carrier) rather than the sparse-pulse regime.

### 5.4 Erez, Tischler, Moran & Bar-Gad (2010)
*Generalized framework for stimulus artifact removal (SARGE).* **Journal of Neuroscience Methods** 191(1):45–59.
DOI: [10.1016/j.jneumeth.2010.06.005](https://doi.org/10.1016/j.jneumeth.2010.06.005) · Code: [github.com/ibglab/SARGE](https://github.com/ibglab/SARGE)

End-to-end multi-stage pipeline: pulse detection → artifact estimation → removal → signal reconstruction → **quantified assessment of removal quality**, including the residual artifact's measured impact on downstream spike sorting.

**Relevance:** The residual-impact quantification is the part to copy — we need to report not just "artifact removed" but "how much residual artifact contaminates the LFP feature the controller acts on." This bears directly on our negative-selectivity artifact-robustness finding.

### ★ 5.5 O'Shea & Shenoy (2018)
*ERAASR: an algorithm for removing electrical stimulation artifacts from multielectrode array recordings.* **Journal of Neural Engineering** 15(2):026020.
DOI: [10.1088/1741-2552/aaa365](https://doi.org/10.1088/1741-2552/aaa365) · Code: [github.com/djoshea/eraasr](https://github.com/djoshea/eraasr)

Exploits the fact that artifact transients — but not spiking activity — share structure **across simultaneously recorded channels, across pulses within a train, and across trials**, removing artifact by sequential PCA-based projection along each of those three axes.

**Relevance:** The three-way shared-structure insight maps perfectly onto our 64-channel array with a repeating 100 Hz carrier and repeated trials. Because artifact is common-mode across channels while the touch response is not, ERAASR-style projection should preserve the low-rank signal we care about — though note the caution that our *signal* is also low-rank, so the subspaces may collide.

### 5.6 Mena, Grosberg, Madugula, Hottowy, Litke, Cunningham, Chichilnisky & Paninski (2017)
*Electrical stimulus artifact cancellation and neural spike detection on large multi-electrode arrays.* **PLoS Computational Biology** 13(11):e1005842.
DOI: [10.1371/journal.pcbi.1005842](https://doi.org/10.1371/journal.pcbi.1005842)

Structured computational framework jointly estimating the artifact and the neural signal (rather than removing artifact then detecting spikes), demonstrated on real and simulated 512-electrode primate retina recordings under single- and multi-electrode stimulation.

**Relevance:** The "estimate artifact and signal *jointly*" principle — rather than sequentially — is the statistically correct approach and is what we should aim for in the loop, since sequential removal biases the feature the controller sees.

### 5.7 Shokri, Gogliettino, Hottowy, Sher, Litke, Chichilnisky, Pequito & Muratore (2024)
*Spike sorting in the presence of stimulation artifacts: a dynamical control systems approach.* **Journal of Neural Engineering** 21(1):016022.
DOI: [10.1088/1741-2552/ad228f](https://doi.org/10.1088/1741-2552/ad228f)

Models both artifact and individual neurons as dynamical systems with distinct spatiotemporal propagation signatures, then uses an **input estimator** to infer which neurons fired. Activation thresholds matched manual analysis with R²≈0.95 on 512-electrode primate retina data; explicitly framed as enabling future closed-loop stimulation.

**Relevance:** Recasts artifact removal as a *state-estimation* problem — meaning it can be folded directly into our observer rather than sitting as a separate preprocessing stage. This is the most architecturally compatible artifact method for an MPC loop.

### 5.8 Najafabadi, Chen, Dutta, Norris, Feng, Schnupp, Rosskothen-Kuhl, Read & Escabí (2020)
*Optimal multichannel artifact prediction and removal for neural stimulation and brain machine interfaces.* **Frontiers in Neuroscience** 14:709.
DOI: [10.3389/fnins.2020.00709](https://doi.org/10.3389/fnins.2020.00709)

Uses a **linear Wiener filter** to predict the artifact from the known stimulus currents via estimated transfer functions for each stimulating/recording electrode pair, then subtracts it. Achieves 25–40 dB artifact reduction across multiple preparations while preserving neural signals.

**Relevance:** Highly practical for us: we *know* our commanded currents exactly at each control tick, so a per-pair Wiener transfer function is directly estimable and cheap to apply online. Likely the best effort-to-payoff artifact method for our rig.

### 5.9 Kent & Grill (2012)
*Recording evoked potentials during deep brain stimulation: development and validation of instrumentation to suppress the stimulus artefact.* **Journal of Neural Engineering** 9(3):036004.
DOI: [10.1088/1741-2560/9/3/036004](https://doi.org/10.1088/1741-2560/9/3/036004)

Hardware solution: three amplifier stages with anti-parallel input diode clamps that selectively reduce artifact magnitude and duration and prevent amplifier saturation, enabling recovery of short-latency evoked responses.

**Relevance:** Reminder that the cheapest fixes to short-latency contamination are in the front end, before any algorithm. If our early-latency S1 response is saturating the amplifier, no software method recovers it.

### 5.10 Mendrela, Cho, Fredenburg, Nagaraj, Netoff, Flynn & Yoon (2016)
*A bidirectional neural interface circuit with active stimulation artifact cancellation and cross-channel common-mode noise suppression.* **IEEE Journal of Solid-State Circuits** 51(4):955–965.
DOI: [10.1109/JSSC.2015.2506651](https://doi.org/10.1109/JSSC.2015.2506651)

IC-level bidirectional interface with an active artifact-cancellation circuit plus cross-channel common-mode suppression, enabling simultaneous recording and stimulation.

**Relevance:** Cross-channel common-mode suppression is the hardware embodiment of the same insight ERAASR uses in software — evidence that treating artifact as common-mode across our 64 channels is well founded.

### 5.11 Culaclii, Kim, Lo, Li & Liu (2018)
*Online artifact cancelation in same-electrode neural stimulation and recording using a combined hardware and software architecture.* **IEEE Transactions on Biomedical Circuits and Systems** 12(3):601–613.
DOI: [10.1109/TBCAS.2018.2816464](https://doi.org/10.1109/TBCAS.2018.2816464)

Combines a novel hardware front end with concurrent software processing to recover neural signals in the presence of same-electrode artifacts up to **100 dB larger** than the underlying signal.

**Relevance:** Establishes the achievable ceiling for same-electrode artifact rejection, and again shows the winning approach is hardware+software jointly rather than either alone.

### 5.12 Weiss, Flesher, Franklin, Collinger & Gaunt (2019)
*Artifact-free recordings in human bidirectional brain-computer interfaces.* **Journal of Neural Engineering** 16(1):016002.
DOI: [10.1088/1741-2552/aae748](https://doi.org/10.1088/1741-2552/aae748)

Achieves artifact-free recording during bidirectional BCI control using only **simple changes in filtering plus digital signal blanking** on FDA-cleared, off-the-shelf hardware.

**Relevance:** The pragmatic counterpoint to the elaborate methods above: careful filter design plus well-timed blanking may suffice. Given our 100 Hz tick with defined inter-pulse windows, synchronized blanking is easy and should be the first thing tried.

### 5.13 Zhou, Johnson & Muller (2018)
*Toward true closed-loop neuromodulation: artifact-free recording during stimulation.* **Current Opinion in Neurobiology** 50:119–127.
DOI: [10.1016/j.conb.2018.01.012](https://doi.org/10.1016/j.conb.2018.01.012)

Review organizing the field into artifact-*preventing* system configurations, resilient recording front ends, and back-end signal processing for artifact removal.

**Relevance:** The best short orientation to the artifact problem space and the right citation for justifying whichever tier of solution we choose.

### 5.14 Zhou, Santacruz, Johnson, Alexandrov, Moin, Burghardt, Rabaey, Carmena & Muller (2019)
*A wireless and artefact-free 128-channel neuromodulation device for closed-loop stimulation and recording in non-human primates.* **Nature Biomedical Engineering** 3:15–26.
DOI: [10.1038/s41551-018-0323-x](https://doi.org/10.1038/s41551-018-0323-x)

128-channel closed-loop system with **on-board processing that fully cancels stimulation artifacts**, enabling artifact-free long-term LFP recording in an untethered NHP during stimulation.

**Relevance:** Existence proof that artifact-free *LFP* (our exact signal class) recording during stimulation at high channel count is achievable, and a specification target for what our loop should be able to see.

---

## Category 6 — Control of non-stationary/drifting neural plants (adaptive-decoder analogues)

### 6.1 Orsborn, Moorman, Overduin, Shanechi, Dimitrov & Carmena (2014)
*Closed-loop decoder adaptation shapes neural plasticity for skillful neuroprosthetic control.* **Neuron** 82(6):1380–1393.
DOI: [10.1016/j.neuron.2014.04.048](https://doi.org/10.1016/j.neuron.2014.04.048)

Shows that decoder adaptation and neural adaptation can be *combined* to achieve and maintain skilled control despite nonstationary recordings and changing control contexts — the two adaptation processes co-adapt rather than fight.

**Relevance:** The canonical two-learner (algorithm + biology) framing. In our anesthetized prep the biological learner is largely absent, which is itself worth stating: we must carry the full adaptation burden in the controller.

### 6.2 Ahmadipour, Yang, Chang & Shanechi (2021)
*Adaptive tracking of human ECoG network dynamics.* **Journal of Neural Engineering** 18(1):016011.
DOI: [10.1088/1741-2552/abae42](https://doi.org/10.1088/1741-2552/abae42)

Adaptive state-space modeling of multi-site ECoG network dynamics significantly outperforms non-adaptive modeling, and demonstrates that ECoG network dynamics are **non-stationary over their recording periods** in a way adaptive modeling can track.

**Relevance:** Direct empirical support that a fixed LTI model of multi-site field potentials degrades over a session — the same failure mode as our 30-min gain drift, with a demonstrated fix.

### 6.3 Yang, Ahmadipour & Shanechi (2021)
*Adaptive latent state modeling of brain network dynamics with real-time learning rate optimization.* **Journal of Neural Engineering** 18(3):036013.
DOI: [10.1088/1741-2552/abcefd](https://doi.org/10.1088/1741-2552/abcefd)

Adds **real-time optimization of the adaptation learning rate**, so the model neither over-reacts to noise nor under-reacts to genuine drift, tuned automatically from incoming data.

**Relevance:** Solves the practical problem that would otherwise bite us — picking the forgetting factor for online plant adaptation. Adopt their auto-tuned learning rate rather than hand-picking a constant.

### 6.4 Degenhart, Bishop, Oby, Tyler-Kabara, Chase, Batista & Yu (2020)
*Stabilization of a brain-computer interface via the alignment of low-dimensional spaces of neural activity.* **Nature Biomedical Engineering** 4:672–685.
DOI: [10.1038/s41551-020-0542-9](https://doi.org/10.1038/s41551-020-0542-9)

Stabilizes performance against recording instabilities by aligning estimates of the low-dimensional neural **manifold** across time, without requiring recalibration data or task labels.

**Relevance:** Manifold alignment is the unsupervised way to keep a plant/decoder valid across drift and across sessions — the same machinery MiSO (3.10) uses to merge stimulation-response samples across sessions. Highly applicable to pooling our 275-block archive.

---

## Themes and methods we should adopt

1. **MPC horizon and cost structure.** The published neural-MPC precedents (Shanechi 2013; Steffen 2024) use short horizons on a low-order identified model and report wins as *equal tracking at lower input* rather than better tracking. We should frame our result the same way: match Choi's accuracy, win on charge and stability — which is exactly what our 29.5% charge result already shows. Do not over-claim accuracy improvements the literature suggests are not where feedback pays.

2. **Feature choice should be target-relevant, not variance-dominant.** PSID (1.8) shows variance-dominant components are often not the controllable/relevant ones. Under tonic drive our dominant LFP variance is likely artifact-plus-saturation; the controller should regress onto the *touch-response subspace*. Refit our plant with a PSID-style target-prioritized identification and compare to plain subspace ID.

3. **Few channels suffice for feedback.** Basu 2023 (4.7) decoded single-trial state from a small number of electrodes; Solomon 2018 (4.10) predicted efficacy from baseline connectivity. We should test whether a reduced feature vector (5–10 of 64 channels, chosen by touch-response weight) controls as well as the full set — this cuts loop latency and artifact exposure simultaneously.

4. **Observer design: augment with a slow adaptation state.** Ullah & Schiff (2.19) show that omitting a slow state corrupts the observer's fast estimates. Our tonic saturation is precisely such a slow state. Add an explicit adaptation/depression state to the plant rather than treating saturation as unmodeled disturbance; Tian 2024 (2.20) does exactly this for thalamic DBS.

5. **Artifact belongs inside the observer, not upstream of it.** Shokri 2024 (5.7) and Mena 2017 (5.6) both argue for *joint* estimation of artifact and signal. Sequential "clean then control" biases the feature the controller acts on. Given we command known currents every tick, the Wiener-filter approach (5.8, 25–40 dB reduction) is the cheapest correct first step; escalate to joint estimation if residuals still move the controller.

6. **Try blanking before algorithms.** Weiss 2019 (5.12) got artifact-free bidirectional recording from filtering changes plus digital blanking on stock hardware. With a 100 Hz carrier we have well-defined inter-pulse windows — synchronized blanking should be attempted and reported before any elaborate method, and Kent & Grill (5.9) warn that front-end saturation is unrecoverable in software.

7. **Beware subspace collision in artifact removal.** ERAASR (5.5) works because artifact is low-rank/common-mode while spiking is not. Our *signal* is also low-rank, so common-mode projection risks removing the response along with the artifact. Quantify signal loss, not just artifact reduction — and follow SARGE (5.4) in reporting residual artifact's effect on the downstream control feature.

8. **Handling drift: two-timescale architecture.** Grado 2018 (2.9) is the template — keep the fast MPC inner loop and add a slow outer loop that retunes the operating point/weights. Combine with adaptive plant parameters (1.5, 1.6, 6.2) and auto-tuned learning rate (6.3). Yang 2019 reports >70% control-error reduction from within-session adaptation in rodent; that is our expected payoff.

9. **Drift may be partly self-inflicted.** Keller 2018 (4.6) shows repetitive stimulation itself changes cortical excitability. Interleave low-charge probe pulses to track the operator continuously, and test whether our drift rate scales with delivered charge — if it does, it is stimulation-induced and partly avoidable by duty-cycling.

10. **Forgetting factors, not fixed models, for the outer loop.** TV-BayesOpt (3.3) and Aiello 2023 (3.4) both show that stale samples anchor an optimizer to a dead operating point. Any outer-loop parameter search on our rig must discount old stim-response samples on the ~30 min timescale we measured.

11. **Non-negativity: use an integral bias, and keep it in the QP.** Gorzelic 2013 (2.4) found the best DBS controller needed integral *bias* — i.e. sit at a nonzero operating point and modulate bidirectionally around it, which is the classical answer to a unipolar command. Ahmadian 2011 (1.17) shows the constrained-convex formulation; our condensed QP already has the right structure, so keep the non-negativity as an explicit constraint rather than clipping post hoc (clipping invalidates the observer's input estimate).

12. **Burst/duty-cycled stimulation is the principal lever for rank recovery, and it is well supported.** Ching & Ritt (1.14) prove common continuous drive to a coupled/homogeneous ensemble yields synchrony (rank collapse), and that heterogeneity is what buys diversity. Whitmire 2016 (4.12) shows burst vs. tonic thalamic firing transmits *different* information to cortex in our exact nucleus and species. Holt 2016 (2.10) and Tass 2003 (2.13) provide the two concrete designs: phase-referenced bursts, and coordinated reset with staggered multi-site timing. **Recommendation: implement a CR-style staggered burst across our 8 pairs and measure the operator rank against tonic drive** — this is the single highest-value experiment suggested by this review.

13. **Add input dimensions cheaply.** Fleming 2023 (2.7) controls amplitude *and* pulse duration; Yang 2021 (1.3) modulates amplitude *and* frequency. Before adding electrodes, add per-channel pulse-width/frequency/phase-offset as control degrees of freedom — with 8 pairs this multiplies the reachable set without new hardware.

14. **Excitation design for identification under charge constraints.** Yang 2018 (1.4) gives the answer we need: a pulse train modulated by *stochastic binary noise*, near-optimal for identification while respecting unipolar safety limits. Adopt this for our ARX identification blocks in place of whatever deterministic sweep we currently use.

15. **Keep a model-free comparator honest.** Tafazoli 2020 (3.9) achieved our exact goal — patterned multi-site stimulation reproducing a naturally evoked cortical response — with **no plant model**, converging in ~15 min and robust to drift. MiSO (3.10) does the same over electrode subsets with cross-session alignment. If our model-based MPC cannot beat an iterative-learning baseline, that is a finding worth reporting, not hiding; and ILC (3.16) layered under the MPC exploits our repeated trial structure to get the best of both.

16. **How the literature compares open-loop vs. feedback.** The strongest comparisons (Little 2013, Basu 2023, Oehrn 2024, Ezzyat 2018) hold the stimulation *dose* fixed or lower in the closed-loop arm and show equal-or-better outcome — the win is in *timing and charge*, not raw magnitude. Cagnan 2017 delivered <50% of conventional energy; Little 2013 cut stimulation time 56%; Velisar 2019 used <57%. Our 29.5% charge win is real but modest against these benchmarks — worth noting explicitly, and worth revisiting whether our cost weights are penalizing charge aggressively enough.

---

## Ten-plus must-reads (starred above)

| # | Citation | DOI |
|---|---|---|
| 1.1 | Bolus, Willats, Rozell & Stanley 2021, *J Neural Eng* 18:036006 | 10.1088/1741-2552/abb89c |
| 1.2 | Bolus et al. 2018, *J Neural Eng* 15:026011 | 10.1088/1741-2552/aaa506 |
| 1.3 | Yang, …, Shanechi 2021, *Nat Biomed Eng* 5:324–345 | 10.1038/s41551-020-00666-w |
| 1.4 | Yang, Connolly & Shanechi 2018, *J Neural Eng* 15:066007 | 10.1088/1741-2552/aad1a8 |
| 1.12 | Schiff 2012, *Neural Control Engineering*, MIT Press | ISBN 9780262015370 |
| 2.1 | Little et al. 2013, *Ann Neurol* 74:449–457 | 10.1002/ana.23951 |
| 2.12 | Cagnan et al. 2017, *Brain* 140:132–145 | 10.1093/brain/aww286 |
| 3.1 | Bonizzato et al. 2023, *Cell Rep Med* 4:101008 | 10.1016/j.xcrm.2023.101008 |
| 3.9 | Tafazoli et al. 2020, *J Neural Eng* 17:056007 | 10.1088/1741-2552/abb860 |
| 3.10 | Minai, Soldado-Magraner, Smith & Yu 2024, NeurIPS (MiSO) | [NeurIPS proceedings](https://proceedings.neurips.cc/paper_files/paper/2024/file/2af641762dc02035c31a9314b2d090b6-Paper-Conference.pdf) |
| 4.2 | Stiso et al. 2019, *Cell Reports* 28:2554–2566 | 10.1016/j.celrep.2019.08.008 |
| 5.5 | O'Shea & Shenoy 2018, *J Neural Eng* 15:026020 | 10.1088/1741-2552/aaa365 |
