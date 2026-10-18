<!-- Condensed from: /etc/profile.d/epics.sh, /usr/local/projects/fourone_monitor/{README.md,config.json,fourone_monitor.py}, /usr/local/projects/beamtimehero_cli/src/beamtimehero_cli/{config.py,station.py,station_services.py}, /usr/local/projects/ssrl-current-amp/epics_usage_guide_BL4-1.txt, /usr/local/projects/xspress_32element/docs/pvs.md, /usr/local/projects/gasmixer/gas-mixer/{docs/IOC_NOTES.md,gasmixer/pvmap.py}, /usr/local/lib/spec.d/spec/config, 2026-10-17 -->
# BL4-1 EPICS PVs for read-only caget

All PVs below are for **reading** (`caget`). Never write them from the help agent.

## Where the IOCs are (CA address list, /etc/profile.d/epics.sh)

`EPICS_CA_AUTO_ADDR_LIST=NO`; searches go only to:

| Entry | Serves |
|---|---|
| `spearca1.slac.stanford.edu:5100` | SPEAR gateway: `SPEAR:*`, `BL04:State` |
| `192.168.41.255` (broadcast, port 5064) | beamline IOCs: .5 Xspress3 (`XSP3_32Chan:`), .40 gas mixer (`BL41:GAS`), .42 ADC plot Pi, .49 cscan box (`BL41:SCAN:MASTER`), .51 iseg HV (`BL41:ISEG`) |
| `192.168.41.6:5070` | SR570 current amp IOC (`Local:BL4-1:`) on bl41lx1 |
| `192.168.41.6:5072` | Ge detector config IOC (`Local:BL4-1:XSP32:`) on bl41lx1 |

## Beam and beamline state

Source: fourone_monitor/config.json; beamtimehero_cli config.py + station.py.

| PV | Meaning | Units |
|---|---|---|
| `SPEAR:BeamCurrAvg` | SPEAR ring current (~500 mA nominal; < 200 mA "low") | mA |
| `BL04:State` | beamline state enum: Moving / Open / Closed / Fault. Open or Moving = OK | enum |

BL4-1 is a wiggler beamline: there is no undulator gap or gap-owner PV.

## Mono

Source: fourone_monitor (config.json, fourone_monitor.py); SPEC config.
There is **no direct energy PV**; energy comes from the crystal angle.

| PV | Meaning | Units |
|---|---|---|
| `BL41:SCAN:MASTER:MOTOR1.RBV` | mono crystal angle readback | deg |
| `BL41:SCAN:MASTER:MOTOR1.DMOV` | 1 = done moving, 0 = moving | |
| `BL41:SCAN:MASTER:MOTOR1.REP` | raw encoder readback (SPEC counter `monoenc`) | counts |

Energy (eV) = 12398.42 x L / (2 x 5.43102 x sin(theta)), with L = sqrt(8) for
crystal set A Si(220), sqrt(3) for set B Si(111). The current set is in
`/usr/local/lib/spec.d/mono.cfg` (written by SPEC `set_crystal`); SPEC's `absev`
counter is the authoritative per-point energy.

## Current amplifiers (SR570)

Source: ssrl-current-amp/epics_usage_guide_BL4-1.txt; SPEC config. `<ch>` = `i0`,
`i1`, `i2`, `pips`.

| PV | Meaning | Units |
|---|---|---|
| `Local:BL4-1:<ch>:SensitivityValue` | gain (SPEC `i0gain`, `i1gain`, `i2gain`, `pipgain`) | A/V |
| `Local:BL4-1:<ch>:SensitivityString` | gain as text, e.g. `2 uA/V` | string |
| `Local:BL4-1:<ch>:OffsetCurrent` | input offset, signed (SPEC `i0offs` ...) | A |
| `Local:BL4-1:<ch>:OffsetString` | offset as text, e.g. `-50 nA` | string |

## cscan box (amp voltages)

Source: fourone_monitor README/config.json; cherfd_claude/confs/bl41_cscan_box_adc.json.

| PV | Meaning | Units |
|---|---|---|
| `BL41:SCAN:MASTER.ADC1` | i0 amp output | raw word |
| `BL41:SCAN:MASTER.ADC2` | i1 amp output | raw word |
| `BL41:SCAN:MASTER.ADC3` | i2 amp output | raw word |
| `BL41:SCAN:MASTER.ADC4` | pips amp output | raw word |

Decode: volts = (word - 2147483648) / 65536 / 3090 (3090 counts/V is a rough
calibration). Linear window 0.3-3.5 V.

## Ge detector (24-element, Xspress3)

Source: xspress_32element/docs/pvs.md. Config/status IOC prefix
`Local:BL4-1:XSP32:`; counts from `XSP3_32Chan:`. `<n>` = 1..24.

| PV | Meaning | Units |
|---|---|---|
| `Local:BL4-1:XSP32:NElem` | elements in use (24) | |
| `Local:BL4-1:XSP32:Label` | `24-element Ge detector` | string |
| `Local:BL4-1:XSP32:Status` | `ready`, `not ready: <why>`, `waiting for the Xspress IOC` | string |
| `Local:BL4-1:XSP32:Ready` | No/Yes: TTL veto, DTC on, acquiring | enum |
| `Local:BL4-1:XSP32:Connected` | No/Yes: Xspress IOC connected | enum |
| `Local:BL4-1:XSP32:Heartbeat` | +1 per second while the service runs | |
| `Local:BL4-1:XSP32:Frames` | frame counter (limit 16384) | frames |
| `Local:BL4-1:XSP32:Bad` | array, 1 = dead element | |
| `Local:BL4-1:XSP32:Groups` | array, 0 none / 1 A / 2 B | |
| `Local:BL4-1:XSP32:RoiLo`, `RoiHi` | array, ROI 1 per element | bins (10 eV) |
| `Local:BL4-1:XSP32:GA:RoiLo`, `GA:RoiHi`, `GB:RoiLo`, `GB:RoiHi` | group ROIs | bins |
| `Local:BL4-1:XSP32:E<nn>:Bad`, `E<nn>:Group` | per element, `E01`..`E24` | |
| `XSP3_32Chan:det1:ArrayCounter_RBV` | frames since last reset | frames |
| `XSP3_32Chan:MCA<n>ROI:1:Total_RBV` | last frame ROI 1 counts, element n (DTC) | counts |
| `XSP3_32Chan:C<n>SCA:0:Value_RBV` | last frame clock ticks (80 MHz) -> live time | ticks |

## Gas mixer and ion chamber HV

Source: gasmixer/gas-mixer/gasmixer/pvmap.py, docs/IOC_NOTES.md.

| PV | Meaning | Units |
|---|---|---|
| `BL41:GAS.IC1P`, `.IC2P`, `.IC3P` | I0, I1, I2 pressure | bar (IOC wiki says atm) |
| `BL41:GAS.MainP`, `.Line1P`..`.Line3P` | manifold, He/N2/Ar line pressure | bar |
| `BL41:GAS.Fill`, `.Vent` | illdefined/idle/start/in progress | enum |
| `BL41:GAS.SetIC`, `.SetLine`, `.SetP` | last chamber (4 = manifold), gas line (1 He, 2 N2, 3 Ar), target P | |
| `BL41:ISEG:0:0:<ch>:VoltageMeasure` | HV channel `<ch>` (0-3; ICs use 0) | V |
| `BL41:ISEG:0:0:<ch>:VoltageSet` | HV set point (signed, -1600 typical) | V |
| `BL41:ISEG:0:0:<ch>:CurrentMeasure` | HV current | (units not documented) |
| `BL41:ISEG:0:0:<ch>:isOn` | off/on | enum |

## Sample temperature

No temperature PVs are configured at BL4-1 (`BTH_SAMPLE_TEMP_PVS` is empty; no
temperature controller in the SPEC config). If staff add a cryostat or heater, its
PVs go in `BTH_SAMPLE_TEMP_PVS` as `label=PV,label=PV`.
