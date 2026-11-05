"""Synthetic pixels and a stub metric verify extraction, not scientific quality."""
import json
import tempfile
import unittest
from pathlib import Path

from research_harness.sr_evaluation import evaluate_sr
from research_harness.task_contracts import binding, SR_TASK

try:
    import numpy as np
    import cv2
except ImportError:
    np = cv2 = None


@unittest.skipIf(np is None or cv2 is None, 'SR numeric dependencies unavailable')
class SREvaluatorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.control = self.root/'control'
        self.output = self.control/'candidate-output'; self.output.mkdir(parents=True)
        metric = self.root/'external/SwinIR/utils/util_calculate_psnr_ssim.py'
        metric.parent.mkdir(parents=True)
        metric.write_text('''def calculate_psnr(pred, gt, crop_border, test_y_channel):
    assert crop_border == 2 and test_y_channel is True
    assert pred.dtype.name == "uint8" and pred.shape == gt.shape
    return (float(pred[0, 0, 0]) + 2*float(pred[0, 0, 1]) + 3*float(pred[0, 0, 2])) / 100
''')
        reference = self.control/'reference-png'; reference.mkdir()
        truth = self.root/'external/SelfExSR/data/Urban100/image_SRF_2'; truth.mkdir(parents=True)
        ids = [f'image-{i}' for i in range(10)]
        for key in ids:
            value = np.zeros((8, 8, 3)); value[:] = [1.2, .5, -.2]
            np.save(self.output/f'{key}.npy', value)
            cv2.imwrite(str(reference/f'{key}.png'), np.full((8, 8, 3), 10, dtype=np.uint8))
            cv2.imwrite(str(truth/f'{key}_SRF_2_HR.png'), np.zeros((8, 8, 3), dtype=np.uint8))
        (self.output/'timings.json').write_text(json.dumps([{'id': key, 'postprocess_seconds': .1} for key in ids]))
        (self.control/'reference-timings.json').write_text(json.dumps({key: {'plain_seconds': 1, 'strong_baseline_seconds': 2} for key in ids}))
        self.policy = {'task': binding(SR_TASK), 'dataset': 'Urban100', 'observation_ids': ids,
                       'primary_metric': {'direction': 'higher', 'unit': 'dB'}, 'minimum_effect': .05,
                       'max_latency_ratio': 2.5, 'bootstrap': {'resamples': 1000, 'seed': 42, 'confidence': .95}}

    def test_conversion_reference_timing_and_frozen_gates_preserved(self):
        result, rows = evaluate_sr(self.root, self.control, self.policy)
        self.assertEqual(rows[0]['candidate_score'], 10.21)  # clip, RGB/BGR, uint8 rounding: [0,128,255]
        self.assertEqual(rows[0]['baseline_score'], .6)
        self.assertEqual(rows[0]['candidate_latency_ms'], 1100)
        self.assertEqual(rows[0]['baseline_latency_ms'], 2000)
        self.assertAlmostEqual(result['mean_gain_db'], 9.61)
        self.assertEqual(result['latency_ratio'], .55)
        self.assertEqual(result['status'], 'CONTINUE')
        self.assertIn('Original-image', result['bootstrap_scope'])
        # Historical policy without binding must produce the exact same result.
        legacy = dict(self.policy); legacy.pop('task')
        self.assertEqual(evaluate_sr(self.root, self.control, legacy), (result, rows))

    def test_missing_or_linked_candidate_outputs_still_rejected(self):
        path = self.output/'image-0.npy'; path.unlink()
        with self.assertRaisesRegex(ValueError, 'identities'): evaluate_sr(self.root, self.control, self.policy)
        path.symlink_to(self.output/'image-1.npy')
        with self.assertRaisesRegex(ValueError, 'identities'): evaluate_sr(self.root, self.control, self.policy)
