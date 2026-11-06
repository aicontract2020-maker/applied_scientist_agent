# 自主提案与待审回归候选执行

0.18 支持“隔离 actor 查文献并提出固定特征 → 冻结人工审查包 → 获准后单次隔离训练/评分 → 独立复算审计”。T2 已获用户批准并执行一次，[结果 STOP](../tasks/tabular_regression/t2/REPORT.md)，804 条最终留出已消耗。该具体特征未达到冻结门槛，不能视为算法成功。0.19 的统一入口需显式 `--stage propose/execute`；未指定阶段仍拒绝启动。

## 边界与命令

运行环境沿用 `scripts/bootstrap-tabular.sh` 的 Python 3.12 和固定依赖。提案 actor 的隔离探针也使用现有 SR 环境，因此还需先运行 `scripts/bootstrap.sh --skip-assets`，安装 Codex CLI、pdftotext，并在运行机器上独立登录。不要在仓库或证据包中保存/转移登录文件。

```sh
# 一次提案会话；最多 600 秒。需要本机登录，无真实训练或评分。
.venv-sr/bin/python -m research_harness tabular propose --baseline BASELINE_DIR --out NEW_PROPOSAL_DIR

# 全文证据与具体候选已存在后，生成待审包；不运行真实特征或模型。
python3 -m research_harness tabular prepare-trial --baseline BASELINE_DIR --proposal NEW_PROPOSAL_DIR/proposal.json --literature NEW_PROPOSAL_DIR/literature.json --out NEW_REVIEW_DIR
python3 -m research_harness tabular verify-trial --review NEW_REVIEW_DIR

# 仅在人工审核了具体源码、文献、预算、数据消耗并同意后：
python3 -m research_harness tabular approve-trial --review NEW_REVIEW_DIR --sha256 EXACT_REVIEW_SHA --reviewer REVIEWER
.venv-tabular/bin/python -m research_harness tabular run-trial --review NEW_REVIEW_DIR
.venv-tabular/bin/python -m research_harness tabular audit-trial --review NEW_REVIEW_DIR
```

actor 只能得到任务列名、旧基线汇总和停止规则，不获得数据行/标签、训练或评分 RPC。现有 OS 边界拒绝仓库和控制目录访问。原生联网检索保留轨迹，检索次数 1–6 是事后核验的上限，不是工具层硬限流；模型费用未知。任务禁止获取外部基准标签，但网络出口并非域名白名单，这仍是本地研究原型。

候选源码必须只有 `def augment(row): return [...]`，返回 1–3 个新增特征。支持固定索引、有限数字、加减乘除、abs/min/max/sqrt/log1p；没有导入、属性、循环、任意调用、拟合状态或标签参数。控制器只解析 AST 并解释这些算术节点，**从不执行或导入候选 Python**。原十个特征不可修改。符合 one-hot 类别约束的合成探针拒绝常数、重复列、单列单调映射及明显无效表达式；有限探针不能证明所有程序等价性或科学新颖性。

## 固定执行协议

审核包绑定候选、文献文本、原基线证据、源码和全部分区。原基线批准不能覆盖候选研究；源码或候选变动会使批准失效。

- 固定 HGB 基线和追加特征的 HGB，各拟合 seeds 11/22/33，共六次；没有参数搜索。
- 基线验证预测须重现历史结果至 1e-8；两组留出预测跨 seed 范围也须不超过 1e-8。这是重复性检查，不是独立训练统计证据。
- 每个 seed 及平均 MAE 改善至少 0.05 ring，配对行 bootstrap 1,000 次、95% 下界大于零，预测时延比不超过 1.1，才 CONTINUE。使用现有共享效果/区间/时延判定函数。
- 时延固定取五次整批预测的中位数，候选包含特征构造；保留全部计时，不挑最好一次。训练耗时、特征构造、wall time、RSS、保留字节另报，真实货币成本未知。
- 240 秒 worker、16 MiB 输出监测上限、单线程 CPU；无硬内存保证。worker 有训练标签和无标签的验证/留出特征；最终标签仅控制器持有。
- 在暴露留出特征前写入整组分区预留。有效失败 STOP；无效测量/中断也保留预留，不自动重试，不换候选补救。

0.19 已补齐 [回归离线记忆与证据交接](TABULAR_HANDOFF.md)。不能在另一个 clone 把同一留出当成未用数据；离线快照与本机锁不能提供实时跨服务器协调。只读审计检查冻结输入、批准、执行源码、环境/隔离记录、预测、账本与重算决定；它不认证执行者、不证明数据独立性或基线全局最强。

## 这一轮的真实提案与故障记录

T2 是一个固定的壳重比例特征，见 [具体待审方案](../tasks/tabular_regression/t2/REVIEW.md)。actor 完成 5 次原生联网工具调用（其中 2 批共 6 条检索查询），控制器独立获取 3 篇主论文全文；提案阶段没有真实训练或评分；2026-11-06 用户批准后执行了一次真实试验，T2 已 STOP，不重跑。原始 Abalone 基线证据保持不变，T1 不重开。

首次 macOS npm/Node 启动器在初始化时 SIGABRT，stdout 没有任何 agent 事件，未产生提案。原记录完整保留；另一次显式基础设施恢复使用已安装原生 Codex，隔离配置不变。`--recover-launch` 只接受有保留证据的这类启动失败，且最多一次；产生任何 agent 事件/提案后都不允许该恢复。这是环境测量失败处理，不是失败研究路线重试。启动前新增不调用模型的 CLI 探针。

自动审批拒绝了把主机登录文件复制到 Linux 虚拟机，因此未转移凭据。真实提案会话在 macOS 完成；Linux 验证使用合成数据，不声称已在 Linux 跑过真实提案。

## 验证

```sh
python3 -m unittest discover -s tests -v
.venv-tabular/bin/python scripts/check-tabular-trial.py
```

单元测试检查算术语言拒绝、无效测量、效果/时延停止规则、独立审批和数据预留。集成脚本在真实内核隔离下用合成数据运行六次固定拟合，检查最终标签未进入 worker、独立复算、篡改拒绝和重复执行拒绝。Linux CI 包含同一脚本。所有 fixture 的批准均明确标记为软件测试，不是对真实 T2 的用户批准。

真实 T2 结果需用冻结的 `.venv-tabular/bin/python` 复核；Python 3.9 的统计浮点末位差异会触发严格审计拒绝。没有为此放宽比较容差或更改原始记录。
