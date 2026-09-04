#!/usr/bin/env python3

from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.colors import LinearSegmentedColormap
import seaborn as sns
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.util import add_cyclic_point

# ============================================================
# Paths and configuration
# ============================================================

JRA_DIR = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/INPUT/OMIP")
SPEEDY_DIR = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/access_forcing")
FIG_DIR = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/scripts/figures")
FIG_DIR.mkdir(parents=True, exist_ok=True)

# JRA_FILES = (
#     sorted(JRA_DIR.glob("tas_input4MIPs_atmosphericState_OMIP_MRI-JRA55-do-1-5-0_gr_1989*.nc")) +
#     sorted(JRA_DIR.glob("tas_input4MIPs_atmosphericState_OMIP_MRI-JRA55-do-1-5-0_gr_1990*.nc")) +
#     sorted(JRA_DIR.glob("tas_input4MIPs_atmosphericState_OMIP_MRI-JRA55-do-1-5-0_gr_1991*.nc"))
# )
SPEEDY_FILES = [SPEEDY_DIR / f"tas_SPEEDY_{year}.nc" for year in (1989, 1990, 1991)]
JRA_FILES = sum(
    [sorted(JRA_DIR.glob(f"tas_input4MIPs_atmosphericState_OMIP_MRI-JRA55-do-1-5-0_gr_{year}*.nc"))
     for year in (1989, 1990, 1991)],
    []
)

if not JRA_FILES: raise FileNotFoundError("No JRA55 tas files found for 1989–1991")
for f in SPEEDY_FILES:
    if not f.exists(): raise FileNotFoundError(f)

print("JRA files:", len(JRA_FILES))
print("SPEEDY files:", len(SPEEDY_FILES))

# ============================================================
# Open data
# ============================================================

jra = xr.open_mfdataset(JRA_FILES, combine="by_coords", chunks={"time":120},
                        data_vars="minimal", coords="minimal", compat="override")["tas"]
speedy = xr.open_mfdataset(SPEEDY_FILES, combine="by_coords", chunks={"time":120},
                           data_vars="minimal", coords="minimal", compat="override")["tas"]

print("JRA:", jra.time.min().values, "to", jra.time.max().values, "|", jra.sizes["time"], "steps")
print("SPEEDY:", speedy.time.min().values, "to", speedy.time.max().values, "|", speedy.sizes["time"], "steps")

def normalize_lon(da):
    return da.assign_coords(lon=((da.lon + 180) % 360) - 180).sortby("lon")

def area_weighted_mean(da):
    weights = np.cos(np.deg2rad(da.lat))
    return da.weighted(weights).mean(("lat","lon"))

def make_cyclic(da):
    return add_cyclic_point(da.values, coord=da.lon.values, axis=da.get_axis_num("lon"))

def setup_map(ax):
    ax.set_global()
    ax.coastlines(resolution="110m", linewidth=0.7)
    ax.add_feature(cfeature.BORDERS, linewidth=0.3)

# 1. 1989–1991 mean maps

print("\nComputing 1989–1991 mean fields...")
jra_mean = normalize_lon(jra.mean("time", skipna=True).compute())
print("JRA mean done")
speedy_mean = normalize_lon(speedy.mean("time", skipna=True).compute())
print("SPEEDY mean done")

print("Interpolating SPEEDY mean -> JRA grid...")
speedy_on_jra = speedy_mean.interp(lat=jra_mean.lat, lon=jra_mean.lon)

reference_mean = jra_mean - 273.15
candidate_mean = speedy_on_jra - 273.15
difference_mean = speedy_on_jra - jra_mean

reference_mean.attrs["units"] = "°C"
candidate_mean.attrs["units"] = "°C"
difference_mean.attrs["units"] = "°C"

sns.set_theme(style="white")
plt.rcParams.update({"font.family":"Nimbus Sans"})

temp_cmap = plt.get_cmap("turbo")
diff_cmap = LinearSegmentedColormap.from_list(
    "TemperatureBlueWhiteRed",
    ["#313695","#4575b4","#74add1","#abd9e9","#e0f3f8","#ffffff",
     "#fee090","#fdae61","#f46d43","#d73027","#a50026"], N=256)

temp_levels = np.arange(-50, 52.5, 2.5)
temp_norm = mcolors.TwoSlopeNorm(vmin=-50, vcenter=0, vmax=50)
temp_ticks = np.arange(-50, 51, 10)
diff_levels = np.arange(-10, 10.5, 0.5)
diff_norm = mcolors.TwoSlopeNorm(vmin=-10, vcenter=0, vmax=10)
diff_ticks = np.arange(-10, 11, 2)

fig = plt.figure(figsize=(14,9), facecolor="white")
gs = fig.add_gridspec(2,6, height_ratios=[1,1.3], hspace=0.3, wspace=0.12)

ax1 = fig.add_subplot(gs[0,0:3], projection=ccrs.PlateCarree())
ax2 = fig.add_subplot(gs[0,3:6], projection=ccrs.PlateCarree())
ax3 = fig.add_subplot(gs[1,0:6], projection=ccrs.PlateCarree())

data, lon = make_cyclic(reference_mean)
im1 = ax1.contourf(lon, reference_mean.lat, data, levels=temp_levels, norm=temp_norm, cmap=temp_cmap,
                   transform=ccrs.PlateCarree(), extend="both")
setup_map(ax1)
ax1.set_title("Mean T10m [°C] JRA55, 1989–1991", fontsize=14, fontweight="bold", pad=10)

data, lon = make_cyclic(candidate_mean)
ax2.contourf(lon, candidate_mean.lat, data, levels=temp_levels, norm=temp_norm, cmap=temp_cmap,
             transform=ccrs.PlateCarree(), extend="both")
setup_map(ax2)
ax2.set_title("Mean Near-Surface Air T [°C] SPEEDY T30, 1989–1991", fontsize=14, fontweight="bold", pad=10)

data, lon = make_cyclic(difference_mean)
im3 = ax3.contourf(lon, difference_mean.lat, data, levels=diff_levels, norm=diff_norm, cmap=diff_cmap,
                   transform=ccrs.PlateCarree(), extend="both")
setup_map(ax3)
ax3.set_title("SPEEDY − JRA55", fontsize=14, fontweight="bold", pad=10)

cbar1 = fig.colorbar(im1, ax=[ax1,ax2], orientation="horizontal",
                     fraction=0.045, pad=0.07, aspect=40, ticks=temp_ticks)
cbar1.set_label("Temperature [°C]", fontsize=12, labelpad=8)
cbar1.ax.tick_params(labelsize=11, length=5, width=1)
cbar1.outline.set_visible(False)

cbar2 = fig.colorbar(im3, ax=ax3, orientation="horizontal",
                     fraction=0.045, pad=0.08, aspect=30, ticks=diff_ticks)
cbar2.set_label("Temperature difference [°C]", fontsize=12, labelpad=8)
cbar2.ax.tick_params(labelsize=11, length=5, width=1)
cbar2.outline.set_visible(False)

map_file = FIG_DIR / "diff_annual_mean_T_1989_1991.png"
fig.savefig(map_file, dpi=150, bbox_inches="tight")
plt.close(fig)
print("Saved:", map_file)

# ============================================================
# 2. Area-weighted global-mean temperature time series, 1990
# ============================================================

print("\nComputing area-weighted global-mean temperature for 1990...")
jra_1990 = jra.sel(time=slice("1990-01-01","1990-12-31"))
speedy_1990 = speedy.sel(time=slice("1990-01-01","1990-12-31"))

jra_global = area_weighted_mean(jra_1990).compute() - 273.15
print("JRA global mean done")
speedy_global = area_weighted_mean(speedy_1990).compute() - 273.15
print("SPEEDY global mean done")

fig, ax = plt.subplots(figsize=(12,5))
ax.plot(jra_global.time, jra_global, linewidth=1.5, label="JRA55")
ax.plot(speedy_global.time, speedy_global, linewidth=1.5, label="SPEEDY T30")

ax.set_title("Area-weighted Global-Mean Temperature 1990", fontsize=15, fontweight="bold", pad=10)
ax.set_ylabel("Temperature [°C]", fontsize=13, labelpad=10)
ax.set_xlabel("Time", fontsize=13, labelpad=10)
ax.tick_params(axis="both", direction="out", length=6, width=1.2, labelsize=12)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_linewidth(1.5)
ax.spines["bottom"].set_linewidth(1.5)
ax.legend(frameon=False, fontsize=12)

fig.tight_layout()
ts_file = FIG_DIR / "global_mean_T_timeseries_1990.png"
fig.savefig(ts_file, dpi=150, bbox_inches="tight")
plt.close(fig)
print("Saved:", ts_file)

# ============================================================
# 3. Global-mean statistics, 1990
# ============================================================

jra_stats = {"Mean":float(jra_global.mean()), "Min":float(jra_global.min()), "Max":float(jra_global.max())}
speedy_stats = {"Mean":float(speedy_global.mean()), "Min":float(speedy_global.min()), "Max":float(speedy_global.max())}

print("\n1990 global-mean temperature statistics [°C]")
print("JRA55 :", jra_stats)
print("SPEEDY:", speedy_stats)

# ============================================================
# Cleanup
# ============================================================

jra.close()
speedy.close()

print("\nDONE")
