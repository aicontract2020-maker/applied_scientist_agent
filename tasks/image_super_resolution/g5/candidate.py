import numpy as np


def enhance(lr, sr):
    """Select a nearby 8-bit RGB lattice point that best preserves float BT.601 Y."""
    x = np.asarray(sr, dtype=np.float32)
    z = np.clip(x, 0.0, 1.0) * np.float32(255.0)
    lo = np.floor(z)
    hi = np.minimum(lo + np.float32(1.0), np.float32(255.0))
    target_y = (z[..., 0] * np.float32(0.299) +
                z[..., 1] * np.float32(0.587) +
                z[..., 2] * np.float32(0.114))

    best = lo.copy()
    best_err = np.full(z.shape[:2], np.float32(np.inf), dtype=np.float32)
    best_rgb_err = np.full(z.shape[:2], np.float32(np.inf), dtype=np.float32)

    # The eight floor/ceiling corners are the nearest enclosing RGB lattice cell.
    for mask in range(8):
        r = hi[..., 0] if (mask & 1) else lo[..., 0]
        g = hi[..., 1] if (mask & 2) else lo[..., 1]
        b = hi[..., 2] if (mask & 4) else lo[..., 2]
        y = (r * np.float32(0.299) + g * np.float32(0.587) +
             b * np.float32(0.114))
        err = np.abs(y - target_y)
        rgb_err = ((r - z[..., 0]) ** 2 + (g - z[..., 1]) ** 2 +
                   (b - z[..., 2]) ** 2)
        take = (err < best_err) | ((err == best_err) & (rgb_err < best_rgb_err))
        best[..., 0] = np.where(take, r, best[..., 0])
        best[..., 1] = np.where(take, g, best[..., 1])
        best[..., 2] = np.where(take, b, best[..., 2])
        best_err = np.where(take, err, best_err)
        best_rgb_err = np.where(take, rgb_err, best_rgb_err)

    return (best / np.float32(255.0)).astype(np.float32)
