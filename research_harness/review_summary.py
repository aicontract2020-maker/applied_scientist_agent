"""Human-review summaries of verified frozen materials, never execution readiness."""
from copy import deepcopy
from pathlib import Path

from .core import digest
from .memory import read_json


WORKFLOWS = ('abalone-baseline-v1', 'abalone-candidate-v1',
             'airfoil-baseline-v1', 'airfoil-candidate-v1')


def _local_materials(folder):
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError('Review must be a regular directory')
    marker = folder/'EVIDENCE_ONLY.json'
    if marker.exists() or marker.is_symlink():
        raise ValueError('Imported evidence is audit-only; use its evidence verification command')


def _qualification(content):
    entry = content.get('data_admission')
    if entry is None:
        return {'status': 'ABSENT_SOFTWARE_FIXTURE_ONLY', 'execution_authorized': False}
    snapshot = entry['qualification']
    packet, decision = snapshot['packet'], snapshot['decision']
    return {'status': 'ACCEPTED_FOR_PROTOCOL_DESIGN_ONLY',
            'context': deepcopy(entry['context']), 'qualification_sha256': packet['sha256'],
            'decision_sha256': decision['sha256'], 'scope': decision['content']['scope'],
            'criteria': {key: value['state'] for key, value in packet['content']['criteria'].items()},
            'evidence_count': len(packet['content']['evidence']),
            'authenticity': 'UNVERIFIED', 'execution_authorized': False,
            'full_evidence': 'Read data_admission.qualification in the frozen packet; evidence text is not reproduced here.'}


def inspect(workflow_id, review):
    if not isinstance(workflow_id, str) or workflow_id not in WORKFLOWS:
        raise ValueError('Review summary supports the four Abalone/Airfoil workflows; SR uses sr-preflight. See task workflows.')
    folder = Path(review).absolute()
    _local_materials(folder)
    candidate = workflow_id.endswith('-candidate-v1')
    if candidate:
        _local_materials(folder/'baseline')
    if workflow_id == 'abalone-baseline-v1':
        from .tabular_baseline import load_review
        packet, _ = load_review(folder)
        base = packet
    elif workflow_id == 'airfoil-baseline-v1':
        from .airfoil_baseline import load_review
        packet, _ = load_review(folder)
        base = packet
    elif workflow_id == 'abalone-candidate-v1':
        from .tabular_trial import load_trial
        packet, _, _ = load_trial(folder)
        base = read_json(folder/'baseline/bundle.json')
        if (not isinstance(base, dict) or set(base) != {'content', 'sha256'}
                or base.get('sha256') != packet['content']['baseline_sha256']
                or digest(base.get('content')) != base.get('sha256')):
            raise ValueError('Baseline changed after native verification')
    else:
        from .airfoil_trial import load_trial
        packet, base, _, _ = load_trial(folder)
    content = packet['content']
    filename = 'trial.json' if candidate else 'bundle.json'
    # The recipe and proposal are exact frozen content, not generated paraphrases.
    # Deliberately exclude data rows, baseline predictions, literature full text,
    # private qualification evidence and mutable REVIEW.md / approval files.
    return {'schema_version': 1, 'status': 'FROZEN_MATERIALS_VERIFIED',
            'workflow_id': workflow_id, 'review': str(folder), 'packet_file': filename,
            'packet_sha256': packet['sha256'], 'read_only': True,
            'execution_authorized': False, 'execution_approval_checked': False,
            'current_constraints_checked': False, 'isolation_checked': False,
            'archived_baseline_audited': candidate,
            'protocol': deepcopy(content['recipe']),
            'proposal': deepcopy(content.get('proposal')),
            'reference': {'review_sha256': base['sha256'], 'recipe': deepcopy(base['content']['recipe']),
                          'planned_model': 'hgb' if workflow_id.startswith('abalone-') else 'extra_trees'} if candidate else None,
            'dataset': {'source': deepcopy(base['content']['source']), 'counts': deepcopy(content['counts']),
                        'unit': 'independent row' if workflow_id.startswith('abalone-') else 'condition group',
                        'partition_manifest_sha256': digest(base['content']['files'])},
            'data_qualification': _qualification(content),
            'source_file_count': len(content['sources']),
            'note': 'Frozen-material integrity only, not pending approval or current eligibility. The attempt may already be consumed or blocked. Read full evidence, obtain separate exact-hash approval and use the original preflight/execution checks. No training, new predictions, scoring of new results or model calls.'}
