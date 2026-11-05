"""Trusted SR image evaluator; candidate code is never imported here.

The existing controller owns private HR and calls this only after isolated execution.
Conversion, official metric, crop, reference and result format are unchanged.
"""
import importlib.util
import json
from .observations import summarize, passes_gates
from .task_contracts import validate_sr_policy


def evaluate_sr(root, control, policy):
    validate_sr_policy(policy)
    import cv2
    import numpy as np
    spec = importlib.util.spec_from_file_location('fixed_metrics', root / 'external/SwinIR/utils/util_calculate_psnr_ssim.py')
    metric = importlib.util.module_from_spec(spec); spec.loader.exec_module(metric)
    output = control / 'candidate-output'
    expected = set(policy['observation_ids'])
    files = list(output.glob('*.npy'))
    if {x.stem for x in files} != expected or any(x.is_symlink() or x.stat().st_nlink != 1 for x in files):
        raise ValueError('Candidate output identities or file types changed')
    timings = {r['id']: r for r in json.loads((output / 'timings.json').read_text())}
    baseline = json.loads((control / 'reference-timings.json').read_text())
    rows = []
    dataset = policy.get('dataset', 'Set14')
    for name in policy['observation_ids']:
        value = np.load(output / f'{name}.npy', allow_pickle=False)
        gt = cv2.imread(str(root / f'external/SelfExSR/data/{dataset}/image_SRF_2/{name}_SRF_2_HR.png'), cv2.IMREAD_COLOR)
        ref = cv2.imread(str(control / 'reference-png' / f'{name}.png'), cv2.IMREAD_COLOR)
        if value.shape != gt.shape or not np.isfinite(value).all():
            raise ValueError(f'Invalid candidate shape/value: {name}')
        pred = (np.clip(value[:, :, ::-1], 0, 1) * 255.).round().astype(np.uint8)
        rows.append({'id': name,
                     'baseline_score': metric.calculate_psnr(ref, gt, crop_border=2, test_y_channel=True),
                     'candidate_score': metric.calculate_psnr(pred, gt, crop_border=2, test_y_channel=True),
                     'baseline_latency_ms': baseline[name]['strong_baseline_seconds'] * 1000,
                     'candidate_latency_ms': (baseline[name]['plain_seconds'] + timings[name]['postprocess_seconds']) * 1000})
    summary = summarize(policy, rows)
    mean = sum(r['candidate_score'] - r['baseline_score'] for r in rows) / len(rows)
    passed = passes_gates(policy, mean, summary)
    result = {'status': 'CONTINUE' if passed else 'STOP', 'measurement_valid': True, 'mean_gain_db': mean,
              'baseline_psnr_y': sum(r['baseline_score'] for r in rows) / len(rows),
              'candidate_psnr_y': sum(r['candidate_score'] for r in rows) / len(rows),
              'reason': 'All frozen thresholds met.' if passed else 'Effect, interval, or latency did not meet the frozen adoption threshold.',
              **summary}
    return result, rows
