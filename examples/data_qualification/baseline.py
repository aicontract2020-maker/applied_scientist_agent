"""Build synthetic metadata ONLY for testing the baseline admission boundary."""
import hashlib
import json
from pathlib import Path

from research_harness import data_admission as admission
from research_harness import data_qualification as dq

USE = 'SYNTHETIC SOFTWARE CHECK ONLY; no real data permission or experiment approval'


def qualification(root, adapter, source):
    root = Path(root).resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    draft, packet = root/'draft.json', root/'packet.json'
    dq.template(draft)
    content = json.loads(draft.read_text())
    content.update(id='synthetic-baseline-admission', **admission.context(adapter, source, USE))
    text = b'SYNTHETIC METADATA ONLY. NO REAL DATA OR PERMISSION.\n'
    (root/'note.txt').write_bytes(text)
    content['evidence'] = {'note': {'path': 'note.txt', 'source': 'synthetic software fixture',
                                  'locator': 'entire note', 'sha256': hashlib.sha256(text).hexdigest()}}
    for criterion in content['criteria'].values():
        criterion.update(state='supported', rationale='Synthetic assertion for software testing only', evidence=['note'])
    draft.write_text(json.dumps(content))
    result = dq.prepare(draft, packet)
    dq.decide(packet, result['sha256'], 'SYNTHETIC_REVIEWER', 'accept', 'Software fixture only')
    return admission.accepted_snapshot(packet, adapter, source, USE)
