# C6：候选试验的数据资格与执行前检查

0.24 将已验收的 C4/C5 机制接入两个已有封闭候选流程：Abalone 固定 HGB 算术特征试验、Airfoil 固定 Strouhal 特征试验。没有新增候选方法、数据来源或通用训练能力。

## 基线接受不扩大为候选许可

候选会访问最终留出，必须单独准备适用该阶段的 C4 资格包并由人接受。`task` 必须分别为 `abalone-candidate-v1` 或 `airfoil-candidate-v1`，不能使用 `abalone-baseline-v1` / `airfoil-baseline-v1`。数据身份、版本字符串 `1`、来源与 [C5](DATA_ADMISSION.md) 对应表一致；`intended_use` 须准确说明固定训练、历史验证复现、一次最终留出评价及预定发布范围。

匹配字符串不等于事实或许可认证。审查者必须核实八项证据，特别是用途、标签访问、数据已暴露历史和已停止路线。资格接受不能解除停止记忆或让已消费的数据重新可用。

## 固定流程

1. 验证已有基线的历史证据，并检查本次候选阶段资格与用途。这里只读核验已保存的基线，不重新训练基线。
2. 保留原候选机制审查、停止记忆与数据可用性检查。冻结候选后，`trial.json` 中嵌入独立候选资格、人工决定和用途，同时绑定**完整候选、固定 recipe、精确基线证据摘要、全部数据分区摘要**。
3. 人工单独批准该候选执行包的精确摘要。数据资格接受和基线执行批准都不能替代候选执行批准。
4. `preflight-trial` 只读核对资格、绑定、代码、批准和停止/占用记忆，不启动隔离探针、工作进程或模型。
5. 真正执行时重新检查这些条件，再运行原环境/隔离探针；探针结束后再次核对完整包、基线、数据、批准和可用性，然后才预留与注册、启动唯一一次执行。

原评价函数、阈值、seed、复制次数、成本记录、隔离规则和有效失败 STOP 均未改变。资格原文仅保存在控制端审查包，worker 的请求结构不增加资格或私有通信。

## 准备与检查命令

以下是将来**单独获准的新候选**的操作方法，不是对当前已停止/已消费数据的运行授权。真实候选流程要精确审计历史基线，须先按安装说明准备项目固定的 Python 3.12 表格环境；下面使用 `.venv-tabular/bin/python`，不要依赖系统默认 Python。

```sh
.venv-tabular/bin/python -m research_harness tabular prepare-trial \
  --baseline PATH_TO_AUDITED_BASELINE --proposal PATH_TO_PROPOSAL \
  --literature PATH_TO_RETRIEVED_PAPERS --out reviews/new-candidate \
  --data-review PATH_TO_ACCEPTED_CANDIDATE_PACKET \
  --intended-use '与候选资格包完全一致的用途'

.venv-tabular/bin/python -m research_harness airfoil prepare-trial \
  --baseline PATH_TO_AUDITED_BASELINE --proposal PATH_TO_PROPOSAL \
  --out reviews/new-airfoil-candidate \
  --data-review PATH_TO_ACCEPTED_CANDIDATE_PACKET \
  --intended-use '与候选资格包完全一致的用途'
```

人审时必须阅读 `REVIEW.md` 以及 `trial.json` 内完整资格证据。获得精确执行批准并记录后，可运行：

```sh
.venv-tabular/bin/python -m research_harness tabular preflight-trial --review reviews/new-candidate
.venv-tabular/bin/python -m research_harness airfoil preflight-trial --review reviews/new-airfoil-candidate
```

通过输出 `PRECHECK_PASSED`、`read_only: true`、`memory_checked: true`，同时保留 `execution_authorized: false` 和 `isolation_checked: false`。静态检查本身不是新的批准，也不证明当前系统隔离可用。失败退出 1，不自动换候选或修订协议。

统一提案入口也需要候选资格，并在创建研究输出、预留和调用 actor 前检查：

```sh
.venv-tabular/bin/python -m research_harness research --task tabular-regression --stage propose \
  --id NEW_STUDY --baseline PATH_TO_AUDITED_BASELINE \
  --data-review PATH_TO_ACCEPTED_CANDIDATE_PACKET --intended-use '完全一致的用途'
```

直接 `tabular propose` 同样有这两个必填参数。资格不会作为 actor 输入；冻结时再次校验并保存到人审包。`research --stage execute` 使用冻结资格，不接受运行时 `--data-review` / `--intended-use` 覆盖。原执行命令也没有覆盖选项。

## 历史与边界

旧真实候选包没有候选资格时，只读审计继续支持；新批准/执行拒绝，不能删除字段回退。带资格的历史包即使只读审计也检查其完整性；私有证据包交接保留嵌入资格，导入后仍是 review-only。内部纯合成 fixture 保留旧格式兼容，用于原有测试；提供资格时同样严格验证。

冻结快照不自动同步后续许可变化。新限制必须停止并重新审查，不能以旧快照抵消。摘要、人名仍不是签名或身份认证；拥有整目录写权限的人可伪造材料。跨 checkout 没有实时锁，原停止/暴露记忆交接仍必需。公开仓库不会收录私有资格全文、标签或邮件。

本次仅覆盖上述两个候选入口及其统一提案调用链。SR 和通用可信本地 `run` 没有因此被宣称为候选资格管理入口。Delft 尚不具备直接复现条件，不能套用 Airfoil 原始数据 adapter 绕过未决问题。接受 C6 工程交付不批准新研究实验。

## 当前数据暂停记录

0.25 起，Abalone/Airfoil 的准备、批准、提案和执行另检查本地[数据使用暂停](DATA_USE_BLOCKS.md)。暂停包须单独随原记忆／证据交接并导入接收方实际执行的 checkout；旧批准和本页的交接文件不能解除或隐式同步暂停。历史只读审计保留。
