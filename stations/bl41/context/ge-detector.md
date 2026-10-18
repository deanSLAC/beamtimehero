<!-- Condensed from: /usr/local/projects/xspress_32element/{README.md,docs/pvs.md,docs/notes.md,gui/app.py,config/local.toml}, /usr/local/projects/autonomous_fourone/config/{defaults.yaml,bl41_station.json}, /usr/local/projects/cscan_acq/README.md, 2026-10-17 -->
# Ge fluorescence detector (24-element, Xspress3)

BL4-1 has a **24-element germanium detector** installed, read out by an Xspress3
(IOC `XSP3_32Chan`, 32 channels; the 24-element uses channels 1-24, 25-32 unused).
The same software also supports a 32-element detector (one detector at a time), so
some names and docs say "xsp32" or "32-element"; that is the software name, not the
installed hardware.

## Counters in SPEC

| Counter | Meaning |
|---|---|
| `xsum` | Sum of all **good** (not dead) elements, ROI counts |
| `xsA` | Sum of the good members of group A (the usual group: every live element) |
| `xsB` | Sum of the good members of group B (only used for two-ROI work) |
| `xs01`..`xs24` | Single elements. `xs25`..`xs32` exist in the SPEC config but read 0 and are switched off on the 24-element |

Fluorescence data are normalised as counter / I0 (e.g. `xsum/I0`). Counts per point
are already **deadtime corrected in hardware** (DTC on).

## ROIs, groups, dead elements

- **ROI** = the energy window counted per element (ROI 1), in bins of 10 eV
  (bin 2048 = 20.48 keV; 4096 bins). Set on the emission line of the element of
  interest (e.g. Kα).
- **Double photons**: two photons arriving together are recorded as one event at
  twice the energy. The server sets ROI 2 = twice ROI 1 and counts photons as
  ROI 1 + 2 x ROI 2. If ROI 1 is above bin 2048 there is no room for ROI 2 and only
  ROI 1 is used.
- **Groups**: A and B each have one shared ROI. Joining a group takes its ROI;
  setting an element's own ROI to something different removes it from the group.
  Elements in no group count only in `xsum`.
- **Dead (bad) elements** are excluded from every sum. Marking dead/alive is
  persistent and every change (ROI, group, dead) is logged with undo.
- ROIs, groups and dead elements persist across restarts.

## Count rate, dead time and saturation

- The GUI colours each element green up to **200 kcps** and red above
  (`kcps_limit`). Red elements are near the region where deadtime correction
  becomes unreliable; spectra flatten at the peak and the jump shrinks.
- Typical remedies (staff/user decision): move the detector back, add a filter,
  reduce the slit size, or mark a hot or noisy element dead. Element rates scale
  with distance and beam size; ROI counts alone can look fine while total
  (all-energy) rate is high from scatter.
- The autonomous tools have no fixed Ge rate ceiling configured (`ge_max_cps: null`);
  deadtime is judged per case.

## Frames and frame resets

Each SPEC count (and each cscan box gate) makes one Xspress frame (TTL veto
mode). The Xspress holds **16384 frames**, then stops. SPEC resets it
(stop/erase/start, about 2 s pause) at scan start if the scan's points would not
fit, or before a count within 20 frames of the limit. A brief ~2 s pause during
long timescans is therefore normal.

## Ready state

The detector service reports `Ready` = Yes when the counting setup is correct:
TTL veto, deadtime correction on, acquiring. SPEC warns at each ct/scan if it is not
ready or if all xs counters are disabled. Common causes of "not ready":
- someone changed settings by hand (caput, medm, Xspress GUI); staff run `xsp_setup`
  (SPEC) or `xsp32ctl setup` to re-apply;
- the Xspress IOC restarted (comes up with DTC off, internal trigger); the service
  re-applies automatically when it reconnects;
- the Xspress IOC is down: `Connected` = No, Status "waiting for the Xspress IOC".

## GUI

**http://192.168.41.6:8032** (beamline network). Shows a 2-4-6-6-4-2 grid of the 24
elements with last-frame counts and kcps (grey = no data, green <= 200 kcps,
red > 200, dark = dead, blue/orange ring = group A/B). Clicking an element shows its
spectrum (sum since last frame reset, and last frame) with the ROI shaded, and lets
staff set the ROI, group or dead/alive. "Assign all to A" puts every live element in
group A. The JSON state is at `/api/state` (counts, kcps, bad, groups, ROIs,
ready/status, frames).

## SPEC commands (staff)

`xsp` (list), `xsp enable|disable|sums`, `xsp_roi`, `xsp_roie` (ROI in eV),
`xsp_group`, `xsp_bad`, `xsp_good`, `xsp_undo`, `xsp_show`, `xsp_status`,
`xsp_reset_now`, `xsp_setup`. Changing ROIs/groups/dead elements is a write; users
ask staff or use the GUI with staff guidance.

## Common problems

| Symptom | Likely cause |
|---|---|
| `xsum` is 0 / flat | xs counters disabled in SPEC, detector not ready, ROI on the wrong line, shutter closed, Xspress IOC down |
| One element far above/below the others | hot or dead element; mark it dead |
| Peaks flattened, red elements | count rate too high (> ~200 kcps per element) |
| ~2 s pause mid-scan | frame reset near 16384 frames (normal) |
| `xs25`-`xs32` are 0 | expected on the 24-element |
