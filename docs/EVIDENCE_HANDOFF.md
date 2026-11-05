# 离线审查证据交接

0.14.0 新增的是某一轮运行的**审计必要证据包**。它与研究记忆用途不同：`memory export/import` 用来防止新研究复用数据、文献和停止路线；证据包供同事独立查看一轮运行的方案、代码、决定和数值记录。展开证据包不会导入研究记忆、创建预留、恢复进程或执行源码。

## 发送方

在源码目录中，用基础Python导出一个已通过只读审计的原始运行目录：

```sh
python3 -m research_harness study export --run runs/my-study --out /existing/path/my-study.evidence.json
```

export 先审计原始产物，再复制选定文件，在临时目录重新审计副本，并检查复制期间源文件是否变化。只有全部通过才独占创建输出文件，默认权限为仅本人可读写。已有文件、损坏/缺失或不一致的证据、符号链接、变化中的快照、超量内容都会拒绝。不会自动修复或重试研究。

一致的有效负结果、CONTINUE、测量无效STOP、注册前REJECTED都可以导出；这不改变各自科学含义。不完整运行不能用该命令包装成完成的审查包，原始记录仍应保留。

## 接收方

在有本项目源码的机器上，无需模型账号、研究依赖或图像资产：

```sh
python3 -m research_harness study verify /path/to/my-study.evidence.json
python3 -m research_harness study unpack /path/to/my-study.evidence.json --out /existing/path/review-copy
python3 -m research_harness study audit --run /existing/path/review-copy/run
```

verify 检查闭合模式、版本、逐文件及整包哈希，再在私有临时目录独立运行当前只读审计；不信任发送方的旧workflow或审计成功标志。校验与审计都通过时退出0，语义不一致或包损坏时退出1。语义失败的包即使哈希正确，也不能通过unpack。

unpack 拒绝任何已存在的目标；新建私人容器，先在 `.pending` 写齐文件，再发布 `run/` 子目录。返回的run路径可直接用于study status/audit。`receipt.json` 在run目录外保存包哈希与逐文件哈希，原文件字节保留。普通写入失败会清理本次独占创建的容器，已有目录不会被覆盖或清理。进程强杀可能留下未完成容器；写齐前不会发布run目录。导出进程被强杀也可能留下不完整的包文件，verify会拒绝，命令不会自动覆盖它。

包的sha256是`core.digest(payload)`的规范化JSON内容哈希；文件sha256对应各文件的UTF-8字节。相同文件的再次导出得到相同payload哈希，即使接收目录不同。保留原包或通过独立可信渠道交换该哈希，后续审查副本若有改动，可以重新导出并与原哈希比较。收据本身不是数字签名。

## 格式和选取范围

版本1是JSON envelope：`payload`含kind、version和files，顶层另有sha256。每个files项仅含content和sha256。只允许下列平面文件名，不提取ZIP，不跟随包内任何外部路径：

- result.json、session.json、ledger.jsonl、agent-REPORT.md、search-records.json
- registered.json、candidate.py、agent-candidate.py、agent-research.json
- intervention-review.json、observations.json、workflow.json、REPORT.md

具体终止路径可以没有某些文件，但仍须通过完整审计。每文件最多4 MiB、合计原始内容8 MiB、编码后整包16 MiB；不默默截断。未知字段/版本、重复JSON键、路径穿越、绝对路径、非白名单文件名、错误哈希和超量内容都会被拒绝。

不会自动收集auth.json、原始模型事件、完整论文、图片、输出数组、权重、环境或任意附件。**白名单不是脱敏器**：代码、报告或账本中仍可能有人手写的密钥、公司知识、个人信息或原始路径。发送前检查全文、决定分享范围。包没有加密，也不自动发送到第三方。

## 能证明什么

哈希检查完整性，不认证发送者；一致的文件可能仍是错误或伪造的科学记录。包内源码只当文本，不导入或执行。审计仅从已保存的逐图数值重算统计量，不重新评分图像，也不足以复现完整实验。没有论文全文、原始模型日志和数组，所以这不是全部原始证据的归档替代品。

`audit_ok`不证明候选新颖性、模型实际执行、文献阅读真实性或科学成功。修改整套文件后重新计算全部哈希的攻击者不能被无签名格式认证出来。接收方需要信任交接来源，必要时要求额外原始产物或人工复核。

验证依据见 [证据交接验收](EVIDENCE_HANDOFF_VALIDATION.md)；所有新增验收都是平台软件测试，没有新增科研实验、调参、图像评分或研究模型调用。
