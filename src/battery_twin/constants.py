"""Values used by several modules, kept in one place so that they cannot drift apart."""
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"     # measured and published data, fitted values

# JRC rules for the carbon footprint of industrial batteries (CFB-IND, Andreasi Bassi et
# al. 2025): end of service life at >= 70 % of the initial capacity, and at most 1000
# equivalent full cycles per year. The TEA retires the battery at the same threshold by
# default, so that the TEA and the LCA share one functional unit (ISO/TS 14076).
CFB_MIN_EOL_SOH = 0.70
CFB_MAX_CYCLES_PER_YEAR = 1000
