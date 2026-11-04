"""Agent-side file RPC client. Controller validates every request independently."""
import argparse
import json
import time
import uuid
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('operation', choices=('check', 'register', 'run', 'status', 'read'))
parser.add_argument('--url')
parser.add_argument('--full', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parent
name = uuid.uuid4().hex + '.json'
path = root / 'requests' / name
partial = path.with_suffix('.tmp')
partial.write_text(json.dumps({'operation': args.operation, 'url': args.url, 'full': args.full}))
partial.replace(path)
response = root / 'responses' / name
start = time.monotonic()
while not response.exists():
    if time.monotonic() - start > 760:
        raise SystemExit('Controller response timeout. Do not duplicate the request or rerun an experiment.')
    time.sleep(.2)
print(response.read_text())
