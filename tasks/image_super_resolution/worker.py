"""Audited deterministic baseline inference; no training, download, search or tuning.

Model outputs are saved before a separate metric process reads the HR images.
This separates responsibilities, not filesystem permissions.
"""
import argparse
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.seed != 0:
        raise ValueError('Deterministic execution identifier must be 0')
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads(args.manifest.read_text())
    for name, expected in manifest['inputs'].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Frozen input changed: {name}')
    torch.manual_seed(0)
    np.random.seed(0)
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    sys.path.insert(0, str(root / 'external/SwinIR'))
    from models.network_swinir import SwinIR
    model = SwinIR(upscale=2, in_chans=3, img_size=64, window_size=8, img_range=1.,
                   depths=[6, 6, 6, 6], embed_dim=60, num_heads=[6, 6, 6, 6],
                   mlp_ratio=2, upsampler='pixelshuffledirect', resi_connection='1conv')
    # Explicit CPU placement and restricted weight loading; never execute pickled objects.
    checkpoint = torch.load(root / manifest['checkpoint'], map_location='cpu', weights_only=True)
    model.load_state_dict(checkpoint['params'], strict=True)
    model.eval()
    outputs = args.output.parent / 'predictions'
    outputs.mkdir(exist_ok=False)
    timings = []
    begin = time.monotonic()
    with torch.no_grad():
        for name in manifest['images']:
            low = cv2.imread(str(root / f'external/SwinIR/testsets/Set5/LR_bicubic/X2/{name}x2.png'), cv2.IMREAD_COLOR)
            if low is None:
                raise ValueError(f'Missing input: {name}')
            low = low.astype(np.float32) / 255.
            tensor = torch.from_numpy(np.transpose(low[:, :, [2, 1, 0]], (2, 0, 1))).float().unsqueeze(0)
            h, w = tensor.shape[-2:]
            # Match the official extra-window mirror padding, including divisible sizes.
            hp = (h // 8 + 1) * 8 - h
            wp = (w // 8 + 1) * 8 - w
            tensor = torch.cat([tensor, torch.flip(tensor, [2])], 2)[:, :, :h + hp, :]
            tensor = torch.cat([tensor, torch.flip(tensor, [3])], 3)[:, :, :, :w + wp]
            start = time.monotonic()
            pred = model(tensor)[..., :h * 2, :w * 2]
            elapsed = time.monotonic() - start
            timings.append({'image': name, 'seconds': elapsed})
            image = pred.squeeze().float().cpu().clamp_(0, 1).numpy()
            image = np.transpose(image[[2, 1, 0], :, :], (1, 2, 0))
            image = (image * 255.).round().astype(np.uint8)
            if not cv2.imwrite(str(outputs / f'{name}.png'), image):
                raise ValueError('Prediction write failed')
            print(json.dumps({'image': name, 'inference_seconds': elapsed}), flush=True)
    subprocess.run([sys.executable, str(root / 'tasks/image_super_resolution/evaluate.py'),
                    '--root', str(root), '--predictions', str(outputs),
                    '--output', str(args.output.parent / 'metrics.json')], check=True, timeout=60)
    scores = json.loads((args.output.parent / 'metrics.json').read_text())
    duration = time.monotonic() - begin
    artifact_bytes = sum(p.stat().st_size for p in args.output.parent.rglob('*') if p.is_file())
    metadata = {'device': 'cpu', 'threads': 4, 'dtype': 'float32', 'seed_is_execution_id': True,
                'timings': timings, 'mean_inference_seconds': sum(x['seconds'] for x in timings) / 5,
                'peak_parent_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                'peak_child_rss_bytes': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                'rss_unit': 'bytes on macOS; parent/child peaks are not simultaneous peak memory',
                'asset_storage_bytes': manifest['setup_disk_bytes'],
                'storage_accounting': 'setup footprint + current artifacts, charged for worker wall duration only; retention excluded'}
    (args.output.parent / 'resources.json').write_text(json.dumps(metadata, indent=2))
    result = {'seed': 0, 'baseline_score': 38.14, 'candidate_score': scores['psnr_y'],
              'validity': {'All five frozen image pairs evaluated': len(scores['per_image']) == 5,
                           'Frozen assets and metric code unchanged': True,
                           'No training, tuning, or model changes': True},
              'measurements': {'storage_byte_hours': (manifest['setup_disk_bytes'] + artifact_bytes) * duration / 3600,
                               'latency_ms': metadata['mean_inference_seconds'] * 1000}}
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
