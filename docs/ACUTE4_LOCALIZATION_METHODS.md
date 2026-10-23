# Acute #4: array verification and VPL localization methods (literature survey, 2026-10-16)

Why: on acute #3 (2026-10-14) the 64-ch cortical array was electrically broken before the first
recording (connector-bank pattern: ch1-16 and 57-64 dead, 21-27/64 contacts with their own signal,
pairwise channel correlation 0.98-0.99 vs 0.87-0.90 on the same array during acute #2). Thalamic
targeting was done only by stim-evoked cortical responses, which that array could not show. Auditory
unit monitoring was unavailable. Every method below was found on the web this week; items marked
*uncertain* could not be verified from a citable source.

Notes from the search: Butovas & Schwarz 2003 (J Neurophysiol 90:3024) is intracortical
microstimulation, not thalamic, so it is not a placement protocol. Francis, Xu & Chapin 2008
(J Neurophysiol 99:2291, rat VPL receptive-field mapping) is the right reference for forepaw-VPL
coordinates but the full text was not accessible; coordinates come from the other sources.

## A. Cortical array electrical integrity (before trusting it)

1. **1 kHz impedance census with explicit open/short bands.** Barrese et al. 2013, J Neural Eng
   10:066014 (https://pmc.ncbi.nlm.nih.gov/articles/PMC4868924/). Utah arrays, 1 kHz: pre-implant
   mean 305 kOhm; > 2500 kOhm = open; connector shorts = all channels < 50 kOhm (acute shorts
   50-100 kOhm); viable channel = spike p-p >= 40 uV with noise < 150 uV. 48 % of failures were acute
   mechanical and 83 % of those connector-related. Microprobes MEA spec: Pt/Ir electrodes custom
   10 kOhm-5 MOhm (https://microprobes.com/products/multichannel-arrays/mea); flag channels > 5x
   nominal or < ~50 kOhm.
2. **1 kHz alone can miss broken leads; add a low-frequency magnitude/phase point.** Caldwell et al.
   2018, J Neural Eng (https://pmc.ncbi.nlm.nih.gov/articles/PMC6266965/): "a 1 kHz impedance was
   not able to differentiate between functional and presumed broken channels"; opens = mean |Z| at
   < 100 Hz > 1e8 Ohm; phase at < 100 Hz discriminates. Practical: run the Synapse impedance sweep
   at two frequencies (100 Hz and 1 kHz) and compare.
3. **Synapse runtime impedance (IZ2 / PZ5).** TDT docs
   (https://www.tdt.com/docs/synapse/hardware/iz2-electrical-stimulation/,
   https://tdt.com/docs/synapse/hardware/subject-interface-amplifiers/,
   https://www.tdt.com/files/fastfacts/PZ5.pdf): 500 ms sine per channel at a set frequency and
   target current, green/yellow/red vs user thresholds, "Save Impedance to CSV" into the block
   folder; PZ5 adds Ref-to-ground and Gnd impedance and a sort by deviation. Default thresholds are
   not documented (*uncertain*).
4. **Common-mode signature as a broken-array / bad-reference test.** TDT reference modes: Local =
   pin 5 per 16-ch bank, Shared = one reference, None = ground as reference. The "all channels
   identical" signature is not documented as a diagnostic in any citable source (*uncertain*, but it
   is what our 10-14 data showed: pairwise corr 0.99, differential RMS 7 uV).
5. **Pre-implant saline bench test.** Emory CAMBER protocol
   (https://camber.emory.edu/documents/instructions-for-impedance-test_09232023.pdf): contacts and
   the ground/reference wire fully submerged, no bubbles on contacts (bubbles covered 44 % of
   contacts in one cochlear study), inspect under magnification, then run the headstage impedance
   test. Our 10-13 bench block was recorded in air and showed pure mains on every channel, which
   cannot distinguish a good array from a broken one.

## B. VPL target confirmation

6. **Stereotaxic forepaw-VPL coordinates (rat, from bregma).**
   | source | AP | ML | depth | note |
   |---|---|---|---|---|
   | Choi et al. 2016, J Neural Eng 13:056007 (https://iopscience.iop.org/article/10.1088/1741-2560/13/5/056007) | -2.4 | 2.8 | 6-7 mm | VPL hand region; S1 digit 4.0 L, 0.5 A |
   | Chao et al. 2014, PLoS One 9:e97305 (https://pmc.ncbi.nlm.nih.gov/articles/PMC4019572/) | -2.7 | 2.5 | 5-6 mm | reference plane not stated |
   | Aguilar et al. 2008, Eur J Neurosci 27:378 (https://pmc.ncbi.nlm.nih.gov/articles/PMC2253690/) | -2.3 to -4 | 2-4 | 5-7 mm | forepaw in dorsolateral VPL |
   | Jiang et al. 2015, PLoS One 10:e0117289 | -2.9 to -3.1 | 3.3-3.8 | 6.3-6.65 mm | hindpaw VPL |
   Our tips are 7.4-8.0 mm long and acute #2 found 8/8 responsive pairs there, so the reference
   plane (skull vs dura; tip vs shank) must be written on the runbook rather than re-derived.
7. **Receptive-field mapping while advancing (audio).** Choi 2016 / patent US10384064: units with
   hand-specific receptive fields identified by audio; depth fine-tuned to maximize responsive
   units; 2-4 shanks picked up touch responses. Chao 2014: tap the forepaw, 300-3000 Hz filter,
   audio monitor, 145 kOhm tungsten. Aguilar 2008: paintbrush light touch, 4 MOhm tungsten.
8. **Latency criteria.** Forepaw VB units 7.1 +/- 1.6 ms (Aguilar 2008); 4.5 ms to wrist electrical,
   6.6 ms mechanical (Angel & Clarke 1975, J Physiol 249:399,
   https://pmc.ncbi.nlm.nih.gov/articles/PMC1309581/). S1 after natural touch 9-15 ms (Choi 2016);
   S1 after VPL stim ~2 ms (patent). Jiang 2015: stim- vs touch-evoked S1 latencies within 0.5 ms.
9. **Antidromic identification** (Lipski 1981, J Neurosci Methods 4:1, PMID 7253697): constant
   latency, follows 200-333 Hz trains, collision test. Needs a live S1 recording; not a primary gate.
10. **Post-hoc marking.** Electrolytic lesion 30 uA anodal 30 s, cresyl violet (Chao 2014). DiI on
    the shank backs before an acute insertion (DiCarlo et al. 1996, J Neurosci Methods,
    https://dicarlolab.mit.edu/biblio/marking-microelectrode-penetrations-fluorescent-dyes; CM-DiI
    protocol https://www.protocols.io/view/painting-neuropixels-probes-and-other-silicon-prob-wxqffmw.pdf).
11. **Descent landmarks (hippocampal theta / ripple layer, unit-free zones).** No rat VPL paper found
    that uses them as a protocol step (*uncertain* for our use).

## C. Stimulus-delivery checks

12. **IZ2 hardware monitors** (https://www.tdt.com/docs/hardware/iz2m-iz2mh-stimulator/): compliance
    +/-12 V; IZ2M +/-300 uA into <= 40 kOhm; front-panel lights green > +/-150 mV, red > +/-10 V
    (compliance hit); MonBank A/D samples the output voltage on a bank of 8 via the IZ2_Control
    macro. No swing or railing at +/-10 V = open / high-impedance lead. A constant-current stimulator
    cannot drive a lead that has left tissue (WPI app note,
    https://wpiinc.com/blogs/all/isolated-stimulation-explained).
13. **Bipolar vs monopolar.** Choi 2016 chose adjacent-pair bipolar for lower artifact on cortical
    channels; 200 us/phase symmetric biphasic, <= 25-40 uA; 480 us blanking on 24.4 kHz broadband.
    Artifact on a raw channel confirms current flow but not location. Our 610 Hz LFP stream shows no
    pulse artifact even on the acute #2 GO block, so artifact-as-delivery-proof needs the raw stream
    or the MonBank trace.

## Use for acute #4 (top 5)

1. Saline bench impedance of both arrays at two frequencies, bubbles excluded, plus Ref/Gnd
   impedance, saved to CSV; reject channels < 50 kOhm or > 2.5 MOhm; abort if all channels cluster
   at one value (A1-A3, A5).
2. Repeat impedance in tissue right after cortical insertion; require spikes/LFP with the channel's
   own signal on the majority of contacts (cortical gate: footprint < 16 ch, pairwise corr < 0.95,
   common-mode evoked wave < 20 uV) before the thalamic descent (A1, this week's data).
3. VPL descent with audio and forepaw tap from 5.5 mm, expecting forepaw units at 6-7 mm by the
   literature reference planes, tactile latency 5-9 ms; fine-tune depth to maximize responsive
   shanks (B6-B8).
4. Single-pulse bipolar VPL stim 20-30 uA, 200 us/phase: S1 evoked response at 2-5 ms on >= 2 pairs
   (existing thalamic gate), with the IZ2 MonBank trace showing a non-railing pulse per channel
   (C12-C13).
5. DiI-coat the thalamic array and lesion 30 uA / 30 s at the end for histology (B10).
