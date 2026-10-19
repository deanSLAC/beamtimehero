<!-- Condensed from: /usr/local/lib/spec.d/41_spec/{CLAUDE.md,site.mac,mono.mac,theta.mac,gscan.mac,kscan.mac,shutter.mac,check_beam.mac,offset_subtraction.mac,set_user_dir.mac,srs_set.mac,ctcscan.mac,utilities.mac,set_limits.mac,table.mac,tracking.mac,mono_detune.mac,xsp32.mac}, /usr/local/projects/autonomous_fourone/.claude/skills/spec-reference/SKILL.md, /usr/local/projects/autonomous_microagents/refdocs/spec-reference.md, 2026-10-17 -->

# BL4-1 SPEC Command Reference

Only macros loaded by `41_spec/site.mac` are listed. Commands marked **(staff)** change
beamline setup or calibration; users should ask beamline staff before using them.

## Motors

| Motor | Meaning | Who moves it |
|---|---|---|
| `mono` | Photon energy (eV), pseudo-motor over `crystal` | users |
| `crystal` | Mono Bragg angle (deg), travel 5.5-39.5 | normally via `mono` |
| `Sx` | Sample stage horizontal (mm, limits ~20-60.5) | users |
| `Sz` | Sample stage vertical (mm, limits ~0.5-72) | users |
| `foilhor`, `foilver` | Reference foil stage | users with staff guidance |
| `jjvgap`, `jjhgap`, `jjvtra`, `jjhtra` | Endstation slit S1 gap/translation (pseudo over `topjaw1 botjaw1 sprjaw1 srljaw1`) | gaps: users with staff guidance; translations staff |
| `Dx`, `digvert` | Detector stages | staff |
| `solx`, `solz` | Solenoid stages | staff |
| `Tz`, `Tp`, `Tx` | Table height/pitch (pseudo over `Tz1`,`Tz2`), transverse | staff (the `Tz`/`Tp` pseudo device is currently switched off) |
| `pitcha`, `rolla`, `pitchb`, `rollb`, `monab` | Mono 2nd-crystal stages (raw steps) | staff |
| `monvgap`, `monvtra`, `montopj`, `monbotj` | Mono slits | staff |
| `m0vert`, `m0pitch`, `m0topj`, `m0botj`, `m0bend`, `m0vgap`, `m0vtra` | M0 mirror and its jaws/bender | staff |
| `girder`, `bmpipe`, `diag` | Girder, beampipe, diagnostic | staff |
| `em0topj` ... `erollb` | LVDT voltages (read-only) | none |

## Moving and checking positions

| Command | Meaning |
|---|---|
| `wa` | Show all motor positions |
| `wm Sx Sz mono` | Show selected motors |
| `wsamp` | Show sample stage (`wm Sx Sz`) |
| `umv mono 7112` | Absolute move with live position display |
| `umvr Sz 0.5` | Relative move with live display |
| `mv` / `mvr` | Same without live display |
| `lm` | Show soft limits |

## Counting

| Command | Meaning |
|---|---|
| `ct 1` | Count 1 s and print all counters (max **67 s**) |
| `plotselect xsum` | Choose the counter plotted during scans (set before the scan) |

`mcount` (preset on monitor) is not available. `ct` is refused while a continuous scan is
using the cscan box; wait for the sweep to finish.

## Step scans

All energies are **absolute eV**. Count time per point at most 67 s.

| Command | Syntax |
|---|---|
| `ascan` | `ascan motor start end intervals sec` |
| `dscan` | `dscan motor rel_start rel_end intervals sec` (returns to start position afterwards) |
| `gscan` | `gscan motor start end1 step1 [end2 step2 ...] sec` |
| `kscan` | `kscan start step1 sec1 end1 [step2 sec2 end2 ...] E0 k1 kstep k2 ksec1 ksec2 kweight` |

Examples:

```
dscan Sz -2 2 40 0.5             # vertical sample-stage scan, 41 points, 0.5 s
dscan mono -15 15 60 0.2         # around a foil edge
gscan mono 6540 6542 1 6550 0.2 6570 1 6620 5 1
#   6540-6542 in 1 eV, 6542-6550 in 0.2 eV, to 6570 in 1 eV, to 6620 in 5 eV; 1 s per point
kscan 6738 0.5 1 6746 0.1 1 6756 0.5 1 6760 6749 1.75 0.05 11.0 1 12 2
#   eV regions (step, sec, end), then k = 1.75-11.0 A^-1 in 0.05 steps above E0 = 6749,
#   count time ramping 1 s -> 12 s
```

Notes:
- `gscan`: pairs are (end, step); one count time for the whole scan (last argument).
- `kscan`: always scans `mono`. eV regions are (step, sec, end) triples, the reverse order of
  gscan. k grid: E = E0 + k^2/0.2625. Count time ramps quadratically from ksec1 to ksec2; the
  `kweight` argument is accepted but not used (pass 2).
- Grids are capped at 1024 points.
- After a scan: `cen` / `peak` move to the centre / peak of the plotted counter; `optcen` is a
  robust centre (centre of mass unless the peak is asymmetric).

## Mono and energy

| Command | Meaning |
|---|---|
| `umv mono <eV>` | Change energy (the only energy move; no `energy` or `absenergy` macro at BL4-1) |
| `ct 1`, read `absev` | Check where the mono actually is (encoder energy) |
| `get_crystal` | Show crystal set: A = Si(220), B = Si(111), and d-spacing |
| `set_crystal A\|B` | **(staff)** Switch the mono energy calculation to set A or B (writes `mono.cfg`) |
| `calibrate_mono <eV>` | **(staff)** With the mono at the measured foil-edge inflection: redefine `mono` to the tabulated edge energy and store the encoder offset for the current set (4500-25000 eV) |
| `set_theta <deg>`, `print_theta` | **(staff)** Encoder offset; print raw encoder and theta |
| `peak_mono_pitch`, `mono_detune(25)` | **(staff)** Peak the 2nd-crystal pitch on I0; peak then detune until I0 is down 25 % (harmonic rejection) |
| `tracking 1\|0`, `get_tracking`, `wtrack` | **(staff)** Table height tracking with energy (off at load) |

Energy calibration routine (with staff): park the mono at the tabulated foil edge, `dscan mono -15
15 60 0.2` on the foil signal ln(I1/I2), find the inflection, move there, `calibrate_mono
<tabulated>`, re-scan to confirm.

## Shutter

| Command | Meaning |
|---|---|
| `fsopen` / `fsclose` | Open / close the fast shutter |
| `fsoff` | Leave auto mode (shutter state unchanged) |
| `fson` | Refused at BL4-1 (no fast shutter) |

Hold the shutter open for counting with `fsopen; fsoff`.

## Beam check

| Command | Meaning |
|---|---|
| `check_beam_on` | Pause at the start of each scan while SPEAR < 200 mA or the beamline is not Open; resume automatically |
| `check_beam_off` | Disable that check (it is off when SPEC starts) |
| `p beam_status()` | Print SPEAR current and beamline state |

A scan also pauses while the file `/usr/local/projects/spec_scripts/pause` exists (desktop
"resume" shortcut removes it).

## Dark offsets

| Command | Meaning |
|---|---|
| `measure_offsets` | **(staff)** Interactive: asks for x-rays and hutch lights off, holds the shutter closed, counts once and stores dark rates for I0/I1/I2/pips |
| `bgI0 bgI1 bgI2 bgpips` | Counters with dark rate x `sec` subtracted |

Re-measure after any amplifier gain or offset change, or the `bg*` values are wrong.

## Amplifier gains (SR570)

| Command | Meaning |
|---|---|
| `wsrs` | Show gain and offset of i0, i1, i2, pips |
| `set_i0_gain("50 nA/V")` | Set sensitivity; also `set_i1_gain`, `set_i2_gain`, `set_pips_gain` |
| `set_i0_offset("-2 nA")` | Set offset current; also `_i1_`, `_i2_`, `_pips_` forms |
| `srs_set("i1", "gain", "200 nA/V")` | Generic form |

Strings must match exactly: sensitivities 1/2/5 x 10^n from `1 pA/V` to `500 uA/V`, plus `1 mA/V`;
offsets `1 pA` to `5 mA` with optional `-`. Smaller A/V = more amplification. Aim for
3e4-3.5e5 counts/s on each channel. The amps can also be set from the SRS current amps web GUI.
Readbacks are recorded in every scan (`i0gain` ... `pipoffs`).

## Data files and directories

| Command | Meaning |
|---|---|
| `set_user_dir("2026-10_Smith")` | Go to (and create) `/fourone/2026-10_Smith`; a full path is used as given (normally staff) |
| `newfile <name>` | Open or reopen a data file in the current directory; scan numbers continue |
| `naa` | `newfile alignment` |
| `p DATAFILE`, `p SCAN_N`, `pwd` | Current file, last scan number, current directory |

## Ge detector (Xspress)

`xsp`, `xsp_status`, `xsp_show` show the detector state. ROI, group, bad-element and setup
commands (`xsp_roi`, `xsp_group`, `xsp_bad`, `xsp_good`, `xsp_setup`, `xsp enable|disable`) are
**(staff)**; the detector web GUI does the same.

## Continuous scans

There is no SPEC command for continuous scans at BL4-1 (the old `cherfd.mac` is intentionally not
loaded). Continuous energy scans are run from the **cscan** web app (port 5013), command form
`cscan start end speed [end speed ...] freq`. While a sweep runs, SPEC counting and moves of the
mono must wait. `csct_release` **(staff)** clears the box after a crashed scan.
