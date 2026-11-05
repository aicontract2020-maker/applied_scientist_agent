# 历史基线审计与注册前提案筛查

0.17.0 将“已有基线是否可信地通过”和“新提案是否值得进入留出评估”分开处理。本轮新增只读审计和一种固定机制的筛查，不开放任意候选执行，也没有完成第二任务的自主研究适配。

## 历史审计不等于重新批准执行

```sh
python3 -m research_harness tabular audit-baseline --review reviews/abalone-baseline-016
```

检查批准摘要、三事件单次账本、冻结 worker 源码摘要、精确训练/验证输入、环境与隔离记录、全部模型/seed 的预测和决定。它从已保存验证预测重算资格结果，不训练、推理或评分最终留出集。

升级仓库后，`current_sources_match=false` 是允许的：审计比较历史源码作为文本，不导入或执行它。普通 `tabular verify/approve/baseline` 仍默认要求当前源码匹配冻结摘要，不能用历史审计通过来重新执行旧批准。不能修改旧 bundle/hash 去迎合新代码。

审计证明记录内部一致，不能认证执行者、确认进程确实运行或证明基线全局最强；一套自洽的伪造记录仍可能通过。无效/不完整的基线不能用于这项提案筛查。

## 固定机制与筛查规则

仅支持 `additive_validation_median_residual_v1`：使用已通过的 HGB seed-11 验证预测，拟合 `delta = median(y - prediction)`，对未来预测统一加 delta。拟合算法、0.05 ring 最小效果、候选公式及停止含义先记录，再计算这个统计量。

对任意真实值 y、原预测 p 和偏移 delta，由三角不等式：

```text
|y - p| - |y - (p + delta)| <= |delta|
```

因此最终测试集的平均 MAE 改善也不可能超过 `abs(delta)`。筛查不需要使用任何最终标签：

- delta 为零：REJECTED / NOT_RUN，属于空操作。
- `abs(delta) < 0.05`：REJECTED / NOT_RUN，无法达到冻结效果门槛；不调大偏移、不降低门槛、不更换候选。
- 其余：AWAITING_RESEARCH_REVIEW，仅满足必要条件；不表示有效、已注册或获准评分。

若未来确有合格提案，仍需完整独立审查和执行接口。本轮协议中的配对 bootstrap、延迟门槛是待审前瞻设计，当前没有执行它们。现有验证集曾参与基线选择，不能当成新确认数据，也不能套用文献的独立校准样本保证。

## 命令与保守记录

```sh
# 新提案：仅闭合的固定协议；源码/参数/阈值不能由协议任意指定。
python3 -m research_harness tabular screen --baseline PATH_TO_BASELINE --protocol SCREEN_PROTOCOL.json --out NEW_PROPOSAL_DIR

# 已有提案：只读复核，或者保留它的机制关闭记录。
python3 -m research_harness tabular verify-screen --baseline PATH_TO_BASELINE --proposal PATH_TO_PROPOSAL
python3 -m research_harness tabular retain-screen --baseline PATH_TO_BASELINE --proposal PATH_TO_PROPOSAL
python3 -m research_harness tabular screen-history
```

`screen` 在计算前写入保守预留；中断不会自动释放。同一任务/数据分区的同一机制不能仅更换 ID 或目录重复提出。仓库发布的 `tasks/tabular_regression/screen-history.json` 与本地 `.research-memory/tabular-screen/` 合并，冲突拒绝；新 clone 继承已发布关闭记录。`retain-screen` 先独立核对旧提案及其基线，重复保留幂等，原始记录不改写。

这是机制筛查历史，不是最终留出分配器、跨服务器实时锁、全任务记忆或通用证据包。不同任务/分区分别作用域化，SR 记忆接口保持原样。哈希和本地锁不阻止能修改整个仓库的恶意用户。

## 本轮真实提案

[T1 报告](../tasks/tabular_regression/t1/REPORT.md)：delta 为 0.012122178108001425 ring，解析上界低于 0.05，按预声明规则拒绝。没有新的训练、留出推理/评分或模型服务调用。804 条最终留出记录仍未评分。

T1 最初由本轮编程助手检索文献并记录协议后执行了一次协调器筛查；随后新增接口对保存记录做只读复核并保留关闭状态。这不是原生自主研究 actor 的运行，不能记作第二领域完整自主闭环。公开文件仅包含协议、标量结果、账本及摘要，不是完整原始基线证据包；完整验证仍需要本地历史基线产物。

## 软件与证据检查

macOS 完整依赖环境的 141 项软件测试通过；系统 Python 同一套测试通过，其中 6 项依赖检查跳过。覆盖旧源码只读审计、篡改拒绝、seed 一致性、阈值冻结、中断预留及跨 clone 停止记录。原始基线运行的 12 个文件前后哈希一致，公开 T1 协议、结果、账本与本地原件逐字节一致。这些检查验证实现和记录一致性，不证明科学收益。
