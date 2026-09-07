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

# prra 1989 in INPUT/OMIP is currently empty, so use 1990–1991 for now.
# After re-downloading it, change to YEARS = (1989, 1990, 1991).
YEARS = (1990, 1991)
TS_YEAR = 1990

VARIABLES = {
    "prra": {
        "label": "Rainfall",
        "levels": np.arange(0, 15.5, 0.5),
        "ticks": np.arange(0, 16, 2),
        "diff_levels": np.arange(-5, 5.25, 0.25),
        "diff_ticks": np.arange(-5, 6, 1),
        "diff_lim": 5,
    },
    "prsn": {
        "label": "Snowfall",
        "levels": np.arange(0, 6.25, 0.25),
        "ticks": np.arange(0, 7, 1),
        "diff_levels": np.arange(-2, 2.1, 0.1),
        "diff_ticks": np.arange(-2, 2.1, 0.5),
        "diff_lim": 2,
    },
}

# ============================================================
# Helpers
# ============================================================

def get_files(var):
    jra_files = []
    speedy_files = []

    for year in YEARS:
        matches = sorted(JRA_DIR.glob(
            f"{var}_input4MIPs_atmosphericState_OMIP_MRI-JRA55-do-*_gr_{year}*.nc"
        ))
        matches = [f for f in matches if f.stat().st_size > 0]
        if not matches:
            raise FileNotFoundError(f"No non-empty JRA55 {var} file found for {year}")
        jra_files.extend(matches)

        f = SPEEDY_DIR / f"{var}_SPEEDY_{year}.nc"
        if not f.exists() or f.stat().st_size == 0:
            raise FileNotFoundError(f)
        speedy_files.append(f)

    return jra_files, speedy_files


def open_var(files, var):
    return xr.open_mfdataset(
        files, combine="by_coords", chunks={"time": 120},
        data_vars="minimal", coords="minimal", compat="override"
    )[var]


def normalize_lon(da):
    return da.assign_coords(lon=((da.lon + 180) % 360) - 180).sortby("lon")


def gaussian_global_mean(da):
    """Area-weighted global mean for an equally spaced longitude Gaussian grid."""
    _, w = np.polynomial.legendre.leggauss(da.sizes["lat"])
    if da.lat.values[0] > da.lat.values[-1]:
        w = w[::-1]
    weights = xr.DataArray(w, coords={"lat": da.lat}, dims="lat")
    return da.weighted(weights).mean(("lat", "lon"))


def make_cyclic(da):
    return add_cyclic_point(da.values, coord=da.lon.values, axis=da.get_axis_num("lon"))


def setup_map(ax):
    ax.set_global()
    ax.coastlines(resolution="110m", linewidth=0.7)
    ax.add_feature(cfeature.BORDERS, linewidth=0.3)


sns.set_theme(style="white")
plt.rcParams.update({"font.family": "Nimbus Sans"})
main_cmap = plt.get_cmap("turbo")
diff_cmap = LinearSegmentedColormap.from_list(
    "PrecipBlueWhiteRed",
    ["#313695", "#4575b4", "#74add1", "#abd9e9", "#e0f3f8", "#ffffff",
     "#fee090", "#fdae61", "#f46d43", "#d73027", "#a50026"], N=256
)

# ============================================================
# Compare prra and prsn
# ============================================================

for var, cfg in VARIABLES.items():
    print(f"\n{'='*70}\n{var}: {cfg['label']}\n{'='*70}")

    JRA_FILES, SPEEDY_FILES = get_files(var)
    print("JRA files:", len(JRA_FILES))
    print("SPEEDY files:", len(SPEEDY_FILES))

    jra = open_var(JRA_FILES, var)
    speedy = open_var(SPEEDY_FILES, var)

    print("JRA:", jra.time.min().values, "to", jra.time.max().values, "|", jra.sizes["time"], "steps")
    print("SPEEDY:", speedy.time.min().values, "to", speedy.time.max().values, "|", speedy.sizes["time"], "steps")
    print("JRA range [kg m-2 s-1]:", float(jra.min().compute()), "to", float(jra.max().compute()))
    print("SPEEDY range [kg m-2 s-1]:", float(speedy.min().compute()), "to", float(speedy.max().compute()))

    # ========================================================
    # 1. Multi-year mean maps
    # ========================================================

    print(f"\nComputing {YEARS[0]}–{YEARS[-1]} mean fields...")
    jra_mean = normalize_lon(jra.mean("time", skipna=True).compute())
    print("JRA mean done")
    speedy_mean = normalize_lon(speedy.mean("time", skipna=True).compute())
    print("SPEEDY mean done")

    # Difference map only: interpolate the already-computed SPEEDY mean to JRA grid.
    # Global means below are always computed independently on each native Gaussian grid.
    print("Interpolating SPEEDY mean -> JRA grid for difference map...")
    speedy_on_jra = speedy_mean.interp(lat=jra_mean.lat, lon=jra_mean.lon)

    # kg m-2 s-1 water flux == mm s-1; multiply by 86400 -> mm/day.
    reference_mean = (jra_mean * 86400.0).where(jra_mean > 0)
    candidate_mean = speedy_on_jra * 86400.0
    difference_mean = candidate_mean - reference_mean
    

    reference_mean.attrs["units"] = "mm day-1"
    candidate_mean.attrs["units"] = "mm day-1"
    difference_mean.attrs["units"] = "mm day-1"
    

    print("JRA mean range [mm/day]:", float(reference_mean.min()), "to", float(reference_mean.max()))
    print("SPEEDY mean range [mm/day]:", float(candidate_mean.min()), "to", float(candidate_mean.max()))
    print("Difference range [mm/day]:", float(difference_mean.min()), "to", float(difference_mean.max()))

    diff_norm = mcolors.TwoSlopeNorm(vmin=-cfg["diff_lim"], vcenter=0, vmax=cfg["diff_lim"])

    fig = plt.figure(figsize=(14, 9), facecolor="white")
    gs = fig.add_gridspec(2, 6, height_ratios=[1, 1.3], hspace=0.3, wspace=0.12)
    ax1 = fig.add_subplot(gs[0, 0:3], projection=ccrs.PlateCarree())
    ax2 = fig.add_subplot(gs[0, 3:6], projection=ccrs.PlateCarree())
    ax3 = fig.add_subplot(gs[1, 0:6], projection=ccrs.PlateCarree())

    data, lon = make_cyclic(reference_mean)
    im1 = ax1.contourf(
        lon, reference_mean.lat, data, levels=cfg["levels"], cmap=main_cmap,
        transform=ccrs.PlateCarree(), extend="max"
    )
    setup_map(ax1)
    ax1.set_title(f"Mean {cfg['label']} [mm/day]\nJRA55, {YEARS[0]}–{YEARS[-1]}",
                  fontsize=14, fontweight="bold", pad=10)

    data, lon = make_cyclic(candidate_mean)
    ax2.contourf(
        lon, candidate_mean.lat, data, levels=cfg["levels"], cmap=main_cmap,
        transform=ccrs.PlateCarree(), extend="max"
    )
    setup_map(ax2)
    ax2.set_title(f"Mean {cfg['label']} [mm/day]\nSPEEDY T30, {YEARS[0]}–{YEARS[-1]}",
                  fontsize=14, fontweight="bold", pad=10)

    data, lon = make_cyclic(difference_mean)
    im3 = ax3.contourf(
        lon, difference_mean.lat, data, levels=cfg["diff_levels"], norm=diff_norm,
        cmap=diff_cmap, transform=ccrs.PlateCarree(), extend="both"
    )
    setup_map(ax3)
    ax3.set_title("SPEEDY − JRA55", fontsize=14, fontweight="bold", pad=10)

    cbar1 = fig.colorbar(im1, ax=[ax1, ax2], orientation="horizontal",
                         fraction=0.045, pad=0.07, aspect=40, ticks=cfg["ticks"])
    cbar1.set_label(f"{cfg['label']} [mm/day]", fontsize=12, labelpad=8)
    cbar1.ax.tick_params(labelsize=11, length=5, width=1)
    cbar1.outline.set_visible(False)

    cbar2 = fig.colorbar(im3, ax=ax3, orientation="horizontal",
                         fraction=0.045, pad=0.08, aspect=30, ticks=cfg["diff_ticks"])
    cbar2.set_label(f"{cfg['label']} difference [mm/day]", fontsize=12, labelpad=8)
    cbar2.ax.tick_params(labelsize=11, length=5, width=1)
    cbar2.outline.set_visible(False)

    map_file = FIG_DIR / f"diff_mean_{var}_{YEARS[0]}_{YEARS[-1]}.png"
    fig.savefig(map_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Saved:", map_file)

    # ========================================================
    # 2. Area-weighted global-mean time series, TS_YEAR
    # ========================================================

    print(f"\nComputing area-weighted global-mean {cfg['label'].lower()} for {TS_YEAR}...")
    jra_year = jra.sel(time=str(TS_YEAR))
    speedy_year = speedy.sel(time=str(TS_YEAR))

    jra_global = gaussian_global_mean(jra_year).compute() * 86400.0
    print("JRA global mean done")
    speedy_global = gaussian_global_mean(speedy_year).compute() * 86400.0
    print("SPEEDY global mean done")

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(jra_global.time, jra_global, linewidth=1.2, label="JRA55")
    ax.plot(speedy_global.time, speedy_global, linewidth=1.2, label="SPEEDY T30")
    ax.set_title(f"Area-weighted Global-Mean {cfg['label']} {TS_YEAR}",
                 fontsize=15, fontweight="bold", pad=10)
    ax.set_ylabel(f"{cfg['label']} [mm/day]", fontsize=13, labelpad=10)
    ax.set_xlabel("Time", fontsize=13, labelpad=10)
    ax.tick_params(axis="both", direction="out", length=6, width=1.2, labelsize=12)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(1.5)
    ax.spines["bottom"].set_linewidth(1.5)
    ax.legend(frameon=False, fontsize=12)
    fig.tight_layout()

    ts_file = FIG_DIR / f"global_mean_{var}_timeseries_{TS_YEAR}.png"
    fig.savefig(ts_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Saved:", ts_file)

    # ========================================================
    # 3. Global-mean statistics, TS_YEAR
    # ========================================================

    jra_stats = {"Mean": float(jra_global.mean()), "Min": float(jra_global.min()), "Max": float(jra_global.max())}
    speedy_stats = {"Mean": float(speedy_global.mean()), "Min": float(speedy_global.min()), "Max": float(speedy_global.max())}

    print(f"\n{TS_YEAR} global-mean {cfg['label'].lower()} statistics [mm/day]")
    print("JRA55 :", jra_stats)
    print("SPEEDY:", speedy_stats)

    jra.close()
    speedy.close()

print("\nDONE")
