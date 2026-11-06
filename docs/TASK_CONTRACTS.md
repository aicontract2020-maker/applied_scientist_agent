# 任务接口与能力范围

0.15.0 将任务身份、领域评价和共用判定分开；0.19.0 在不修改历史 v1 评价绑定的前提下增加独立的工作流能力查询。当前仅有两个内置任务，任务文档不能指定 Python 模块、shell 命令或放宽隔离权限。

| 任务 ID | 评价 | 执行能力 |
| --- | --- | --- |
| `swinir-s-x2` | 原有 PSNR-Y、uint8 转换和裁边、固定双次参考 | 现有 macOS/Linux 自主研究流程 |
| `tabular-regression` | 固定预测的逐行绝对误差，聚合 MAE，越低越好 | v1 绑定仅数值评价；另有明确 propose/execute 阶段及人工审批的 Abalone 特征试验流程 |

```sh
python3 -m research_harness task list
python3 -m research_harness task show swinir-s-x2
python3 -m research_harness task show tabular-regression
python3 -m research_harness task capabilities tabular-regression
```

目录列出数据、基线、允许干预、不确定性、预算解释、评价器及能力边界。`task` 绑定含 `id/version/sha256`，哈希对应内置契约的规范化 JSON。新 SR policy 自动保存该绑定；执行和审计检查它。未知版本、错误哈希或把回归任务交给 SR runner 都会拒绝。历史没有绑定的 SR 记录保留原行为，不重写历史文件。

## 已分离的边界

- `task_contracts.py`：可信任务目录、内容绑定和能力检查。
- `sr_evaluation.py`：从既有控制器提取的图像评价。仍由控制器持有 HR，候选在原隔离环境运行；公式、字段、参考和冻结阈值保持一致。
- `regression_evaluation.py`：输入固定数值记录，输出共用的逐观测指标；不导入或执行候选源码。
- `observations.py`：配对 bootstrap、延迟比和共用三个门槛。高低方向按协议处理；CONTINUE 必须同时满足最小效果、区间下界大于零、延迟比不超限。
- `Workspace`：继续负责冻结协议、结果有效性和声明成本检查、一次终局决定、账本与停止规则。

SR 的文件代理、参考进程、干预审查、数据预留和研究记忆仍是 SR 专用；没有为了抽象而扩大权限。普通 `run` 仍不提供隔离，不能拿它代替第二任务的自主 runner。

## 回归数值接口

`evaluate_predictions(protocol, targets, baseline, candidate)` 是可信调用方的纯数值函数，不自行注册实验。调用方必须先注册并加载冻结协议，再评价并记录结果；合成演示展示此顺序。独立调用此函数不构成一轮已注册研究。

协议使用原有 `paired_observations` 字段，另需：

- `task`：`binding('tabular-regression')`。
- `dataset`：`id`、目标记录的 `sha256`、`observation_unit: independent_row`。
- `intervention`：`kind: fixed_predictions`，以及 `baseline_sha256/candidate_sha256`。
- `primary_metric`：`name: MAE`、`direction: lower`、目标值单位。

目标表的每项只含 `{id, target}`；两张预测表的每项只含 `{id, prediction, latency_ms}`。哈希均为 `core.digest(完整记录列表)`，列表顺序也被绑定。每张表必须覆盖所有冻结 ID 且无重复，值必须有限，时延必须为正。评分结果使用冻结 ID 的顺序；输入改动、缺失、多余字段或非有限值均拒绝。每次 bootstrap 最多一百万次观测抽样，避免无界软件计算。

候选效果为 `baseline_MAE - candidate_MAE`。仅允许一次确定性比较，`replicates=1/seeds=[0]`，不是训练重复。独立行假设需在真实协议中论证；不得把时间序列、同一实体的重复记录或相关分组直接当作独立行。

记录仍由可信调用方提供。哈希不证明没有标签泄漏、基线最强、训练过程真实或时延诚实；手工 `record` 没有独立评分来源保证。`budget_usd` 与完整成本字段沿用既有声明核算，不是外部账单硬限额。任务绑定不替代人工研究审查。

## 合成验收

```sh
python3 -m examples.tabular_demo.workflow --out runs/tabular-software-demo
```

输出包括输入、冻结协议、REGISTER → RESULT → DECISION 账本及报告。固定候选比基线差，预期 STOP；不能覆盖同名目录。测试另用相互独立的合成场景验证正结果、效果不足、不确定性过高和延迟超限，没有在科研负结果后调参。

这个合成演示的数值、时延和费用全部是 fixture，既不是一个真实回归实验，也不是第二领域自主能力的证明。演示不选择真实数据集、训练算法或研究假设，不调用模型。

`research --id example --task tabular-regression` 未提供阶段时仍会在锁、环境检查、数据预留和模型调用前拒绝。0.19.0 必须显式指定 `--stage propose` 或 `--stage execute`，分别进入文献/提案/冻结审查和获批后一次隔离执行；参见 [特征试验](TABULAR_FEATURE_TRIAL.md) 与 [记忆和证据交接](TABULAR_HANDOFF.md)。回归使用独立的 `tabular memory/evidence` 命令，不冒充 SR 的 `memory`、`study audit/export` 接口。当前 Abalone 留出已经全部消耗；跨任务完整自主能力仍未宣称完成，见 [路线图](ROADMAP.md)。

## 本轮验证记录

2026-11-05，macOS 项目环境全套 120 个软件测试通过；基础 Python 运行 120 个，其中 6 个因缺少研究数值依赖跳过，其余通过。新增测试验证任务能力拒绝、冻结输入、独立行指标、三项采用门槛、停止后不可追加结果、真实 CLI 和合成图像转换。SR 合成测试使用桩指标，不代表真实图像科研性能。

另用新实现只读审计历史 G7 完整本地镜像，除目录路径外，整个审计输出与已经公开的 `docs/inspection-evidence/g7-read-only-audit.json` 完全一致，仍为有效 STOP；没有重新评分图像或修改旧记录。Linux CI 增加了基础 Python 的任务目录与回归合成演示步骤，并保留原有隔离和干预拒绝探针。
