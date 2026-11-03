import numpy as np
import cv2


def enhance(lr, sr):
    """Apply one conservative back-projection step toward LR consistency."""
    lr32 = np.asarray(lr, dtype=np.float32)
    sr32 = np.asarray(sr, dtype=np.float32)
    h, w = lr32.shape[:2]

    predicted_lr = cv2.resize(sr32, (w, h), interpolation=cv2.INTER_CUBIC)
    lr_residual = lr32 - predicted_lr
    correction = cv2.resize(
        lr_residual,
        (sr32.shape[1], sr32.shape[0]),
        interpolation=cv2.INTER_CUBIC,
    )
    return (sr32 + np.float32(0.20) * correction).astype(np.float32, copy=False)
