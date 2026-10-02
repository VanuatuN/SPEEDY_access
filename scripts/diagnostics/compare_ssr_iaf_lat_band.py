#!/usr/bin/env python3
from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from xgrads import open_CtlDataset
from cartopy.io import shapereader
from shapely.ops import unary_union

try:
    from shapely import contains_xy
except ImportError:
    from shapely.vectorized import contains as contains_xy

SPD_OLD_CTL = "/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/output/exp_198/attm198.ctl"
SPD_NEW_CTL = "/leonardo_work/ICT26_ESP/ntilinin/SPEEDY_forcing/exp_197/attm197.ctl"
ERA = Path("/leonardo_work/ICT26_ESP/ntilinin/ERA5/")
OUT = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/scripts/figures/IAF_1958_2019")
OUT.mkdir(parents=True, exist_ok=True)

YEARS = range(1958, 2021)
SEASONS = {"JJAS":[6,7,8,9], "DJFM":[12,1,2,3]}
Y0 = YEARS.start
Y1 = YEARS.stop - 1

VAR = "SSR"
ERA_VAR = "avg_snswrf"
VVAR = "surface net shortwave radiation"

plt.rcParams.update({"font.family":"Nimbus Sans","font.size":12})

def normlon(x):
    return x.assign_coords(lon=((x.lon+180)%360)-180).sortby("lon")

def standard_coords(x):
    ren = {}
    if "latitude" in x.dims:
        ren["latitude"] = "lat"
    if "longitude" in x.dims:
        ren["longitude"] = "lon"
    if "valid_time" in x.dims:
        ren["valid_time"] = "time"
    return x.rename(ren)

def ocean_mask(x):
    shp = shapereader.natural_earth("110m","physical","land")
    land = unary_union(list(shapereader.Reader(shp).geometries()))
    lon,lat = np.meshgrid(x.lon.values,x.lat.values)
    return xr.DataArray(
        ~contains_xy(land,lon,lat),
        coords={"lat":x.lat,"lon":x.lon},
        dims=("lat","lon")
    )

def era_file(y):
    return ERA / f"era5_sw_{y}.nc"

def means_speedy(ds,y):
    x = normlon(standard_coords(ds[VAR]))
    x = x.where(x.time.dt.year==y,drop=True)

    counts = {}
    out = {}

    for season,months in SEASONS.items():
        z = x.where(x.time.dt.month.isin(months),drop=True)
        counts[season] = z.sizes["time"]
        out[season] = z.mean("time")

    return xr.Dataset(out).compute(), counts

def means_era(path):
    with xr.open_dataset(path) as ds:
        x = normlon(standard_coords(ds[ERA_VAR]))
        counts = {}
        out = {}

        for season,months in SEASONS.items():
            z = x.where(x.time.dt.month.isin(months),drop=True)
            counts[season] = z.sizes["time"]
            out[season] = z.mean("time")

        return xr.Dataset(out).compute(), counts

print("Opening SPEEDY old")
spd_old = open_CtlDataset(SPD_OLD_CTL)

print("Opening SPEEDY new")
spd_new = open_CtlDataset(SPD_NEW_CTL)

print("OLD SSR:",spd_old[VAR])
print("NEW SSR:",spd_new[VAR])

names = ["ERA5","SPEEDY old","SPEEDY new"]

colors = {
    "ERA5": "darkorange",
    "SPEEDY old": "forestgreen",
    "SPEEDY new": "#CD0000",
}
sum_g = {n:{s:None for s in SEASONS} for n in names}
sum_o = {n:{s:None for s in SEASONS} for n in names}
count = {n:{s:0 for s in SEASONS} for n in names}
masks = {n:None for n in names}

for y in YEARS:
    print(y,flush=True)

    data = {
        "ERA5": means_era(era_file(y)),
        "SPEEDY old": means_speedy(spd_old,y),
        "SPEEDY new": means_speedy(spd_new,y),
    }

    for name,(ds,cnt) in data.items():
        if masks[name] is None:
            masks[name] = ocean_mask(ds["JJAS"])

        for season in SEASONS:
            g = ds[season].mean("lon")
            o = ds[season].where(masks[name]).mean("lon",skipna=True)
            n = cnt[season]

            sum_g[name][season] = g*n if sum_g[name][season] is None else sum_g[name][season]+g*n
            sum_o[name][season] = o*n if sum_o[name][season] is None else sum_o[name][season]+o*n
            count[name][season] += n

res = {"Global":{},"Ocean":{}}

for domain,sums in [("Global",sum_g),("Ocean",sum_o)]:
    for season in SEASONS:
        res[domain][season] = {
            name:sums[name][season]/count[name][season]
            for name in names
        }

for domain in ["Global","Ocean"]:
    fig,axes = plt.subplots(1,2,figsize=(14,5),sharey=True)

    for ax,season in zip(axes,["JJAS","DJFM"]):
        for name in names:
            x = res[domain][season][name]
            ax.plot(x.lat,x,lw=1.8,label=name,color=colors[name])

        ax.set_title(season,fontweight="bold",fontsize=14)
        ax.set_xlabel("Latitude")
        ax.set_xlim(-90,90)
        ax.grid(alpha=.25)
        ax.spines["top"].set_visible(True)
        ax.spines["right"].set_visible(True)

    axes[0].set_ylabel(f"{VAR} [W m$^{{-2}}$]")
    axes[0].legend(frameon=False)

    fig.suptitle(
        f"{domain} zonal-mean {VVAR}, {Y0}-{Y1}",
        fontsize=15,fontweight="bold"
    )

    fig.tight_layout()

    fig.savefig(
        OUT/f"zonal_{VAR.lower()}_{domain.lower()}_JJAS_DJFM_{Y0}_{Y1}.png",
        dpi=150,bbox_inches="tight"
    )

    plt.close(fig)

print("DONE")