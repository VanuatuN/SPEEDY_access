#!/usr/bin/env python3

from pathlib import Path
import gc, calendar, time
import numpy as np
import xarray as xr
from xgrads import open_CtlDataset

SOURCE_CTL = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/output/exp_195/attm195.ctl")
OUT_DIR = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/access_forcing/IAF/")

START_YEAR = 1958
END_YEAR = 2025

VARMAP = {"U0": "uas", "V0": "vas", "MSLP": "psl"}

SHIFT_LONGITUDE_TO_MINUS180_180 = False
SORT_LATITUDE_NORTH_TO_SOUTH = False
SKIP_EXISTING = False


VAR_ATTRS = {
    "uas": {
        "standard_name": "eastward_wind",
        "long_name": "Near-surface eastward wind",
        "units": "m s-1",
        "cell_methods": "area: mean time: point",
        "source_variable": "U0",
        "source_model": "SPEEDY",
        "mapping_note": "SPEEDY U0 -> ACCESS-OM2 uas",
    },
    "vas": {
        "standard_name": "northward_wind",
        "long_name": "Near-surface northward wind",
        "units": "m s-1",
        "cell_methods": "area: mean time: point",
        "source_variable": "V0",
        "source_model": "SPEEDY",
        "mapping_note": "SPEEDY V0 -> ACCESS-OM2 vas",
    },
    "psl": {
        "standard_name": "air_pressure_at_mean_sea_level",
        "long_name": "Mean sea level pressure",
        "units": "Pa",
        "cell_methods": "area: mean time: point",
        "source_variable": "MSLP",
        "source_model": "SPEEDY",
        "mapping_note": "SPEEDY MSLP converted from hPa to Pa",
    },
}

GLOBAL_ATTRS = {
    "Conventions": "CF-1.7",
    "title": "SPEEDY forcing for ACCESS-OM2",
    "source": "SPEEDY model output",
    "frequency": "3hrPt",
    "history": "Created from SPEEDY U0, V0 and MSLP",
    "comment": "3-hourly Gregorian forcing. Leap-day values are linearly interpolated from surrounding SPEEDY data.",
}


def expected_records(year):
    return 2928 if calendar.isleap(year) else 2920


def validate_source_time(ds, year):
    times = ds.time.values
    dt = np.diff(times) / np.timedelta64(1, "h")

    if ds.sizes["time"] != 2920:
        raise ValueError(f"{year}: expected 2920 SPEEDY records, got {ds.sizes['time']}")

    bad = np.where(dt != 3)[0]

    if not calendar.isleap(year):
        if len(bad):
            raise ValueError(f"{year}: unexpected time intervals {np.unique(dt)} h")
        return

    if len(bad) != 1:
        raise ValueError(f"{year}: expected one leap-day gap, found {len(bad)}")

    i = bad[0]
    s0 = np.datetime_as_string(times[i], unit="h")
    s1 = np.datetime_as_string(times[i + 1], unit="h")

    if not (s0.endswith("02-28T21") and s1.endswith("03-01T00") and dt[i] == 27):
        raise ValueError(f"{year}: unexpected leap gap {s0} -> {s1} = {dt[i]} h")

    print(f"{year}: SPEEDY leap gap found: {s0} -> {s1}", flush=True)


def add_leap_day(ds, year):
    if not calendar.isleap(year):
        return ds

    target_time = np.arange(
        np.datetime64(f"{year}-01-01T00:00"),
        np.datetime64(f"{year + 1}-01-01T00:00"),
        np.timedelta64(3, "h"),
    )

    ds = ds.interp(time=target_time)
    for var in VARMAP.values():
        ds[var] = ds[var].astype("float32")

    feb29 = (ds.time.dt.month == 2) & (ds.time.dt.day == 29)
    if int(feb29.sum()) != 8:
        raise ValueError(f"{year}: expected 8 records on Feb 29, got {int(feb29.sum())}")

    print(f"{year}: inserted 8 records for Feb 29", flush=True)
    return ds


def validate_final_time(ds, year):
    dt = np.diff(ds.time.values) / np.timedelta64(1, "h")
    expected = expected_records(year)

    if ds.sizes["time"] != expected:
        raise ValueError(f"{year}: expected {expected} records, got {ds.sizes['time']}")
    if not np.all(dt == 3):
        raise ValueError(f"{year}: final time axis is not 3-hourly: {np.unique(dt)}")

    return expected


def validate_values(ds, year, undef):
    for var in ["uas", "vas", "psl"]:
        values = ds[var].values

        if not np.isfinite(values).all():
            raise ValueError(f"{year}: {var} contains NaN/Inf")

        invalid = np.count_nonzero(np.abs(values) >= abs(undef) * 0.9)
        if invalid:
            raise ValueError(f"{year}: {invalid} invalid values in {var}")

        vmin, vmax, vmean = float(values.min()), float(values.max()), float(values.mean())

        if var in ("uas", "vas") and (vmin < -150 or vmax > 150):
            print(f"WARNING {year}: unusual {var} range {vmin:.3f} to {vmax:.3f} m s-1")

        if var == "psl" and (vmin < 80000 or vmax > 110000):
            print(f"WARNING {year}: unusual psl range {vmin:.1f} to {vmax:.1f} Pa")

        print(f"{year}: {var} min={vmin:.3f}, mean={vmean:.3f}, max={vmax:.3f}", flush=True)


def build_dataset(ds):
    for var in VARMAP.values():
        ds[var].attrs = VAR_ATTRS[var].copy()

    time_coord = ds.time
    ds["time_bnds"] = xr.DataArray(
        np.stack([
            (time_coord - np.timedelta64(90, "m")).values,
            (time_coord + np.timedelta64(90, "m")).values
        ], axis=1),
        dims=("time", "bnds"),
        coords={"time": time_coord, "bnds": [0, 1]},
    )

    ds["lat"].attrs.update({
        "standard_name": "latitude", "long_name": "Latitude",
        "units": "degrees_north", "axis": "Y"
    })
    ds["lon"].attrs.update({
        "standard_name": "longitude", "long_name": "Longitude",
        "units": "degrees_east", "axis": "X"
    })
    ds["time"].attrs.update({
        "standard_name": "time", "long_name": "time",
        "axis": "T", "bounds": "time_bnds"
    })

    ds.attrs = GLOBAL_ATTRS.copy()
    return ds


def make_encoding(ds, var):
    return {
        var: {
            "dtype": "float32", "zlib": True, "complevel": 1,
            "shuffle": True, "_FillValue": np.float32(1e20),
            "chunksizes": (1, ds.sizes["lat"], ds.sizes["lon"]),
        },
        "time": {
            "dtype": "float64",
            "units": "days since 1900-01-01 00:00:00",
            "calendar": "gregorian", "_FillValue": None,
        },
        "time_bnds": {
            "dtype": "float64",
            "units": "days since 1900-01-01 00:00:00",
            "calendar": "gregorian", "_FillValue": None,
        },
        "lat": {"dtype": "float64", "_FillValue": None},
        "lon": {"dtype": "float64", "_FillValue": None},
    }


def verify_output(path, var, source_first, year, expected):
    with xr.open_dataset(path) as check:
        if check.sizes["time"] != expected:
            raise ValueError(f"{year} {var}: wrong record count")

        dt = np.diff(check.time.values) / np.timedelta64(1, "h")
        if not np.all(dt == 3):
            raise ValueError(f"{year} {var}: output is not 3-hourly")

        widths = (check.time_bnds[:, 1] - check.time_bnds[:, 0]).values / np.timedelta64(1, "h")
        if not np.all(widths == 3):
            raise ValueError(f"{year} {var}: time_bnds width is not 3 h")

        if calendar.isleap(year):
            feb29 = (check.time.dt.month == 2) & (check.time.dt.day == 29)
            if int(feb29.sum()) != 8:
                raise ValueError(f"{year} {var}: Feb 29 is incomplete")

        output_first = check[var].isel(time=0).load()
        max_diff = float(np.abs(source_first.values - output_first.values).max())

        if max_diff != 0:
            raise ValueError(f"{year} {var}: round-trip changed values, max diff={max_diff}")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ds = open_CtlDataset(str(SOURCE_CTL))

    for src in VARMAP:
        if src not in ds:
            raise KeyError(f"{src} not found. Variables: {list(ds.data_vars)}")

    years_all = ds.time.dt.year.values.astype(int)
    available = np.unique(years_all)
    undef = ds.attrs.get("undef", 9.999e19)

    for year in range(START_YEAR, END_YEAR + 1):
        print("\n" + "=" * 70)
        print(f"YEAR {year}", flush=True)
        t_year = time.perf_counter()

        if year not in available:
            raise ValueError(f"{year}: not present in SPEEDY output")

        outputs = {v: OUT_DIR / f"{v}_SPEEDY_{year}.nc" for v in VARMAP.values()}

        if SKIP_EXISTING and all(p.exists() for p in outputs.values()):
            print(f"{year}: all files exist -> SKIP", flush=True)
            continue

        idx = np.flatnonzero(years_all == year)
        print(f"{year} [1] selected {len(idx)} timesteps", flush=True)

        t = time.perf_counter()
        yearly = xr.Dataset({
            access: ds[speedy].isel(time=idx).astype("float32")
            for speedy, access in VARMAP.items()
        })

        # MSLP is hPa in SPEEDY -> Pa for ACCESS-OM2
        yearly["psl"] = yearly["psl"] * np.float32(100.0)

        if SHIFT_LONGITUDE_TO_MINUS180_180:
            yearly = yearly.assign_coords(lon=((yearly.lon + 180) % 360) - 180).sortby("lon")
        if SORT_LATITUDE_NORTH_TO_SOUTH:
            yearly = yearly.sortby("lat", ascending=False)

        print(f"{year} [2] selection built: {time.perf_counter()-t:.1f} s", flush=True)

        t = time.perf_counter()
        print(f"{year} [3] starting LOAD...", flush=True)
        yearly = yearly.load()
        print(f"{year} [3] LOAD done: {(time.perf_counter()-t)/60:.2f} min, "
              f"{sum(yearly[v].nbytes for v in VARMAP.values())/1024**2:.1f} MB", flush=True)

        t = time.perf_counter()
        validate_source_time(yearly, year)
        print(f"{year} [4] source time validation: {time.perf_counter()-t:.1f} s", flush=True)

        t = time.perf_counter()
        yearly = add_leap_day(yearly, year)
        expected = validate_final_time(yearly, year)
        print(f"{year} [5] leap/final time processing: {time.perf_counter()-t:.1f} s", flush=True)

        t = time.perf_counter()
        validate_values(yearly, year, undef)
        print(f"{year} [6] value validation: {time.perf_counter()-t:.1f} s", flush=True)

        yearly = build_dataset(yearly)

        for var in ["uas", "vas", "psl"]:
            output = outputs[var]

            if SKIP_EXISTING and output.exists():
                print(f"{year} {var}: already exists -> SKIP", flush=True)
                continue

            tmp = OUT_DIR / f".{var}_SPEEDY_{year}.nc.part"
            tmp.unlink(missing_ok=True)

            source_first = yearly[var].isel(time=0).copy(deep=True)
            var_ds = yearly[[var, "time_bnds"]]

            t = time.perf_counter()
            print(f"{year} [7] writing {var}...", flush=True)

            var_ds.to_netcdf(
                tmp,
                format="NETCDF4",
                engine="netcdf4",
                unlimited_dims=["time"],
                encoding=make_encoding(var_ds, var),
            )

            print(f"{year} [7] {var} WRITE: {(time.perf_counter()-t)/60:.2f} min", flush=True)

            t = time.perf_counter()
            verify_output(tmp, var, source_first, year, expected)
            print(f"{year} [8] {var} VERIFY: {time.perf_counter()-t:.1f} s", flush=True)

            tmp.replace(output)
            print(f"DONE {output.name}: {output.stat().st_size/1024**2:.1f} MB", flush=True)

            del source_first, var_ds

        print(f"{year} TOTAL: {(time.perf_counter()-t_year)/60:.2f} min", flush=True)

        del yearly
        gc.collect()

    try:
        ds.close()
    except Exception:
        pass

    print("\nALL YEARS COMPLETED", flush=True)


if __name__ == "__main__":
    main()