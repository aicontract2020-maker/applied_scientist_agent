"""Freeze inputs before running G0. No inference is performed by this script."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK = ROOT / 'tasks/image_super_resolution'
REVISION = '6545850fbf8df298df73d81f3e8cba638787c8bd'
actual = subprocess.check_output(['git', '-C', str(ROOT / 'external/SwinIR'), 'rev-parse', 'HEAD'], text=True).strip()
if actual != REVISION:
    raise ValueError('Upstream revision does not match selection')
paths = ['external/SwinIR/models/network_swinir.py', 'external/SwinIR/utils/util_calculate_psnr_ssim.py',
         'external/SwinIR/main_test_swinir.py', 'tasks/image_super_resolution/worker.py',
         'tasks/image_super_resolution/evaluate.py', 'tasks/image_super_resolution/requirements.lock.txt',
         'assets/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x2.pth']
names = ['baby', 'bird', 'butterfly', 'head', 'woman']
for name in names:
    paths.extend([f'external/SwinIR/testsets/Set5/HR/{name}.png', f'external/SwinIR/testsets/Set5/LR_bicubic/X2/{name}x2.png'])
inputs = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in paths}
setup_bytes = sum(p.stat().st_size for folder in ('.venv-sr', '.cache', 'external', 'assets')
                  for p in (ROOT / folder).rglob('*') if p.is_file() and not p.is_symlink())
manifest = {'revision': REVISION, 'checkpoint': paths[-1] if paths[-1].endswith('.pth') else paths[6],
            'inputs': inputs, 'images': names, 'setup_disk_bytes': setup_bytes,
            'environment': sys.version, 'platform': sys.platform}
manifest_path = TASK / 'assets.lock.json'
with manifest_path.open('x') as f:
    json.dump(manifest, f, indent=2)
inputs['tasks/image_super_resolution/assets.lock.json'] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
protocol = {
 'id': 'swinir-g0-reproduction', 'design': 'deterministic_reproduction',
 'hypothesis': 'Official SwinIR-S x2 reproduces Set5 mean PSNR-Y 38.14 dB within 0.02 dB on this fixed CPU environment.',
 'baseline': f'Official SwinIR-S x2 DIV2K pretrained weights; source {REVISION}; reference Table 3, arXiv:2108.10257v1. This is reproduction, not global SOTA improvement.',
 'reference_score': 38.14, 'reference_source': 'https://arxiv.org/pdf/2108.10257 (v1, Table 3, lightweight x2 Set5)',
 'reproduction_tolerance': 0.02, 'minimum_effect': 0,
 'primary_metric': {'name': 'Set5 mean per-image PSNR-Y', 'direction': 'higher', 'unit': 'dB'},
 'controlled_variables': ['Exactly baby/bird/butterfly/head/woman and official x2 LR pairs; asset hashes frozen',
                         'CPU float32, four threads, fixed official lightweight architecture and weights',
                         'Official mirror padding, BGR/RGB conversions, uint8 rounding, crop border 2, Y-channel metrics',
                         'No model selection, training, self-ensemble, tiling, test-driven adjustments, or automatic retries'],
 'replicates': 1, 'seeds': [0], 'budget_usd': 0.20,
 'validity_checks': ['All five frozen image pairs evaluated', 'Frozen assets and metric code unchanged', 'No training, tuning, or model changes'],
 'outcomes': {'go': 'The baseline pipeline is usable; plan one separately preregistered improvement study with distinct development and held-out data.',
              'stop': 'Stop this reproduction route; do not change the metric, model or tolerance to rescue the result.',
              'invalid': 'No scientific conclusion: log the precise prespecified validity/operational failure before considering a new measurement protocol.'},
 'cost_assumptions': {'compute_usd_per_hour': 'Local accounting proxy of USD 1 per allocated machine-hour, not an external invoice.',
                      'external_api_usd': 0, 'cloud_compute_usd': 0,
                      'unpriced': ['Hardware depreciation and electricity are not measured', 'Acquisition/setup time was not fully metered', 'Storage after the run is not included'],
                      'setup_disk_bytes': setup_bytes, 'retention': 'Keep source, weights, environment and artifacts locally until reviewed; actual disk footprint reported separately'},
 'execution': {'cwd': str(ROOT), 'command': [str(ROOT / '.venv-sr/bin/python'), 'tasks/image_super_resolution/worker.py',
                     '--manifest', 'tasks/image_super_resolution/assets.lock.json', '--seed', '{seed}', '--output', '{output}'],
               'timeout_seconds': 600, 'compute_usd_per_hour': 1,
               'fixed_costs': {'data_usd': 0, 'storage_usd': 0, 'tuning_usd': 0}, 'inputs': inputs}}
with (TASK / 'g0-protocol.json').open('x') as f:
    json.dump(protocol, f, indent=2)
print(json.dumps({'protocol': str(TASK / 'g0-protocol.json'), 'setup_disk_bytes': setup_bytes}, indent=2))
