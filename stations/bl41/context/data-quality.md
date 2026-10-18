<!-- Condensed from: autonomous_fourone/.claude/skills/{analyze-statistical-convergence,assess-sample-damage,exafs-reduction,cryostat-procedures}/SKILL.md, autonomous_microagents/refdocs/{analyze-statistical-convergence,assess-sample-damage}.md, autonomous_fourone/config/defaults.yaml, 2026-10-17 -->

# Judging data quality at BL4-1

Always compare **edge-step-normalized** spectra (pre-edge -> 0, post-edge
-> 1, signal divided by I0 first) on the `absev` energy axis. Raw counts drift
with SPEAR ring current (~5 mA over a session is normal) and with beam
motion.

## 1. Beam damage / photoreduction

Compare two back-to-back scans on **the same spot** with the same grid, count
time and gains (a stage move or gain change in between invalidates the pair).

| Feature | Damage if | Clean if |
|---|---|---|
| Edge position E0 (half-height) | shift > 0.3 eV suspicious, > 0.5 eV definite | within 0.2 eV |
| White-line height | > ~3 % change, monotonic across reps | within 1-2 % |
| Pre-edge peak height | > ~5 % change on a clearly resolved peak | within 1-2 % |
| Signal/I0 at the white line | drops > 5 % with no SPEAR drop (> 2 %) or gain change | flat within +/-2 % |
| Post-edge baseline (50-100 eV above E0) | - | within 1 % of 1.0 |

- Require **two indicators** before calling damage from one pair - noise
  alone gives false positives. A steady drift of E0 / white line in the
  reducing direction over all reps is photoreduction even when each pair
  looks fine.
- Reduction typically shifts the edge to lower energy and (for Cr(VI),
  V(V), Mn(IV)-type species) drops the white line; oxidation often raises it.
- In between (e.g. 3 % white-line change, no shift, noisy data):
  **inconclusive** - take one more scan on the same spot and compare again.
  Still inconclusive: treat as safe.
- **Damaging:** move to a fresh spot (~2 beam widths in Sx, inside the
  bounds) and halve the count time; re-test with a new pair. Damage on two
  fresh spots in a row: talk to staff (further flux reduction, e.g. more
  detuning, is a staff action).
- Not damage: an E0 "shift" right after a `calibrate_mono`, or between scans
  where `absev` and `mono` disagreed. Short noisy scans can wobble 5-10 % at
  the white line from counting statistics alone.
- Cooling (cryostat) slows damage but does not stop photoreduction.

## 2. When to stop repeating (convergence)

Judge convergence on **the feature you will publish**, in a window around it
(e.g. ~7-10 eV around a 3d K-edge white line, or the pre-edge peak), never on
the whole spectrum - flat normalized regions look converged by construction.

- **Converged:** the standard error of the mean of that feature (peak area
  preferred over peak height) is **< 1 % of its value** (0.5 % for a small
  feature that drives a result), with no monotonic trend across reps, over
  at least 4 reps.
- **Still photon-limited:** the merged noise keeps falling as 1/sqrt(n) -
  more reps help. If the reps needed do not fit the time left, lengthen the
  count time (or accept a looser target) rather than adding many short reps.
- **Stop and diagnose, do not average more**, when:
  - the merged noise stops falling (a systematic floor): spot change,
    damage, sample heterogeneity, detector saturation, or energy drift;
  - the feature drifts monotonically with rep number, or the first and
    second halves of the reps disagree;
  - spots disagree (different chemistry or damage at one spot): the average
    is a population mean; decide with staff whether to keep spots separate.
- Damage can masquerade as convergence (nothing left to change). Check
  damage before trusting an "it stopped changing" signal.
- After a spot move, expect slower convergence; edge-step normalization
  absorbs thickness/concentration differences, not chemistry differences.
- Per-rep wall time growing > 25 % (dead-time creep): re-plan before adding
  reps.
- BL4-1 aims at **publication-quality** data: when in doubt, collect more.

## 3. Glitches

- **Sharp spikes at the same energies in every rep** are monochromator or
  sample (Bragg) glitches. Mono glitches appear in I0 and mostly divide out
  in transmission; check I0 at that energy.
- In cryostat runs, **new** spikes at fixed energies plus a slow drop in I1
  or fluorescence point to **ice** on the windows or sample - ask staff.
- A spike in one rep only: beam/injection event or a dropout - discard or
  re-measure that rep rather than averaging it in.
- Single-point glitches can be removed before merging; do not let them
  dominate an FT.

## 4. Saturation and dead time

- Ion chambers / PIPS: keep **3e4-3.5e5 counts/s** at every energy. A
  flat-topped white line or a signal/I0 that stops scaling is saturation:
  lower the gain one step (then redo darks). Below 3e4 cps: one step more
  sensitive.
- **Ge detector (24-element Xspress):** the sum counters are dead-time
  corrected in the Xspress hardware, but at high rates the correction
  degrades and the noise floor rises. A white line that flattens or an edge
  step lower than expected for a concentrated sample suggests too high a
  rate - reduce the rate (move the detector back / smaller slit; staff)
  rather than collect more reps. Ask staff for the per-element rate limit.
- A saturated counter caps the achievable SNR: more reps will not fix it.

## 5. Edge step guidelines

| Mode | Minimum | Notes |
|---|---|---|
| Transmission, change in ln(I0/I1) | **0.05** | above **3** the sample is too thick (distorted amplitudes); ~0.1-2 is comfortable |
| Fluorescence, (F/I0 above) / (below) | **1.2** | much higher ratios for dilute samples are normal; a concentrated thick sample in fluorescence suffers self-absorption (damped white line / EXAFS) |

A raw edge step that varies from rep to rep means the sample moved or is
inhomogeneous between spots. An edge-position spread > ~0.5 eV across reps:
mono drift or a real chemical shift.
