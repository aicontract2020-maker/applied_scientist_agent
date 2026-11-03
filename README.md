# ResearchHarness

面向 Applied Scientist agent 的最小研究框架。当前版本提供确定性的研究流程约束，
尚未接入 LLM、自动查文献、执行训练任务或部署模型。

## 快速开始

需要 Python 3.10+，直接从仓库运行，无需安装依赖：

```sh
python3 -m research_harness --help
python3 -m research_harness register examples/protocol.json
python3 -m research_harness record forecast-pilot examples/result.json
python3 -m research_harness evaluate forecast-pilot
python3 -m unittest discover -s tests -v
```

示例是合成数据，仅演示协议格式；不代表任何真实研究结果。
第一次 record 后为 PENDING。完成流程需要提供独立的 seed=22、33 的结果文件，
不能重复录入 seed=11。真实实验前替换假设、最强基线及版本、控制变量和原始产物位置。
可通过 `--workspace /path/to/store` 指定实验目录（放在子命令前）。默认 runs/ 不纳入 Git。

## 决策规则 v0.1

- 注册协议后冻结并记录 SHA-256，禁止覆盖；结果附加到 ledger.jsonl。
- 预注册至少三个唯一 seed，按相同 seed 配对运行基线与候选方法。
- 效应使用主要指标的**绝对单位**：higher 为 candidate-baseline，lower 为 baseline-candidate。
- 完成所有预定重复后，平均效应 >= 最小有意义效果且每次效应均 > 0 才 CONTINUE。
- 报告每次效应、均值、样本标准差；这是一条保守的一致性规则，不是显著性检验或置信区间。
- 任一有效性检查失败或总美元成本超过预算，立即 STOP。
- STOP/CONTINUE 均关闭当前实验；CONTINUE 只允许规划下一项预注册研究，不是部署批准。
- 负结果不能靠增加调参或模型复杂度补救。新协议应明确关联旧实验，记录测量失效
  或新外部证据，以及为何构成新假设。当前版本由人工审查这项理由。

## 成本与证据

每次结果必须包含原始日志/检查点位置、有效性检查以及完整成本字段。
compute/storage/data/tuning 美元字段应互不重叠，覆盖基线、候选方法、失败尝试和调参。
compute_seconds 与 storage_byte_hours 累加；latency_ms 是同一测量条件下的单次推理延迟，
报告均值和最大值，不累加。零成本也必须明确填 0。费用在结果录入后才检查，
当前版本不能提前终止外部作业，也不自动核验账单或产物。

## 结构与边界

- `research_harness/core.py`：协议校验、结果登记、决策和账本。
- `research_harness/cli.py`：register / record / evaluate。
- `examples/`：合成协议和单次结果格式。
- `tests/`：停止条件、重复实验、成本和冻结规则的回归测试。
- `AGENTS.md`：后续研究和开发必须遵守的规则。

本地存储仅支持**单写入者**。哈希能发现意外修改，不能抵抗拥有整个目录写权限的 agent；
账本也不是不可篡改的审计系统。有效性检查为调用方声明，当前不存在独立测试集隔离。
研究代码执行、模型提供方和测试集访问应在后续版本通过独立权限边界实现。

## 下一步

1. 为一个明确业务任务制定真实协议，验证是否值得继续投入。
2. 接入模型适配器，先让 agent 草拟协议，由规则层校验。
3. 增加受限实验执行器、独立评价接口、预算计量及失败恢复。
4. 达到预注册标准后，再研究更长期的自主循环。
