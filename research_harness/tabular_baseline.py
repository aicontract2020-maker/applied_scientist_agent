"""Reviewed, single-attempt baseline qualification; not autonomous research."""
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time

from .core import digest, number, Workspace
from .memory import read_json
from .portable import ROOT
from .state_lock import research_lock
from .tabular_data import FILES, SOURCE, parse_abalone, split_rows, write_json
from . import data_admission as admission

ADAPTER = 'abalone-baseline-v1'
FIXTURE = {'id': 'synthetic-software-fixture'}

PACKAGES = {'numpy': '1.26.4', 'scipy': '1.15.3', 'scikit-learn': '1.7.2',
            'joblib': '1.5.2', 'threadpoolctl': '3.6.0'}
RECIPE = {
    'kind': 'tabular-baseline-qualification', 'version': 1, 'seeds': [11, 22, 33],
    'hypothesis': 'At least one prespecified learned baseline improves validation MAE over train-median by >=0.05 rings for every fixed seed, with prediction range <=1e-8.',
    'decision_purpose': 'Qualify a reference from a frozen two-model set before proposing any scientific intervention; no global strongest-baseline claim.',
    'controls': ['Pinned raw data and feature-only hash split', 'Training labels only inside worker; validation labels only in controller',
                 'No final holdout exposure/scoring', 'Fixed model parameters and dependency versions',
                 'Single-thread CPU; all three seeds and all models reported; one attempt, no tuning'],
    'validity_checks': ['Bound code/data/environment', 'Disjoint feature groups and exact prediction identities',
                        'Finite outputs and all nine model/seed results', 'Actual OS isolation probe passes',
                        'Prediction repeatability within frozen tolerance'],
    'models': ['median', 'ridge', 'hgb'], 'metric': 'MAE in ring counts',
    'split': 'feature SHA256: [0,.6) train, [.6,.8) validation, [.8,1) final holdout',
    'minimum_validation_gain': .05, 'max_prediction_range': 1e-8,
    'selection': 'lowest mean validation MAE of ridge/hgb; ties choose ridge',
    'go': 'Only draft a separate candidate research protocol; no automatic holdout access or experiment',
    'stop': 'Close this baseline qualification; no hyperparameter tuning, replacement or retry',
    'invalid': 'Close the attempt and preserve failure; no scientific conclusion or automatic retry',
    'baseline_parameters': {'median': 'training median', 'ridge': 'StandardScaler then Ridge(alpha=1, solver=svd)',
        'hgb': 'absolute_error, learning_rate=.1, max_iter=100, max_leaf_nodes=31, min_samples_leaf=20, l2_regularization=0, max_bins=255, max_features=1.0, categorical_features=None, early_stopping=False'},
    'limits': {'worker_seconds': 240, 'output_bytes': 16777216, 'threads': 1, 'attempts': 1},
    'costs': {'external_model_calls': 0, 'paid_cloud_jobs': 0, 'actual_local_cost_usd': None,
              'unpriced': ['installation/downloads', 'electricity/depreciation', 'retention']},
    'uncertainty': 'Three fixed seeds test repeatability, not independent training evidence or generalization; no holdout scoring',
    'python': '3.12', 'packages': PACKAGES,
}


def source_hashes():
    files = [*sorted((ROOT/'research_harness').glob('*.py')), ROOT/'requirements-tabular.lock.txt',
             ROOT/'scripts/bootstrap-tabular.sh', ROOT/'scripts/check-tabular-isolation.py']
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def prepare(data, output, data_review=None, intended_use=None):
    snapshot = admission.accepted_snapshot(data_review, ADAPTER, SOURCE, intended_use)
    return prepare_rows(parse_abalone(data), output, SOURCE, qualification=snapshot, intended_use=intended_use)


def prepare_rows(rows, output, source, *, qualification=None, intended_use=None):
    """Internal fixture seam. Public CLI only accepts the pinned UCI raw file."""
    if source not in (SOURCE, FIXTURE): raise ValueError('Unsupported dataset provenance')
    if source == SOURCE and qualification is None: raise ValueError('Real data requires accepted data qualification')
    parts = split_rows(rows)
    content = {'recipe': RECIPE, 'source': source, 'files': {name: digest(parts[name]) for name in FILES},
               'counts': {key: len(parts[key+'.json']) for key in ('train', 'validation', 'holdout')},
               'sources': source_hashes(), 'status': 'AWAITING_REVIEW'}
    if qualification is not None:
        content['data_admission'] = admission.bind(qualification, ADAPTER, source, intended_use, content['files'], RECIPE)
    admission.check_packet_size(content)
    folder = Path(output).absolute()
    folder.mkdir(parents=True, mode=0o700, exist_ok=False)
    for name in FILES: write_json(folder/name, parts[name])
    packet = {'content': content, 'sha256': digest(content)}
    write_json(folder/'bundle.json', packet)
    (folder/'REVIEW.md').write_text(f'''# 第二任务基线资格审查

状态：AWAITING_REVIEW。未训练、未评分，没有批准记录。

审核摘要：`{packet['sha256']}`

任务：预测 UCI Abalone 的 Rings。来源及许可：{json.dumps(source, ensure_ascii=False)}。
这是一项工程迁移基准，不证明行业需求或商业价值；来源缺少站点/群组标识，无法认证观测独立性。最终留出集不参与本阶段。

固定划分：{json.dumps(content['counts'])}。使用特征哈希，未按目标或分数选择样本；相同特征不会跨集合。

比较训练中位数、固定标准化 Ridge 和固定 HGB，仅训练集参与拟合。验证标签仅在控制器。比较 11/22/33 三个 seed，检查重复性，不把相同预测当作独立科研证据。

在 ridge/hgb 中按验证平均 MAE 选较低者，同分选 ridge。选中模型每个 seed 比中位数至少低 0.05 ring，且每个模型跨 seed 预测范围 <=1e-8，才允许起草后续研究协议；否则 STOP。0.05 是待审核的工程门槛，没有已验证业务意义。不是复现某篇论文的已发表分数，也不声称所选模型是全局最强。

CPU 单线程、固定依赖、工作进程最多 240 秒、输出监测上限 16 MiB、一次尝试。候选不联网；本阶段没有 agent、模型额度或云任务。记录耗时、RSS 和保留字节，真实本地货币费用未知，不记为零；无硬内存/磁盘配额保证。失败不重试或调参。

协议、数据分区和源码摘要绑定在 bundle.json。普通 run 不参与；必须使用本任务隔离 runner。最终留出特征/标签不挂载给 worker。Linux 使用既有 Bubblewrap 机制；macOS 使用 Seatbelt。运行前必须通过真实隔离探针。

本次请审核：是否接受 Abalone 作为工程第二任务、这组固定基线与资格门槛，以及上述本地执行范围。批准只覆盖这次基线资格检查；不批准后续科研候选或最终留出评分。

待确认后才可执行（路径以本目录为准）：

```sh
python3 -m research_harness tabular approve --review PATH --sha256 {packet['sha256']} --reviewer YOUR_NAME
python3 -m research_harness tabular baseline --review PATH
```

同一目录只能批准/执行一次，内容变动使批准失效。批准是本地审查记录，不是身份认证。不同副本无全局锁；不得通过复制或删除记录重跑。若任务或门槛不合适，应在看见分数前修订方案并重新审查。
''')
    with (folder/'REVIEW.md').open('a') as handle: handle.write(admission.review_note(content))
    return {'status': 'AWAITING_REVIEW', 'review': str(folder/'REVIEW.md'), 'sha256': packet['sha256'], 'counts': content['counts']}


def load_review(folder, *, require_current_sources=True):
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir(): raise ValueError('Review must be a regular directory')
    packet = read_json(folder/'bundle.json')
    if not isinstance(packet, dict) or set(packet) != {'content', 'sha256'}: raise ValueError('Invalid review envelope')
    c = packet['content']
    fields = {'recipe', 'source', 'files', 'counts', 'sources', 'status'}
    if (not isinstance(c, dict) or set(c) not in (fields, fields | {'data_admission'})
            or packet['sha256'] != digest(c) or digest(c['recipe']) != digest(RECIPE) or c['status'] != 'AWAITING_REVIEW'
            or not isinstance(c['files'], dict) or set(c['files']) != set(FILES)):
        raise ValueError('Changed/unsupported baseline review')
    if c['source'] != SOURCE and c['source'] != {'id': 'synthetic-software-fixture'}:
        raise ValueError('Unsupported dataset provenance')
    admission.verify(c, ADAPTER, required=require_current_sources and c['source'] == SOURCE)
    if (not isinstance(c['sources'], dict) or not c['sources'] or
            any(not isinstance(k,str) or not isinstance(v,str) or not re.fullmatch('[0-9a-f]{64}',v) for k,v in c['sources'].items())):
        raise ValueError('Invalid frozen source hashes')
    if require_current_sources and c['sources'] != source_hashes(): raise ValueError('Reviewed source changed; rebuild and review before execution')
    parts = {name: read_json(folder/name) for name in FILES}
    if any(digest(parts[name]) != c['files'][name] for name in FILES): raise ValueError('Reviewed data changed')
    rows = list(parts['train.json'])
    for split in ('validation', 'holdout'):
        features, targets = parts[split+'.json'], parts[split+'-targets.json']
        if len(features) != len(targets): raise ValueError('Feature/target mismatch')
        for feature, target in zip(features, targets):
            if set(feature) != {'id', 'features'} or set(target) != {'id', 'target'} or feature['id'] != target['id']:
                raise ValueError('Invalid split schema/order')
            rows.append({**feature, 'target': target['target']})
    if split_rows(rows) != parts or c['counts'] != {k: len(parts[k+'.json']) for k in ('train', 'validation', 'holdout')}:
        raise ValueError('Frozen split rule/counts violated')
    return packet, parts


def approve(folder, expected_hash, reviewer):
    with research_lock(ROOT):
        packet, _ = load_review(folder)
        if packet['sha256'] != expected_hash or not isinstance(reviewer, str) or not reviewer.strip():
            raise ValueError('Approval requires exact content hash and reviewer name')
        if (Path(folder)/'run').exists(): raise ValueError('Attempt already exists; no new approval')
        write_json(Path(folder)/'approval.json', {'sha256': expected_hash, 'reviewer': reviewer.strip(),
                   'scope': 'One baseline qualification only; no candidate study or final holdout scoring'})
        return {'status': 'APPROVED_BASELINE_ONLY', 'sha256': expected_hash}


def environment(python):
    code = "import json,sys,importlib.metadata as m;print(json.dumps({'python':list(sys.version_info[:2]),'packages':{x:m.version(x) for x in " + repr(list(PACKAGES)) + "}}))"
    value = json.loads(subprocess.check_output([str(python), '-I', '-c', code], text=True, timeout=15))
    if value != {'python': [3, 12], 'packages': PACKAGES}: raise ValueError('Tabular environment differs from lock')
    return value


def qualify(output, targets):
    """Controller-only scoring; final holdout is not an argument."""
    if not isinstance(output, dict) or set(output) != {'results', 'peak_rss_native'}: raise ValueError('Invalid worker output')
    number(output['peak_rss_native'], 'peak RSS', 0)
    expected = {(model, seed) for model in RECIPE['models'] for seed in RECIPE['seeds']}
    truth = {r['id']: r['target'] for r in targets}
    entries, scores, predictions = set(), {}, {}
    for item in output['results']:
        if not isinstance(item, dict) or set(item) != {'model', 'seed', 'fit_seconds', 'predict_seconds', 'predictions'}:
            raise ValueError('Invalid worker result')
        key = item['model'], item['seed']
        if type(item['seed']) is not int or key not in expected or key in entries: raise ValueError('Missing/duplicate/unexpected model or seed')
        entries.add(key)
        for field in ('fit_seconds', 'predict_seconds'): number(item[field], field, 0)
        values = {}
        for row in item['predictions']:
            if not isinstance(row, dict) or set(row) != {'id', 'prediction'} or row['id'] not in truth or row['id'] in values:
                raise ValueError('Invalid prediction identities')
            values[row['id']] = number(row['prediction'], 'prediction')
        if set(values) != set(truth): raise ValueError('Missing validation predictions')
        scores[key] = number(statistics.mean(abs(values[i]-truth[i]) for i in truth), 'validation MAE', 0)
        predictions[key] = values
    if entries != expected: raise ValueError('Missing baseline/seed results')
    variability = {m: max(max(predictions[m,s][i] for s in RECIPE['seeds'])-min(predictions[m,s][i] for s in RECIPE['seeds']) for i in truth) for m in RECIPE['models']}
    if max(variability.values()) > RECIPE['max_prediction_range']: raise ValueError('Predeclared repeatability check failed')
    means = {m: statistics.mean(scores[m,s] for s in RECIPE['seeds']) for m in RECIPE['models']}
    selected = min(('ridge', 'hgb'), key=lambda m: means[m])
    gains = [scores['median',s]-scores[selected,s] for s in RECIPE['seeds']]
    passed = min(gains) >= RECIPE['minimum_validation_gain']
    return {'status': 'CONTINUE' if passed else 'STOP', 'measurement_valid': True,
            'selected_baseline': selected, 'mean_validation_mae': means,
            'per_seed_mae': {m: [scores[m,s] for s in RECIPE['seeds']] for m in RECIPE['models']},
            'gains_vs_median': gains, 'prediction_range': variability,
            'conclusion': RECIPE['go'] if passed else RECIPE['stop'], 'final_holdout_scored': False}


def _approved_review(folder):
    packet, parts = load_review(folder)
    approval = read_json(Path(folder)/'approval.json')
    if (not isinstance(approval, dict) or set(approval) != {'sha256', 'reviewer', 'scope'}
            or approval['sha256'] != packet['sha256'] or not isinstance(approval['reviewer'], str) or not approval['reviewer'].strip()
            or approval['scope'] != 'One baseline qualification only; no candidate study or final holdout scoring'):
        raise ValueError('Missing/stale baseline-only approval')
    run = Path(folder)/'run'
    if run.exists() or run.is_symlink(): raise ValueError('Baseline attempt already consumed; inspect evidence, no retry')
    return packet, parts, approval


def preflight(folder):
    packet, _, _ = _approved_review(folder)
    return {'status': 'PRECHECK_PASSED', 'read_only': True, 'sha256': packet['sha256'],
            'data_admission': admission.verify(packet['content'], ADAPTER, required=packet['content']['source'] == SOURCE),
            'execution_authorized': False, 'isolation_checked': False,
            'note': 'Execution still rechecks exact approval, data and environment, then probes isolation.'}


def execute(folder):
    from .tabular_sandbox import isolation_probe, isolated_worker
    with research_lock(ROOT):
        folder = Path(folder).absolute()
        packet, parts, approval = _approved_review(folder)
        run = folder/'run'
        python = ROOT/'.venv-tabular/bin/python'
        env = environment(python)
        probe = isolation_probe(ROOT, python)
        if _approved_review(folder) != (packet, parts, approval):
            raise ValueError('Review or approval changed during preflight; no execution')
        run.mkdir(mode=0o700, exist_ok=False)
        Workspace.append(run, {'event': 'REGISTER', 'review_sha256': packet['sha256']})
        begin = time.monotonic()
        write_json(run/'preflight.json', {'environment': env, 'platform': platform.platform(), 'isolation': probe})
        try:
            trusted, inputs, output = (run/x for x in ('trusted', 'inputs', 'output'))
            trusted.mkdir(); inputs.mkdir()
            shutil.copyfile(ROOT/'research_harness/tabular_worker.py', trusted/'worker.py')
            write_json(inputs/'request.json', {'recipe': RECIPE, 'train': parts['train.json'], 'validation': parts['validation.json']})
            # Freeze source again after staging; no mutable review paths enter the worker.
            if packet['content']['sources'] != source_hashes(): raise ValueError('Source changed before worker start')
            Workspace.append(run, {'event': 'BASELINE_STARTED', 'review_sha256': packet['sha256']})
            process = isolated_worker(ROOT, python, folder, trusted, inputs, output, 'worker.py',
                                      ['--input', inputs/'request.json', '--output', output/'predictions.json'])
            write_json(run/'process.json', process)
            if process['error']: raise ValueError('Worker failed: '+process['error'])
            raw = read_json(output/'predictions.json')
            result = qualify(raw, parts['validation-targets.json'])
            result['peak_rss_bytes'] = raw['peak_rss_native'] * (1024 if sys.platform == 'linux' else 1)
        except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            result = {'status': 'STOP', 'measurement_valid': False, 'reason': str(exc), 'conclusion': RECIPE['invalid'], 'final_holdout_scored': False}
        result.update(wall_seconds=time.monotonic()-begin, actual_local_cost_usd=None, model_calls=0,
                      retained_bytes_before_report=sum(p.stat().st_size for p in run.rglob('*') if p.is_file() and not p.is_symlink()),
                      scope='Baseline qualification only; no scientific candidate or global-SOTA claim')
        write_json(run/'result.json', result)
        Workspace.append(run, {'event': 'DECISION', 'result': result})
        (run/'REPORT.md').write_text('# Baseline qualification\n\n```json\n'+json.dumps(result, indent=2)+'\n```\n\nNo final holdout scoring. Inspect approval, frozen recipe, inputs, predictions and ledger. Costs are incomplete, not zero.\n')
        return result
