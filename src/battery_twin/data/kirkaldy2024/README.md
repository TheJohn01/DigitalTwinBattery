# Reference data: LG M50T cycle ageing (Kirkaldy et al., 2024)

Measured ageing of commercial LG M50T 21700 cells (NMC811 / graphite-SiOx), the same
cell family as the Chen 2020 parameter set used for the NMC chemistry in this project.

- **Paper (peer-reviewed):** N. Kirkaldy, M. A. Samieian, G. J. Offer, M. Marinescu, Y. Patel.
  *Lithium-ion battery degradation: Comprehensive cycle ageing data and analysis for
  commercial 21700 cells.* Journal of Power Sources 603 (2024) 234185.
  https://doi.org/10.1016/j.jpowsour.2024.234185
- **Dataset:** https://doi.org/10.5281/zenodo.10637534 (licence CC-BY-4.0)
- **Files here:** the six "Processed Data" summary tables of Experiment 2 (cells A–F),
  obtained via https://github.com/jojusmathew/li-ion-aging-pybamm, which states they are
  unmodified copies. The beginning-of-life capacities agree with the paper's statistics.

## Test conditions (Experiment 2)
- Cycling between 70 and 85 % state of charge: 0.3C charge, 1C discharge.
- Chamber (base-cooling) set-points: 10 °C (cells A, B), 25 °C (C, D), 40 °C (E, F).
- 6,204 cycles over 258 days; a check-up (RPT) at 25 °C every ~3 weeks.

## Columns used
- `Days of degradation`: time since the start of ageing.
- `Age set av. temperature [°C]`: measured cell surface temperature during cycling.
- `C/10 Capacity [mA h]`, `SoH`: capacity at C/10 and its fraction of the initial value.
- `LLI`: loss of lithium inventory (fraction), from open-circuit-voltage fitting.
