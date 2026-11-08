"""Offline software demonstration. Every assertion and approval is SYNTHETIC."""
import argparse
import hashlib
import json
from pathlib import Path

from research_harness import data_qualification as dq


def demonstrate(output):
    root = Path(output).absolute()
    root.mkdir(parents=True, mode=0o700, exist_ok=False)
    note = b'SYNTHETIC SOFTWARE FIXTURE ONLY. No real data, permission or research evidence.\n'
    (root / 'synthetic-note.txt').write_bytes(note)
    statuses = {}
    # Independent software cases, not successive repairs of a failed study.
    for name, state in (('missing', 'unresolved'), ('incompatible', 'incompatible'), ('supported', 'supported')):
        draft = root / (name + '-draft.json')
        packet = root / (name + '-packet.json')
        dq.template(draft)
        content = json.loads(draft.read_text())
        content.update(id='synthetic-' + name, task='software-demonstration',
                       dataset={'id': 'synthetic-only', 'version': '1', 'source': 'generated fixture'},
                       intended_use='Synthetic software demonstration; no actual dataset use')
        content['evidence'] = {'note': {'path': 'synthetic-note.txt', 'source': 'generated fixture',
                                      'locator': 'entire note', 'sha256': hashlib.sha256(note).hexdigest()}}
        for criterion in content['criteria'].values():
            criterion.update(state='supported', rationale='Synthetic assertion only', evidence=['note'])
        content['criteria']['permission']['state'] = state
        draft.write_text(json.dumps(content, indent=2) + '\n')
        prepared = dq.prepare(draft, packet)
        statuses[name] = prepared['status']
        if name == 'supported':
            accepted = dq.decide(packet, prepared['sha256'], 'SYNTHETIC_REVIEWER', 'accept', 'Software test only')
            statuses['synthetic_acceptance'] = accepted['status']
            assert accepted['execution_authorized'] is False
    result = {'synthetic_only': True, 'execution_authorized': False, 'statuses': statuses}
    (root / 'software-validation.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    print(json.dumps(demonstrate(args.out), indent=2))
