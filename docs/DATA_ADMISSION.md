# C5：数据资格与执行前检查

0.23 将 C4 接入现有两个封闭适配器的**新建基线资格检查**：Abalone 与 Airfoil。它们是任务进入候选研究之前的第一道真实执行边界。没有新增任意数据训练入口；Delft 仍不是受支持的数据适配器。

## 现在的顺序

1. 元数据阶段：C4 八项完整，并由人接受精确摘要，只得到协议设计资格。
2. `prepare`：先检查已接受的资格与本次用途，再读取固定数据；冻结数据分区、固定方案、资格全文及其人工决定。
3. 人工审阅新的基线执行包，独立批准精确摘要。资格接受不能替代这次批准。
4. `preflight`：只读检查材料、数据、代码、执行批准和已有尝试；不启动环境探针或 worker。
5. `baseline`：重新执行同样的检查，再检查环境和实际 OS 隔离。探针结束后再次核对整包与批准，完全一致才创建尝试/预留并交给原隔离 runner。

数值门槛、固定模型、seed、隔离方式和原有停止规则未改变。资格原文留在控制端，worker 仍仅获得原来允许的训练和验证输入。任何真实执行仍需要用户单独批准；本轮研发没有提供这样的授权。

## 资格内容必须对应适配器

| 字段 | Abalone 新建基线 | Airfoil 新建基线 |
| --- | --- | --- |
| `task` | `abalone-baseline-v1` | `airfoil-baseline-v1` |
| `dataset.id` | `uci-abalone-v1` | `uci-airfoil-condition-v1` |
| `dataset.version` | `1`（字符串） | `1`（字符串） |
| `dataset.source` | `https://archive.ics.uci.edu/dataset/1/abalone` | `https://archive.ics.uci.edu/dataset/291/airfoil+self-noise` |
| `intended_use` | 必须与本次传入的用途全文一致 | 必须与本次传入的用途全文一致 |

这里的 task 是封闭数据适配器标识，不修改原 `task list` 的数值评价契约。版本 1 对应代码中固定的原始数据摘要与解析规则，不能换一个同名 CSV。工具只核对文本和摘要一致性，人仍需核实用途描述是否准确、许可是否实际覆盖，不能用相同字符串把不同实际用途伪装成一致。

## 命令（仅用于将来单独审查的新材料）

先按 [C4 说明](DATA_QUALIFICATION.md)准备并人工接受资格文件。然后为真实的新基线材料调用：

```sh
python3 -m research_harness airfoil prepare \
  --data /absolute/path/airfoil_self_noise.dat \
  --data-review /absolute/path/accepted-packet.json \
  --intended-use '与资格包完全一致的用途描述' \
  --out reviews/new-baseline
```

Abalone 使用 `tabular prepare`，相同新增参数。命令仅准备材料，不执行研究。既有 A1/A2 数据已用，这个示例不是重跑授权。

审阅 `reviews/new-baseline/REVIEW.md` **以及 bundle.json 内完整资格证据**。新执行批准仍使用原来各适配器的 `approve` 命令，并指定新包精确摘要。批准后可做只读检查：

```sh
python3 -m research_harness airfoil preflight --review reviews/new-baseline
# 或对应的 tabular preflight
```

通过时返回 `PRECHECK_PASSED`、`read_only: true`、`execution_authorized: false`、`isolation_checked: false`。这只表示静态条件满足；不会自动调用 `baseline`，也不是对隔离环境可用性的证明。没有单独执行批准、尝试已消费或材料不匹配时退出 1。

## 冻结与变更

基线包的新 `data_admission` 字段包含 C4 包和决定的完整快照，绑定适配器/数据身份/用途、分区摘要及基线 recipe 摘要。整个外层包再绑定源码和执行批准。证据、用途、分区或方案改变后，旧执行批准失效。总包超过 4 MiB 时在创建输出目录前拒绝。

运行时使用冻结快照，不依赖原 C4 文件的位置，也不联网同步作者后续通信。收到撤回许可或其他新限制时必须停止并重新人审，不能拿旧快照推翻新信息。每次运行重新核对的是冻结材料一致性，不是实时许可认证。

历史真实包未包含此字段时：只读审计仍支持原格式；新批准/执行拒绝，不会自动补一个虚构的资格接受。历史审查文档中的旧准备命令保留作记录，当前命令增加了必填参数。内部 `prepare_rows` 的纯软件 fixture 继续兼容旧测试；它不是任意新数据的公共入口。带资格的 fixture 与真实材料一样严格检查资格，不忽略坏证据。

## 覆盖范围与限制

- C5 首次接入只覆盖上述两个**新基线**入口，不把所有旧候选、SR 或可信本地 `run` 自动升级为 C4 管理的执行器。未知数据源依然在封闭适配器层拒绝，无默认 fallback。
- 已停止路线和已消耗留出不能因重新接受元数据而重开；既有候选路径继续检查原停止记忆和留出预留。新 adapter 仍必须单独实现自己的停止/暴露历史消费规则。
- 没有增加跨 checkout 协调。Airfoil 保留原数据来源级预留；Abalone 基线仍只有原目录级一次尝试限制，跨副本防重不在本轮保证内，不能通过复制目录重跑。
- 摘要和本地人名仍不是身份签名；写权限可伪造材料。并发修改在探针后发现会拒绝，但这不是对恶意同用户进程的文件系统事务保证。
- 包包含私人元数据和标签，继续留在私有审查目录，不能直接推到公开 Git。原始证据不进入 worker 请求。

下一步接入候选或新数据 adapter 时，必须重新明确任务范围、数据映射、停止记忆与执行批准；本模块没有替它们提供许可或科研有效性。
