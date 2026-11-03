"""Trusted preparation of fixed SwinIR inputs and the stronger existing reference.
No quality metric is calculated here; HR is read only by the controller evaluator.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]


def infer(model, x):
    h, w = x.shape[-2:]
    hp, wp = (h // 8 + 1) * 8 - h, (w // 8 + 1) * 8 - w
    y = torch.cat([x, torch.flip(x, [2])], 2)[:, :, :h + hp, :]
    y = torch.cat([y, torch.flip(y, [3])], 3)[:, :, :, :w + wp]
    return model(y)[..., :h * 2, :w * 2]


def rgb(value):
    return np.transpose(value.squeeze(0).cpu().numpy(), (1, 2, 0)).astype(np.float32)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--control', type=Path, required=True)
    parser.add_argument('--policy', type=Path, required=True)
    args = parser.parse_args()
    policy = json.loads(args.policy.read_text())
    inputs = args.control / 'candidate-inputs'; inputs.mkdir()
    refs = args.control / 'reference-png'; refs.mkdir()
    torch.set_num_threads(4); torch.set_num_interop_threads(1)
    torch.manual_seed(0); torch.use_deterministic_algorithms(True)
    sys.path.insert(0, str(ROOT / 'external/SwinIR'))
    from models.network_swinir import SwinIR
    model = SwinIR(upscale=2, in_chans=3, img_size=64, window_size=8, img_range=1.,
                   depths=[6, 6, 6, 6], embed_dim=60, num_heads=[6, 6, 6, 6],
                   mlp_ratio=2, upsampler='pixelshuffledirect', resi_connection='1conv')
    weights = torch.load(ROOT / 'assets/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x2.pth', map_location='cpu', weights_only=True)
    model.load_state_dict(weights['params'], strict=True); model.eval()
    timings = {}
    with torch.no_grad():
        z = torch.zeros(1, 3, 64, 64)
        infer(model, z); infer(model, z); infer(model, torch.flip(z, [3]))
        for index, name in enumerate(policy['observation_ids']):
            low = cv2.imread(str(ROOT / f'external/SelfExSR/data/Set14/image_SRF_2/{name}_SRF_2_LR.png'), cv2.IMREAD_COLOR)
            if low is None:
                raise ValueError('Missing frozen LR input')
            lr = low[:, :, ::-1].astype(np.float32) / 255.
            x = torch.from_numpy(np.transpose(lr.copy(), (2, 0, 1))).float().unsqueeze(0)
            arms = ('plain', 'strong') if index % 2 == 0 else ('strong', 'plain')
            for arm in arms:
                begin = time.monotonic()
                if arm == 'plain':
                    sr = infer(model, x)
                else:
                    stronger = (infer(model, x) + torch.flip(infer(model, torch.flip(x, [3])), [3])) / 2
                seconds = time.monotonic() - begin
                timings.setdefault(name, {})['plain_seconds' if arm == 'plain' else 'strong_baseline_seconds'] = seconds
            np.savez(inputs / f'{name}.npz', lr=lr, sr=rgb(sr))
            image = (np.clip(rgb(stronger)[:, :, ::-1], 0, 1) * 255.).round().astype(np.uint8)
            if not cv2.imwrite(str(refs / f'{name}.png'), image):
                raise ValueError('Reference PNG write failed')
            print(json.dumps({'reference_image': index + 1, 'total': len(policy['observation_ids'])}), flush=True)
    (args.control / 'reference-timings.json').write_text(json.dumps(timings, indent=2))


if __name__ == '__main__':
    main()
