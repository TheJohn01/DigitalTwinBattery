# Commercial sodium-ion cell: model curves and measured data (Schneider et al., 2025)

Cell: **Shenzhen Mushang NA18650-1250** (18650, 1.25 Ah, 3.0 V nominal, 1.5–3.8 V),
layered-oxide cathode Na0.96Ca0.02Ni1/3Fe1/3Mn1/3O2 and hard-carbon anode.

- **Paper:** N. Schneider, N. Stapf, C. Mehlich, A. Biswas, K. P. Birke, A. Fill. *Towards
  accurate sodium-ion cell modelling: parametrization and validation of a commercial
  sodium-ion cell incorporating temperature-dependent kinetics.* J. Electrochem. Soc. 172
  (2025) 090525. https://doi.org/10.1149/1945-7111/adfd16. Licence CC BY 4.0.
- **How the files were made:** the figures in the published PDF are vector graphics, so the
  plotted curves were read from the drawing paths, with the axes calibrated on the tick
  marks (`scripts/extract_schneider_fig12.py`, `scripts/extract_schneider_fig15_16.py`; both
  take the PDF path and an output folder). No manual digitising. The mean activation energies
  of the extracted curves agree with the values in the paper's text within 2 kJ/mol
  (anode diffusion 82.0 vs 80.4; anode kinetics 74.9 vs 77.0; cathode diffusion 103.7 vs
  101.9; cathode kinetics 37.2 vs 37.8 kJ/mol).

## Files (stoichiometry 0-1 = empty-full of sodium)
| File | Content | Source |
|---|---|---|
| `anode_ocp_V.csv`, `cathode_ocp_V.csv` | open-circuit potential vs Na/Na+ | Fig. 12c (pOCV) |
| `anode_diffusivity_m2_s.csv`, `cathode_diffusivity_m2_s.csv` | solid diffusivity at 25 °C, "fit" curves (incl. scaling factors 1.3 / 5) | Fig. 12a, dashed |
| `anode_kinetic_rate.csv`, `cathode_kinetic_rate.csv` | kinetic rate k in i0 = F k (cmax-cs)^0.5 cs^0.5 ce^0.5, 25 °C, "fit" curves | Fig. 12b, dashed |
| `*_Ea_kJ_mol.csv` | Arrhenius activation energies of diffusivity and kinetic rate | Fig. 12d |
| `measured_discharge_voltage.csv` | measured voltage, commercial cell, C/100-5C, 25 °C | Fig. 15a, dashed |
| `measured_surface_temperature.csv` | measured surface temperature, same tests | Fig. 16, dashed |

Scalar parameters (geometry, thermal, electrolyte) are in `sodium_ion_params.py`, with the
readings of Table III that needed a choice explained there.
