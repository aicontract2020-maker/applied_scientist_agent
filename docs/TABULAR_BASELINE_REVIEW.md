# 第二任务：Abalone 基线资格审查

状态：**已获用户审核并完成一次真实基线资格检查，HGB 通过**。中位数/Ridge/HGB 的验证 MAE 分别为 2.3538283 / 1.5698358 / 1.4852994；三个固定 seeds 预测一致，最终留出未评分。下文保留原审查范围与门槛，不授权重跑或后续候选研究。0.17 的 [T1 提案](../tasks/tabular_regression/t1/REPORT.md)已在评分前被解析上界拒绝。

## 待决定的范围

建议先用 UCI Abalone 验证第二领域的工程流程。目标是从物理测量预测 Rings；它不是付费行业需求的证据，也不是年龄/医疗决策系统。UCI 列出 4,177 条记录、8 个输入特征，许可为 CC BY 4.0；缺少站点、群组等标识，不能认证行独立性。[UCI 数据与许可](https://archive.ics.uci.edu/dataset/1/abalone)

归属：Nash, W., Sellers, T., Talbot, S., Cawthorn, A., & Ford, W. (1994). Abalone. UCI Machine Learning Repository. [DOI](https://doi.org/10.24432/C55C7W)。这里只做数据接口和基线准备，未声称数据能代表商业部署总体。

| 项目 | 提议及已准备内容 |
| --- | --- |
| 数据 | 固定 `abalone.data`，SHA-256 `de37cdcdcaaa50c309d514f248f7c2302a5f1f88c168905eba23fe2fbc78449f` |
| 特征处理 | Sex 固定 M/F/I 三列 one-hot，其余七列保留原数值；不做看分数后的清理或筛选 |
| 划分 | 特征向量哈希固定 60%/20%/20% 区间；实际训练 2,511、验证 862、最终留出 804 条 |
| 重复特征 | 相同特征整组进入同一分区；结构检查发现这份固定数据没有重复特征向量。这不证明统计独立 |
| 拟合 | 仅训练集标签；验证特征进入 worker，验证标签由控制器持有 |
| 最终留出 | 本阶段不挂载给 worker、不评分；仅存储及完整性校验 |
| 本轮研究决策 | 是否有一个合格的固定参考流程，值得起草后续候选研究协议 |

划分在任何训练和效果测量之前确定；结构检查没有计算目标分布、基线分数或候选分数。

## 固定基线与停止规则

比较三种预先指定的方法，不做超参数搜索：

1. 训练目标中位数：仅作为最低限度资格检查。
2. StandardScaler → Ridge，`alpha=1, solver=svd`。
3. HistGradientBoostingRegressor：`loss=absolute_error, learning_rate=0.1, max_iter=100, max_leaf_nodes=31, min_samples_leaf=20, l2_regularization=0, max_bins=255, max_features=1.0, categorical_features=None, early_stopping=False`。

scikit-learn 的直方图提升回归器支持绝对误差损失；关闭 early stopping，固定全部参数和随机状态，以避免根据本轮验证结果调整训练过程。[官方参数说明（固定 1.7 系列）](https://scikit-learn.org/1.7/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html)

三个固定 seeds 为 11、22、33。它们用于检查当前确定性配置的重复性，不把重复预测当作三个独立的数据样本或泛化证据。每个模型每个验证样本的预测范围必须 ≤ `1e-8`；否则是预声明的测量有效性失败，停止并保留错误。

在 Ridge 与 HGB 中，选择三个 seeds 的平均验证 MAE 较低者；同分选 Ridge。选中模型在每个 seed 上均需比训练中位数 MAE 至少低 **0.05 ring**，否则 STOP，不加模型、调参或重新划分。

0.05 是本次待审核的工程资格门槛，尚无业务价值依据。通过只意味着允许准备下一份研究协议：既不证明泛化增益，也不批准最终留出评分。后续科学实验仍需最强相关基线审查、合适的不确定性设计及有意义的效果门槛。当前是固定候选集内的基线选择，不能称为全局最强方法，也不是复现某篇论文相同划分下的已发表分数。

## 执行范围与成本

- 独立 `.venv-tabular`，Python 3.12；numpy 1.26.4、scipy 1.15.3、scikit-learn 1.7.2、joblib 1.5.2、threadpoolctl 3.6.0。
- 本机 CPU 单线程；一个工作进程最多 240 秒，另有环境/隔离检查开销；输出监测阈值 16 MiB。这不是硬内存或磁盘配额。
- 没有 agent、模型调用或付费云任务。报告保存墙钟时间、各模型拟合/预测时间、RSS 和保留字节；电费、折旧、安装与长期存储未定价，货币费用记为未知。
- Linux 使用 Bubblewrap；macOS 使用 Seatbelt。只挂载/允许训练输入、无标签验证特征、固定 worker、运行环境及输出。工作进程禁止联网；它没有模型登录文件。
- 预检不通过就不训练；一旦创建实际 attempt，失败、无效、STOP 或 CONTINUE 都不能在同目录自动重跑。进程强杀留下的未完成目录同样不能复用。

本地批准绑定方案、分区内容、源码和依赖要求的摘要，变更后失效。批准记录不是身份认证；没有跨副本全局锁，不得通过复制或删除记录复用一次尝试。人工查看公开数据的可能性仍存在，OS 隔离不把公开标签变成未知科学测试集。

## 同事如何准备同一份审查材料

从源码根目录运行；这些命令不训练、不评分：

```sh
bash scripts/bootstrap-tabular.sh
python3 -m research_harness tabular fetch --out assets/tabular/abalone
python3 -m research_harness tabular prepare --data assets/tabular/abalone/abalone.data --out reviews/abalone-baseline
python3 -m research_harness tabular verify --review reviews/abalone-baseline
```

输出目录不能覆盖。阅读该目录的 `REVIEW.md` 和 `bundle.json`，其中包含本次源码对应的精确摘要。只有审核后才使用 `tabular approve` 与 `tabular baseline`；命令写在生成的 REVIEW.md 中。默认 `research --task tabular-regression` 仍拒绝，不能借此入口运行自主候选。

公开仓库只提交代码和本审查说明，不提交原始数据、划分标签、批准记录或运行日志。数据保留 UCI 许可与归属；本地审查包含标签，不能交给未来候选 actor。

## 已完成的软件验证与剩余工作

macOS 已通过真实文件/网络隔离探针，以及合成数据的隔离拟合 → 控制器评分 → 终局账本流程。合成 fixture 的批准明确标为软件测试，不是用户批准。Linux CI 增加同样的实际内核与固定模型软件验收；两平台检查均不下载或训练真实 Abalone。

真实 Abalone 已完成上述一次固定基线检查。进入自主候选研究前，还需完整任务作用域内的数据/路线记忆、干预审查、严格完成审计和证据交接；现有 SR 接口没有被当作这些能力的替代品。0.17 仅增加基线历史审计和固定机制的筛查记录，不代表这些剩余能力已全部具备。

原审核问题已获确认并完成。本阶段到此关闭；不能再次按本页启动资格检查。若目标改为某个付费行业，应另选任务、数据并冻结新协议。
