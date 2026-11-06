# 回归工作流与离线交接

0.19 增加分阶段统一入口、跨 checkout 的保守排除记录，以及可离线复算的私有证据包。T2 的 804 个已用特征组随仓库发布，新 clone 会在提案/训练前拒绝复用。没有重开 T1/T2，也没有新增真实实验。

## 统一入口仍保留人工审查

```sh
python3 -m research_harness task capabilities tabular-regression

# 仅适用于尚未使用、已通过资格检查的基线；当前 T2 数据会提前拒绝。
.venv-sr/bin/python -m research_harness research --task tabular-regression \
  --stage propose --baseline BASELINE_DIR --id NEW_WORKFLOW_ID

# 上一步冻结具体候选与 review 后，经人工明确批准精确摘要：
python3 -m research_harness tabular approve-trial --review REVIEW_DIR --sha256 EXACT_SHA --reviewer REVIEWER
.venv-tabular/bin/python -m research_harness research --task tabular-regression \
  --stage execute --review REVIEW_DIR --id FROZEN_PROPOSAL_ID
```

提案阶段只返回待审包，没有自动审批/执行。执行阶段核对原候选 ID、当前源码、精确批准与数据/路线排除，仍只有一次试验。v1 的评价契约及摘要没有改变；未带 `--stage` 的回归 `research` 仍拒绝。`task capabilities` 单独说明这些工作流能力，不能把它解释为任意任务的全自动研究。

目前实际数据入口仍限定已有 Abalone/HGB 特征研究，不支持任意数据集、目标或训练算法。现有 Abalone 留出已消耗，统一入口不会据此自动启动下一轮。新任务需要新的数据定义与审核。

## 排除记录：先交接，再串行接手

```sh
python3 -m research_harness tabular memory status
.venv-tabular/bin/python -m research_harness tabular memory retain --review COMPLETED_TRIAL_DIR
python3 -m research_harness tabular memory export --out NEW_MEMORY.json
# 接收者在自己的 checkout 中：
python3 -m research_harness tabular memory import NEW_MEMORY.json
```

记录合并仓库已发布历史、本机预留和导入包。终局不能被旧 RESERVED 降级，冲突拒绝；重复导入幂等。中断/测量无效的预留不释放。新试验在暴露留出前保存特征指纹和路线指纹；旧版只有分区摘要的本机记录保持保守排除，可经完整审计补全。

相同特征向量的指纹不依赖行 ID、顺序或其他训练分区，能够拦截这些方式造成的复用。它不能认证实体身份，也不能识别所有数据伪装。已 STOP 候选保留源码/机制，并用抹去数值常数但保留列索引的 AST 指纹拒绝改常数补救；不同代数写法的等价性仍需人工审查，不声称通用语义判定。

这类包不含原始行、标签、批准文本，但含候选源码和机制描述；分享前审查知识产权。特征哈希也不是匿名化证明，可能泄露已知数据成员关系。

这是离线交换和本机锁，**不是分布式协调**。两个旧快照仍可能同时认为新数据可用；共同数据池必须先交接，再由一个接收者串行执行。记录不能通过删除、复制或回退仓库版本来解除。

## 完整证据：私有、只读、与执行授权分开

```sh
.venv-tabular/bin/python -m research_harness tabular evidence export --review COMPLETED_TRIAL_DIR --out PRIVATE_PACKET.json
.venv-tabular/bin/python -m research_harness tabular evidence verify PRIVATE_PACKET.json
.venv-tabular/bin/python -m research_harness tabular evidence unpack PRIVATE_PACKET.json --out NEW_CONTAINER
```

完整包包含冻结协议、原始训练数据、留出标签/预测、原审批文本、引用论文文本及必要执行源码。**它不是可默认公开的摘要**，本轮没有上传到 GitHub。输出文件默认权限 0600。公开仓库仅存排除记录和检查摘要。

文件名采用固定 25 项允许列表，无归档解压或任意路径；逐文件和整体哈希、大小上限、重复 JSON key、非有限数、符号链接及未知字段均检查。验证时只把源码作为文本比较，不导入其中的 Python。完整复算使用冻结 Python 3.12；其他版本明确拒绝，不放宽浮点比较容差。

解包目录带有只读证据标记，不能用于当前审批/执行。证据验证也不会自动导入排除记忆，这两个动作分别明确执行。哈希和审计证明记录内部一致，不认证发送者、实际进程运行或数据独立性；来自不可信方的一套自洽伪造记录仍可能通过。

## 一条命令做接收端验收

```sh
.venv-tabular/bin/python scripts/check-tabular-handoff.py \
  --packet PRIVATE_PACKET.json --memory MEMORY.json --out NEW_RECEIVER_FOLDER
```

此命令不调用模型、不训练、不推理，只复算保存记录并确认：结果一致、排除记忆与证据绑定、已用数据被拒绝、导入的旧审批不可执行。它创建独立接收目录，不改变原试验或将数据重新变为可用。

本轮 macOS 3.12.13 → Linux 3.12.3 对真实 T2 包完成只读验收，STOP 和 804 个排除特征组一致；原始 T2 所有文件保持不变。见 [macOS 检查](tabular-handoff-evidence/macos.json) 和 [Linux 检查](tabular-handoff-evidence/linux.json)。这是本机不同环境的工程验证，尚不是独立同事的可用性验收。

后续 C3 [独立同事交接验收](INDEPENDENT_HANDOFF_REVIEW.md)已于 2026-11-06 由用户确认通过，接收端原始记录未附；不将上面的维护者检查冒充独立使用者证据。下一步为 [D1 研究价值评测设计](RESEARCH_VALUE_REVIEW.md)。
