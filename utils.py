import numpy as np

def compute_distance(lat1, lon1, lat2, lon2):
    dlat = (lat1 - lat2) * 110.574
    dlon = (lon1 - lon2) * 111.32 * np.cos(np.radians(lat2))
    return np.sqrt(dlat**2 + dlon**2)