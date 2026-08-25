# SPEEDY–ACCESS-OM2 Coupling

This repository contains the development work for coupling the SPEEDY Intermediate complexity AGCM with ACCESS-OM2.

The long-term objective is to develop a computationally efficient coupled climate model of intermediate complexity - CMIC:

```text
       SPEEDY atmosphere
              ↕
            OASIS
              ↕
MOM ocean ↔ OASIS ↔ CICE sea ice
```

### Stage 1 — Offline SPEEDY forcing

```text
SPEEDY
   ↓
6-hourly atmospheric fields
   ↓
JRA55-compatible NetCDF forcing
   ↓
YATM
   ↓
OASIS
   ↓
MOM + CICE
```

The objective of this stage is to run ACCESS-OM2 without modifying the ocean/sea-ice model or the existing YATM forcing interface.

SPEEDY replaces JRA55-do as the source of atmospheric forcing.

This allows independent testing of:

* SPEEDY atmospheric fields;
* units and sign conventions;
* temporal sampling;
* forcing-file structure;
* calendar handling;
* remapping;
* ACCESS-OM2 stability under SPEEDY forcing.

### Stage 2 — Online coupling

After the offline forcing configuration has been validated, the file-based interface will be replaced by direct exchange through OASIS:

```text
                 ┌─────────────┐
                 │   SPEEDY    │
                 │ atmosphere  │
                 └──────┬──────┘
                        │
             atmospheric forcing
                        │
                        ▼
                 ┌─────────────┐
                 │    OASIS    │
                 └──────┬──────┘
                        │
                        ▼
                 ┌─────────────────────┐
                 │ MOM + OASIS + CICE  │
                 └──────┬──────────────┘
                        │
                   SST / sea ice
                        │
                        └──────────────► SPEEDY
```


## Atmospheric fields required by ACCESS-OM2

The current ACCESS-OM2 RYF configuration supplies the following atmospheric fields through YATM:

| ACCESS-OM2 field | OASIS coupling name | Description                    |
| ---------------- | ------------------- | ------------------------------ |
| `rsds`           | `swfld_ai`          | downward shortwave radiation   |
| `rlds`           | `lwfld_ai`          | downward longwave radiation    |
| `prra`           | `rain_ai`           | rainfall                       |
| `prsn`           | `snow_ai`           | snowfall                       |
| `psl`            | `press_ai`          | sea-level pressure             |
| `tas`            | `tair_ai`           | near-surface air temperature   |
| `huss`           | `qair_ai`           | near-surface specific humidity |
| `uas`            | `uwnd_ai`           | near-surface zonal wind        |
| `vas`            | `vwnd_ai`           | near-surface meridional wind   |
| `friver`         | `runof_ai`          | river runoff                   |
| `licalvf`        | `licalvf_ai`        | land-ice runoff                |

The last two fields are land/runoff forcing rather than atmospheric fields and can
initially remain derived from the existing ACCESS-OM2 forcing dataset.

## Available SPEEDY output fields

The standard SPEEDY atmospheric output contains, among others:

```text
MSLP       mean-sea-level pressure        [hPa]
U0         near-surface u-wind            [m/s]
V0         near-surface v-wind            [m/s]
TEMP0      near-surface air temperature   [K]
RH0        near-surface relative humidity [%]

PRECLS     large-scale precipitation      [mm/day]
PRECNV     convective precipitation       [mm/day]

SSR        surface shortwave radiation    [W/m2]
SLR        surface longwave radiation     [W/m2]
```

The preliminary SPEEDY → ACCESS-OM2 mapping is:

| ACCESS-OM2 | SPEEDY                   | Conversion/status                        |
| ---------- | ------------------------ | ---------------------------------------- |
| `rsds`     | `SSR`                    | check exact sign/definition              |
| `tas`      | `TEMP0`                  | K → K                                    |
| `uas`      | `U0`                     | m/s → m/s                                |
| `vas`      | `V0`                     | m/s → m/s                                |
| `psl`      | `MSLP`                   | hPa × 100 → Pa                           |
| `prra`     | `PRECLS + PRECNV`        | mm/day ÷ 86400 → kg m⁻² s⁻¹              |
| `huss`     | `RH0 + TEMP0 + pressure` | must be calculated                       |
| `rlds`     | TBD                      | downward LW component must be identified |
| `prsn`     | TBD                      | snowfall component must be identified    |

For the first forcing experiment, fields not yet available from SPEEDY may temporarily remain from JRA55-do. This allows the forcing pipeline to be validated incrementally.


## Current development status

Completed:

* [x] examined standard SPEEDY atmosphere/sea interface;
* [x] examined an existing SPEEDY–NEMO OASIS coupling implementation;
* [x] identified the role of `ICSEA`;
* [x] examined the ACCESS-OM2 YATM driver;
* [x] identified atmospheric fields required by YATM;
* [x] identified most corresponding SPEEDY diagnostic fields;
* [x] established that SPEEDY uses 36 timesteps/day;
* [x] determined that 6 hours correspond to 9 SPEEDY timesteps;
* [x] prepared a SPEEDY configuration with `NSTPPR = 9`.

Current task:

* [ ] restore a working SPEEDY compiler configuration on Leonardo;
* [ ] compile SPEEDY;
* [ ] run a short experiment with `NSTPPR = 9`;
* [ ] determine the actual temporal frequency of generated output;
* [ ] identify or implement a suitable 6-hourly output pathway.

Next:

* [ ] produce 6-hourly SPEEDY atmospheric fields;
* [ ] convert SPEEDY output to NetCDF;
* [ ] reproduce the variable names, units, calendar and time axis expected by YATM;
* [ ] create SPEEDY-based `forcing.json`;
* [ ] run ACCESS-OM2 using SPEEDY atmospheric forcing;
* [ ] validate the resulting ocean/sea-ice simulation;
* [ ] replace the file-based interface with online OASIS coupling.


For every successful HPC build, record:

```text
HPC system:
compiler:
compiler version:
loaded modules:
MPI implementation:
NetCDF version:
build command:
git commit:
```

This information is essential for reproducing the model on another machine.


