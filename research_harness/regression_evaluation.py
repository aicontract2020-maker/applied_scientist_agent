"""Trusted numeric evaluation, never prediction-code execution or live research.

Inputs are already produced records. Hash binding does not prove label isolation,
baseline strength, independence, honest timings or a prior training procedure.
"""
import statistics

from .core import digest, number, validate_protocol
from .task_contracts import REGRESSION_TASK


def evaluate_predictions(protocol, targets, baseline, candidate):
    validate_protocol(protocol)
    if protocol.get('task', {}).get('id') != REGRESSION_TASK:
        raise ValueError('A bound tabular-regression protocol is required')
    ids = protocol['observation_ids']

    def indexed(records, fields):
        if not isinstance(records, list) or len(records) != len(ids):
            raise ValueError('Every frozen row must appear exactly once')
        table = {}
        for row in records:
            if not isinstance(row, dict) or set(row) != {'id', *fields}:
                raise ValueError('Record has missing or unknown fields')
            key = row['id']
            if not isinstance(key, str) or key not in ids or key in table:
                raise ValueError('Unknown or duplicate row ID')
            for field in fields:
                number(row[field], field, 1e-12 if field == 'latency_ms' else None)
            table[key] = row
        return table

    truth = indexed(targets, ('target',))
    ref = indexed(baseline, ('prediction', 'latency_ms'))
    pred = indexed(candidate, ('prediction', 'latency_ms'))
    expected = (protocol['dataset']['sha256'], protocol['intervention']['baseline_sha256'],
                protocol['intervention']['candidate_sha256'])
    if tuple(map(digest, (targets, baseline, candidate))) != expected:
        raise ValueError('Target/baseline/candidate content differs from preregistration')
    rows = [{'id': key, 'baseline_score': abs(ref[key]['prediction'] - truth[key]['target']),
             'candidate_score': abs(pred[key]['prediction'] - truth[key]['target']),
             'baseline_latency_ms': ref[key]['latency_ms'], 'candidate_latency_ms': pred[key]['latency_ms']}
            for key in ids]
    for row in rows:
        number(row['baseline_score'], 'absolute error')
        number(row['candidate_score'], 'absolute error')
    return {'baseline_score': statistics.mean(r['baseline_score'] for r in rows),
            'candidate_score': statistics.mean(r['candidate_score'] for r in rows), 'observations': rows}
