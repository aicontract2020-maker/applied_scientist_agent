"""Closed, versioned task contracts. Documents cannot supply executable plugins."""
from copy import deepcopy
import re

from .core import digest

SR_TASK = 'swinir-s-x2'
REGRESSION_TASK = 'tabular-regression'
_CONTRACTS = {
    SR_TASK: {
        'id': SR_TASK, 'version': 1, 'autonomous_research': True,
        'evaluator': 'sr-psnr-y-v1', 'metric': {'direction': 'higher', 'unit': 'dB'},
        'data': 'Fixed Urban100 x2 original-image pairs; private HR in controller',
        'baseline': 'Frozen two-pass horizontal-flip SwinIR-S x2 reference',
        'intervention': 'One frozen deterministic postprocess; preregistration intervention review required for new studies',
        'uncertainty': 'Original-image paired bootstrap; no training replication claim',
        'budget': 'Frozen policy limits; one experiment; model invoice may be unknown',
        'execution': 'Existing macOS Seatbelt / Linux Bubblewrap broker only',
    },
    REGRESSION_TASK: {
        'id': REGRESSION_TASK, 'version': 1, 'autonomous_research': False,
        'evaluator': 'regression-mae-v1', 'metric': {'name': 'MAE', 'direction': 'lower'},
        'data': 'Content-bound target records and frozen independent-row IDs; not time series or clustered rows',
        'baseline': 'Caller must identify strongest relevant reproduced fixed predictor; predictions are content-bound',
        'intervention': 'One fixed prediction table, content-bound before evaluation; no code execution or tuning',
        'uncertainty': 'Independent-row paired bootstrap; not training variability or proof of independence',
        'budget': 'Protocol budget and complete declared result costs; no billing enforcement',
        'execution': 'Trusted in-process numeric evaluator only; autonomous runner, memory and study audit unavailable',
    },
}


def contract(task_id):
    if not isinstance(task_id, str) or task_id not in _CONTRACTS:
        raise ValueError(f'Unknown built-in task: {task_id!r}')
    return deepcopy(_CONTRACTS[task_id])


def binding(task_id):
    item = contract(task_id)
    return {'id': task_id, 'version': item['version'], 'sha256': digest(item)}


def validate_binding(value):
    if not isinstance(value, dict) or set(value) != {'id', 'version', 'sha256'}:
        raise ValueError('Task binding requires only id, version and sha256')
    expected = binding(value['id'])
    if type(value['version']) is not int or value != expected:
        raise ValueError('Unknown or changed task contract version/digest')
    return contract(value['id'])


def list_tasks():
    return [dict(contract(key), binding=binding(key)) for key in _CONTRACTS]


def require_autonomous(task_id):
    item = contract(task_id)
    if not item['autonomous_research']:
        raise ValueError(f'{task_id} is evaluation-only; no autonomous isolation/review/memory adapter. No study started.')
    return item


def capabilities(task_id):
    contract(task_id)  # Closed registry; no external plugin loading.
    if task_id==SR_TASK:
        return {'task':task_id,'full_autonomous_cycle':True,'workflow':'research --task swinir-s-x2 --id ID',
                'handoff':'memory / study evidence','evaluation_binding':binding(task_id)}
    return {'task':task_id,'full_autonomous_cycle':False,'human_reviewed_workflow':True,
            'stages':['propose','execute'],'proposal_entry':'research --task tabular-regression --stage propose --baseline BASE --id ID',
            'execution_entry':'research --task tabular-regression --stage execute --review REVIEW --id FROZEN_PROPOSAL_ID',
            'handoff':'handoff (regression/Airfoil exclusions + data pauses) / tabular evidence','evaluation_binding':binding(task_id),
            'limits':'Pinned qualified Abalone/HGB feature pilot only; exact human approval, fresh data and closed-language review remain required'}


def validate_sr_policy(policy):
    # Historical immutable SR policies predate task bindings.
    if 'task' not in policy:
        return
    item = validate_binding(policy['task'])
    if item['id'] != SR_TASK:
        raise ValueError('SR runner cannot execute another task contract')
    metric = policy.get('primary_metric', {})
    if any(metric.get(k) != v for k, v in item['metric'].items()):
        raise ValueError('SR policy metric differs from task contract')


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def validate_task_protocol(p):
    item = validate_binding(p['task'])
    if item['id'] != REGRESSION_TASK or p.get('design') != 'paired_observations':
        raise ValueError('Task-bound Workspace protocols currently support only paired tabular regression')
    metric = p.get('primary_metric', {})
    if any(metric.get(k) != v for k, v in item['metric'].items()):
        raise ValueError('Regression task requires lower-is-better MAE')
    dataset = p.get('dataset')
    if (not isinstance(dataset, dict) or set(dataset) != {'id', 'sha256', 'observation_unit'}
            or not isinstance(dataset['id'], str) or not dataset['id'].strip()
            or not _sha(dataset['sha256']) or dataset['observation_unit'] != 'independent_row'):
        raise ValueError('Freeze dataset id, target-record sha256 and independent_row observation_unit')
    intervention = p.get('intervention')
    if (not isinstance(intervention, dict) or set(intervention) != {'kind', 'baseline_sha256', 'candidate_sha256'}
            or intervention['kind'] != 'fixed_predictions'
            or not all(_sha(intervention[k]) for k in ('baseline_sha256', 'candidate_sha256'))):
        raise ValueError('Freeze baseline and candidate prediction digests; only fixed_predictions supported')
    if 'execution' in p:
        raise ValueError('Evaluation-only task cannot attach execution commands')

