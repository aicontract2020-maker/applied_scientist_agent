# 批准前审阅冻结材料

0.35.0 新增 `task review`，供人工在记录执行批准**之前**核对四类固定
Abalone / Airfoil 材料。不需要先批准，也不依赖可编辑的 `REVIEW.md`。

```sh
.venv-tabular/bin/python -m research_harness task review \
  --workflow abalone-baseline-v1 --review /checkout/reviews/baseline

.venv-tabular/bin/python -m research_harness task review \
  --workflow airfoil-candidate-v1 --review /checkout/reviews/candidate
```

支持的 ID 是 `abalone-baseline-v1`、`abalone-candidate-v1`、
`airfoil-baseline-v1`、`airfoil-candidate-v1`。SR 的自主注册流程不同，
不会套用人工批准摘要；使用已有 `sr-preflight` 与原研究材料。

## 摘要的依据

入口直接调用原生严格加载器，验证冻结包摘要、当前源码、固定科学协议、
数据分区和资格绑定。候选还核对代码、干预审查及内嵌基线历史审计。之后
只从已验证内容中选择字段输出 JSON：

| 字段 | 审阅用途 |
|---|---|
| `packet_sha256` / `packet_file` | 识别本次冻结包；原批准仍绑定该包摘要 |
| `protocol` | 完整原协议，包含假设或决策目的、控制、指标、阈值、重复/不确定性、成本、STOP / GO 及无效测量规则 |
| `proposal` | 候选假设、机制、新颖性理由、代码、证据主张及限制；基线阶段为 null |
| `reference` | 候选所用基线包摘要、原基线协议与计划比较模型；不宣称全局最强基线 |
| `dataset` | 固定来源、分区数量、观测单元、分区清单摘要；不含数据行 |
| `data_qualification` | 用途、八项资格状态、资格和决定摘要、证据数量；资格接受只支持协议设计 |

协议和提案是冻结内容的原样结构，不由模型改写。修改或删除 `REVIEW.md`
不会改变摘要；修改冻结协议、数据、代码或资格则由原加载器拒绝。旧源码
材料不会自动刷新。`EVIDENCE_ONLY.json` 标记的材料（含候选内嵌基线）
拒绝进入此入口，应改用已有历史证据审计命令。

输出不展开数据行、标签、保存的预测、论文全文或资格证据全文。审查者仍须
阅读原包内的完整证据，核实许可、独立性、文献解释及实际用途；资格摘要不
是真实性认证。提案文字和用途仍按原文展示，这是本地审阅工具，不是公开
脱敏导出功能，也不会将其自动交给研究 actor。

## 通过不等于当前可执行

成功状态是 `FROZEN_MATERIALS_VERIFIED`，仅表示冻结材料校验通过。
`execution_approval_checked`、`current_constraints_checked`、
`isolation_checked` 和 `execution_authorized` 均为 false。

这一步不读取或修改**本次**执行批准，也不检查当前暂停、停止路线、占用、
已消费数据或运行目录；已经执行过的材料仍可能获得有效摘要。因此它不
返回“等待批准”或“可执行”结论，不代表人尚未批准、数据尚未使用或路线
仍可继续。候选的历史基线批准会由原历史审计核验，不能替代当前执行批准。

人工决定、记录精确摘要批准、[`task check`](WORKFLOWS.md)和原执行器的
锁内复查仍分别保留。消费/暂停后的摘要不能使这些入口通过，也不释放预留
或重开 STOP。当前约束、材料或代码变化时，仍按原规则拒绝，不自动改方案。

命令不写研究目录或批准，不启动安装诊断、隔离探针、训练、预测或研究模型。
原生加载器会读取数据以核验分区；候选会复算已有基线预测的历史审计统计，
不会产生新实验结果。Airfoil 候选的历史审计要求 Python 3.12；其他只读
摘要支持 Python >=3.10。使用已安装的 `.venv-tabular/bin/python` 可统一
调用。实际研究范围与执行规则不变。

错误使用非零退出码和 stderr，不输出成功摘要。未知流程在读取路径前拒绝。
完整工程验证见 [C17 验收说明](REVIEW_SUMMARY_REVIEW.md)。
