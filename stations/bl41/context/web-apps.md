<!-- Condensed from: /usr/local/projects/BL4-1_Web/services.json, /usr/local/projects/{cherfd_claude/cscan_ui/README.md,cscan_acq/README.md,fourone_monitor/README.md,motor_mover/README.md,gasmixer/gas-mixer/README.md,xasplusplus/README.md,autonomous_user/README.md}, 2026-10-17 -->

# BL4-1 Web Apps

`localhost` apps run on the beamline computer (bl41lx1); 192.168.41.x apps are on the beamline network.

| App | URL | Purpose | Audience |
|---|---|---|---|
| AI Beamline (autonomous app) | http://localhost:5005 (/dashboard, /config, /samples, /viewer ...) | Agent-run XAS beamtime: experiment form, holders, phases, data viewer | users + staff (when the beamtime uses it) |
| Experimenter Console | http://localhost:5025 | Same phases, experimenter approves and runs each step | users + staff |
| XAS++ | http://localhost:5018 | Manual step cards for each procedure, with checks | users + staff |
| cscan | http://localhost:5013 (docs: /docs-page) | Continuous energy scans: technique, command, sweeps, data path, live plots, results | **users** |
| cscan acquisition | http://localhost:5012 | cscan box diagnostics: quick count, ADC streams, box reference | staff |
| Beam monitor | http://localhost:5014 | Read-only wall display: beamline state, SPEAR current, I0/I1/I2/pips volts, mono energy | **users** |
| CHERFD data processing | http://localhost:5009/app | View and process continuous-scan data | **users** |
| Motor mover | http://localhost:8043 | Move SPEC motors from tiles (relative / absolute / named positions) | users with care; staff for optics |
| Ge detector (Xspress 24-element) | http://192.168.41.6:8032 | Detector GUI: ROIs, groups, bad elements, status | staff (users may view) |
| SRS current amps | http://192.168.41.6:8570 | SR570 gains and offsets for i0, i1, i2, pips | users with guidance |
| Gas mixer | http://localhost:5006 | Ion chamber gas fill/vent, mixtures and HV | staff |
| Beamline camera | http://192.168.41.91/view/viewer_index.shtml?id=0 | Camera viewer | users |

Desktop programs: `spec` (SPEC terminal), cscan box EDM and Xspress MEDM (staff panels), PyMca
(view SPEC files and spectra).

Notes:
- The cscan app forwards to the continuous-scan server (REST, port 5002, not a user page).
- Only one client can use the cscan box at a time: while cscan or cscan acquisition is running,
  SPEC `ct` and step scans are refused.
