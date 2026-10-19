<!-- Condensed from: /usr/local/projects/autonomous_user/docs/glossary.md, /usr/local/projects/autonomous_fourone/config/{defaults.yaml,bl41_station.json}, /usr/local/projects/xspress_32element/README.md, /usr/local/projects/cscan_acq/README.md, /usr/local/projects/beamtimehero_cli/src/beamtimehero_cli/station.py, 2026-10-17 -->
# BL4-1 glossary

SSRL Beamline 4-1 is a **wiggler** X-ray absorption (XAS / EXAFS) station: X-rays
from SPEAR pass the monochromator, the JJ slits, the ion chambers and the sample.

## Detectors and signals

- **I0, I1, I2** - gas ion chambers measuring beam intensity as a current. I0 before
  the sample (incident), I1 after the sample (transmitted), I2 after the reference
  foil (foil sits between I1 and I2). Transmission = `ln(I0/I1)`; reference foil =
  `ln(I1/I2)`.
- **pips** - PIPS photodiode, a simple fluorescence detector; also read via an SR570.
- **Ge detector, xsum, xsA, xsB, xsNN** - the 24-element germanium fluorescence
  detector (Xspress3 electronics). `xsum` = sum of good elements, `xsA`/`xsB` = group
  sums, `xs01`..`xs24` = single elements. Software is named "xsp32" for historical
  reasons.
- **ROI** - region of interest: the energy window each Ge element counts (set on the
  emission line).
- **Dead element** - a Ge element marked bad, excluded from all sums.
- **Dead time** - time the detector is busy and misses photons; corrected in
  hardware (DTC), unreliable at high rates (> ~200 kcps per element).
- **Fluorescence** - counter / I0 (e.g. `xsum/I0`).
- **Signal detector** - I1 in transmission, the Ge (or pips) in fluorescence.
- **SR570, gain / sensitivity** - current amplifier per ion chamber and pips.
  Sensitivity (e.g. `2 uA/V`) = amps per volt out; smaller = more gain.
- **V/F, linear window** - amp voltage is turned into counts at 1 V = 100 000 cps;
  linear 0.3-3.5 V = 3e4-3.5e5 cps.
- **Darks (dark offsets)** - counts with no beam, measured and subtracted
  (`bgI0`, `bgI1`, `bgI2`, `bgpips`). Re-measure after any gain change; I0's dark
  needs the slits closed.
- **i0gain, i0offs ...** - SPEC columns recording each amp's gain (A/V) and offset
  (A) at every point.
- **plotselect** - which counter SPEC plots live (and uses for `cen`/`peak`).
- **Shutter, fsopen / fsclose** - the shutter before the sample; held open with
  `fsopen; fsoff`, closed with `fsclose`. No fast shutter here: SPEC refuses `fson`.

## Energy and monochromator

- **Mono** - double-crystal silicon monochromator; energy moved with `mono` (eV).
- **Crystal set A / B** - A = Si(220), ~5.1-33.7 keV; B = Si(111), ~3.1-20.6 keV
  (needed below ~5.1 keV, e.g. Ti K). Chosen by staff (`set_crystal`).
- **Pitch, detune, harmonics** - the second crystal is peaked on I0 then detuned
  (I0 drops ~25 %) to suppress harmonics (2x, 3x energy). Done ~1000 eV above the
  edge.
- **E0, edge** - absorption edge position, taken as the maximum of the derivative
  (e.g. Cu K 8979.0 eV).
- **Edge step / edge jump** - size of the absorption jump across the edge.
  Fluorescence: ratio (F/I0 above) / (F/I0 below), >= 1.2 counts as clear.
  Transmission: change in `ln(I0/I1)`, about 0.05-3.0 usable (above 3 the sample is
  too thick).
- **White line** - strong peak just above the edge (L3 edges especially).
- **Foil calibration** - a metal foil of known edge energy is scanned; if off by
  > 0.3 eV the mono is recalibrated (`calibrate_mono`), once per beamtime.
- **absev** - energy from the mono's angle encoder, recorded every point; use it as
  the energy axis.
- **k, k max** - photoelectron wavenumber (1/A): E - E0 = k^2 / 0.2625 eV. k max is
  how far the EXAFS scan goes (e.g. 12-14).
- **XANES / EXAFS** - near-edge region / oscillations far above the edge.

## Beam and positions

- **SPEAR current** - ring current, ~500 mA nominal.
- **BL04:State** - beamline state (Open, Moving, Closed, Fault).
- **Wiggler** - the insertion device feeding BL4-1; there is no undulator gap to
  manage.
- **JJ slits, jjvgap / jjhgap** - beam-defining slits before I0 (mm; `jjvgap -1` =
  closed). Presets: open_start 2 x 3, calibration 0.5 x 3, alignment 1 x 1,
  collection 1 x sample width (max 10).
- **Table, Tz / Tx** - table holding ion chambers and sample stage; height and
  horizontal. Re-centred after large energy changes.
- **Sx / Sz** - sample stage horizontal (20-60.5 mm) / vertical (0-72 mm).
- **Fresh spot** - new position on the same sample, at least two beam sizes away.

## Scans and counting

- **ct** - a single SPEC count (max 67 s per count at BL4-1).
- **ascan / dscan** - absolute / relative motor scans.
- **gscan** - XANES energy scan in regions (fine steps across the edge).
- **kscan** - EXAFS scan: eV regions then even k steps, count time growing with k.
- **cscan, cscan box** - continuous scanning: the mono sweeps through the edge
  without stopping while data are recorded on the fly. Live at BL4-1 via a
  dedicated Python app; the default scan mode, with step scans also available. The
  **cscan box** (`BL41:SCAN:MASTER`) is the FPGA counter/timer: it counts the V/F
  pulses (I0, I1, I2, pips), reads the amp voltages on ADC1-4 and gates the Ge
  detector (one Xspress frame per count).
- **CHERFD, sweep** - the continuous-scan server; one sweep = one repetition.
- **Rep** - one repetition of a scan; reps are averaged.
- **Frame reset** - ~2 s Ge detector restart when its 16384-frame buffer fills;
  normal in long scans.
