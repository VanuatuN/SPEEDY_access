### SPEEDY adjustments and plots

Modifications made to the original SPEEDY configuration for producing atmospheric forcing for ACCESS-OM2.

Current SPEEDY run launched as: `./run_exp.s t30 101 0`
Emacs:
switch between buffers: Ctrl+x b
save: Ctrl+x Ctrl+s
exit: Ctrl+x Ctrl+c

**1.** Time-stepping parameters in ver41.input/cls_instep.h:
```text
NSTOUT = 9 (1 step 40 mins -> 6 hr output) 
IYEAR0 = 1989 (start year) 
NMONTS = 36 (length of integration -> 3 years)
```
**2.** RYF files produced with `scripts/access_forcing/speedy_forcing_accessom2.ipynb`
**3.** Forcing fiels for ACCESS-OM2 are currently stored in the `access_forcing` folder

**SPEEDY output check**
![Global mean SPEEDY temperature](../scripts/figures/sp_T30_globT_1989_1991.png)

**4.** Comparison of JRA55 RYF (May 1990 – May 1991) forcing with SPEEDY

Notebook: `scripts/diagnostics/compare_jra_speedy_forcing_1989.ipynb`

| [°K]  | JRA55 T | SPEEDY Near Surface Air Temp (!) |
|-----------|--------------:|---------------:|
| Mean      | 14.8        | 15.80         |
| Min       | 12.45        | 13.76         |
| Max       | 17.09        | 17.66         |

![Global mean SPEEDY temperature](../scripts/figures/diff_annual_mean_T_1989_1991.png)

**5.** Annual cycle T

Notebook: `scripts/diagnostics/compare_jra_speedy_forcing_1989.ipynb`

![Global mean SPEEDY temperature](../scripts/figures/global_mean_T_timeseries_1989_1991.png)

**6.** Wind

![Global mean SLP](../scripts/figures/diff_annual_mean_wind_speed_1990.png)

**7.** Sea Level Pressure

![Global mean WIND](../scripts/figures/diff_annual_mean_mslp_1990.png)

**8.** Surface Downward Radiation Output Changes
   
Two additional radiation diagnostics were added to the time-mean output for compatibility with ACCESS-OM2 forcing:

- `SSRD` — surface downwelling shortwave radiation → `rsds`
- `SLRD` — surface downwelling longwave radiation → `rlds`

Changes:

- `par_tmean.h`: increased `NS2D_2` from 12 to 14.
- `ppo_dmflux.f`: added `SSRD` and `SLRD` to `SAVE2D_2` as fields 13 and 14.
- `ppo_setctl.f`: added `SSRD` and `SLRD` descriptions to the output `.ctl`.

![Surface LR](../scripts/figures/diff_annual_mean_RLDS_1990.png)
![Surface SR](../scripts/figures/diff_annual_mean_RSDS_1990.png)  

**9.** Surface Specific Humidity 

![Surface SH](../scripts/figures/diff_annual_mean_huss_1989_1991.png)  

**10.** Precipitation and Snowfall

SPEEDY provides large-scale (`PRECLS`) and convective (`PRECNV`) precipitation: `PREC = PRECLS + PRECNV`

Total snowfall (`SNOW`) was added as a diagnostic in `ppo_dmflux.f`, without modifying the precipitation physics:

`SNOW = PREC` for `TS < 273.15 K`, otherwise `SNOW = 0`.

Total Rainfall: `PREC = PRECLS + PRECNV - SNOW`

![Surface RA](../scripts/figures/diff_mean_prra_1990_1991.png)  

![Surface SN](../scripts/figures/diff_mean_prsn_1990_1991.png)  

**11.** SPEEDY does not provide river runoff/ice flux, so `friver` (and `licalvf`) will remain from JRA55 for the initial hybrid forcing experiments.

<p align="center">
  <img src="../scripts/figures/jra_mean_friver_1990_1991.png" width="47%" />
  <img src="../scripts/figures/jra_mean_licalvf_1990_1991.png" width="47%" />
</p>
