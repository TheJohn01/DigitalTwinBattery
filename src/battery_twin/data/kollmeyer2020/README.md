# LG 18650HG2 drive cycles at six temperatures (McMaster University)

A new 3 Ah LG 18650HG2 cell (NMC / graphite) in a thermal chamber at 40, 25, 10, 0, -10 and
-20 °C: C/20 discharge and charge, then the UDDS, HWFET, LA92 and US06 power profiles of a
compact electric car, each from full until about 95 % of the 1C capacity is used.

Source: Kollmeyer P., "LG 18650HG2 Li-ion Battery Data", Mendeley Data, version 2,
doi 10.17632/b5mj79w5w9.2 (tests by Dr. Phillip Kollmeyer, McMaster University).

- `hg2_ocv.csv`: per temperature, the C/20 discharge and charge voltage at 101 SOC points
  and the C/20 capacity (files `*_C20DisCh.csv`).
- `hg2_drive_1s.csv.gz`: one-second means of current (+ = charge, as logged), voltage and Ah
  counter during each drive cycle (rows with status TABLE of `*_UDDS.csv`, `*_HWFET.csv`,
  `*_LA92.csv`, `*_US06.csv`). The 25 °C HWFET file of the dataset holds no cycle, so it is
  missing; one unreadable line (10 °C LA92) is dropped.

Rebuilt by `python scripts/validate_estimator_drive.py "<unzipped dataset>"`.
