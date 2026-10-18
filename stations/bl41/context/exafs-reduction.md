<!-- Condensed from: autonomous_fourone/.claude/skills/exafs-reduction/SKILL.md, autonomous_fourone/.claude/skills/sample-data-collection/SKILL.md, 2026-10-17 -->

# XANES / EXAFS reduction at BL4-1

Reduction of a sample's reps is done with the SSRL `exafs_analysis` package
(developed on BL 4-3 data; its background removal is AUTOBK, validated
against Larch). It reads recorded SPEC scans; a scan still running is not
included.

## Signals and energy axis

- **Transmission:** mu = ln(I0/I1), from the dark-subtracted `bgI0/bgI1`
  when recorded.
- **Fluorescence:** `xsum` (24-element Ge sum, or group `xsA`/`xsB`;
  dead-time corrected in the Xspress hardware) / I0, or `pips`/I0.
- **Energy:** `absev` (encoder readback).
- **Reference foil** ln(I1/I2) is used only as a calibration check (reports
  the foil edge offset).
- XANES (gscan) and EXAFS (kscan) reps of a sample are never merged
  together.

## Steps

1. **Rep QC:** each rep is compared with the median rep. Status: `ok`
   (merged), `outlier` (much worse fit than the others, not merged -
   re-measure it), `rejected` (no beam, aborted/truncated scan, I0 or
   detector dropout - check the beam and re-measure). An **evolving series**
   (reps change systematically with time) means damage or chemistry, not
   noise: check for damage before adding reps; the merge is then a time
   average. Reps are energy-aligned only when a rigid shift explains the
   differences.
2. **Merge** the good reps.
3. **Normalize:** pre-edge line and post-edge curve fit, E0 found, edge
   step set to 1 -> normalized XANES.
4. **Background (mu0) removal** with AUTOBK -> chi(k), k from
   E = E0 + k^2/0.2625 (k in 1/A).
5. **Fourier transform** of k-weighted chi(k) over a noise-limited k window
   -> |chi(R)|.

## What the outputs mean

- **Verdict:** `ok`, `caution` (weak edge, low SNR - chi/sigma < 3 in the FT
  window, noise-limited k, evolving series, sweeps disagree, first peak near
  R_bkg), or `suspect` (do not use the numbers: no sample edge / reference
  channel, E0 > 25 eV above or > 10 eV below tabulated - wrong edge or
  calibration, implausible chi amplitude, unstable background, AUTOBK not
  converged). Info flags (single sweep, short k range, few independent
  points) describe the measurement, not a problem. Always read the warnings
  (truncation before a neighbouring edge, glitches removed, I0 step at the
  edge, foil offset).
- **E0, edge step:** the edge position (compare with tabulated / the foil)
  and absorption jump.
- **chi(k):** should oscillate about zero, with a noise band much narrower
  than the signal across most of the FT window.
- **Noise-limited k_max:** where chi(k) becomes noise dominated. If it is
  below your target and still rising with each rep, more reps pay; if it has
  stopped moving over the last 2-3 reps, more reps at this dwell will not
  extend it - use a longer high-k count time instead (kscan `ksec2`).
  chi SNR should grow roughly as sqrt(n).
- **|chi(R)|:** small below R_bkg; first peak plausible for the sample
  (metal-O ~1.4-1.7 A, metal-metal or metal-S/Cl ~2.0-2.8 A). These are
  **apparent distances, not phase corrected** (real bond lengths are
  ~0.3-0.5 A longer).
- A good summary figure: normalized reps overlay; mu0 smooth through the
  oscillations; chi(k) about zero; clean first-shell FT peak that sharpens as
  reps are added. A monotonic chi amplitude decay across reps is damage, not
  statistics.

## Limits

- Thresholds were tuned on BL 4-3 fluorescence data; BL4-1 transmission and
  PIPS paths are less exercised - treat them as guidance.
- No self-absorption correction and no FEFF fitting: for structural
  parameters, fit the merged chi(k) yourself (e.g. Larch / Athena-Artemis).
- PIPS (current mode) noise is estimated from the data, not Poisson counts.
