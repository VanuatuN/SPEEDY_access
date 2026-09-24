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
from cartopy.io import shapereader
from shapely.ops import unary_union

try:
    from shapely import contains_xy
except ImportError:
    from shapely.vectorized import contains as contains_xy

JRA = Path("/leonardo_work/ICT26_ESP/ntilinin/INPUT/OMIP")
SPD = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/access_forcing/IAF")
OUT = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/scripts/figures/IAF_1958_2019")
OUT.mkdir(parents=True, exist_ok=True)
YEARS = range(1958, 2020)

def normlon(x):
    return x.assign_coords(lon=((x.lon + 180) % 360) - 180).sortby("lon")

def gmean(x, mask=None):
    _, w = np.polynomial.legendre.leggauss(x.sizes["lat"])
    if x.lat.values[0] > x.lat.values[-1]: w = w[::-1]
    w = xr.DataArray(w, coords={"lat": x.lat}, dims="lat")
    return x.where(mask).weighted(w).mean(("lat", "lon")) if mask is not None else x.weighted(w).mean(("lat", "lon"))

def omask(x):
    shp = shapereader.natural_earth("110m", "physical", "land")
    land = unary_union(list(shapereader.Reader(shp).geometries()))
    lon, lat = np.meshgrid(x.lon.values, x.lat.values)
    return xr.DataArray(~contains_xy(land, lon, lat), coords={"lat": x.lat, "lon": x.lon}, dims=("lat", "lon"))

def cyc(x):
    return add_cyclic_point(x.values, coord=x.lon.values, axis=x.get_axis_num("lon"))

def setup(ax):
    ax.set_global()
    ax.coastlines(resolution="110m", linewidth=.7)
    ax.add_feature(cfeature.BORDERS, linewidth=.3)

j_sum = s_sum = None
nj = ns = 0
jm = sm = None
years, jg, sg, jo, so = [], [], [], [], []

for y in YEARS:
    jf = next(f for f in sorted(JRA.glob(
        f"tas_input4MIPs_atmosphericState_OMIP_MRI-JRA55-do-*_gr_{y}*.nc"
    )) if f.stat().st_size > 0)
    sf = SPD / f"tas_SPEEDY_{y}.nc"
    if not sf.exists(): raise FileNotFoundError(sf)

    print(y)

    with xr.open_dataset(jf, chunks={"time": 240}) as ds:
        x = normlon(ds.tas)
        n = x.sizes["time"]
        m = x.mean("time", skipna=True).compute()
        if jm is None: jm = omask(m)
        j_sum = m*n if j_sum is None else j_sum + m*n
        nj += n
        jg.append(float(gmean(m)) - 273.15)
        jo.append(float(gmean(m, jm)) - 273.15)

    with xr.open_dataset(sf, chunks={"time": 240}) as ds:
        x = normlon(ds.tas)
        n = x.sizes["time"]
        m = x.mean("time", skipna=True).compute()
        if sm is None: sm = omask(m)
        s_sum = m*n if s_sum is None else s_sum + m*n
        ns += n
        sg.append(float(gmean(m)) - 273.15)
        so.append(float(gmean(m, sm)) - 273.15)

    years.append(y)

jmean = j_sum / nj - 273.15
smean = s_sum / ns - 273.15
sext = xr.concat([
    smean.isel(lon=[-1]).assign_coords(lon=[float(smean.lon[-1])-360]),
    smean,
    smean.isel(lon=[0]).assign_coords(lon=[float(smean.lon[0])+360])
], dim="lon")
sj = sext.interp(lat=jmean.lat, lon=jmean.lon)
diff = sj - jmean

sns.set_theme(style="white")
plt.rcParams.update({"font.family": "Nimbus Sans"})

tcmap = plt.get_cmap("turbo")
dcmap = LinearSegmentedColormap.from_list(
    "bwr",
    ["#313695","#4575b4","#74add1","#abd9e9","#e0f3f8","#ffffff",
     "#fee090","#fdae61","#f46d43","#d73027","#a50026"], N=256
)
tlev = np.arange(-50, 52.5, 2.5)
dlev = np.arange(-10, 10.5, .5)
tnorm = mcolors.TwoSlopeNorm(vmin=-50, vcenter=0, vmax=50)
dnorm = mcolors.TwoSlopeNorm(vmin=-10, vcenter=0, vmax=10)

fig = plt.figure(figsize=(14, 9), facecolor="white")
gs = fig.add_gridspec(2, 6, height_ratios=[1, 1.3], hspace=.3, wspace=.12)
ax1 = fig.add_subplot(gs[0, :3], projection=ccrs.PlateCarree())
ax2 = fig.add_subplot(gs[0, 3:], projection=ccrs.PlateCarree())
ax3 = fig.add_subplot(gs[1, :], projection=ccrs.PlateCarree())

for ax, x, title in [
    (ax1, jmean, "Mean Near-Surface Air T [°C] JRA55, 1958–2019"),
    (ax2, sj, "Mean Near-Surface Air T [°C] SPEEDY T30, 1958–2019")
]:
    d, lon = cyc(x)
    im = ax.contourf(lon, x.lat, d, levels=tlev, norm=tnorm, cmap=tcmap,
                     transform=ccrs.PlateCarree(), extend="both")
    setup(ax)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=10)

d, lon = cyc(diff)
imd = ax3.contourf(lon, diff.lat, d, levels=dlev, norm=dnorm, cmap=dcmap,
                   transform=ccrs.PlateCarree(), extend="both")
setup(ax3)
ax3.set_title("SPEEDY − JRA55", fontsize=14, fontweight="bold", pad=10)

c1 = fig.colorbar(im, ax=[ax1, ax2], orientation="horizontal",
                  fraction=.045, pad=.07, aspect=40, ticks=np.arange(-50, 51, 10))
c1.set_label("Temperature [°C]", fontsize=12, labelpad=8)
c1.ax.tick_params(labelsize=11, length=5, width=1)
c1.outline.set_visible(False)

c2 = fig.colorbar(imd, ax=ax3, orientation="horizontal",
                  fraction=.045, pad=.08, aspect=30, ticks=np.arange(-10, 11, 2))
c2.set_label("Temperature difference [°C]", fontsize=12, labelpad=8)
c2.ax.tick_params(labelsize=11, length=5, width=1)
c2.outline.set_visible(False)

fig.savefig(OUT/"diff_mean_T_1958_2019.png", dpi=150, bbox_inches="tight")
plt.close(fig)

years = np.array(years)
jg, sg, jo, so = map(np.array, (jg, sg, jo, so))

def plot_ts(a, b, title, name):
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(years, a, lw=1.5, label="JRA55")
    ax.plot(years, b, lw=1.5, label="SPEEDY T30")
    ax.set_title(title, fontsize=15, fontweight="bold", pad=10)
    ax.set_xlabel("Year", fontsize=13, labelpad=10)
    ax.set_ylabel("Temperature [°C]", fontsize=13, labelpad=10)
    ax.tick_params(axis="both", direction="out", length=6, width=1.2, labelsize=12)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(1.5)
    ax.spines["bottom"].set_linewidth(1.5)
    ax.legend(frameon=False, fontsize=12)
    fig.tight_layout()
    fig.savefig(OUT/name, dpi=150, bbox_inches="tight")
    plt.close(fig)

plot_ts(jg, sg, "Area-weighted Global-Mean Near-Surface Air T [°C], 1958–2019",
        "global_mean_T_1958_2019.png")
plot_ts(jo, so, "Area-weighted Global-Mean Near-Surface Air T [°C] over Ocean, 1958–2019",
        "ocean_mean_T_1958_2019.png")

print("DONE")