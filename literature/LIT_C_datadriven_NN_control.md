# Literature Survey C — Data-driven, learning-based and neural-network methods for modelling and controlling neural responses to stimulation (2010–2026)

Compiled 2026-09-18 for the TDTClosedLoop / NNController program (VPL microstimulation → S1 LFP tracking, anesthetized rat; real-time ARX-MPC at ~100 Hz; PyTorch NN inverse/forward controllers; C++ inference server).

Scope: forward (plant) models of stimulation-evoked activity; inverse-model / learned-policy controllers (incl. RL, Koopman, Bayesian optimization); system identification for low-SNR, low-rank, drifting plants; linear-vs-nonlinear comparisons and gray-box models; real-time deployment and data budgets.

Verification notes: DOIs/URLs marked **[verified]** were resolved by fetching the publisher/PubMed/Europe PMC/arXiv record during this search. Those marked *[DOI unverified]* are from bibliographic memory and should be checked before citing in a manuscript. Web-search quota was exhausted late in the search, so a handful of items (Newman 2015, Cleo, Chang 1997 DOI, Ahmadipour 2021 DOI) are cited from memory with that caveat.

★ = must-read for our project (11 starred).

Reference baseline (our own lab): Choi J.S., Brockmeier A.J., McNiel D.B., Von Kraus L.M., Príncipe J.C., Francis J.T. (2016). *Eliciting naturalistic cortical responses with a sensory prosthesis via optimized microstimulation.* J Neural Eng 13(5):056007. https://doi.org/10.1088/1741-2560/13/5/056007 — N4SID plant + QP-optimized open-loop stimulation; the linear baseline every entry below is judged against.

---

## Category 1 — Neural-network / deep-learning forward (plant) models of stimulation-evoked activity

### 1.1 ★ Yang Y., Qiao S., Sani O.G., Sedillo J.I., Ferrentino B., Pesaran B., Shanechi M.M. (2021). Modelling and prediction of the dynamic responses of large-scale brain networks during direct electrical stimulation. *Nature Biomedical Engineering* 5:324–345.
DOI: https://doi.org/10.1038/s41551-020-00666-w **[verified]**; code: https://github.com/ShanechiLab/DynamicStimulation
Summary: Two awake macaques received ongoing multi-site microstimulation whose amplitude and frequency were varied as temporally random patterns while ECoG/LFP network activity was recorded across many regions. Linear state-space input–output models (LSSM, subspace-identified; the GitHub code is "LSSM fitting and prediction") predicted held-out multiregional responses, revealing damping and oscillatory response dynamics; prediction accuracy and response strength across regions were explained by resting-state functional connectivity. The linear class was sufficient at the LFP/ECoG scale; no nonlinear model was needed to obtain significant single-trial prediction.
Relevance: The canonical demonstration that (i) random amplitude+frequency-modulated stimulation is a good identification input, (ii) linear subspace models of stim→LFP are adequate on this data scale, and (iii) forward-model prediction accuracy should be reported per channel and explained by connectivity — our rank-1 tonic plant fits this picture, and the paper is the standard our NN forward models must beat.

### 1.2 Yang Y., Connolly A.T., Shanechi M.M. (2018). A control-theoretic system identification framework and a real-time closed-loop clinical simulation testbed for electrical brain stimulation. *J Neural Eng* 15(6):066007.
DOI: https://doi.org/10.1088/1741-2552/aad1a8 **[verified]**
Summary: Formalizes stimulation as a control input and neural activity as output, fits linear state-space models from stimulation experiments and builds a real-time closed-loop simulation testbed for validating controllers before human use. Includes a treatment of input design (stimulation parameters as exogenous inputs), model-order selection and controller-in-the-loop simulation.
Relevance: Template for a "digital twin" of our rig: fit ARX/LSSM from excitation captures, then run MPC / NN controllers against the identified model in silico before each acute; the paper's identification pipeline is close to our `ingest_block`/fitter.

### 1.3 Vahidi P., Sani O.G., Shanechi M.M. (2024). Modeling and dissociation of intrinsic and input-driven neural population dynamics underlying behavior. *PNAS* 121(7):e2212887121.
DOI: https://doi.org/10.1073/pnas.2212887121 **[verified]**; code in https://github.com/ShanechiLab/PSID (IPSID)
Summary: Extends preferential subspace identification to measured inputs (IPSID), analytically learning linear state-space models that account for external inputs (sensory stimuli, stimulation) so that input-driven dynamics are not mis-attributed to intrinsic dynamics; prioritizes behaviorally relevant latent states.
Relevance: An analytical, closed-form alternative to our ARX fitter that separates stim-driven from ongoing S1 dynamics — directly useful for estimating the effective rank of the stim-driven subspace (our "rank ~1 under tonic drive" finding) and for a low-order MIMO plant.

### 1.4 ★ Abbaspourazad H., Erturk E., Pesaran B., Shanechi M.M. (2024). Dynamical flexible inference of nonlinear latent factors and structures in neural population activity. *Nature Biomedical Engineering* 8:85–108.
DOI: https://doi.org/10.1038/s41551-023-01106-1 **[verified]**
Summary: DFINE separates a nonlinear "manifold" latent (learned autoencoder) from a linear "dynamic" latent evolved by an LSSM with Kalman filtering, so inference is causal, recursive, and robust to missing samples. On motor-cortical spiking and LFP it beat prior sequential autoencoders (LFADS-type) on neural and behavior prediction while keeping real-time filtering.
Relevance: The most credible architecture for a *nonlinear* stim-response plant that still admits linear MPC: nonlinear readout + linear latent dynamics. Our GRU-inverse failure suggests trying DFINE-style forward models (linear dynamics with a learned observation map) rather than end-to-end recurrent inverses.

### 1.5 Vahidi P., Sani O.G., Shanechi M.M. (2025). BRAID: Input-driven nonlinear dynamical modeling of neural-behavioral data. *ICLR 2025*; arXiv:2509.18627.
URL: https://arxiv.org/abs/2509.18627 **[verified]**
Summary: Input-driven RNN framework with a multi-step forecasting objective that disentangles intrinsic recurrent dynamics from measured inputs (explicitly including neurostimulation as a use case); a multi-stage optimization prioritizes behaviorally relevant intrinsic dynamics. Beat autonomous and input-driven baselines on forecasting in simulations and motor-cortical data.
Relevance: Modern nonlinear counterpart of IPSID with a *forecasting* (multi-step) loss — exactly the loss an MPC plant needs; also a warning that one-step supervised losses (as in our NN training) do not guarantee multi-step usefulness.

### 1.6 Vaziri K., Oganesian L.L., Jo H., Vera R.M.C., Liu C.Y., Lee B., Shanechi M.M. (2025). Nonlinear dynamical modeling of human intracranial brain activity with flexible inference. arXiv:2512.22785.
URL: https://arxiv.org/abs/2512.22785 **[verified]**
Summary: Applies DFINE to multisite human iEEG; the nonlinear DFINE substantially outperformed linear LSSMs for forecasting field potentials and matched or exceeded a GRU, with the gain concentrated in high-gamma bands.
Relevance: One of few LFP-scale results showing where nonlinearity actually buys prediction (high-frequency bands, readout), supporting a "linear dynamics + nonlinear observation" design over a plain GRU.

### 1.7 ★ Bryan M.J., Schwock F., Yazdan-Shahmorad A., Rao R.P.N. (2025). Temporal basis function models for closed-loop neural stimulation. *J Neural Eng* (2025) / arXiv:2507.15274.
DOI: https://doi.org/10.1088/1741-2552/ae036a (IOP) ; https://arxiv.org/abs/2507.15274 **[verified]**
Summary: A single-trial spatiotemporal forward model of optogenetic-stimulation effects on LFP built from temporal basis functions; trains in 2–4 min from 15–20 min of data per session, runs at ~0.2 ms latency on a desktop CPU, explicitly accounts for loop latency and stimulation-state dependence. Across 40 NHP sessions it matched a nonlinear dynamical-systems model that takes hours to train and outperformed linear state-space models; in simulation it drove closed-loop control toward target LFP patterns.
Relevance: Closest published analogue to our problem (stim → multichannel LFP forward model for closed-loop shaping). Its design choices — low-parameter basis expansion, per-session fast refit, state-dependent gain, explicit latency — map directly onto our drift and SNR constraints and are a strong alternative to a GRU.

### 1.8 ★ Moure P., Granley J., Grani F., Soo L., Lozano A., López-Peco R., Villamarín-Ortiz A., Soto-Sánchez C., Liu S.-C., Beyeler M., Fernández E. (2026). Deep learning-based control of electrically evoked activity in human visual cortex. *Neuron* (2026); preprint bioRxiv 2025.09.24.678361.
DOI: https://doi.org/10.1016/j.neuron.2026.07.006 ; preprint https://doi.org/10.1101/2025.09.24.678361 **[verified]**
Summary: With a 96-channel bidirectional Utah array in a blind participant, a deep network was trained to predict single-trial multi-electrode evoked responses from multi-electrode stimulation patterns and resting state. Two controllers were derived: a *learned inverse network* (for real-time synthesis) and a *gradient-based optimizer through the forward model* (for precise targeting). Both beat conventional calibration, reached targets at lower currents, adapted to the resting state, and produced more consistent percepts; recorded population activity predicted percepts better than stimulation parameters did.
Relevance: The single most relevant recent paper: a working NN inverse for multi-electrode stim→population response. Note the recipe — the inverse is trained *against a learned forward model* (distal-teacher style) and conditioned on the current resting state, not by naive regression from LFP features to commands.

### 1.9 Kumaravelu K., Tomlinson T., Callier T., Sombeck J., Bensmaia S.J., Miller L.E., Grill W.M. (2020). A comprehensive model-based framework for optimal design of biomimetic patterns of electrical stimulation for prosthetic sensation. *J Neural Eng* 17(4):046045.
DOI: https://doi.org/10.1088/1741-2552/abacd8 **[verified]**
Summary: Biophysical cortical-column model of ICMS responses used to find pulse-train patterns whose simulated responses approximate measured responses to physical stimuli; an RNN "sensory encoder" then learned the mapping from physical stimulus to biomimetic stimulation pattern and generalized to untrained limb movements/indentations.
Relevance: A model-based inverse for biomimetic ICMS where the inverse is learned *from the model* (not from noisy recordings) — a data-efficient route we could copy: fit a plant, synthesize optimal commands by optimization, then distill into an NN.

### 1.10 Kumaravelu K., Oza C.S., Behrend C.E., Grill W.M. (2018). Model-based deconstruction of cortical evoked potentials generated by subthalamic nucleus deep brain stimulation. *J Neurophysiol* 120(4):1409–1429.
DOI: https://doi.org/10.1152/jn.00862.2017 **[verified]**
Summary: Cortical evoked potentials in healthy and parkinsonian rats at varying DBS frequencies were reproduced by a biophysical thalamocortical network model; short-, intermediate- and long-latency components were attributed to antidromic, recurrent and polysynaptic cortico-thalamo-cortical pathways.
Relevance: Mechanistic gray-box reference for what a rat thalamocortical evoked LFP contains and why multi-pulse responses saturate; useful when deciding which features the forward model must reproduce and why tonic drive collapses to rank 1.

### 1.11 Sombeck J.T., Heye J., Kumaravelu K., Goetz S.M., Peterchev A.V., Grill W.M., Bensmaia S., Miller L.E. (2022). Characterizing the short-latency evoked response to intracortical microstimulation across a multi-electrode array. *J Neural Eng* 19(2):026044.
DOI: https://doi.org/10.1088/1741-2552/ac63e8 **[verified]**
Summary: Artifact-suppressed single-unit responses to ICMS trains in NHP cortex: short high-frequency trains raise firing for ~0.1 s; during long trains the response on the stimulated electrode decays while responses on non-stimulated electrodes persist.
Relevance: Empirical basis for adaptation/saturation under sustained drive — the same phenomenon that makes our plant rank-1 under tonic stimulation and argues for burst-modulated excitation in identification data.

### 1.12 Pandarinath C., O'Shea D.J., Collins J., et al., Sussillo D. (2018). Inferring single-trial neural population dynamics using sequential auto-encoders. *Nature Methods* 15:805–815.
DOI: https://doi.org/10.1038/s41592-018-0109-9 **[verified]**
Summary: LFADS: RNN variational sequential autoencoder that infers single-trial latent dynamics and inferred inputs, denoises spiking, and can stitch sessions. Inputs are inferred rather than measured, but the architecture accommodates known inputs.
Relevance: Reference architecture for a denoising forward model when trial-averaged targets are not available; our "trial averaging" question is what LFADS sidesteps by pooling across trials in the latent space.

### 1.13 Keshtkaran M.R., Sedler A.R., Chowdhury R.H., et al., Pandarinath C. (2022). A large-scale neural network training framework for generalized estimation of single-trial population dynamics. *Nature Methods* 19:1572–1577.
DOI: https://doi.org/10.1038/s41592-022-01675-0 **[verified]**; code https://github.com/arsedler9/lfads-torch
Summary: AutoLFADS automates regularization schedules and hyperparameter search (population-based training), yielding robust single-trial rate estimates across areas and tasks without behavioral labels; provides the PyTorch LFADS implementation.
Relevance: Demonstrates that on small neural datasets, *hyperparameter search and regularization* — not architecture — dominate NN performance; our GRU/MLP results with fixed hyperparameters are not a fair test of the model class.

### 1.14 Ye J., Pandarinath C. (2021). Representation learning for neural population activity with Neural Data Transformers. *Neurons, Behavior, Data analysis, and Theory*; arXiv:2108.01210.
URL: https://arxiv.org/abs/2108.01210 **[verified]**
Summary: Non-recurrent transformer for neural population dynamics matching LFADS on synthetic and motor-cortical data, with 3.9 ms inference (>6× faster than recurrent baselines), within real-time loop budgets.
Relevance: Establishes that transformer inference is real-time-compatible; but on small datasets NDT needed heavy regularization to match LFADS — relevant to our ~28k-tick budget.

### 1.15 Ye J., Collinger J., Wehbe L., Gaunt R. (2023). Neural Data Transformer 2: multi-context pretraining for neural spiking activity. *NeurIPS 2023*.
URL: https://proceedings.neurips.cc/paper_files/paper/2023/hash/fe51de4e7baf52e743b679e3bdba7905-Abstract-Conference.html **[verified]**
Summary: Spatiotemporal transformer pretrained across sessions, subjects and tasks (learned context embeddings, asymmetric encode–decode) that adapts rapidly to novel sessions for iBCI decoding.
Relevance: Shows that pretraining across sessions/animals is the main lever for low-data regimes; our multi-acute archive (275 blocks) could be used the same way for a stim-response forward model.

### 1.16 Ye J., Rizzoglio F., et al. (2025). A generalist intracortical motor decoder (NDT3). *NeurIPS 2025*; bioRxiv 2025.02.02.634313.
DOI: https://doi.org/10.1101/2025.02.02.634313 **[verified]**
Summary: Foundation model pretrained on ~2,000 h of spiking from >30 subjects; with minutes to hours of new-task data it beats multi-session specialist models, with explicit data-scaling curves.
Relevance: Provides the only published data-scaling curves for neural time-series models; there is no analogous pretrained model for stimulation-evoked LFP, which means our NN must be trained from a small, in-lab corpus.

### 1.17 Azabou M., Arora V., Ganesh V., et al., Dyer E.L. (2023). A unified, scalable framework for neural population decoding (POYO). *NeurIPS 2023*; arXiv:2310.16046.
URL: https://arxiv.org/abs/2310.16046 **[verified]**
Summary: Tokenizes individual spikes with learnable unit embeddings and timestamps so one transformer trains across heterogeneous recordings without alignment; supports few-shot transfer to new sessions (POYO+ extends to calcium imaging and multitask).
Relevance: Illustrates session-embedding tricks (learned per-session unit embeddings) that could handle our electrode-map and drift variability across acutes.

### 1.18 Pei F., Ye J., Zoltowski D., et al., Pandarinath C. (2021). Neural Latents Benchmark '21: evaluating latent variable models of neural population activity. *NeurIPS Datasets & Benchmarks 2021*.
URL: https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/hash/979d472a84804b9f647bc185a877a8b5-Abstract-round2.html **[verified]**
Summary: Benchmark suite (4 datasets) and standardized unsupervised metrics (co-smoothing bits/spike, forward prediction) for comparing latent variable models; results show that with careful tuning, several model families converge and that forward prediction is much harder than co-smoothing.
Relevance: Defines the evaluation protocol we should adopt for forward models: held-out-channel co-prediction and *k-step forward prediction*, not just one-step R².

---

## Category 2 — Inverse-model / learned-policy controllers for neurostimulation

### 2.1 ★ Jordan M.I., Rumelhart D.E. (1992). Forward models: supervised learning with a distal teacher. *Cognitive Science* 16:307–354.
DOI: https://doi.org/10.1207/s15516709cog1603_1 **[verified]**
Summary: Shows why direct inverse modelling fails when the plant is many-to-one (non-convex inverse image: averaging valid solutions yields an invalid one) and proposes learning a forward model, then training the controller by backpropagating target errors *through* the forward model (distal teacher).
Relevance: The theoretical diagnosis of our negative result: with a rank-1 plant, many stim vectors map to the same LFP, so a supervised inverse regresses to the conditional mean — the tonic mean we observed. The remedy is forward-model + optimization (what Moure 2026 and Kumaravelu 2020 do).

### 2.2 Chang G.-C., Luh J.-J., Liao G.-D., Lai J.-S., Cheng C.-K., Kuo B.-L., Kuo T.-S. (1997). A neuro-control system for the knee joint position control with quadriceps stimulation. *IEEE Trans Rehabil Eng* 5(1):2–11.
DOI: 10.1109/86.559344 *[DOI unverified]*; PubMed https://pubmed.ncbi.nlm.nih.gov/9086380/ **[verified]**
Summary: A time-delay feedforward NN trained as the *inverse* of the FES-quadriceps-shank system from random-signal experiments, used as a feedforward controller with a fixed-gain PID feedback loop around it ("neuro-PID") to absorb modelling error and disturbances; validated in able-bodied and paraplegic subjects.
Relevance: Early evidence that NN inverses only work when wrapped by a linear feedback loop — the "residual-on-MPC" or "NN feedforward + linear feedback" architecture rather than NN-alone.

### 2.3 Kostov A., Andrews B.J., Popovic D.B., Stein R.B., Armstrong W.W. (1995). Machine learning in control of functional electrical stimulation systems for locomotion. *IEEE Trans Biomed Eng* 42(6):541–551.
DOI: https://doi.org/10.1109/10.387193 **[verified]**
Summary: Adaptive logic networks and inductive learning used to synthesize rule-based FES gait controllers from sensor data; emphasizes learned mappings must be constrained to physiologically safe outputs.
Relevance: Historical anchor for learned neurostimulation policies; the safety/constraint framing matters for our unipolar, amplitude-capped commands.

### 2.4 Liu S., Sock N.M., Ching S. (2018). Learning-based approaches for controlling neural spiking. *American Control Conference 2018*.
DOI: https://doi.org/10.23919/ACC.2018.8431158 **[verified]**
Summary: A "control network" (CONET) is trained to maximize mutual information between its output and realized spiking, learning to induce target patterns in stochastic networks with actuator:neuron ratios >10:1 without an explicit dynamics model.
Relevance: Model-free learned control of underactuated ensembles in simulation — instructive for the underactuation (8 pairs → 64 channels) we face, but never demonstrated in vivo.

### 2.5 Ching S., Ritt J.T. (2013). Control strategies for underactuated neural ensembles driven by optogenetic stimulation. *Front Neural Circuits* 7:54.
DOI: https://doi.org/10.3389/fncir.2013.00054 **[verified]**
Summary: Theory of spike-pattern control for ensembles of uncoupled IF neurons sharing one input; heterogeneity enables non-synchronous control up to biophysical rate limits.
Relevance: Formal statement of what a single common drive can and cannot do to a population — our rank-1 plant is the LFP-scale version of this underactuation.

### 2.6 Newman J.P., Fong M.-f., Millard D.C., Whitmire C.J., Stanley G.B., Potter S.M. (2015). Optogenetic feedback control of neural activity. *eLife* 4:e07192.
DOI: https://doi.org/10.7554/eLife.07192 *[cited from memory; DOI unverified]*
Summary: PI feedback control of population firing rate in cultures and in vivo using optogenetic drive; establishes that simple linear feedback with an integrator gives robust tracking despite plant nonlinearity and drift.
Relevance: Linear feedback contrast that a learned controller must beat; integral action is what covers drift in practice.

### 2.7 Bolus M.F., Willats A.A., Rozell C.J., Stanley G.B. (2021). State-space optimal feedback control of optogenetically driven neural activity. *J Neural Eng* 18(3):036006.
DOI: https://doi.org/10.1088/1741-2552/abb89c **[verified]**
Summary: LQR state feedback with a parameter-adaptive Kalman filter (adapting the process disturbance online) controlled single-unit firing in thalamus of awake mice; simulated multi-output control of a heterogeneous population.
Relevance: Adaptive-estimator + linear optimal control, i.e., the MPC-family answer to drift; the cited contrast for any claim that a learned controller is needed.

### 2.8 Guez A., Vincent R.D., Avoli M., Pineau J. (2008). Adaptive treatment of epilepsy via batch-mode reinforcement learning. *IAAI/AAAI 2008*; and Pineau J., Guez A., Vincent R., Panuccio G., Avoli M. (2009). Treating epilepsy via adaptive neurostimulation: a reinforcement learning approach. *Int J Neural Syst* 19(4):227–240.
URLs: https://www.cs.mcgill.ca/~jpineau/files/guez-iaai08.pdf **[verified]**; DOI 10.1142/S0129065709001987 *[unverified]*
Summary: Fitted Q-iteration with extremely randomized trees learned stimulation policies from labelled in-vitro slice recordings to reduce seizure incidence while minimizing stimulation.
Relevance: Earliest batch (offline) RL for neurostimulation; the offline, tree-based formulation is far more sample-efficient than deep RL and is the kind of RL that could plausibly run on our data volumes.

### 2.9 Krylov D., Tachet des Combes R., Laroche R., Rosenblum M., Dylov D.V. (2020). Reinforcement learning framework for deep brain stimulation study. *IJCAI 2020*; arXiv:2002.10948.
URL: https://arxiv.org/abs/2002.10948 **[verified]**
Summary: PPO agents suppress pathological synchrony in three oscillator-model regimes; robustness to noise characterized; multiple agents remove oscillations.
Relevance: Representative in-silico deep-RL DBS work; millions of environment steps — infeasible on a drifting in-vivo plant.

### 2.10 Lu M., Wei X., Che Y., Wang J., Loparo K.A. (2020). Application of reinforcement learning to deep brain stimulation in a computational model of Parkinson's disease. *IEEE Trans Neural Syst Rehabil Eng* 28(1):339–349.
DOI: https://doi.org/10.1109/TNSRE.2019.2952637 **[verified]**
Summary: Actor–critic RL tuned DBS in a basal-ganglia network model to suppress beta with less energy than continuous DBS.
Relevance: Another in-silico RL result; useful mainly for how they scored charge against effect — our charge-per-tracking metric is comparable.

### 2.11 Gao Q., Naumann M., Jovanov I., Lesi V., Kumaravelu K., Grill W.M., Pajic M. (2020). Model-based design of closed loop deep brain stimulation controller using reinforcement learning. *ACM/IEEE ICCPS 2020*, pp. 108–118; and Gao Q., Schmidt S.L., Chowdhury A., et al., Pajic M. (2023). Offline learning of closed-loop deep brain stimulation controllers for Parkinson disease treatment. *ICCPS 2023*, pp. 44–55.
DOI (2023): https://doi.org/10.1145/3576841.3585925 **[verified]**; 2020 IEEE Xplore 9096004
Summary: 2020: RL controller trained against a biophysical BG model. 2023: offline RL that learns closed-loop DBS controllers from previously logged clinical stimulation data, with off-policy evaluation, to avoid unsafe online exploration.
Relevance: Offline RL from logged excitation/tracking blocks is the only RL variant compatible with a 30-min-drifting acute; the 2023 paper is the template.

### 2.12 Pan M., Schrum M., Myers V., Bıyık E., Dragan A. (2024). Coprocessor Actor Critic: a model-based reinforcement learning approach for adaptive brain stimulation. *ICML 2024*; arXiv:2406.06714.
URL: https://arxiv.org/abs/2406.06714 **[verified]**
Summary: Model-based RL that learns a stimulation policy for a "neural coprocessor" by separately learning how the (injured) brain responds to stimulation and how to act; more sample-efficient than model-free RL on neurologically realistic injury simulations.
Relevance: Reinforces the pattern that learning a forward model first is what makes learned neurostimulation sample-efficient.

### 2.13 Ravivarapu H., Bagwe G., Yuan X., Yu C., Zhang L. (2025). SEA-DBS: sample-efficient reinforcement learning controller for deep brain stimulation in Parkinson's disease. *IEEE IMC 2025*; arXiv:2507.06326.
URL: https://arxiv.org/abs/2507.06326 **[verified]**
Summary: Actor–critic with a predictive reward model and Gumbel-softmax exploration in a binary action space; faster convergence and beta suppression in a BG simulation; FP16-quantized policy retains performance for embedded use.
Relevance: Shows the current state of RL-DBS: still simulation-only, with sample efficiency the acknowledged bottleneck.

### 2.14 Carter N., Gupta A., Ganguli P., Dietrich B., Krishna V., Chakraborty S. (2025). In-vivo training for deep brain stimulation. arXiv:2510.03643.
URL: https://arxiv.org/abs/2510.03643 **[verified]**
Summary: TD3 agent modulating frequency and amplitude using biomarkers that are actually measurable in patients (rather than simulation-only ones); reports greater biomarker suppression than clinical aDBS in simulation despite the title.
Relevance: Highlights that RL work is still gated on measurable feedback signals; our S1 LFP target is measurable, which is an advantage, but per-tick 8-D continuous actions are far harder than their 2-D case.

### 2.15 Gupta A., et al. (2026). Bandit algorithms for deep brain stimulation. *ACM/IEEE ICCPS 2026*; arXiv:2601.12699.
URL: https://arxiv.org/abs/2601.12699 **[verified]**
Summary: Time- and threshold-triggered pruned multi-armed bandit jointly tunes frequency and amplitude with no offline training, converging in <2 min on a microcontroller and outperforming deep-RL baselines in beta suppression and power.
Relevance: For slow, low-dimensional parameter choices (electrode pair selection, gain scaling) a bandit is more practical than deep RL and could sit above our MPC.

### 2.16 Nguyen B., Josephson C., Teodorescu M., Cauwenberghs G., Eshraghian J. (2026). Neuromorphic energy-aware learning for adaptive deep brain stimulation. arXiv:2606.28600.
URL: https://arxiv.org/abs/2606.28600 **[verified]**
Summary: Deep spiking Q-network trained in a cortico-BG-thalamic model suppresses alpha–beta by 45.2% with 80% less charge than continuous DBS; deployed on a SynSense Xylo neuromorphic chip at 0.52 mW (28× less energy/inference than an ANN on edge hardware).
Relevance: Example of a learned policy compressed for deterministic embedded inference; charge-aware reward shaping is relevant to our charge-efficiency metric.

### 2.17 ★ Coventry B.S., Bartlett E.L. (2024). Protocol for artificial intelligence-guided neural control using deep reinforcement learning and infrared neural stimulation. *STAR Protocols* 6(1):103496.
DOI: https://doi.org/10.1016/j.xpro.2024.103496 **[verified]**
Summary: TD3 (twin-delayed DDPG) actor–critic trained *in vivo* in anesthetized rats to drive auditory-cortex firing toward target distributions by adjusting infrared stimulation of auditory thalamus (pulse number, power, width, ISI); the "SpikerNet" agent finds parameter sets targeting arbitrary firing states in small iteration counts. (The same group's computational SpikerNet DBS paper is Cho et al. 2023.)
Relevance: The only in-vivo RL neurostimulation demonstration in a thalamus→cortex anesthetized-rat preparation — the same preparation class as ours. Note it optimizes a handful of slowly varying parameters per episode, not a 100 Hz vector command; that is the granularity at which RL is currently feasible.

### 2.18 Madondo M., Verma D., Ruthotto L., Au Yong N. (2023). Learning control policies of Hodgkin-Huxley neuronal dynamics. *ML4H 2023*; arXiv:2311.07563.
URL: https://arxiv.org/abs/2311.07563 **[verified]**
Summary: Offline NN value-function approximation using Pontryagin/HJB structure to produce real-time feedback stimulation for HH neurons; robust to out-of-distribution states and disturbances.
Relevance: A principled "learn the value function offline, act online" alternative that keeps the online step trivial; interesting if our plant were reliably nonlinear.

### 2.19 Borda L., Gozzi N., Preatoni G., Valle G., Raspopovic S. (2023). Automated calibration of somatosensory stimulation using reinforcement learning. *J NeuroEng Rehabil* 20:131.
DOI: https://doi.org/10.1186/s12984-023-01246-0 **[verified]**
Summary: RL agent (trained on 49 subjects) automatically maps TENS parameters to evoked sensations; on 15 nerves in 5 subjects it beat naive and brute-force search and matched expert experimenters while cutting mapping time.
Relevance: RL used as a *calibration* tool over a small discrete parameter space — the realistic role for RL in a sensory prosthesis today.

### 2.20 ★ Steffen S., Cannon M. (2025). Deep learning model predictive control for deep brain stimulation in Parkinson's disease. arXiv:2504.00618.
URL: https://arxiv.org/abs/2504.00618 **[verified]**
Summary: Nonlinear data-driven MPC whose multi-step predictor is a *difference of input-convex neural networks* (keeps the MPC problem tractable), trained on beta-band responses fitted to PD patient data; cut tracking error and control activity by >20% versus P, PI and thresholded-switching aDBS.
Relevance: The cleanest "learned dynamics + MPC" recipe for neurostimulation: a multi-step ICNN predictor drops into an MPC exactly where our ARX sits, preserves convexity for a 10 ms solve, and is validated against linear baselines the way we should validate.

### 2.21 Fehrman C., Meliza C.D. (2025). Model predictive control on the neural manifold. *Neural Computation* 37(12):2125–; arXiv:2406.14801.
URL: https://arxiv.org/abs/2406.14801 **[verified]**
Summary: Data-driven latent dynamics of a spiking-network model controlled by MPC versus PID under partial observability; MPC was consistently more accurate and needed less hand tuning.
Relevance: Supports controlling a *low-dimensional latent* (our rank-1/3 subspace) rather than 64 raw channels, and MPC over PID.

### 2.22 Li Y., Shanechi M.M. (2025). Modulation of nonlinear neural dynamics for closed-loop deep brain stimulation systems. *IEEE EMBC 2025*.
DOI: https://doi.org/10.1109/embc58623.2025.11252898 **[verified]**
Summary: Head-to-head of LSSM, Koopman-operator, and RNN + iterative LQR (iLQR) for identification and control in biologically inspired closed-loop DBS simulations; RNN-iLQR won on both, while Koopman struggled with observable selection under limited data.
Relevance: Direct comparison of the three model classes we have discussed (linear, Koopman, RNN) inside a control loop; note that the RNN is used as a *forward* model with trajectory optimization, never as an inverse.

### 2.23 Proctor J.L., Brunton S.L., Kutz J.N. (2016). Dynamic mode decomposition with control. *SIAM J Appl Dyn Syst* 15(1):142–161; and Marrouch N., Slawinska J., Giannakis D., Read H.L. (2020). Data-driven Koopman operator approach for computational neuroscience. *Ann Math Artif Intell* 88:1155–1173.
DOIs: https://doi.org/10.1137/15M1013857 ; https://doi.org/10.1007/s10472-019-09666-2 **[verified via search records]**
Summary: DMDc extracts low-order linear input–output models from high-dimensional data with actuation (a close cousin of N4SID/ARX); Marrouch applies Koopman eigendecomposition to electrophysiology.
Relevance: DMDc on our 64-ch LFP with 8-D input is a one-line alternative fitter that exposes rank explicitly; Koopman lifting is only worthwhile if a nonlinearity is demonstrated first (see 2.22, 4.x).

### 2.24 Nagabandi A., Kahn G., Fearing R.S., Levine S. (2018). Neural network dynamics for model-based deep RL with model-free fine-tuning. *ICRA 2018*; and Chua K., Calandra R., McAllister R., Levine S. (2018). Deep RL in a handful of trials using probabilistic dynamics models (PETS). *NeurIPS 2018*.
URLs: https://arxiv.org/abs/1708.02596 ; https://arxiv.org/abs/1805.12114 *[method references; not neuro]*
Summary: Learn an NN dynamics model, then plan with MPC (random-shooting/CEM); PETS adds probabilistic ensembles and trajectory sampling to handle model uncertainty, matching model-free RL with orders-of-magnitude fewer samples.
Relevance: Method blueprints for "NN forward model + MPC" with uncertainty-aware planning; ensembles would give us a principled way to fall back to the linear MPC when the NN model is uncertain.

### 2.25 Grado L.L., Johnson M.D., Netoff T.I. (2018). Bayesian adaptive dual control of deep brain stimulation in a computational model of Parkinson's disease. *PLoS Comput Biol* 14(12):e1006606.
DOI: https://doi.org/10.1371/journal.pcbi.1006606 **[verified]**
Summary: Inner feedback stimulator + outer Bayesian-optimization loop that balances exploration/exploitation to tune stimulation parameters in few evaluations.
Relevance: Two-timescale architecture (fast linear feedback inside, slow BO outside) — a natural way to add learning on top of our MPC without touching the 10 ms loop.

### 2.26 Laferrière S., Bonizzato M., Côté S.L., Dancause N., Lajoie G. (2020). Hierarchical Bayesian optimization of spatiotemporal neurostimulations for targeted motor outputs. *IEEE Trans Neural Syst Rehabil Eng* 28(6):1452–1460.
DOI: 10.1109/TNSRE.2020.2987001 *[unverified]*; IEEE Xplore 9062604 **[verified]**
Summary: GP-BO on a hierarchy of increasingly complex stimulation spaces learns which multi-electrode spatiotemporal M1 patterns evoke target EMG patterns in NHP where flat search fails.
Relevance: Hierarchical search (pairs → pairs+timing → full pattern) is a concrete way to handle our 8-D command space with tens, not thousands, of trials.

### 2.27 Losanno E., Badi M., Wurth S., et al., Micera S. (2021). Bayesian optimization of peripheral intraneural stimulation protocols to evoke distal limb movements. *J Neural Eng* 18(6):066046.
DOI: https://doi.org/10.1088/1741-2552/ac3f6c **[verified]**
Summary: Multi-output GP BO with task-specific objectives tunes intraneural stimulation protocols to evoke functional movements efficiently.
Relevance: Multi-output GP as a surrogate over 64 channels of evoked response is a low-data alternative to an NN forward model for per-session tuning.

### 2.28 ★ Bonizzato M., Guay Hottin R., Côté S.L., Massai E., Choinière L., Macar U., Laferrière S., Sirpal P., Quessy S., Lajoie G., Martinez M., Dancause N. (2023). Autonomous optimization of neuroprosthetic stimulation parameters that drive the motor cortex and spinal cord outputs in rats and monkeys. *Cell Reports Medicine* 4(4):101008.
DOI: https://doi.org/10.1016/j.xcrm.2023.101008 **[verified]**
Summary: GP-BO autonomously selects stimulation parameters in real time across brain and spinal cord, rats and NHP, healthy and injured, with immediate and multi-session continual learning; beats other search strategies after testing only a fraction of the space and benefits from expert priors.
Relevance: The best-validated learning agent in a rat neurostimulation setting; the exact tool for the *outer* problem (which pairs/gains produce touch-like S1 patterns) that our MPC does not address.

### 2.29 Fleming J.E., Pont Sanchis I., Lemmens O., Denison-Smith A., West T.O., Denison T., Cagnan H. (2023). From dawn till dusk: time-adaptive Bayesian optimization for neurostimulation. *PLoS Comput Biol* 19(12):e1011674.
DOI: https://doi.org/10.1371/journal.pcbi.1011674 **[verified]**
Summary: Time-varying BO tracks slowly drifting and periodically varying optima of phase-locked DBS parameters, outperforming static controllers.
Relevance: Directly addresses our ~30-min plant drift at the outer-loop level: a forgetting GP kernel rather than a fixed model.

### 2.30 Wernisch L., et al. (2024). Online Bayesian optimization of vagus nerve stimulation. *J Neural Eng* 21(2):026019.
DOI: https://doi.org/10.1088/1741-2552/ad33ae **[verified]**
Summary: GP-BO over VNS waveforms in pigs converges to target heart-rate changes in few iterations despite inter-subject variability, using uncertainty estimates to avoid unsafe parameters.
Relevance: In-vivo evidence that GP uncertainty can enforce safety bounds during search — the same mechanism could keep amplitude under our hard cap while exploring.

### 2.31 Küçükoğlu B., Soo L., Leeftink D., Grani F., Soto Sanchez C., Güçlü U., van Gerven M., Fernández E. (2025). Bayesian optimization of cortical neuroprosthetic vision using perceptual feedback. *J Neural Eng*.
DOI: https://doi.org/10.1088/1741-2552/adeae9 (preprint 10.1101/2025.01.24.634528) **[verified]**
Summary: Trust-region BO over 40 electrode currents (0–50 µA each, 500 µA total budget) in a blind participant with a 96-ch array; ratings converged to higher values than random generation, with current reallocated to effective electrodes.
Relevance: BO over a per-electrode current vector with a total-charge constraint — structurally identical to choosing our 8 amplitudes under a cap.

### 2.32 Küçükoğlu B., Rueckauer B., de Ruyter van Steveninck J., et al., van Gerven M. (2025). End-to-end learning of safe stimulation parameters for cortical neuroprosthetic vision. *J Neural Eng*.
DOI: https://doi.org/10.1088/1741-2552/ade918 **[verified]**
Summary: Learns amplitude/pulse-width/frequency encoders end-to-end through a differentiable phosphene simulator with explicit charge-safety constraints; safe constraints preserved reconstruction quality.
Relevance: Shows how to bake unipolar/cap/charge constraints into NN training (constrained parametrization + penalty) rather than clipping after the fact.

### 2.33 Downing M., Peng M., Granley J., Beyeler M., Bultan T. (2026). Fuzzing the brain: automated stress testing for the safety of ML-driven neurostimulation. *J Neural Eng*.
DOI: https://doi.org/10.1088/1741-2552/ae4927 **[verified]**
Summary: Coverage-guided fuzzing of deep-learning stimulation encoders finds inputs that push outputs past charge-density, current and active-electrode limits, with coverage metrics for comparing architectures.
Relevance: A validation step we should run on any exported NN controller before it drives the stimulator (our y-liveness and cap rules are the runtime guard; fuzzing is the offline guard).

### 2.34 Sarikhani P., Hsu H.-L., Zeydabadinezhad M., Yao Y., Kothare M., Mahmoudi B. (2022). Automated tuning of closed-loop neuromodulation control systems using Bayesian optimization. *IEEE EMBC 2022*.
DOI: 10.1109/EMBC48229.2022.9871006 *[unverified]*; PubMed 36085689 **[verified]**
Summary: BO tunes PI-controller gains for set-point neuromodulation in a mean-field model of stimulated neural populations.
Relevance: BO can equally tune our MPC weights/horizon per session — cheaper than learning a new controller.

### 2.35 Johnsen K.A., Cruzado N.A., Menard Z.C., Willats A.A., Charles A.S., Markowitz J.E., Rozell C.J. (2026). Bridging model and experiment in systems neuroscience with Cleo: the closed-loop, electrophysiology, and optophysiology simulation testbed. *J Neurosci* 46(1):e2239242025.
URL: https://cleosim.readthedocs.io ; bioRxiv https://doi.org/10.1101/2023.01.27.525963 **[verified]**; J Neurosci DOI *[unverified]*
Summary: Brian2-based testbed injecting electrodes, optogenetics and closed-loop controllers (with latency) into spiking-network simulations; includes LQR/MPC tutorials.
Relevance: Off-the-shelf environment for pre-testing learned controllers under realistic loop latency before an acute.

---

## Category 3 — System identification for low-SNR, low-rank, drifting plants

### 3.1 ★ Bolus M.F., Willats A.A., Whitmire C.J., Rozell C.J., Stanley G.B. (2018). Design strategies for dynamic closed-loop optogenetic neurocontrol in vivo. *J Neural Eng* 15(2):026011.
DOI: https://doi.org/10.1088/1741-2552/aaa506 **[verified]**
Summary: In rodent somatosensory thalamus, fits a linear-nonlinear-Poisson model of firing rate vs light *during the experiment*, uses it to design a PI controller, and tracks sinusoidal and non-sinusoidal rate targets with disturbance rejection; discusses estimator (exponential filter) bandwidth vs noise trade-offs and how identification data should span the intended operating range.
Relevance: A practical guide for the same preparation class (rodent thalamus, anesthetized/awake): identify a low-order model around the operating point from short excitation, then use integral feedback; it argues against over-parameterized models at this SNR.

### 3.2 Sani O.G., Abbaspourazad H., Wong Y.T., Pesaran B., Shanechi M.M. (2021). Modeling behaviorally relevant neural dynamics enabled by preferential subspace identification. *Nature Neuroscience* 24:140–149.
DOI: https://doi.org/10.1038/s41593-020-00733-0 **[verified]**
Summary: PSID is a subspace-ID variant that prioritizes latent states predictive of a secondary signal, finding that relevant dynamics are lower-dimensional than standard SID implies.
Relevance: Use the *target S1 touch response* as the "behavior" signal so the identified stim→LFP model prioritizes the subspace that matters for tracking.

### 3.3 Yang Y., Ahmadipour P., Shanechi M.M. (2021). Adaptive latent state modeling of brain network dynamics with real-time learning rate optimization. *J Neural Eng* 18(3):036013.
DOI: https://doi.org/10.1088/1741-2552/abcefd **[verified]**; code https://github.com/ShanechiLab/AdaptiveLSSM
Summary: Recursive adaptive LSSM identification with online optimization of the forgetting/learning rate; tracks non-stationary network dynamics and beats non-adaptive fits, especially at low latent dimension.
Relevance: Exactly our situation (30-min drift, low rank): a recursive ARX/LSSM update with a tuned forgetting factor is the literature's answer, and cheaper than retraining an NN.

### 3.4 Ahmadipour P., Yang Y., Chang E.F., Shanechi M.M. (2021). Adaptive tracking of human ECoG network dynamics. *J Neural Eng* 18(1):016011.
DOI: 10.1088/1741-2552/abae42 *[unverified]*; PubMed 33624610 **[verified]**
Summary: Across 10 ECoG subjects, adaptive modeling improved prediction over static models and allowed further dimensionality reduction, i.e., non-stationarity is real at the field-potential scale.
Relevance: Supports our "feedback adapts vs replay" finding and argues for online adaptation in every deployed model, NN or linear.

### 3.5 Keshtkaran M.R., Pandarinath C. (2019). Enabling hyperparameter optimization in sequential autoencoders for spiking neural data. *NeurIPS 2019*; arXiv:1908.07896.
URL: https://arxiv.org/abs/1908.07896 **[verified]**
Summary: Identifies a form of overfitting in sequential autoencoders undetectable by standard validation; introduces sample validation (held-out samples) and coordinated dropout (forces models to learn only structure shared across channels).
Relevance: Our held-out R² ≈ 0 could be masking, not lack of signal: coordinated dropout across the 64 LFP channels is a cheap regularizer well-suited to a rank-1 shared signal buried in channel noise.

### 3.6 Degenhart A.D., Bishop W.E., Oby E.R., et al., Yu B.M. (2020). Stabilization of a brain–computer interface via the alignment of low-dimensional spaces of neural activity. *Nature Biomedical Engineering* 4:672–685.
DOI: https://doi.org/10.1038/s41551-020-0542-9 **[verified]**
Summary: Aligns the low-dimensional manifold of new recordings to a reference so a fixed decoder keeps working through abrupt instabilities in NHP online BCI.
Relevance: Latent-space alignment is a low-cost way to reuse an NN plant model across acutes/electrode maps instead of retraining from scratch.

### 3.7 Karpowicz B.M., Ali Y.H., Wimalasena L.N., et al., Pandarinath C. (2025). Stabilizing brain–computer interfaces through alignment of latent dynamics. *Nature Communications* 16.
DOI: https://doi.org/10.1038/s41467-025-59652-y **[verified]**
Summary: NoMAD uses unsupervised distribution alignment onto an RNN dynamics model to keep decoding stable over weeks to months without recalibration.
Relevance: If we ever pretrain a forward model across animals, NoMAD-style alignment is how it would transfer to a new acute.

### 3.8 Basu I., Yousefi A., Crocker B., et al., Widge A.S. (2021). Closed-loop enhancement and neural decoding of cognitive control in humans. *Nature Biomedical Engineering* 7:576–588.
DOI: https://doi.org/10.1038/s41551-021-00804-y **[verified]**
Summary: Closed-loop capsular stimulation triggered on decoded lapses in cognitive control improved task performance more than open-loop; decoders used few electrodes with implant-compatible features.
Relevance: Example of a linear, low-feature, implant-realistic closed loop that produced a behavioral gain; a reminder that closed-loop *triggering* with a simple model can beat elaborate open-loop tapes.

### 3.9 Nozari E., Bertolero M.A., Stiso J., et al., Pappas G.J., Bassett D.S. (2024). Macroscopic resting-state brain dynamics are best described by linear models. *Nature Biomedical Engineering* 8:68–84.
DOI: https://doi.org/10.1038/s41551-023-01117-y **[verified]**
Summary: Across iEEG (122 subjects) and fMRI (700 subjects), linear autoregressive models won on predictive power, complexity and residual structure against a broad family of nonlinear models (incl. deep nets); nonlinearity is averaged away at the macro scale and by noise.
Relevance: The strongest published prior that at the LFP scale and our SNR a regularized ARX is close to the Bayes-optimal model class; it sets the burden of proof on any nonlinear model.

---

## Category 4 — Comparisons of model classes on stimulation-response data; gray-box models

### 4.1 Sani O.G., Pesaran B., Shanechi M.M. (2024). Dissociative and prioritized modeling of behaviorally relevant neural dynamics using recurrent neural networks. *Nature Neuroscience* 27:2033–2045.
DOI: https://doi.org/10.1038/s41593-024-01731-2 **[verified]**
Summary: DPAD (multi-section RNN) improves neural–behavior prediction across four tasks (spikes and LFP) and, importantly, localizes *where* nonlinearity helps: mostly in the readout/embedding maps rather than in the recurrent dynamics.
Relevance: Evidence for "linear dynamics + nonlinear input/output maps" as the right nonlinear upgrade for LFP-scale data — i.e., MLP readout on top of ARX latent rather than a GRU end-to-end.

### 4.2 Li & Shanechi 2025 EMBC (entry 2.22) — LSSM vs Koopman vs RNN-iLQR in closed-loop DBS simulation: RNN forward model + trajectory optimization wins; Koopman brittle under limited data.

### 4.3 Bryan et al. 2025 TBFM (entry 1.7) — basis-function forward model ≈ nonlinear DS model > LSSM on 40 NHP optogenetic sessions, at 0.2 ms latency and 15–20 min of data.

### 4.4 Vaziri et al. 2025 (entry 1.6) — DFINE ≥ GRU > LSSM on iEEG forecasting; gain concentrated in high-gamma.

### 4.5 Nozari et al. 2024 (entry 3.9) — linear AR best at macroscale.

### 4.6 Martínez S., Sánchez-Peña R.S., García-Violini D. (2024). Controlling neural activity: LPV modelling of optogenetically actuated Wilson–Cowan model. *J Neural Eng* 21(3).
DOI: https://doi.org/10.1088/1741-2552/ad4212 **[verified]**
Summary: Reformulates the Wilson–Cowan model as a linear-parameter-varying system so linear robust-control synthesis applies; an LPV controller regulates neural activity under nonlinearity, noise and uncertainty.
Relevance: Gray-box middle ground: keep our linear MPC but schedule the ARX gains on a measured operating variable (e.g., tonic level / recent stim history) — a "gain-scheduled MPC" that captures saturation without an NN.

### 4.7 Tian Y., Saradhi S., Bello E., Johnson M.D., D'Eleuterio G., Popovic M.R., Lankarany M. (2024). Model-based closed-loop control of thalamic deep brain stimulation. *Front Netw Physiol* 4:1356653.
DOI: https://doi.org/10.3389/fnetp.2024.1356653 **[verified]**
Summary: Hybrid pipeline: biophysical Vim model with short-term synaptic plasticity (Tsodyks–Markram) fitted to human DBS recordings, a data-driven polynomial decoder to EMG, and PID on stimulation frequency; predicts the clinical 130 Hz optimum.
Relevance: Demonstrates that a short-term-plasticity term is what a stimulation-response model needs to reproduce frequency-dependent saturation — a physically motivated nonlinearity we could add to ARX (input-side depression) instead of a black box.

### 4.8 Kumaravelu et al. 2018 (entry 1.10) — biophysical deconstruction of rat cortical evoked potentials under thalamocortical/DBS drive.

### 4.9 Acharya G., Ruf S.F., Nozari E. (2022). Brain modeling for control: a review. *Front Control Eng* 3:1046764.
DOI: https://doi.org/10.3389/fcteg.2022.1046764 **[verified]**
Summary: Reviews mechanistic vs data-driven brain models for each stimulation modality from a controllability standpoint; concludes that low-order linear/latent models remain the dominant practical choice and that data-driven nonlinear models lack validated control demonstrations.
Relevance: Good citation for the framing of our NN-vs-MPC comparison and its (so far) negative result.

### 4.10 Oliveira A.M., Coelho L., Carvalho E., Ferreira-Pinto M.J., Vaz R., Aguiar P. (2023). Machine learning for adaptive deep brain stimulation in Parkinson's disease: closing the loop. *J Neurol* 270:5313–5326.
DOI: https://doi.org/10.1007/s00415-023-11873-1 **[verified]**
Summary: Review noting that RL "has not yet been employed" clinically for PD DBS, that aDBS should run low-complexity algorithms for power reasons, and that long-term datasets are the gating resource.
Relevance: Independent confirmation that learned controllers remain pre-clinical, and that deployment constraints favour simple models.

---

## Category 5 — Real-time deployment of learned models; training-data budgets

### 5.1 Willsey M.S., Nason-Tomaszewski S.R., Ensel S.R., Temmar H., Mender M.J., Costello J.T., Patil P.G., Chestek C.A. (2022). Real-time brain–machine interface in non-human primates achieves high-velocity prosthetic finger movements using a shallow feedforward neural network decoder. *Nature Communications* 13:6899.
DOI: https://doi.org/10.1038/s41467-022-34452-w **[verified]**
Summary: A shallow feedforward NN decoder run in real time (xPC/Simulink) gave 36% higher throughput than ReFIT-KF for 2-DoF finger control in two macaques; the nonlinear gain came from a small MLP, not a deep recurrent model.
Relevance: Existence proof that a *shallow* MLP deployed deterministically can beat the linear standard in a closed loop — and that this was achieved with a simple architecture, careful feature design, and online recalibration.

### 5.2 Ye & Pandarinath 2021 NDT (entry 1.14) — 3.9 ms transformer inference, within real-time budgets.

### 5.3 Erturk E., Shanechi M.M. (2025). Dynamical modeling of nonlinear latent factors in multiscale neural activity with real-time inference. *NeurIPS 2025*; arXiv:2512.12462.
URL: https://arxiv.org/abs/2512.12462 **[verified]**
Summary: Multiscale (spike + LFP, different rates, missing samples) nonlinear latent model with recursive real-time decoding; beats linear and nonlinear multimodal baselines on three datasets.
Relevance: Shows that DFINE-family models keep a Kalman-style recursive inference that is deterministic and cheap enough for a 10 ms loop.

### 5.4 Bryan et al. 2025 TBFM (entry 1.7) — 0.2 ms CPU latency; 2–4 min training; 15–20 min data per session.

### 5.5 Nguyen et al. 2026 (entry 2.16) — policy compressed to a 0.52 mW neuromorphic chip. Ravivarapu et al. 2025 (entry 2.13) — FP16 quantization retained performance. Gupta et al. 2026 (entry 2.15) — bandit converges in <2 min on a microcontroller.

### 5.6 Ye et al. 2025 NDT3 (entry 1.16) and Ye et al. 2023 NDT2 (entry 1.15) — published data-scaling curves: minutes-to-hours of new-session data suffice *only* with large cross-session pretraining; specialist models trained from scratch need hours per session.

### 5.7 Bonizzato et al. 2023 (entry 2.28) and Laferrière et al. 2020 (entry 2.26) — GP-BO reaches near-optimal stimulation in tens of trials per session; Küçükoğlu et al. 2025 (entry 2.31) — BO over 40 currents converged within a single human session.

### 5.8 Keshtkaran et al. 2022 AutoLFADS (entry 1.13) — on small datasets, population-based hyperparameter search matters more than model class.

### 5.9 Moure et al. 2026 (entry 1.8) — real-time inverse network for stimulation synthesis deployed in a human implant loop; the forward model was trained on within-session single-trial data plus resting-state conditioning.

---

## Diagnosis and recommendations for our NN methodology

**(a) Is direct supervised inverse learning the wrong formulation at this SNR and rank?**

1. Yes, and the literature predicted the exact symptom. Jordan & Rumelhart (2.1) show that when the plant is many-to-one (our rank-1 tonic plant means an 8-D command maps to a ~1-D LFP effect), minimizing MSE from output features to command returns the *conditional mean* of all commands consistent with the output — the tonic mean. The R² ≈ 0 held-out result and the collapse of the open-loop tape are the textbook distal-teacher failure, not a training bug.
2. Every recent success (Moure 2026, 1.8; Kumaravelu 2020, 1.9; Steffen & Cannon 2025, 2.20; Li & Shanechi 2025, 2.22; Pan 2024, 2.12) learns a **forward** model and derives commands by optimization (gradient through the forward model, iLQR, or MPC). Where an inverse network is used (Moure), it is trained *through* the forward model and conditioned on the current state, then used only for speed. Our "inverse" mode should be re-cast as: (i) NN forward model, (ii) MPC/gradient synthesis, (iii) optional distillation into a fast inverse for the C++ server.
3. The most defensible formulation for our data is **residual-on-MPC**: keep the ARX plant and MPC as the base, and let the NN learn only (a) a static nonlinear readout/observation map (DPAD 4.1 and DFINE 1.4 show that is where nonlinearity lives at LFP scale) or (b) a forward residual/multi-step correction (TBFM 1.7, ICNN predictor 2.20). Chang 1997 (2.2) is the historical precedent: NN feedforward only worked with a linear feedback loop around it.
4. Deep RL on the per-tick 8-D command at 100 Hz is not supported by any in-vivo result. All DBS-RL papers (2.9–2.16) are simulation-only; the one in-vivo RL (Coventry & Bartlett 2.17, same anesthetized-rat thalamus→cortex preparation class) optimizes a few slow parameters per episode. If RL is used, use offline RL from logged blocks (Gao 2023, 2.11) or a bandit/BO outer loop (2.15, 2.25, 2.28) over pair weights and MPC gains, not over the tick-level command.
5. Bayesian optimization is the learning method with the best in-vivo track record in rats (Bonizzato 2.28, Laferrière 2.26) and with drift handling (Fleming 2.29). It should own the *outer* problem (which pairs, what gains, what target scaling reproduce touch-like S1 patterns) while MPC owns the inner loop.

**(b) Input design for training data**

6. Yang 2021 (1.1) identified linear stim→LFP models with *random amplitude- and frequency-modulated* pulse trains, and Bolus 2018 (3.1) stresses spanning the operating range; a pure PRBS on amplitude at constant pulse rate only excites the tonic (rank-1) mode. Training captures should be **burst-modulated** (random burst on/off, random inter-burst gaps ≥ the adaptation time-constant seen by Sombeck 2022, 1.11) with amplitude PRBS/multisine *inside* bursts, so the un-adapted, higher-rank dynamics are exercised — this is the acute-#3 "burst-probing lever".
7. Use a mid-range **bias/operating point** and identify deviations (ΔLFP vs Δamplitude) so both directions are excited despite unipolar commands; the LPV/gain-scheduled view (Martínez 2024, 4.6) and short-term-depression terms (Tian 2024, 4.7) are the natural way to encode the amplitude-dependent gain we see.
8. For forward-model training, single-trial data with many repeats is fine (LFADS/AutoLFADS, TBFM), but the *loss* should be multi-step forecasting of the stim-evoked deviation (BRAID 1.5; Steffen & Cannon 2.20), not one-step prediction; one-step R² can be near zero while the k-step evoked-response prediction is usable. For inverse/controller training, use **trial-averaged or model-denoised targets** so the distal teacher is not itself noise-dominated.
9. Add noise-aware regularization proven on small neural datasets: coordinated dropout and sample validation (Keshtkaran 2019, 3.5) exploit exactly the shared low-rank structure our plant has; heteroscedastic/Gaussian NLL losses so channels at floor SNR do not dominate; input augmentation by resampling stim history windows.

**(c) Data budget and pretraining**

10. Our ~28k ticks (~4.7 min at 100 Hz) is below what any published nonlinear stim-response model used: TBFM needed 15–20 min/session (1.7), Yang 2021 used many minutes of randomized stimulation per session, and NDT2/NDT3 (1.15–1.16) show that from-scratch specialist models need hours unless pretrained. Plan ≥15–20 min of excitation per acute, and treat the 275-block archive as a pretraining corpus with per-session/animal embeddings (POYO 1.17) plus latent alignment (Degenhart 3.6, NoMAD 3.7) for the new acute.
11. Because no pretrained stimulation-response model exists, the *recursive adaptive LSSM/ARX* (Yang & Ahmadipour 2021, 3.3; Ahmadipour 2021, 3.4) with a tuned forgetting factor is the only drift solution with in-vivo evidence; any NN plant must have an equivalent online adaptation (at least an adaptive output bias/gain) or it will lose to the adapting linear model within 30 min.
12. Hyperparameter search dominates model class on small data (AutoLFADS 1.13); before concluding "GRU fails", run a population-based search with sample validation on the forward-modelling task, not the inverse.

**(d) How others validated that a learned controller beats a linear one**

13. The accepted evidence chain is: (i) held-out single-trial forward-prediction accuracy vs an LSSM/ARX baseline, with k-step-ahead curves (Yang 2021, TBFM, DFINE-iEEG, NLB protocol 1.18); (ii) closed-loop tracking error and control effort vs the linear/PID/LQR controller on the *same* plant and targets (Steffen & Cannon: >20% lower error and effort than P/PI/threshold; Fehrman & Meliza: MPC vs PID; Willsey: 36% throughput over ReFIT-KF); (iii) interleaved A/B arms within a session to cancel drift (Bonizzato multi-session continual learning; our own interleaved-run builder does this). Reporting only open-loop tape performance, as we did for the NN, is not how any of these groups established a win.
14. Report sample-efficiency curves (performance vs minutes of training data) — the metric that decides whether an NN is worth a longer excitation block in a 30-min-drift preparation.

**(e) Which architectures the literature actually shows helping over linear on LFP-scale data**

15. Not end-to-end GRUs as inverses. What has helped: (1) **linear latent dynamics + nonlinear observation map** (DFINE 1.4/1.6; DPAD 4.1 localizes nonlinearity to readouts); (2) **basis-function / linear-in-parameters forward models with state-dependent gain** (TBFM 1.7) that match nonlinear DS models at ~0.2 ms latency; (3) **input-convex NN multi-step predictors** inside MPC (2.20) that preserve a convex 10 ms solve; (4) **shallow MLPs** deployed in real time (Willsey 5.1). At the macroscale-LFP level, linear AR remains the best-supported prior (Nozari 3.9); Koopman lifting was brittle under limited data (Li & Shanechi 2.22).
16. Concrete next architecture for us: ARX/IPSID latent (rank 2–3, fit with PSID using the touch-response as the prioritized signal) → MLP readout to 64 channels, with an input-side short-term-depression nonlinearity (4.7) and an ICNN multi-step residual; keep MPC as the controller; distill the MPC solution into a small inverse MLP only for latency, and fuzz-test it against the amplitude cap (Downing 2.33; Küçükoğlu 2.32) before it touches the stimulator.
17. Safety/constraints: encode unipolarity and the cap in the NN parametrization (softplus/sigmoid-scaled outputs, charge penalty) as in 2.32, and keep the runtime y-liveness/cap guards independent of the learned model.
18. Deployment: all real-time successes use deterministic, recursive inference (Kalman-style filters in DFINE-family models, feedforward MLPs, basis models); avoid architectures with variable-length attention over history in the 10 ms loop, and quantize/export with a fixed compute budget (2.13, 2.16).
19. A two-timescale program is what the evidence supports: inner loop = adaptive ARX-MPC (linear, recursive, proven); middle = NN forward residual/readout validated by k-step prediction; outer = GP-BO over pairs/gains/targets with a time-varying kernel for drift. That structure, not a single learned inverse, is where a learned component has a realistic chance to show a measurable gain in the next acute.
