import numpy as np


def enhance(lr, sr):
    """Remove a constant 2x2 phase-locked luminance offset from an x2 SR image."""
    x = np.asarray(sr, dtype=np.float32)
    h = (x.shape[0] // 2) * 2
    w = (x.shape[1] // 2) * 2
    if h == 0 or w == 0:
        return x.copy()

    # BT.601 luminance is the evaluation-relevant direction.  A shared RGB
    # offset changes luminance without changing chroma differences.
    y = (np.float32(0.299) * x[:h, :w, 0] +
         np.float32(0.587) * x[:h, :w, 1] +
         np.float32(0.114) * x[:h, :w, 2])
    blocks = y.reshape(h // 2, 2, w // 2, 2)
    block_mean = blocks.mean(axis=(1, 3), dtype=np.float32)

    offsets = np.empty((2, 2), dtype=np.float32)
    for py in range(2):
        for px in range(2):
            residual = blocks[:, py, :, px] - block_mean
            offsets[py, px] = np.float32(np.median(residual))

    # Centering prevents a global brightness shift. Full subtraction is the
    # exact correction under the preregistered constant phase-bias model.
    offsets -= offsets.mean(dtype=np.float32)
    out = x.copy()
    for py in range(2):
        for px in range(2):
            out[py:h:2, px:w:2, :] -= offsets[py, px]
    return out
