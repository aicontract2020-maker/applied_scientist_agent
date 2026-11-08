#!/usr/bin/env python3
"""Read only pinned Delft case metadata. Never open acoustic targets or fit models.

This is an inventory check, not an experiment-approval command. It deliberately
cannot declare the external replication executable from field presence alone.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

PINNED = {
    'LRM': 'd22fd8ce53d34735bfd94c0608684fa4d2b73994b2793fad428c6ed40a6a0e5c',
    'HRM': '946c511c89d830e0b708ce1640593344d2dee46b265c73ad141829cb6678259b',
}


def inventory(directory):
    summary = {}
    for model, expected in PINNED.items():
        path = Path(directory) / ('delft-' + model + '_Master.txt')
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 100000:
            raise ValueError('Regular small metadata file required: ' + path.name)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Pinned metadata checksum differs: ' + path.name)
        rows = list(csv.DictReader(io.StringIO(data.decode('utf-8')), delimiter='\t'))
        baseline = [r for r in rows if r['TE configuration'] == 'BASELINE']
        complete = [r for r in baseline if r['delta* (mm)'] != 'N/A']
        # A metadata upper bound only: do not count clean/forced, nozzle repeats,
        # or spectral bins as independent operating conditions.
        proxies = {(r['Re_c (x10^6)'], r['alpha geom (deg)']) for r in complete}
        summary[model] = {
            'sha256': expected, 'bytes': len(data), 'all_case_count': len(rows),
            'straight_edge_case_count': len(baseline),
            'straight_edge_cases_with_reported_delta_star': len(complete),
            'case_ids_with_reported_delta_star': [r['Code'] for r in complete],
            'nominal_re_angle_proxy_count': len(proxies),
        }
    return {
        'dataset_doi': '10.4121/20940646.v1',
        'status': 'BLOCKED_DATA_QUALIFICATION', 'execution_ready': False,
        'metadata_only': True, 'models_fitted': 0, 'acoustic_targets_read': False,
        'files': summary,
        'combined_model_re_angle_proxy_count': sum(
            s['nominal_re_angle_proxy_count'] for s in summary.values()),
        'count_caveat': 'Field presence is not confirmed suction-side semantics, '
                        'valid acoustic coverage, independence or an eligible holdout count.',
        'unresolved': ['target_scale_mapping', 'suction_side_and_flow_semantics',
                       'predeclared_acoustic_validity_mask', 'eligible_group_count',
                       'intended_use_permission', 'frozen_external_adapter_and_manifest'],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata-dir', required=True)
    args = parser.parse_args()
    print(json.dumps(inventory(args.metadata_dir), indent=2))
