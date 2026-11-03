# G1：首次真实规划与推理改进对照

本目录保存一次真实模型规划，以及由其选定、在结果前预注册的图像推理对照。
本轮已完成并判定 STOP：平均增益 0.01472 dB，低于预注册的 0.05 dB。
完整报告见 `REPORT.md`；原始证据见 `evidence/`。

## 文件

- `planner-request.json`：调用前规定的一次规划检查及停止条件。
- `BRIEF.md`：传给规划器的完整研究范围、既有方法短名单、指标、预算和全部图像 ID。
- `planner-response.json`：真实返回的结构化方案，不是 fixture。
- `planner-provider.json`、`operator-audit.json`：适配器信息、实际 token 用量和约束核查。
- `data.lock.json`：BSD100/Set14 原作者仓库提交、全部 HR/LR 文件哈希。
- `protocol.json`：结果前注册的 G1 协议，固定两次前向的水平翻转平均。
- `execution.lock.json`：执行代码、指标、数据、权重与统计决策代码的哈希。
- `worker.py`：只读 LR 图像做双臂推理，按图像交替次序，保存 PNG 与计时。
- `evaluate.py`：全部预测保存完成后，另起进程读取 HR 和 PNG，计算原图级指标。
- `REGISTRATION.md`：易读的预注册审查材料与完整限制。

## 能证明什么

这一轮检查一条受约束的流程：真实模型在给定的两项现有工程方案中选一个，
协作者检查并实现它，冻结实验，再由固定评价规则作决策。
即使成功，也不是开放式科研、新算法发现、独立代码生成或完整职位替代的证明。
失败则是这个干预在已声明采用门槛下的最终负结果，不能靠追加尝试补救。

## 运行方式

准备与冻结脚本使用排他写入，当前实例已经注册，不得覆盖后重新运行：

```sh
.venv-sr/bin/python -m research_harness evaluate swinir-g1-inference
```

原始模型 stdout/事件在本机 `proposals/swinir-g1-p1/`，默认不提交 Git。
官方模型、第三方源码、数据、缓存、依赖和 PNG 预测均保留本地，不随代码提交。

## 数据与推论边界

Set5 仅作 G0 复现，未作为 G1 的候选选择数据。G1 对全部 BSD100 做一次预定比较，
未使用 Set14 试探参数。数据公开，无法保证模型从未见过这些图像；目录权限也没有
隔离 HR。图像 bootstrap 仅反映本 benchmark 原图抽样的不确定性，不能替代跨领域
复现、独立训练或真实用户价值验证。

代码依据：[SwinIR 官方项目](https://github.com/JingyunLiang/SwinIR)。
图像来源：[SelfExSR 原作者仓库](https://github.com/jbhuang0604/SelfExSR)。
