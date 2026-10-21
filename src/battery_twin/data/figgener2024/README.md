# Home storage system 10, 2022 (Figgener et al., 2024)

- **Paper:** J. Figgener, J. van Ouwerkerk, D. Haberschusz, J. Bors, P. Woerner, M. Mennekes,
  F. Hildenbrand, C. Hecht, K.-P. Kairies, O. Wessels, D. U. Sauer. *Multi-year field
  measurements of home storage systems and their use in capacity estimation.* Nature Energy 9,
  1438-1447 (2024). https://doi.org/10.1038/s41560-024-01620-9
- **Data:** Zenodo, https://doi.org/10.5281/zenodo.12091223 (CC BY 4.0), files
  `2022_01_System_ID_10.csv` ... `2022_12_System_ID_10.csv` (1 s: time, power, voltage, current,
  battery housing temperature, room temperature, interpolation flag).
- **System:** a privately operated PV home storage system in Germany. The voltage (44-52 V on a
  sloping curve) matches the paper's 'MediumNMC' product with 46.8 V nominal and 8.8 kWh
  (Table 1), i.e. 13 NMC cells in series; the system ID is not mapped to a product in the paper,
  so this is inferred.

| File | Content |
|---|---|
| `system10_2022_1min.csv.gz` | One-minute means of the whole of 2022: time, current (+ = charging, as in the data), pack voltage, housing temperature. Written by `scripts/validate_estimator_storage.py <folder>`; used to test the SOC filter and the rest-to-rest capacity method. |
