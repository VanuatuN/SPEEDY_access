![Global mean T](../scripts/figures/IAF_1958_2019/diff_mean_T_1958_2019.png)
![Global mean T map](../scripts/figures/IAF_1958_2019/global_mean_T_1958_2019.png)
![Global mean T ocean](../scripts/figures/IAF_1958_2019/ocean_mean_T_1958_2019.png)

**Radiation** \
Two additional radiation diagnostics were added to the time-mean output for compatibility with ACCESS-OM2 forcing:

- `SSRD` — surface downwelling shortwave radiation → `rsds`
- `SLRD` — surface downwelling longwave radiation → `rlds`

Changes:

- `par_tmean.h`: increased `NS2D_2` from 12 to 14.
- `ppo_dmflux.f`: added `SSRD` and `SLRD` to `SAVE2D_2` as fields 13 and 14.
- `ppo_setctl.f`: added `SSRD` and `SLRD` descriptions to the output `.ctl`.

![SW](../scripts/figures/IAF_1958_2019/ocean_mean_rsds_1958_2019.png)
![SW_diff](../scripts/figures/IAF_1958_2019/diff_mean_rsds_1958_2019.png)

![LW](../scripts/figures/IAF_1958_2019/ocean_mean_rlds_1958_2019.png)
![LW_diff](../scripts/figures/IAF_1958_2019/diff_mean_rlds_1958_2019.png)

**Precipitation and Snowfall**

SPEEDY provides large-scale (`PRECLS`) and convective (`PRECNV`) precipitation:

`PREC = PRECLS + PRECNV`

Total snowfall (`SNOW`) was added as a diagnostic in `ppo_dmflux.f`, without modifying the precipitation physics:

`SNOW = PREC` for `TS < 273.15 K`; otherwise `SNOW = 0`.

Total rainfall is then calculated as:

`PREC = PRECLS + PRECNV - SNOW`

![Precipitation](../scripts/figures/IAF_1958_2019/diff_mean_prra_1958_2019.png)

## River Runoff and Land-Ice Flux

SPEEDY does not provide river runoff or land-ice freshwater fluxes, so `friver` and `licalvf` remain from JRA55-do for the initial hybrid forcing experiments.

<p align="center">
  <img src="../scripts/figures/jra_mean_friver_1990_1991.png" width="47%" />
  <img src="../scripts/figures/jra_mean_licalvf_1990_1991.png" width="47%" />
</p>
