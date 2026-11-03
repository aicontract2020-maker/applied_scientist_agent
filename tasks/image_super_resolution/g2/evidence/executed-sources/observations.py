"""Paired original-image bootstrap for a single frozen deterministic comparison.

Intervals summarize image sampling variability, not independent training variation.
"""
import math
import random
import statistics

from .core import number


def validate_design(p):
    if p['replicates'] != 1 or type(p['replicates']) is not int or p['seeds'] != [0]:
        raise ValueError('Paired observations require one execution with seeds=[0]')
    if p['minimum_effect'] <= 0:
        raise ValueError('Paired observations require a positive minimum effect')
    ids = p.get('observation_ids')
    if not isinstance(ids, list) or len(ids) < 10 or len(ids) > 10000 or any(not isinstance(x, str) or not x.strip() for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('Freeze 10..10000 unique original observation IDs')
    bootstrap = p.get('bootstrap')
    if not isinstance(bootstrap, dict) or set(bootstrap) != {'resamples', 'seed', 'confidence'}:
        raise ValueError('bootstrap needs resamples, seed, confidence')
    if type(bootstrap['resamples']) is not int or not 1000 <= bootstrap['resamples'] <= 100000:
        raise ValueError('Bootstrap resamples must be 1000..100000')
    if type(bootstrap['seed']) is not int:
        raise ValueError('Bootstrap seed must be an integer')
    number(bootstrap['confidence'], 'confidence')
    if not 0.8 <= bootstrap['confidence'] <= 0.99:
        raise ValueError('Confidence must be 0.8..0.99')
    number(p.get('max_latency_ratio'), 'max_latency_ratio', 1)
    intervention = p.get('intervention')
    if not isinstance(intervention, dict) or set(intervention) != {'kind', 'step_size'}:
        raise ValueError('intervention needs kind and step_size')
    if intervention['kind'] not in ('horizontal_flip_ensemble', 'single_step_back_projection'):
        raise ValueError('Intervention outside the supported audited research space')
    expected = 0 if intervention['kind'] == 'horizontal_flip_ensemble' else 1
    if type(intervention['step_size']) not in (int, float) or intervention['step_size'] != expected:
        raise ValueError('Intervention parameter is fixed; tuning is not allowed')


def validate_result(p, result):
    rows = result.get('observations')
    if not isinstance(rows, list) or len(rows) != len(p['observation_ids']):
        raise ValueError('Must report every frozen original observation exactly once')
    ids = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'id', 'baseline_score', 'candidate_score', 'baseline_latency_ms', 'candidate_latency_ms'}:
            raise ValueError('Observation requires id, paired scores, and paired inference latencies')
        ids.append(row['id'])
        for key in ('baseline_score', 'candidate_score'):
            number(row[key], key)
        for key in ('baseline_latency_ms', 'candidate_latency_ms'):
            number(row[key], key, 1e-12)
    if any(not isinstance(x, str) for x in ids) or len(set(ids)) != len(ids) or set(ids) != set(p['observation_ids']):
        raise ValueError('Observation IDs must match preregistration, with no duplicates')
    for key in ('baseline_score', 'candidate_score'):
        if not math.isclose(result[key], statistics.mean(row[key] for row in rows), rel_tol=0, abs_tol=1e-9):
            raise ValueError('Aggregate score must match all observation scores')


def summarize(p, rows):
    ordered = {row['id']: row for row in rows}
    rows = [ordered[x] for x in p['observation_ids']]
    sign = 1 if p['primary_metric']['direction'] == 'higher' else -1
    effects = [sign * (row['candidate_score'] - row['baseline_score']) for row in rows]
    rng = random.Random(p['bootstrap']['seed'])
    means = sorted(statistics.mean(rng.choices(effects, k=len(effects))) for _ in range(p['bootstrap']['resamples']))
    alpha = (1 - p['bootstrap']['confidence']) / 2
    # Nearest-order-statistic percentile interval; rule frozen before measurement.
    lo = means[max(0, math.floor(alpha * (len(means) - 1)))]
    hi = means[min(len(means) - 1, math.ceil((1 - alpha) * (len(means) - 1)))]
    latency_ratio = sum(r['candidate_latency_ms'] for r in rows) / sum(r['baseline_latency_ms'] for r in rows)
    return {'observation_count': len(rows), 'observation_effects': effects,
            'observation_effect_std': statistics.stdev(effects),
            'bootstrap_interval': [lo, hi], 'bootstrap_confidence': p['bootstrap']['confidence'],
            'latency_ratio': latency_ratio,
            'bootstrap_scope': 'Original-image sampling variability; not training replication or proof against dataset contamination'}
