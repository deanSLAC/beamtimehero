<!-- Condensed from: autonomous_fourone/.claude/skills/energy-calibration/SKILL.md, autonomous_microagents/refdocs/energy-calibration.md, autonomous_fourone/docs/beamline-energy-configuration.md, 41_spec/{theta,mono}.mac, cherfd_claude/CLAUDE.md, 2026-10-17 -->

# Energy calibration with a reference foil at BL4-1

The mono is calibrated by scanning a reference foil's absorption edge,
finding its inflection point, and redefining the mono so that point reads as
the tabulated edge energy. Do it once per beamtime at the start, and again
after any crystal change or if the reference edge drifts.

## Two calibrations, one per app (by design)

SPEC and the cscan app each keep their **own** energy calibration, because
each has its own representation of the mono energy. Each needs its own
calibration run:

| Use | Goes through | Calibrated with |
|---|---|---|
| Manual energy moves, step scans (`gscan`, `kscan`, `ascan mono`) | SPEC | `calibrate_mono` (procedure below); read back in `absev` |
| Monitoring and continuous scans | cscan app | the cscan app's **Calibrate energy** step |

Calibrating one does not calibrate the other. After a crystal change or a
new edge, both need doing if both are used. Manual energy moves are always
submitted through SPEC.

## Before you start

- The beamline is configured for the foil's edge (pitch, table, gains,
  darks: see `changing-energy`).
- Calibration slits: **jjvgap 0.5, jjhgap 3 mm** (vertical gap closed for
  energy resolution). At these gaps check `ct 1` at the edge: I0/I1/I2 inside
  3e4-3.5e5 cps, otherwise re-set gains and darks.
- Pick a foil whose edge is close to your sample's edge (e.g. Pt L3 foil for
  an Ir L3 experiment, Fe foil for Fe K).

## Signal and E0 convention

- The reference foil sits **between I1 and I2**, so its absorption is
  **ln(I1/I2)**, recorded on every scan whatever is at the sample position.
  Use the dark-subtracted counters `bgI1`, `bgI2` for ratios by hand.
- A foil mounted at the sample position instead: ln(I0/I1).
- **E0 = the inflection point = maximum of the first derivative** of the
  absorption edge.
- Assign it to the **unrounded** tabulated value:

| Foil / edge | E0 (eV) |
|---|---|
| Fe K | 7112.0 |
| Cu K | 8979.0 |
| Ir L3 | 11215.2 |
| Pt L3 | 11563.7 |
| Au L3 | 11918.7 (not 11919) |

  Check a primary source (e.g. NIST / Bearden) for other elements.

## Procedure

1. Open a scratch file: `newfile energy_calibration`
2. Move to the tabulated edge: `umv mono 7112.0` (Fe example). `ct 1` and
   read `absev` (encoder energy) to see where it landed.
3. **Edge scan:** `dscan mono -15 15 60 0.2`. Plot ln(I1/I2). No edge in
   view: widen the range.
   - **If the edge is more than 50 eV off, stop** - wrong foil, foil out,
     wrong crystal set, or a crystal change. That needs a staff coarse
     calibration (step 10 eV from 100 eV below the edge watching I2, set the
     midpoint of the edge step, then this procedure).
4. **Find the inflection** (derivative maximum) of ln(I1/I2) and compare
   with the tabulated value.
5. **If |measured - tabulated| > 0.3 eV, apply the calibration:**
   ```
   umv mono <measured_inflection>
   calibrate_mono <tabulated_edge>        # e.g. calibrate_mono 7112.0
   ```
   `calibrate_mono` sets the mono position to the tabulated value and
   updates the crystal encoder offset (for the current crystal set) so the
   current physical angle reads as that energy.
6. **Verify:** repeat the edge scan (finer is fine: `dscan mono -15 15 80
   0.2`) and find the inflection again. Accept within **~0.2 eV** of
   tabulated; otherwise repeat steps 4-5.
7. **Check absev:** after calibration `ct 1` at the edge should show
   `absev` essentially equal to the `mono` position. If they disagree the
   calibration is incomplete - iterate.

## Checking the calibration later

- The foil is in every scan (between I1 and I2): find the ln(I1/I2)
  inflection in any recent scan that covers the foil edge and compare with
  the tabulated value. A shift of more than ~0.3 eV means drift: recalibrate
  before relying on absolute edge positions.
- If the sample and foil edges differ, the foil only checks calibration
  when your scan range covers the foil's edge.
- Continuous (cscan) scans: calibrated separately, with the cscan app's
  **Calibrate energy at the current position** button, which sets the cscan
  app's encoder offset so the encoder reads the mono's current setpoint.
  It does not change SPEC's calibration (see the table above).
- Without a calibration from this beamtime, edge positions are only
  relative (mono offsets are eV-scale, the same size as oxidation-state
  shifts) - do not quote absolute oxidation states.

## Energy axis in your data

Use the **`absev`** column (encoder readback) as the energy axis for
analysis; it is the canonical value. Recalibrating mid-beamtime changes the
axis from that point on: note the scan number where it happened.
