# 跨任务数据资格审查

0.22 提供 `data-review`，把新数据的使用范围、未决问题、证据及人工判断保存为可检查的离线材料。它没有训练、预测、网络、模型调用或研究执行入口；不会预留或消费留出。数据资格通过只允许起草后续协议。

## 先跑纯软件演示

Python 3.10+，无需安装额外依赖。在仓库根目录执行，输出目录必须不存在：

```sh
python3 -m examples.data_qualification.workflow --out runs/data-review-demo
python3 -m research_harness data-review inspect runs/data-review-demo/supported-packet.json
```

三个独立合成案例分别展示缺失、不兼容和证据齐全；第三个案例记录明确标记 `SYNTHETIC_REVIEWER` 的模拟接受。不是修复一条失败的研究路线，也不是对任何真实数据的批准。演示结果始终包含 `synthetic_only: true` 和 `execution_authorized: false`。

## 准备真实材料（不是运行研究）

先创建本地私有目录，再生成空模板：

```sh
mkdir -p reviews/my-data
python3 -m research_harness data-review template --out reviews/my-data/draft.json
```

填写 `id`（安全的小写标识）、`task`（文字范围，不是插件名）、`dataset.id/version/source`、`intended_use`。用途必须说清研究/商业背景、共享对象及拟发布内容。空模板不能冻结。

八项条件必须全部保留，不允许删除或写成“不适用”以跳过检查：

| 字段 | 审查内容 |
| --- | --- |
| provenance | 数据来源、版本、与既有数据来源的独立性 |
| permission | 精确用途和发布范围的适用许可依据 |
| features | 输入定义、单位、无标签参与的变换 |
| target | 目标定义、单位及确定性的转换依据 |
| independence | 独立观测单元、依赖群组、划分规则 |
| validity | 评分前确定的质量掩码、排除条件、最少有效单元 |
| holdout_history | 已暴露、预留和消费记录，包括已知外部交接历史 |
| access_boundary | 标签访问权限及可用隔离执行边界 |

每项填写 `state`、`rationale` 和证据 ID 列表 `evidence`。状态只接受 `unresolved`、`supported`、`incompatible`；后两者必须引用至少一份证据。`supported` 是提交者的主张，不是工具对事实的认证。

证据是显式选择的 UTF-8 元数据文本。顶层 `evidence` 例子：

```json
{
  "author-note": {
    "path": "author-note.txt",
    "sha256": "替换为该文件实际字节的64位小写SHA-256",
    "source": "材料来源及日期",
    "locator": "支持相应条件的章节或段落"
  }
}
```

路径相对草稿所在目录；不接受绝对路径、`..`、符号链接或特殊设备文件。输入/输出路径的父目录也不能是符号链接；例如 macOS 使用临时目录时用解析后的实际路径。每份证据最多 256 KiB，合计最多 1 MiB、64 份，编码后包最大 4 MiB。未引用的证据、未知字段、重复 JSON 键、摘要不符均拒绝。工具不下载 `source` 中的链接，也不执行文字中的命令。

填写完成后冻结并检查：

```sh
python3 -m research_harness data-review prepare reviews/my-data/draft.json --out reviews/my-data/packet.json
python3 -m research_harness data-review inspect reviews/my-data/packet.json
```

包内保留全文证据、来源与定位信息。`inspect` 输出摘要及未决/不兼容项目，不回显全文。人审时必须阅读 `packet.json` 中的实际内容，不能仅凭摘要接受。包默认文件权限 0600；`reviews/` 不进入 Git。不会自动删去个人信息，不能把此包当作可公开发布的报告。不得加入原始标签、密钥或未经授权共享的邮件；程序无法仅凭文本识别这些内容。

## 状态和人工决定

| 条件 | 状态与允许的下一步 |
| --- | --- |
| 任一 incompatible | STOP_DATA_QUALIFICATION；停止该来源的资格路线，不是对科学假设的否定 |
| 无 incompatible，但存在 unresolved | BLOCKED_DATA_QUALIFICATION；等待明确外部证据，不能接受 |
| 八项 supported 且证据一致 | AWAITING_DATA_REVIEW；等待人核实陈述、证据及使用范围 |
| 人工接受精确摘要 | QUALIFIED_FOR_PROTOCOL_DESIGN；只可准备独立冻结的研究协议 |
| 人工拒绝 | STOP_DATA_QUALIFICATION；保留拒绝及理由 |

人工明确审核后才记录决定，下面的摘要和审查者必须替换为真实值：

```sh
python3 -m research_harness data-review decide reviews/my-data/packet.json \
  --sha256 EXACT_PACKET_SHA256 --reviewer REVIEWER \
  --decision accept --reason '核实证据后具体接受的用途与限制'
```

拒绝时使用 `--decision reject` 并写明原因。决定自动保存为 `packet.json.decision.json`，同一路径只写一次，不覆盖；以后 `inspect` 自动校验并应用它，不能在命令里忽略已有拒绝。改变用途、证据或条件会改变整个包摘要，旧决定不再匹配；不能静默换包。交接时一起传递包与同名决定文件，保持命名关系，再执行只读检查。原草稿与源文件不需要传递，因为证据已嵌入包。

正常检查的退出码 0 表示材料格式/完整性有效，可能仍为 BLOCKED 或 STOP；不是研究成功。格式、摘要或决定不一致退出 1。输出始终是 `execution_authorized: false`。现有实验注册器不接受这种包作为协议。

## 明确边界

这是离线审查记录，不是签名、身份认证、法律判断或全局锁。拥有整个目录写权限的人仍可删除或伪造材料；复制包到另一个位置也不会自动共享决定。禁止删除、改名或复制记录以重开被拒绝的路线。新外部证据若确实改变判断，应另外记录原因、保留旧包及旧决定并重新人工审查，不能伪装成原包通过。

0.23 已通过 [C5](DATA_ADMISSION.md)接入 Airfoil/Abalone **新建基线**的执行前检查；其他旧 runner 不因此自动纳入，不回写历史 A1/A2/T2 或超分记录，也不声称已经实现通用数据 adapter。新任务仍须完成任务专用映射、最强相关基线、预注册、停止记忆与数据预留、隔离探针及独立执行批准。数据资格通过不能替代任何一项。当前 Delft 未决事项保持原状，没有因为新增模块而获得资格或实验许可。
