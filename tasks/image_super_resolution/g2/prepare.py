"""Freeze trusted task policy and input identity before starting the autonomous agent."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
names = [f'img_{i:03d}' for i in range(1, 15)]
policy = {'study_id': 'autonomous-g2', 'observation_ids': names,
          'primary_metric': {'name': 'Set14 mean paired PSNR-Y gain versus fixed two-pass reference', 'direction': 'higher', 'unit': 'dB'},
          'minimum_effect': 0.05, 'max_latency_ratio': 2.5,
          'bootstrap': {'resamples': 10000, 'seed': 20261103, 'confidence': 0.95},
          'controls': ['All 14 original Set14 x2 image pairs, frozen before candidate creation',
                       'Candidate: plain fixed SwinIR-S x2 prediction followed by one agent-authored deterministic array function',
                       'Comparator: existing fixed two-pass horizontal-flip SwinIR-S x2 reference; no optimization or reopening G1',
                       'CPU float32, four reference threads, same weights, official padding, RGB/uint8 conversion, Y metric, border crop 2',
                       'No training, extra weights, model forwards in candidate code, parameter sweeps, repeated holdout access, or automatic retries',
                       'All constants frozen in candidate.py and research.json before registration; synthetic checks only before registration'],
          'limits': {'agent_session_seconds': 900, 'reference_seconds': 300, 'candidate_seconds': 90,
                     'synthetic_checks': 3, 'experiments': 1, 'candidate_output_bytes': 268435456},
          'costs': {'local_proxy_usd_per_machine_hour': 1, 'max_session_proxy_usd': 0.5,
                    'actual_model_billing_usd': None, 'unpriced': ['setup time', 'electricity and depreciation', 'long-term artifact retention']},
          'baseline_scope': 'Stronger existing inference reference within frozen weights; not an exhaustive global SR SOTA comparison'}
files = ['research_harness/autonomy.py', 'research_harness/autonomous_candidate.py', 'research_harness/autonomous_reference.py',
         'research_harness/observations.py', 'external/SwinIR/models/network_swinir.py',
         'external/SwinIR/utils/util_calculate_psnr_ssim.py', 'tasks/image_super_resolution/requirements.lock.txt',
         'assets/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x2.pth',
         'tasks/image_super_resolution/g2/TASK.md', 'tasks/image_super_resolution/g2/literature.json',
         'tasks/image_super_resolution/g2/labctl.py']
for name in names:
    files.extend([f'external/SelfExSR/data/Set14/image_SRF_2/{name}_SRF_2_HR.png',
                  f'external/SelfExSR/data/Set14/image_SRF_2/{name}_SRF_2_LR.png'])
for target,value in [('policy.json',policy),('inputs.lock.json',{'files':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},
                                                              'note':'Set14 quality was not scored in G0/G1. Agent never receives HR paths/files.'})]:
    with (HERE/target).open('x') as stream:
        json.dump(value,stream,indent=2)
print('Frozen G2 policy and trusted inputs. No candidate code or algorithm supplied.')
