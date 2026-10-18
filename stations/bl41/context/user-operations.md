<!-- Condensed from: /usr/local/projects/autonomous_fourone/{docs/app-user-guide.md,.claude/skills/user-reference/SKILL.md,config/defaults.yaml}, /usr/local/projects/autonomous_microagents/refdocs/user-reference.md, /usr/local/projects/cherfd_claude/cscan_ui/README.md, /usr/local/projects/BL4-1_Web/services.json, /usr/local/lib/spec.d/41_spec/{CLAUDE.md,set_user_dir.mac,check_beam.mac,offset_subtraction.mac}, 2026-10-17 -->

# A User Session at BL4-1

## 1. Arrival and setup (with staff)

- Staff set the data directory: `set_user_dir("YYYY-MM_Name")` -> `/fourone/YYYY-MM_Name`.
  Everything there is copied hourly to `/data/fourone/YYYY-MM_Name` on the fileserver.
- Check SPEC is in that directory (`pwd`) and has a file open (`p DATAFILE`); open one per
  sample with `newfile <sample>`, and `naa` for alignment scans.
- Confirm the crystal set (`get_crystal`): set A Si(220) for ~5.1 keV and up, set B Si(111)
  needed below ~5.1 keV. A crystal change is a staff job.
- `check_beam_on` so scans wait out beam dumps (SPEAR < 200 mA or beamline closed).

## 2. Energy change to the edge

- `umv mono <eV>` (a little above the edge for alignment), then `ct 1` and read `absev`.
- Set amplifier gains so I0, I1, I2 (and pips) sit around 3e4-3.5e5 counts/s on both sides of
  the edge (`wsrs`, `set_i0_gain("...")`, or the SRS current amps web GUI).
- Staff typically peak/detune the mono pitch, set the slits and check the table for a new edge.
- After any gain change, dark offsets need re-measuring (`measure_offsets`, staff; x-rays off).

## 3. Sample alignment

- Typical slit gaps: ~1 mm vertical; horizontal up to the sample width (max ~10 mm).
- Scan the sample stage with the transmission or fluorescence signal plotted:
  `plotselect I1` (or `xsum`), `dscan Sz -3 3 60 0.5`, `cen`; same for `Sx`.
- Put alignment scans in the `alignment` file so sample files hold only spectra.

## 4. Energy calibration on the reference foil

- Foil sits between I1 and I2; signal ln(I1/I2). Once per beamtime per edge (or after a
  crystal change): `dscan mono -15 15 60 0.2` around the tabulated edge, find the inflection,
  move there, `calibrate_mono <tabulated eV>` (staff), re-scan to confirm.
- Because the foil is measured simultaneously in every scan, small drifts can also be corrected
  later in analysis.

## 5. Data collection

**Continuous (default at BL4-1)** - cscan web app, `http://localhost:5013` on the beamline computer:
1. Choose the technique: Transmission (ln(I0/I1)), TFY PIPS (pips/I0), or Ge detector
   (xsum/I0; up to 80 Hz, 16384 points per sweep).
2. Set Data path: directory under `/fourone` and a file root; optionally tick "Also write a
   SPEC file after each scan".
3. Enter the command, e.g. `cscan 7090 7105 .5 7115 .1 7130 1 20` (start, then end/speed pairs
   with speed 0.2-1 of full speed, last number the trigger rate in Hz, 20-500), set Sweeps and
   "Include reverse", Start scan. Energies must all increase (use reverse for down sweeps).
4. Watch the live box readouts and the Scan results panel; Stop ends a sweep cleanly.
Each sweep is saved as `scan_results_<fileroot>_<n>_<fwd|rev>_<time>_dataframe.pkl`.
Statistics come from more sweeps (a sweep cannot slow its counting at high k).

**Step scans (SPEC)** - `gscan mono ...` for XANES, `kscan ...` for EXAFS; `fson` to limit dose;
max 67 s per point.

If the autonomous app (port 5005) or XAS++ / Experimenter Console is in use for the beamtime,
collection is run from there; ask staff which one your beamtime uses.

## 6. Checking data

- Energy axis `absev`; transmission ln(I0/I1), fluorescence xsum/I0, foil ln(I1/I2).
- Every scan records every counter, so the columns do not tell the mode; check with the user.
- Watch for: edge step too small or ln(I0/I1) jump > ~3 (sample too thick), counters
  near saturation, changes between repeats on one spot (beam damage: move to a fresh spot).
- Viewers: CHERFD data processing app (continuous sweeps), PyMca (SPEC files), the data viewers
  of the autonomous / XAS++ apps.

## 7. Finishing

- Close the shutter / stop scans; tell staff when done.
- Data stays in `/fourone/YYYY-MM_Name` and `/data/fourone/YYYY-MM_Name`; staff arrange copying
  it off site (there is no download button on the beamline apps).

## Where to go for what (user-relevant web apps)

| Need | App | URL |
|---|---|---|
| Continuous energy scans | cscan | http://localhost:5013 |
| Live beam / I0 / energy at a glance | Beam monitor | http://localhost:5014 |
| Look at / merge continuous scan data | CHERFD data processing | http://localhost:5009/app |
| Move motors from a browser | Motor mover | http://localhost:8043 |
| Amplifier gains | SRS current amps | http://192.168.41.6:8570 |
| Autonomous run / guided manual run | AI Beamline / XAS++ / Experimenter Console | :5005 / :5018 / :5025 |
| See the beam | Beamline camera | http://192.168.41.91 |

## When to call staff

- Beam down for long, beamline state not Open, or Fault
- Crystal set change, mono pitch, mirror, slits translation or table adjustments
- Energy calibration (`calibrate_mono`) and dark offsets (`measure_offsets`)
- Ge detector reading zero, bad elements, ROI or group changes
- Ion chamber gas or HV changes (Gas mixer app)
- cscan errors (scan refused, stuck "box busy", SPEC `ct` refused after a scan)
- Hutch access, sample mounting, cryostat or gas/operando setups, anything alarming
