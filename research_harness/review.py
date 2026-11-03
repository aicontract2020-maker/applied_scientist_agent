"""Content-bound, local human review records (not identity authentication)."""
import json
from pathlib import Path

from .core import Workspace, digest, validate_protocol
from .planning import validate_plan


def read_envelope(path):
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict) or set(value) != {'content', 'sha256'} or digest(value['content']) != value['sha256']:
        raise ValueError('Review/proposal content hash mismatch')
    return value


def write_envelope(path, content):
    value = {'content': content, 'sha256': digest(content)}
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
    return value


def build_review(proposal_path, execution_path, output_dir):
    proposal = read_envelope(proposal_path)
    content = proposal['content']
    plan = content['plan']
    validate_plan(plan)
    if plan['status'] != 'ready_for_review':
        raise ValueError('Missing context: resolve questions before creating an execution review')
    execution = json.loads(Path(execution_path).read_text())
    protocol = {**plan['protocol'], 'execution': execution}
    validate_protocol(protocol)
    folder = Path(output_dir).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    bundle = write_envelope(folder / 'bundle.json', {'proposal': content, 'protocol': protocol})
    p = protocol
    c = execution
    reserve = sum(c['fixed_costs'].values()) + c['timeout_seconds'] / 3600 * c['compute_usd_per_hour']
    lines = [f'# 研究计划审查：{p["id"]}', '',
             '**状态：等待人工审查。未注册、未启动实验。**', '',
             f'内容摘要：`{bundle["sha256"]}`', '',
             '## 研究问题', '', plan['summary'], '', plan['rationale'], '',
             '## 冻结协议', '', f'- 假设：{p["hypothesis"]}', f'- 基线：{p["baseline"]}',
             f'- 指标：{p["primary_metric"]["name"]}；{p["primary_metric"]["direction"]}；单位 {p["primary_metric"]["unit"]}',
             f'- 最小有意义效果：{p["minimum_effect"]}（绝对单位）',
             f'- 配对重复：{p["replicates"]}；seeds={p["seeds"]}',
             '- CONTINUE：平均效应达到阈值，且每个 seed 都改善。其他有效测量结果 STOP。',
             f'- 成功后的决策：{p["outcomes"]["go"]}',
             f'- 未达标后的决策：{p["outcomes"]["stop"]}',
             f'- 测量失效后的决策：{p["outcomes"]["invalid"]}', '',
             '## 控制变量与有效性检查', '']
    lines += [f'- {x}' for x in p['controlled_variables'] + p['validity_checks']]
    lines += ['', '## 执行范围和成本', '',
              f'- 工作目录：`{c["cwd"]}`',
              '- 命令参数：`' + json.dumps(c['command'], ensure_ascii=False) + '`',
              f'- 单次超时：{c["timeout_seconds"]} 秒；预算：${p["budget_usd"]}',
              f'- 每小时合计费率：${c["compute_usd_per_hour"]}；每次固定费用：{c["fixed_costs"]}',
              f'- 全部预定重复的最大声明费用（不含进程开销）：${reserve * p["replicates"]:.6f}',
              '- 规划模型费用单独保存在 provider.json，可能未知，未计入实验预算。',
              '- 本地执行具有当前用户的文件/网络权限；工作目录不是访问边界。',
              '- 目前仅用于人工检查过的可信代码；隐藏测试集未进行独立权限隔离。', '',
              '### 待核对的输入文件', '']
    lines += [f'- `{name}`：`{sha}`' for name, sha in c['inputs'].items()]
    lines += ['', '## 模型提出的证据（未经系统核验）', '']
    lines += [f'- {e["claim"]} — {e["source"]}' for e in plan['evidence']] or ['- 无']
    lines += ['', '## 假设与风险', '']
    lines += [f'- {x}' for x in plan['assumptions'] + plan['risks']] or ['- 无']
    lines += ['', '## 审查重点', '',
              '- 核实基线是否最强相关基线，数据划分和原始数据是否适用。',
              '- 核实效果阈值有业务意义、失败会淘汰哪条路线。',
              '- 阅读命令涉及的全部代码，确认权限和成本可接受。',
              '- 同意后，用 approve 命令提交上面的完整摘要和真实审查者名称。',
              '- approve 仅保存审查记录；register-review 才注册，run 才执行。',
              '- 任意协议、命令或输入内容变化都需要重建审查材料。', '']
    (folder / 'REVIEW.md').write_text('\n'.join(lines))
    return {'review': str(folder / 'REVIEW.md'), 'bundle': str(folder / 'bundle.json'), 'sha256': bundle['sha256'], 'status': 'AWAITING_REVIEW'}


def approve(bundle_path, expected_hash, reviewer):
    bundle = read_envelope(bundle_path)
    if bundle['sha256'] != expected_hash:
        raise ValueError('Approval must name the exact reviewed content hash')
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError('A human reviewer name is required')
    validate_protocol(bundle['content']['protocol'])
    path = Path(bundle_path).parent / 'approval.json'
    write_envelope(path, {'bundle_sha256': expected_hash, 'reviewer': reviewer.strip(),
                          'scope': 'Register the exact protocol; execute only reviewed trusted code'})
    return {'approval': str(path), 'status': 'APPROVED_FOR_REGISTRATION'}


def register_review(workspace, bundle_path):
    bundle = read_envelope(bundle_path)
    approval = read_envelope(Path(bundle_path).parent / 'approval.json')['content']
    if approval['bundle_sha256'] != bundle['sha256']:
        raise ValueError('Approval is stale: review content changed')
    protocol = bundle['content']['protocol']
    validate_protocol(protocol)
    folder = workspace.register(protocol)
    workspace.append(folder, {'event': 'REVIEW_APPROVED', 'bundle_sha256': bundle['sha256'], 'reviewer': approval['reviewer']})
    return {'registered': str(folder), 'status': 'REGISTERED'}


def report(workspace, experiment_id, output):
    _, p, events = workspace.load(experiment_id)
    decision = workspace.evaluate(experiment_id)
    lines = [f'# 研究决策报告：{experiment_id}', '',
             f'状态：**{decision["status"]}**', '',
             f'假设：{p["hypothesis"]}', '', f'基线：{p["baseline"]}', '',
             f'原因：{decision["reason"]}', '',
             f'结论：{decision.get("conclusion", "等待预注册的重复实验完成。")}', '',
             f'完成重复：{decision["n"]}/{decision["planned_n"]}',
             f'平均效应：{decision["mean_effect"]}；样本标准差：{decision["effect_std"]}',
             f'总声明费用：${decision["total_usd"]}；预算：${p["budget_usd"]}', '',
             '## 每次测量（不只展示最佳 seed）', '',
             '| Seed | 基线 | 候选 | 效应 | 原始产物 |',
             '|---|---:|---:|---:|---|']
    sign = 1 if p['primary_metric']['direction'] == 'higher' else -1
    for e in events:
        if e['event'] == 'RESULT':
            r = e['result']
            lines.append(f'| {r["seed"]} | {r["baseline_score"]} | {r["candidate_score"]} | {sign * (r["candidate_score"] - r["baseline_score"]):.6g} | {r["artifact"]} |')
    lines += ['', '## 完整成本与延迟', '', '```json', json.dumps({k: decision[k] for k in ('cost_totals', 'mean_latency_ms', 'max_latency_ms')}, indent=2), '```', '',
              '执行失效和预算停止不等于科学假设被否定；请核对原因和账本。',
              '有效性检查仍由执行代码声明；费用依赖配置，未核验云账单。',
              'CONTINUE 不授权追加调参、部署或改变原阈值。', '']
    with Path(output).open('x') as f:
        f.write('\n'.join(lines))
    return {'report': str(Path(output).resolve()), 'status': decision['status']}
