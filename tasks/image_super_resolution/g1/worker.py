"""One-shot paired inference for the single planner-selected horizontal flip policy.

No training/tuning, no network, no case filtering, no access to HR for inference.
A separate metric process reads HR after all prediction files have been saved.
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


def infer(model, tensor):
    h, w = tensor.shape[-2:]
    hp, wp = (h // 8 + 1) * 8 - h, (w // 8 + 1) * 8 - w
    padded = torch.cat([tensor, torch.flip(tensor, [2])], 2)[:, :, :h + hp, :]
    padded = torch.cat([padded, torch.flip(padded, [3])], 3)[:, :, :, :w + wp]
    return model(padded)[..., :h * 2, :w * 2]


def candidate(model, tensor):
    return (infer(model, tensor) + torch.flip(infer(model, torch.flip(tensor, [3])), [3])) / 2


def save(tensor, path):
    image = tensor.squeeze().float().cpu().clamp(0, 1).numpy()
    image = np.transpose(image[[2, 1, 0], :, :], (1, 2, 0))
    if not cv2.imwrite(str(path), (image * 255.).round().astype(np.uint8)):
        raise ValueError('Prediction write failed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.seed != 0:
        raise ValueError('Deterministic execution identifier must be 0')
    root = Path(__file__).resolve().parents[3]
    task = root / 'tasks/image_super_resolution/g1'
    manifest = json.loads((task / 'execution.lock.json').read_text())
    protocol = json.loads((task / 'protocol.json').read_text())
    if protocol['intervention'] != {'kind': 'horizontal_flip_ensemble', 'step_size': 0}:
        raise ValueError('Only the frozen selected policy is implemented')
    for name, expected in manifest['inputs'].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Frozen input changed: {name}')
    torch.manual_seed(0)
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    sys.path.insert(0, str(root / 'external/SwinIR'))
    from models.network_swinir import SwinIR
    model = SwinIR(upscale=2, in_chans=3, img_size=64, window_size=8, img_range=1.,
                   depths=[6, 6, 6, 6], embed_dim=60, num_heads=[6, 6, 6, 6],
                   mlp_ratio=2, upsampler='pixelshuffledirect', resi_connection='1conv')
    checkpoint = torch.load(root / manifest['checkpoint'], map_location='cpu', weights_only=True)
    model.load_state_dict(checkpoint['params'], strict=True)
    model.eval()
    predictions = args.output.parent / 'predictions'
    for arm in ('baseline', 'candidate'):
        (predictions / arm).mkdir(parents=True, exist_ok=False)
    timings = []
    start_run = time.monotonic()
    with torch.no_grad():
        # Exactly one unscored, fixed small warmup for each arm, charged to runtime.
        warmup = torch.zeros(1, 3, 64, 64)
        infer(model, warmup)
        candidate(model, warmup)
        for index, name in enumerate(protocol['observation_ids']):
            path = root / f'external/SelfExSR/data/BSD100/image_SRF_2/{name}_SRF_2_LR.png'
            low = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if low is None:
                raise ValueError(f'Missing image: {name}')
            tensor = torch.from_numpy(np.transpose((low.astype(np.float32) / 255.)[:, :, [2, 1, 0]], (2, 0, 1))).float().unsqueeze(0)
            order = ('baseline', 'candidate') if index % 2 == 0 else ('candidate', 'baseline')
            timing = {'id': name}
            for arm in order:
                begin = time.monotonic()
                pred = infer(model, tensor) if arm == 'baseline' else candidate(model, tensor)
                timing[f'{arm}_latency_ms'] = (time.monotonic() - begin) * 1000
                save(pred, predictions / arm / f'{name}.png')
                del pred
            timings.append(timing)
            print(json.dumps({'completed_images': index + 1, 'of': len(protocol['observation_ids']), **timing}), flush=True)
    (predictions / 'timings.json').write_text(json.dumps(timings, indent=2))
    subprocess.run([sys.executable, str(task / 'evaluate.py'), '--predictions', str(predictions),
                    '--output', str(args.output.parent / 'metrics.json')], check=True, timeout=90)
    metrics = json.loads((args.output.parent / 'metrics.json').read_text())
    elapsed = time.monotonic() - start_run
    artifact_bytes = sum(x.stat().st_size for x in args.output.parent.rglob('*') if x.is_file())
    resources = {'device': 'cpu', 'threads': 4, 'precision': 'float32', 'inference_wall_seconds': elapsed,
                 'parent_peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                 'child_peak_rss_bytes': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                 'rss_note': 'macOS bytes; peaks are not simultaneous',
                 'setup_disk_bytes': manifest['setup_disk_bytes'], 'artifact_bytes': artifact_bytes,
                 'bootstrap_unit': 'Original image, not patch or repeated inference',
                 'timing_scope': 'One warmed forward per arm and image; alternating order; excludes image IO; not a production latency benchmark'}
    (args.output.parent / 'resources.json').write_text(json.dumps(resources, indent=2))
    output = {k: metrics[k] for k in ('baseline_score', 'candidate_score', 'observations')}
    output.update(seed=0, validity={name: True for name in protocol['validity_checks']},
                  measurements={'storage_byte_hours': (manifest['setup_disk_bytes'] + artifact_bytes) * elapsed / 3600,
                                'latency_ms': sum(r['candidate_latency_ms'] for r in timings) / len(timings)})
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
