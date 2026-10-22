
#!/usr/bin/env python3
from pathlib import Path
import numpy as np
import xarray as xr
from xgrads import open_CtlDataset
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from cartopy.io import shapereader
from shapely.ops import unary_union

try:
    from shapely import contains_xy
except ImportError:
    from shapely.vectorized import contains as contains_xy

BASE = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access")
JRA = Path("/leonardo_work/ICT26_ESP/ntilinin/INPUT/OMIP")
OUT = BASE / "scripts/figures/IAF_1958_2019"
OUT.mkdir(parents=True, exist_ok=True)

CTL_OLD = BASE / "output/exp_198/attm198.ctl"
CTL_NEW = Path("/leonardo_work/ICT26_ESP/ntilinin/SPEEDY_forcing/exp_197/attm197.ctl")
CTL_V2 = BASE / "output/exp_211/attm211.ctl"

YEARS = range(1958, 2020)
Y0, Y1 = min(YEARS), max(YEARS)
VAR_SPD, VAR_JRA = "SSRD", "rsds"

COLORS = {
    "JRA55-do": "tab:blue",
    "SPEEDY old": "forestgreen",
    "SPEEDY new": "#CD0000",
    "SPEEDY new v2": "#9467BD"
}

plt.rcParams.update({"font.family":"Nimbus Sans", "font.size":11})

def standard_coords(x):
    ren = {}
    for old, new in [("latitude","lat"), ("longitude","lon"), ("y","lat"), ("x","lon")]:
        if (old in x.dims or old in x.coords) and new not in x.dims and new not in x.coords:
            ren[old] = new
    return x.rename(ren) if ren else x

def normlon(x):
    x = standard_coords(x)
    return x.assign_coords(lon=((x.lon+180)%360)-180).sortby("lon").sortby("lat")

def ocean_mask(x, land):
    lon, lat = np.meshgrid(x.lon.values, x.lat.values)
    return xr.DataArray(~contains_xy(land, lon, lat), coords={"lat":x.lat, "lon":x.lon}, dims=("lat","lon"))

def gaussian_weights(x):
    nodes, w = np.polynomial.legendre.leggauss(x.sizes["lat"])
    expected = np.degrees(np.arcsin(nodes))
    actual = np.asarray(x.lat.values)
    if not np.allclose(actual, expected, atol=0.05):
        raise ValueError(f"Latitude grid is not Gaussian (nlat={len(actual)}, max difference={np.max(np.abs(actual-expected)):.4f} deg)")
    return xr.DataArray(w, coords={"lat":x.lat}, dims="lat")

def spatial_mean(x, weights, mask=None):
    if mask is not None: x = x.where(mask)
    return float(x.weighted(weights).mean(("lat","lon")))

def jra_file(year):
    files = sorted(f for f in JRA.glob(
        f"rsds_input4MIPs_atmosphericState_OMIP_MRI-JRA55-do-*_gr_{year}*.nc"
    ) if f.stat().st_size > 0)
    if len(files) != 1: raise ValueError(f"Expected one JRA file for {year}, found {len(files)}")
    return files[0]

def annual_mean(x, year):
    z = x.sel(time=slice(f"{year}-01-01", f"{year}-12-31"))
    if z.sizes["time"] == 0: raise ValueError(f"No data for {year}")
    return z.mean("time").compute()

SPD_FILES = {
    "SPEEDY old": CTL_OLD,
    "SPEEDY new": CTL_NEW,
    "SPEEDY new v2": CTL_V2
}

spd = {}
for name, path in SPD_FILES.items():
    print(f"Opening {name}...", flush=True)
    spd[name] = normlon(open_CtlDataset(str(path))[VAR_SPD].squeeze(drop=True))

shp = shapereader.natural_earth("110m", "physical", "land")
land = unary_union(list(shapereader.Reader(shp).geometries()))

masks = {name:ocean_mask(x.isel(time=0), land) for name,x in spd.items()}
weights = {name:gaussian_weights(x) for name,x in spd.items()}

mask_jra, weights_jra = None, None
years = []
ocean = {"JRA55-do":[], **{name:[] for name in spd}}
global_mean = {"JRA55-do":[], **{name:[] for name in spd}}

for year in YEARS:
    print(f"Processing {year}...", flush=True)

    with xr.open_dataset(jra_file(year), chunks={"time":240}) as ds:
        jra = annual_mean(normlon(ds[VAR_JRA]), year)

    if mask_jra is None:
        mask_jra, weights_jra = ocean_mask(jra, land), gaussian_weights(jra)

    years.append(year)
    ocean["JRA55-do"].append(spatial_mean(jra, weights_jra, mask_jra))
    global_mean["JRA55-do"].append(spatial_mean(jra, weights_jra))

    for name, x in spd.items():
        m = annual_mean(x, year)
        ocean[name].append(spatial_mean(m, weights[name], masks[name]))
        global_mean[name].append(spatial_mean(m, weights[name]))

years = np.array(years)
ocean = {name:np.array(v) for name,v in ocean.items()}
global_mean = {name:np.array(v) for name,v in global_mean.items()}

fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)

for ax, title, data in [(axes[0],"Ocean mean",ocean), (axes[1],"Global mean",global_mean)]:
    for name, values in data.items():
        ax.plot(years, values, lw=1.8, color=COLORS[name], label=name)
    ax.set_title(title, fontweight="bold", pad=10)
    ax.set_ylabel("RSDS [W m$^{-2}$]")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, alpha=0.25, linewidth=0.5)

axes[1].set_xlabel("Year")

fig.suptitle(f"Annual Mean Downward Shortwave Radiation, {Y0}–{Y1}",
             fontsize=15, fontweight="bold", y=.98)

handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(.5,.935),
           ncol=4, frameon=False, fontsize=11, columnspacing=2, handlelength=2.5)

fig.subplots_adjust(left=.09, right=.97, top=.84, bottom=.08, hspace=.30)

filename = f"ocean_global_mean_rsds_speedyold_new_{Y0}_{Y1}.png"
fig.savefig(OUT / filename, dpi=150, bbox_inches="tight")
plt.close(fig)

for title, data in [("OCEAN MEAN",ocean), ("GLOBAL MEAN",global_mean)]:
    print(f"\n{title}, {Y0}–{Y1}")
    for name, values in data.items():
        print(f"{name:16s}: {values.mean():.3f} W/m2")
    for name in spd:
        print(f"BIAS {name:13s} - JRA: {(data[name]-data['JRA55-do']).mean():+.3f} W/m2")

print("\nSaved:", OUT / filename)
print("DONE")
