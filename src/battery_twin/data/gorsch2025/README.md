# BYD Blade pulse resistance (Gorsch et al., 2025)

- **Paper:** J. Gorsch, J. Schneiders, M. Frieges, N. Kisseler, D. Klohs, H. Heimes, A. Kampker,
  M. Muñoz Castro, E. Siebecke. *Contrasting a BYD Blade prismatic cell and Tesla 4680 cylindrical
  cell with a teardown analysis of design and performance.* Cell Rep. Phys. Sci. 6 (2025) 102453.
  https://doi.org/10.1016/j.xcrp.2025.102453. Licence CC BY 4.0.
- **How the file was made:** `scripts/digitize_gorsch.py <paper.pdf> <folder>` reads the BYD markers
  of Fig. 8C (a raster image) by colour, with the axes calibrated on the grid lines.

| File | Content |
|---|---|
| `blade_dcr_20C.csv` | volume-specific heating at 1C vs SOC (Fig. 8C) and the resistance it implies, R = heating x 1.216 dm3 / 135 A² (mean of the 18 s 1C charge and discharge pulses at 20 °C, ISO 12405-4) |

The other Blade values used by `lfp_blade_params.py` (Table 1, Fig. 5 electrode sizes, Fig. 7
component masses) are typed in there with their figure numbers. Fig. 8A (resistance vs SOC and
10/20/40 °C) is a 3D surface and was not read.
