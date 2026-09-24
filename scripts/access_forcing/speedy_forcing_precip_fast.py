#!/usr/bin/env python3

from pathlib import Path
import gc, calendar, time
import numpy as np
import xarray as xr
from xgrads import open_CtlDataset

SOURCE_CTL = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/output/exp_195/attm195.ctl")
OUT_DIR = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/access_forcing/IAF/")

START_YEAR = 1989
END_YEAR = 2025

SHIFT_LONGITUDE_TO_MINUS180_180 = False
SORT_LATITUDE_NORTH_TO_SOUTH = False
SKIP_EXISTING = False

ATTRS = {
    "prra": {
        "standard_name": "rainfall_flux", "long_name": "Rainfall Flux",
        "units": "kg m-2 s-1", "cell_methods": "area: time: mean",
        "source_variable": "PRECLS + PRECNV - SNOW", "source_model": "SPEEDY",
        "mapping_note": "SPEEDY liquid precipitation converted from mm day-1 to kg m-2 s-1",
    },
    "prsn": {
        "standard_name": "snowfall_flux", "long_name": "Snowfall Flux",
        "units": "kg m-2 s-1", "cell_methods": "area: time: mean",
        "source_variable": "SNOW", "source_model": "SPEEDY",
        "mapping_note": "SPEEDY snowfall converted from mm day-1 water equivalent to kg m-2 s-1",
    },
}

GLOBAL_ATTRS = {
    "Conventions": "CF-1.7",
    "title": "SPEEDY forcing for ACCESS-OM2",
    "source": "SPEEDY model output",
    "frequency": "3hr",
    "history": "Created from SPEEDY PRECLS, PRECNV and SNOW",
    "comment": "3-hour mean precipitation forcing. Leap-day values are averages of corresponding Feb 28 and Mar 1 intervals.",
}


def expected_records(year):
    return 2928 if calendar.isleap(year) else 2920


def validate_source_time(ds, year):
    dt = np.diff(ds.time.values) / np.timedelta64(1, "h")

    if ds.sizes["time"] != 2920:
        raise ValueError(f"{year}: expected 2920 SPEEDY records, got {ds.sizes['time']}")

    bad = np.where(dt != 3)[0]

    if not calendar.isleap(year):
        if len(bad):
            raise ValueError(f"{year}: unexpected intervals {np.unique(dt)} h")
        return

    if len(bad) != 1:
        raise ValueError(f"{year}: expected one leap gap, found {len(bad)}")

    i = bad[0]
    s0 = np.datetime_as_string(ds.time.values[i], unit="h")
    s1 = np.datetime_as_string(ds.time.values[i + 1], unit="h")

    if not (s0.endswith("02-28T21") and s1.endswith("03-01T00") and dt[i] == 27):
        raise ValueError(f"{year}: unexpected leap gap {s0} -> {s1} = {dt[i]} h")

    print(f"{year}: leap gap found: {s0} -> {s1}", flush=True)


def add_leap_day(ds, year):
    if not calendar.isleap(year):
        return ds

    feb28 = ds.sel(time=slice(f"{year}-02-28T00:00", f"{year}-02-28T21:00"))
    mar01 = ds.sel(time=slice(f"{year}-03-01T00:00", f"{year}-03-01T21:00"))

    if feb28.sizes["time"] != 8 or mar01.sizes["time"] != 8:
        raise ValueError(f"{year}: expected 8 records on Feb 28 and Mar 1")

    leap_time = np.arange(
        np.datetime64(f"{year}-02-29T00:00"),
        np.datetime64(f"{year}-03-01T00:00"),
        np.timedelta64(3, "h"),
    )

    leap = xr.Dataset({
        var: xr.DataArray(
            (0.5 * (feb28[var].values + mar01[var].values)).astype("float32"),
            dims=ds[var].dims,
            coords={"time": leap_time, "lat": ds.lat, "lon": ds.lon},
        )
        for var in ["prra", "prsn"]
    })

    ds = xr.concat([ds, leap], dim="time").sortby("time")
    print(f"{year}: inserted 8 Feb 29 precipitation intervals", flush=True)
    return ds


def validate_final_time(ds, year):
    expected = expected_records(year)
    dt = np.diff(ds.time.values) / np.timedelta64(1, "h")

    if ds.sizes["time"] != expected:
        raise ValueError(f"{year}: expected {expected} records, got {ds.sizes['time']}")
    if not np.all(dt == 3):
        raise ValueError(f"{year}: final time is not 3-hourly: {np.unique(dt)}")

    return expected


def validate_values(ds, year):
    for var in ["prra", "prsn"]:
        x = ds[var].values

        if not np.isfinite(x).all():
            raise ValueError(f"{year}: {var} contains NaN/Inf")
        if np.min(x) < 0:
            raise ValueError(f"{year}: negative {var} found")

        print(
            f"{year}: {var} min={x.min():.8f}, mean={x.mean():.8f}, max={x.max():.8f}",
            flush=True,
        )


def build_dataset(ds):
    for var in ["prra", "prsn"]:
        ds[var].attrs = ATTRS[var].copy()

    # SPEEDY raw time = beginning of the 3-hour mean interval
    raw_time = ds.time.values.copy()
    midpoint = raw_time + np.timedelta64(90, "m")

    ds = ds.assign_coords(time=midpoint)

    ds["time_bnds"] = xr.DataArray(
        np.stack([raw_time, raw_time + np.timedelta64(3, "h")], axis=1),
        dims=("time", "bnds"), coords={"time": midpoint, "bnds": [0, 1]}
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
            "dtype": "float32", "zlib": True, "complevel": 1, "shuffle": True,
            "_FillValue": np.float32(1e20),
            "chunksizes": (1, ds.sizes["lat"], ds.sizes["lon"]),
        },
        "time": {
            "dtype": "float64", "units": "days since 1900-01-01 00:00:00",
            "calendar": "gregorian", "_FillValue": None,
        },
        "time_bnds": {
            "dtype": "float64", "units": "days since 1900-01-01 00:00:00",
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
            raise ValueError(f"{year} {var}: time is not 3-hourly")

        b0, b1 = check.time_bnds[:, 0].values, check.time_bnds[:, 1].values
        widths = (b1 - b0) / np.timedelta64(1, "h")
        midpoint = b0 + (b1 - b0) / 2

        if not np.all(widths == 3):
            raise ValueError(f"{year} {var}: bounds are not 3 h")
        if not np.array_equal(midpoint, check.time.values):
            raise ValueError(f"{year} {var}: time is not bounds midpoint")

        if calendar.isleap(year):
            feb29 = (check.time.dt.month == 2) & (check.time.dt.day == 29)
            if int(feb29.sum()) != 8:
                raise ValueError(f"{year} {var}: incomplete Feb 29")

        output_first = check[var].isel(time=0).load()
        diff = float(np.abs(source_first.values - output_first.values).max())

        if diff != 0:
            raise ValueError(f"{year} {var}: round-trip changed values, max diff={diff}")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ds = open_CtlDataset(str(SOURCE_CTL))

    for var in ["PRECLS", "PRECNV", "SNOW"]:
        if var not in ds:
            raise KeyError(f"{var} not found. Variables: {list(ds.data_vars)}")

    years_all = ds.time.dt.year.values.astype(int)
    available = np.unique(years_all)

    for year in range(START_YEAR, END_YEAR + 1):
        print("\n" + "=" * 70)
        print(f"YEAR {year}", flush=True)
        t_year = time.perf_counter()

        if year not in available:
            raise ValueError(f"{year}: not present in SPEEDY output")

        outputs = {v: OUT_DIR / f"{v}_SPEEDY_{year}.nc" for v in ["prra", "prsn"]}

        if SKIP_EXISTING and all(p.exists() for p in outputs.values()):
            print(f"{year}: files exist -> SKIP", flush=True)
            continue

        idx = np.flatnonzero(years_all == year)

        print(f"{year} [1] selected {len(idx)} timesteps", flush=True)

        # Read all required source fields once
        src = xr.Dataset({
            "PRECLS": ds["PRECLS"].isel(time=idx).astype("float32"),
            "PRECNV": ds["PRECNV"].isel(time=idx).astype("float32"),
            "SNOW": ds["SNOW"].isel(time=idx).astype("float32"),
        })

        t = time.perf_counter()
        print(f"{year} [2] starting LOAD...", flush=True)
        src = src.load()
        print(f"{year} [2] LOAD: {(time.perf_counter()-t)/60:.2f} min", flush=True)

        validate_source_time(src, year)

        # mm/day water equivalent -> kg m-2 s-1
        yearly = xr.Dataset({
            "prra": ((src["PRECLS"] + src["PRECNV"] - src["SNOW"]) / 86400.0).clip(min=0).astype("float32"),
            "prsn": (src["SNOW"] / 86400.0).clip(min=0).astype("float32"),
        })

        del src

        if SHIFT_LONGITUDE_TO_MINUS180_180:
            yearly = yearly.assign_coords(lon=((yearly.lon + 180) % 360) - 180).sortby("lon")
        if SORT_LATITUDE_NORTH_TO_SOUTH:
            yearly = yearly.sortby("lat", ascending=False)

        t = time.perf_counter()
        yearly = add_leap_day(yearly, year)
        expected = validate_final_time(yearly, year)
        print(f"{year} [3] leap/time: {time.perf_counter()-t:.1f} s", flush=True)

        validate_values(yearly, year)
        yearly = build_dataset(yearly)

        for var in ["prra", "prsn"]:
            output = outputs[var]

            if SKIP_EXISTING and output.exists():
                print(f"{year} {var}: exists -> SKIP", flush=True)
                continue

            tmp = OUT_DIR / f".{var}_SPEEDY_{year}.nc.part"
            tmp.unlink(missing_ok=True)

            source_first = yearly[var].isel(time=0).copy(deep=True)
            var_ds = yearly[[var, "time_bnds"]]

            t = time.perf_counter()
            print(f"{year} [4] writing {var}...", flush=True)

            var_ds.to_netcdf(
                tmp, format="NETCDF4", engine="netcdf4",
                unlimited_dims=["time"], encoding=make_encoding(var_ds, var)
            )

            print(f"{year} [4] {var} WRITE: {(time.perf_counter()-t)/60:.2f} min", flush=True)

            verify_output(tmp, var, source_first, year, expected)
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