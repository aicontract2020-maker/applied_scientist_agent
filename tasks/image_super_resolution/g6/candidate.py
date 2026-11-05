import numpy as np


def enhance(lr, sr):
    """Project the plain SR prediction onto the valid normalized RGB cube."""
    return np.clip(sr, np.float32(0.0), np.float32(1.0)).astype(np.float32, copy=False)
