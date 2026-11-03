# ResearchHarness

面向 Applied Scientist agent 的最小研究框架。当前版本提供确定性的研究流程约束，
已支持预注册的本地命令执行；尚未接入 LLM、自动查文献或部署模型。

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
手动 record 模式不能提前终止外部作业，也不自动核验账单或产物。
run 模式按预注册费率计量，详见下文；它不是实际云账单核验。

## 结构与边界

- `research_harness/core.py`：协议校验、结果登记、决策和账本。
- `research_harness/cli.py`：register / record / evaluate / run。
- `research_harness/execution.py`：命令执行、预算预检、超时与日志。
- `examples/`：合成协议和单次结果格式。
- `tests/`：停止条件、重复实验、成本和冻结规则的回归测试。
- `AGENTS.md`：后续研究和开发必须遵守的规则。

本地存储仅支持**单写入者**。哈希能发现意外修改，不能抵抗拥有整个目录写权限的 agent；
账本也不是不可篡改的审计系统。有效性检查为调用方声明，当前不存在独立测试集隔离。
研究代码执行、模型提供方和测试集访问应在后续版本通过独立权限边界实现。

## 下一步

1. 为一个明确业务任务制定真实协议，验证是否值得继续投入。
2. 接入模型适配器，先让 agent 草拟协议，由规则层校验。
3. 在本地执行器之上增加独立评价权限、真实费用计量和显式恢复流程。
4. 达到预注册标准后，再研究更长期的自主循环。


## 本地执行器 v0.2

运行一个**合成软件演示**，只验证流程，不作科学结论：

```sh
mkdir -p runs
python3 examples/local_demo/prepare.py > runs/demo-protocol.json
python3 -m research_harness register runs/demo-protocol.json
python3 -m research_harness run synthetic-execution-demo
python3 -m research_harness evaluate synthetic-execution-demo
```

同一实验不会覆盖注册。已关闭的实验再次 run 只返回原决策，不启动新进程。

协议增加 `execution` 对象：

- `cwd`：预先指定的绝对工作目录。
- `command`：参数数组，无 shell 展开；支持 `{python}`、`{seed}`、`{output}`。
  每个命令负责同一 seed 的基线和候选评估，并写出结果 JSON。
- `inputs`：相对于 cwd 的文件路径到 SHA-256 的映射。注册时和每次启动前校验。
  必须列入实际使用的代码、数据和评价文件；未列入的依赖不会被自动发现或冻结。
- `timeout_seconds`：每次重复的时间上限；超时终止同一进程组。
- `compute_usd_per_hour`：整次运行分配资源的合计每小时费率，按墙钟时间计量。
- `fixed_costs`：每次尝试的 data_usd、storage_usd、tuning_usd，要求非负。

执行前用时间上限和固定费用预留预算。该预检依赖正确费率，进程启动/终止开销
可能使实际计量略超预留；它不能限制代码自行调用外部服务的支出。软件不会自行
连接计费服务。硬件、电费等本地成本如需核算，应反映到配置费率。

命令输出结构与手动 result 类似，但由父进程填写 `artifact` 与 `costs`；
子进程须提供 `seed`、`baseline_score`、`candidate_score`、`validity`，以及：

```json
{"measurements": {"storage_byte_hours": 1024, "latency_ms": 5}}
```

每次运行保留 `attempts/seed-N/` 下的 stdout.log、stderr.log、result.json。
账本记录启动、结束、费用、结果和最终决策。失败、超时、结果缺失或格式错误立即
STOP，保留已经发生的费用，不自动重试。命令尚未产生有效测量时，STOP 表示执行
失效，不构成对科学假设的否定。

进程或父程序意外中断会留下未完成尝试；下一次 run 拒绝自动重跑，要求人工核对
产物、残留进程及成本。当前尚无自动恢复命令，不能通过删除账本绕过这一限制。

### 权限边界

本地执行器只约束启动参数、时长和流程，**不是操作系统隔离环境**。
工作目录不等于文件访问边界：子进程继承当前用户的文件、网络和环境变量权限。
不要在此运行不可信生成代码；接入模型自动执行之前，应增加容器或其他操作系统
权限隔离，并将隐藏测试集和评价器放到独立边界。当前有效性检查仍是执行代码声明。
输出日志也没有硬性大小配额；超时控制不能替代磁盘配额。
