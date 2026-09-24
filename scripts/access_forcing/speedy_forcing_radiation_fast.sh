#!/bin/bash

#SBATCH --job-name=rad_forcing
#SBATCH --account=ICT26_ESP
#SBATCH --partition=dcgp_usr_prod
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=06:00:00
#SBATCH --mem=20G
#SBATCH --output=rad_forcing-%j.out
#SBATCH --error=rad_forcing-%j.err

set -e
module purge

source /leonardo/home/userexternal/ntilinin/.venvs/ocean2/bin/activate
python speedy_forcing_radiation_fast.py
