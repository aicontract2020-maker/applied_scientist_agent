# ResearchHarness

面向 Applied Scientist agent 的研究工作流 MVP。已支持结构化规划接口、人工审查、
预注册、本地可信命令执行、决策账本与报告。提供 Codex CLI 规划适配器及离线回放。
模型适配器经过模拟接口测试，尚未在本项目真实调用模型；不声称已验证模型研究能力。
当前没有自动文献检索、生成代码执行、独立隐藏测试环境或部署功能。

## 快速开始

建议 Python 3.10+（本次真实任务环境为 Python 3.12.14），直接从仓库运行，无需安装依赖：

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

## 已完成的真实基线

图像超分 SwinIR-S ×2 / Set5 已完成一次确定性复现：PSNR-Y 38.13941 dB，
参考 38.14 dB，误差 0.00059 dB，小于预注册的 0.02 dB。
详见 [基线报告](tasks/image_super_resolution/G0_REPORT.md)。这不是模型改进或 agent 能力验证。

## 决策规则 v0.1

- 注册协议后冻结并记录 SHA-256，禁止覆盖；结果附加到 ledger.jsonl。
- 随机改进研究（默认 paired_improvement）：预注册至少三个唯一 seed，配对运行基线与候选方法。
- 确定性复现（deterministic_reproduction）：一次执行、seeds=[0]、minimum_effect=0；
  必须冻结 reference_score、reference_source、reproduction_tolerance，并使用双侧绝对误差门槛。
  seed=0 是执行编号，不是假装独立训练。
- 效应使用主要指标的**绝对单位**：higher 为 candidate-baseline，lower 为 baseline-candidate。
- 随机改进完成所有预定重复后，平均效应 >= 最小有意义效果且每次效应均 > 0 才 CONTINUE。
- 确定性复现与参考绝对误差 <= 容差才 CONTINUE，分数大幅高于参考也视为复现不符。
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
- `research_harness/cli.py`：规划、审查、注册、执行及报告命令。
- `research_harness/planning.py`：结构化计划校验与 fixture/Codex 适配器。
- `research_harness/review.py`：与内容摘要绑定的审查记录及报告导出。
- `research_harness/execution.py`：命令执行、预算预检、超时与日志。
- `examples/`：合成协议和单次结果格式。
- `tests/`：停止条件、重复实验、成本和冻结规则的回归测试。
- `AGENTS.md`：后续研究和开发必须遵守的规则。

本地存储仅支持**单写入者**。哈希能发现意外修改，不能抵抗拥有整个目录写权限的 agent；
账本也不是不可篡改的审计系统。有效性检查为调用方声明，当前不存在独立测试集隔离。
研究代码执行、模型提供方和测试集访问应在后续版本通过独立权限边界实现。

## 下一步

1. 人工审查首个真实业务任务、数据、基线、预算和权限（见 REVIEW.md）。
2. 真实调用规划适配器，检查其缺失信息处理和计划质量。
3. 接入独立评价权限、受隔离的实验环境、真实费用计量和显式恢复流程。
4. 在预注册实验支持继续后，再研究更长期的自主循环。


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


## 规划与审查 v0.3

### 离线完整演示

```sh
python3 examples/local_demo/workflow.py
```

创建新的 `runs/reviewed-software-demo/`，完成计划回放、模拟人工审查、注册、三次
合成测量、决策和 Markdown 报告。演示中的审批明确标记为软件测试记录，不是用户
对真实研究的许可。不要把演示的自动批准逻辑用于模型输出或真实研究。

缺失上下文示例（不调用模型）：

```sh
python3 -m research_harness plan examples/product-brief.md \
  --response examples/needs-context-response.json --out proposals/missing-context
```

fixture 是已保存响应的回放，不会生成研究计划，不是自主规划能力的演示。

### 真实规划接口（需要可用的 Codex 登录和已审查的数据范围）

```sh
python3 -m research_harness plan path/to/brief.md \
  --provider codex --timeout 120 --out proposals/first-real-plan
```

可传 `--model` 明确模型，否则由 CLI 默认决定。使用本机 Codex CLI，要求支持
`--output-schema`、`--ignore-user-config`、`--ephemeral` 和 `--sandbox read-only`。
适配器指定只读、无交互提升权限和结构化输出，不加载用户 config.toml 中的 MCP/
插件配置；这不是模型访问数据的保密边界。只读权限不等于只能读取 brief：不要把它
当作隔离秘密、整个主机文件系统或防止提示注入的保证。模型服务仍需要网络登录。
规划提示要求不要调用工具，但当前系统没有强制的工具白名单；需要受限环境才能
用于敏感数据。仅将允许向模型服务发送的内容放入 brief 和规划运行目录。

命令只生成候选计划，不注册、不执行实验。不自动重试；失败保留 request、prompt、
原始输出和本地日志。外部模型费用记为未知，不伪装为零，不包含在实验预算中；
首次真实调用前需确认账户使用方式和费用范围。日志可能包含敏感内容，proposals/
与 reviews/ 默认不提交 Git。

返回 `needs_context` 时必须先解决问题；不会用虚构的预算或数据自动补全。
返回 `ready_for_review` 只表示字段齐全，不能证明证据、基线或计划科学有效。
模型输出禁止包含 execution 配置；实际执行命令由操作者另行提供。

### 真实计划审查流程

```sh
python3 -m research_harness review proposals/first-real-plan/proposal.json \
  --execution path/to/execution.json --out reviews/first-real-review
# 阅读 reviews/first-real-review/REVIEW.md，核实输入、代码、阈值、成本和权限。
python3 -m research_harness approve reviews/first-real-review/bundle.json \
  --sha256 EXACT_HASH_FROM_REVIEW --reviewer YOUR_NAME
python3 -m research_harness register-review reviews/first-real-review/bundle.json
python3 -m research_harness run EXPERIMENT_ID
python3 -m research_harness report EXPERIMENT_ID --out runs/REPORT.md
```

审批绑定完整内容摘要，不能复用到改过的计划、预算或命令。输入文件改变会导致
审批/注册/执行校验失败。approve 不是身份认证：具有目录写权限的人可修改文件；
该记录用于本地协作追踪，不是安全或合规审计证明。
原始 register 命令仍保留，适合人工编写的可信协议，**没有审查来源保证**；不要
使用它绕过模型计划审查。最终运行的代码、环境及测试集仍需可信与独立权限设计。

Codex 接口依据：[官方非交互模式文档](https://developers.openai.com/codex/noninteractive)。
本地适配器已对照安装版本的 `codex exec --help`，未进行真实模型调用。
