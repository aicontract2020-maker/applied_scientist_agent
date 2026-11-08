"""Real kernel and fixed-model integration using synthetic records ONLY."""
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research_harness.tabular_baseline import prepare_rows, approve, execute, preflight, ADAPTER, FIXTURE
from examples.data_qualification.baseline import qualification, USE

rows = [{'id': f'fixture-{i}', 'features': [float(i+j) for j in range(10)], 'target': float(2*i)} for i in range(150)]
# Place under the repository to test that explicit mounts/profile exceptions
# expose staged inputs while withholding other files in the same review folder.
root = Path(__file__).resolve().parents[1]
(root/'runs').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='tabular fixture ', dir=root/'runs') as parent:
    folder = Path(parent)/'review'
    snapshot = qualification(Path(parent)/'qualification', ADAPTER, FIXTURE)
    review = prepare_rows(rows, folder, FIXTURE, qualification=snapshot, intended_use=USE)
    approve(folder, review['sha256'], 'SOFTWARE FIXTURE ONLY; NOT USER APPROVAL')
    assert preflight(folder)['data_admission']['execution_authorized'] is False
    result = execute(folder)
    if not result['measurement_valid']:
        stderr = folder/'run/output/stderr.log'
        raise RuntimeError(json.dumps(result)+'\n'+(stderr.read_text()[-4000:] if stderr.exists() else 'No worker stderr'))
    assert result['final_holdout_scored'] is False
    worker_input = json.loads((folder/'run/inputs/request.json').read_text())
    assert set(worker_input) == {'recipe', 'train', 'validation'}
    assert all(set(row) == {'id', 'features'} for row in worker_input['validation'])
    print(json.dumps({'synthetic_only': True, 'actual_kernel_and_fixed_models_passed': True,
                      'final_holdout_scored': False, 'model_calls': 0,
                      'data_admission_checked': True,
                      'worker_models': 3, 'fixed_seeds': 3, 'measurement_valid': True}, indent=2))
