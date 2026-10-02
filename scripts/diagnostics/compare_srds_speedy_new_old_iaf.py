#!/usr/bin/env python3
from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.util import add_cyclic_point

JRA = Path("/leonardo_work/ICT26_ESP/ntilinin/INPUT/OMIP")
SPD_OLD = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/access_forcing/IAF/SR_npar")
SPD_NEW = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/access_forcing/IAF/SR_par")
OUT = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/scripts/figures/IAF_1958_2019")
OUT.mkdir(parents=True, exist_ok=True)

YEARS = range(1958, 2020)
SEASONS = {"DJFM":[12,1,2,3], "JJAS":[6,7,8,9]}
Y0, Y1 = YEARS.start, YEARS.stop - 1
VAR = "rsds"
DLIM = 60

plt.rcParams.update({"font.family":"Nimbus Sans","font.size":11})

def normlon(x):
    return x.assign_coords(lon=((x.lon + 180) % 360) - 180).sortby("lon")

def cyclic(x):
    return add_cyclic_point(x.values, coord=x.lon.values)

def setup(ax):
    ax.set_global()
    ax.coastlines(resolution="110m", linewidth=.7)
    ax.add_feature(cfeature.BORDERS, linewidth=.3)

def jra_file(y):
    return next(
        f for f in sorted(JRA.glob(f"{VAR}_input4MIPs_atmosphericState_OMIP_MRI-JRA55-do-*_gr_{y}*.nc"))
        if f.stat().st_size > 0
    )

def speedy_file(base, y):
    return base / f"{VAR}_SPEEDY_{y}.nc"

def means_3h(path, var):
    with xr.open_dataset(path, chunks={"time":240}) as ds:
        x = normlon(ds[var])
        out, cnt = {}, {}
        for season, months in SEASONS.items():
            z = x.where(x.time.dt.month.isin(months), drop=True)
            cnt[season] = z.sizes["time"]
            out[season] = z.mean("time")
        return xr.Dataset(out).compute(), cnt

def interp_to_jra(sp, jr):
    spx = xr.concat([
        sp.isel(lon=[-1]).assign_coords(lon=[float(sp.lon[-1]) - 360]),
        sp,
        sp.isel(lon=[0]).assign_coords(lon=[float(sp.lon[0]) + 360])
    ], dim="lon")
    return spx.interp(lat=jr.lat, lon=jr.lon)

sum_old = {s:None for s in SEASONS}
sum_new = {s:None for s in SEASONS}
sum_jra = {s:None for s in SEASONS}
cnt_old = {s:0 for s in SEASONS}
cnt_new = {s:0 for s in SEASONS}
cnt_jra = {s:0 for s in SEASONS}

for y in YEARS:
    print(y, flush=True)

    old, co = means_3h(speedy_file(SPD_OLD, y), VAR)
    new, cn = means_3h(speedy_file(SPD_NEW, y), VAR)
    jra, cj = means_3h(jra_file(y), VAR)

    for s in SEASONS:
        sum_old[s] = old[s] * co[s] if sum_old[s] is None else sum_old[s] + old[s] * co[s]
        sum_new[s] = new[s] * cn[s] if sum_new[s] is None else sum_new[s] + new[s] * cn[s]
        sum_jra[s] = jra[s] * cj[s] if sum_jra[s] is None else sum_jra[s] + jra[s] * cj[s]
        cnt_old[s] += co[s]
        cnt_new[s] += cn[s]
        cnt_jra[s] += cj[s]

oldm = {s: sum_old[s] / cnt_old[s] for s in SEASONS}
newm = {s: sum_new[s] / cnt_new[s] for s in SEASONS}
jram = {s: sum_jra[s] / cnt_jra[s] for s in SEASONS}

d_old = {s: newm[s] - oldm[s] for s in SEASONS}
d_jra = {s: interp_to_jra(newm[s], jram[s]) - jram[s] for s in SEASONS}

DLIM=60
levels=np.arange(-DLIM,DLIM+5,5)
norm=mcolors.TwoSlopeNorm(vmin=-DLIM,vcenter=0,vmax=DLIM)

fig,axes=plt.subplots(2,2,figsize=(14,8),
                      subplot_kw={"projection":ccrs.PlateCarree()})

fig,axes=plt.subplots(2,2,figsize=(14,8),
                      subplot_kw={"projection":ccrs.PlateCarree()})

for i,s in enumerate(["DJFM","JJAS"]):
    for j,(da,ttl) in enumerate([
        (d_old[s],"SPEEDY new − SPEEDY old"),
        (d_jra[s],"SPEEDY new − JRA55")
    ]):
        ax=axes[i,j]
        data,lon=cyclic(da)
        im=ax.contourf(lon,da.lat,data,levels=levels,cmap="RdBu_r",
                       norm=norm,extend="both",transform=ccrs.PlateCarree())
        setup(ax)
        ax.set_title(f"{s}\n{ttl}",fontweight="bold",pad=6)

fig.subplots_adjust(left=.03,right=.99,top=.90,bottom=.17,
                    wspace=.08,hspace=.16)

cax=fig.add_axes([.24,.035,.52,.025])
cbar=fig.colorbar(im,cax=cax,orientation="horizontal",
                  ticks=np.arange(-DLIM,DLIM+1,20))
cbar.set_label("RSDS difference [W m$^{-2}$]")
cbar.outline.set_visible(False)

fig.suptitle(
    f"Seasonal mean downward shortwave radiation differences, {Y0}-{Y1}",
    fontsize=15,fontweight="bold",y=.97
)

fig.tight_layout(rect=[0, 0.06, 1, 0.95])

fig.savefig(
    OUT / f"maps_{VAR}_diff_speedyold_jra_DJFM_JJAS_{Y0}_{Y1}.png",
    dpi=150, bbox_inches="tight"
)
plt.close(fig)

print("DONE")