# 0.14.0 证据交接验收

2026-11-05，测试实现提交 `d79291d`。本轮只验证平台软件和历史证据交接，没有调用研究模型、重新评分图像、消耗新留出图或改变任何停止决定。

## 软件检查

| 环境 | 结果 |
| --- | --- |
| macOS，项目 `.venv-sr` | 109 个测试通过 |
| macOS，基础 `python3` | 109 个测试运行，4 个研究依赖相关测试跳过，其余通过 |
| Ubuntu 24.04 ARM64，项目 `.venv-sr` | 109 个测试通过 |

新增 11 个证据包测试覆盖有效负结果、CONTINUE、测量无效 STOP、注册前 REJECTED、逐文件和整包哈希损坏、重算哈希后的错误决定、未知字段/版本、重复键、路径穿越、符号链接、大小限制、已有输出保护、变化中或不完整源目录、部分写入失败清理，以及携带的 Python 源码不被执行。测试使用合成记录，仅证明软件行为。

## 历史 G7 的 macOS → Linux → macOS 交接

1. macOS 用基础 Python 从历史 G7 原始镜像导出并验证证据包。
2. 将包和实现提交传入 Lima `rh-linux-validation`；该 Ubuntu ARM64 虚拟机没有宿主目录挂载，本轮没有复制模型登录。
3. 在 Linux 用 `git archive HEAD` 展开一个仅含源码的干净目录，以系统 `python3.12` 执行 `study verify`、`study unpack`、`study audit` 和再次 `study export`。
4. 该系统解释器检测结果为 `numpy=false`、`cv2=false`、`torch=false`；干净目录没有实验资产，`$HOME/.codex-research` 不存在。
5. 取回 Linux 再导出的包，在 macOS 比较完整解析后的 envelope：完全相等，13 个文件的文本内容、逐文件哈希和 payload 哈希均一致。
6. 验证虚拟机已停止。

两端 payload SHA-256：

```text
748f6035b65ffe8694b903588faee5f45ff5ff7691e0896bdd6acae6a8c3e798
```

Linux 独立校验与展开后审计均为 `audit_ok=true`；历史 G7 仍为测量有效的 **STOP**。这是从保存的逐图数值重新核对原有决定，没有重新执行候选代码或测量效果。

机器可读摘要见 [acceptance.json](evidence-handoff-evidence/acceptance.json)，Linux 独立校验原始输出见 [linux-verify.json](evidence-handoff-evidence/linux-verify.json)。不把完整证据包复制进本次文档目录；原始研究记录仍应单独保留。

## 边界

哈希一致与只读审计通过不能认证发送者、证明原始模型实际执行或证明科学成功。本次实机交接验证了 macOS 与 Linux ARM64；Linux x86_64 由仓库的 Linux CPU and isolation checks 工作流验证软件测试与隔离探针，不能视为同一次历史 G7 实机交接。使用方式与分享范围见 [EVIDENCE_HANDOFF.md](EVIDENCE_HANDOFF.md)。
