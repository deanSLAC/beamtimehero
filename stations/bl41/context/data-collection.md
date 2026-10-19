<!-- Condensed from: autonomous_fourone/.claude/skills/sample-data-collection/SKILL.md, autonomous_microagents/refdocs/{sample-data-collection,user-reference}.md, autonomous_fourone/config/defaults.yaml, cherfd_claude/cscan_ui/README.md, cherfd_claude/CLAUDE.md, BL4-1_Web/services.json, 41_spec/{gscan,kscan,offset_subtraction,shutter,check_beam}.mac, 2026-10-17 -->

# Collecting XANES / EXAFS at BL4-1

## Before every sample

- The beamline is configured and calibrated for the edge
  (`changing-energy`, `energy-calibration`) and the sample is aligned, with
  known Sx/Sz bounds (`sample-alignment`).
- **Shutter in auto mode:** `fson` (opens only while counting - limits dose).
- **Pause on beam loss:** `check_beam_on` (step scans pause at scan start if
  SPEAR < 200 mA or BL4 is closed, and resume when the beam is back).
- **One data file per sample:** `newfile <sample_name>` (spaces and `/` as
  `_`).
- Move to a spot **inside the aligned bounds**: `umv Sx <x> Sz <z>`.

## Transmission or fluorescence?

| Choose | When |
|---|---|
| **Transmission** (ln(I0/I1)) | concentrated, uniform samples (foils, pellets of neat or diluted powder) with an edge step Delta(mu x) of roughly 0.1-2; BL4-1 checks: change in ln(I0/I1) across the edge **at least 0.05**, **at most 3** (too thick) |
| **Fluorescence, 24-element Ge** (`xsum`/I0, groups `xsA`, `xsB`) | dilute samples, thin films, thick or non-uniform samples; energy-resolved (ROI on the emission line); check: (F/I0 above edge) / (below) **at least 1.2** |
| **Fluorescence, PIPS diode** (`pips`/I0, TFY) | quick total-yield checks; no energy discrimination (scatter adds background), no dead time |

The foil reference ln(I1/I2) is recorded with every scan regardless.

## Count-rate linear window

I0, I1, I2 and pips read through SR570 amplifiers into a V-to-F converter:
keep every channel between **3e4 and 3.5e5 counts/s** (0.3-3.5 V;
1e5 cps = 1 V) at all energies of the scan (check `ct 1` below and above the
edge). Above 4.5e5 cps the SR570 is near overload. Gains: `wsrs` to show,
`set_i0_gain("2 uA/V")` etc. to change, one step at a time.

## Darks (offset subtraction)

The `bgI0 bgI1 bgI2 bgpips` columns are the raw counts minus the stored dark
rate x count time. **Re-measure darks after every gain change** (and every
~2 h).

```
measure_offsets      # prompts: x-rays off / hutch lights off, then y; holds the shutter closed and counts
```

The shutter is **downstream of I0**, so it blocks I1/I2/pips but not I0. For
a true I0 dark the slit must be closed (jjvgap -1) during the count and
reopened afterwards - ask staff.

## Continuous scans (default)

Continuous scanning is the BL4-1 default. It runs from the **cscan** web
app (Continuous scanning > cscan, port 5013; documentation page linked
there), not from the SPEC prompt. SPEC stays idle during a sweep.

1. Choose the **technique**: Transmission, TFY (PIPS), or Ge detector.
2. Set the **data path** (directory and file root). Optionally tick "Also
   write a SPEC file after each scan" (for PyMca).
3. Enter the command: `cscan start end speed [end speed] ... freq`
   - energies in eV, all increasing (one direction per command);
   - `speed` = fraction of full speed per region, **0.2-1** (slower = more
     points per eV - use the slow speed across the edge);
   - `freq` = trigger rate, **20-500 Hz** (sets the point spacing); with the
     **Ge detector at most 80 Hz** and 16384 points per sweep.
   - Example, Fe K: `cscan 7062 7102 1 7132 0.2 7312 0.6 50`
4. Set **Sweeps** and optionally **Include reverse** (back-and-forth
   sweeps). **One sweep = one rep.**
5. **Start scan**; **Stop** halts the mono within ~0.5 s and saves the
   partial sweep.

Notes: the crystal drive has ~2 eV (at 7.1 keV) of slack at the start of a
sweep that reverses direction; the energy axis comes from the encoder, so it
stays right.

**Important: table tracking is explicitly disabled throughout the cscan app**
(the table never moves during a sweep). Before cscan is ever run *with* the
table, staff must first update the table's anchored position (the stored
anchor energy/height); the current anchor is not valid for BL4-1. Users
cannot enable table tracking.

## Step scans (SPEC)

**XANES - `gscan`** (absolute eV, regions of different step, one count
time):

```
gscan mono start end1 step1 [end2 step2 ...] sec
gscan mono 7062 7092 5 7107 1 7127 0.25 7162 1 7312 3 1     # Fe K, 1 s/point
```

Default grid relative to E0: E0-50 to -20 at 5 eV; -20 to -5 at 1 eV;
-5 to +15 at 0.25 eV; +15 to +50 at 1 eV; +50 to +200 at 3 eV.

**EXAFS - `kscan`** (eV regions, then a k region with count time ramping
quadratically in k from ksec1 to ksec2):

```
kscan start0 step1 sec1 end1 [step2 sec2 end2 ...] E0 k1 kstep k2 ksec1 ksec2 kweight
kscan 6992 5 1 7092 0.5 1 7142  7112 3 0.05 12 1 10 2       # Fe K to k = 12
```

All eV values are absolute (kscan does not add E0); k uses
E = E0 + k^2/0.2625, so start k1 just past the last eV point (k = 3 is
E0 + 34 eV). Longer `ksec2` buys signal at high k where chi(k) decays.

**Count time cap: no point may count longer than 67 s.**

## How many reps

- Take **at least 2 identical reps on one spot** first - the pair is the
  beam-damage test (`data-quality`).
- Then repeat until the feature you will publish (white line, pre-edge,
  edge position, or chi(k) to your k_max) stops improving - see
  `data-quality` for the convergence criteria. Noise falls as 1/sqrt(n).
- Every ~2 reps compare the latest pair for damage. Damage: move to a fresh
  spot (~2 beam widths in Sx, inside the bounds) and/or halve the count time
  (continuous: fewer sweeps per spot).
- Same file and same grid for all reps of a sample; spot changes are
  recorded in the scan headers through the motor positions.

## Your files

- Step scans: SPEC files, one `#S` block per scan, in the session data
  directory (`/fourone/YYYY-MM_NAME`, copied hourly to `/data/fourone/`).
- Continuous sweeps: per-sweep result files under the cscan data root
  (optionally a SPEC file per sweep in `<directory>/specformat_cscans/`).
- Use the **`absev`** column as the energy axis.
