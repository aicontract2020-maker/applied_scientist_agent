import numpy as np
import cv2


def enhance(lr, sr):
    """Correct a small global geometric displacement relative to the LR observation."""
    out = np.asarray(sr, dtype=np.float32)
    low = np.asarray(lr, dtype=np.float32)
    h, w = low.shape[:2]

    # BT.601 luminance is used only to estimate geometry; RGB is warped together.
    weights = np.array([0.299, 0.587, 0.114], dtype=np.float32)
    low_y = np.sum(low * weights, axis=2, dtype=np.float32)
    sr_y = np.sum(out * weights, axis=2, dtype=np.float32)
    reduced = cv2.resize(sr_y, (w, h), interpolation=cv2.INTER_AREA)

    # A Hann window suppresses boundary discontinuities in the global translation estimate.
    window = cv2.createHanningWindow((w, h), cv2.CV_32F)
    shift, response = cv2.phaseCorrelate(reduced, low_y, window)
    dx = float(np.clip(shift[0] * 2.0, -0.5, 0.5))
    dy = float(np.clip(shift[1] * 2.0, -0.5, 0.5))

    # Suppress unreliable motion estimates rather than moving a weakly correlated image.
    if (not np.isfinite(response)) or response < 0.10:
        dx = 0.0
        dy = 0.0
    matrix = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
    registered = cv2.warpAffine(out, matrix, (out.shape[1], out.shape[0]),
                                flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_REFLECT_101)
    return np.asarray(registered, dtype=np.float32)
