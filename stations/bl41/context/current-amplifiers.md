<!-- Condensed from: /usr/local/projects/ssrl-current-amp/{epics_usage_guide_BL4-1.txt,README.md,config/BL4-1/*_default.json,config/autozero.json}, /usr/local/projects/autonomous_fourone/config/{defaults.yaml,bl41_station.json}, /usr/local/projects/autonomous_user/docs/glossary.md, /usr/local/projects/fourone_monitor/README.md, /usr/local/projects/cherfd_claude/confs/bl41_cscan_box_adc.json, 2026-10-17 -->
# Current amplifiers (SR570) on I0, I1, I2 and PIPS

Each ion chamber (I0, I1, I2) and the PIPS diode feeds an SRS **SR570** current
preamplifier. The amps are controlled by the `ssrl-current-amp` server
(web UI **http://192.168.41.6:8570**, EPICS prefix `Local:BL4-1:`, channels `i0`,
`i1`, `i2`, `pips`), which talks to them over serial via Moxa servers.

## Signal chain

```
ion chamber / PIPS current -> SR570 (gain A/V, offset A) -> voltage
   -> V/F converter (1 V = 100 000 cps) -> cscan box counters -> SPEC I0/I1/I2/pips
   -> also: cscan box ADC1-4 (i0, i1, i2, pips) read the voltage directly
```

- **Sensitivity (gain)**, e.g. `2 uA/V`: amps of input per volt of output. A smaller
  number = more amplification. Options are the 1-2-5 ladder from `1 pA/V` to `1 mA/V`.
- **Offset**: a calibrated input offset current (signed, `1 pA` to `5 mA`) that keeps
  the output positive with no beam.
- **V/F scale**: 1e5 cps per volt of SR570 output.

## Linear window

| Output | cps | Meaning |
|---|---|---|
| < 0.3 V | < 3.0e4 | too low: lower the sensitivity number (more gain) |
| 0.3 - 3.5 V | 3.0e4 - 3.5e5 | **linear window**, aim here |
| > 3.5 V | > 3.5e5 | too high: raise the sensitivity number (less gain) |
| ~4.5 V | ~4.5e5 | treated as saturated by the gain-selection tool |
| ~5 V | | SR570 output overload |

Outside the window counts no longer follow the beam (saturation flattens peaks).
Because flux changes with energy, gains are chosen for the whole scan range
(checked below and above the edge).

## Default gains/offsets (BL4-1)

Same for both crystal sets (Si(220) A and Si(111) B); tuned per experiment:

| Channel | Gain | Offset |
|---|---|---|
| i0 | 2 uA/V | 100 pA |
| i1 | 200 nA/V | 100 pA |
| i2 | 50 nA/V | 1 nA |
| pips | 10 nA/V | 20 pA |

Other default settings (from the server's default files, i0 shown): 6 dB lowpass
filter at 100 Hz, Low Noise gain mode, output inverted, bias off.

## Changing gain (who / how)

Gain and offset changes are writes and are done by staff or the beamline's
automated tools, not by the read-only help agent:
- the ssrl-current-amp web UI (port 8570), per-channel tabs, "Restore Defaults";
- `caput Local:BL4-1:<ch>:SensitivityString "10 nA/V"` /
  `...:OffsetString "-50 nA"`;
- the autonomous tools (`set-amp-gain`, `set-amp-offset`, `set-gains-across-edge`),
  which write through the amp IOC, never via SPEC.

The server sends at most 2 serial commands per second, so a change takes a moment
to apply. **After any gain change, darks must be re-measured.**

## Darks and offsets

- **Darks (dark offsets)**: the counts each detector gives with no beam (amp
  offset + leakage). They are measured per gain and subtracted; the SPEC counters
  `bgI0`, `bgI1`, `bgI2`, `bgpips` are the dark-subtracted values.
- I0's dark needs the **JJ slits closed** (`jjvgap -1`), because the hutch shutter is
  downstream of I0. The automated darks are considered stale after 2 h.
- **Zero Offsets** (button in the amp web UI, staff): sets each amp's offset so its
  cscan box ADC reads the smallest positive voltage (target 0.002 V). Done with the
  shutter closed, about 30 s, skipped while SPEC is counting.

## Readback

| Where | What |
|---|---|
| SPEC counters `i0gain`, `i1gain`, `i2gain`, `pipgain` | gain in A/V (from `Local:BL4-1:<ch>:SensitivityValue`), recorded every point |
| SPEC counters `i0offs`, `i1offs`, `i2offs`, `pipoffs` | offset in A (from `...:OffsetCurrent`) |
| `Local:BL4-1:<ch>:SensitivityString` / `OffsetString` | human-readable, e.g. `2 uA/V`, `-50 nA` |
| `BL41:SCAN:MASTER.ADC1`..`ADC4` | live amp output (i0, i1, i2, pips) as raw offset-binary words; volts = (word - 2^31) / 2^16 / ~3090 |
| fourone_monitor (wall screen, http://127.0.0.1:5014 on bl41lx1) | i0/i1/i2/pips in volts, live plot |

The ADC counts-per-volt (~3090) is a rough calibration (not checked with a DMM);
it is used only for display, and scan data keep counts.

## Quick checks for users

- Count rate in the 3e4-3.5e5 cps range on every channel used (counts divided by count time).
- Transmission: I0 and I1 both in window; fluorescence: I0 in window, Ge rates OK.
- A sudden step in one channel mid-session often means a gain change: compare the
  `*gain` columns across scans.
