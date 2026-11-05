"""Pinned public data preparation only. No fitting, model call or outcome selection."""
import csv
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

from .core import digest, number

ABALONE_SHA = 'de37cdcdcaaa50c309d514f248f7c2302a5f1f88c168905eba23fe2fbc78449f'
SOURCE = {'id': 'uci-abalone-v1', 'url': 'https://archive.ics.uci.edu/dataset/1/abalone',
          'download': 'https://archive.ics.uci.edu/static/public/1/abalone.zip',
          'raw_sha256': ABALONE_SHA, 'license': 'CC BY 4.0',
          'citation': 'Nash, Sellers, Talbot, Cawthorn & Ford (1994). Abalone. UCI. DOI:10.24432/C55C7W'}
FILES = ('train.json', 'validation.json', 'validation-targets.json', 'holdout.json', 'holdout-targets.json')


def fetch_abalone(output):
    """Bounded download; read fixed ZIP members without extracting archive paths."""
    folder = Path(output)
    if folder.exists() or folder.is_symlink(): raise ValueError('Download destination already exists; no overwrite')
    with urllib.request.urlopen(SOURCE['download'], timeout=45) as response:
        archive = response.read(1024*1024+1)
    if len(archive) > 1024*1024 or hashlib.sha256(archive).hexdigest() != '755a6a67c5b266961a3f149ea13be2cfb6e6c727e48cee3c83bc0b4526210ee4':
        raise ValueError('UCI archive SHA-256/size mismatch')
    with zipfile.ZipFile(io.BytesIO(archive)) as handle:
        data = handle.read('abalone.data')
        names = handle.read('abalone.names')
    if (hashlib.sha256(data).hexdigest() != ABALONE_SHA or
            hashlib.sha256(names).hexdigest() != '542eee5a2a0ee72db563de010dc3b5055b03c5dc624049ae1f2208fc66a14aac'):
        raise ValueError('Pinned UCI member hashes differ')
    folder.mkdir(parents=True, exist_ok=False)
    for name, content in (('abalone.data', data), ('abalone.names', names)):
        with (folder/name).open('xb') as target: target.write(content)
    write_json(folder/'source.json', SOURCE)
    return {'status': 'DOWNLOADED_NOT_SCORED', 'data': str((folder/'abalone.data').resolve()), 'source': SOURCE}


def parse_abalone(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024*1024:
        raise ValueError('Expected a regular Abalone data file <=1 MiB')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ABALONE_SHA:
        raise ValueError('Abalone raw SHA-256 mismatch; no alternate data accepted')
    rows = []
    for i, row in enumerate(csv.reader(io.StringIO(raw.decode('ascii'))), 1):
        if len(row) != 9 or row[0] not in ('M', 'F', 'I'):
            raise ValueError('Invalid Abalone schema')
        features = [float(row[0] == sex) for sex in ('M', 'F', 'I')] + [float(x) for x in row[1:8]]
        target = int(row[8])
        for value in features: number(value, 'feature', 0)
        if not 1 <= target <= 29: raise ValueError('Invalid ring count')
        rows.append({'id': f'abalone-{i:04}', 'features': features, 'target': target})
    if len(rows) != 4177: raise ValueError('Expected 4177 pinned records')
    return rows


def split_rows(rows):
    """Feature-only hash groups: identical feature vectors never cross partitions."""
    parts = {'train': [], 'validation': [], 'holdout': []}
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'id', 'features', 'target'}
                or not isinstance(row['id'], str) or not row['id'] or row['id'] in seen
                or not isinstance(row['features'], list) or len(row['features']) != 10):
            raise ValueError('Invalid/duplicate tabular row')
        seen.add(row['id'])
        for value in row['features']: number(value, 'feature')
        number(row['target'], 'target')
        key = digest({'split': 'abalone-feature-v1', 'features': row['features']})
        bucket = int(key[:8], 16) / 2**32
        parts['train' if bucket < .6 else 'validation' if bucket < .8 else 'holdout'].append(row)
    if any(len(part) < 10 for part in parts.values()):
        raise ValueError('Each partition needs at least ten rows')
    data = {'train.json': parts['train']}
    for key in ('validation', 'holdout'):
        data[key+'.json'] = [{'id': r['id'], 'features': r['features']} for r in parts[key]]
        data[key+'-targets.json'] = [{'id': r['id'], 'target': r['target']} for r in parts[key]]
    return data


def write_json(path, value):
    with Path(path).open('x') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write('\n')
