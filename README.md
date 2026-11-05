# ResearchHarness

一个可审查的 Applied Scientist agent 研究原型：agent 自己查论文、提出一个可证伪假设、写代码、冻结方案、请求执行一次实验，并按预注册门槛报告 STOP / CONTINUE。负结果是最终输出，不自动调参或换候选补救。

当前完整任务是 **固定 SwinIR-S ×2 图像超分的确定性后处理研究**，不是任意领域的通用科学家。基础工作流无需模型；完整研究使用你自己的 Codex 登录与额度。

0.15.0 开始分离任务接口：超分保留完整自主流程；新增的表格回归仅支持固定预测的可信数值评价和合成演示，尚不能自主查文献、训练或运行候选。查看 [研发路线图](docs/ROADMAP.md) 和 [任务接口](docs/TASK_CONTRACTS.md)。

```sh
python3 -m research_harness task list
python3 -m research_harness task show tabular-regression
python3 -m examples.tabular_demo.workflow --out runs/tabular-software-demo
```

演示先冻结方案和输入哈希，再评价并写入 STOP 账本；所有数据、时延和成本都是软件 fixture。`research --task tabular-regression` 会在环境检查和数据预留前拒绝，不会退回无隔离执行。

最近一轮 [G7 Linux研究与审查记录](tasks/image_super_resolution/g7/REPORT.md)：新机制审查通过，几何校正候选有效负结果，按规则 STOP；未调参重跑。

## 注册前干预审查

新建研究会先冻结首次提交的方案与代码，再检查历史实现指纹（包括改数值的重试）、隔离合成输入经过实际裁剪/量化后的输出变化，并由独立隔离的模型审阅机制是否重开任何已停止路线。拒绝或无法确认时关闭本轮，记录 `REJECTED / NOT_RUN`，不注册、不推理、不评分、不换候选。通过后仍只允许一次留出评估，原成功门槛不变。

合成探针和模型审查不能证明任意程序在所有输入上的等价性；探针未观察到差异会保守拒绝。审查只接触方案、代码、历史路线与合成检查摘要，不接触留出图或分数。审查的时间、日志和模型用量单独保留；真实账单仍未知。详细边界与验证命令见 [干预审查](docs/INTERVENTION_REVIEW.md)。

## 支持范围

| 部分 | 支持情况 |
|---|---|
| 离线工作流、账本、协议与软件测试 | Python 3.10+；不调用模型 |
| 完整自主超分流程 | Apple Silicon macOS，或 Linux x86_64/aarch64 + Bubblewrap；Python 3.12、CPU |
| Windows / Intel Mac 的完整自主研究 | 尚未验证支持；不会降级成无隔离执行 |
| 安装方式 | 从源码运行，在仓库根目录执行命令 |

完整流程需要 git、`pdftotext`（poppler）、Codex CLI 和可访问 GitHub/arXiv/模型服务的网络。建议预留数 GB 磁盘；没有 GPU 要求。第一次安装会下载 PyTorch、上游代码、约 16 MB 权重及 Urban100 ×2 数据。第三方材料保留各自使用条款，仓库公开不等于获得数据或权重的商用授权。

## Linux 服务器

Ubuntu 24.04 的完整安装、无桌面登录、Bubblewrap/AppArmor 管理员配置见 [Linux 指南](docs/LINUX.md)。Linux ARM64 已完成一次真实自主检索/编码/预注册/实验/STOP 报告；x86_64 CI 已验证 CPU 安装、软件测试和实际内核隔离，不含真实模型登录/研究调用。见 [Linux 验证记录](docs/LINUX_VALIDATION.md)。两平台共用预注册与停止逻辑，无不隔离回退。

## Mac 同事首次安装

先安装 Python 3.12、poppler 与 Codex CLI。例如，已安装 Homebrew 的 Mac：

```sh
brew install python@3.12 poppler node
npm install -g @openai/codex
codex login
```

使用自己的账号完成浏览器登录，不共享开发者的凭据。安装/登录依据：[OpenAI Codex 官方安装说明](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex)、[认证说明](https://developers.openai.com/codex/auth)。本项目验证的 CLI 为 0.144.0；`doctor` 会检查实际所需参数是否存在，而不是假设所有版本都兼容。默认模型由 CLI 选择，当前不能保证跨账户规划结果一致。

```sh
git clone https://github.com/aicontract2020-maker/applied_scientist_agent.git
cd applied_scientist_agent
bash scripts/bootstrap.sh
.venv-sr/bin/python -m research_harness doctor --network
```

`bootstrap.sh` 创建仓库自己的 `.venv-sr`，安装 `requirements-sr.txt` 的直接依赖与对应平台 lock 的完整版本约束（macOS 为 `requirements-sr.lock.txt`），保存实际解析的完整环境列表，下载并核对固定上游提交和权重 SHA-256。不会读取原开发者的环境或复制其数据。已有文件不匹配时拒绝自动重置/覆盖。

找不到 Python 时，可指定解释器，例如 `PYTHON_BIN=/path/to/python3.12 bash scripts/bootstrap.sh`。脚本也支持 `--skip-assets`，但完整研究必须随后运行 `.venv-sr/bin/python -m research_harness setup-assets`。普通终端中 `doctor` 的所有检查都通过才继续。

## 与同事交接研究记忆

开始下一轮前可查看剩余数据，或导入同事的记录：

```sh
python3 -m research_harness memory status
python3 -m research_harness memory export --out /path/to/handoff.json
# 同事在自己的 clone 执行：
python3 -m research_harness memory import /path/to/handoff.json
```

新任务自动继承共享的已用/预留图像、已读文献和停止实现。导入完整校验后原子保存，冲突拒绝、重复幂等；拒绝/中断的研究不释放图像。包可能含假设和候选源码，分享前审查公司知识产权；不包含论文全文、图片、原始日志或凭据。详见 [研究记忆交接](docs/RESEARCH_MEMORY.md)。

这是离线快照交换；不同服务器没有实时锁。共享留出池时先交接再串行接手，不能让两个旧快照独立分配数据。当前发布历史已用84张Urban100原图，余16张，最多再容纳一轮12张研究；本地预留另扣。

## 启动一个完整自主周期

```sh
.venv-sr/bin/python -m research_harness research --id first-study
```

该命令依次执行：

1. 检查 Python/依赖、Codex 登录和参数、固定资产，以及实际 OS 文件与网络隔离；不通过则不调用模型。
2. 为新 ID 创建本机预注册任务，按 ID/文件名哈希固定 12 张新 Urban100 留出图；排除仓库历史、本机及已导入记忆中已用/预留图像。
3. 让 agent 实时搜索、读取至少两篇原始论文（至少一篇全文提取），引用至少一篇此前未使用的来源，再独立提出新机制和实现。
4. 最多三次合成形状检查；冻结方案和代码后进行注册前干预审查，通过才执行唯一一次真实实验；拒绝则记录 REJECTED / NOT_RUN 并结束。
5. 用独立评价器计算配对指标，保留原始报告、全文来源、数组、账本和流程检查结果。

论文全文提取可能只返回前 40,000 字符，截断会明确记录。模型调用可能消耗你的额度；真实美元账单未知，不会记为零。单次会话上限 20 分钟，参考推理 10 分钟、候选 90 秒；这些不是模型服务的美元消费上限，也不包含首次安装时间。

完成后打开 `runs/first-study/REPORT.md`。科学结果为 STOP 也可正常退出（0），表示完整流程结束；测量无效、缺少 agent 报告或流程不完整则退出 1。不要只看进程退出码判断科学成功。

通过标准固定为 **平均 PSNR-Y 增益 >=0.05 dB、10,000 次原图配对 bootstrap 的 95% 区间下界 >0、候选/参考延迟 <=2.5**。对照是固定双次翻转 SwinIR 参考，不是 bicubic，也不声称全球最强方法。CPU float32 四线程、权重、量化和裁边保持一致。确定性任务不用训练 seed 假装独立重复。

已关闭或已预留 ID 不覆盖、不自动恢复、不自动重跑。下一项研究要换新 ID、提供新外部证据，且不能修改已 STOP 路线的参数来重开。数据用完会拒绝继续，要求获得新数据并审查协议。同一 clone 的研究、建任务及记忆变更受本地锁保护；并发调用在预留和模型调用前报忙。进程退出释放锁，保留图像预留，不自动恢复研究。

## 查看进度与只读审计

```sh
python3 -m research_harness study list
python3 -m research_harness study status --run runs/first-study
python3 -m research_harness study audit --run runs/first-study
```

状态只显示已记录阶段，不猜测进程存活，也不恢复或重跑任务。审计核对冻结代码/方案、账本顺序和审查绑定，并从已存逐图分数重算统计量、核对全部采用门槛；不调用模型或重新评分图像。新 `research` 完成检查强制执行该审计，不一致就不能声称流程完成。`audit_ok` 表示产物一致，不代表科研成功；完整的拒绝/无效/负结果都应保留。详见 [状态与审计](docs/STUDY_INSPECTION.md)。

## 交给同事独立审查

```sh
python3 -m research_harness study export --run runs/first-study --out /existing/path/first-study.evidence.json
# 接收方，无需模型登录或研究依赖：
python3 -m research_harness study verify /path/to/first-study.evidence.json
python3 -m research_harness study unpack /path/to/first-study.evidence.json --out /existing/path/review-copy
python3 -m research_harness study audit --run /existing/path/review-copy/run
```

证据包携带白名单内的方案、源码、报告、账本和逐图数值；接收方重新审计，不能只信旧的成功标志。它不导入研究记忆，不执行源码、不恢复实验。不会自动收集原始模型日志、论文、图片数组或登录文件；文本仍需检查公司知识与敏感信息，哈希不认证发送者。详见 [审查证据交接](docs/EVIDENCE_HANDOFF.md)。

## 产物与历史

- `local_studies/ID/`：本机独立任务、冻结输入哈希、图像清单和环境检查。
- `runs/ID/registered.json`：不可复用到改过代码的冻结协议。
- `runs/ID/agent-REPORT.md`：agent 原始解释；`REPORT.md` 是控制器结果与成本摘要。
- `runs/ID/workflow.json`、`ledger.jsonl`、`observations.json`：流程审计、事件与逐图指标。
- `runs/ID/artifacts/`：下载论文、候选数组、参考日志与时序；不依赖临时目录存活。
- `.cache/environment.freeze.txt`、`assets/manifest.json`：实际安装环境及资产来源。

这些本地产物、环境、第三方数据默认不提交 Git。日志可能含输入文本；分享时自行选择允许公开的内容。不同同事的 clone 没有共享实时登记中心；跨机器接手前须使用 memory export/import 交接保守记忆。仅换 clone 不能把旧路线当新研究。

历史 G0 复现达到参考容差；G1–G4 候选均 STOP。见[决策账本](tasks/image_super_resolution/DECISIONS.md)、[G3](tasks/image_super_resolution/g3/REPORT.md)、[G4](tasks/image_super_resolution/g4/REPORT.md)。已纳入新任务模板的历史停止路线包括：集成、LR 残差回投、弱高频收缩、全局亮度对比度扩张、Mac 验证中未通过的保亮度色域压缩，Linux 验证中未通过的 2×2 相位偏置校正，以及 G5 未通过的 RGB 格点舍入。本机后续 STOP 和使用过的文献也会带入新任务。G7 的全图相位相关几何校正也已停止，合计八条科学停止路线；G6 空提案单独记录。历史目录是证据，不能作为可直接重跑的安装模板；不要修改其中旧哈希去迁就新环境。

## 不调用模型的演示与检查

```sh
python3 -m research_harness --help
python3 examples/local_demo/workflow.py
python3 -m unittest discover -s tests -v
```

Python >=3.10；纯 Python 环境会跳过依赖 torch/numpy/cv2 的合成软件测试。演示只用合成数据和保存的规划响应，不证明研究性能。它的输出目录不能覆盖，重跑请指定新路径：`python3 examples/local_demo/workflow.py --out runs/demo-2`。

完整环境中的软件测试：`.venv-sr/bin/python -m unittest discover -s tests -v`。安装和干净副本验证依据见[可移植性验证协议](docs/PORTABILITY_PROTOCOL.md)及[验证记录](docs/PORTABILITY_VALIDATION.md)。

## 常见问题

| 提示 | 处理 |
|---|---|
| Python/依赖版本不符 | 用 Python 3.12 在本 clone 执行 bootstrap；不要改历史 lock |
| `codex` 未登录或缺少参数 | 安装兼容 CLI，执行 `codex login`；不需要复制别人的 auth.json |
| `pdftotext` 缺失 | `brew install poppler` |
| `sandbox_apply: Operation not permitted` | 在正常 macOS 终端运行；某些容器/受限父进程不能嵌套隔离，不要关闭隔离绕过 |
| 下载/TLS/代理失败 | 修复网络/企业证书；不要关闭证书验证。中断下载若留下 `.download`，先检查并移走该不完整文件 |
| 资产提交或校验和不匹配 | 检查本地修改；程序不会 reset 或覆盖用户文件。新 clone 可重新准备 |
| ID 已存在、实验无效或未完成 | 查看该 ID 的账本、报告和错误；不删除目录来自动重试 |
| 科学结果 STOP | 接受并保留负结果，不调参救回；新研究须有新外部依据和不同机制 |

Linux 的 namespace/PID/只读输入/私有网络探针纳入了 [持续检查](.github/workflows/linux-checks.yml)。这不是研究模型能力评测，也不需要账号凭据。

## 权限与能力边界

这是本机研究原型，不是多租户执行服务。OS 隔离限制候选文件访问并禁止候选联网；独立控制器持有 HR 和评价逻辑。Actor 为模型与搜索保留网络，**没有域名级硬隔离**，也不是整个主机秘密的完整保密边界。不要部署成允许陌生用户提交任务的公网服务。

普通 `run` 执行器仅用于可信代码，不提供上述 OS 隔离。`research` 目前只支持源码目录下的固定 SR 任务，不支持自由训练、任意数据/模型切换、Windows 隔离或自动部署。静态检查、哈希和路线声明不构成形式化安全证明或不可篡改审计。

原图 bootstrap 不证明训练稳定性，公开数据也无法排除模型已知信息。一次有界自主流程完成不等于发现新算法、证明商业价值或替代 Applied Scientist 职位。

G5 已在 Linux 完成独立的新文献/假设/代码/单次实验周期：−0.10021 dB，保持 STOP，无调参或重跑。见 [G5 报告](tasks/image_super_resolution/g5/REPORT.md)，含原始 agent 报告中门槛摘要遗漏的审阅说明。

G6 在 Linux 执行后发现 agent 的 clip-only 候选重复了评价器已有步骤，**未满足新的实际干预要求，按方案失败停止**，未换候选或重跑。原始数值与自动流程记录保留，操作者审阅单列；见 [G6 失败报告](tasks/image_super_resolution/g6/REPORT.md)。未来提示明确原有裁剪/量化公式，拒绝此类空提案。G6结束时累计72张已评分；G7之后累计84张，后续请以 memory status 的合并记录为准。
