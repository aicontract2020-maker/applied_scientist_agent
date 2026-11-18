# Airfoil 私有证据交接

0.30.0 提供已完成 Airfoil 候选及其基线的固定证据包。接收者使用本地可信
评价器离线复算历史预测，不训练、不重新预测，也不运行包内的 Python 文本。
只支持当前固定 Airfoil 任务；无效或未完成测量不能伪装成完整证据导出。
有效 STOP 与 CONTINUE 均可交接，结论原样保留。

使用已安装的 Python 3.12 环境；完整性检查和复算不需要模型服务或额外科学
依赖。包内包括训练数据、留出标签与预测、批准文字及历史代码，默认是私有材料。
请使用受控私有路径，是否能分享仍需单独核实数据与文字的使用权限。

```sh
.venv-tabular/bin/python -m research_harness airfoil evidence export \
  --review /absolute/private/completed-trial --out /absolute/private/airfoil-evidence.json
.venv-tabular/bin/python -m research_harness airfoil evidence verify \
  /absolute/private/airfoil-evidence.json
.venv-tabular/bin/python -m research_harness airfoil evidence unpack \
  /absolute/private/airfoil-evidence.json --out /absolute/private/new-received
```

输出路径不得已存在；输入及输出路径不接受符号链接。macOS 上 `/tmp`、`/var`
可能是系统别名，请使用其真实路径（例如 `/private/tmp`）。解包先校验和复算，
再创建私有目录，最终记录在 `new-received/review`，另附回执。文件权限 0600、
所建目录 0700；写入失败清理本次新目录，已有目录不动。

固定清单包含候选冻结、批准、运行输入、预测、结果、事件、环境/隔离与必要
源代码，以及内嵌基线的同类材料。真实来源额外包含固定原始数据；合成来源
不能附加该文件。额外日志、任意附件和路径不导出。每文件最多 4 MiB，内容总计
16 MiB，JSON 包最多 32 MiB；重复键、非有限值和超过 64 层嵌套拒绝。

候选及内嵌基线都有 `EVIDENCE_ONLY.json`。活动加载、批准、执行前检查、执行
和以该基线准备新候选均拒绝；只读 `airfoil audit-trial` / `airfoil audit`
仍可使用。即使删掉外层标记，内嵌标记仍拒绝活动加载。标记防止正常入口误用，
不是对能任意修改本地文件的人的强制安全边界；包无签名，`authenticity` 始终
为 `UNVERIFIED`，自洽的记录不证明远端真的执行过或取得许可。

**证据包不导入停止记录和数据占用，也不授予执行权。** 同事继续任何活动工作
前，另用 [统一交接 v4](SR_UNIFIED_HANDOFF.md) 与 [只读预览](HANDOFF_PREVIEW.md) 合并全部已知约束。证据接收
本身不释放预留、不解除数据暂停、不重开失败路线，也不消费新的留出。

历史审计仍要求固定研究配方和原评价规则；旧材料不因缺少新资格字段失去只读
复核能力，但旧批准不能变成新执行批准。当前没有通用 Airfoil 自主 actor、
新数据 adapter、在线身份认证或跨机器实时协调。
