<!-- Condensed from: /usr/local/projects/gasmixer/gas-mixer/{README.md,docs/IOC_NOTES.md,gasmixer/pvmap.py,config/GAS_MIXER.TXT}, /usr/local/projects/beamtimehero_cli/src/beamtimehero_cli/{station.py,station_services.py}, /usr/local/projects/autonomous_user/docs/glossary.md, 2026-10-17 -->
# Ion chambers: gas fills and high voltage

BL4-1 has three gas ion chambers: **I0** (before the sample), **I1** (after the
sample), **I2** (after the reference foil, which sits between I1 and I2). Each
measures beam intensity as a current, read through an SR570 amplifier (see
`current-amplifiers`). The gas and its pressure set how much of the beam each
chamber absorbs; the HV collects the ions.

## Hardware

| Part | Where | EPICS |
|---|---|---|
| Gas mixer IOC (Raspberry Pi) + Galil PLC | 192.168.41.40 / .44 | `BL41:GAS` |
| iseg SHR HV supply | 192.168.41.51 | `BL41:ISEG:0:0:<ch>:*`, channels 0-3 |
| ADC rolling plots (ion chambers) | 192.168.41.42:3000 | |

Gas lines (from `GAS_MIXER.TXT`): **1 = He, 2 = N2, 3 = Ar**.
All three chambers (I0, I1, I2) are on **HV channel 0**. Polarity NEGATIVE,
default set voltage **1600 V** (reads -1600 V on `VoltageSet`).

## The gas mixer app

A local web app (**http://127.0.0.1:5006** on bl41lx1) replacing the old WebXAS
"Gas Mixer - BL4-1" page. Per ion chamber it shows pressure, set gas, set
pressure, HV state, status (IDLE / VENTING... / FILLING...), and a "Contains" line
(what was last filled). It also has a High Voltage box, a mixer readback panel, a
Sequence panel with a log, and two-gas mixtures.

Every action is planned first and shown as a list of exact steps; nothing runs
until confirmed. Modes: offline (simulator), live dry-run (reads real IOCs, writes
nothing), and armed (writes). **Armed mode had never been run as of the app's
README**; fills are a staff operation.

Read-only JSON status: `/api/status` (mode, mixer, ion_chambers, hv, pvs). This is
what the sample-environment status reports.

## Fill and vent procedure (staff)

Single gas (the Fill button vents first):
`SetIC n; SetLine g; SetP p; Vent -> wait idle; Fill -> wait idle`

Two-gas mixture (total <= 3 bar, the two partial pressures differ by > 0.2 bar):
vent the IC; fill it with the lower-pressure gas to p1; vent the manifold; fill the
manifold with gas 2 to p1+p2; fill the IC to p1+p2.

## Safety rules (interlocks in the app)

- No vent/fill while any chamber's HV reads |V| >= 5 V: **turn HV off first**.
- No HV on while a chamber on that channel is below 0.95 bar.
- Set pressure limited to 1.1-2.5 bar; HV set 0-2000 V.
- One action at a time; Abort stops further steps but not a vent/fill the IOC has
  already started.
- HV on: set voltage, switch on, wait until within 10 V of target (up to 300 s).
  HV off: set 0 V, wait for < 5 V, switch off.

## Reading the state

| PV | Meaning |
|---|---|
| `BL41:GAS.IC1P`, `IC2P`, `IC3P` | I0, I1, I2 chamber pressure (bar; see units note) |
| `BL41:GAS.MainP`, `Line1P`..`Line3P` | manifold and gas line (He, N2, Ar) pressure |
| `BL41:GAS.Fill`, `BL41:GAS.Vent` | illdefined / idle / start / in progress |
| `BL41:GAS.SetIC`, `SetLine`, `SetP` | last selected chamber (4 = manifold), gas line, target pressure |
| `BL41:ISEG:0:0:0:VoltageMeasure` | ion chamber HV, V (negative) |
| `BL41:ISEG:0:0:0:isOn` | HV channel on/off |
| `BL41:ISEG:0:0:0:CurrentMeasure` | HV channel current |

Units: the IOC wiki says SetP is in atm; the app and the old page label bar
(1.3 % difference, unconfirmed).

The record of what gas is in each chamber (`IC[n]L[m]Set*`) is not on the running
IOC; the app's "Contains" line is its own record of the last fill it did, so it may
not reflect fills done another way.

## Choosing gases

> **TODO (staff):** add the BL4-1 table of ion-chamber gas fills (I0, I1, I2)
> versus energy / edge. Until then, the fill is chosen by staff per experiment.

No BL4-1-specific gas-per-energy table exists yet; the choice is made by
staff. General XAS practice (not BL4-1 policy): lighter gases (He,
N2) at low energy, heavier (N2/Ar mixtures, Ar) as energy rises; I0 is filled to
absorb a smaller fraction (roughly 10-20 %) than I1/I2, so most of the beam reaches
the sample. Ask staff for the fill used this session.

## Common problems

| Symptom | Likely cause |
|---|---|
| I0/I1/I2 near zero with beam on | HV off, chamber not filled, amp gain wrong, shutter/slits closed |
| Ion chamber signal slowly drifting | pressure changing (leak), check `IC<n>P` over time |
| Gas mixer page refuses a fill | HV still on (>= 5 V) or another action in progress |
| Signal saturated after a gas change | heavier gas absorbs more: amp gain needs adjusting |
