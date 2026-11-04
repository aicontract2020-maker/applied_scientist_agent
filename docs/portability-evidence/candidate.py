import numpy as np


def enhance(lr, sr):
    """Compress only out-of-gamut RGB chroma while preserving BT.601 luma."""
    x = np.asarray(sr, dtype=np.float32)
    # Normalized BT.601 weights used by standard RGB-to-Y evaluation.
    w = np.array([0.299, 0.587, 0.114], dtype=np.float32)
    y = np.sum(x * w, axis=2, keepdims=True)
    d = x - y

    # Largest scale t in [0, 1] for which y + t*d is inside [0, 1].
    upper = np.where(d > 0.0, (1.0 - y) / np.maximum(d, np.float32(1e-12)), np.inf)
    lower = np.where(d < 0.0, (0.0 - y) / np.minimum(d, np.float32(-1e-12)), np.inf)
    t = np.minimum(np.float32(1.0), np.min(np.minimum(upper, lower), axis=2, keepdims=True))
    t = np.maximum(t, np.float32(0.0))
    out = y + t * d

    # If luminance itself is outside the representable interval, neutral clipping
    # is the only gamut point on the constant-luminance axis.
    out = np.where(y < 0.0, np.float32(0.0), out)
    out = np.where(y > 1.0, np.float32(1.0), out)
    return out.astype(np.float32, copy=False)
