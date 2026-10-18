<!-- Condensed from: autonomous_fourone/.claude/skills/changing-energy/SKILL.md, autonomous_fourone/docs/beamline-energy-configuration.md, autonomous_fourone/config/defaults.yaml, 41_spec/{mono,theta,table,peak_mono_pitch,offset_subtraction,srs_set}.mac, 41_spec/CLAUDE.md, 2026-10-17 -->

# Changing energy (moving to a new edge) at BL4-1

BL4-1 is a **wiggler** beamline with a double-crystal monochromator (no
undulator gap to follow). A new edge is more than a mono move: the exit beam
height changes with energy, so the second-crystal pitch and the table must
follow. **An edge change is a staff-supervised procedure.**

## Who does what

| Step | Who |
|---|---|
| Choosing / changing the crystal set (A/B) | **Staff only** (planned per session) |
| Mono pitch tune / detune, table Tz/Tx scans, slit translations | **Staff** |
| Slit gaps (jjvgap, jjhgap) | Staff, or user with staff approval |
| `umv mono`, gains, darks, count checks | User (staff can help) |
| Energy calibration on the foil | User or staff (see `energy-calibration`) |

A plain `umv mono` to a distant edge without the steps below leaves the pitch
and table set for the old energy - the beam can miss the slits and I0, and
counts drop to dark. **Ask staff before changing edge mid-beamtime.**

## Crystal sets

Set with `set_crystal A|B` (staff); show the current one with `get_crystal`.
Both sets use Si a0 = 5.43102 A.

| Set | Crystal | Approx. range (5.5-39.5 deg crystal travel) |
|---|---|---|
| **A** | Si(220) | ~5.1-33.7 keV - covers most edges |
| **B** | Si(111) | ~3.1-20.6 keV - needed below ~5.1 keV (e.g. Ti K) |

`calibrate_mono` accepts 4500-25000 eV. After a crystal change the energy can
be tens of eV off and needs a **coarse calibration** by staff before the
normal foil calibration.

Tabulated edges (unrounded): Fe K 7112.0, Cu K 8979.0, Ir L3 11215.2,
Pt L3 11563.7, Au L3 11918.7 eV.

## The procedure (at each new edge E0)

1. **Open the slits for the start:** jjvgap 2, jjhgap 3 mm (`umv jjvgap 2
   jjhgap 3`, with staff OK). jjvtra and jjhtra stay at 0.
2. **Move the mono to the edge:** `umv mono <E0>`. Check where it landed with
   `ct 1` (the `absev` column is the encoder energy).
3. **Table height (staff).** The slits and I0 ride on the table, so after a
   keV-scale move the beam can pass above or below the slit. Staff predict
   and, if Tz is more than ~0.3 mm off, re-centre Tz on I0 now. (Example: Fe K
   to Pt L3 needed about +0.9 mm.) If I0 reads zero: check the beam is up and
   the shutter open; then the table, before escalating.
4. **Gains across the edge.** Count at E0 - 50 and E0 + 50 eV
   (`umv mono <E0-50>; ct 1`, then E0 + 50). Pick one SR570 sensitivity per
   channel that keeps **I0, I1, I2 (and pips)** between **3e4 and 3.5e5
   counts/s** at both energies (0.3-3.5 V; 1e5 cps = 1 V; the SR570
   overloads near 5 V). Set with e.g. `set_i0_gain("2 uA/V")`; `wsrs` shows
   all. Strings must match the server's list exactly.
5. **Darks.** Any gain change makes the darks stale; measure them now (see
   `data-collection`, "Darks"). The I0 dark needs the slit closed
   (jjvgap -1) because the shutter is downstream of I0.
6. **Mono pitch detune (staff), 1000 eV above the edge:** `umv mono
   <E0+1000>`, then `mono_detune(25)` - peaks the second-crystal pitch
   (`peak_mono_pitch`) and detunes until I0 is down 25 % (harmonic
   rejection). Reference LVDT for set A: epitcha = 7.5623.
7. **Table on I0 (staff):** Tz and Tx scans (+/-3 mm), moved to the centre;
   Tz should end within ~2 mm of the predicted height change.
8. **Set the working slit gaps** and recheck counts at the edge:
   - Foil calibration: jjvgap 0.5, jjhgap 3 (energy resolution).
   - Sample alignment: 1 x 1 mm.
   - Data collection: jjvgap 1, jjhgap = sample width (max 10 mm; a tilted
     sample counts as width x cos(tilt)), or 1 mm on request.
   Any channel outside 3e4-3.5e5 cps at the new gaps: redo the gains (4) and
   darks (5).
9. **Calibrate the energy** on the reference foil (`energy-calibration`).
10. **Plot counter for the new edge:** `plotselect I1` (transmission) or
    `plotselect xsum` / `plotselect pips`. For the Ge detector, move the ROI
    to the new element's emission line first (`xsp_roie A <lo_eV> <hi_eV>`
    or the detector GUI).

## Slit settings summary

| Use | jjvgap (mm) | jjhgap (mm) |
|---|---|---|
| Start of an energy change | 2.0 | 3.0 |
| Foil calibration | 0.5 | 3.0 |
| Sample alignment | 1.0 | 1.0 |
| Darks with I0 blocked | -1.0 (closed) | - |
| Data collection | 1.0 | sample width (<= 10), or 1 on request |

Allowed ranges: jjvgap -1 to 3 mm, jjhgap 0 to 10 mm.

## Starting amplifier gains (both crystal sets)

i0 2 uA/V, i1 200 nA/V, i2 50 nA/V, pips 10 nA/V - starting points only;
always set from the measured counts.
