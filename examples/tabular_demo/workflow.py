"""Synthetic second-task integration, not research or human approval.

Run from the checkout: python3 -m examples.tabular_demo.workflow --out NEW_DIR
All targets, predictions, latencies and costs below are software fixtures.
"""
import argparse
import json
from pathlib import Path

from research_harness.core import COST_FIELDS, Workspace, digest
from research_harness.regression_evaluation import evaluate_predictions
from research_harness.review import report
from research_harness.task_contracts import REGRESSION_TASK, binding


def fixture():
    ids = [f'row-{i:02}' for i in range(12)]
    targets = [{'id': key, 'target': i * 2.0} for i, key in enumerate(ids)]
    baseline = [{'id': r['id'], 'prediction': r['target'] + 2, 'latency_ms': 1} for r in targets]
    candidate = [{'id': r['id'], 'prediction': r['target'] + 2.25, 'latency_ms': 1} for r in targets]
    protocol = {
        'id': 'synthetic-tabular', 'task': binding(REGRESSION_TASK),
        'hypothesis': 'SOFTWARE FIXTURE: fixed candidate reduces MAE by at least 0.5 target units.',
        'baseline': 'SOFTWARE FIXTURE: fixed target+2 predictor; not a real strongest baseline.',
        'controlled_variables': ['Same twelve synthetic targets; all prediction records frozen before evaluation',
                                 'Fixed candidate; no training, selection, tuning, model or network call'],
        'primary_metric': {'name': 'MAE', 'direction': 'lower', 'unit': 'synthetic target units'},
        'design': 'paired_observations', 'minimum_effect': 0.5, 'replicates': 1, 'seeds': [0],
        'observation_ids': ids, 'bootstrap': {'resamples': 1000, 'seed': 42, 'confidence': 0.95},
        'max_latency_ratio': 2.5, 'dataset': {'id': 'synthetic-only-v1', 'sha256': digest(targets),
                                          'observation_unit': 'independent_row'},
        'intervention': {'kind': 'fixed_predictions', 'baseline_sha256': digest(baseline),
                         'candidate_sha256': digest(candidate)},
        'validity_checks': ['Frozen input digests and exact row identities checked'],
        'budget_usd': 0,
        'outcomes': {'go': 'Synthetic gate passed; no scientific or deployment claim.',
                     'stop': 'Close this fixture candidate; no tuning or replacement.',
                     'invalid': 'Record invalid fixture measurement; no automatic retry.'},
    }
    return protocol, targets, baseline, candidate


def demonstrate(output):
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    protocol, targets, baseline, candidate = fixture()
    inputs = root/'inputs.json'
    inputs.write_text(json.dumps({'synthetic_only': True, 'targets': targets, 'baseline': baseline,
                                 'candidate': candidate}, indent=2) + '\n')
    workspace = Workspace(root/'experiments')
    workspace.register(protocol)
    # Load the frozen protocol before the trusted numeric evaluator; never import a candidate.
    _, frozen, _ = workspace.load(protocol['id'])
    scores = evaluate_predictions(frozen, targets, baseline, candidate)
    result = dict(scores, seed=0, artifact=str(inputs),
                  validity={key: True for key in frozen['validity_checks']},
                  costs={key: 0 for key in COST_FIELDS})
    result['costs']['latency_ms'] = 1  # Synthetic, not a measured runtime/cost claim.
    decision = workspace.record(protocol['id'], result)
    (root/'decision.json').write_text(json.dumps(decision, indent=2) + '\n')
    report(workspace, protocol['id'], root/'REPORT.md')
    return {'synthetic_only': True, 'task': REGRESSION_TASK, 'status': decision['status'],
            'report': str(root/'REPORT.md'), 'note': 'All data, timings and costs are fixtures; no research or agent execution.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    print(json.dumps(demonstrate(parser.parse_args().out), indent=2))
