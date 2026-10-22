
#!/usr/bin/env python3
from pathlib import Path
import numpy as np
import xarray as xr
from xgrads import open_CtlDataset
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.util import add_cyclic_point
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER

BASE = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access")

CTL_OLD = BASE / "output/exp_198/attm198.ctl"
CTL_NEW = BASE / "output/exp_211/attm211.ctl"

JRA = Path("/leonardo_work/ICT26_ESP/ntilinin/INPUT/OMIP")
OUT = BASE / "scripts/figures/IAF_1958_2019"
OUT.mkdir(parents=True, exist_ok=True)

YEARS = range(1958, 2020)
SEASONS = {"DJFM": [12,1,2,3], "JJAS": [6,7,8,9]}
Y0, Y1 = min(YEARS), max(YEARS)

VAR_SPD = "SSRD"
VAR_JRA = "rsds"
DLIM = 60

plt.rcParams.update({"font.family":"Nimbus Sans","font.size":11})

def standard_coords(x):
    ren = {}
    for old, new in [
        ("latitude","lat"),
        ("longitude","lon"),
        ("y","lat"),
        ("x","lon")
    ]:
        if old in x.dims or old in x.coords:
            if new not in x.dims and new not in x.coords:
                ren[old] = new
    return x.rename(ren) if ren else x

def normlon(x):
    x = standard_coords(x)
    return x.assign_coords(
        lon=((x.lon + 180) % 360) - 180
    ).sortby("lon").sortby("lat")

def cyclic(x):
    return add_cyclic_point(x.values, coord=x.lon.values)


def setup(ax):
    ax.set_global()
    ax.coastlines(resolution="110m", linewidth=.7)
    ax.add_feature(cfeature.BORDERS, linewidth=.3)

    # ax.set_xticks(
    #     np.arange(-180, 181, 30),
    #     crs=ccrs.PlateCarree()
    # )

    # ax.set_yticks(
    #     np.arange(-80, 81, 20),
    #     crs=ccrs.PlateCarree()
    # )

    # ax.xaxis.set_major_formatter(LONGITUDE_FORMATTER)
    # ax.yaxis.set_major_formatter(LATITUDE_FORMATTER)

    # ax.tick_params(
    #     axis="both",
    #     labelsize=8,
    #     length=3,
    #     pad=3
    # )

    ax.grid(
        True,
        linewidth=0.5,
        color="gray",
        alpha=0.45,
        linestyle="--"
    )


def jra_file(y):
    files = sorted(JRA.glob(
        f"{VAR_JRA}_input4MIPs_atmosphericState_OMIP_MRI-JRA55-do-*_gr_{y}*.nc"
    ))
    files = [f for f in files if f.stat().st_size > 0]
    if not files:
        raise FileNotFoundError(f"No JRA rsds file for {y}")
    if len(files) > 1:
        raise ValueError(f"Multiple JRA files for {y}: {files}")
    return files[0]

def means_for_year(x, year):
    zyear = x.sel(
        time=slice(f"{year}-01-01", f"{year}-12-31")
    )

    out, cnt = {}, {}

    for season, months in SEASONS.items():
        z = zyear.where(
            zyear.time.dt.month.isin(months),
            drop=True
        )
        cnt[season] = z.sizes["time"]

        if cnt[season] == 0:
            raise ValueError(f"No data for {season}, {year}")

        out[season] = z.mean("time").compute()

    return out, cnt

def interp_to_jra(sp, jr):
    spx = xr.concat([
        sp.isel(lon=[-1]).assign_coords(
            lon=[float(sp.lon.values[-1]) - 360]
        ),
        sp,
        sp.isel(lon=[0]).assign_coords(
            lon=[float(sp.lon.values[0]) + 360]
        )
    ], dim="lon")

    return spx.interp(lat=jr.lat, lon=jr.lon)

print("Opening SPEEDY old...", flush=True)
ds_old = open_CtlDataset(str(CTL_OLD))
sp_old = normlon(ds_old[VAR_SPD].squeeze(drop=True))

print("Opening SPEEDY new v2...", flush=True)
ds_new = open_CtlDataset(str(CTL_NEW))
sp_new = normlon(ds_new[VAR_SPD].squeeze(drop=True))

sum_old = {s:None for s in SEASONS}
sum_new = {s:None for s in SEASONS}
sum_jra = {s:None for s in SEASONS}

cnt_old = {s:0 for s in SEASONS}
cnt_new = {s:0 for s in SEASONS}
cnt_jra = {s:0 for s in SEASONS}

for y in YEARS:
    print(y, flush=True)

    old, co = means_for_year(sp_old, y)
    new, cn = means_for_year(sp_new, y)

    with xr.open_dataset(
        jra_file(y),
        chunks={"time":240}
    ) as ds:
        jr = normlon(ds[VAR_JRA])
        jra, cj = means_for_year(jr, y)

    for s in SEASONS:
        sum_old[s] = (
            old[s]*co[s] if sum_old[s] is None
            else sum_old[s]+old[s]*co[s]
        )
        sum_new[s] = (
            new[s]*cn[s] if sum_new[s] is None
            else sum_new[s]+new[s]*cn[s]
        )
        sum_jra[s] = (
            jra[s]*cj[s] if sum_jra[s] is None
            else sum_jra[s]+jra[s]*cj[s]
        )

        cnt_old[s] += co[s]
        cnt_new[s] += cn[s]
        cnt_jra[s] += cj[s]

oldm = {s:sum_old[s]/cnt_old[s] for s in SEASONS}
newm = {s:sum_new[s]/cnt_new[s] for s in SEASONS}
jram = {s:sum_jra[s]/cnt_jra[s] for s in SEASONS}

d_old = {
    s:newm[s]-oldm[s]
    for s in SEASONS
}

d_jra = {
    s:interp_to_jra(newm[s],jram[s])-jram[s]
    for s in SEASONS
}

levels = np.arange(-DLIM, DLIM+5, 5)
norm = mcolors.TwoSlopeNorm(
    vmin=-DLIM,
    vcenter=0,
    vmax=DLIM
)

fig,axes=plt.subplots(2,2,figsize=(14,8),
                      subplot_kw={"projection":ccrs.PlateCarree()})

fig,axes=plt.subplots(2,2,figsize=(14,8),
                      subplot_kw={"projection":ccrs.PlateCarree()})

for i,s in enumerate(["DJFM","JJAS"]):
    for j,(da,ttl) in enumerate([
        (d_old[s],"SPEEDY new v2 − SPEEDY old"),
        (d_jra[s],"SPEEDY new v2 − JRA55-do")
    ]):
        ax=axes[i,j]
        data,lon=cyclic(da)

        im=ax.contourf(
            lon,da.lat,data,
            levels=levels,
            cmap="RdBu_r",
            norm=norm,
            extend="both",
            transform=ccrs.PlateCarree()
        )

        setup(ax)
        ax.set_title(
            f"{s}\n{ttl}",
            fontweight="bold",
            pad=6
        )

fig.subplots_adjust(left=.03,right=.99,top=.90,bottom=.17,
                    wspace=.08,hspace=.16)

cax=fig.add_axes([.24,.035,.52,.025])
cbar=fig.colorbar(
    im,
    cax=cax,
    orientation="horizontal",
    ticks=np.arange(-DLIM,DLIM+1,20)
)
cbar.set_label("RSDS difference [W m$^{-2}$]")
cbar.outline.set_visible(False)

fig.suptitle(
    f"Seasonal mean downward shortwave radiation differences, {Y0}-{Y1}",
    fontsize=15,fontweight="bold",y=.97
)

fig.tight_layout(rect=[0, 0.06, 1, 0.95])

fig.savefig(
    OUT / f"maps_{VAR_JRA}_diff_speedyold_v2_DJFM_JJAS_{Y0}_{Y1}.png",
    dpi=150,
    bbox_inches="tight"
)

plt.close(fig)

print("DONE")
