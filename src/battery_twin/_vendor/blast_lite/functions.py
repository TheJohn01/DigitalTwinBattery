import numpy as np


def rescale_soc(soc, rescaling_factor):
    # Rescale an soc vector by scaling dSOC by the rescaling factor.
    dSOC = np.diff(soc, prepend=soc[0])
    dSOC = dSOC * rescaling_factor
    soc = np.cumsum(dSOC) + soc[0]
    if np.max(soc) > 1 or np.min(soc) < 0:
        soc = np.maximum(0, np.minimum(1, soc))
    return soc
