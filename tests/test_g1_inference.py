"""Synthetic software checks only: flip inversion, output geometry and quantization."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

AVAILABLE = all(importlib.util.find_spec(x) for x in ('torch', 'numpy', 'cv2'))


@unittest.skipUnless(AVAILABLE, 'Requires the optional pinned SR environment')
class InferenceContractTest(unittest.TestCase):
    def setUp(self):
        import torch
        from tasks.image_super_resolution.g1.worker import candidate, infer, save
        self.torch, self.candidate, self.infer, self.save = torch, candidate, infer, save

    def test_equivariant_model_and_odd_geometry(self):
        torch = self.torch
        image = torch.arange(45, dtype=torch.float32).reshape(1, 3, 3, 5)
        def upscale(x):
            return x.repeat_interleave(2, -2).repeat_interleave(2, -1)
        expected = upscale(image)
        self.assertTrue(torch.equal(self.infer(upscale, image), expected))
        self.assertTrue(torch.equal(self.candidate(upscale, image), expected))

    def test_inverse_flip_before_mean_and_exactly_two_forwards(self):
        torch = self.torch
        image = torch.zeros(1, 3, 3, 5)
        calls = []
        def biased(x):
            calls.append(1)
            y = x.repeat_interleave(2, -2).repeat_interleave(2, -1)
            return y + torch.arange(y.shape[-1], dtype=y.dtype)[None, None, None, :]
        output = self.candidate(biased, image)
        self.assertEqual(len(calls), 2)
        self.assertTrue(torch.equal(output, torch.full((1, 3, 6, 10), 4.5)))

    def test_save_clamps_quantizes_and_converts_rgb_to_bgr(self):
        import cv2
        torch = self.torch
        image = torch.tensor([-1, 0.5, 2]).reshape(1, 3, 1, 1).expand(1, 3, 2, 2)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'prediction.png'
            self.save(image, path)
            self.assertEqual(cv2.imread(str(path))[0, 0].tolist(), [255, 128, 0])
