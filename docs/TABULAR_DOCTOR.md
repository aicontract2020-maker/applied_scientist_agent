# Abalone / Airfoil 安装诊断

0.34.0 为两类固定表格任务提供独立诊断，不再要求先安装超分图像资源或
登录 Codex。它只检查**已冻结基线/候选的 worker 执行环境**，不检查研究
材料、数据资格、批准或停止记忆，也不启动自主提案 actor。

## 最小安装与检查

在仓库根目录操作。固定执行环境仍为 Python 3.12、CPU，以及受支持的
macOS Apple Silicon 或 Linux x86_64/aarch64。

```sh
# 创建/补齐固定表格环境；不下载研究数据、不训练。
bash scripts/bootstrap-tabular.sh

# 默认仅检查安装。两个入口使用同一套诊断。
python3 -m research_harness tabular doctor
python3 -m research_harness airfoil doctor

# 可选：显式运行一次原生合成隔离探针。
python3 -m research_harness airfoil doctor --probe-isolation
```

诊断命令的控制端支持 Python >=3.10；实际被检查的是当前安装所在仓库的
`.venv-tabular/bin/python`，必须为固定 Python 3.12 环境，与原执行器一致。
不会使用 PATH 中偶然找到的其他 Python，也不会解析符号链接后丢失 venv。

Linux 普通用户需要 Bubblewrap。这里只运行固定 worker，不需要 SR 的
PyTorch、Urban100、Node、poppler 或 Codex 登录。主机用户命名空间与
AppArmor 等设置仍须满足[原 Linux 隔离要求](LINUX.md)，诊断不会自动改
系统策略。Abalone **自主提案**仍需要自己的 Codex 和 actor 环境；该部分
不在这项诊断的通过范围内。SR 仍使用原顶层 `doctor`。

## 输出与含义

| 结果 | 含义 |
|---|---|
| `ENVIRONMENT_CHECKS_PASSED` | 受支持平台、解释器、原生版本锁、科学库导入和隔离工具检查通过；没有验证实际隔离 |
| `ENVIRONMENT_AND_ISOLATION_CHECKS_PASSED` | 上述检查及一次原生合成内核探针通过 |
| `BLOCKED_ENVIRONMENT` | 至少一个必要检查未通过，报告逐项原因和处理建议；不启动研究 |

每项包含 `PASS` / `FAIL` / `SKIPPED` / `NOT_REQUESTED` 状态。默认成功
时 `ok` 为 true、退出码为 0，但 `isolation_verified` 为 false。显式要求
探针后，只有探针通过才能整体成功；失败退出码为 1，不自动重试探针。
前置检查失败时跳过探针，并明确区分“没有请求”“无法运行”和“运行失败”。

`execution_authorized` 始终为 false。诊断通过不创建批准、预留、实验、
运行目录或新研究结果。数据资格、材料完整性与当前约束应另用已有
[`task check`](WORKFLOWS.md)；真正执行仍在原锁内核对材料和批准，再次
测试隔离，保持预注册、单次实验与停止规则。

默认诊断仅运行固定解释器的版本查询和科学库导入，不拟合或生成预测，
不联网、不安装、不读研究数据。显式探针使用原来的隔离函数，临时生成
合成秘密与输入，验证私有标签/仓库读取被拒、输入只读、输出可写和网络
连接被拒；会尝试一次应被拒绝的连接，完成后清理临时目录。它不是研究
实验，也不代表整台主机或多租户环境的安全认证。

## 验证范围

单元检查用虚构运行时覆盖成功、缺失、错误版本、导入失败、解释器身份、
不支持平台、Linux root、缺隔离工具、失败/不完整探针、CLI 与无研究状态
写入。macOS 与 Linux 使用实际内核探针验证成功路径。具体结果见
[C16 工程验收](TABULAR_DOCTOR_REVIEW.md)。
