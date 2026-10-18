<!-- Condensed from: autonomous_fourone/.claude/skills/cryostat-procedures/SKILL.md, 41_spec/CLAUDE.md, 2026-10-17 -->

# Samples in the BL4-1 cryostat

SSRL runs BL4-1 cryostat experiments at 4-273 K, most at 77 K (liquid
nitrogen).

## Safety rules (read first)

- **Cool-down, warm-up, venting, refilling (cryogens) and sample changes are
  staff actions.** Ask staff and wait; never work around a cryostat that is
  not ready.
- **The temperature is set by staff.** At BL4-1 there is no SPEC command to
  read or set the cryostat temperature (the BL15-2 `cryo` macro is not
  loaded here). Never assume a temperature: confirm it with staff and write
  it down.
- **Do not move the table or the cryostat mount.** Users move only the
  sample stage (Sx, Sz) and the mono energy, as for any sample.
- Usable Sx / Sz range through the cryostat windows: **confirm with staff**.
  Until then keep scans inside the aligned sample bounds (plus the usual
  alignment margins).

## Alignment

- **Re-align after every temperature change.** Thermal contraction of the
  cold finger moves samples by up to a few tenths of a mm, mostly in Sz.
  Warm alignment results do not carry over to a cold run. Wait until staff
  report the temperature is stable, then at least repeat the fine Sz scan
  per sample (`dscan Sz -3 3 30 0.3`; see `sample-alignment`), ideally Sx
  too.
- **Windows absorb.** The cryostat windows add absorption on the incident,
  transmitted and fluorescence paths, so I1 and fluorescence counts are lower
  than for the same sample at room temperature. Set gains from the measured
  counts (`ct 1`; 3e4-3.5e5 cps window), not from ambient experience.

## Ice

Frost or ice on the windows or the sample shows as:

- a slow, monotonic drop in I1 (and fluorescence) at a fixed position, and
- in EXAFS, **Bragg glitches** - sharp spikes at fixed energies that repeat
  across reps.

Note it and ask staff to check. Do not chase it by moving to new spots.

## Beam damage at low temperature

- Cooling slows radiation damage but **does not stop photoreduction**.
  Do the usual damage test (two identical reps on one spot; see
  `data-quality`). A sample stable for two quick XANES at 77 K may still
  drift over many reps - keep comparing reps throughout.
- Fresh-spot moves work as at ambient, inside the aligned bounds.

## What to record

For every cryostat holder, in your notes / logbook:

- the temperature staff reported (or "temperature not recorded");
- whether alignment was redone after the last temperature change;
- any ice or window effects seen (scan numbers).
