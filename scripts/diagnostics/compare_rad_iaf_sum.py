#!/usr/bin/env python3
from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.colors import LinearSegmentedColormap
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

levels = np.arange(200, 751, 20)
ticks = np.arange(200, 751, 100)
dlim = 100

plt.rcParams.update({"font.family": "Nimbus Sans", "font.size": 11})
diff_cmap = LinearSegmentedColormap.from_list(
    "diff", ["#313695","#4575b4","#74add1","#abd9e9","#e0f3f8","#ffffff",
             "#fee090","#fdae61","#f46d43","#d73027","#a50026"], N=256
)

def normlon(x):
    return x.assign_coords(lon=((x.lon + 180) % 360) - 180).sortby("lon")

def cyclic(x):
    return add_cyclic_point(x.values, coord=x.lon.values)

def gmean(x, mask=None):
    _, w = np.polynomial.legendre.leggauss(x.sizes["lat"])
    if x.lat[0] > x.lat[-1]:
        w = w[::-1]
    w = xr.DataArray(w, coords={"lat": x.lat}, dims="lat")
    if mask is not None:
        x = x.where(mask)
    return x.weighted(w).mean(("lat", "lon"))

def ocean_mask(x):
    shp = shapereader.natural_earth("110m", "physical", "land")
    land = unary_union(list(shapereader.Reader(shp).geometries()))
    lon, lat = np.meshgrid(x.lon.values, x.lat.values)
    return xr.DataArray(~contains_xy(land, lon, lat),
                        coords={"lat": x.lat, "lon": x.lon},
                        dims=("lat", "lon"))

def setup(ax):
    ax.set_global()
    ax.coastlines(resolution="110m", linewidth=.7)
    ax.add_feature(cfeature.BORDERS, linewidth=.3)

jsum = ssum = None
nj = ns = 0
years, jts, sts = [], [], []
jmask = smask = None

for y in YEARS:
    jrlds = next(f for f in sorted(JRA.glob(f"rlds_input4MIPs_atmosphericState_OMIP_MRI-JRA55-do-*_gr_{y}*.nc")) if f.stat().st_size > 0)
    jrsds = next(f for f in sorted(JRA.glob(f"rsds_input4MIPs_atmosphericState_OMIP_MRI-JRA55-do-*_gr_{y}*.nc")) if f.stat().st_size > 0)
    srlds = SPD / f"rlds_SPEEDY_{y}.nc"
    srsds = SPD / f"rsds_SPEEDY_{y}.nc"

    print(y)

    with xr.open_dataset(jrlds, chunks={"time": 240}) as dlw, \
         xr.open_dataset(jrsds, chunks={"time": 240}) as dsw:
        lw, sw = xr.align(dlw.rlds, dsw.rsds, join="inner")
        x = normlon(lw + sw)
        n = x.sizes["time"]
        m = x.mean("time").compute()
        if jmask is None:
            jmask = ocean_mask(m)
        jsum = m*n if jsum is None else jsum + m*n
        nj += n
        jts.append(float(gmean(m, jmask)))

    with xr.open_dataset(srlds, chunks={"time": 240}) as dlw, \
         xr.open_dataset(srsds, chunks={"time": 240}) as dsw:
        lw, sw = xr.align(dlw.rlds, dsw.rsds, join="inner")
        x = normlon(lw + sw)
        n = x.sizes["time"]
        m = x.mean("time").compute()
        if smask is None:
            smask = ocean_mask(m)
        ssum = m*n if ssum is None else ssum + m*n
        ns += n
        sts.append(float(gmean(m, smask)))

    years.append(y)

jm = jsum / nj
sm = ssum / ns

smx = xr.concat([
    sm.isel(lon=[-1]).assign_coords(lon=[float(sm.lon[-1]) - 360]),
    sm,
    sm.isel(lon=[0]).assign_coords(lon=[float(sm.lon[0]) + 360])
], dim="lon")

sj = smx.interp(lat=jm.lat, lon=jm.lon)
diff = sj - jm

fig = plt.figure(figsize=(14, 9), facecolor="white")
gs = fig.add_gridspec(2, 6, height_ratios=[1, 1.3], hspace=.32, wspace=.12)
ax1 = fig.add_subplot(gs[0, :3], projection=ccrs.PlateCarree())
ax2 = fig.add_subplot(gs[0, 3:], projection=ccrs.PlateCarree())
ax3 = fig.add_subplot(gs[1, :], projection=ccrs.PlateCarree())

for ax, da, title in [
    (ax1, jm, "JRA55 Downward Radiation, 1958–2019"),
    (ax2, sj, "SPEEDY Downward Radiation, 1958–2019"),
]:
    data, lon = cyclic(da)
    im = ax.contourf(
        lon, da.lat, data,
        levels=levels, cmap="turbo",
        transform=ccrs.PlateCarree(),
        extend="both"
    )
    setup(ax)
    ax.set_title(title, fontweight="bold", pad=10)

dlevels = np.arange(-dlim, dlim + 5, 5)
data, lon = cyclic(diff)

imd = ax3.contourf(
    lon, diff.lat, data,
    levels=dlevels,
    norm=mcolors.TwoSlopeNorm(vmin=-dlim, vcenter=0, vmax=dlim),
    cmap=diff_cmap,
    transform=ccrs.PlateCarree(),
    extend="both"
)

setup(ax3)
ax3.set_title("SPEEDY − JRA55", fontweight="bold", pad=10)

c1 = fig.colorbar(
    im, ax=[ax1, ax2],
    orientation="horizontal",
    fraction=.045, pad=.07,
    aspect=40, ticks=ticks
)
c1.set_label("RLDS + RSDS [W m$^{-2}$]")
c1.outline.set_visible(False)

c2 = fig.colorbar(
    imd, ax=ax3,
    orientation="horizontal",
    fraction=.045, pad=.08,
    aspect=30,
    ticks=np.arange(-dlim, dlim + 1, 20)
)
c2.set_label("RLDS + RSDS difference [W m$^{-2}$]")
c2.outline.set_visible(False)

fig.savefig(
    OUT / "diff_mean_radiation_1958_2019_co2.png",
    dpi=150, bbox_inches="tight"
)
plt.close(fig)

years = np.array(years)
jts = np.array(jts)
sts = np.array(sts)

fig, ax = plt.subplots(figsize=(12, 5))

ax.plot(years, jts, lw=1.8, label="JRA55")
ax.plot(years, sts, lw=1.8, label="SPEEDY")

ax.set_title(
    "Annual Ocean-Mean Downward Radiation, 1958–2019",
    fontweight="bold", pad=10
)
ax.set_xlabel("Year")
ax.set_ylabel("RLDS + RSDS [W m$^{-2}$]")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.legend(frameon=False)

fig.tight_layout()
fig.savefig(
    OUT / "ocean_mean_radiation_1958_2019_co2.png",
    dpi=150, bbox_inches="tight"
)
plt.close(fig)

print("\nRLDS + RSDS ocean mean")
print("JRA55 :", jts.mean())
print("SPEEDY:", sts.mean())
print("BIAS  :", (sts-jts).mean())
print("\nDONE")