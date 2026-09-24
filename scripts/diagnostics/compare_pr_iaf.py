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

JRA = Path("/leonardo_work/ICT26_ESP/ntilinin/INPUT/OMIP")
SPD = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/access_forcing/IAF")
OUT = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/scripts/figures/IAF_1958_2019")
OUT.mkdir(parents=True, exist_ok=True)

YEARS = range(1958, 2020)
VARS = {
    "prra": dict(label="Rainfall", levels=np.arange(0, 15.5, .5), ticks=np.arange(0, 16, 2), dlim=5, dticks=np.arange(-5, 6, 1)),
    "prsn": dict(label="Snowfall", levels=np.arange(0, 6.25, .25), ticks=np.arange(0, 6.5, 1), dlim=2, dticks=np.arange(-2, 2.1, .5)),
}

sns.set_theme(style="white")
plt.rcParams.update({"font.family": "Nimbus Sans"})

dcmap = LinearSegmentedColormap.from_list(
    "bwr",
    ["#313695","#4575b4","#74add1","#abd9e9","#e0f3f8","#ffffff",
     "#fee090","#fdae61","#f46d43","#d73027","#a50026"], N=256
)

def normlon(x):
    return x.assign_coords(lon=((x.lon + 180) % 360) - 180).sortby("lon")

def gmean(x):
    _, w = np.polynomial.legendre.leggauss(x.sizes["lat"])
    if x.lat.values[0] > x.lat.values[-1]: w = w[::-1]
    w = xr.DataArray(w, coords={"lat": x.lat}, dims="lat")
    return x.weighted(w).mean(("lat", "lon"))

def cyc(x):
    return add_cyclic_point(x.values, coord=x.lon.values, axis=x.get_axis_num("lon"))

def setup(ax):
    ax.set_global()
    ax.coastlines(resolution="110m", linewidth=.7)
    ax.add_feature(cfeature.BORDERS, linewidth=.3)

def plot_ts(years, a, b, label, var):
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(years, a, lw=1.5, label="JRA55")
    ax.plot(years, b, lw=1.5, label="SPEEDY T30")
    ax.set_title(f"Area-weighted Global-Mean {label}, 1958–2019", fontsize=15, fontweight="bold", pad=10)
    ax.set_xlabel("Year", fontsize=13, labelpad=10)
    ax.set_ylabel(f"{label} [mm/day]", fontsize=13, labelpad=10)
    ax.tick_params(axis="both", direction="out", length=6, width=1.2, labelsize=12)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(1.5)
    ax.spines["bottom"].set_linewidth(1.5)
    ax.legend(frameon=False, fontsize=12)
    fig.tight_layout()
    fig.savefig(OUT/f"global_mean_{var}_1958_2019.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

for var, cfg in VARS.items():
    jsum = ssum = None
    nj = ns = 0
    years, jts, sts = [], [], []

    for y in YEARS:
        jf = next(f for f in sorted(JRA.glob(
            f"{var}_input4MIPs_atmosphericState_OMIP_MRI-JRA55-do-*_gr_{y}*.nc"
        )) if f.stat().st_size > 0)
        sf = SPD / f"{var}_SPEEDY_{y}.nc"
        if not sf.exists(): raise FileNotFoundError(sf)

        with xr.open_dataset(jf, chunks={"time": 240}) as ds:
            x = ds[var]
            n = x.sizes["time"]
            m = x.mean("time", skipna=True).compute()
            jsum = m*n if jsum is None else jsum + m*n
            nj += n
            jts.append(float(gmean(m))*86400)

        with xr.open_dataset(sf, chunks={"time": 240}) as ds:
            x = ds[var]
            n = x.sizes["time"]
            m = x.mean("time", skipna=True).compute()
            ssum = m*n if ssum is None else ssum + m*n
            ns += n
            sts.append(float(gmean(m))*86400)

        years.append(y)
        print(var, y)

    jm = normlon(jsum/nj) * 86400
    sm = normlon(ssum/ns) * 86400
    sext = xr.concat([
        sm.isel(lon=[-1]).assign_coords(lon=[float(sm.lon[-1])-360]),
        sm,
        sm.isel(lon=[0]).assign_coords(lon=[float(sm.lon[0])+360])
    ], dim="lon")
    sj = sext.interp(lat=jm.lat, lon=jm.lon)
    diff = sj - jm

    fig = plt.figure(figsize=(14, 9), facecolor="white")
    gs = fig.add_gridspec(2, 6, height_ratios=[1, 1.3], hspace=.3, wspace=.12)
    ax1 = fig.add_subplot(gs[0, :3], projection=ccrs.PlateCarree())
    ax2 = fig.add_subplot(gs[0, 3:], projection=ccrs.PlateCarree())
    ax3 = fig.add_subplot(gs[1, :], projection=ccrs.PlateCarree())

    for ax, x, title in [
        (ax1, jm, f"Mean {cfg['label']} JRA55, 1958–2019"),
        (ax2, sj, f"Mean {cfg['label']} SPEEDY T30, 1958–2019")
    ]:
        d, lon = cyc(x)
        im = ax.contourf(lon, x.lat, d, levels=cfg["levels"], cmap="turbo",
                         extend="max", transform=ccrs.PlateCarree())
        setup(ax)
        ax.set_title(title, fontsize=14, fontweight="bold", pad=10)

    dlev = np.linspace(-cfg["dlim"], cfg["dlim"], 41)
    d, lon = cyc(diff)
    imd = ax3.contourf(
        lon, diff.lat, d, levels=dlev, cmap=dcmap,
        norm=mcolors.TwoSlopeNorm(vmin=-cfg["dlim"], vcenter=0, vmax=cfg["dlim"]),
        extend="both", transform=ccrs.PlateCarree()
    )
    setup(ax3)
    ax3.set_title("SPEEDY − JRA55", fontsize=14, fontweight="bold", pad=10)

    c1 = fig.colorbar(im, ax=[ax1, ax2], orientation="horizontal",
                      fraction=.045, pad=.07, aspect=40, ticks=cfg["ticks"])
    c1.set_label(f"{cfg['label']} [mm/day]", fontsize=12, labelpad=8)
    c1.ax.tick_params(labelsize=11, length=5, width=1)
    c1.outline.set_visible(False)

    c2 = fig.colorbar(imd, ax=ax3, orientation="horizontal",
                      fraction=.045, pad=.08, aspect=30, ticks=cfg["dticks"])
    c2.set_label("Difference [mm/day]", fontsize=12, labelpad=8)
    c2.ax.tick_params(labelsize=11, length=5, width=1)
    c2.outline.set_visible(False)

    fig.savefig(OUT/f"diff_mean_{var}_1958_2019.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    plot_ts(np.array(years), np.array(jts), np.array(sts), cfg["label"], var)

print("DONE")