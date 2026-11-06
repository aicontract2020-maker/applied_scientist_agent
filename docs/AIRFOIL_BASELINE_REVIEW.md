# A1：公开翼型噪声任务与基线资格审查

2026-11-06，状态 **AWAITING_REVIEW / NOT_RUN**。用户目前没有业务数据或人类对照，授权先选择公开任务并完成可自主推进的准备。这一关验证新任务的基线与工程适配，不是 D1 人工时间/商业价值评测。真实数据尚未拟合、推理或评分；最终留出未消耗。

## 任务选择与来源

选择 [UCI Airfoil Self-Noise](https://archive.ics.uci.edu/dataset/291/airfoil+self-noise)：1,503 条观测，5 个连续数值输入，目标是 scaled sound pressure level（dB），许可 CC BY 4.0。输入为频率、迎角、弦长、流速、吸力侧位移厚度。数据来自风洞翼型测试，适合作为小型 CPU 回归及相关观测分组的工程基准。它不直接代表整机风机噪声、未见翼型、行业需求或客户付费意愿。

同轮也查看了 [UCI Concrete Compressive Strength](https://archive.ics.uci.edu/dataset/165/concrete+compressive+strength)。它具有材料实验背景，但混合配方和龄期需要新的分组论证，原文件还需 XLS 解析依赖。本轮优先选择文本可直接固定校验、工况含义清楚的 Airfoil；没有拟合任何候选数据集来挑选“容易出正结果”的任务。

[Brooks、Pope、Marcolini 的 NASA RP-1218](https://ntrs.nasa.gov/citations/19890016302)提供自噪声机制与半经验预测的背景。本轮阅读的是官方摘要和数据字段说明，不声称复现论文公式或分数。UCI 表没有逐次运行/实验批次标识，也没有完整的观察位置等物理输入；本阶段不会假装已实现完整物理基线。后续科学候选若依赖原文公式，必须另行查阅和核验。

[Grinsztajn 等的表格基准研究](https://arxiv.org/abs/2207.08815)支持把树模型纳入相关基线集合，但不能证明某个固定配置在 Airfoil 上最强。本阶段同时比较线性、平滑核方法和两种树集成；“最强”仅指这组预先固定的可复现模型中验证误差最低者。若要发表算法优越性结论，仍需更强的任务专门基线论证。

## 下载前固定的分区

按迎角、弦长、流速三元组归组，同组所有频率和位移厚度观测不可跨分区。组键为规范 JSON `{split: airfoil-condition-v1, condition: [angle, chord, velocity]}` 的 SHA-256；前 8 位十六进制除以 2^32，落在 `[0,.6)`、`[.6,.8)`、`[.8,1)` 分别进入训练、验证、最终留出。

规则及最少组数在下载前记录于 intake-rule.json；没有尝试第二个 salt、拆分或按标签筛选。检查只涉及格式、非有限值、哈希和特征分组数量，没有查看目标分布或模型分数。原始 archive/raw 的 SHA-256 随源码及审查包绑定。

| 分区 | 观测数 | 工况组数 | 本次使用 |
| --- | ---: | ---: | --- |
| 训练 | 961 | 67 | 拟合固定模型及 scaler |
| 验证 | 257 | 18 | 控制器评分、固定集合内选参考 |
| 最终留出 | 285 | 21 | 保留；特征和标签均不挂载给 worker |

最少组数预定为训练 20、验证 10、留出 10；不满足就停止准备。这种分组只是保守代理，不认证真实实验独立性。共享实验装置、翼型族或批次仍可能带来相关性。目的限于未见工况，不声称跨实验室泛化。参照 [scikit-learn 分组评价说明](https://scikit-learn.org/1.7/modules/cross_validation.html)，不把同工况的频率点当作独立样本。

## 固定假设和决定

假设：预设学习模型中验证集平均工况 MAE 最低者，在 11/22/33 每个 seed 下都较训练中位数至少改善 **1 dB**，且其工况 bootstrap 差值区间下界大于零，足以成为后续候选研究的参考。

固定集合：训练中位数、标准化 Ridge、标准化 RBF-SVR、HGB、Extra Trees，共 **15 次拟合**。所有模型、scaler 仅使用训练行；参数和依赖完整冻结在 bundle.json 的 recipe 中。SVR 的 C=10、epsilon=.1、gamma=scale；HGB 为 100 轮、31 叶节点、无早停；Extra Trees 为 100 棵树、无 bootstrap。没有网格搜索或候选实验。参数以 [scikit-learn 1.7.2 官方 API](https://scikit-learn.org/1.7/modules/generated/sklearn.svm.SVR.html)及锁定版本为准，未用新数据分数调参。

主要指标为每个工况内先算 MAE，再对工况等权平均，单位 dB；与所有行直接取平均不同。训练仍逐行等权，该选择事前固定。1 dB 是待用户批准的工程门槛，没有已验证业务或听感意义。

按三个 seed 的平均工况 MAE 选最低的学习模型，同分顺序 Ridge、SVR、HGB、Extra Trees。选定后若失败，不能改用另一模型救回资格。报告所有 seed 的 MAE、改善量、标准差、预测范围和全部拟合成本；不把 seed 当成独立数据重复。

不确定性：对 **完整验证工况**抽样 10,000 次，随机种子 20261106；比较的是 seed 平均的配对工况损失。每个学习模型都报告 99% percentile 区间（排序索引 floor((N−1)×.005) 与 floor((N−1)×.995)）。四个比较的名义 Bonferroni 家族覆盖至少 96%，但这仍是小样本近似 bootstrap，无法消除未知组间依赖或验证选择乐观性；不作为最终泛化证明。

- 效果与区间门槛均通过：CONTINUE，只允许起草新的科学候选审查包，不自动运行候选或评分留出。
- 任一门槛失败：有效 STOP，关闭这次基线资格路线，不换模型、调参、改分区或重跑。
- 数据/源码/环境、预测身份、有限性或实际隔离检查失败：阻止执行或保留测量无效结果；启动后的预留不释放，不自动重试。
- Median/Ridge/SVR/HGB 跨 seed 预测范围须 ≤1e−8；Extra Trees 的随机差异属于应报告的训练变异，不按此确定性条件判无效。

## 执行边界与成本

CPU 单线程，Python 3.12 和现有 tabular 锁定依赖；worker 最长 240 秒，输出监测上限 16 MiB。没有模型 API 或付费云任务。记录 15 次 fit/predict 时间、墙钟时间、峰值 RSS、保留字节；安装下载、存储、能源/硬件折旧和人工审查费用列为未计价，不填零。没有额外硬内存或总磁盘配额保证。

沿用实际 macOS Seatbelt / Linux Bubblewrap 边界，必须先通过隐藏标签、repo、输入只读和断网探针；不允许退回普通 subprocess。审批绑定数据、协议、代码和依赖摘要。公开 CLI 仅接受固定 UCI 字节；合成数据入口是软件检查接口。结果由控制器持有验证标签计算，worker 不接受任意源码或命令。

同一 checkout 下使用数据级预留：换目录、ID 或协议无法绕过已启动的尝试；复制旧 checkout 仍不是分布式全局锁。获批后应指定一处执行并保存完整记录，不能在两台机器各跑一次。此新任务尚无通用跨 clone 记忆包或自主候选 adapter；不冒充原 Abalone 的 0.19 完整接口。

## 可复现命令与当前审核点

```sh
bash scripts/bootstrap-tabular.sh
python3 -m research_harness airfoil fetch --out assets/airfoil-020
python3 -m research_harness airfoil prepare \
  --data assets/airfoil-020/airfoil_self_noise.dat --out reviews/airfoil-baseline-020
python3 -m research_harness airfoil review --review reviews/airfoil-baseline-020
# 只有用户批准具体冻结摘要后才写 approval，并执行一次：
python3 -m research_harness airfoil approve --review reviews/airfoil-baseline-020 \
  --sha256 EXACT_REVIEW_SHA --reviewer REVIEWER
.venv-tabular/bin/python -m research_harness airfoil baseline --review reviews/airfoil-baseline-020
.venv-tabular/bin/python -m research_harness airfoil audit --review reviews/airfoil-baseline-020
```

本次已经准备实际审查包，公开摘要见 [A1 审查索引](../tasks/airfoil_noise/a1/README.md)。请审核：是否接受工况分组及局限、固定五模型/三 seed、1 dB 与区间门槛、单线程本地一次执行范围。该审批不覆盖后续候选、最终留出或商业效率评测。保留审查门槛来自既有精确审批流程及用户“直到需要我审查”的任务范围。
