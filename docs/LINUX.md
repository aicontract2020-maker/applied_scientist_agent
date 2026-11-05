# 在 Linux 服务器上运行

目标环境：Ubuntu 24.04、Python 3.12、普通用户、x86_64 或 aarch64、CPU 推理。完整实跑与支持范围见 [Linux 验证记录](LINUX_VALIDATION.md)。其他发行版、受限容器或 HPC 环境必须自行通过 `doctor`，不承诺默认可用。Linux 使用 Bubblewrap 用户、挂载、PID 与网络命名空间；不使用无隔离 subprocess 回退。

## 管理员一次性准备

Ubuntu 24.04 示例，安装系统依赖时才用 sudo：

```sh
sudo apt-get update
sudo apt-get install -y python3.12-venv git bubblewrap poppler-utils nodejs npm ca-certificates
```

项目在 Bubblewrap 0.9.0 上验证，要求支持 `--disable-userns`、`--assert-userns-disabled`。主机必须允许普通用户建立命名空间。不要以 root/sudo 运行 bootstrap 或研究进程。

某些 Ubuntu 镜像缺少 bwrap 的 AppArmor userns 许可，会报 `setting up uid map: Permission denied`。先请管理员检查已有策略；**不要关闭 AppArmor、全局修改 userns 限制或给 bwrap 设置 setuid 来绕过**。仓库提供仅附着于 root-owned `/usr/bin/bwrap` 的 [示例策略](linux/bwrap.apparmor)，依据 [Ubuntu 官方说明](https://documentation.ubuntu.com/release-notes/24.04/#unprivileged-user-namespace-restrictions)。经管理员审查且确认没有冲突的已有策略后，可以安装：

```sh
sudo install -m 644 docs/linux/bwrap.apparmor /etc/apparmor.d/research-harness-bwrap
sudo apparmor_parser -r /etc/apparmor.d/research-harness-bwrap
```

该文件给 bwrap 创建 userns 的权限，不是文件访问控制本身；真正的工作区、输入和网络限制由本项目构造的命名空间实现。bootstrap 不会自动改系统策略。管理员不允许 userns、seccomp 阻止 namespace 或容器策略不兼容时，本项目会在调用模型之前拒绝运行。不要改成特权容器来跳过检查。

## 同事自己的账号和安装

```sh
git clone https://github.com/aicontract2020-maker/applied_scientist_agent.git
cd applied_scientist_agent
npm install --prefix "$HOME/.local" -g @openai/codex@0.144.0
export PATH="$HOME/.local/bin:$PATH"
export CODEX_HOME="$HOME/.codex-research"
install -d -m 700 "$CODEX_HOME"
codex -c 'cli_auth_credentials_store="file"' login --device-auth
bash scripts/bootstrap.sh
.venv-sr/bin/python -m research_harness doctor --network
.venv-sr/bin/python -m research_harness research --id my-first-linux-study
```

在本地浏览器完成 device-code 登录；账号须有相应访问和用量权限。命令依据 [OpenAI 认证说明](https://developers.openai.com/codex/auth)。如组织不允许 device-code 登录，按组织的认证方式准备自己的文件型 CLI 登录状态，仍需通过隔离内登录检查。不要共享他人的 auth.json。后续 SSH 登录应设置同样的 PATH/CODEX_HOME；不要把凭据放进 repo。CODEX_HOME 必须与 checkout、控制目录和任务目录互不包含，避免凭据挂载形成隐藏数据的别名；程序会拒绝这种配置。自定义 CA 文件也应放在 checkout/控制/任务目录之外。

CPU 安装遵循 [PyTorch 2.8 官方 CPU 源](https://pytorch.org/get-started/previous-versions/#v280)。为避免拉取 CUDA，bootstrap 先从 CPU 源安装 torch/torchvision，再按平台完整约束安装依赖。x86_64 的 torchvision 为 `0.23.0+cpu`，aarch64 的该官方 CPU wheel 为 `0.23.0`；因此有两个 Linux lock 文件，不能拿 macOS lock 强行覆盖。

## 实际隔离边界

- Actor：只挂载只读系统/运行时、任务目录及专用 Codex 状态目录；repo/HR/控制目录不暴露，控制器响应只读。临时目录位于任务工作区。
- 候选：只读 Python 环境、冻结代码、输入和可信适配器；只能写输出；清空环境变量、移除 capabilities、隔离 PID、禁止再建 userns，并使用无外网路由的独立网络命名空间。
- `doctor` 真正尝试读取隐藏数据、符号链接跳转、修改响应/输入、越界写入、联网和访问主机 PID；也在 actor 内运行 CLI 版本/登录检查。只有安装 bwrap 或检查命令字符串不算通过。
- Actor 为模型与检索仍共享主机网络，没有域名级出口限制；可访问挂载的 Codex 凭据。它不是对整个主机秘密或多租户恶意代码的形式化安全保证，不应开放成公网任意任务执行服务。

`python scripts/check-linux-isolation.py`（请使用本 repo 的 `.venv-sr/bin/python`）是 CI/管理员的无凭据内核探针，仅检查隔离和 CLI 运行，不检查真实登录、资产或科学能力，不能替代完整 `doctor`。

预注册、强参考、12 张新留出图、+.05 dB/置信区间/延迟门槛、单次实验与 STOP 规则与 macOS 共用；不因服务器更快就允许扫参。输出仍为 `runs/ID/REPORT.md`，重复 ID 拒绝执行。Linux 峰值 RSS 已从内核的 KiB 转为 bytes，不能直接照抄 macOS 单位。

会话和子进程时限不是服务器调度/内存 cgroup 配额或模型美元预算。首次环境安装与下载时间不计入实验会话；实际模型账单仍可能未知。若研究进程中断或测量失效，检查已有账本并记录原因，不自动重试。
