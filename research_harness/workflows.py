"""Discover fixed workflows and delegate read-only checks; never launch research."""
from copy import deepcopy
from pathlib import Path

from .portable import ROOT


# Descriptive capabilities, deliberately separate from frozen numerical contracts.
_WORKFLOWS = {
    'swinir-s-x2': {
        'dataset': 'Fixed Urban100 x2; unused images only',
        'unit': 'image',
        'automation': 'autonomous literature, hypothesis, code and one registered experiment',
        'review_required': 'Existing explicitly authorized research scope; frozen local study',
        'preparation': 'portable.new_study (also called by research for a new ID)',
        'execution': 'autonomous --study PATH --out CHECKOUT/runs/ID --literature',
        'evaluation_binding': 'swinir-s-x2 v1',
        'preflight_python': '>=3.10',
        'archived_prediction_audit': False,
    },
    'abalone-baseline-v1': {
        'dataset': 'Fixed UCI Abalone', 'unit': 'independent row',
        'automation': 'fixed baseline qualification; no research actor',
        'review_required': 'Data qualification and exact-hash baseline-only human approval',
        'preparation': 'tabular prepare', 'execution': 'tabular baseline --review PATH',
        'evaluation_binding': 'Frozen Abalone baseline recipe and source inventory',
        'preflight_python': '>=3.10', 'archived_prediction_audit': False,
    },
    'abalone-candidate-v1': {
        'dataset': 'Fixed UCI Abalone with qualified HGB baseline', 'unit': 'independent row',
        'automation': 'agent proposes; human reviews; one frozen candidate executes',
        'review_required': 'Candidate-scoped data qualification and exact-hash trial human approval',
        'preparation': 'research --task tabular-regression --id ID --stage propose',
        'execution': 'research --task tabular-regression --id ID --stage execute --review PATH',
        'evaluation_binding': 'Frozen Abalone candidate recipe and source inventory',
        'preflight_python': '>=3.10', 'archived_prediction_audit': True,
    },
    'airfoil-baseline-v1': {
        'dataset': 'Fixed UCI Airfoil Self-Noise', 'unit': 'condition group',
        'automation': 'fixed grouped baseline qualification; no research actor',
        'review_required': 'Data qualification and exact-hash baseline-only human approval',
        'preparation': 'airfoil prepare', 'execution': 'airfoil baseline --review PATH',
        'evaluation_binding': 'Frozen Airfoil grouped recipe and source inventory',
        'preflight_python': '>=3.10', 'archived_prediction_audit': False,
    },
    'airfoil-candidate-v1': {
        'dataset': 'Fixed UCI Airfoil Self-Noise with qualified Extra Trees baseline',
        'unit': 'condition group',
        'automation': 'fixed reviewed Strouhal feature; no autonomous proposal actor',
        'review_required': 'Candidate-scoped data qualification and exact-hash trial human approval',
        'preparation': 'airfoil prepare-trial', 'execution': 'airfoil execute-trial --review PATH',
        'evaluation_binding': 'Frozen Airfoil candidate recipe and source inventory',
        'preflight_python': '3.12 (historical baseline audit)', 'archived_prediction_audit': True,
    },
}


def workflow(workflow_id):
    if not isinstance(workflow_id, str) or workflow_id not in _WORKFLOWS:
        raise ValueError('Unknown workflow; use task workflows for supported IDs')
    return dict(deepcopy(_WORKFLOWS[workflow_id]), id=workflow_id,
                frozen_review_summary=(None if workflow_id == 'swinir-s-x2' else
                                       f'task review --workflow {workflow_id} --review PATH'),
                environment_check=('doctor' if workflow_id == 'swinir-s-x2' else
                                   'airfoil doctor' if workflow_id.startswith('airfoil-') else 'tabular doctor'),
                execution_python='3.12',
                execution_platforms=['macOS Apple Silicon', 'Linux x86_64/aarch64 with Bubblewrap'],
                readiness='NOT_CHECKED', execution_authorized=False)


def catalog():
    return {'schema_version': 1, 'read_only': True, 'execution_authorized': False,
            'workflows': [workflow(key) for key in _WORKFLOWS],
            'note': 'Fixed workflows, not arbitrary dataset adapters. Listing does not check installation, data or approval.'}


def check(workflow_id, review, *, root=ROOT):
    """Use native checks unchanged. No writes, execution, environment or isolation probe."""
    selected = workflow(workflow_id)  # Reject unknown routes before inspecting paths.
    root = Path(root).resolve(strict=True)
    review = Path(review).absolute()
    if not root.is_dir() or not review.is_dir():
        raise ValueError('Root and review must be existing directories')
    if workflow_id == 'swinir-s-x2':
        from .sr_preflight import preflight
    elif workflow_id == 'abalone-baseline-v1':
        from .tabular_baseline import preflight
    elif workflow_id == 'abalone-candidate-v1':
        from .tabular_trial import preflight_trial as preflight
    elif workflow_id == 'airfoil-baseline-v1':
        from .airfoil_baseline import preflight
    else:
        from .airfoil_trial import preflight
    result = preflight(review, root=root)
    if (result.get('read_only') is not True or result.get('execution_authorized') is not False
            or result.get('status') not in ('PRECHECK_PASSED', 'READY_FOR_LAUNCH_CHECKS')):
        raise ValueError('Native preflight did not return a read-only, non-authorizing pass')
    return {'schema_version': 1, 'status': 'PRECHECK_PASSED', 'read_only': True,
            'execution_authorized': False, 'isolation_checked': False,
            'workflow': selected, 'root': str(root), 'review': str(review), 'checks': result,
            'note': 'Snapshot only. Execution rechecks current state, original approval and isolation. No reservation or transferable permission was created.'}
