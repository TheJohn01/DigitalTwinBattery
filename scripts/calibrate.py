"""Calibrate the NMC physics model against measured LG M50T data (takes a few minutes).
Writes results/calibration.json and results/calibration_fit.png."""
from battery_twin.calibration import main

main("results")
