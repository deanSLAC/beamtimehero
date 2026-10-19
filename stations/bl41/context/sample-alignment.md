<!-- Condensed from: autonomous_fourone/.claude/skills/sample-alignment/SKILL.md, autonomous_microagents/refdocs/sample-alignment.md, autonomous_fourone/config/defaults.yaml, 41_spec/{shutter,offset_subtraction,srs_set,xsp32}.mac, 2026-10-17 -->

# Sample alignment at BL4-1

The goal: for every sample on the holder, find its usable extent in **Sx**
(horizontal) and **Sz** (vertical) and its centre, so data collection can
move to each sample and to fresh spots inside known bounds.

## Safety and ground rules

- **Move only the sample stage (Sx, Sz), the mono energy, the shutter and the
  amplifier gains.** The table (Tz, Tx), mono pitch, slit translations
  (jjvtra/jjhtra, always 0) and upstream optics are staff-set. Ask staff
  before changing slit gaps.
- Stage limits: **Sx 20 to 60.5 mm, Sz 0 to 72 mm.** Keep scans inside them.
- **Keep dose low:** short count times (0.2-0.3 s). Alignment should not use
  up the sample's damage budget.
- The beamline must already be configured for this edge (see
  `changing-energy`). Alignment does not change the table or pitch.

## What signal to align on

| Detection | Signal | What the sample looks like |
|---|---|---|
| Transmission | `I1` | a **dip** in I1 where the sample absorbs |
| Fluorescence (Ge) | `xsum` (24-element Ge, Xspress) | a **rise / plateau** on the sample |
| Fluorescence (PIPS diode) | `pips` | a rise / plateau on the sample |

For the Ge detector, the ROI must cover the element's emission line first
(`xsp_show` to check; `xsp_roie A <lo_eV> <hi_eV>`, or the detector web GUI;
ask staff if unsure).

## Setup (once per holder)

1. Open the alignment data file so alignment scans stay out of your sample
   files: `newfile alignment`
2. Move ~300 eV **above the edge** so the sample absorbs/fluoresces strongly,
   e.g. Fe K (7112 eV): `umv mono 7412`
3. Check counts: `ct 1`. I0, I1, I2 and pips should read inside the linear
   window **3e4-3.5e5 counts/s** (0.3-3.5 V on the V/F; 1e5 cps = 1 V).
   Show gains with `wsrs`; change one step at a time, e.g.
   `set_i1_gain("100 nA/V")`. After any gain change, re-measure the darks
   (see `data-collection`).
4. Hold the shutter open: `fsopen; fsoff` (no fast shutter here; SPEC refuses `fson`)
5. Select the plotted counter, which `cen`/`peak` act on:
   `plotselect I1` (transmission) or `plotselect xsum` / `plotselect pips`.
6. Slits for alignment are normally 1 x 1 mm (jjvgap 1, jjhgap 1) - staff set
   or approve this.

## Coarse survey of the holder

One long Sz scan to see every sample at once (about 0.25 mm per point):

```
dscan Sz -10 20 60 0.3        # relative to the current position
ascan Sz 5 45 160 0.3         # or absolute, around where the samples are
```

Read the plot: transmission dips (or fluorescence plateaus) separated by the
holder frame. Note the approximate Sz of each sample, bottom (lowest Sz)
first. A slot with no feature may be empty, or the sample is too thick at
this energy (I1 near zero everywhere) - check before moving on.

## Per-sample fine alignment

For each sample:

1. Move to its approximate centre: `umv Sz <z>`
2. **Fine Sz scan:** `dscan Sz -3 3 30 0.3`. For a sample of known height h,
   scan +/-(h/2 + 1.5) mm so both edges are inside the scan. Note where the
   signal changes (the dip or plateau edges) as Sz low / high.
3. **Fine Sx scan:** `dscan Sx -5 5 40 0.3` (or +/-(w/2 + 1.5) mm for width
   w). Note Sx low / high.
4. **Move to the centre:** `cen` after a symmetric scan (moves to the
   centre of the FWHM), `peak` to move to the maximum, or `umv Sx <mid>` /
   `umv Sz <mid>` to the midpoint of the edges you noted. Write down the
   bounds: collection spots must stay inside them.
5. **Edge-step and count-rate check** (every sample):
   - Signal gain per sample (rates differ between samples): pips or I1 inside
     3e4-3.5e5 cps at E0 + 50 eV; re-measure darks after a change.
   - Quick edge scan: `umv mono <E0>`, then `dscan mono -30 70 41 0.2`.
     Look for: an edge present, a white line, no flat-topped (saturated)
     peak.
   - `ct 1` at E0 - 50 and at E0 + 50 eV: every channel at least 3e4 cps,
     none above 3.5e5 cps at any energy.
   - Edge step: fluorescence (signal/I0 above) / (below) **at least 1.2**;
     transmission change in ln(I0/I1) across the edge **at least 0.05**
     (above ~3 the sample is too thick).
   - Go back to E0 + 300 eV before the next sample.
6. After the last sample, staff set the **collection slit gaps**: jjvgap 1,
   jjhgap = the narrowest sample width (at most 10 mm), or 1 mm if you ask.
   Recheck `ct 1`: nothing over 3.5e5 cps at the wider gap.

## What good alignment looks like

- **Transmission:** a flat open-beam level with a clear dip over the sample.
  A dip floor near zero means a thick or concentrated sample - fine for
  finding edges, but note it (may be too thick for transmission XAS).
- **Fluorescence:** near zero off the sample, a flat plateau on it.
- **Sharp, symmetric edges** in the fine scans; the centre is well inside the
  sample, not near an edge or the holder frame.
- Less than ~10x contrast at the expected position: widen the scan range
  before concluding the sample is missing.

## Cryostat samples

Re-align (at least the fine Sz scan) after every temperature change: the
cold finger contracts and moves samples a few tenths of a mm, mostly in Sz.
See `cryostat-procedures`.
