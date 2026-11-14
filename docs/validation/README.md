# Validation dossiers

One file per chemistry, each with the same five sections: the cells behind each part of the
model, what was fitted and how well, the checks against data not used in the fit, the range of
validity, and the known gaps.

- [NMC](NMC.md)
- [LFP](LFP.md)
- [NCA](NCA.md)
- [Sodium-ion](Na-ion.md)

Shared by all chemistries:
- **State estimation** (`scripts/validate_estimator_*.py`): SOC within 3.1 points on a real
  car's charge (Tesla Model 3), 2.3 points on 83 days of a home storage system, 1.4-4.9 points
  on drive cycles at 0-40 °C (US06: 7.6-14); rest-to-rest capacity within 2 %.
- **Uncertainty:** the dashboard's shaded band and the README give the life with its range.
- **Software:** the test suite (`pytest`) runs on every change (GitHub Actions).

The data licences are in [../data_licences.md](../data_licences.md); two validation datasets
are research only.
