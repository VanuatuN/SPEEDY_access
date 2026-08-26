Load current modules and environment (ancestry and identical with ones that COSIMA was compiled):

```bash
source ~/leo_env.sh
```

Conda environment (manually or just `ocean` as alias in bash profile)

```bash
alias ocean='source /leonardo/prod/spack/03/install/0.19/linux-rhel8-icelake
/gcc-8.5.0/anaconda3-2022.05-e7262poa2u2i3rurf3cdt6a5r6dqieik/etc/profile.d/
conda.sh && conda activate ocean'

For jupyter notebook activation (manually or just `ocean_jupyter`)
alias ocean_jupyter='ocean && export PYTHONHOME=$CONDA_PREFIX && export PYTH
ONNOUSERSITE=1 && unset PYTHONPATH PYTHONUSERBASE && hash -r && jupyter lab 
--no-browser --port=8888'
```
