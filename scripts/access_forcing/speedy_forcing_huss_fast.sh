#!/bin/bash

#SBATCH --job-name=tas_forcing
#SBATCH --account=ICT26_ESP
#SBATCH --partition=dcgp_usr_prod
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=02:00:00
#SBATCH --mem=20G
#SBATCH --output=tas_forcing-%j.out
#SBATCH --error=tas_forcing-%j.err

set -e
module purge

source /leonardo/home/userexternal/ntilinin/.venvs/ocean2/bin/activate
python speedy_forcing_huss_fast.py
