#!/bin/bash
#SBATCH --partition=small-andre01
#SBATCH --time=01:00:00
#SBATCH --output=build_%J.log
#SBATCH --mem=4G

rm -f env.sif

apptainer build env.sif env.def

if [ $? -eq 0 ]; then
    echo "Build successful!"
else
    echo "Build failed..."
    exit 1
fi
