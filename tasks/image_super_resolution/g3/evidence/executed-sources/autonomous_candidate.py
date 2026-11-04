"""Trusted boundary adapter for an agent-authored, deterministic NumPy function.
Executed under the OS candidate profile, never in the controller process.
"""
import argparse
import importlib.util
import json
import os
import resource
import sys
import time
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    np.random.seed(0)
    spec = importlib.util.spec_from_file_location('agent_candidate', args.candidate)
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    records = []
    paths = [] if args.smoke else sorted(args.inputs.glob('*.npz'))
    if args.smoke:
        samples = [('synthetic-zero', np.zeros((12, 16, 3), dtype=np.float32), np.zeros((24, 32, 3), dtype=np.float32)),
                   ('synthetic-constant', np.full((12, 16, 3), .4, dtype=np.float32), np.full((24, 32, 3), .4, dtype=np.float32))]
    else:
        samples = []
        for path in paths:
            with np.load(path, allow_pickle=False) as values:
                samples.append((path.stem, values['lr'], values['sr']))
    for name, lr, sr in samples:
        begin = time.monotonic()
        result = candidate.enhance(lr.copy(), sr.copy())
        seconds = time.monotonic() - begin
        if not isinstance(result, np.ndarray) or result.shape != sr.shape or result.dtype.kind != 'f' or not np.isfinite(result).all():
            raise ValueError(f'Invalid finite float RGB output shape for {name}')
        # The adapter, not the agent function, owns output names and file format.
        np.save(args.output / f'{name}.npy', result.astype(np.float32), allow_pickle=False)
        records.append({'id': name, 'postprocess_seconds': seconds})
    (args.output / 'timings.json').write_text(json.dumps(records, indent=2))
    (args.output / 'resources.json').write_text(json.dumps({'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                                                          'platform': sys.platform, 'smoke': args.smoke}))


if __name__ == '__main__':
    main()
