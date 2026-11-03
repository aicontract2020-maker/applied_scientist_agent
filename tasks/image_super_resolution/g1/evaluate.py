"""Frozen evaluator reads completed PNG predictions, HR and timings; no model."""
import argparse
import importlib.util
import json
import statistics
from pathlib import Path

import cv2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--predictions', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    manifest = json.loads((root / 'tasks/image_super_resolution/g1/data.lock.json').read_text())
    ids = manifest['holdout_ids']
    spec = importlib.util.spec_from_file_location('frozen_metrics', root / 'external/SwinIR/utils/util_calculate_psnr_ssim.py')
    metrics = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(metrics)
    timing_rows = json.loads((args.predictions / 'timings.json').read_text())
    if [r['id'] for r in timing_rows] != ids:
        raise ValueError('Frozen observation order or timing identities changed')
    for arm in ('baseline', 'candidate'):
        if {x.stem for x in (args.predictions / arm).glob('*.png')} != set(ids):
            raise ValueError('Missing, extra, or selectively reported image predictions')
    rows = []
    ssim = {'baseline': [], 'candidate': []}
    for name, timing in zip(ids, timing_rows):
        target = cv2.imread(str(root / f'external/SelfExSR/data/BSD100/image_SRF_2/{name}_SRF_2_HR.png'), cv2.IMREAD_COLOR)
        row = {'id': name, 'baseline_latency_ms': timing['baseline_latency_ms'], 'candidate_latency_ms': timing['candidate_latency_ms']}
        for arm in ('baseline', 'candidate'):
            pred = cv2.imread(str(args.predictions / arm / f'{name}.png'), cv2.IMREAD_COLOR)
            if pred is None or target is None or pred.shape != target.shape:
                raise ValueError(f'Dimension mismatch: {name}')
            row[f'{arm}_score'] = metrics.calculate_psnr(pred, target, crop_border=2, test_y_channel=True)
            ssim[arm].append(metrics.calculate_ssim(pred, target, crop_border=2, test_y_channel=True))
        rows.append(row)
    report = {'observations': rows,
              'baseline_score': statistics.mean(r['baseline_score'] for r in rows),
              'candidate_score': statistics.mean(r['candidate_score'] for r in rows),
              'ssim_y': {k: statistics.mean(v) for k, v in ssim.items()}}
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
