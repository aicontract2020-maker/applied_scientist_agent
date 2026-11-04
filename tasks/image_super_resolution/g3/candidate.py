import numpy as np
import cv2


def enhance(lr, sr):
    """Shrink only weak luminance high-frequency coefficients in the SR result."""
    x = np.asarray(sr, dtype=np.float32)
    # Rec.601 luminance is used only to locate weak spatial detail.  The same
    # scalar correction is applied to RGB, avoiding chroma/hue changes.
    y = (np.float32(0.299) * x[:, :, 0] +
         np.float32(0.587) * x[:, :, 1] +
         np.float32(0.114) * x[:, :, 2])
    low = cv2.GaussianBlur(y, (3, 3), 0.55, borderType=cv2.BORDER_REFLECT_101)
    high = y - low

    # At |high| << one 8-bit code value, attenuate 25%; at real edges the
    # exponential gate rapidly tends to zero, leaving SwinIR unchanged.
    threshold = np.float32(1.0 / 255.0)
    gate = np.exp(-np.square(high / threshold)).astype(np.float32)
    correction = np.float32(-0.25) * high * gate
    return x + correction[:, :, None]
