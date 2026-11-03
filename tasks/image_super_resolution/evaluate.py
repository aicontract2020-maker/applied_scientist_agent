"""Fixed image evaluator: loads saved predictions and HR images, never a model."""
import argparse
import importlib.util
import json
from pathlib import Path

import cv2


def evaluate(root, predictions, output):
    spec = importlib.util.spec_from_file_location('frozen_metrics', root / 'external/SwinIR/utils/util_calculate_psnr_ssim.py')
    metrics = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(metrics)
    names = ['baby', 'bird', 'butterfly', 'head', 'woman']
    if {p.stem for p in predictions.glob('*.png')} != set(names):
        raise ValueError('Predictions must contain exactly the five preregistered Set5 images')
    rows = []
    for name in names:
        pred = cv2.imread(str(predictions / f'{name}.png'), cv2.IMREAD_COLOR)
        target = cv2.imread(str(root / f'external/SwinIR/testsets/Set5/HR/{name}.png'), cv2.IMREAD_COLOR)
        if pred is None or target is None or pred.shape != target.shape:
            raise ValueError(f'Invalid prediction/target dimensions: {name}')
        rows.append({'image': name,
                     'psnr_y': metrics.calculate_psnr(pred, target, crop_border=2, test_y_channel=True),
                     'ssim_y': metrics.calculate_ssim(pred, target, crop_border=2, test_y_channel=True)})
    report = {'per_image': rows, 'psnr_y': sum(r['psnr_y'] for r in rows) / 5,
              'ssim_y': sum(r['ssim_y'] for r in rows) / 5}
    output.write_text(json.dumps(report, indent=2, allow_nan=False))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--predictions', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    evaluate(args.root, args.predictions, args.output)
