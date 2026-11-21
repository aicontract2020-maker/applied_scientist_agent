# 工作流目录与统一只读检查

0.33.0 提供五个固定工作流的能力目录，方便新同事找到对应入口：

```sh
python3 -m research_harness task workflows
```

| workflow ID | 实际能力 | 审查边界 |
|---|---|---|
| `swinir-s-x2` | 固定 SwinIR-S / Urban100 的自主检索、提案、编码与单次实验 | 已授权研究范围、冻结本机准备、未使用图像、注册前干预审查 |
| `abalone-baseline-v1` | 固定 UCI Abalone 基线资格检查 | 数据资格、单独的精确摘要批准 |
| `abalone-candidate-v1` | agent 提案，人工审查后执行单一冻结候选 | 候选用途数据资格、合格 HGB 基线、单独执行批准 |
| `airfoil-baseline-v1` | 固定 UCI Airfoil 条件分组基线资格检查 | 数据资格、单独的精确摘要批准 |
| `airfoil-candidate-v1` | 固定 Strouhal 特征与合格 Extra Trees 基线 | 候选用途数据资格、单独执行批准；没有自主提案 actor |

目录是描述性能力信息，不检查安装、材料或批准。其 preparation/execution
字段是入口提示，完整参数请查看对应子命令的 `--help`。`task list/show` 仍展示旧的
数值评价契约；本轮不添加 Airfoil 到那个冻结目录，不改变任何契约摘要。
通用 `tabular-regression` evaluator 不代表可以接入任意数据。Delft 外部复现
资格仍未完成；历史 A2 的 CONTINUE 不授予新实验权，已用留出仍不可重跑。

## 检查一份已有准备材料

```sh
# 在仓库根目录，用对应 review/study 的实际路径替换占位符。
python3 -m research_harness task check \
  --workflow swinir-s-x2 --review /checkout/local_studies/ID

.venv-tabular/bin/python -m research_harness task check \
  --workflow airfoil-candidate-v1 --review /checkout/local_reviews/ID
```

此命令只读，既不准备新研究，也不执行研究。五个 ID 分别委托已有的
`sr-preflight`、`tabular preflight`、`tabular preflight-trial`、
`airfoil preflight`、`airfoil preflight-trial` 检查。不会从材料猜测流程，
不会加载外部插件；未知 ID 在读取路径前拒绝。错误写入 stderr，并以非零
退出，不产生“通过”结果。缺批准、过期冻结、已占用/消费及导入证据限制保持。

成功返回 `PRECHECK_PASSED`，原生完整结果保留在 `checks`（SR 原状态是
`READY_FOR_LAUNCH_CHECKS`）。`workflow` 保留静态目录元数据，其
`readiness: NOT_CHECKED` 指目录本身不评估运行环境；实际材料结果看 `checks`。
`execution_authorized` 与 `isolation_checked` 始终是 false。

不创建运行目录、锁、批准、预留或可转交的执行凭证，不检查登录/安装，不调用
模型，不探测隔离、不训练模型或生成新预测。SR 读取冻结文件字节计算摘要；
候选检查会复算已有基线预测的审计统计，仍不是新的研究实验。Airfoil 候选
的精确历史审计要求 Python 3.12，其余只读检查支持 Python >=3.10；实际
执行仍要求原来的 Python 3.12 环境和 macOS/Linux 隔离。

`--root /checkout` 可显式选择**已有**本地状态目录；默认是当前安装对应的
仓库根目录，结果会显示选定路径。只读检查允许查看其他目录，不证明该目录
具有完整或可信历史，也不授予在那里执行的权利。SR 仍要求原始本机 checkout。
不要用空目录绕开原检查：执行入口独立读取自己的状态、批准并实际探测隔离。

检查不持锁，结果仅是当前快照；执行前仍须由原生执行入口在原锁与原隔离下
重新检查。状态变化会使先前通过结果失效，不自动刷新方案或释放任何预留。

## 验证边界

软件测试使用合成材料；实际隔离脚本在生成合成基线与候选后调用该统一入口，
再运行原有软件验证。它们不评估真实科学效果，不调用研究模型。验收记录见
[C15 工程验收](WORKFLOWS_REVIEW.md)。

## 按流程检查安装

0.34 的目录增加 `environment_check` 提示。SR 继续使用原 `doctor`；
Abalone / Airfoil 使用 `tabular doctor` / `airfoil doctor`，检查共享的
固定 worker 环境，无需 SR 资源或 Codex 登录。默认不测试内核隔离，显式
`--probe-isolation` 才运行合成探针；不覆盖自主提案 actor。完整说明见
[表格安装诊断](TABULAR_DOCTOR.md)。安装诊断与材料只读检查均不授权实验。

## 批准前查看冻结材料

0.35 的四类 Abalone / Airfoil 工作流增加 `frozen_review_summary` 入口
提示。`task review --workflow ID --review PATH` 无需已有执行批准，从原生
校验后的冻结内容生成协议、候选与资格摘要；不检查当前执行资格。SR 不套用
该格式。完整边界见[批准前审阅](REVIEW_SUMMARY.md)。准备材料、审阅、记录
批准、只读执行前检查与实际隔离执行仍是独立步骤。
