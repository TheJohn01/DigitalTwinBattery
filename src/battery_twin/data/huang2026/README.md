# Samsung INR21700-50E cycling at 0, 23 and 40 °C, 0.5/1C charge, 1/2C discharge

Capacity fade [%] against cycle number, mean of three cells per condition, read from
Figure 5b of Huang et al., "Experimental Study on the Impact of Aging Trajectories on
High-Nickel Ternary NCA Lithium-Ion Cells", Electronics 15(12), 2563 (2026),
doi 10.3390/electronics15122563 (open access, CC BY 4.0). The raw data are only available on
request from the authors, so the points were read by eye from the figure (about ±0.5 %-point
and ±10 cycles).

Protocol (Section 2.2): CC-CV charge at the given rate to 4.2 V (CV to 0.05C), 5 min rest,
CC discharge at the given rate to 2.5 V, 25 min rest; about 100 % depth of discharge; ESPEC
chamber. One 23 °C 1C/1C cell with an early sudden drop was excluded by the authors.

Used by `scripts/fit_ageing.py` (NCA step 3, the 23 and 40 °C rows) for the 50E's
charge-rate term `K_CH`, `T_CH` (ageing.NcaRefit). The 0 °C rows are kept as a record of the
fast low-temperature failure the model does not reproduce.
