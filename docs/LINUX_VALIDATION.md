# Linux 验证记录

日期：2026-11-04（America/Toronto；原始 UTC 日志已跨到 11-05）。协议先于模型调用记录于 [LINUX_VALIDATION_PROTOCOL.md](LINUX_VALIDATION_PROTOCOL.md)。

结论：**Ubuntu 24.04 ARM64 的独立安装、实际隔离和一次完整自主研究流程通过。** x86_64 Ubuntu CI 通过 CPU 安装、最终 70 项软件测试、实际 namespace/文件/网络探针及离线流程；CI 不使用真实登录、不调用研究模型，不能冒称 x86 上也完成了同一次真实研究。

## 环境与边界

本机新建独立 Lima Linux VM：4 vCPU、12 GiB RAM、24 GiB 虚拟盘，**没有挂载 macOS 目录**。公开源码候选通过 Git bundle 在 Linux 全新 clone 到含空格的路径；VM 自己建立 venv 并重新下载模型/数据，没有复用 Mac 环境。Python 3.12.3、Linux 6.8.0-106-generic、aarch64、普通 uid=501、Bubblewrap 0.9.0、CPU torch 2.8.0+cpu / torchvision 0.23.0。

真实研究执行提交 `c003af6`，执行源码和全部隔离参数已归档。最终额外增加无凭据 CI/隔离内 CLI 版本检查、文档及本轮 STOP/数据登记，未重跑科学候选。

研究前的软件有效性修复全部在任何模型调用/图像评分之前完成：

1. 官方 ARM torchvision 0.23 CPU wheel 没有 x86 的 `+cpu` 后缀，采用单独锁文件。
2. 该 Ubuntu 镜像缺少 bwrap AppArmor profile，uid map 被拒绝。仅安装管理员审查的 `/usr/bin/bwrap` userns profile；全局 `kernel.apparmor_restrict_unprivileged_userns` 仍为 **1**，没有关闭 AppArmor、使用 setuid 或 root 运行研究。
3. Doctor 将 Linux EROFS 识别为真实只读拒绝；同时禁止 actor 在私有 `/tmp` 额外写入，把临时文件置于任务目录。

探针实际确认：repo/控制文件和符号链接逃逸不可读；响应、候选输入和外部文件不可写；候选可导入 numpy/cv2，但与主机网络命名空间不同且不能连接外网；两角色看不到主机控制器 PID；禁建嵌套 userns；隔离内 CLI 与登录可用。不是仅检验命令包含了 bwrap 字符串。Actor 为模型/检索仍共享网络，不是域名级出口过滤。

最终 Linux 版本还复验了安装幂等性、70 项软件测试、隔离内 CLI 和全部探针。暂时撤销本任务添加的 bwrap profile 后，`research` 在预留图像或启动 agent 之前返回 1；恢复许可后重复已关闭 ID 也返回 1，原账本摘要不变。没有第二次 agent/实验。见 final-checks.json、final-doctor.json；无凭据独立探针见 no-auth-probes.json。

## 完整自主周期

`research --id linux-validation-20261104` 自动冻结此前未评分的 12 张 Urban100 图像；门槛和强参考与 Mac 一致。Agent 自己搜索，读取 [Aitken 等的亚像素卷积棋盘伪影论文](https://arxiv.org/abs/1707.02937) 完整提取文本（此次未截断），以及 [Sugawara 等的无棋盘伪影超分论文](https://arxiv.org/abs/1806.02658) 摘要。

它提出的推断是：普通 SwinIR 输出若存在固定 2×2 像素相位亮度偏置，可用块均值残差的各相位中位数估计，去中心化后一次减去偏置。论文并没有证明本轮 SwinIR 后处理有效；这里是 agent 的新假设，区别于五条已 STOP 路线。代码、公式、指标与通过/失败/无效的决策含义先冻结，再运行。

| 指标 | 实际结果 |
|---|---:|
| 固定双次参考 PSNR-Y | 33.628299 dB |
| 候选 PSNR-Y | 33.506719 dB |
| 平均配对效应 | **−0.121580 dB** |
| 原图效应标准差 | 0.081866 dB |
| 95% 原图配对 bootstrap 区间 | **[−0.169112, −0.082569] dB** |
| 候选/参考延迟 | 0.503138 |
| 测量有效 / 科学决策 | 是 / **STOP** |
| 流程完成 / CLI 退出 | 是 / 0 |

一个合成检查、一次注册、一次真实实验，12/12 相对参考为负；无调参、重跑或额外消融。停止相位偏置校正路线，已将新 STOP、文献及本轮图像纳入公开模板。累计 48 张 Urban100 原图已评分，不再作为新留出集。

该对照同时改变推理次数与后处理，不能单独归因于相位校正本身，也没有证明原模型是否存在该偏置。Bootstrap 是 12 张原图上的 10,000 次重采样，不是训练重复。

## 成本与留存

会话 173.650 秒，实验子集 51.585 秒；按 $1/机时代理分别为 $0.048236 与子集 $0.014329，不相加、不等于账单。Tokens：input=429729、cached=404352、output=5458、reasoning_output=734。实际默认模型标识与美元账单未知。

环境/资产/运行/临时会话逻辑文件约 989,033,207 bytes；按全会话驻留粗估约 47.71 MB-hours。候选峰值 RSS **83,009,536 bytes**（Linux ru_maxrss 的 KiB 已换算），参考峰值未计量。两篇论文成功下载 3,425,707 bytes。VM 镜像、系统/npm/pip 设置时间、网络开销、CI 账单、电费折旧和长期证据保留未完整计价。无训练、参数扫描或云 GPU。

Git 仅保存 [linux-evidence](linux-evidence/) 的协议、候选、逐图分数、原始 agent 报告、来源/原始大日志哈希、运行时版本和隔离策略。原始 PDF/数组/大日志另有本机私有镜像，不发布全文或大图像。临时 VM 凭据不在导出范围内；验证后删除临时凭据并停止 VM。

x86 CI：[成功运行](https://github.com/aicontract2020-maker/applied_scientist_agent/actions/runs/41940003397)，结构化状态及探针摘录已归档；没有冒用模型登录或把 CI 合成检查当科学证据。macOS Seatbelt 的真实读写/网络探针及 67 项软件回归也通过。

## 适用范围

这是允许 rootless userns 的 Ubuntu/Linux 安装验证，不是任意 HPC、Docker/Kubernetes 策略或全部发行版的认证。拒绝运行的受限主机须由管理员评估，不绕过隔离。只读系统/运行时挂载与专用 Codex 凭据仍在 actor 可见范围，网络未按域名封闭；这不是多租户恶意代码服务或整个主机秘密的形式化保证。单次完整流程也不证明科研可靠性、算法进步或商业价值。
