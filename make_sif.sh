#!/bin/bash
#SBATCH --partition=interactive
#SBATCH --time=01:00:00
#SBATCH --output=build_%J.log

rm -f env.sif

apptainer build env.sif env.def

if [ $? -eq 0 ]; then
    echo "Build successful!"
else
    echo "Build failed..."
    exit 1
fi
