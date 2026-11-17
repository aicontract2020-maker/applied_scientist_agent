# C12 工程验收：Airfoil 私有证据交接

2026-11-17，0.30.0，**AWAITING_ENGINEERING_REVIEW**。C11 已由用户验收，
其原提交在 [macOS 15 Intel / Python 3.12 定向补验](https://github.com/aicontract2020-maker/applied_scientist_agent/actions/runs/44146265622)
通过：原 130 项兼容检查无跳过，额外完整集 307 项、6 项可选依赖跳过。
原 ARM 任务重跑后仍因容量不足被取消，未执行测试；不计作 ARM Python 3.12 远端通过。

## 本次交付

- `airfoil evidence export/verify/unpack` 支持固定 Airfoil 已完成候选及其完整
  已通过基线，私有清单、大小限制、逐文件/整包摘要及可信独立复算。
- 候选和内嵌基线均只读。复制的历史批准不能用于活动加载、准备、批准或执行；
  原历史审计仍可用，STOP 仍是可交接的终局结果。
- 统一记忆 v3 独立保留。证据不导入记忆、不新增执行权限、不释放数据；
  任何后续研究继续需要完整资格、预注册、独立批准和原停止规则。
- 定向 macOS 补验固定完整提交 SHA；常规四组矩阵改用标准 macOS 15 Intel
  池，保留 Python 3.10/3.12 和全部检查。本机 macOS ARM 的完整环境及实际
  隔离仍独立验证，不把 Intel 结果表述成 ARM 结果。

操作方式及权限/真实性边界见 [使用说明](AIRFOIL_EVIDENCE.md)。

## 验证记录

新增 13 项软件检查。本地 macOS ARM / Python 3.12 完整环境 **320 项全部通过**；
Python 3.10 完整集 320 项、16 项因固定 3.12 审计或可选依赖跳过。实际 macOS
隔离合成流程通过，包含完整证据往返审计、两个层级的活动入口拒绝以及占用保留。
研究配方、评价/审计/执行函数的语法树与上一版一致；隔离、分区、工作进程、
统一交接与真实任务文件保持原样。[结构化验证记录](airfoil-evidence-validation/validation.json)。
[远端同一代码提交 `405aead` 的五项任务全部通过](https://github.com/aicontract2020-maker/applied_scientist_agent/actions/runs/44147687838)：
Linux/macOS Intel × Python 3.10/3.12 四组兼容检查（每组 143 项，3.10 版本
跳过 7 项固定 3.12 审计）；Linux x86_64 从零安装、320 项完整测试无跳过、
实际内核隔离、预注册拒绝以及四套基线/候选合成流程。Airfoil 证据往返审计和
导入批准拒绝也在 Linux 实际隔离中通过。[远端记录](airfoil-evidence-validation/remote-validation.json)。
仅合成软件记录及实际隔离合成流程；没有
新的研究实验、真实 A1/A2 数据评分、真实证据包导出、研究模型调用或外部复现。

## 请审查

接受这一工程边界：**私有完整记录可离线复算；导入批准仅供查看；停止与占用
另行保守交接；完整性不等于真实性或执行许可**。验收本功能不批准新的研究。

SR 预留迁移、通用任务适配、跨机器实时协调、Delft 数据资格及 D1 人类效率
对照仍未完成；本次不宣称研究能力或商业效果已经得到新的实证支持。
