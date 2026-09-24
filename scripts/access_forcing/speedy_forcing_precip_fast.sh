#!/bin/bash

#SBATCH --job-name=precip_forcing
#SBATCH --account=ICT26_ESP
#SBATCH --partition=dcgp_usr_prod
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=06:00:00
#SBATCH --mem=20G
#SBATCH --output=precip_forcing-%j.out
#SBATCH --error=precip_forcing-%j.err

set -e
module purge

source /leonardo/home/userexternal/ntilinin/.venvs/ocean2/bin/activate
python speedy_forcing_precip_fast.py
