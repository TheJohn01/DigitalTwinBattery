# Commercial NCA cell: model curves and measured data (Schmitt et al., 2023)

Cell: **Samsung INR21700-50E** (21700, 4.9 Ah, 3.6 V nominal, 2.5–4.2 V), cathode
LiNi0.87Co0.11Al0.02O2 (NCA), anode graphite with Si/SiOx.

- **Paper:** C. Schmitt, M. Gerle, D. Kopljar, K. A. Friedrich. *Full parameterization study of
  a high-energy and a high-power Li-ion cell for physicochemical models.* J. Electrochem. Soc.
  170 (2023) 070509. https://doi.org/10.1149/1945-7111/ace1a7. Licence CC BY 4.0. Scalar
  parameters: supplementary Table SIV (in `nca_params.py`).
- **How the files were made:** `scripts/digitize_schmitt.py <paper.pdf> <supplement.pdf> <folder>`.
  The figures are embedded 300 dpi images, so curves are read pixel by pixel by colour, with the
  axes calibrated on the tick marks.

## Files
| File | Content | Source |
|---|---|---|
| `anode_ocp_V.csv`, `cathode_ocp_V.csv` | open-circuit potential vs stoichiometry | Fig. 9a balanced half-cell OCPs; capacity turned into stoichiometry with the simulation balancing of Table SIV (x = 0.999 / 0.16 at 100 % SOC; 4.205 / 5.951 mAh/cm²). Beyond 3 mAh/cm² the anode is cathode OCP minus the measured 0.04C discharge (offset to the OCV), so the cell OCV follows the real cell to 2.5 V |
| `anode_j0_25C.csv`, `cathode_j0_25C.csv` | measured exchange-current density at 25 °C [A/m²] vs stoichiometry | Supplementary Fig. S14a/b markers (the Table SIV fits do not reproduce them) |
| `measured_ocv_V.csv` | measured OCV of the 21700 cell vs discharge capacity | Fig. 9a |
| `measured_discharge_voltage.csv` | measured discharges at 0.04C (full), 0.5C and 1C (to 3 mAh/cm², where measured and simulated curves overlap) and each end capacity at 2.5 V | Fig. 14a |

Checks: the OCPs reproduce the measured OCV within 12 mV RMS; the model reproduces the
measured discharges within 1 % in capacity and 15–24 mV RMS (`scripts/validate_nca.py`).
