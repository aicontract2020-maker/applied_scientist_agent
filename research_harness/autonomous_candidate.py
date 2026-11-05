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
    parser.add_argument('--intervention-probe', action='store_true')
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    np.random.seed(0)
    spec = importlib.util.spec_from_file_location('agent_candidate', args.candidate)
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    if args.intervention_probe:
        # Fixed software challenges, never benchmark pixels, labels or metrics.
        y, x = np.indices((24, 32), dtype=np.float32)
        ramp = np.stack((x/31, y/23, (x+y)/54), axis=-1)
        rng = np.random.default_rng(20261104)
        cases = [np.zeros_like(ramp), np.full_like(ramp, .4), ramp,
                 np.where(ramp < .5, .1, .9).astype(np.float32),
                 rng.uniform(0, 1, ramp.shape).astype(np.float32),
                 (ramp*1.4-.2).astype(np.float32),
                 ((np.floor(ramp*255)+.5)/255).astype(np.float32)]
        def quantize(value):
            return (np.clip(value[:, :, ::-1], 0, 1)*255.).round().astype(np.uint8)
        changes = []
        for index, sr in enumerate(cases):
            lr = (sr[::2, ::2]*.97+.01).astype(np.float32)
            a = candidate.enhance(lr.copy(), sr.copy())
            b = candidate.enhance(lr.copy(), sr.copy())
            for value in (a, b):
                if not isinstance(value, np.ndarray) or value.shape != sr.shape or value.dtype.kind != 'f' or not np.isfinite(value).all():
                    raise ValueError('Invalid synthetic intervention output')
            if not np.array_equal(a, b):
                raise ValueError('Candidate is not deterministic on repeated synthetic input')
            # Match evaluator's float32 adapter before mandatory conversion.
            changes.append(int(np.count_nonzero(quantize(a.astype(np.float32)) != quantize(sr))))
        (args.output/'probe.json').write_text(json.dumps({'changed_channels': changes,
            'observable_change': any(changes), 'deterministic': True,
            'scope': 'Seven fixed synthetic cases only; not a proof of semantic inequivalence or SR quality'}))
        return
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
    (args.output / 'resources.json').write_text(json.dumps({'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1024 if sys.platform == 'linux' else 1),
                                                          'platform': sys.platform, 'smoke': args.smoke}))


if __name__ == '__main__':
    main()
