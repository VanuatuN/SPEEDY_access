#!/bin/bash
#SBATCH -A ICT26_ESP
#SBATCH -p dcgp_usr_prod
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH -t 00:30:00
#SBATCH -J tas
#SBATCH -o tas_%j.out
#SBATCH -e tas_%j.err
#SBATCH --export=NONE

set -e

source /leonardo/prod/spack/03/install/0.19/linux-rhel8-icelake/gcc-8.5.0/anaconda3-2022.05-e7262poa2u2i3rurf3cdt6a5r6dqieik/etc/profile.d/conda.sh
conda activate ocean

export PYTHONHOME=$CONDA_PREFIX
export PYTHONNOUSERSITE=1
unset PYTHONPATH
unset PYTHONUSERBASE
hash -r

echo "NODE: $(hostname)"
echo "CONDA_PREFIX: $CONDA_PREFIX"
echo "PYTHON: $(which python)"
python --version

python -c "import sys, platform; print('prefix:', sys.prefix); print('executable:', sys.executable); print('platform:', platform.__file__)"
python -c "import xarray, pandas, dask; print('xarray/pandas/dask OK')"

python compare_pr.py