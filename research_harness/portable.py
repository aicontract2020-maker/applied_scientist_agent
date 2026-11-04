"""Local setup and fresh-study creation; never rewrites historical experiments."""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'SwinIR': ('https://github.com/JingyunLiang/SwinIR.git', '6545850fbf8df298df73d81f3e8cba638787c8bd', ['models', 'utils', 'testsets/Set5']),
    'SelfExSR': ('https://github.com/jbhuang0604/SelfExSR.git', '8f6dd8c1d20cb7e8792a7177b4f6fd677633f598', ['data/Urban100/image_SRF_2']),
}
WEIGHT = 'assets/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x2.pth'
WEIGHT_SHA = '193b229909ca89cd8b55de9c9e7fce146ae759d59dfcd78d8feb9dd1d6fa0fd7'
WEIGHT_URL = 'https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/' + Path(WEIGHT).name


def environment_lock():
    if sys.platform == "linux":
        return "requirements-sr-linux-aarch64.lock.txt" if __import__("platform").machine()=="aarch64" else "requirements-sr-linux.lock.txt"
    return "requirements-sr.lock.txt"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(folder, *args):
    return subprocess.check_output(['git', '-C', str(folder), *args], text=True, stderr=subprocess.PIPE, timeout=300).strip()


def verify_sources(root=ROOT):
    for name, (_, revision, _) in SOURCES.items():
        folder = root/'external'/name
        if git(folder, 'rev-parse', 'HEAD') != revision:
            raise ValueError(f'{name} revision differs from the pinned version; use a fresh checkout or inspect it manually')
        git(folder, 'diff', '--exit-code', 'HEAD', '--')
    if sha(root/WEIGHT) != WEIGHT_SHA:
        raise ValueError('Checkpoint SHA-256 mismatch; do not run inference')
    # Fixed upstream source hashes, independent of the mutable local asset manifest.
    trusted = json.loads((root/'tasks/image_super_resolution/assets.lock.json').read_text())['inputs']
    for path in ['external/SwinIR/models/network_swinir.py', 'external/SwinIR/utils/util_calculate_psnr_ssim.py']:
        if sha(root/path) != trusted[path]:
            raise ValueError(f'Upstream evaluator/model changed: {path}')
    folder = root/'external/SelfExSR/data/Urban100/image_SRF_2'
    expected = {f'img_{i:03d}_SRF_2_{kind}.png' for i in range(1, 101) for kind in ('LR', 'HR')}
    if not all((folder/name).is_file() for name in expected):
        raise ValueError('Urban100 x2 requires all 100 original LR/HR pairs; rerun setup-assets')


def setup_assets(root=ROOT):
    root = Path(root).resolve()
    for name, (url, revision, sparse) in SOURCES.items():
        folder = root/'external'/name
        if not folder.exists():
            folder.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['git', 'clone', '--filter=blob:none', '--no-checkout', url, str(folder)], check=True, timeout=300)
            git(folder, 'sparse-checkout', 'set', *sparse)
            git(folder, 'checkout', '--detach', revision)
        else:
            if git(folder, 'rev-parse', 'HEAD') != revision:
                raise ValueError(f'{folder}: existing checkout is not pinned; refusing to reset user files')
            git(folder, 'diff', '--exit-code', 'HEAD', '--')
            # Add required paths without removing other studies' data.
            git(folder, 'sparse-checkout', 'add', *sparse)
    target = root/WEIGHT
    if target.exists():
        if sha(target) != WEIGHT_SHA: raise ValueError('Existing checkpoint has wrong hash; inspect/remove it manually')
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix('.download')
        digest = hashlib.sha256(); total = 0
        if partial.exists(): raise ValueError('Incomplete .download exists; inspect/move it before downloading again')
        try:
            with urllib.request.urlopen(WEIGHT_URL, timeout=60) as response, partial.open('xb') as out:
                while chunk := response.read(1024*1024):
                    total += len(chunk)
                    if total > 32*1024*1024: raise ValueError('Checkpoint download exceeds 32 MiB cap')
                    out.write(chunk); digest.update(chunk)
            if digest.hexdigest() != WEIGHT_SHA: raise ValueError('Downloaded checkpoint SHA-256 mismatch')
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
    verify_sources(root)
    files = [root/WEIGHT, *(root/'external/SelfExSR/data/Urban100/image_SRF_2').glob('*.png')]
    manifest = {'sources': {k: {'url': v[0], 'revision': v[1]} for k,v in SOURCES.items()},
                'files': {str(p.relative_to(root)): sha(p) for p in files},
                'rights': 'Third-party repositories, weights and datasets retain their respective terms; no redistribution grant implied.'}
    (root/'assets/manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return {'status': 'READY', 'manifest': str(root/'assets/manifest.json'), 'files': len(files)}


def new_study(name, root=ROOT):
    root = Path(root).resolve()
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', name):
        raise ValueError('Study id: 1–64 lowercase letters/digits/underscore/hyphen, starting with letter/digit')
    here = root/'local_studies'/name
    if here.exists(): raise ValueError('Study id already reserved. Inspect its result; never delete/recreate it to retry')
    verify_sources(root)
    template = root/'templates/sr'
    policy = json.loads((template/'policy.json').read_text())
    history = json.loads((template/'history.json').read_text())
    used = set(history['used_urban100_ids'])
    prior = []
    for path in sorted((root/'local_studies').glob('*/policy.json')):
        previous = json.loads(path.read_text()); used.update(previous['observation_ids'])
        policy['excluded_evidence_ids'] = sorted(set(policy['excluded_evidence_ids']) | set(previous['excluded_evidence_ids']))
        registration = root/'runs'/previous['study_id']/'registered.json'
        outcome = root/'runs'/previous['study_id']/'result.json'
        if registration.exists():
            plan = json.loads(registration.read_text())['plan']
            policy['excluded_evidence_ids'] = sorted(set(policy['excluded_evidence_ids']) | {item['source'].rsplit('/',1)[-1].split('v')[0] for item in plan['new_evidence']})
            if outcome.exists() and json.loads(outcome.read_text()).get('status') == 'STOP' and json.loads(outcome.read_text()).get('measurement_valid') is True:
                prior.append({'id': previous['study_id'], 'hypothesis': plan['hypothesis'], 'stop_route': plan['stop_route']})
                policy['stopped_route_compliance']['reuses_local_route_'+previous['study_id']] = False
    pool = [f'img_{i:03d}' for i in range(1,101) if f'img_{i:03d}' not in used]
    if len(pool) < 12: raise ValueError('Fewer than 12 unused Urban100 images remain. Stop: obtain new data and review a new protocol')
    ids = sorted(sorted(pool, key=lambda n: hashlib.sha256((name+':'+n).encode()).hexdigest())[:12])
    policy.update(study_id=name, observation_ids=ids)
    policy['controls'][0] = 'Twelve Urban100 x2 pairs selected by fixed study-id/filename hash excluding historical and local reserved IDs, before search; no image or score selection'
    task = (template/'TASK.md').read_text()+'\n## Local stopped routes (do not reopen)\n'+json.dumps(prior,indent=2)+'\nCopy stopped_route_compliance EXACTLY from policy.json; it includes all historical families and any local STOP routes.\n'
    here.mkdir(parents=True, exist_ok=False)
    (here/'policy.json').write_text(json.dumps(policy,indent=2)+'\n')
    (here/'TASK.md').write_text(task)
    (here/'literature.json').write_text('[]\n')
    shutil.copyfile(template/'labctl.py',here/'labctl.py')
    (here/'selection.json').write_text(json.dumps({'selected_ids':ids,'excluded_ids':sorted(used),'rule':'12 smallest SHA256(study_id:ID), sorted, before search/inference; reservations are not reclaimed automatically'},indent=2)+'\n')
    files = [* (root/'research_harness').glob('*.py'), root/'requirements-sr.txt', root/'requirements-sr.lock.txt', root/'requirements-sr-linux.lock.txt', root/'requirements-sr-linux-aarch64.lock.txt', root/WEIGHT,
             root/'external/SwinIR/models/network_swinir.py',root/'external/SwinIR/utils/util_calculate_psnr_ssim.py',
             *here.glob('*'), *template.glob('*')]
    if (root/'.cache/environment.freeze.txt').exists(): files.append(root/'.cache/environment.freeze.txt')
    for image in ids:
        files.extend(root/f'external/SelfExSR/data/Urban100/image_SRF_2/{image}_SRF_2_{kind}.png' for kind in ('LR','HR'))
    (here/'inputs.lock.json').write_text(json.dumps({'files':{str(p.relative_to(root)):sha(p) for p in files if p.is_file()},'runtime':{'python':sys.version,'executable':str(Path(sys.executable).resolve()),'platform':sys.platform,'architecture':__import__('platform').machine()}},indent=2)+'\n')
    return here
