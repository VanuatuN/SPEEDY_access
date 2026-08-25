# SPEEDY_access

# SPEEDY–ACCESS-OM2 Coupling

This repository contains the development work for coupling the SPEEDY atmospheric general circulation model with the ocean and sea-ice components of ACCESS-OM2.

The long-term objective is to develop a computationally efficient coupled climate model of intermediate complexity:

```text
SPEEDY atmosphere
        ↕
      OASIS
        ↕
MOM ocean + CICE sea ice
```

Development is performed incrementally. Before implementing online atmosphere–ocean coupling, SPEEDY is first used to generate atmospheric forcing compatible with the existing ACCESS-OM2/YATM forcing interface.

---

## 1. Development strategy

The coupling is developed in two stages.

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
                 ┌─────────────┐
                 │ MOM + CICE  │
                 └──────┬──────┘
                        │
                   SST / sea ice
                        │
                        └──────────────► SPEEDY
```

This is the target coupled model.

---

# 2. SPEEDY configuration

The current SPEEDY configuration uses T30 horizontal resolution.

Relevant time-stepping parameters are stored in:

```text
cls_instep.h
```

The standard configuration examined here contains:

```fortran
NMONTS = 3
NDAYSL = 0
NSTEPS = 36

NSTDIA = 36*5
NSTPPR = 6
NSTOUT = -1
IDOUT  = 0
NMONRS = 3
```

## Atmospheric timestep

There are 36 model timesteps per day:

```text
24 h / 36 = 40 min
```

Therefore:

```text
1 SPEEDY timestep = 40 min
```

The ACCESS-OM2 JRA55-do forcing currently used by YATM has a 6-hourly temporal resolution.

Six hours correspond to:

```text
6 h × 60 min / 40 min = 9 SPEEDY timesteps
```

For the SPEEDY forcing experiment, the post-processing interval is therefore changed from:

```fortran
NSTPPR = 6
```

to:

```fortran
NSTPPR = 9
```

**Important:** this parameter controls the post-processing interval. It must still be verified whether changing `NSTPPR` alone produces the required 6-hourly records or whether a separate output routine must be added.

---

# 3. SPEEDY sea-surface configuration

Two SPEEDY configurations have been examined.

## Standard/uncoupled SPEEDY

```fortran
ICSEA  = 0
ICICE  = 1
ISSTAN = 1
```

In this configuration SST is externally prescribed.

## Existing SPEEDY–NEMO coupled version

The existing coupled version uses:

```fortran
ICSEA  = 3
ICICE  = 1
ISSTAN = 0
```

`ICSEA = 3` activates the configuration in which the SST anomaly is supplied by the coupled ocean model and combined with the observed SST climatology.

This existing implementation is an important reference for the future online SPEEDY–ACCESS-OM2 coupling.

---

# 4. Atmospheric fields required by ACCESS-OM2

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

The last two fields are land/runoff forcing rather than atmospheric fields and can initially remain derived from the existing ACCESS-OM2 forcing dataset.

---

# 5. Available SPEEDY output fields

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

---

# 6. Running SPEEDY

Experiments are launched from the `run` directory using:

```bash
./run_exp.s t30 <experiment_number> 0
```

Example:

```bash
./run_exp.s t30 101 0
```

The script interactively asks whether model parameters should be modified.

For the 6-hourly forcing experiment:

```text
Do you want to modify the time-stepping parameters (y/n)?
y
```

The editable parameter file is:

```text
cls_instep.h
```

Set:

```fortran
NSTPPR = 9
```

The remaining parameter groups can initially be left unchanged.

---

# 7. Compilation environment

The original SPEEDY makefile may attempt to compile the model using the PGI compiler:

```text
pgf90
```

If the compiler is unavailable, compilation terminates with:

```text
make: pgf90: Command not found
```

followed by:

```text
./imp.exe: not found
```

The latter error is a consequence of the failed compilation rather than an independent runtime problem.

The repository also contains alternative makefiles:

```text
makefile
makefile_ifort
makefile_pgf90
```

The compiler configuration appropriate for the target HPC system must therefore be selected before building SPEEDY.

### Environment diagnostics

Before compiling on a new system, record:

```bash
hostname
module list
which pgf90
which ifort
which ifx
which gfortran
```

The exact compiler/module configuration used on Leonardo should be documented here once recovered.

---

# 8. Current development status

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

---

# 9. Reproducibility notes

Every non-default modification should be committed separately.

Recommended workflow:

```bash
git status
git diff

git add <modified_files>
git commit -m "Set SPEEDY post-processing interval to 6 hours"
```

Do not combine unrelated compiler, physics, forcing and coupling modifications into one commit.

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

---

# 10. Development principle

The existing ACCESS-OM2 ocean/sea-ice configuration should remain unchanged for the initial forcing experiments.

The first interface is deliberately:

```text
SPEEDY
   ↓
JRA55-like forcing files
   ↓
existing YATM
   ↓
existing OASIS configuration
   ↓
existing MOM/CICE
```

Only after this configuration works and has been validated should direct online atmosphere–ocean coupling be introduced.
