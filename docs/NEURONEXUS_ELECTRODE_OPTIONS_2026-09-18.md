# NeuroNexus electrode options brief — cortical recording + thalamic stimulation (rat VPL → S1FL)

Date: 2026-09-18. Prepared for the TDTClosedLoop acute-experiment program (RZ2 + PZ2-256 + ZIF-Clip headstages; IZ2 stimulator).
All part numbers, geometries and connector facts below are quoted from NeuroNexus / TDT pages and PDFs fetched today; where a
number is my own calculation it is labelled as such. Nothing here is a price quote — NeuroNexus publishes no list prices.

Sources used (fetched 2026-09-18):

- Sale / promotions: <https://solutions.neuronexus.com/sale> (Pre-SfN Sale), <https://www.neuronexus.com/news_post/back-to-school-sale-on-a-b-stock-probes/>, <https://www.neuronexus.com/september-newsletter/>, <https://www.neuronexus.com/news_post/spring-cleaning-inventory-sale-up-to-40-off/>, <https://www.neuronexus.com/news_post/last-chance-for-30-off-in-stock-probes/>, <https://www.neuronexus.com/news_post/enjoy-30-off-on-b-stock-probes/>, <https://www.neuronexus.com/blog/>, <https://www.neuronexus.com/news/>, <https://shopping.neuronexus.com/Web-Store/Outlet-Store>, <https://shopping.neuronexus.com/Web-Store/B-Stock-Inventory-List>
- Penetrating-probe design catalog (all A-/M-/V- part numbers, tip drawings, package lists): <https://www.neuronexus.com/files/catalog/NNxPenetratingProbes.pdf> (26 MB; also mirrored at <https://solutions.neuronexus.com/hubfs/Penetrating_Probe_Catalog_V2.1.pdf>)
- 2025 Surface Array catalog (ECoG/EEG part numbers): <https://www.neuronexus.com/files/catalog/NNxSurfaceArrays.pdf>
- 2023 Product catalog (packages, Matrix Array, custom design terms): <https://www.neuronexus.com/files/catalog/NeuroNexus-2023ProductCatalog.pdf>
- Matrix Array configuration guide: <https://www.neuronexus.com/files/Matrix%20Array/MatrixArray-ConfigurationGuide.pdf>; 3D probes page: <https://www.neuronexus.com/products/electrode-arrays/3dprobes/>
- NeuroNexus stimulation note (Marzullo, "Intracortical Microstimulation with Microelectrodes"): <https://www.neuronexus.com/files/technicalsupportdocuments/Stimulation.pdf>
- NeuroNexus activation (IrOx) service + tech note: <https://www.neuronexus.com/products/techincal-services/activation/>, <https://www.neuronexus.com/files/technicalsupportdocuments/Activation.pdf>
- Packages: <https://www.neuronexus.com/product_documentation/z-series/>, <https://www.neuronexus.com/files/probemapping/32-channel/Z32-Maps.pdf>, <https://www.neuronexus.com/files/probemapping/64-channel/A64-Maps.pdf>, <https://www.neuronexus.com/product_documentation/128-channel-package/>, <https://www.linkedin.com/pulse/neuronexus-connector-packages-alexis-d-paez>
- Custom design terms: <https://www.neuronexus.com/products/custom-design/>
- Other NNx pages: small-animal probes <https://www.neuronexus.com/products/electrode-arrays/up-to-10-mm-depth/>, large-animal/Vector <https://www.neuronexus.com/products/electrode-arrays/over-10-mm-depth/>, DBS/rDBSA <https://www.neuronexus.com/products/electrode-arrays/deep-brain-stimulation/>, Fusion probe <https://www.neuronexus.com/products/electrode-arrays/fusion-probe/>, X-Series <https://www.neuronexus.com/products/x-series-intan-compatible-probes/>, new products <https://www.neuronexus.com/new-products/>
- TDT: ZIF-Clip adapters <https://www.tdt.com/docs/hardware/zif-clip-headstage-adapters/>, ZCA-NN product page <https://www.tdt.com/product/zif-clip-headstage-to-neuronexus-acute-probes/>, ZCA fast facts <https://www.tdt.com/files/fastfacts/ZIFAdaptersZCA-NN.pdf>, ZIF adapter manual <https://www.tdt.com/files/manuals/hardware/ZIFAdapters.pdf>, ZC headstages <https://www.tdt.com/docs/hardware/zif-clip-analog-headstages/> and <https://www.tdt.com/files/manuals/hardware/ZIFclips.pdf>, switching headstages <https://www.tdt.com/product/switching-headstage/>, IZ2/IZ2H manual <https://tdt.com/files/manuals/Sys3Manual/IZ2.pdf>, IZ2M/IZ2MH <https://www.tdt.com/docs/hardware/iz2m-iz2mh-stimulator/> and <https://www.tdt.com/files/manuals/hardware/IZ2M.pdf>
- Competitors (brief): Cambridge NeuroTech <https://www.cambridgeneurotech.com/neural-probes>, Diagnostic Biochips Deep Array <https://diagnosticbiochips.com/hubfs/Product%20PDFs/DA128-1.pdf>, Plexon S-Probe <https://plexon.com/products/plexon-s-probe/>

---

## 1. Sale details (what is actually verifiable today)

| Item | What the source says | URL |
|---|---|---|
| **Live landing page: "Pre-SfN Sale"** (SfN 2026 is in November) | Page is live on 2026-09-18 but **prints no percentage and no end date**. Scope listed: "X-Series, Optoelectrodes, Vector Arrays, Active Probes (Activus), Matrix Arrays" plus "Surface Arrays: ECoG, EEG"; A-stock = "Pre-assembled devices on our web store are ready to ship within 1-2 days of order"; "B-stock devices are discounted because they have some irregular channels. *All B-stock sales final"; bundle: "purchase Radiens Suite plus support plan, get FREE B-stock probes for training"; "SiNAPS complete setup under $17,000"; X-Series probe coupons for XDAQ/X-Headstage buyers "must be used by December 8". | <https://solutions.neuronexus.com/sale> |
| **Outlet store (A- and B-stock)** | Search-engine snippet of the outlet store (Sept 2026) states "20% off A-Stock probes and 30% off already discounted B-Stock probes"; the store page itself shows no banner (inventory is behind a NetSuite search: 4,144 serialised devices listed, no prices shown without login). | <https://shopping.neuronexus.com/Web-Store/Outlet-Store>, <https://shopping.neuronexus.com/Web-Store/B-Stock-Inventory-List> |
| Reference: the same-season sale last year ("Back to School", posted 2025-09-03) | "20% off A-Stock probes", "30% off B-Stock probes (in addition to their already reduced price)", **through September 19**, in-stock inventory only; contact sales@neuronexus.com. The September newsletter repeats "ending September 19th". | <https://www.neuronexus.com/news_post/back-to-school-sale-on-a-b-stock-probes/>, <https://www.neuronexus.com/september-newsletter/> |
| Reference: 2026 sales so far | March 2026 "Spring Cleaning Inventory Sale": "up to 40% off" in-stock probes, valid through March 27. June 2026: "30% off a-stock and b-stock probes", through June 30. No news post for Aug/Sept 2026 exists on the news feed (latest post is June 12, 2026). | <https://www.neuronexus.com/news/>, <https://www.neuronexus.com/blog/> |

**Bottom line on the sale.** The only September-2026 promotion NeuroNexus has put on the web is the "Pre-SfN Sale" page (percentage not published) and the outlet-store discount (20% A-stock / 30% extra on B-stock, if the snippet is current). Every NeuroNexus promotion in the last 18 months has applied **only to in-stock (A/B-stock) pre-assembled devices** — never to custom designs — so the discount matters mainly for the catalog items below that happen to be in inventory (A8x8-…-Z64, A1x32-10mm-…-703-Z32, E32/E64-…-HZ grids are common stock items; check the serialised inventory list). Ask the rep (Section 5) whether the Pre-SfN terms extend to build-to-order catalog designs and to activation.

---

## 2. Connector / packaging compatibility with TDT ZIF-Clip and IZ2

NeuroNexus package naming (catalog + Paez note): **A** = acute rigid DIP-style (Samtec MOLC pins), **CM** = Omnetics nano (chronic, also usable acutely), **H** = hybrid flexible polyimide cable + connector (letter after H gives the connector: blank = Omnetics like CM, **HZ** = ZIF-Clip, HC = angled Omnetics), **Z** = TDT ZIF-Clip directly on the probe, **X3/X6** = Intan-style X-Series, **AC/HC** = 128-ch Omnetics variants, **AV/AVI/AVH** = Activus active packages, **MA/MCM/MH** = Matrix Array platforms. Catalog cable lengths are fixed per channel count: HZ16_21mm / HZ32_21mm / HZ64_30mm.

| NeuroNexus package | Pins / connector | TDT recording path (PZ2-256 + ZIF-Clip) | TDT stimulation path (IZ2/IZ2H) | Notes |
|---|---|---|---|---|
| **Z16 / Z32 / Z64** | ZIF-Clip receptacle on the probe (Hirose DF30 family; ZC16/ZC32 use DF30FC-20DS-0.4V, ZC64 uses DF30FC-34DS-0.4V) | **Direct** — NNx: "Z16 connects to TDT ZC16 headstage", "Z32 … ZC32", "Z64 … ZC64" (weights 0.23/0.24/0.45 g). Gen-5 Z16/Z32 packages carry 2 insulated ref/gnd wires. | Via a **ZIF-Clip switching headstage** (ZC16_SW4, ZC32_SW8, ZC64_SW16 — records all channels, stimulates 4/8/16 of them on the same electrode, ~82/123/205 µs switch time, 500 mV input range) — TDT states these are "controlled from the Subject Interface through Synapse"; confirm RZ2+IZ2 compatibility with TDT. Otherwise no ZIF-to-DB26 adapter is listed by TDT. | Best choice for the recording probe; also for a stim probe if the SW headstage route is confirmed. |
| **HZ16 / HZ32 / HZ64** | Same ZIF-Clip receptacle at the end of a 21 mm (16/32-ch) or 30 mm (64-ch) polyimide cable | Direct to ZC16/32/64 | Same as Z | Cable decouples the headstage weight from the stereotaxic holder — useful when the 64-ch probe is inserted at a shallow tangent angle. |
| **A16 / A32 / A64** (acute) | A32: 40-pin Samtec MOLC-110-01-S-Q; A64: 2× MOLC (mates FOLC-140) | **Adapter**: ZCA-DIP16 (16), **ZCA-NN32** (32, "32-channel NeuroNexus A32-style probes", use with ZC32/ZD32/ZCD32), **ZCA-NN64** (64, "A64-style", ZC64/ZD64/ZCD64; three jumper options for ref/gnd/X-ref) | Direct wiring from the IZ2 DB26 to the MOLC pins ("Connect the DB26 output connectors on the stimulator to the stimulating electrodes using your preferred method such as direct wiring or a custom pass through connector (available from TDT)") | Cheapest package; adapter adds a remap layer (use Synapse Mapper). |
| **CM16LP / CM32**, **H16 / H32 / HC32** | Omnetics nano-strip (18-pin / 36-pin) | Adapter ZCA-OMN16 / ZCA-OMN32 / ZCA32-FLEX-OMN | Custom Omnetics→DB26 cable (this is how a Microprobes Omnetics array is normally driven from the IZ2) | Good "dual-use" package: one Omnetics male can be swapped between the ZCA adapter (record) and the IZ2 cable (stim) or split across a switching headstage. |
| **H64 / H64LP / HC64 / SEACM64** | 2× Omnetics 36 (H64) or Samtec (SEACM64) | Adapter ZCA64-FLEX-OMN ("two 32-channel chronic Omnetics based probes to a 64-ch ZIF-Clip"; ZC64 analog only) — verify pinout against the H64 map | Custom cable | Catalog note: H-package 64-ch designs ship "with up to 2 irregular sites" unless a perfect probe is requested. |
| **AC128 / HC128 / X6-128 / AV128** (all 128-ch designs) | Omnetics/Intan-style | **No TDT ZCA adapter listed for 128-ch NeuroNexus** (TDT's ZC128 exists — 4× DF30-34 — but the adapter table stops at 96 ch) | — | For 128 channels on the PZ2-256, buy 2× 64-ch Z64 probes instead (see §3). |
| **Matrix packages MA64 / MA128 (acute), MCM64/128, MH64/128** | Omnetics NSD36 ("4 guideposts") ×2 or ×4 | ZCA64-FLEX-OMN (2×32 Omnetics) or ZCA-OMN32 per 32-ch bank — confirm NSD36 vs NPD36 keying with TDT | Custom Omnetics→DB26 cable | Matrix Array packages are Omnetics-only in the selection guide; no Z variant listed. |
| **ECoG E-series** | H32/HC32/HZ32/X3-H32 (32-ch), H64/H64LP/HC64/HZ64/X3-H64 (64-ch) | HZ32/HZ64 direct to ZC32/ZC64 | — (E32-1000-20-50/100 has 200 µm "stim sites" + 100 µm rec sites, Pt) | 15 µm polyimide, Pt sites. |

IZ2 facts relevant to the electrode choice (IZ2 manual; IZ2M page):

- IZ2-32/64/128: current mode "up to 300 µA … across up to 128 stimulating electrodes (impedance up to 50 kOhm)"; IZ2H: "up to 3 mA … up to 16 stimulating electrodes (impedance up to 5 kOhm)"; voltage compliance ±12 V (±15 V through electrode + return per the LED note). Channels are in 16-ch banks "powered down when no headstage is connected"; outputs are **DB26**.
- With the LZ48M battery, "no more than 10 of the channels can be enabled for stimulation at the same time" unless pin 8 is set (which also bypasses over-current fault detection). Eight true bipolar pairs driven as +I/−I on 16 channels exceed that limit — clarify how the current Microprobes protocol handles this (sequential pairs, or common return).
- Sampling: 128 ch at 50 kHz, 64 ch at 100 kHz, 32 ch at 200 kHz; RB100 (100 kΩ) / RB10 (10 kΩ) resistor blocks ship with IZ2 / IZ2H for testing.
- Site impedance matters: NeuroNexus recommends "low impedance probes (50-300 kΩ)" for stimulation and monitoring back-voltage; with 50 kΩ IZ2 compliance, a 703 µm² IrOx site (typically tens of kΩ at 1 kHz) is fine, a 177 µm² unactivated Ir site (~1 MΩ) is not.

---

## 3. Cortical recording options (S1FL, tangent-planar 64-ch LFP)

Current probe: 64-ch, 8 shanks × 8 sites, 200 µm × 200 µm — this is the catalog **A8x8-5mm-200-200-177** or **-703** (5 mm shanks, 1400 µm shank span, 122 µm max shank width, 4200 µm² reference site, 15 or 50 µm thick; packages A64, H64_30mm, H64LP_30mm, HC64_30mm, HZ64_30mm, SEACM64, Z64, AV64…). Check which site area you own (site diameter 15 µm = 177 µm², 30 µm = 703 µm²).

| # | Part number (catalog page) | Sites / geometry | Site area | Package for TDT | Fit vs current 8×8-200-200 |
|---|---|---|---|---|---|
| C1 | **A8x8-5mm-200-200-703** (p.082) | 64; 8 shanks @200 µm, 8 sites @200 µm; span 1.4 × 1.4 mm; 15 or 50 µm thick | 703 µm² (30 µm dia) | **Z64** or **HZ64_30mm** (direct to ZC64) | Identical geometry to the current array, so all existing maps/pipelines carry over. Larger sites → lower impedance, lower thermal noise, better LFP SNR in the 5-200 Hz band, and spike-silent by design (which matches the LFP-dominant use). If the current probe is the 177 variant this is the zero-risk upgrade; if it is already 703, buy a spare (A-stock likely). |
| C2 | **A8x8-10mm-200-200-703** / **-177** (p.083) | Same 8×8-200-200 layout at the tip of 10 mm shanks (83 µm shank width at sites, 123 µm max; 50 µm thick only) | 703 or 177 µm² | Z64 / HZ64_30mm | Same footprint; the extra 5 mm lets the site block be driven further along a shallow tangent track (or reach medial/ventral S1 from a lateral entry) without the package touching bone. Only 50 µm thickness — stiffer, better for a shallow-angle insertion through pia. |
| C3 | **A8x8-Edge-5mm-100-200-177** (p.086) or **A8x8-Edge-5mm-50-150-177** (p.085) | 64; 8 shanks @200 µm (or 150 µm) with 8 edge sites @100 µm (700 µm span) or @50 µm (350 µm span); 60 µm max shank width; 15 µm thick | 177 µm² | Z64 / HZ64_30mm | Denser laminar sampling on the same 8 shank tracks (100 µm instead of 200 µm along the shank), i.e. a laminar-resolved version of the current array. Worse for pure LFP coverage (700 µm instead of 1400 µm along the shank), worse per-site impedance (177 µm²), better if you want CSD across layers at the tangent insertion. |
| C4 | **E64-500-20-60** / **E64-500-25-100** / **E64-500-80-60** rat ECoG grids (Surface catalog pp.032-034; naming = E{ch}-{pitch µm}-{cable mm}-{site dia µm}) or the coarser **E64-1000-50-200** (p.035: 8×8, 1000 µm pitch, 200 µm Pt sites = 31,416 µm², footprint ≈7.6 × 7.9 mm, 50 mm cable) | 64 surface sites; 15 µm polyimide; Pt | 60 / 100 / 200 µm dia | **HZ64** (direct to ZC64), also H64/H64LP/HC64/X3-H64 | True epicortical LFP with no penetration — the closest commercial analog of the "surface/laminar hybrid" you get from the tangent insertion, and it can sit on the dura/pia over S1FL while the thalamic probe is placed. 500 µm pitch (3.5 mm span) is 2.5× coarser than the current 200 µm grid; 1000 µm pitch is 5× coarser but covers all of S1FL + S1HL/M1. Not in the penetrating-probe sale line, but ECoG **is** in the Pre-SfN list. |
| C5 | 128-ch: **2 × A8x8-5mm-200-200-703-Z64** (two ZC64 headstages on the PZ2-256), rather than a single 128-ch design | 2 × 64 = 128; two 1.4 mm blocks side by side or S1FL + S1HL/M1 | 703 µm² | Z64 ×2 | The catalog 128-ch planar/edge designs (**A8x16-Edge-5mm-100-200-177**, **A16x8-5mm-berg-200-160**, **A4x32-5mm-100-400-1250**) come only in AC128/HC128/Activus/X6 packages, and TDT lists no 128-ch NeuroNexus ZIF adapter — so two Z64 probes are the practical way to double the cortical channel count on TDT hardware. |

Not recommended for this role: Buzsaki64 / Poly2 / Poly3 (spike-oriented, 20-50 µm site pitch, wrong footprint), SiNAPS/Activus active probes (need the NNx interface box, not the PZ2), Fusion double-sided probes (no ZIF package listed yet).

---

## 4. Thalamic stimulation options (VPL, 5.5-7 mm deep; ≥ 8 independent bipolar pairs with separated footprints)

### 4.1 Charge-injection limits that constrain every option (NeuroNexus stimulation note + my arithmetic)

NeuroNexus' own note: iridium charge capacity "100-150 µC/cm²", activated iridium oxide "1200 µC/cm²"; recommended "site sizes (≥ 703 µm²)" and "low impedance probes (50-300 kΩ)"; electrolysis window for NNx IrOx "0.6 V and -0.8 V"; worked example: 1250 µm² IrOx, 200 µs phase → **75 µA** electrode limit; Shannon k = 1.7 tissue limit at 1250 µm² → 0.025 µC → **125 µA**. The activation note says NNx activates to "no more than 30 mC/cm²" CSC by cyclic voltammetry in 0.3 M Na2HPO4 (−0.85 to 0.75 V square wave).

Max current per site for the lab's **200 µs/phase** pulses (I = Q/t; Q_electrode = capacity × area; Q_tissue = sqrt(A·10^1.7) with A in cm²):

| Site area | Bare Ir (150 µC/cm²) | **Activated IrOx (1200 µC/cm²)** | Shannon k = 1.7 tissue limit | Lab's 40 µA × 200 µs = 8 nC/phase |
|---|---|---|---|---|
| 177 µm² | 1.3 µA | 10.6 µA | 47 µA | far over electrode limit |
| 413 µm² | 3.1 µA | 25 µA | 72 µA | over electrode limit |
| **703 µm²** | 5.3 µA | **42 µA (8.4 nC)** | 94 µA | **just inside** (≤ 40 µA OK) |
| **1250 µm²** | 9.4 µA | **75 µA (15 nC)** | 125 µA | 2× headroom |
| 4200 µm² (the large reference site on A8x8/A1x32-10mm designs) | 32 µA | 252 µA | 229 µA (tissue-limited) | usable as a low-impedance return |

Consequences: (a) any silicon option **must be activated (IrOx)** — bare-iridium 703 µm² sites are limited to ~5 µA; (b) 703 µm² IrOx sites sit exactly at the lab's 40 µA ceiling, 1250 µm² sites give 2× headroom but exist in the catalog only on ≤ 5 mm designs (A4x32-5mm-100-400-1250, A4x4-4mm-200-200-1250), so 1250 µm² at 8-10 mm is a custom; (c) bipolar pairs on adjacent 200 µm sites keep the current path local, which is what you want for spatially distinct footprints. NeuroNexus lists "Record and stimulate" as a supported usage for all standard silicon probes (catalog specs: "Usage: Single unit, Multiple unit, LFP. Record and stimulate. Acute and chronic."), for Matrix Arrays ("record and stimulate from 64 to 256 channels"), Vector Arrays and the rDBSA; it does not publish per-design current ratings — the note above is the only guidance.

### 4.2 Options

| # | Part / config (catalog page) | Reach & 3D coverage | Sites | Independent bipolar pairs | TDT package / stim path | Stimulation listed? | Assessment for raising the stim→S1 rank |
|---|---|---|---|---|---|---|---|
| T1 | **A8x8-10mm-200-200-703** (p.083), activated (IrOx) | 10 mm shanks (VPL at 5.5-7 mm reached with margin); 8 shanks @200 µm = 1.4 mm across (ML or AP, set by insertion orientation); 8 sites @200 µm = 1.4 mm DV per shank; 50 µm thick, 83 µm wide at the sites | 703 µm² ×64 + 4200 µm² ref | **8 pairs, one per shank** (adjacent-site dipole, 200 µm, at a chosen depth) → 8 footprints 200 µm apart across the VPL somatotopic axis; or 4 shanks × 2 depths for a DV/ML mix; the other 48 sites record VPL LFP/MUA simultaneously (Z64 → ZC64) | **Z64** (or H64_30mm + custom Omnetics→DB26 cable); with ZC64_SW16 you get 16 stim + 64 rec on one probe | Yes ("record and stimulate") | Best off-the-shelf match: same 200 µm pitch as the cortical grid, sites large enough for 40 µA after activation, and — unlike the single-contour microwire array — the pairs are distributed across a 1.4 × 1.4 mm sheet so each drives a different VPL sub-population. Same-day A-stock possible (this is a stocked design in the 64-ch map set). |
| T2 | **A2x16-10mm-100-500-703** (p.042) or **A2x16-10mm-50-500-703** (p.041), activated | 10 mm; 2 shanks 500 µm apart; 16 sites @100 µm (1.5 mm DV) or @50 µm (0.75 mm DV); 50 µm thick | 703 µm² ×32 + 4200 µm² ref | 8 pairs stacked in DV (4 per shank) → footprints separated in depth and 500 µm in ML/AP | **Z32** direct to ZC32; ZC32_SW8 gives exactly 8 stim channels | Yes | Cheapest 703 µm²/10 mm option and fits the ZC32_SW8 exactly, but only 2 lateral positions — rank gain comes from depth (dorsal vs ventral VPL = different body parts) rather than the ML map. Good second probe / pilot. |
| T3 | **Matrix Array, MA64 acute package with 2 × M4x8-10mm-100-200-703** (p.167) at 300-400 µm platform spacing | 10 mm; 4 shanks @200 µm × 2 rows @300-400 µm = true **3D 4×2 shank grid**; 8 sites @100 µm (0.7 mm DV); 50 µm thick | 703 µm² ×64 | 8 pairs = one per shank in a 4 × 2 grid (0.6 × 0.3-0.4 mm footprint) or 4 × 2 depths | MA64 (2× Omnetics NSD36) → ZCA64-FLEX-OMN for recording; custom Omnetics→DB26 for stim | Yes (Matrix "record and stimulate") | Real 3D coverage at 200-400 µm spacing — the configuration that most directly attacks a rank-1 operator by separating dipoles in all three axes. Trade-offs: Omnetics-only packages (adapter), 128-ch version needs 4 arrays, insertion of a multi-row platform is harder (NNx sells the IST-Matrix vacuum insertion tool), and the 0.7 mm DV span per shank is short — pair with T4 lengths for the full dorsoventral extent. |
| T4 | **Matrix Array with M3x10-8mm-500-900-703** (p.156) ×2, or **M3x8/16-12mm-1500/700-900-703** (p.157) | 8 mm (or 12 mm) shanks; 3 shanks @900 µm; 10 sites @500 µm → **4.5 mm DV span**; two arrays at 400-1000 µm platform spacing → 3 × 2 shank grid over ~1.8 × 1 mm | 703 µm² ×60 (+121 µm² tip sites) | up to 8 pairs distributed across 6 shanks and 2-3 depths | MA64 → ZCA64-FLEX-OMN / custom DB26 | Yes | Sparse but wide: covers the whole DV extent of VPL/VPM so you can pick the depth with the strongest S1FL response per shank, then form pairs there. 900 µm shank pitch is coarser than the 200-400 µm target — useful as a mapping probe more than as the final high-rank driver. |
| T5 | **Custom "VPL-contour" 8-shank array** (NNx custom design; per-shank lengths specifiable "to the nearest 0.1 mm", 1.1-15 mm range; site area, spacing, shank spacing, material all custom) — e.g. 8 shanks at 250-300 µm pitch with staggered lengths 7.4-8.0 mm (replicating the Microprobes contour) and 4-8 sites of **1250 µm²** at 200 µm near each tip, IrOx-activated, **Z64 / HZ64** package | Exactly matched to VPL curvature; 2D or (as a Matrix, 3D) | 1250 µm² → 75 µA per site headroom | 8-16 pairs with tip-local dipoles on independent tracks | Z64 direct; ZC64_SW16 for simultaneous stim/rec | Yes | Highest-rank design on paper and the only way to get 1250 µm² sites at 8 mm. Cost/lead time: NNx custom = non-refundable engineering fee, minimum order **5 probes for 64-ch (10 for ≤ 32-ch)**, "up to 2 irregular sites" allowed per 64-ch probe, tiered pricing "dependant on channel count, feature spacing, packaging, shank length and site material", and mask sets run "only once every few months" so expect months, not weeks. Not sale-eligible. |
| T6 | **A1x16-10mm-100-703** (p.021) / **A1x32-10mm-100-703** (p.040) single-shank laminar, activated | 10 mm; 16 sites @100 µm (1.5 mm) or 32 @100 µm (3.1 mm DV) | 703 µm² + 4200 µm² ref | ≤ 8 DV-stacked pairs on one track | Z16/Z32 direct; ZC16_SW4 / ZC32_SW8 | Yes | Lowest cost, in stock, ideal for a first activation + charge-limit + DV-mapping pilot of the IZ2 with silicon sites; by itself it cannot raise rank across ML/AP (one track). |
| — | Not suited: **A4x8-7mm-100-200-177** (7 mm is marginal, 177 µm² sites cap at ~10 µA IrOx); **A4x8-5mm-200-200-703** (5 mm, too short — but the natural template for a custom 10 mm A4x8-200-200-703); **rDBSA** rat lead (Pt, "16-channel design with 4 stimulation bars and 10 recording sites", Omnetics NPD18) — only 4 stim contacts on one lead = rank ≤ 4 and no 200 µm structure; **Vector Array** (NHP, 70/110 mm, 177 µm² Ir) — wrong scale. |

---

## 5. Recommended buy

### Cortical recording (S1FL, 64-ch tangent planar)

1. **A8x8-5mm-200-200-703-Z64** (or **-HZ64_30mm** if you want the cable for the shallow-angle holder) — keeps the exact 8×8/200/200 geometry your MPC, Choi-replay and touch pipelines assume, improves LFP SNR via 703 µm² sites, and plugs straight into the ZC64. Likely A-stock → eligible for the Pre-SfN / outlet discount (20% A-stock, per the outlet-store terms) and same-day shipping. Buy two if the price allows (one spare against the PZ2-off/y-liveness class of incidents).
2. **E64-500-20-60-HZ64** (or E64-1000-50-200-HZ64) rat ECoG grid — a surface-only LFP complement over S1FL that occupies no cortical tissue, plugs into a second ZC64 on the PZ2-256, and is on the Pre-SfN product list. Use it to validate that the tangent-planar array's spatial patterns are surface-visible (important for the closed-loop biomimetic claims) and as a fallback when a penetrating insertion damages S1FL.

### Thalamic stimulation (VPL, ≥ 8 independent pairs, higher-rank drive)

1. **A8x8-10mm-200-200-703-Z64, IrOx-activated by NeuroNexus** (+ TDT **ZC64_SW16** switching headstage if TDT confirms RZ2/IZ2 support; otherwise order as **H64_30mm** and have TDT/NNx build an Omnetics→DB26 stim cable). Rationale: 8 shanks × 200 µm gives eight spatially separated dipoles across VPL's somatotopic axis (vs the single contour of the 2×8 microwire array that yielded rank ≈ 1 under tonic drive), 703 µm² IrOx sites support the lab's 40 µA/200 µs pulses (8.4 nC limit vs 8 nC used), and the remaining sites record thalamic LFP/MUA for the plant-ID work. Stock design; sale-eligible if in inventory; activation is a quoted service.
2. **Matrix Array MA64 with 2 × M4x8-10mm-100-200-703 at 400 µm platform spacing (IrOx-activated)** — the true-3D option (4 × 2 shanks, 200 × 400 µm, 0.7 mm DV) for the follow-on experiment once T1 shows which axis carries the extra rank. Order with the IST-Matrix insertion tool quote; expect Omnetics packaging (ZCA64-FLEX-OMN for recording, custom cable for IZ2). If budget allows only one thalamic buy this season, buy T1 now and spec the custom VPL-contour array (T5, 1250 µm² sites, per-shank lengths) for the next mask cycle.

Pricing: NeuroNexus does not publish list prices; the only public numbers are "X-Series probe packages … beginning at $450 unit price" and "SiNAPS complete setup under $17,000". Treat any per-probe figure as a quote item. Cost levers you control: A-stock vs build-to-order, 15 vs 50 µm thickness (no price difference stated), Z vs A packaging (A is "generally lower cost"), and activation (per-probe service fee).

### Questions for the NeuroNexus sales rep (sales@neuronexus.com, +1 734 913 8858)

1. Pre-SfN Sale: exact discount % on A-stock and B-stock, end date, and whether it applies to build-to-order catalog designs (A8x8-10mm-200-200-703-Z64) and to the activation service; does the B-stock "irregular channels" list let us exclude designated stim sites?
2. Is **A8x8-10mm-200-200-703** with **Z64** or **HZ64_30mm** in A-stock today (serial-number lookup), and in which thickness (50 µm only per catalog)? Same for A8x8-5mm-200-200-703-Z64 and A2x16-10mm-100-500-703-Z32.
3. Activation (IrOx): cost, lead time, resulting 1 kHz impedance and CSC (they target ≤ 30 mC/cm²), whether they will activate only designated sites, and their recommended max charge/phase for 703 µm² and 1250 µm² activated sites at 200 µs — do they endorse the 42 µA / 75 µA numbers from their note?
4. Can the 4200 µm² reference site be used as a low-impedance stimulation return, and can it be activated?
5. Custom VPL-contour array (T5): NRE fee, minimum order (5 for 64-ch?), unit price, next mask-set date, and whether 1250 µm² sites and per-shank staggered lengths (7.4-8.0 mm) on a Z64/HZ64 package are within the standard design rules; can it be built as a Matrix 2-row platform?
6. Matrix Array: does an MA64 with two M4x8-10mm-100-200-703 arrays exist in stock; which platform spacings (200/300/400 µm) are available for 10 mm arrays; is a Z/ZIF package possible for Matrix, or only Omnetics NSD36; IST-Matrix insertion tool pricing.
7. Connector mapping: provide the Z64 and HZ64 pin maps for A8x8 (Gen-5 wiring) and confirm which ZIF-Clip generation the TDT ZC64 in the lab matches; for Omnetics packages confirm NSD36 vs NPD36 keying for TDT's ZCA64-FLEX-OMN.
8. Stimulation support statement: will NNx put in writing that A8x8-…-703 (activated) is rated for 40 µA / 200 µs biphasic at 100 Hz for acute sessions, and what failure mode they see (delamination, site loss) above the limit?
9. ECoG: current stock and price of E64-500-20-60-HZ64 / E64-1000-50-200-HZ64; site diameter, pitch and footprint drawings for the E64-500 family (only names are indexed in the surface catalog).
10. Fusion probe: does a 10 mm, 703 µm² double-sided version exist, is stimulation rated, and is a ZIF package planned?

### Questions for TDT (support@tdt.com)

1. Do the ZC32_SW8 / ZC64_SW16 switching headstages work with an RZ2 + PZ2-256 + IZ2 (not the Subject Interface), and what is the current limit through the switch?
2. Part number/price for the "custom pass-through connector" that takes IZ2 DB26 outputs to Omnetics 36 (H64) or ZIF-Clip (Z64).
3. Confirm that ZCA64-FLEX-OMN accepts NeuroNexus H64_30mm / MA64 (NSD36) connectors, and whether a 128-ch NeuroNexus adapter for ZC128 exists.

---

## 6. Brief competitor comparison (for context only)

| Vendor | Relevant product | Why it does not replace the NNx options above |
|---|---|---|
| Cambridge NeuroTech | Silicon probes, 16-128 ch, Omnetics/Intan-style, "plug & play" with mainstream headstages; recording spans 0.15-3.15 mm | Recording-oriented (~50 kΩ small sites, no stimulation rating, no IrOx service); shank lengths for rat thalamus and ZIF packaging must be requested. |
| Diagnostic Biochips | Deep Array DA128 (128 sites, 16 µm dia, on a 0.2 mm stainless-steel shank up to 90 mm; recording span 3.175 mm) | Single shank, tiny sites (~200 µm²) — a recording probe, not a multi-pair stimulator. |
| Plexon | S-Probe / V-Probe (8-64 ch, 15-40 µm Pt/Ir sites, single shank, Omnetics; 32-ch S-Probe has a 16-rec + 16-stim column; ~6-week lead) | One shank per probe and 15 µm sites (~180 µm²) cap charge per site far below 8 nC; multi-shank 3D coverage would need multiple probes/manipulators. |
| Microprobes (current) | 2×8 microwire array, custom staggered lengths | Excellent per-wire charge capacity but the single contour gave rank ≈ 1; no simultaneous per-site recording at 200 µm granularity. |

---

### Appendix A — catalog part-number decoding (NNx convention)

`A{shanks}x{sites per shank}-{shank length}-{site spacing µm}-{shank spacing µm}-{site area µm²}` (+ layout tags Edge/Poly2/Poly3/tet/berg; `s` = staggered); Matrix 2D arrays use the `M` prefix; surface grids `E{ch}-{pitch}-{cable length mm}-{site dia µm}`; package suffix e.g. `-Z64`, `-HZ64_30mm`, `-A64`, `-H64LP_30mm`, `-CM32`. Site areas in the catalog: 121, 160, 177, 225, 413, 703, 1250 µm² (plus 4200 µm² reference sites); thickness 15 or 50 µm (10 mm designs: 50 µm only); standard site metal iridium (Pt, Au custom; PtIr standard on Matrix arrays).

### Appendix B — candidate part numbers found in today's catalog index (for the quote request)

Cortical: A8x8-5mm-200-200-177 / -703 (p.082); A8x8-10mm-200-200-177 / -703 (p.083); A8x8-Edge-5mm-50-150-177 (p.085); A8x8-Edge-5mm-100-200-177 (p.086); A4x16-3mm-50-200-177 (p.081); A8x16-Edge-5mm-100-200-177 (p.122, 128-ch); A16x8-5mm-berg-200-160 (p.123, 128-ch); E32-1000-30-200 (surface p.024); E64-500-20-60 / E64-500-25-100 / E64-500-80-60 / E64-1000-50-200 / E64-2500-50-200 (surface pp.032-036).

Thalamic: A8x8-10mm-200-200-703 (p.083); A2x16-10mm-50-500-703 / A2x16-10mm-100-500-703 (pp.041-042); A1x16-10mm-100-703 (p.021); A1x32-10mm-50-703 / A1x32-10mm-100-703 (pp.039-040); A1x16-12mm-250-ref-gnd-703 (p.022); A4x8-7mm-100-200-177 (p.051); M4x8-10mm-100-200-703 (p.167); M3x10-8mm-500-900-703 (p.156); M3x8/16-12mm-1500/700-900-703 (p.157); M2x16-5mm-200-400-703 (p.153); M4x8-11mm-1500-400-177 (p.168); A4x32-5mm-100-400-1250 (p.113, 1250 µm² reference design); A4x4-4mm-200-200-1250 (p.028).
