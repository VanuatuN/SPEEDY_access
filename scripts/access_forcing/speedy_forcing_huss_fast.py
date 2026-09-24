#!/usr/bin/env python3

from pathlib import Path
import gc, calendar, time
import numpy as np
import xarray as xr
from xgrads import open_CtlDataset

# ===== USER SETTINGS =====

SOURCE_CTL = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/output/exp_195/attm195.ctl")
OUT_DIR = Path("/leonardo_scratch/fast/ICT26_ESP/ntilinin/SPEEDY_access/access_forcing/IAF/")

START_YEAR = 2004
END_YEAR = 2025

SPEEDY_VARIABLE = "Q0"
ACCESS_VARIABLE = "huss"

SHIFT_LONGITUDE_TO_MINUS180_180 = False
SORT_LATITUDE_NORTH_TO_SOUTH = False
SKIP_EXISTING = False

HUSS_ATTRS = {
    "standard_name": "specific_humidity",
    "long_name": "Near-Surface Specific Humidity",
    "comment": "Near-surface specific humidity from SPEEDY Q0",
    "units": "1",
    "cell_methods": "area: mean time: point",
    "source_variable": "Q0",
    "source_model": "SPEEDY",
    "mapping_note": "SPEEDY Q0 converted from g kg-1 to kg kg-1 -> ACCESS-OM2 huss",
}

GLOBAL_ATTRS = {
    "Conventions": "CF-1.7",
    "title": "SPEEDY forcing for ACCESS-OM2",
    "source": "SPEEDY model output",
    "frequency": "3hrPt",
    "history": "Created from SPEEDY Q0 and exported as huss",
    "comment": "3-hourly Gregorian forcing. Leap-day values are linearly interpolated from surrounding SPEEDY data.",
}


def expected_records(year):
    return 2928 if calendar.isleap(year) else 2920


def validate_source_time(huss, year):
    times = huss.time.values
    dt = np.diff(times) / np.timedelta64(1, "h")

    if huss.sizes["time"] != 2920:
        raise ValueError(f"{year}: expected 2920 SPEEDY records, got {huss.sizes['time']}")

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

    print(f"{year}: leap gap found: {s0} -> {s1}", flush=True)


def add_leap_day(huss, year):
    if not calendar.isleap(year):
        return huss

    target_time = np.arange(
        np.datetime64(f"{year}-01-01T00:00"),
        np.datetime64(f"{year + 1}-01-01T00:00"),
        np.timedelta64(3, "h"),
    )

    huss = huss.interp(time=target_time).astype("float32")

    feb29 = (huss.time.dt.month == 2) & (huss.time.dt.day == 29)
    if int(feb29.sum()) != 8:
        raise ValueError(f"{year}: expected 8 Feb 29 records, got {int(feb29.sum())}")

    print(f"{year}: inserted 8 records for Feb 29", flush=True)
    return huss


def validate_final_time(huss, year):
    dt = np.diff(huss.time.values) / np.timedelta64(1, "h")
    expected = expected_records(year)

    if huss.sizes["time"] != expected:
        raise ValueError(f"{year}: expected {expected} records, got {huss.sizes['time']}")
    if not np.all(dt == 3):
        raise ValueError(f"{year}: final time axis is not 3-hourly: {np.unique(dt)}")

    return expected


def validate_values(huss, year, undef):
    values = huss.values

    if not np.isfinite(values).all():
        raise ValueError(f"{year}: huss contains NaN/Inf")

    invalid = np.count_nonzero(np.abs(values) >= abs(undef) * 0.9)
    if invalid:
        raise ValueError(f"{year}: {invalid} values close to SPEEDY undef={undef}")

    vmin, vmax, vmean = float(values.min()), float(values.max()), float(values.mean())

    if vmin < 0:
        print(f"WARNING {year}: negative huss minimum {vmin:.6f}")
    if vmax > 0.05:
        print(f"WARNING {year}: unusually high huss maximum {vmax:.6f}")

    print(f"{year}: huss min={vmin:.6f}, mean={vmean:.6f}, max={vmax:.6f}", flush=True)


def build_dataset(huss):
    huss.attrs = HUSS_ATTRS.copy()
    out = huss.to_dataset()
    t = out.time

    out["time_bnds"] = xr.DataArray(
        np.stack([(t - np.timedelta64(90, "m")).values,
                  (t + np.timedelta64(90, "m")).values], axis=1),
        dims=("time", "bnds"), coords={"time": t, "bnds": [0, 1]}
    )

    out["lat"].attrs.update({"standard_name": "latitude", "long_name": "Latitude",
                             "units": "degrees_north", "axis": "Y"})
    out["lon"].attrs.update({"standard_name": "longitude", "long_name": "Longitude",
                             "units": "degrees_east", "axis": "X"})
    out["time"].attrs.update({"standard_name": "time", "long_name": "time",
                              "axis": "T", "bounds": "time_bnds"})
    out.attrs = GLOBAL_ATTRS.copy()

    return out


def make_encoding(ds):
    return {
        ACCESS_VARIABLE: {
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


def verify_output(path, source_first, year, expected):
    with xr.open_dataset(path) as check:
        if check.sizes["time"] != expected:
            raise ValueError(f"{year}: wrong record count")

        dt = np.diff(check.time.values) / np.timedelta64(1, "h")
        if not np.all(dt == 3):
            raise ValueError(f"{year}: output is not 3-hourly")

        widths = (check.time_bnds[:, 1] - check.time_bnds[:, 0]).values / np.timedelta64(1, "h")
        if not np.all(widths == 3):
            raise ValueError(f"{year}: time_bnds width is not 3 h")

        if calendar.isleap(year):
            feb29 = (check.time.dt.month == 2) & (check.time.dt.day == 29)
            if int(feb29.sum()) != 8:
                raise ValueError(f"{year}: incomplete Feb 29")

        output_first = check[ACCESS_VARIABLE].isel(time=0).load()
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

    # Q0 is converted g/kg -> kg/kg, so undef must be converted too
    undef = ds.attrs.get("undef", 9.999e19) / 1000.0

    for year in range(START_YEAR, END_YEAR + 1):
        print("\n" + "=" * 70)
        print(f"YEAR {year}", flush=True)
        t_year = time.perf_counter()

        if year not in available:
            raise ValueError(f"{year}: not present in SPEEDY output")

        output = OUT_DIR / f"huss_SPEEDY_{year}.nc"
        tmp = OUT_DIR / f".huss_SPEEDY_{year}.nc.part"

        if SKIP_EXISTING and output.exists():
            print(f"SKIP {output.name}", flush=True)
            continue

        tmp.unlink(missing_ok=True)

        idx = np.flatnonzero(years_all == year)
        print(f"{year} [1] selected {len(idx)} timesteps", flush=True)

        t = time.perf_counter()
        huss = (source.isel(time=idx) / 1000.0).rename(ACCESS_VARIABLE).astype("float32")
        print(f"{year} [2] selection done: {time.perf_counter()-t:.1f} s", flush=True)

        if SHIFT_LONGITUDE_TO_MINUS180_180:
            huss = huss.assign_coords(lon=((huss.lon + 180) % 360) - 180).sortby("lon")
        if SORT_LATITUDE_NORTH_TO_SOUTH:
            huss = huss.sortby("lat", ascending=False)

        t = time.perf_counter()
        print(f"{year} [3] starting LOAD...", flush=True)
        huss = huss.load()
        print(f"{year} [3] LOAD done: {(time.perf_counter()-t)/60:.2f} min, "
              f"{huss.nbytes/1024**2:.1f} MB", flush=True)

        validate_source_time(huss, year)

        t = time.perf_counter()
        huss = add_leap_day(huss, year)
        expected = validate_final_time(huss, year)
        print(f"{year} [4] leap/time processing: {time.perf_counter()-t:.1f} s", flush=True)

        t = time.perf_counter()
        validate_values(huss, year, undef)
        print(f"{year} [5] value validation: {time.perf_counter()-t:.1f} s", flush=True)

        source_first = huss.isel(time=0).copy(deep=True)
        yearly = build_dataset(huss)

        t = time.perf_counter()
        print(f"{year} [6] starting WRITE...", flush=True)

        yearly.to_netcdf(
            tmp, format="NETCDF4", engine="netcdf4",
            unlimited_dims=["time"], encoding=make_encoding(yearly)
        )

        print(f"{year} [6] WRITE done: {(time.perf_counter()-t)/60:.2f} min", flush=True)

        t = time.perf_counter()
        verify_output(tmp, source_first, year, expected)
        print(f"{year} [7] VERIFY done: {time.perf_counter()-t:.1f} s", flush=True)

        tmp.replace(output)

        print(f"DONE {output.name}: {output.stat().st_size/1024**2:.1f} MB", flush=True)
        print(f"{year} TOTAL: {(time.perf_counter()-t_year)/60:.2f} min", flush=True)

        del huss, yearly, source_first
        gc.collect()

    try:
        ds.close()
    except Exception:
        pass

    print("\nALL YEARS COMPLETED", flush=True)


if __name__ == "__main__":
    main()