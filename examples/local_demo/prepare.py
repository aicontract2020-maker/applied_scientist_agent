"""Generate a portable synthetic demo protocol with absolute cwd and input hashes."""
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
protocol = json.loads((folder.parent / 'protocol.json').read_text())
protocol.update(id='synthetic-execution-demo', hypothesis='SYNTHETIC FIXTURE ONLY: exercise execution and decision gates; no scientific claim.')
protocol['baseline'] = 'Synthetic constant score fixture, not an empirical baseline'
protocol['execution'] = {
    'cwd': str(folder),
    'command': ['{python}', 'worker.py', '--seed', '{seed}', '--output', '{output}'],
    'timeout_seconds': 5,
    'compute_usd_per_hour': 0,
    'fixed_costs': {'data_usd': 0, 'storage_usd': 0, 'tuning_usd': 0},
    'inputs': {'worker.py': hashlib.sha256((folder / 'worker.py').read_bytes()).hexdigest()},
}
print(json.dumps(protocol, indent=2))
