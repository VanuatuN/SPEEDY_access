#!/usr/bin/env python3

from pathlib import Path
import gc, calendar
import numpy as np
import xarray as xr
from xgrads import open_CtlDataset
import time 

SOURCE_CTL = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/output/exp_195/attm195.ctl")
OUT_DIR = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/access_forcing/IAF/")

START_YEAR = 1958
END_YEAR = 2025

SPEEDY_VARIABLE = "TEMP0"
ACCESS_VARIABLE = "tas"

SHIFT_LONGITUDE_TO_MINUS180_180 = False
SORT_LATITUDE_NORTH_TO_SOUTH = False
SKIP_EXISTING = False


TAS_ATTRS = {
    "standard_name": "air_temperature",
    "long_name": "Near-Surface Air Temperature",
    "comment": "Near-surface air temperature from SPEEDY TEMP0",
    "units": "K",
    "cell_methods": "area: mean time: point",
    "source_variable": "TEMP0",
    "source_model": "SPEEDY",
    "mapping_note": "SPEEDY TEMP0 -> ACCESS-OM2 tas",
}

GLOBAL_ATTRS = {
    "Conventions": "CF-1.7",
    "title": "SPEEDY forcing for ACCESS-OM2",
    "source": "SPEEDY model output",
    "frequency": "3hrPt",
    "history": "Created from SPEEDY TEMP0 and exported as tas",
    "comment": "3-hourly forcing on Gregorian calendar. Leap-day values are linearly interpolated from surrounding SPEEDY data.",
}


def expected_records(year):
    return 2928 if calendar.isleap(year) else 2920


def validate_source_time(tas, year):
    """Validate original SPEEDY 365-day output before adding Feb 29."""
    times = tas.time.values
    dt = np.diff(times) / np.timedelta64(1, "h")

    if tas.sizes["time"] != 2920:
        raise ValueError(f"{year}: expected 2920 SPEEDY records, got {tas.sizes['time']}")

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

    print(f"{year}: SPEEDY leap gap found: {s0} -> {s1}")


def add_leap_day(tas, year):
    """Insert Feb 29 at 3-hour intervals using linear interpolation."""
    if not calendar.isleap(year):
        return tas

    target_time = np.arange(
        np.datetime64(f"{year}-01-01T00:00"),
        np.datetime64(f"{year + 1}-01-01T00:00"),
        np.timedelta64(3, "h"),
    )

    tas = tas.interp(time=target_time).astype("float32")

    feb29 = (tas.time.dt.month == 2) & (tas.time.dt.day == 29)
    if int(feb29.sum()) != 8:
        raise ValueError(f"{year}: expected 8 records on Feb 29, got {int(feb29.sum())}")

    print(f"{year}: inserted 8 records for Feb 29")
    return tas


def validate_final_time(tas, year):
    dt = np.diff(tas.time.values) / np.timedelta64(1, "h")
    expected = expected_records(year)

    if tas.sizes["time"] != expected:
        raise ValueError(f"{year}: expected {expected} final records, got {tas.sizes['time']}")

    if not np.all(dt == 3):
        raise ValueError(f"{year}: final time axis is not 3-hourly: {np.unique(dt)}")

    return expected


def validate_values(tas, year, undef):
    values = tas.values

    if not np.isfinite(values).all():
        raise ValueError(f"{year}: NaN/Inf found")

    invalid = np.count_nonzero(np.abs(values) >= abs(undef) * 0.9)
    if invalid:
        raise ValueError(f"{year}: {invalid} values close to SPEEDY undef={undef}")

    vmin, vmax, vmean = float(values.min()), float(values.max()), float(values.mean())

    if not (150 < vmin < 350):
        print(f"WARNING {year}: unusual minimum {vmin:.3f} K")
    if not (200 < vmax < 400):
        print(f"WARNING {year}: unusual maximum {vmax:.3f} K")

    print(f"{year}: min={vmin:.3f}, mean={vmean:.3f}, max={vmax:.3f} K")


def build_dataset(tas):
    tas.attrs = TAS_ATTRS.copy()
    out = tas.to_dataset()
    time = out.time

    out["time_bnds"] = xr.DataArray(
        np.stack([
            (time - np.timedelta64(90, "m")).values,
            (time + np.timedelta64(90, "m")).values
        ], axis=1),
        dims=("time", "bnds"),
        coords={"time": time, "bnds": [0, 1]},
    )

    out["lat"].attrs.update({
        "standard_name": "latitude", "long_name": "Latitude",
        "units": "degrees_north", "axis": "Y"
    })
    out["lon"].attrs.update({
        "standard_name": "longitude", "long_name": "Longitude",
        "units": "degrees_east", "axis": "X"
    })
    out["time"].attrs.update({
        "standard_name": "time", "long_name": "time",
        "axis": "T", "bounds": "time_bnds"
    })

    out.attrs = GLOBAL_ATTRS.copy()
    return out


def make_encoding(ds):
    return {
        ACCESS_VARIABLE: {
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


def verify_output(path, source_first, year, expected):
    with xr.open_dataset(path) as ds:
        if ds.sizes["time"] != expected:
            raise ValueError(f"{year}: wrong output record count")

        if ds.attrs.get("frequency") != "3hrPt":
            raise ValueError(f"{year}: wrong frequency metadata")

        if "time_bnds" not in ds:
            raise ValueError(f"{year}: time_bnds missing")

        dt = np.diff(ds.time.values) / np.timedelta64(1, "h")
        if not np.all(dt == 3):
            raise ValueError(f"{year}: output time axis is not 3-hourly")

        widths = (ds.time_bnds[:, 1] - ds.time_bnds[:, 0]).values / np.timedelta64(1, "h")
        if not np.all(widths == 3):
            raise ValueError(f"{year}: time_bnds width is not 3 h")

        if calendar.isleap(year):
            feb29 = (ds.time.dt.month == 2) & (ds.time.dt.day == 29)
            if int(feb29.sum()) != 8:
                raise ValueError(f"{year}: output does not contain 8 Feb 29 records")

        output_first = ds[ACCESS_VARIABLE].isel(time=0).load()
        max_diff = float(np.abs(source_first.values - output_first.values).max())

        if max_diff != 0:
            raise ValueError(f"{year}: round-trip changed values, max diff={max_diff}")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ds = open_CtlDataset(str(SOURCE_CTL))

    if SPEEDY_VARIABLE not in ds:
        raise KeyError(f"{SPEEDY_VARIABLE} not found. Variables: {list(ds.data_vars)}")

    source = ds[SPEEDY_VARIABLE]
    years_all = ds.time.dt.year.values.astype(int)
    available = np.unique(years_all)
    undef = ds.attrs.get("undef", 9.999e19)

    for year in range(START_YEAR, END_YEAR + 1):
        print("\n" + "=" * 70)
        print(f"YEAR {year}")

        if year not in available:
            raise ValueError(f"{year}: not present in SPEEDY output")

        output = OUT_DIR / f"tas_SPEEDY_{year}.nc"
        tmp = OUT_DIR / f".tas_SPEEDY_{year}.nc.part"

        if SKIP_EXISTING and output.exists():
            print(f"SKIP {output.name}")
            continue

        tmp.unlink(missing_ok=True)

        t_year = time.perf_counter()

        idx = np.flatnonzero(years_all == year)
        print(f"{year} [1] selected {len(idx)} timesteps", flush=True)

        t = time.perf_counter()
        tas = source.isel(time=idx).rename(ACCESS_VARIABLE).astype("float32")
        print(f"{year} [2] isel done: {time.perf_counter()-t:.1f} s", flush=True)

        if SHIFT_LONGITUDE_TO_MINUS180_180:
            tas = tas.assign_coords(lon=((tas.lon + 180) % 360) - 180).sortby("lon")

        if SORT_LATITUDE_NORTH_TO_SOUTH:
            tas = tas.sortby("lat", ascending=False)

        t = time.perf_counter()
        print(f"{year} [3] starting LOAD...", flush=True)
        tas = tas.load()
        print(f"{year} [3] LOAD done: {(time.perf_counter()-t)/60:.2f} min, "
              f"{tas.nbytes/1024**2:.1f} MB", flush=True)

        t = time.perf_counter()
        validate_source_time(tas, year)
        print(f"{year} [4] source time validation: {time.perf_counter()-t:.1f} s", flush=True)

        t = time.perf_counter()
        print(f"{year} [5] starting leap-day processing...", flush=True)
        tas = add_leap_day(tas, year)
        print(f"{year} [5] leap-day processing done: {time.perf_counter()-t:.1f} s", flush=True)

        t = time.perf_counter()
        expected = validate_final_time(tas, year)
        print(f"{year} [6] final time validation: {time.perf_counter()-t:.1f} s", flush=True)

        t = time.perf_counter()
        print(f"{year} [7] starting value validation...", flush=True)
        validate_values(tas, year, undef)
        print(f"{year} [7] value validation done: {time.perf_counter()-t:.1f} s", flush=True)

        t = time.perf_counter()
        print(f"{year} [8] building output dataset...", flush=True)
        source_first = tas.isel(time=0).copy(deep=True)
        yearly = build_dataset(tas)
        print(f"{year} [8] dataset built: {time.perf_counter()-t:.1f} s", flush=True)

        t = time.perf_counter()
        print(f"{year} [9] starting NetCDF WRITE...", flush=True)

        yearly.to_netcdf(
            tmp,
            format="NETCDF4",
            engine="netcdf4",
            unlimited_dims=["time"],
            encoding=make_encoding(yearly),
        )

        print(f"{year} [9] WRITE done: {(time.perf_counter()-t)/60:.2f} min", flush=True)

        t = time.perf_counter()
        print(f"{year} [10] starting output verification...", flush=True)
        verify_output(tmp, source_first, year, expected)
        print(f"{year} [10] VERIFY done: {(time.perf_counter()-t)/60:.2f} min", flush=True)

        tmp.replace(output)

        print(f"{year} DONE: {output.stat().st_size/1024**2:.1f} MB", flush=True)
        print(f"{year} TOTAL: {(time.perf_counter()-t_year)/60:.2f} min", flush=True)

        del tas, yearly, source_first
        gc.collect()

    try:
        ds.close()
    except Exception:
        pass

    print("\nALL YEARS COMPLETED")


if __name__ == "__main__":
    main()