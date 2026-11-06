"""Pinned Airfoil intake and target-blind condition grouping; never fit a model."""
import hashlib
import io
from pathlib import Path
import urllib.request
import zipfile

from .core import digest, number
from .tabular_data import FILES, write_json

SOURCE = {
    'id': 'uci-airfoil-condition-v1',
    'url': 'https://archive.ics.uci.edu/dataset/291/airfoil+self-noise',
    'download': 'https://archive.ics.uci.edu/static/public/291/airfoil+self+noise.zip',
    'archive_sha256': '5c7767ba53ad827d3f48ba1eb9434117f4892df8f10bc4c99e118a9e8a7ae07c',
    'raw_sha256': '74c75fd71783f1e6b71f8a622b993dc592897a97cd689c5090a07147a1b097b3',
    'license': 'CC BY 4.0',
    'citation': 'Brooks, Pope & Marcolini (1989). Airfoil Self-Noise. UCI. DOI:10.24432/C5VW2C',
}
FIXTURE = {'id': 'synthetic-airfoil-software-fixture'}
GROUP_RULE = {'columns': [1, 2, 3], 'split': 'airfoil-condition-v1',
              'boundaries': [.6, .8], 'minimum_groups': {'train': 20, 'validation': 10, 'holdout': 10}}


def fetch(output):
    folder = Path(output)
    if folder.exists() or folder.is_symlink(): raise ValueError('Destination exists; no overwrite')
    with urllib.request.urlopen(SOURCE['download'], timeout=45) as response:
        archive = response.read(1024*1024+1)
    if len(archive)>1024*1024 or hashlib.sha256(archive).hexdigest()!=SOURCE['archive_sha256']:
        raise ValueError('Pinned archive hash/size mismatch')
    with zipfile.ZipFile(io.BytesIO(archive)) as handle:
        if handle.namelist()!=['airfoil_self_noise.dat']: raise ValueError('Unexpected archive members')
        if handle.getinfo('airfoil_self_noise.dat').file_size>1024*1024: raise ValueError('Oversized member')
        raw = handle.read('airfoil_self_noise.dat')
    if hashlib.sha256(raw).hexdigest()!=SOURCE['raw_sha256']: raise ValueError('Pinned raw hash mismatch')
    folder.mkdir(parents=True, mode=0o700, exist_ok=False)
    (folder/'airfoil_self_noise.dat').write_bytes(raw)
    write_json(folder/'source.json', SOURCE)
    return {'status': 'DOWNLOADED_NOT_SCORED', 'data': str((folder/'airfoil_self_noise.dat').resolve()), 'source': SOURCE}


def parse(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>1024*1024:
        raise ValueError('Regular bounded Airfoil raw file required')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SOURCE['raw_sha256']: raise ValueError('Pinned Airfoil raw SHA-256 mismatch')
    rows = []
    for i, line in enumerate(raw.decode('ascii').splitlines(), 1):
        values = [float(x) for x in line.split()]
        if len(values)!=6: raise ValueError('Expected five inputs and one target')
        rows.append({'id': f'airfoil-{i:04}', 'features': values[:5], 'target': values[5]})
    if len(rows)!=1503: raise ValueError('Expected 1503 pinned Airfoil rows')
    return rows


def condition(features):
    return digest({'split': GROUP_RULE['split'], 'condition': [float(features[i]) for i in GROUP_RULE['columns']]})


def split_rows(rows):
    if not isinstance(rows, list) or not 1<=len(rows)<=10000: raise ValueError('Invalid Airfoil row count')
    parts = {k: [] for k in ('train', 'validation', 'holdout')}; seen = set()
    for row in rows:
        if (not isinstance(row, dict) or set(row)!={'id', 'features', 'target'}
                or not isinstance(row['id'], str) or not row['id'] or row['id'] in seen
                or not isinstance(row['features'], list) or len(row['features'])!=5):
            raise ValueError('Invalid/duplicate Airfoil row')
        seen.add(row['id'])
        for i, value in enumerate(row['features']):
            number(value, 'feature', 0)
            if i!=1 and value<=0: raise ValueError('Frequency/length/speed/thickness must be positive')
        number(row['target'], 'target')
        group = condition(row['features']); bucket = int(group[:8],16)/2**32
        key = 'train' if bucket<.6 else 'validation' if bucket<.8 else 'holdout'
        parts[key].append({**row, 'group': group})
    for key in parts:
        parts[key].sort(key=lambda row: row['id'])
        if len({r['group'] for r in parts[key]})<GROUP_RULE['minimum_groups'][key]:
            raise ValueError('Insufficient condition groups; stop without changing split salt')
    result = {'train.json': parts['train']}
    for key in ('validation', 'holdout'):
        result[key+'.json'] = [{k:r[k] for k in ('id','features','group')} for r in parts[key]]
        result[key+'-targets.json'] = [{k:r[k] for k in ('id','target','group')} for r in parts[key]]
    return result


def counts(parts):
    return {key: {'rows':len(parts[key+'.json']), 'groups':len({r['group'] for r in parts[key+'.json']})}
            for key in ('train','validation','holdout')}
