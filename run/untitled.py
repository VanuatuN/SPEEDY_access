from pathlib import Path
import json
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt

# ------------------------------------------------------------------
# Paths: replace these with the actual JRA and SPEEDY files/patterns.
# open_mfdataset accepts wildcards.
# ------------------------------------------------------------------
JRA_PATH = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/INPUT/OMIP/tas_input4MIPs_atmosphericState_OMIP_MRI-JRA55-do-1-5-0_gr_198901010000-198912312100.nc")
SPEEDY_PATH = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/forcing/tas_SPEEDY_1989.nc")

JRA_VARIABLE = "tas"
SPEEDY_VARIABLE = "tas"

# Scientific comparison target:
# "jra"    -> interpolate SPEEDY to the JRA grid
# "speedy" -> interpolate JRA to the SPEEDY grid
REGRID_TO = "jra"

# Use only for a quick test before running over all files.
MAX_TIME_RECORDS = None


# =========================
# 1. Open datasets

def open_any(path):
    path = str(path)
    if any(char in path for char in "*?[]"):
        return xr.open_mfdataset(
            path,
            combine="by_coords",
            parallel=False,
            chunks={"time": 120},
            decode_times=True,
            use_cftime=True,
        )

    return xr.open_dataset(
        path,
        chunks={"time": 120},
        decode_times=True,
        use_cftime=True,
    )

jra = open_any(JRA_PATH)
speedy = open_any(SPEEDY_PATH)

if MAX_TIME_RECORDS is not None:
    jra = jra.isel(time=slice(0, MAX_TIME_RECORDS))
    speedy = speedy.isel(time=slice(0, MAX_TIME_RECORDS))

print("JRA")
print(jra)
print("\nSPEEDY")
print(speedy)
