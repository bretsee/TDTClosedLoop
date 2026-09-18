# Literature Review B: Biomimetic / Naturalistic Sensory Feedback via Microstimulation, Thalamic Sensory Prostheses, and the Physiology That Constrains Them

Compiled 2026-09-18 for the TDTClosedLoop VPL-to-S1 closed-loop MPC program (anesthetized rat; Microprobes 2x8 VPL array, 8 bipolar pairs, 100 Hz carrier, amplitude-modulated at 100 Hz control ticks, 200 us/phase biphasic, 5-40 uA; NeuroNexus 64-ch 8x8 planar S1 LFP array; comparison against Choi et al. 2016 open-loop QP and NN inverse controllers).

Conventions: entries marked with a star (★) are the must-reads (12 total). DOIs were verified against publisher/PubMed/PMC pages during compilation where noted "(verified)"; a few classic DOIs are given from standard indexing and marked "(indexed)". Each entry gives citation, DOI/URL, method+findings summary, and relevance to our project. Entries are numbered continuously across the six categories.

---

## Category 1. Francis-lab lineage and thalamic sensory prostheses

### ★ 1. Francis JT, Xu S, Chapin JK (2008). Proprioceptive and cutaneous representations in the rat ventral posterolateral thalamus. *J Neurophysiol* 99(5):2291-2304.
DOI: 10.1152/jn.01206.2007 (verified) - https://journals.physiology.org/doi/full/10.1152/jn.01206.2007
Summary: Extracellular mapping of rat VPL with microelectrodes under anesthesia, characterizing receptive fields by joint manipulation and cutaneous stimulation. The rostral VPL carries a large proprioceptive representation; caudal to it is a zone of focal cutaneous receptive fields with a fine topographic map of fore- and hindlimb. The paper gives the depth/AP extent of the forepaw cutaneous zone that later Francis-lab stimulation studies targeted.
Relevance: This is the anatomical basis for our Microprobes array placement. Site selectivity (digit vs pad) is only plausible if the 2x8 array actually spans the caudal cutaneous forepaw zone rather than the rostral proprioceptive zone; our "all pairs evoke the same footprint" result should be checked against the AP coordinate of the array relative to Francis 2008's cutaneous/proprioceptive border.

### ★ 2. Choi JS, Brockmeier AJ, McNiel DB, von Kraus LM, Principe JC, Francis JT (2016). Eliciting naturalistic cortical responses with a sensory prosthesis via optimized microstimulation. *J Neural Eng* 13(5):056007.
DOI: 10.1088/1741-2560/13/5/056007 (verified) - https://iopscience.iop.org/article/10.1088/1741-2560/13/5/056007
Summary (methods verified from full text): Nine urethane-anesthetized Long-Evans rats; VPL stimulation with either a 2x8 Pt-Ir microwire grid (75 um wires, 250 um pitch, 500 um row spacing) or a NeuroNexus A4x8 silicon array; bipolar pairs, 200 us/phase symmetric biphasic pulses, 7-40 uA, with Poisson (exponential-ISI) probing at mean 3-18 Hz for 6-18 min. S1 forelimb LFP (5-200 Hz, 610 Hz sampling) recorded with a 32-ch Utah array or 4-shank NeuroNexus array; LFP reduced to 12-15 PCs. A 50-state linear state-space model (subspace identification) with an input threshold/attenuation gate was fit (39% +/- 17% variance within 400 ms; r = 0.61), and a quadratic program with non-negativity and amplitude bounds, plus input-energy and smoothness penalties, solved by interior-point/iterative linearization (iLQR gave similar solutions), found stimulation envelopes that reproduce touch-evoked LFPs. Results: trial-averaged natural vs. "virtual touch" correlation 0.78 +/- 0.05 overall and 0.90 +/- 0.03 within 100 ms of onset; channel-wise spatial correlation 0.72; LDA decoding of touch condition (30-54 classes) 56% natural vs 61% virtual, and 90% for location alone; ~4 bits mutual information; Mahalanobis distance of optimized responses was 1.23x smaller than unmatched and 1.38x smaller than a rate-matched (PSTH-mimicking) control.
Relevance: This is our direct comparator. Note three design differences from our closed loop: (i) their probing used sparse Poisson pulses (3-18 Hz mean), not a 100 Hz tonic carrier, which is exactly the regime where we find rank ~5 rather than rank ~1; (ii) their model was fit on the sparse regime and then optimized open-loop; (iii) their fidelity metrics (temporal r, spatial r, Mahalanobis, LDA decoding, bits/s) are the metrics the PI expects us to report. Their per-trial control horizon (hold + 50 ms) and hand-tuned mu/lambda are the analogue of our MPC weights.

### 3. Choi JS, DiStasio MM, Brockmeier AJ, Francis JT (2012). An electric field model for prediction of somatosensory (S1) cortical field potentials induced by ventral posterior lateral (VPL) thalamic microstimulation. *IEEE Trans Neural Syst Rehabil Eng* 20(2):161-169.
DOI: 10.1109/TNSRE.2011.2181417 (verified) - https://pubmed.ncbi.nlm.nih.gov/22203725/
Summary: In quiet-awake rats, S1 LFP responses to VPL microstimulation delivered through many electrode configurations were used to fit an electric-field-based model that predicts the cortical response for novel (untested) electrode configurations. The model treats the S1 response as a function of the field produced in VPL by the electrode geometry, enabling design of spatially optimized multi-electrode patterns.
Relevance: Provides a principled prior for how bipolar-pair geometry (which of our 8 pairs, what current) maps to the S1 footprint; relevant to diagnosing our "no site selectivity" finding, because it predicts when neighbouring pairs' fields overlap enough to recruit the same VPL population.

### 4. Brockmeier AJ, Choi JS, DiStasio MM, Francis JT, Principe JC (2011). Optimizing microstimulation using a reinforcement learning framework. *Proc IEEE EMBC* 2011:1069-1072.
DOI: 10.1109/IEMBS.2011.6090249 (verified) - https://pubmed.ncbi.nlm.nih.gov/22254498/
Summary: Proposes selecting microstimulation parameters online so that the evoked cortical response approaches a natural-touch template, framed as a bandit/reinforcement-learning problem with the template distance as reward. Demonstrated on rat VPL-S1 data.
Relevance: An early online/closed-loop precedent from the same lab; our MPC is the model-based descendant. Their reward (template distance) is a usable per-trial fidelity score.

### 5. Brockmeier AJ, Choi JS, Emigh MS, Li L, Francis JT, Principe JC (2012). Subspace matching thalamic microstimulation to tactile evoked potentials in rat somatosensory cortex. *Proc IEEE EMBC* 2012:2957-2960.
DOI: 10.1109/EMBC.2012.6346584 (verified) - https://pubmed.ncbi.nlm.nih.gov/23366545/
Summary: Shows that S1 LFPs from natural digit touch and from matched VPL microstimulation can be quantitatively similar, and uses subspace projection (an "eigenface"-style PCA matching) to select which stimulation configuration best matches a natural response; per-realization matching beat random selection from the pruned set.
Relevance: Subspace (PCA) matching is a low-cost fidelity criterion that is robust to trial-to-trial noise; it also anticipates our rank analysis: if the evoked subspace is rank ~1 under tonic drive, subspace matching collapses to matching a single mode.

### 6. Li L, Brockmeier AJ, Choi JS, Francis JT, Sanchez JC, Principe JC (2014). A tensor-product-kernel framework for multiscale neural activity decoding and control. *Comput Intell Neurosci* 2014:870160.
DOI: 10.1155/2014/870160 (verified) - https://onlinelibrary.wiley.com/doi/10.1155/2014/870160
Summary: Proposes a kernel framework combining spike trains and LFPs (multiscale) for decoding and for adaptive inverse control of microstimulation, with an RKHS inverse controller mapping desired cortical patterns to stimulation.
Relevance: The kernel inverse controller is the nearest published relative of our NN inverse controllers, and its reported difficulties (ill-posed inversion, need for regularization) mirror our "NN-inverse honest negative".

### 7. Semework M, DiStasio M (2014). Short-term dynamics of causal information transfer in thalamocortical networks during natural inputs and microstimulation for somatosensory neuroprosthesis. *Front Neuroeng* 7:36.
DOI: 10.3389/fneng.2014.00036 (verified) - https://pmc.ncbi.nlm.nih.gov/articles/PMC4158812/
Summary: In three anesthetized Long-Evans rats with arrays in S1 and VPL, natural touch vs. microstimulation (25 uA, 200 us, 2 Hz) in VPL or S1 were compared with linear Granger causality on LFPs. Cortical microstimulation produced the largest disruption of causal flow, whereas VPL stimulation better preserved thalamocortical directionality; pre/post baselines did not differ, indicating short-term reversibility.
Relevance: Supports the thalamic (rather than cortical) target for naturalistic S1 patterns, and offers Granger/directed-connectivity as a fidelity metric that goes beyond amplitude matching.

### ★ 8. Francis JT, Rozenboym A, von Kraus L, Xu S, Chhatbar P, Semework M, Hawley E, Chapin J (2022). Similarities between somatosensory cortical responses induced via natural touch and microstimulation in the ventral posterior lateral thalamus in macaques. *Front Neurosci* 16:812837.
DOI: 10.3389/fnins.2022.812837 (verified) - https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2022.812837/full
Summary (verified from full text): Three anesthetized macaques (ketamine/isoflurane/fentanyl); 2x2 stainless array (1 mm spacing) in VPL, single biphasic bipolar pulses (200 us/phase) at 5 Hz, 25-100 uA; 32 tungsten electrodes in S1 hand area. Natural touch = ~1 ms taps at 5 Hz. PSTH z-scores and cross-correlation showed VPL single-pulse responses comparable in amplitude and spatial extent to touch, preserved somatotopy (specific VPL sites drove corresponding S1 hand regions), response amplitude scaling with current, and at >= 50 uA a 5+ cycle ~600 Hz oscillatory burst versus 2-3 cycles for touch.
Relevance: Important precedent that site selectivity in VPL is achievable with 1 mm electrode spacing and single pulses; our 250 um bipolar pairs under 100 Hz tonic drive may simply be too close and too continuous. The >= 50 uA high-frequency ringing is a candidate signature of over-drive that we can look for in our 64-ch LFP.

### ★ 9. Heming E, Sanden A, Kiss ZHT (2010). Designing a somatosensory neural prosthesis: percepts evoked by different patterns of thalamic stimulation. *J Neural Eng* 7(6):064001.
DOI: 10.1088/1741-2560/7/6/064001 (verified) - https://iopscience.iop.org/article/10.1088/1741-2560/7/6/064001
Summary: In DBS patients, sensory thalamus (Vc) was stimulated with pulse patterns derived from recorded thalamic spike trains (natural-touch-like patterns) as well as constant high-frequency (333 Hz) trains. Pattern changes altered the percept quality while preserving somatotopy, but most percepts remained "unnatural" and the biomimetic patterns did not beat 333 Hz constant stimulation in naturalness.
Relevance: The first explicit test of "biomimetic thalamic patterns"; shows that the stimulus temporal pattern is perceptually relevant at the thalamic level but that naive spike-train replay is insufficient. Justifies model-based (rather than replay-based) shaping of our envelopes.

### 10. Swan BD, Gasperson LB, Krucoff MO, Grill WM, Turner DA (2018). Sensory percepts induced by microwire array and DBS microstimulation in human sensory thalamus. *Brain Stimul* 11(2):416-422.
DOI: 10.1016/j.brs.2017.10.017 (verified) - https://pmc.ncbi.nlm.nih.gov/articles/PMC5803348/
Summary: Intraoperative microwire-array and DBS-lead stimulation of human Vc produced focal hand/finger percepts; microwire stimulation gave more focal percepts and temporal patterning of the pulse train altered naturalness.
Relevance: Corroborates thalamic somatotopic selectivity with small (microwire) contacts and supports the burst/patterned-vs-tonic question we are trying to settle for the rat.

### 11. Daly J, Liu J, Aghagolzadeh M, Oweiss K (2012). Optimal space-time precoding of artificial sensory feedback through multichannel microstimulation. *J Neural Eng* 9(6):065004.
DOI: 10.1088/1741-2560/9/6/065004 (verified via search; Oweiss lab, not Francis lab) - https://iopscience.iop.org/article/10.1088/1741-2560/9/6/065004
Summary: Proposes a space-time precoder that chooses multichannel thalamic microstimulation patterns to maximize mutual information between the limb-state variable to be conveyed and the evoked cortical response, treating the thalamocortical pathway as a MIMO channel.
Relevance: Formalizes the MIMO view we use in the blkdiag MIMO fitter, and provides an information-theoretic fidelity/capacity metric (bits conveyed) that complements waveform correlation; especially useful for quantifying loss of channel rank.

### 12. Jiang HJ, Chen KH, Jaw FS (2015). Deep-brain electrical microstimulation is an effective tool to explore functional characteristics of somatosensory neurons in the rat brain. *PLoS ONE* 10(2):e0117289.
DOI: 10.1371/journal.pone.0117289 (verified) - https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0117289
Summary: Pentobarbital-anesthetized Wistar rats; bipolar theta-glass microelectrode in VPL (hindpaw zone); cortical unit responses to VPL pulses had thalamocortical relay latencies and waveforms nearly identical to tactile-evoked ones.
Relevance: Independent confirmation that single VPL pulses reproduce the natural relay timing; useful as a latency benchmark (first cortical spikes/LFP deflection) for single-pulse vs tonic-train regimes.

### 13. Weber DJ, London BM, Hokanson JA, Ayers CA, Gaunt RA, Torres RR, Zaaimi B, Miller LE (2011). Limb-state information encoded by peripheral and central somatosensory neurons: implications for an afferent interface. *IEEE Trans Neural Syst Rehabil Eng* 19(5):501-513.
DOI: 10.1109/TNSRE.2011.2163145 (verified) - https://doi.org/10.1109/TNSRE.2011.2163145
Summary: Compared how DRG and S1 neurons encode limb state in cats/monkeys and drew design rules for an afferent interface, including evidence that DRG stimulation can drive naturalistic cortical activity.
Relevance: Frames the choice of stimulation level along the neuraxis; the thalamus sits between the two sites compared here and inherits the DRG advantage of pre-cortical processing.

### 14. Weber DJ, Friesen R, Miller LE (2012). Interfacing the somatosensory system to restore touch and proprioception: essential considerations. *J Mot Behav* 44(6):403-418.
DOI: 10.1080/00222895.2012.735283 (verified) - https://www.tandfonline.com/doi/full/10.1080/00222895.2012.735283
Summary: Review of neural-interface sites from peripheral nerve to S1, prior electrical-stimulation percept studies, and lessons from cochlear implants; emphasizes matching the code of the target level.
Relevance: Good general framing for the "why thalamus" section of any paper or deck.

### 15. Pezaris JS, Reid RC (2007). Demonstration of artificial visual percepts generated through thalamic microstimulation. *Proc Natl Acad Sci USA* 104(18):7670-7675.
DOI: 10.1073/pnas.0608563104 (verified via search) - https://www.pnas.org/doi/full/10.1073/pnas.0608563104
Summary: Monkeys made saccades to LGN microstimulation as if to a visual spot at the retinotopic location of the stimulated site, proving that thalamic microstimulation yields spatially specific percepts.
Relevance: The canonical demonstration that first-order thalamic nuclei support site-specific artificial percepts; our VPL program is the somatosensory analogue.

### ★ 16. Dadarlat MC, O'Doherty JE, Sabes PN (2015). A learning-based approach to artificial sensory feedback leads to optimal integration. *Nat Neurosci* 18(1):138-144.
DOI: 10.1038/nn.3883 (verified) - https://www.nature.com/articles/nn.3883
Summary: Monkeys learned to use an initially arbitrary multichannel S1 ICMS pattern (spatiotemporal code for hand-target vector) to reach accurately and integrated it with vision in a near-Bayes-optimal way.
Relevance: The counter-hypothesis to biomimicry: in a chronic/behaving preparation, the brain can learn arbitrary codes. For our anesthetized fidelity-focused prep this argues that "naturalistic" must be justified by physiology (Choi 2016, Bensmaia) rather than assumed; it also motivates reporting decodability, not only waveform similarity.

---

## Category 2. Biomimetic ICMS encoding of touch in S1 and peripheral analogues

### ★ 17. Tabot GA, Dammann JF, Berg JA, Tenore FV, Boback JL, Vogelstein RJ, Bensmaia SJ (2013). Restoring the sense of touch with a prosthetic hand through a brain interface. *Proc Natl Acad Sci USA* 110(45):18279-18284.
DOI: 10.1073/pnas.1221113110 (verified) - https://www.pnas.org/doi/10.1073/pnas.1221113110
Summary: In monkeys with Utah arrays in area 1, contact location was conveyed by electrode choice (somatotopy), pressure by ICMS amplitude (a psychometrically derived mapping), and contact timing by transient bursts at onset/offset; animals' discrimination of ICMS matched mechanical touch.
Relevance: The canonical "biomimetic ICMS" recipe: spatial = electrode, intensity = amplitude, onset/offset transients emphasized. Our MPC reference trajectory (touch-evoked LFP) implicitly contains these transients; the question is whether a 100 Hz carrier can express them.

### 18. Kim S, Callier T, Tabot GA, Gaunt RA, Tenore FV, Bensmaia SJ (2015). Behavioral assessment of sensitivity to intracortical microstimulation of primate somatosensory cortex. *Proc Natl Acad Sci USA* 112(49):15202-15207.
DOI: 10.1073/pnas.1509265112 (verified) - https://www.pnas.org/doi/10.1073/pnas.1509265112
Summary: Monkeys detected and discriminated ICMS trains; detection thresholds and JNDs scaled with amplitude, frequency, and duration; sensitivity to amplitude was well described by charge per pulse, and increasing frequency raised perceived intensity over a limited range.
Relevance: Gives the psychophysical amplitude/frequency trade-offs that define what "amplitude modulation on a fixed carrier" can and cannot convey.

### 19. Saal HP, Bensmaia SJ (2015). Biomimetic approaches to bionic touch through a peripheral nerve interface. *Neuropsychologia* 79:344-353.
DOI: 10.1016/j.neuropsychologia.2015.06.010 (verified) - https://www.sciencedirect.com/science/article/pii/S0028393215300592
Summary: Review arguing that stimulation should reproduce the natural afferent population code (rate and timing), grounded in models of mechanoreceptor responses; identifies onset/offset transients and adaptation as central.
Relevance: Foundational rationale for "biomimetic" as a design objective; the same logic transfers to matching thalamocortical drive.

### 20. Okorokova EV, He Q, Bensmaia SJ (2018). Biomimetic encoding model for restoring touch in bionic hands through a nerve interface. *J Neural Eng* 15(6):066033.
DOI: 10.1088/1741-2552/aae398 (verified) - https://iopscience.iop.org/article/10.1088/1741-2552/aae398
Summary: A compact encoder that converts prosthetic contact force/time series into stimulation amplitude/frequency by mimicking the aggregate afferent response (force plus its derivative, emphasizing transients).
Relevance: The simplest biomimetic encoder for our "open-loop biomimetic" arm: envelope = a*F + b*|dF/dt|; we can compare MPC output against this closed-form to see whether MPC is rediscovering derivative emphasis.

### ★ 21. Valle G, Mazzoni A, Iberite F, D'Anna E, Strauss I, Granata G, Controzzi M, Clemente F, Rognini G, Cipriani C, Stieglitz T, Petrini FM, Rossini PM, Micera S (2018). Biomimetic intraneural sensory feedback enhances sensation naturalness, tactile sensitivity, and manual dexterity in a bidirectional prosthesis. *Neuron* 100(1):37-45.e7.
DOI: 10.1016/j.neuron.2018.08.033 (verified) - https://www.cell.com/neuron/fulltext/S0896-6273(18)30738-4
Summary: In trans-radial amputees with TIME intraneural electrodes, biomimetic frequency-modulated encoding (derived from a mechanoreceptor model) was rated more natural, whereas linear amplitude modulation gave better fine force identification; a hybrid did best for dexterity.
Relevance: The cleanest biomimetic-vs-linear encoding comparison; note that naturalness and information transfer were dissociated, which is an argument for reporting both fidelity and decodability metrics.

### 22. George JA, Kluger DT, Davis TS, Wendelken SM, Okorokova EV, He Q, Duncan CC, Hutchinson DT, Thumser ZC, Beckler DT, Marasco PD, Bensmaia SJ, Clark GA (2019). Biomimetic sensory feedback through peripheral nerve stimulation improves dexterous use of a bionic hand. *Sci Robot* 4(32):eaax2352.
DOI: 10.1126/scirobotics.aax2352 (verified via URL) - https://www.science.org/doi/10.1126/scirobotics.aax2352
Summary: Utah Slanted Electrode Array stimulation in amputees; biomimetic (transient-emphasizing) encoding improved object discrimination and dexterity relative to linear encoding.
Relevance: Second independent confirmation that onset/offset transient emphasis is functionally superior; supports weighting early-response error more heavily in our MPC cost.

### 23. Flesher SN, Collinger JL, Foldes ST, Weiss JM, Downey JE, Tyler-Kabara EC, Bensmaia SJ, Schwartz AB, Boninger ML, Gaunt RA (2016). Intracortical microstimulation of human somatosensory cortex. *Sci Transl Med* 8(361):361ra141.
DOI: 10.1126/scitranslmed.aaf8083 (verified) - https://www.science.org/doi/10.1126/scitranslmed.aaf8083
Summary: First human S1 Utah-array ICMS; percepts were localized to the paralyzed hand, mostly pressure-like, graded with amplitude, and stable for months.
Relevance: Establishes amplitude as the primary intensity dimension in humans, consistent with our amplitude-modulation design choice.

### 24. Flesher SN, Downey JE, Weiss JM, Hughes CL, Herrera AJ, Tyler-Kabara EC, Boninger ML, Collinger JL, Gaunt RA (2021). A brain-computer interface that evokes tactile sensations improves robotic arm control. *Science* 372(6544):831-836.
DOI: 10.1126/science.abd0380 (verified) - https://www.science.org/doi/10.1126/science.abd0380
Summary: Bidirectional BCI; ICMS feedback of prosthetic-hand contact force halved task completion time (20.9 to 10.2 s median).
Relevance: Behavioral proof that even simple amplitude-coded ICMS feedback is useful; sets the functional bar for any thalamic alternative.

### 25. Armenta Salas M, Bashford L, Kellis S, Jafari M, Jo H, Kramer D, Shanfield K, Pejsa K, Lee B, Liu CY, Andersen RA (2018). Proprioceptive and cutaneous sensations in humans elicited by intracortical microstimulation. *eLife* 7:e32904.
DOI: 10.7554/eLife.32904 (verified) - https://elifesciences.org/articles/32904
Summary: Two S1 arrays in a tetraplegic participant elicited both cutaneous and proprioceptive percepts whose quality depended on amplitude and frequency.
Relevance: Frequency is a perceptual-quality dimension, which our fixed-100 Hz carrier removes; a duty-cycled/burst carrier would restore it.

### 26. Hughes CL, Flesher SN, Weiss JM, Boninger M, Collinger JL, Gaunt RA (2021). Perception of microstimulation frequency in human somatosensory cortex. *eLife* 10:e65128.
DOI: 10.7554/eLife.65128 (verified) - https://elifesciences.org/articles/65128
Summary: Varying amplitude, frequency, and duration in two participants showed that perceived intensity and quality depend on frequency in an electrode-specific way; frequency and amplitude are not interchangeable.
Relevance: Supports treating carrier frequency as a second control variable rather than fixing it; also warns that frequency effects are site-specific, so a per-pair calibration is needed.

### 27. Callier T, Brantly NW, Caravelli A, Bensmaia SJ (2020). The frequency of cortical microstimulation shapes artificial touch. *Proc Natl Acad Sci USA* 117(2):1191-1200.
DOI: 10.1073/pnas.1916453117 (verified) - https://www.pnas.org/doi/10.1073/pnas.1916453117
Summary: Monkeys discriminated ICMS frequency from 10 to ~200 Hz independent of amplitude; above ~200 Hz frequency changes were not discriminable; the sensory correlate of frequency was electrode-dependent.
Relevance: Places our 100 Hz carrier inside the range where frequency itself carries percept information, so amplitude-only modulation is leaving a channel unused.

### 28. Greenspon CM, Valle G, Hobbs TG, Verbaarschot C, Callier T, Shelchkova ND, ... Collinger JL, Hatsopoulos NG, Gaunt RA, Bensmaia SJ (2024). Evoking stable and precise tactile sensations via multi-electrode intracortical microstimulation of the somatosensory cortex. *Nat Biomed Eng* (published online Dec 2024). [Published version of the bioRxiv preprint "Tessellation of artificial touch via microstimulation of human somatosensory cortex", 2023.]
DOI: 10.1038/s41551-024-01299-z (verified via URL) - https://www.nature.com/articles/s41551-024-01299-z ; preprint https://www.biorxiv.org/content/10.1101/2023.06.23.545425v1
Summary: In three SCI participants, projected fields of individual electrodes were mapped and found stable over years; co-stimulating electrodes with overlapping projected fields yielded more localizable, more intense sensations (near-linear intensity summation), enabling a tessellation of the hand.
Relevance: Multi-electrode co-activation as a means to spatial selectivity and to graded intensity; the analogous experiment for us is co-stimulating VPL pairs and testing whether the S1 footprint moves (spatial rank) rather than merely scales.

### 29. Valle G, Alamri AH, Downey JE, Lienkamper R, Jordan PM, Sobinov AR, Endsley LJ, Prasad D, Boninger ML, Collinger JL, Warnke PC, Hatsopoulos NG, Miller LE, Gaunt RA, Greenspon CM, Bensmaia SJ (2025). Tactile edges and motion via patterned microstimulation of the human somatosensory cortex. *Science* 387(6731):315-322.
DOI: 10.1126/science.adq5978 (verified via URL) - https://www.science.org/doi/10.1126/science.adq5978
Summary: Spatiotemporally patterned ICMS across electrodes with known projected fields evoked percepts of edges and motion across the hand, exploiting the somatotopic tessellation.
Relevance: State of the art in "multi-electrode spatial patterns"; our 8-pair VPL array is the thalamic version of this and would need demonstrable per-pair footprint differences first.

### 30. O'Doherty JE, Lebedev MA, Ifft PJ, Zhuang KZ, Shokur S, Bleuler H, Nicolelis MAL (2011). Active tactile exploration using a brain-machine-brain interface. *Nature* 479(7372):228-231.
DOI: 10.1038/nature10489 (verified) - https://www.nature.com/articles/nature10489
Summary: Monkeys controlled a virtual arm from M1 ensembles while S1 ICMS with distinct temporal patterns signalled virtual texture; they learned to discriminate objects by artificial texture.
Relevance: The original closed-loop BMBI; temporal pattern (not just amplitude) carried the information.

### 31. Klaes C, Shi Y, Kellis S, Minxha J, Revechkis B, Andersen RA (2014). A cognitive neuroprosthetic that uses cortical stimulation for somatosensory feedback. *J Neural Eng* 11(5):056024.
DOI: 10.1088/1741-2560/11/5/056024 (verified) - https://iopscience.iop.org/article/10.1088/1741-2560/11/5/056024
Summary: Closed-loop BMI in a monkey in which S1 ICMS conveyed task-relevant "tactile" state; the animal used the feedback to complete trials.
Relevance: Another closed-loop precedent; useful mainly for the framing that closed-loop feedback need not be biomimetic to be useful.

### 32. Zaaimi B, Ruiz-Torres R, Solla SA, Miller LE (2013). Multi-electrode stimulation in somatosensory cortex increases probability of detection. *J Neural Eng* 10(5):056013.
DOI: 10.1088/1741-2560/10/5/056013 (verified) - https://iopscience.iop.org/article/10.1088/1741-2560/10/5/056013
Summary: In monkeys, detectability (d') of ICMS rose ~30% for electrode pairs and ~260% for seven simultaneously stimulated electrodes versus single electrodes at the same per-electrode current.
Relevance: Supports distributing charge across several VPL pairs at low amplitude rather than driving one pair hard, which may also help stay below the tonic-saturation regime that collapses rank.

### 33. Sombeck JT, Miller LE (2020). Short reaction times in response to multi-electrode intracortical microstimulation may provide a basis for rapid movement-related feedback. *J Neural Eng* 17(1):016013.
DOI: 10.1088/1741-2552/ab5cf3 (verified) - https://iopscience.iop.org/article/10.1088/1741-2552/ab5cf3
Summary: Reaction times to multi-electrode S1 ICMS in monkeys were shorter than to single-electrode ICMS and comparable to mechanical stimuli, especially at higher amplitudes and more electrodes.
Relevance: Latency is part of "naturalistic"; multi-site co-stimulation shortens it, which is another argument for exploring simultaneous multi-pair VPL drive.

### ★ 34. Kumaravelu K, Tomlinson T, Callier T, Sombeck J, Bensmaia SJ, Miller LE, Grill WM (2020). A comprehensive model-based framework for optimal design of biomimetic patterns of electrical stimulation for prosthetic sensation. *J Neural Eng* 17(4):046045.
DOI: 10.1088/1741-2552/abacd8 (verified) - https://iopscience.iop.org/article/10.1088/1741-2552/abacd8
Summary: Couples a biophysical model of ICMS-evoked S1 population activity to a model of natural touch-evoked activity and solves an optimization for the stimulation pattern (multi-electrode, time-varying amplitude/frequency) that minimizes the distance between the two population responses; identifies onset-emphasized, spatially distributed patterns as optimal.
Relevance: The closest modeling analogue to our MPC objective (minimize distance between evoked and natural population response); their objective and distance metric are directly reusable, and their conclusion that optimal patterns are transient-heavy predicts what a well-tuned MPC should output.

### 35. Bensmaia SJ, Miller LE (2014). Restoring sensorimotor function through intracortical interfaces: progress and looming challenges. *Nat Rev Neurosci* 15(5):313-325.
DOI: 10.1038/nrn3724 (verified) - https://www.nature.com/articles/nrn3724
Summary: Review positioning biomimicry and adaptation as the two design principles for afferent interfaces, and cataloguing the limits of ICMS (spread, longevity, percept quality).
Relevance: Standard citation for the biomimicry rationale and for the list of open problems our thalamic approach tries to address.

---

## Category 3. Physiology of microstimulation that limits selectivity, rank, and stability

### 36. Stoney SD, Thompson WD, Asanuma H (1968). Excitation of pyramidal tract cells by intracortical microstimulation: effective extent of stimulating current. *J Neurophysiol* 31(5):659-669.
DOI: 10.1152/jn.1968.31.5.659 (verified) - https://journals.physiology.org/doi/abs/10.1152/jn.1968.31.5.659
Summary: Derived the classic current-distance relation (r = sqrt(I/k), k ~ 1292 uA/mm^2 for PT cells) implying the activated volume grows with current; also showed axon collaterals are as excitable as somata up to ~1 mm away.
Relevance: The "volume grows with current" model that Histed and Kumaravelu 2022 revise; still the standard estimate for how far 5-40 uA reaches (~60-180 um radius for cell bodies), which bounds how distinct our 250 um-spaced pairs can be.

### 37. Ranck JB Jr (1975). Which elements are excited in electrical stimulation of mammalian central nervous system: a review. *Brain Res* 98(3):417-440.
DOI: 10.1016/0006-8993(75)90364-9 (indexed) - https://pubmed.ncbi.nlm.nih.gov/1102064/
Summary: Reviews current-distance data for myelinated fibers vs somata, chronaxies (50-100 us fibers; 200-700 us gray matter), anodal/cathodal differences, and the cathodal block at >8x threshold that confines activation to a shell.
Relevance: Explains why 200 us/phase pulses preferentially recruit axons of passage (lemniscal and corticothalamic fibers) in VPL, which is a plausible mechanism for the loss of site selectivity: fibers from many body regions run through the stimulated volume.

### 38. Tehovnik EJ, Tolias AS, Sultan F, Slocum WM, Logothetis NK (2006). Direct and indirect activation of cortical neurons by electrical microstimulation. *J Neurophysiol* 96(2):512-521.
DOI: 10.1152/jn.00126.2006 (verified) - https://journals.physiology.org/doi/full/10.1152/jn.00126.2006
Summary: Compares current-spread estimates from single-unit, behavioral, and fMRI methods; concludes microstimulation activates the most excitable elements (pyramidal-cell axons), with substantial indirect trans-synaptic spread.
Relevance: Sets expectations that most of the S1 footprint we see is trans-synaptic spread, not the direct VPL activation volume.

### ★ 39. Histed MH, Bonin V, Reid RC (2009). Direct activation of sparse, distributed populations of cortical neurons by electrical microstimulation. *Neuron* 63(4):508-522.
DOI: 10.1016/j.neuron.2009.07.016 (indexed) - https://www.cell.com/neuron/fulltext/S0896627309005455
Summary: Two-photon calcium imaging during ICMS showed that even low currents activate a sparse set of neurons scattered up to millimetres away, because axons passing near the tip are recruited; raising current increased the density but not the radius of activation; moving the electrode ~30 um changed the activated set.
Relevance: Directly explains the "no site selectivity" problem: neighbouring VPL pairs sample overlapping sparse-distributed fiber sets and cannot be expected to give a topographically distinct S1 footprint; selectivity in our prep must come from somatotopic ordering of fiber bundles, not from local somatic activation.

### ★ 40. Butovas S, Schwarz C (2003). Spatiotemporal effects of microstimulation in rat neocortex: a parametric study using multielectrode recordings. *J Neurophysiol* 90(5):3024-3039.
DOI: 10.1152/jn.00245.2003 (verified) - https://journals.physiology.org/doi/full/10.1152/jn.00245.2003
Summary: Near-threshold ICMS in ketamine-anesthetized rat S1 activated a ~1.35 mm zone; the response was a brief excitation followed by >100 ms of inhibition whose duration grew with current and with pulse count; repeated pulses within the inhibitory window were suppressed.
Relevance: The 100+ ms post-pulse inhibition is the single most likely mechanism for our tonic-saturation/rank-1 collapse: at 100 Hz every pulse lands inside the inhibition from the previous ones, so the cortex sees a saturated, low-dimensional envelope rather than the per-pulse structure.

### 41. Logothetis NK, Augath M, Murayama Y, Rauch A, Sultan F, Goense J, Oeltermann A, Merkle H (2010). The effects of electrical microstimulation on cortical signal propagation. *Nat Neurosci* 13(10):1283-1291.
DOI: 10.1038/nn.2631 (verified) - https://www.nature.com/articles/nn.2631
Summary: In monkeys, LGN microstimulation increased fMRI/LFP signals in V1 but suppressed retinotopically matched extrastriate cortex; microinjection experiments showed the stimulated area's output is silenced (feedforward inhibition), so signal propagation beyond the first cortical target is disrupted.
Relevance: Thalamic stimulation drives the first-order cortex but simultaneously silences its output; a naturalistic S1 LFP may therefore not imply naturalistic downstream (S2/M1) propagation, and our S1-only fidelity metric will overestimate biomimicry.

### 42. Overstreet CK, Klein JD, Helms Tillery SI (2013). Computational modeling of direct neuronal recruitment during intracortical microstimulation in somatosensory cortex. *J Neural Eng* 10(6):066016.
DOI: 10.1088/1741-2560/10/6/066016 (verified) - https://iopscience.iop.org/article/10.1088/1741-2560/10/6/066016
Summary: Multi-compartment models of 15 cortical cell types in a layered slab predicted that interneurons are recruited densely and continuously around the tip whereas pyramidal cells are recruited sparsely, with the recruited population depending on depth and current.
Relevance: Mechanistic reason why stronger current mainly adds inhibition (dense interneuron recruitment), supporting the observation that amplitude gain flattens (saturates) rather than expanding the footprint.

### 43. Kumaravelu K, Sombeck J, Miller LE, Bensmaia SJ, Grill WM (2022). Stoney vs. Histed: quantifying the spatial effects of intracortical microstimulation. *Brain Stimul* 15(1):141-151.
DOI: 10.1016/j.brs.2021.11.015 (verified) - https://www.brainstimjrnl.com/article/S1935-861X(21)00830-5/fulltext
Summary: A biophysical cortical-column model reconciled the two views: increasing current mostly raises activation density inside a roughly fixed volume (Histed), with only modest growth of the volume (Stoney); axonal activation dominates.
Relevance: Predicts that our amplitude sweeps (5-40 uA) should scale the S1 response amplitude (density) more than its spatial pattern (footprint), which is exactly a rank-1 gain model. Selectivity must therefore come from where the electrode is, not how hard it is driven.

### 44. Kumaravelu K, Grill WM (2024). Neural mechanisms of the temporal response of cortical neurons to intracortical microstimulation. *Brain Stimul* 17(2):365-381.
DOI: 10.1016/j.brs.2024.03.012 (verified) - https://pmc.ncbi.nlm.nih.gov/articles/PMC11090107/
Summary: A 6,410-neuron, five-layer biophysical model reproduced the single-pulse excitation-then-inhibition, and showed that during high-frequency trains the excitatory response declines progressively as AHP currents and GABAergic inhibition accumulate; both mechanisms scale with amplitude.
Relevance: Model-level confirmation that tonic high-frequency trains self-suppress; gives specific time constants (AHP, GABA-B-like) that could be built into our plant model as a slow adaptation state, and predicts that lower duty cycle restores per-pulse gain.

### 45. Sombeck JT, Heye J, Kumaravelu K, Goetz SM, Peterchev AV, Grill WM, Bensmaia S, Miller LE (2022). Characterizing the short-latency evoked response to intracortical microstimulation across a multi-electrode array. *J Neural Eng* 19(2):026044.
DOI: 10.1088/1741-2552/ac63e8 (verified) - https://iopscience.iop.org/article/10.1088/1741-2552/ac63e8
Summary: With artifact-suppressed recording in monkey S1/M1 arrays, single ICMS pulses evoked spikes within ~10 ms on electrodes across the array (up to millimetres), followed by ~100 ms suppression; response magnitude and suppression duration scaled with amplitude; during trains the excitatory response depressed.
Relevance: Provides an array-wide, artifact-robust protocol (stimulus-triggered response across all recording sites) for measuring our per-pair footprint at single-pulse resolution, and quantifies the train-induced depression we need to avoid.

### 46. Michelson NJ, Eles JR, Vazquez AL, Ludwig KA, Kozai TDY (2019). Calcium activation of cortical neurons by continuous electrical stimulation: frequency dependence, temporal fidelity, and activation density. *J Neurosci Res* 97(5):620-638.
DOI: 10.1002/jnr.24370 (verified) - https://onlinelibrary.wiley.com/doi/10.1002/jnr.24370
Summary: Two-photon GCaMP imaging in mouse cortex during 30 s continuous ICMS at 10-250 Hz: low frequencies gave sustained, temporally faithful activation, while higher frequencies (>= ~90-130 Hz) produced a strong onset response that decayed over seconds, with distinct onset/offset-responding populations and denser activation near the electrode.
Relevance: Direct imaging evidence that continuous ~100 Hz drive yields onset-dominated, decaying activation; supports our 30 min gain-drift observation and the burst/duty-cycle alternative.

### 47. Eles JR, Stieger KC, Kozai TDY (2021). The temporal pattern of intracortical microstimulation pulses elicits distinct temporal and spatial recruitment of cortical neuropil and neurons. *J Neural Eng* 18(1):015001.
DOI: 10.1088/1741-2552/abc29c (verified via URL) - https://iopscience.iop.org/article/10.1088/1741-2552/abc29c
Summary: With equal average rate (10 Hz) and charge, burst-patterned pulse trains recruited neurons and neuropil differently from uniformly spaced pulses (bursts increased neuronal calcium response and altered spatial extent), and a 100 Hz control produced strong initial then declining activation.
Relevance: Evidence that pulse timing within a fixed charge budget changes recruitment; for us it argues for testing burst-gated 100 Hz carriers (e.g., 20-50 ms bursts at a 5-20 Hz envelope) against continuous 100 Hz.

### 48. Stieger KC, Eles JR, Ludwig KA, Kozai TDY (2022). Intracortical microstimulation pulse waveform and frequency recruits distinct spatiotemporal patterns of cortical neuron and neuropil activation. *J Neural Eng* 19(2):026024.
DOI: 10.1088/1741-2552/ac5bf5 (verified via URL) - https://iopscience.iop.org/article/10.1088/1741-2552/ac5bf5
Summary: 30 s trains at 10 vs 100 Hz with symmetric/asymmetric waveforms: 100 Hz produced rapid onset activation that habituated within the train, whereas 10 Hz sustained activation; waveform asymmetry shifted the balance between neuropil (axonal) and somatic activation and the spatial spread.
Relevance: Adds waveform shape (cathodic-first asymmetric vs symmetric) as a lever for selectivity; our 200 us symmetric pulses are the axon-preferring choice and could be varied.

### ★ 49. Hughes CL, Flesher SN, Gaunt RA (2022). Effects of stimulus pulse rate on somatosensory adaptation in the human cortex. *Brain Stimul* 15(4):987-995.
DOI: 10.1016/j.brs.2022.05.021 (verified) - https://pmc.ncbi.nlm.nih.gov/articles/PMC10308851/
Summary: Continuous S1 ICMS at 20, 100, and 300 Hz in humans: percept intensity faded within seconds at 300 Hz and within tens of seconds at 100 Hz, while 20 Hz held for >= 15 s; intermittent trains separated by seconds never extinguished over 3 minutes whereas continuous and burst-continuous protocols extinguished within a minute.
Relevance: The most direct human evidence for our "burst/duty-cycled vs tonic" decision: 100 Hz continuous is in the fast-adapting regime, and the fix that worked was intermittency at the seconds scale (i.e., stimulate only when touch events occur), which is what a biomimetic transient-emphasizing MPC naturally does.

### ★ 50. Millard DC, Wang Q, Gollnick CA, Stanley GB (2013). System identification of the nonlinear dynamics in the thalamocortical circuit in response to patterned thalamic microstimulation in vivo. *J Neural Eng* 10(6):066011.
DOI: 10.1088/1741-2560/10/6/066011 (verified) - https://iopscience.iop.org/article/10.1088/1741-2560/10/6/066011
Summary: Single-electrode VPm microstimulation with Poisson-timed, amplitude-varying pulse trains in anesthetized rats while imaging S1 with voltage-sensitive dye; a two-stage phenomenological model (linear recruitment at the electrode, then a static nonlinearity capturing paired-pulse depression/facilitation and a second nonlinear propagation stage) explained 58% of variance on held-out patterns and reproduced single-trial behaviour when noise was added.
Relevance: The most relevant plant-identification study for us: thalamic pulse trains -> S1 mesoscale response is well described as linear-in-current but strongly nonlinear-in-time (inter-pulse interval). It argues that our linear MPC plant should be fit on a sparse-pulse regime and augmented with a static/dynamic nonlinearity for inter-pulse depression, rather than fit on the saturated 100 Hz regime.

### 51. Millard DC, Whitmire CJ, Gollnick CA, Rozell CJ, Stanley GB (2015). Electrical and optical activation of mesoscale neural circuits with implications for coding. *J Neurosci* 35(47):15702-15715.
DOI: 10.1523/JNEUROSCI.5045-14.2015 (verified) - https://www.jneurosci.org/content/35/47/15702
Summary: VSD imaging of rat S1 in response to whisker deflection, VPm electrical microstimulation, and VPm optogenetic stimulation; electrical stimulation produced a larger, less spatially specific and more synchronous cortical activation than natural input, and pulse-train responses adapted with a frequency dependence that differed from sensory adaptation.
Relevance: Quantifies, at the mesoscale we record, how thalamic electrical stimulation over-synchronizes and over-spreads relative to touch, which is consistent with a rank-deficient, spatially uniform S1 footprint.

### 52. Wang Q, Webber RM, Stanley GB (2010). Thalamic synchrony and the adaptive gating of information flow to cortex. *Nat Neurosci* 13(12):1534-1541.
DOI: 10.1038/nn.2670 (verified) - https://www.nature.com/articles/nn.2670
Summary: Paired thalamic and cortical recordings during adapting whisker stimulation showed that cortical detectability falls and discriminability rises with adaptation, driven by a decrease in thalamic population synchrony rather than thalamic rate.
Relevance: Microstimulation maximizes thalamic synchrony (all recruited cells fire together), which the cortex reads as a "novel/unadapted" event and answers with a large uniform response; this is a mechanistic route to the non-selective footprint and suggests asynchronous/staggered pulses across pairs as a mitigation.

### 53. Whitmire CJ, Waiblinger C, Schwarz C, Stanley GB (2016). Information coding through adaptive gating of synchronized thalamic bursting. *Cell Rep* 14(4):795-807.
DOI: 10.1016/j.celrep.2015.12.068 (verified) - https://www.sciencedirect.com/science/article/pii/S2211124715015223
Summary: Thalamic burst vs tonic firing and the synchrony of bursting across VPm neurons are set by adaptation state along a continuum that trades detection for discrimination; optogenetic manipulation confirmed the causal role of synchrony.
Relevance: Physiological support for "burst-mode" thalamic drive being the natural way to produce large, detectable cortical responses, and for tonic drive being the discrimination-favouring but low-gain regime.

### ★ 54. Chung S, Li X, Nelson SB (2002). Short-term depression at thalamocortical synapses contributes to rapid adaptation of cortical sensory responses in vivo. *Neuron* 34(3):437-446.
DOI: 10.1016/S0896-6273(02)00659-1 (indexed) - https://www.cell.com/neuron/fulltext/S0896-6273(02)00659-1
Summary: In vivo whole-cell recordings in rat barrel cortex: repeated whisker stimulation depressed thalamocortical synaptic input without changing intrinsic properties; the depression recovered with the same time course as sensory responsiveness (hundreds of ms to seconds), and thalamic adaptation was weaker and faster-recovering than cortical.
Relevance: The synaptic mechanism for tonic-drive collapse: under sustained 100 Hz thalamic firing the thalamocortical synapse sits in a depressed steady state, so the cortex reports only slow envelope changes (rank 1) and per-pulse structure is lost; recovery time constants here set the minimum inter-burst gap for a duty-cycled design.

### 55. Castro-Alamancos MA (2004). Absence of rapid sensory adaptation in neocortex during information processing states. *Neuron* 41(3):455-464.
DOI: 10.1016/S0896-6273(03)00853-5 (indexed) - https://www.cell.com/neuron/fulltext/S0896-6273(03)00853-5
Summary: Rapid sensory adaptation (thalamocortical depression) is prominent in quiescent states (anesthesia, slow-wave sleep, quiet waking) and largely absent in aroused/attentive states because tonic thalamic firing already keeps the synapse in the adapted state.
Relevance: Our anesthetized prep is in the state where thalamocortical depression is maximal, so tonic stimulation in the acute prep will look worse than it would in an awake animal; also implies the "baseline" for a biomimetic target should be the adapted, not the naive, thalamocortical gain.

### 56. Boudreau CE, Ferster D (2005). Short-term depression in thalamocortical synapses of cat primary visual cortex. *J Neurosci* 25(31):7179-7190.
DOI: 10.1523/JNEUROSCI.1592-05.2005 (indexed) - https://www.jneurosci.org/content/25/31/7179
Summary: 20-100 Hz LGN electrical trains produced moderate depression of monosynaptic thalamocortical PSPs but marked depression of disynaptic (cortico-cortical) input, so the net cortical response to a train falls mostly through intracortical depression.
Relevance: Suggests that a large part of the loss of evoked LFP under 100 Hz trains is intracortical rather than at the thalamocortical synapse, which matters for where to put the adaptation state in our plant model.

### 57. Swadlow HA, Gusev AG (2001). The impact of "bursting" thalamic impulses at a neocortical synapse. *Nat Neurosci* 4(4):402-408.
DOI: 10.1038/86054 (indexed) - https://www.nature.com/articles/nn0401_402
Summary: In awake rabbits, thalamic bursts (after a preceding silent interval) had greatly enhanced synaptic efficacy at the thalamocortical synapse; the first impulse of a burst was most effective and the silent interval preceding it was essential.
Relevance: Physiological argument that a duty-cycled carrier (silence then burst) delivers more cortical impact per pulse than continuous drive; the required silent interval (~100 ms+) sets a burst-envelope frequency well below our 100 Hz tick rate.

### 58. Sherman SM (2001). Tonic and burst firing: dual modes of thalamocortical relay. *Trends Neurosci* 24(2):122-126.
DOI: 10.1016/S0166-2236(00)01714-8 (verified) - https://pubmed.ncbi.nlm.nih.gov/11164943/
Summary: Reviews the T-type calcium-channel-dependent burst vs tonic modes of thalamic relay cells: tonic mode relays linearly with poorer detectability, burst mode is nonlinear but highly detectable; mode is set by membrane potential/modulatory input.
Relevance: Frames our burst-vs-tonic stimulation question in the relay cell's own terms: a tonic 100 Hz carrier forces tonic-mode-like relay (linear, low gain), whereas gated bursts emulate the high-gain "wake-up call" mode.

### 59. (2025) Neural mechanisms underlying intracortical microstimulation for sensory restoration. *Nat Biomed Eng* (2025). [Authorship not verified during compilation; article page was cookie-walled.]
URL: https://www.nature.com/articles/s41551-025-01583-6
Summary: Recent mechanistic synthesis of ICMS-evoked population activity for sensory restoration, covering amplitude/frequency dependence and adaptation; listed here for completeness and should be checked before citing.
Relevance: Likely the most current review of the physiological constraints in Category 3; verify authors and content before use.

---

## Category 4. Anesthesia and cortical state effects on S1 evoked LFP

### 60. Erchova IA, Lebedev MA, Diamond ME (2002). Somatosensory cortical neuronal population activity across states of anaesthesia. *Eur J Neurosci* 15(4):744-752.
DOI: 10.1046/j.0953-816x.2002.01898.x (verified) - https://onlinelibrary.wiley.com/doi/10.1046/j.0953-816x.2002.01898.x
Summary: Multi-electrode recordings in rat barrel cortex at light, intermediate, and deep urethane: deepening anesthesia increased slow synchronized (up/down) population fluctuations and made stimulus-evoked responses larger but more variable and more dependent on the ongoing state phase.
Relevance: Our touch-evoked target and our stim-evoked response both ride on up/down states; trial-to-trial variance under urethane/ketamine is partly state phase, so fidelity metrics should be computed on trial averages and/or with state (LFP phase or delta power) as a covariate; state drift is a plausible contributor to the ~30 min gain drift.

### 61. Friedberg MH, Lee SM, Ebner FF (1999). Modulation of receptive field properties of thalamic somatosensory neurons by the depth of anesthesia. *J Neurophysiol* 81(5):2243-2252.
DOI: 10.1152/jn.1999.81.5.2243 (verified) - https://journals.physiology.org/doi/full/10.1152/jn.1999.81.5.2243
Summary: ECoG dominant frequency was used to stage halothane/urethane depth while recording VPM units; deeper anesthesia lengthened latency, reduced response probability/magnitude, and shrank receptive fields, with clear stage-dependent ECoG signatures (1-2 Hz at III-4 up to 6 and 10-13 Hz at III-1).
Relevance: Provides an objective anesthesia-depth index (ECoG/LFP dominant frequency) that we can log from the S1 array to stratify sessions and to explain gain drift; also shows thalamic responsiveness itself changes with depth, which affects how much current a VPL pair needs.

### 62. Constantinople CM, Bruno RM (2011). Effects and mechanisms of wakefulness on local cortical networks. *Neuron* 69(6):1061-1068.
DOI: 10.1016/j.neuron.2011.02.040 (indexed) - https://www.cell.com/neuron/fulltext/S0896-6273(11)00162-0
Summary: Intracellular recordings from the same barrel-cortex neurons under anesthesia and after waking: wakefulness abolished the synaptic quiescence (down states) seen under anesthesia and produced a persistently depolarized state, driven by thalamic input (silencing thalamus restored down-state-like activity).
Relevance: The anesthetized cortex alternates between a highly responsive down-state and a saturated up-state; explains large trial-to-trial variance and suggests a state-gated stimulation policy (or state-covariate model) for the acute prep.

### 63. Hasenstaub A, Sachdev RNS, McCormick DA (2007). State changes rapidly modulate cortical neuronal responsiveness. *J Neurosci* 27(36):9607-9622.
DOI: 10.1523/JNEUROSCI.2184-07.2007 (indexed) - https://www.jneurosci.org/content/27/36/9607
Summary: In rodent S1, increases in local network activity (up states) increased responsiveness to injected conductance but decreased responsiveness to whisker deflection, with rapid (tens of ms) switching.
Relevance: Predicts that identical VPL stimulation gives smaller S1 LFP responses in up states than in down states; this is a source of apparent "gain drift" and of nonlinearity that a linear MPC plant cannot capture without a state term.

### 64. Devonshire IM, Grandy TH, Dommett EJ, Greenfield SA (2010). Effects of urethane anaesthesia on sensory processing in the rat barrel cortex revealed by combined optical imaging and electrophysiology. *Eur J Neurosci* 32(5):786-797.
DOI: 10.1111/j.1460-9568.2010.07322.x (verified via URL) - https://onlinelibrary.wiley.com/doi/10.1111/j.1460-9568.2010.07322.x
Summary: Combined VSD imaging and electrophysiology in urethane-anesthetized rats showed dose-dependent effects of urethane on the amplitude, spatial spread, and timing of sensory-evoked cortical responses.
Relevance: Urethane (the Choi 2016 agent) alters the very spatial spread we score; if our prep uses ketamine/xylazine or isoflurane, the touch-evoked "target" footprint is not directly comparable to Choi's.

### 65. Kortelainen J, Al-Nashash H, Vipin A, Thow XY, All A (2016). The effect of anaesthesia on somatosensory evoked potential measurement in a rat model. *Lab Anim* 50(1):63-66.
DOI: 10.1177/0023677215589514 (verified via URL) - https://doi.org/10.1177/0023677215589514
Summary: Compared SEPs recorded under different anesthetics/levels in rats; SEP amplitude and latency depended strongly on agent and depth, with ketamine tending to enhance and inhalational agents to suppress cortical SEP amplitude.
Relevance: Practical reference for choosing/maintaining anesthesia so that the S1 LFP target is stable across a 30+ min closed-loop session; supports logging anesthetic depth as a session covariate.

### 66. Hayton SM, Kriss A, Muller DPR (1999). Comparison of the effects of four anaesthetic agents on somatosensory evoked potentials in the rat. *Lab Anim* 33(3):243-251.
DOI: 10.1258/002367799780578219 (verified via URL) - https://doi.org/10.1258/002367799780578219
Summary: Forepaw and hindpaw SEPs were compared under ketamine-xylazine, medetomidine, isoflurane, and fentanyl/fluanisone-midazolam; latencies and amplitudes differed systematically by agent, with isoflurane producing the most amplitude suppression.
Relevance: Baseline expectations for forepaw SEP amplitude/latency under ketamine-xylazine vs isoflurane, which matter for our amplitude-normalized fidelity metrics.

---

## Category 5. VPL somatotopy and electrode geometry for the forepaw representation

(See also entries 1, 2, 3, 8 for the Francis-lab arrays: 2x8 microwire 250 um pitch and NeuroNexus A4x8 in rat; 2x2 at 1 mm in macaque.)

### 67. Emmers R (1965). Organization of the first and the second somesthetic regions (SI and SII) in the rat thalamus. *J Comp Neurol* 124(2):215-227.
DOI: 10.1002/cne.901240207 (verified) - https://onlinelibrary.wiley.com/doi/10.1002/cne.901240207
Summary: Systematic monopolar-electrode mapping of thalamic regions receiving somesthetic input, defining the ventrobasal (VPL/VPM) somatotopy with the body represented mediolaterally (face medial, limbs lateral) and a separate SII-projecting region.
Relevance: Foundational map for planning the mediolateral placement of the 2x8 array so that its long axis spans the forepaw digits/pads rather than crossing into hindlimb or face.

### 68. Angel A, Clarke KA (1975). An analysis of the representation of the forelimb in the ventrobasal thalamic complex of the albino rat. *J Physiol* 249(2):399-423.
DOI: 10.1113/jphysiol.1975.sp011022 (verified) - https://physoc.onlinelibrary.wiley.com/doi/10.1113/jphysiol.1975.sp011022
Summary: 998 VB units in deeply anesthetized rats (889 forelimb-driven); characterizes the fine somatotopy of the forelimb within VPL, receptive-field sizes, and response latencies to electrical forelimb stimulation, including the spatial extent (in hundreds of microns) of the digit and pad representations.
Relevance: Gives the physical size of the forepaw sub-representations in VPL; if individual digit zones are ~200-300 um across, bipolar pairs at 250 um pitch with 5-40 uA (activation radius ~100-200 um plus axonal recruitment) will straddle several zones, explaining absent selectivity and motivating finer or more medially/laterally staggered contacts.

### 69. Waite PME (1973). Somatotopic organization of vibrissal responses in the ventro-basal complex of the rat thalamus. *J Physiol* 228(2):527-540.
DOI: 10.1113/jphysiol.1973.sp010098 (verified) - https://physoc.onlinelibrary.wiley.com/doi/10.1113/jphysiol.1973.sp010098
Summary: Whisker representation occupies the dorsomedial one-third to one-half of VB across its rostrocaudal extent, with whisker rows at different rostrocaudal levels and single-whisker receptive fields.
Relevance: Defines the medial boundary (VPM) that the lateral (VPL forepaw) array must not cross, and illustrates that thalamic somatotopy is organized in rostrocaudal lamellae, which favours arrays with rostrocaudal extent (our 2x8 long axis) for covering multiple digits.

---

## Category 6. Evaluation metrics for biomimetic fidelity, closed-loop control precedents, and rodent behavioral validation

### 70. Bolus MF, Willats AA, Rozell CJ, Stanley GB (2021). State-space optimal feedback control of optogenetically driven neural activity. *J Neural Eng* 18(3):036006.
DOI: 10.1088/1741-2552/abb89c (verified) - https://iopscience.iop.org/article/10.1088/1741-2552/abb89c
Summary: Real-time closed-loop control of thalamic (VPm) spiking in awake mice using optogenetic drive, a linear state-space (LDS) plant identified from data, Kalman state estimation, and LQR/optimal feedback control; achieved continuously graded tracking of reference firing rates and rejection of disturbances, outperforming PI control.
Relevance: The closest published analogue of our real-time LDS + MPC loop in the thalamocortical circuit (albeit optogenetic and controlling thalamus rather than cortex); their tracking-error, disturbance-rejection, and reference-following metrics are a template for reporting our MPC vs Choi open-loop comparison.

### 71. Kriegeskorte N, Mur M, Bandettini P (2008). Representational similarity analysis - connecting the branches of systems neuroscience. *Front Syst Neurosci* 2:4.
DOI: 10.3389/neuro.06.004.2008 (indexed) - https://www.frontiersin.org/articles/10.3389/neuro.06.004.2008/full
Summary: Introduces representational dissimilarity matrices (RDMs) and second-order correlation of RDMs as a modality-independent way to compare representational geometry across measurements or models.
Relevance: A natural fidelity metric for us that is invariant to the rank-1 gain: build the RDM across touch conditions (D1-D4, P1-P3) from natural responses and from stimulation-evoked responses and correlate them; a rank-1 stimulation map will produce a degenerate RDM even if per-condition waveform correlation is high.

### 72. Butovas S, Schwarz C (2007). Detection psychophysics of intracortical microstimulation in rat primary somatosensory cortex. *Eur J Neurosci* 25(7):2161-2169.
DOI: 10.1111/j.1460-9568.2007.05449.x (verified) - https://onlinelibrary.wiley.com/doi/10.1111/j.1460-9568.2007.05449.x
Summary: Head-fixed rats reported detection of infragranular barrel-cortex ICMS; psychometric curves were measured vs intensity, pulse number, and frequency; single-pulse threshold ~2.0 nC, close to the threshold for short-latency spiking near the electrode; more pulses and higher frequency lowered threshold with diminishing returns.
Relevance: The rat detection paradigm and charge-threshold numbers to adopt for behavioral validation of VPL stimulation in a later chronic phase; also gives the charge scale at which physiological (spiking) and perceptual thresholds coincide.

### 73. Semprini M, Bennicelli L, Vato A (2012). A parametric study of intracortical microstimulation in behaving rats for the development of artificial sensory channels. *Proc IEEE EMBC* 2012:799-802.
DOI: 10.1109/EMBC.2012.6346052 (verified) - https://pubmed.ncbi.nlm.nih.gov/23366013/
Summary: Freely moving rats performed a detection task while pulse amplitude, frequency, and train duration were varied; perceptual thresholds were higher than in head-restrained rats and depended jointly on all three parameters.
Relevance: Behavioral parameter-space reference for freely moving rats; supports designing amplitude-frequency-duration trade-off tables before a chronic VPL behavioral study.

### 74. Venkatraman S, Carmena JM (2011). Active sensing of target location encoded by cortical microstimulation. *IEEE Trans Neural Syst Rehabil Eng* 19(3):317-324.
DOI: 10.1109/TNSRE.2011.2117441 (verified) - https://doi.org/10.1109/TNSRE.2011.2117441
Summary: Real-time whisker tracking triggered barrel-cortex ICMS when the whisker crossed a virtual target; rats integrated the artificial cue with whisker position within 200 ms to localize the target.
Relevance: A rodent closed-loop, event-triggered stimulation paradigm (stimulate at a sensorimotor event) that is the behavioral counterpart of our touch-triggered biomimetic envelopes.

### 75. Devecioglu I, Guclu B (2017). Psychophysical correspondence between vibrotactile intensity and intracortical microstimulation for tactile neuroprostheses in rats. *J Neural Eng* 14(1):016010.
DOI: 10.1088/1741-2552/14/1/016010 (verified) - https://iopscience.iop.org/article/10.1088/1741-2552/14/1/016010
Summary: Awake rats performed detection of glabrous-skin vibrotactile stimuli and of S1 ICMS at 40, 60, and 80 Hz; psychometric equivalence functions mapped vibrotactile amplitude to ICMS current at matched detection probability, giving frequency-dependent intensity mappings.
Relevance: The rat analogue of Tabot's pressure-to-amplitude mapping; a template for establishing a forepaw-touch-to-VPL-current equivalence function behaviorally, which would validate our LFP-based fidelity with a perceptual criterion.

---

## Must-reads (12)

1. Francis, Xu, Chapin 2008 - VPL somatotopy (10.1152/jn.01206.2007)
2. Choi et al. 2016 - the comparator method and metrics (10.1088/1741-2560/13/5/056007)
3. Francis et al. 2022 - macaque VPL single-pulse somatotopic S1 responses (10.3389/fnins.2022.812837)
4. Heming, Sanden, Kiss 2010 - biomimetic thalamic patterns in humans (10.1088/1741-2560/7/6/064001)
5. Dadarlat, O'Doherty, Sabes 2015 - the learning-based counter-hypothesis (10.1038/nn.3883)
6. Tabot et al. 2013 - the canonical biomimetic ICMS recipe (10.1073/pnas.1221113110)
7. Valle et al. 2018 - biomimetic vs linear encoding dissociation (10.1016/j.neuron.2018.08.033)
8. Kumaravelu et al. 2020 - model-based optimal biomimetic pattern design (10.1088/1741-2552/abacd8)
9. Histed, Bonin, Reid 2009 - sparse distributed axonal activation (10.1016/j.neuron.2009.07.016)
10. Butovas & Schwarz 2003 - excitation then >100 ms inhibition (10.1152/jn.00245.2003)
11. Millard et al. 2013 - thalamic-microstim-to-S1 system identification with pulse-interval nonlinearity (10.1088/1741-2560/10/6/066011)
12. Chung, Li, Nelson 2002 - thalamocortical short-term depression in vivo (10.1016/S0896-6273(02)00659-1); read with Hughes, Flesher, Gaunt 2022 (10.1016/j.brs.2022.05.021) for the human intermittent-stimulation result.

---

## Themes and methods we should adopt

1. **Tonic ~100 Hz drive is the wrong operating point for the thalamocortical synapse.** Chung 2002, Boudreau & Ferster 2005, Castro-Alamancos 2004, Butovas 2003, Kumaravelu 2024, Michelson 2019, Stieger 2022 and Hughes 2022 all converge: continuous 100-300 Hz trains produce an onset transient followed by depression/adaptation within ~1-10 s and a >100 ms post-pulse inhibitory window per pulse. Our rank-1 collapse under tonic drive (single-pulse rank ~5) is the expected signature of a synapse and cortex held in a depressed steady state; it is not an artifact of our model.

2. **Adopt intermittent / burst-gated stimulation with silent gaps.** Swadlow & Gusev 2001 (silent interval before a burst multiplies synaptic efficacy), Whitmire 2016 and Sherman 2001 (burst mode = high detectability), Eles 2021 (bursts at fixed charge recruit more) and Hughes 2022 (intermittent trains never extinguished over 3 min; continuous did within 1 min) argue for: 100 Hz within-burst carrier, bursts of ~20-50 ms, burst rate set by the touch envelope (roughly 5-20 Hz), and enforced gaps >= 100 ms whenever touch is absent. This is the "burst-probing lever" for acute #3.

3. **Fit the plant in the sparse-pulse regime, then add an inter-pulse nonlinearity.** Choi 2016 identified its LDS from Poisson probing at 3-18 Hz, and Millard 2013 showed recruitment is linear in current but strongly nonlinear in inter-pulse interval (paired-pulse depression/facilitation) with a second nonlinear propagation stage. Our MPC plant should be identified with Poisson-timed, amplitude-randomized bursts (not tonic 100 Hz), and augmented with a slow adaptation state (time constants from Chung 2002 / Kumaravelu 2024) so the controller "knows" that the next pulse's gain depends on recent history.

4. **Emphasize onset/offset transients in the reference and the cost.** Tabot 2013, Saal & Bensmaia 2015, Okorokova 2018, Valle 2018, George 2019 and Kumaravelu 2020 all find that transient-emphasizing (force + |dF/dt|) encoders are more natural and more useful. Choi 2016's own similarity was 0.90 in the first 100 ms vs 0.78 overall. Weight the first ~100 ms of the touch response more heavily in the MPC cost and compare MPC output to the closed-form Okorokova encoder as an "is MPC rediscovering derivative emphasis?" check.

5. **Selectivity is a placement problem, not an amplitude problem.** Histed 2009 and Kumaravelu 2022 show current mainly changes activation density inside a roughly fixed, axon-dominated volume; Ranck 1975 shows 200 us pulses preferentially recruit fibers of passage. Francis 2022 obtained somatotopic S1 responses in macaque with single pulses at 1 mm spacing; Angel & Clarke 1975 give digit/pad zones of a few hundred microns in rat VPL. Our 250 um bipolar pairs at 5-40 uA almost certainly straddle several zones. Test selectivity with single pulses (not trains), map each pair's footprint with the Sombeck 2022 stimulus-triggered array protocol, and consider an array with wider rostrocaudal span across the caudal cutaneous VPL (Francis 2008) or smaller/asymmetric-waveform contacts (Stieger 2022).

6. **Use multi-pair co-stimulation at low current rather than single-pair high current.** Zaaimi 2013 (d' +260% with seven electrodes), Sombeck & Miller 2020 (shorter reaction times), Greenspon 2024 (overlapping projected fields sum near-linearly and localize better) and Valle 2025 (patterned multi-electrode edges/motion) show spatial patterns across electrodes are the route to graded, localizable, and moving percepts. For us the MIMO fitter should be tested for whether co-activation shifts the S1 footprint (adds rank) or only scales it.

7. **Thalamic stimulation over-synchronizes; consider asynchronous pulses across pairs.** Wang 2010 and Millard 2015 show thalamic synchrony (not rate) sets cortical gain and that electrical stimulation over-synchronizes and over-spreads relative to natural input. Staggering pulse timing across the 8 pairs (rather than simultaneous 100 Hz ticks) is a cheap experiment that could restore spatial structure.

8. **S1-only fidelity overestimates biomimicry.** Logothetis 2010 shows thalamic stimulation silences the output of the first cortical target; Semework & DiStasio 2014 used Granger causality to show VPL stimulation preserves thalamocortical directionality better than cortical stimulation. Add a directed-connectivity or downstream (S2/M1) check when possible.

9. **Report the Choi 2016 metric set plus decodability and representational geometry.** Standard set: (a) trial-averaged temporal Pearson r (overall and 0-100 ms), (b) channel-wise spatial r of peak negativity, (c) rms-energy match, (d) Mahalanobis distance of stimulated response to the natural distribution vs. an unmatched control, (e) LDA/nearest-mean decoding of touch site and pressure with cross-modal generalization, (f) mutual information (bits and bits/s). Add (g) RDM correlation (Kriegeskorte 2008) across the D1-D4/P1-P3 conditions, which is invariant to a rank-1 gain and directly exposes lost selectivity, and (h) Daly/Oweiss 2012 channel capacity as a formal rank/selectivity metric. Bolus 2021 supplies the control-theoretic metrics (tracking error, disturbance rejection, reference following) for MPC vs open-loop.

10. **Anesthesia state is a covariate, not noise.** Erchova 2002, Constantinople & Bruno 2011, Hasenstaub 2007 and Friedberg 1999 show up/down states and anesthetic depth change evoked amplitude by large factors and at seconds-to-minutes scales, which is the timescale of our 30 min gain drift. Log the S1 LFP dominant frequency/delta power per trial (Friedberg's staging), stratify fidelity by state, and consider triggering or gating stimulation on cortical state. Note also that Choi 2016 used urethane, whose evoked spatial spread differs from ketamine-xylazine and isoflurane (Devonshire 2010; Hayton 1999; Kortelainen 2016).

11. **Amplitude is not the only intensity lever; frequency carries percept information and adaptation risk.** Kim 2015, Callier 2020, Hughes 2021, Armenta Salas 2018: perceived intensity/quality depends on frequency up to ~200 Hz in an electrode-specific way. A carrier that varies within-burst frequency (e.g., 50-200 Hz) alongside amplitude increases the expressible code and lets the controller trade adaptation for intensity.

12. **Biomimetic replay is not enough; model-based shaping is needed.** Heming 2010 (thalamic spike-train replay did not beat 333 Hz) and Choi 2016 (rate-matched PSTH replay was 1.38x worse than optimized patterns) both show that copying natural spike timing into current pulses fails; the closed-loop, model-based approach is justified.

13. **Biomimicry vs learning.** Dadarlat 2015, O'Doherty 2011, Klaes 2014 show behaving animals can learn arbitrary codes; the case for naturalistic stimulation must rest on faster learning, more natural percepts (Valle 2018) and better downstream propagation, which we can only argue from physiology in the acute prep. State this explicitly in decks.

14. **Behavioral validation path for rats exists.** Butovas & Schwarz 2007 (head-fixed detection, ~2 nC threshold), Semprini 2012 (freely moving parametric thresholds), Venkatraman & Carmena 2011 (event-triggered closed-loop cue), Devecioglu & Guclu 2017 (touch-to-ICMS psychometric equivalence) provide the templates for a chronic VPL follow-up that ties LFP fidelity to perception.

15. **Artifact handling.** Sombeck 2022 demonstrates array-wide short-latency response characterization with artifact suppression at single-pulse resolution; adopting a single-pulse, stimulus-triggered footprint map per pair (with the Choi 2016 input gate for sub-threshold currents) separates true selectivity from artifact contamination before any closed-loop run.
