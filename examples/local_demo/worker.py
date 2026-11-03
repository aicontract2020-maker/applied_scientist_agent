"""Synthetic plumbing demo. Scores are fixtures, NOT research evidence."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--seed', type=int, required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args()
print(f'SYNTHETIC DEMO: seed={args.seed}; no model was trained.')
Path(args.output).write_text(json.dumps({
    'seed': args.seed,
    'baseline_score': 10,
    'candidate_score': 9,
    'validity': {'No test leakage': True, 'Evaluation implementation unchanged': True},
    'measurements': {'storage_byte_hours': 0, 'latency_ms': 0},
}))
