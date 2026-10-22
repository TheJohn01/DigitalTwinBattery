# TUM multi-stage ageing study, LG INR18650 MJ1

Capacity check-ups (reference performance tests) of 42 LG INR18650 MJ1 cells (NMC /
graphite-SiOx, 3.4 Ah) cycled at 10, 20 and 30 °C, depth of discharge 10-100 % around 50 %
SOC, charge 0.33-1C, for up to about 140 days or until 60 % capacity.

Source: Stroebl et al., "A multi-stage lithium-ion battery aging dataset using various
experimental design methodologies", Scientific Data (2024), doi 10.1038/s41597-024-03859-z;
data on mediaTUM (https://mediatum.ub.tum.de/1745519), CC BY 4.0.

`mj1_rpt.csv` keeps, per cell and check-up, the test conditions (from
`Overview_Aging_Experiment.xlsx`) and the columns `Capacity_DCH_in_mAh`, `EFC` and
`Age_in_days` of the files `Processed/Z005.csv` ... `Z046.csv`; the OCV curves and
resistances are left out. Used by `scripts/validate_nmc_mj1.py`.
