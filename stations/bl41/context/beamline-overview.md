<!-- Condensed from: /usr/local/lib/spec.d/41_spec/{CLAUDE.md,site.mac,mono.mac,theta.mac,set_limits.mac,check_beam.mac,offset_subtraction.mac,set_user_dir.mac,logfile.mac,xsp32.mac,ctcscan.mac}, /usr/local/projects/cherfd_claude/{cscan_ui/README.md,confs/bl41_config.py}, /usr/local/projects/autonomous_fourone/{config/bl41_station.json,config/defaults.yaml,docs/app-user-guide.md}, 2026-10-17 -->

# BL4-1 Beamline Overview

## What BL4-1 is

SSRL Beamline 4-1 is a **wiggler** X-ray absorption spectroscopy beamline (XANES and EXAFS).
Three signals are measured at once on every scan:

- **Transmission** through the sample (I0 before, I1 after the sample)
- **Fluorescence** from the sample (24-element Ge detector, or the PIPS diode)
- **Reference foil** in transmission between I1 and I2, for energy calibration

There is no undulator, no HERFD/XES emission spectrometer, no Vortex detector and no
attenuator filter set at BL4-1. Control software is SPEC; continuous (on-the-fly) energy
scans run through a separate Python app (cscan, see below).

## Energy range and monochromator

Double-crystal Si monochromator (no fixed exit; the beam height changes slightly with energy).
`mono` (eV) is a pseudo-motor over the Bragg angle motor `crystal` (degrees, travel 5.5-39.5 deg).
E = 12398.4244 x sqrt(h^2+k^2+l^2) / (2 x 5.43102 x sin(theta)).

| Crystal set | Reflection | Approx. energy reach over 5.5-39.5 deg | Notes |
|---|---|---|---|
| A | Si(220) | ~5076-33680 eV | Better resolution; cannot reach below ~5.1 keV |
| B | Si(111) | ~3108-20630 eV | Use for edges below ~5.1 keV (e.g. Ti K) |

- Working range offered for user experiments: about **4500-24000 eV**. `calibrate_mono`
  accepts 4500-25000 eV.
- **Which set is in use:** SPEC `get_crystal` prints it; the software setting is stored in
  `/usr/local/lib/spec.d/mono.cfg` (one letter, `A` or `B`) and is re-applied at every SPEC start.
  The cscan UI header also shows the crystal. The software setting must match the crystal set
  physically in the beam; changing sets is a staff job (`set_crystal A|B` plus a hardware change).
- The encoder offset (energy calibration) is stored separately for set A and set B.

## Detectors and counters

All counters are recorded in every SPEC scan.

| Counter | Meaning |
|---|---|
| `sec` | Count time (master timer; column `Seconds` in data files) |
| `I0` | Incident-beam ion chamber |
| `I1` | Ion chamber after the sample (transmission) |
| `I2` | Ion chamber after the reference foil |
| `pips` | PIPS diode, total fluorescence yield (no energy discrimination) |
| `bgI0`, `bgI1`, `bgI2`, `bgpips` | Same channels with the stored dark rate x count time subtracted |
| `xsum` | Ge detector: sum of the good elements (ROI counts, photons) |
| `xsA`, `xsB` | Ge detector: good elements of group A / group B |
| `xs01`-`xs32` | Ge detector: one element each (with the 24-element detector, xs25-xs32 read 0) |
| `absev` | Mono energy (eV) from the crystal encoder: **the energy axis to use** |
| `eth` | Bragg angle (deg) from the encoder |
| `monoenc` | Raw encoder ticks |
| `spear` | SPEAR ring current (mA) |
| `i0gain i1gain i2gain pipgain` | SR570 amplifier sensitivity at count time (A/V) |
| `i0offs i1offs i2offs pipoffs` | SR570 offset current at count time (A, signed) |
| `mod*` | Modulated-excitation counters (normally disabled) |

- **Ion chambers / PIPS** read through SR570 current amplifiers into V-to-F converters
  (about 1e5 counts/s per volt). Good working window: roughly 3e4-3.5e5 counts/s
  (0.3-3.5 V); above ~4.5 V the SR570 saturates. Gas fill and HV of I0/I1/I2 are set with the
  Gas mixer web app (staff).
- **Ge detector:** the installed one is the **24-element Ge (Xspress3)**. Counts are already
  dead-time corrected by the Xspress; ROIs, groups A/B and bad elements are configured in the
  detector web GUI (staff). xsum = 0 usually means the detector server or setup needs staff.
- Counting is done by the "cscan box" timer: **maximum count time 67 s per point**; preset
  on monitor counts (`mcount`) is not available.
- `bg*` counters are only correct if dark offsets were measured after the last gain/offset change.

## Which signal to use

| Mode | Signal |
|---|---|
| Transmission | mu(E) = ln(I0/I1) |
| Fluorescence (Ge) | xsum / I0 (or xsA/I0, xsB/I0) |
| Fluorescence (PIPS, TFY) | pips / I0 |
| Reference foil | ln(I1/I2) |

Energy axis: `absev` in SPEC files. Prefer `bgI0`/`bgI1`/`bgI2` for quantitative ratios when the
darks are current.

**Telling the experiment mode from data:** every scan records every counter, so the presence of
an `xsum` or `I1` column does **not** say whether the experiment is transmission or fluorescence.
Ask the user, look at the experiment configuration, or compare signal sizes (e.g. a clear edge
step in xsum/I0 vs. in ln(I0/I1)). The scan command in the `#S` line says what kind of scan it
was: a `gscan mono ...`/`kscan ...`/continuous sweep is a spectrum; `ascan`/`dscan` on `Sx`, `Sz`,
slits, table or pitch is alignment; a short `dscan mono` around a foil edge is calibration.

## Sample environments

- Room temperature / ambient on the sample stage (`Sx` horizontal, `Sz` vertical)
- Cryostat (holder type available; there is no temperature readout macro in BL4-1 SPEC)
- Operando cells / gas: arranged with staff
- Reference foil on its own stage (`foilhor`, `foilver`) between I1 and I2

## Beam requirements

- SPEAR current must be above **200 mA** and the beamline state (`BL04:State`) **Open**.
- `check_beam_on` makes SPEC pause at the start of each scan while beam is down (checks every
  10 s, resumes automatically). It is off when SPEC starts; `check_beam_off` disables it.
- A fast shutter (Galil output) can open only during counting (`fson`) to limit dose.
- Wall-screen Beam monitor app (port 5014) shows beamline state, SPEAR current, I0/I1/I2/pips
  volts and mono energy live.

## Data directories and files

- Experiment directory: **`/fourone/YYYY-MM_Name`** on the beamline computer's local disk,
  selected in SPEC with `set_user_dir("YYYY-MM_Name")` (created if missing; normally staff do this).
- `/fourone` is copied **hourly** to the fileserver at **`/data/fourone`** (rsync, nothing deleted).
- SPEC data files: `newfile <name>` opens a file in the current directory; one file per sample is
  the convention, plus `alignment` (alignment scans; `naa` is a shortcut) and
  `energy_calibration`. Reopening a file continues its scan numbering.
- SPEC file format: header `#F #E #D #C #O`, then per scan `#S n <command>`, `#D`, `#P` (motor
  positions), `#N`, `#L` (column labels), data rows.
- Continuous scans (cscan app) save per sweep pickles in the chosen directory under `/fourone`:
  `scan_results_<fileroot>_<sweep>_<fwd|rev>_<timestamp>_dataframe.pkl`. A stopped scan's partial
  frames go under `/fourone/partial/`. Optional SPEC export (switch in the cscan Data path card,
  off by default): `/fourone/specformat/<directory>/<pickle name>.spec`, readable by PyMca.
- SPEC session logs (everything typed and printed):
  `/usr/local/lib/spec.log/logfiles/log_<USER>_<MM-DD-YYYY>`.
