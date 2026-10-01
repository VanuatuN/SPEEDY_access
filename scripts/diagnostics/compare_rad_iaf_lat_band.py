#!/usr/bin/env python3
from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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
SEASONS = {"JJAS": [6,7,8,9], "DJFM": [12,1,2,3]}

plt.rcParams.update({"font.family":"Nimbus Sans","font.size":12})

def normlon(x):
    return x.assign_coords(lon=((x.lon+180)%360)-180).sortby("lon")

def ocean_mask(x):
    shp = shapereader.natural_earth("110m","physical","land")
    land = unary_union(list(shapereader.Reader(shp).geometries()))
    lon,lat = np.meshgrid(x.lon.values,x.lat.values)
    return xr.DataArray(
        ~contains_xy(land,lon,lat),
        coords={"lat":x.lat,"lon":x.lon},
        dims=("lat","lon")
    )

def jra_file(y):
    return next(
        f for f in sorted(JRA.glob(
            f"rsds_input4MIPs_atmosphericState_OMIP_MRI-JRA55-do-*_gr_{y}*.nc"
        )) if f.stat().st_size>0
    )

def yearly_means(path,var):
    with xr.open_dataset(path,chunks={"time":240}) as ds:
        x = normlon(ds[var])
        counts = {
            season:int(np.count_nonzero(np.isin(x.time.dt.month.values,months)))
            for season,months in SEASONS.items()
        }
        out = xr.Dataset({
            season:x.where(x.time.dt.month.isin(months),drop=True).mean("time")
            for season,months in SEASONS.items()
        }).compute()
    return out,counts

sum_jg = {s:None for s in SEASONS}
sum_sg = {s:None for s in SEASONS}
sum_jo = {s:None for s in SEASONS}
sum_so = {s:None for s in SEASONS}
nj = {s:0 for s in SEASONS}
ns = {s:0 for s in SEASONS}

jmask = smask = None

for y in YEARS:
    print(y,flush=True)

    jm,jcount = yearly_means(jra_file(y),"rsds")
    sm,scount = yearly_means(SPD/f"rsds_SPEEDY_{y}.nc","rsds")

    if jmask is None:
        jmask = ocean_mask(jm["JJAS"])
        smask = ocean_mask(sm["JJAS"])

    for season in SEASONS:
        jg = jm[season].mean("lon")
        sg = sm[season].mean("lon")
        jo = jm[season].where(jmask).mean("lon",skipna=True)
        so = sm[season].where(smask).mean("lon",skipna=True)

        a = jcount[season]
        b = scount[season]

        sum_jg[season] = jg*a if sum_jg[season] is None else sum_jg[season]+jg*a
        sum_sg[season] = sg*b if sum_sg[season] is None else sum_sg[season]+sg*b
        sum_jo[season] = jo*a if sum_jo[season] is None else sum_jo[season]+jo*a
        sum_so[season] = so*b if sum_so[season] is None else sum_so[season]+so*b

        nj[season] += a
        ns[season] += b

res = {"Global":{},"Ocean":{}}

for season in SEASONS:
    res["Global"][season] = (
        sum_jg[season]/nj[season],
        sum_sg[season]/ns[season]
    )
    res["Ocean"][season] = (
        sum_jo[season]/nj[season],
        sum_so[season]/ns[season]
    )

for domain in ["Global","Ocean"]:
    fig,axes = plt.subplots(1,2,figsize=(14,5),sharey=True)

    for ax,season in zip(axes,["JJAS","DJFM"]):
        j,s = res[domain][season]

        ax.plot(j.lat,j,lw=2.5,label="JRA55")
        ax.plot(s.lat,s,lw=2.5,label="SPEEDY")
        ax.set_title(season,fontweight="bold",fontsize=14)
        ax.set_xlabel("Latitude")
        ax.grid(alpha=.25)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    axes[0].set_ylabel("RSDS [W m$^{-2}$]")
    axes[0].legend(frameon=False)
    fig.suptitle(
        f"{domain} zonal-mean SSR, 1958–2019",
        fontsize=15,fontweight="bold"
    )
    fig.tight_layout()

    fig.savefig(
        OUT/f"zonal_rsds_{domain.lower()}_JJAS_DJFM_1958_2019.png",
        dpi=150,bbox_inches="tight"
    )
    plt.close(fig)

print("DONE")