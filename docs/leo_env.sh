#!/bin/bash
###############################################################################
# leo_env.sh
#
# Restore ACCESS-NRI / Spack / Intel environment on Leonardo
###############################################################################

echo "==> Cleaning environment..."

module purge

unset PYTHONPATH
unset PYTHONHOME
unset PYTHONUSERBASE
unset SPACK_PYTHON

unset CONDA_PREFIX
unset CONDA_DEFAULT_ENV
unset CONDA_EXE
unset CONDA_PYTHON_EXE
unset _CE_CONDA
unset _CE_M

hash -r

###############################################################################
# Spack
###############################################################################

echo "==> Loading Spack..."

source ~/ACCESS-NRI/spack/share/spack/setup-env.sh

###############################################################################
# Modules
###############################################################################

echo "==> Adding ACCESS-NRI module tree..."

module use ~/ACCESS-NRI/release/modules/linux-rhel8-x86_64

###############################################################################
# Intel compiler
###############################################################################

echo "==> Loading Intel oneAPI compiler..."

module load intel-oneapi-compilers/2021.2.0-p7vtyvv
module load openmpi/4.1.4-ga6avsd 

###############################################################################
# Diagnostics
###############################################################################

echo
echo "==============================================================="
echo "Environment summary"
echo "==============================================================="

echo
echo "Python:"
python3 -c "import sys; print(sys.executable)"

echo
echo "Compiler:"
which ifort
which ifx 2>/dev/null

echo
echo "MPI wrapper:"
which mpifort
mpifort -show

echo
echo "Installed Intel package:"
spack find -l intel-oneapi-compilers

export LD_LIBRARY_PATH=/leonardo/home/userexternal/ntilinin/ACCESS-NRI/release/linux-rhel8-x86_64/intel-2021.2.0/openmpi-4.1.4-ga6avsdxmjya35twagfjts7jp3yahbwt/lib/

echo
echo "Loaded modules:"
module list

echo
echo "==============================================================="
echo "Environment ready."
echo "==============================================================="