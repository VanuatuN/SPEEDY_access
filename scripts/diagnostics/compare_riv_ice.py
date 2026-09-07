#!/usr/bin/env python3

from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.util import add_cyclic_point

# ============================================================
# Paths
# ============================================================

JRA_DIR = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/INPUT/OMIP")
FIG_DIR = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/scripts/figures")
FIG_DIR.mkdir(parents=True, exist_ok=True)

YEARS = (1990, 1991)

PLOT_CONFIG = {
    "friver": {
        "title": "Mean River Freshwater Flux JRA55, 1990–1991",
        "outfile": "jra_mean_friver_1990_1991.png",
        "label": r"Flux [kg m$^{-2}$ day$^{-1}$]",
        "plot_threshold": 1e-4,
        "vmin": 1e-4,
        "vmax": 1e1,
        "ticks": [
            1e-4, 2e-4, 5e-4,
            1e-3, 2e-3, 5e-3,
            1e-2, 2e-2, 5e-2,
            1e-1, 2e-1, 5e-1,
            1, 2, 5, 10
        ],
        "n_levels": 100,
    },

    "licalvf": {
        "title": "Mean Land Ice Calving Flux JRA55, 1990–1991",
        "outfile": "jra_mean_licalvf_1990_1991.png",
        "label": r"Flux [kg m$^{-2}$ day$^{-1}$]",
        "plot_threshold": 1e-4,
        "vmin": 1e-4,
        "vmax": 1e1,
        "ticks": [
            1e-4, 2e-4, 5e-4,
            1e-3, 2e-3, 5e-3,
            1e-2, 2e-2, 5e-2,
            1e-1, 2e-1, 5e-1,
            1, 2, 5, 10
        ],
        "n_levels": 100,
    },
}

# ============================================================
# Helpers
# ============================================================

def get_nonempty_files(var, years):
    files = []

    for year in years:
        yearly = sorted(JRA_DIR.glob(f"{var}_input4MIPs_*_{year}*.nc"))
        yearly = [f for f in yearly if f.exists() and f.stat().st_size > 0]

        if not yearly:
            raise FileNotFoundError(
                f"No non-empty JRA55 {var} file found for {year}"
            )

        files.extend(yearly)

    return files


def normalize_lon(da):
    return da.assign_coords(
        lon=((da.lon + 180.0) % 360.0) - 180.0
    ).sortby("lon")


def make_cyclic_masked(da):
    data, lon = add_cyclic_point(
        da.values,
        coord=da.lon.values,
        axis=da.get_axis_num("lon")
    )

    data = np.ma.masked_invalid(data)

    return data, lon


def setup_map(ax):
    ax.set_global()
    ax.coastlines(resolution="110m", linewidth=0.7)
    ax.add_feature(cfeature.BORDERS, linewidth=0.3)


# ============================================================
# Style
# ============================================================

sns.set_theme(style="white")
plt.rcParams.update({"font.family": "Nimbus Sans"})

cmap = plt.get_cmap("turbo").copy()
cmap.set_bad("white")

# ============================================================
# Plot
# ============================================================

for var, cfg in PLOT_CONFIG.items():

    print(f"\n{'='*70}")
    print(f"Processing {var}")
    print(f"{'='*70}")

    files = get_nonempty_files(var, YEARS)

    for f in files:
        print(" ", f.name)

    da = xr.open_mfdataset(
        files,
        combine="by_coords",
        chunks={"time": 120},
        data_vars="minimal",
        coords="minimal",
        compat="override",
    )[var]

    print(
        "Raw range [kg m-2 s-1]:",
        float(da.min().compute()),
        "to",
        float(da.max().compute())
    )

    # ========================================================
    # Multi-year mean
    # ========================================================

    print("Computing mean...")

    mean = da.mean("time", skipna=True).compute()

    # kg m-2 s-1 -> kg m-2 day-1
    mean = mean * 86400.0

    mean = normalize_lon(mean)

    # Keep only values above plotting threshold
    mean = mean.where(mean >= cfg["plot_threshold"])

    positive = mean.values[
        np.isfinite(mean.values) & (mean.values > 0)
    ]

    if positive.size == 0:
        raise ValueError(f"{var}: no positive values to plot")

    print(
        "Positive mean range [kg m-2 day-1]:",
        float(np.nanmin(positive)),
        "to",
        float(np.nanmax(positive))
    )

    # Detailed logarithmic scale
    levels = np.geomspace(
        cfg["vmin"],
        cfg["vmax"],
        cfg["n_levels"]
    )

    norm = mcolors.LogNorm(
        vmin=cfg["vmin"],
        vmax=cfg["vmax"]
    )

    # ========================================================
    # Figure
    # ========================================================

    fig = plt.figure(
        figsize=(12, 5.5),
        facecolor="white"
    )

    ax = fig.add_subplot(
        1,
        1,
        1,
        projection=ccrs.PlateCarree()
    )

    data, lon = make_cyclic_masked(mean)

    im = ax.contourf(
        lon,
        mean.lat.values,
        data,
        levels=levels,
        norm=norm,
        cmap=cmap,
        transform=ccrs.PlateCarree(),
        extend="max",
    )

    setup_map(ax)

    ax.set_title(
        cfg["title"],
        fontsize=14,
        fontweight="bold",
        pad=12
    )

    cbar = fig.colorbar(
        im,
        ax=ax,
        orientation="horizontal",
        fraction=0.055,
        pad=0.10,
        aspect=35,
        ticks=cfg["ticks"],
    )

    cbar.set_label(
        cfg["label"],
        fontsize=12,
        labelpad=8
    )

    cbar.ax.tick_params(
        labelsize=9,
        length=4,
        width=1
    )

    cbar.outline.set_visible(False)

    # Scientific notation on log colorbar
    cbar.ax.set_xticklabels([
        r"$10^{-4}$", "", "",
        r"$10^{-3}$", "", "",
        r"$10^{-2}$", "", "",
        r"$10^{-1}$", "", "",
        r"$10^{0}$", "", "", r"$10^{1}$"
    ])

    outfile = FIG_DIR / cfg["outfile"]

    fig.savefig(
        outfile,
        dpi=150,
        bbox_inches="tight"
    )

    plt.close(fig)

    print("Saved:", outfile)

    da.close()

print("\nDONE")