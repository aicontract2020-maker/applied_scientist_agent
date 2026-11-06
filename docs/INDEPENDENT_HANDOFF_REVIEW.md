# C3：独立同事交接验收 — 用户确认通过

2026-11-06，用户在收到 0.19.0 交付与本方案后明确回复“验收通过”。项目据此记录 C3 为 **PASS（用户确认）**，交付版本为 `bf832f6dbdce593cd4e154fc11e1acbffb4c052e`。

证据来源是用户确认；本会话未收到接收端日志、参与者身份、实际使用的包或耗时/成本记录，不补写这些细节，也不把维护者测试标为独立用户数据。此结论不授权新的科研实验，不证明算法收益、普遍独立运行成功率或替代 Applied Scientist 的商业价值。下面保留原验收方案及其通过/失败条件。

## 为什么需要一位独立使用者

目前作者会话已在 macOS/Linux 完成软件测试和真实 T2 证据的离线交接检查。这能验证实现，却无法证明没有项目背景的同事能仅靠文档独立完成交接。该结论需要真实使用者，不能用本会话重复脚本冒充。

建议选一位未参与实现、具有普通 Python/Linux 使用经验的同事，在自己的 Linux 非 root 账户和新 clone 下执行。先使用**合成软件包**，无需共享真实数据、论文全文、账号或用户审批记录。合成包可由以下命令独立生成：

```sh
bash scripts/bootstrap-tabular.sh
.venv-tabular/bin/python scripts/check-tabular-trial.py --export-fixture /path/to/new-synthetic-handoff
```

本次已生成一套本地合成包供交接；不要求同事在接收端重新训练。包中论文 URL 是格式 fixture，内容明确标为虚构的软件测试材料，不能作为文献证据。真正 T2 的私有证据另行保留，如需向第三方分享，须明确接收人和允许的数据范围。

## 冻结的验收任务

交付指定仓库提交、两份合成 JSON 包及本页。同事只按文档完成下列步骤，原始结果记录不改写：

```sh
git clone https://github.com/aicontract2020-maker/applied_scientist_agent.git
cd applied_scientist_agent
# checkout 交付时明确指定的提交
bash scripts/bootstrap-tabular.sh
.venv-tabular/bin/python scripts/check-tabular-handoff.py \
  --packet /path/to/synthetic-evidence.json \
  --memory /path/to/synthetic-memory.json \
  --out /path/to/new-receiver-folder
```

接收端只读取记录、重算既有预测的统计量、导入排除记录、检查已消耗数据被拒绝以及旧审批不可执行。没有模型服务调用、训练、推理或新留出评分。

## 预先写明的决定

工程假设：同事可以在规定环境中，独立获得与已验证包一致的审计/排除结果。参考是同版本在维护者 macOS/Linux 环境已通过的检查；这不是相对人工研究员的效率对照。

主要验收条件：所有检查通过、没有修改源码/包/停止规则、没有维护者提供未写在交付文档中的步骤。通过才允许把“同事可独立交接”记为已验收。任一条件失败即本次 FAIL，保留首个失败点；不得现场口头修补后把同一次结果改记为 PASS。

同时记录安装总耗时、操作耗时、求助次数、下载/磁盘开销及环境信息。它们用于定位工程摩擦，暂不设“节省多少人工时间”的成功门槛，因为尚无可信的人工对照数据。样本只有一位同事，PASS 也仅是最小可用性交接证据，不代表普遍成功率。

Python 必须为冻结的 3.12。机器/网络不满足已列前提时记录 NOT_RUN 和原因；执行中失败记录 FAIL。修复产生新版本后，可另立一次有编号的工程验收，不能覆盖首次失败或把软件重测说成科研路线继续。

## 原审查范围与后续

原方案要求明确参与者与合成包选择；用户已确认验收通过，具体参与记录仍未附在仓库中。未来若分享真实 T2 私有包，仍须明确接收人和资料范围；本次通过不扩大资料分享授权。

下一步为 [D1 研究价值评测设计](RESEARCH_VALUE_REVIEW.md)，需要明确业务问题、强相关对照和新的独立数据；不能继续用已消耗的 Abalone 留出筛选候选。
