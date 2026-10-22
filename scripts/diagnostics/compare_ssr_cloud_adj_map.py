from pathlib import Path
import numpy as np
import xarray as xr
from xgrads import open_CtlDataset
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.util import add_cyclic_point
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER

CTL = "/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/output/exp_211/attm211.ctl"
JRA=Path("/leonardo_work/ICT26_ESP/ntilinin/INPUT/OMIP")
OUT = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/scripts/figures/IAF_1958_2019")
YEARS=range(1958,2019)
YEAR_START = min(YEARS)
YEAR_END = max(YEARS)
SEASONS={"DJFM":[12,1,2,3],"JJAS":[6,7,8,9]}
DLIM=60

def standard_coords(x):
    ren={}
    for old,new in [("latitude","lat"),("longitude","lon"),("y","lat"),("x","lon")]:
        if old in x.dims or old in x.coords:
            ren[old]=new
    return x.rename(ren) if ren else x

def normlon(x):
    x=standard_coords(x)
    return x.assign_coords(lon=((x.lon+180)%360)-180).sortby("lon")

def seasonal(x):
    out={}
    for s,months in SEASONS.items():
        z=x.where(x.time.dt.month.isin(months),drop=True)
        out[s]=normlon(z.mean("time").compute())
    return out

sp=open_CtlDataset(str(CTL))["SSRD"]
sp = sp.sel(time=slice(f"{YEAR_START}-01-01", f"{YEAR_END}-12-31"))

jra_files=[]
for y in YEARS:
    files=sorted(JRA.glob(
        f"rsds_input4MIPs_atmosphericState_OMIP_MRI-JRA55-do-1-5-0_gr_{y}*.nc"
    ))
    if not files:
        raise FileNotFoundError(f"No JRA rsds file for {y}")
    jra_files.extend(files)

jra=xr.open_mfdataset(
    jra_files,
    combine="by_coords",
    chunks={"time":120},
    data_vars="minimal",
    coords="minimal",
    compat="override"
)["rsds"]

spm=seasonal(sp)
jram=seasonal(jra)

diff={}
for s in SEASONS:
    spi=spm[s].interp(lat=jram[s].lat,lon=jram[s].lon)
    diff[s]=spi-jram[s]

def cyclic(x):
    z,lon=add_cyclic_point(x.values,coord=x.lon.values)
    return z,lon

def setup(ax):
    ax.set_global()
    ax.coastlines(resolution="110m", linewidth=.6)
    ax.add_feature(cfeature.BORDERS, linewidth=.25)

    gl = ax.gridlines(
        crs=ccrs.PlateCarree(),
        draw_labels=True,
        linewidth=0.5,
        color="gray",
        alpha=0.45,
        linestyle="--",
        xlocs=np.arange(-180, 181, 30),
        ylocs=np.arange(-80, 81, 20)
    )

    gl.top_labels = False
    gl.right_labels = False

    gl.bottom_labels = True
    gl.left_labels = True

    gl.xformatter = LONGITUDE_FORMATTER
    gl.yformatter = LATITUDE_FORMATTER

    gl.xlabel_style = {"size": 8, "color": "black"}
    gl.ylabel_style = {"size": 8, "color": "black"}

    gl.xpadding = 3
    gl.ypadding = 3
    
levels=np.arange(-DLIM,DLIM+5,5)
norm=mcolors.TwoSlopeNorm(vmin=-DLIM,vcenter=0,vmax=DLIM)

fig,axes=plt.subplots(
    2,1,
    figsize=(10,8),
    subplot_kw={"projection":ccrs.PlateCarree()}
)

for ax,s in zip(axes,["DJFM","JJAS"]):
    data,lon=cyclic(diff[s])

    im=ax.contourf(
        lon,diff[s].lat,data,
        levels=levels,
        cmap="RdBu_r",
        norm=norm,
        extend="both",
        transform=ccrs.PlateCarree()
    )

    setup(ax)
    ax.set_title(
        f"{s} — SPEEDY cloud experiment − JRA55-do",
        fontweight="bold",
        pad=6
    )

fig.subplots_adjust(
    left=.09, right=.98, top=.91, bottom=.13,
    hspace=.24
)

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
    f"Downward shortwave radiation difference, {YEAR_START}–{YEAR_END}",
    fontsize=15,
    fontweight="bold",
    y=.97
)

fig.savefig(
    OUT / f"maps_rsds_cloudexp_jra_DJFM_JJAS_{YEAR_START}_{YEAR_END}_fred_sig_45N.png",
    dpi=150,
    bbox_inches="tight"
)
plt.close(fig)