#!/bin/bash
#SBATCH -A ICT26_ESP
#SBATCH -p dcgp_usr_prod
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH -t 01:00:00
#SBATCH -J rad
#SBATCH -o rad_%j.out
#SBATCH -e rad_%j.err
#SBATCH --export=NONE

set -e

module load python/3.11.7

export PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=1

source ~/.venvs/ocean2/bin/activate
cd "$SLURM_SUBMIT_DIR"

echo "NODE: $(hostname)"
echo "PYTHON: $(which python)"
python --version

python -u compare_rad_iaf_lat_band.py