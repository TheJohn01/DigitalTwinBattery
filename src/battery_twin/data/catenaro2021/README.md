# Catenaro & Onori (2021): LG M50 self-heating and efficiency

- **Paper:** E. Catenaro, S. Onori. *Experimental data of lithium-ion batteries under
  galvanostatic discharge tests at different rates and temperatures of operation.* Data in
  Brief 35 (2021) 106894. https://doi.org/10.1016/j.dib.2021.106894
- **Data:** Mendeley Data, https://doi.org/10.17632/kxsbr4x3j2 (CC BY 4.0). Credit for the
  measurements belongs to the authors.
- **Cells:** six LG INR21700-M50 (NMC 811 / graphite-SiOx, 5 Ah), the cell of the NMC physics
  model, in a cylindrical holder in a 5, 25 or 35 °C chamber; surface temperature (T-type
  thermocouple at mid-height), 1 s sampling.

| File | Content |
|---|---|
| `nmc_tests.csv` | One row per test file (72: six cells x 1, 2, 3, 5C x three chambers): voltage at the start of the file, charge and discharge Ah and Wh, voltage at the end of the discharge, surface temperature at the start, maximum and end of the discharge. Written by `scripts/extract_catenaro.py` from the original .xlsx files. |

Notes: some tests start part-charged (their charge is incomplete), so efficiency is only taken
from tests whose charge Ah is within 2 % of their discharge Ah. At 5C the tester stopped the
discharge at its temperature limit (about 75 °C at 25 °C). The 5 °C chamber results scatter
widely (start temperatures 5.4-8.3 °C). The LFP (A123 26650) and NCA (Panasonic NCR18650B) files
of the same dataset are not used: they are not the cells of the program's LFP and NCA models.
