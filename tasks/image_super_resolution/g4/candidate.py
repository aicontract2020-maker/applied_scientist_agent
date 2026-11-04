import numpy as np


def enhance(lr, sr):
    """Apply a fixed, image-global luminance contrast expansion."""
    x = np.asarray(sr, dtype=np.float32)
    # Rec.601-style luma is used only to obtain one image-global center.
    y = (np.float32(0.299) * x[..., 0] +
         np.float32(0.587) * x[..., 1] +
         np.float32(0.114) * x[..., 2])
    center = np.mean(y, dtype=np.float32)
    delta = np.float32(0.005) * (y - center)
    out = x + delta[..., None]
    return np.asarray(out, dtype=np.float32)
