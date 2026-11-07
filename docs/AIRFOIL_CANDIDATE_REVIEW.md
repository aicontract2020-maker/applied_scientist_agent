# A2：单一 Strouhal 特征试验 — 冻结方案与执行状态

**执行状态更新（2026-11-07）：**用户已批准下列冻结方案，并在 macOS Seatbelt 内执行一次，结果为有效 [CONTINUE](../tasks/airfoil_noise/a2/REPORT.md)。全部 285 条最终留出已消费，不得重跑。以下是执行前的方案记录；其中“待审/未执行”描述准备阶段，当前状态以结果报告为准。下一步仅可另行审查外部数据复现。

2026-11-07，状态 **AWAITING_RESEARCH_REVIEW / NOT_RUN**。A1 已选定固定 Extra Trees 参考；本轮完成文献核对、一个候选的干预审查、执行与审计支持及合成验证。没有真实候选拟合、候选验证筛选或最终留出预测/评分。A1 和 Abalone T1/T2 的原始记录不改写、不重跑。

## 一个具体假设

在原五列后仅追加 `frequency * suction_side_displacement_thickness / free_stream_velocity`，即 (St=f\delta_s^*/U)，是否足以让固定 Extra Trees 在未使用的工况上降低误差？原输入、标签、训练集、模型参数和随机种子保持一致。与 A1 参考比较，三个 paired seed 的工况等权 MAE 改善都至少 **0.2 dB**，工况 bootstrap 95% 下界大于零，含特征构造的时延比不超过 **1.1**，才 CONTINUE。

这是应用假设，不是首次发现 Strouhal 数，也没有在看完候选分数后选公式。只定义这一候选，不筛选 log 版、比例常数、多个特征或新模型。

## 文献证据与推断的边界

已下载并视觉核对 [NASA RP-1218 原文](https://ntrs.nasa.gov/citations/19890016302)第 5.1.1 节，印刷第 51 页（PDF 第 59 页）。原文的位移厚度频率缩放使用 (f\delta^*/U)，并讨论吸力侧厚度；同页也指出峰值位置、谱形和幅值仍依赖工况。因此，本试验把它当作有物理动机的坐标，而不是完整 BPM 噪声模型或保证有效的谱塌缩。

NASA PDF SHA-256 为 `0c22690c6216c4355c0da7e09ce0d1a1dd96a2b88d3d8abda30e293b3db76006`，6,177,160 bytes；本地文献保存于 `reviews/airfoil-a2-literature-021/`。定位、来源、解释和局限冻结在 [提案](../tasks/airfoil_noise/a2/proposal.json) 中；并未声称完整阅读了全部 146 页或复现论文算法。

[scikit-learn 1.7.2 官方说明](https://scikit-learn.org/1.7/modules/ensemble.html#extremely-randomized-trees)解释了 Extra Trees 的随机切分阈值。增加多变量坐标会改变可用切分及随机选择；**改善预测是本提案的推断，尚无实验确认**。即使改善，也不能仅凭这项试验把原因唯一归于物理机制；本轮不增加一个随机特征对照来扩充试验。

## 注册前干预审查

实现只接受固定机制 `airfoil-suction-strouhal-v1` 及精确展示源码，不接受任意候选 Python。执行时调用冻结的可信算术函数，原五列不变。合成网格检查这列不是常数、原有单列的重复或单列函数；实际合成模型检查预测确实变化。它与 Abalone T1 的残差偏移、T2 的壳重组成比、超分后处理路线不同，原停止路线不因此解除。

这仅是本固定机制的有限审查，不是任意代码等价性或科学新颖性的证明。只支持这一个待审候选，不宣称 Airfoil 已有通用自主提案执行入口。文献检索和提案由本会话 agent 完成，没有额外启动独立模型 actor，也没有模型 API 实验费用。

## 冻结实验设计

| 项目 | A2 固定规则 |
| --- | --- |
| 参考 | A1 中选出的 Extra Trees；不再比较五种模型，不重跑资格选择 |
| 训练 | A1 原 961 行、67 个工况；逐行等权；不合并验证集 |
| 验证 | A1 原 257 行、18 个工况，仅检查基线逐 seed 预测复现（绝对误差 ≤1e−8）；不生成候选验证预测 |
| 最终留出 | 285 行、21 个工况，全量一次；标签仅在控制器 |
| 干预 | 原五列后追加唯一的 (f\delta_s^*/U)，无拟合型特征工程 |
| 训练重复 | seed 11/22/33，每个 seed 同参数 baseline/candidate，各 100 棵树，共六次拟合 |
| 主要指标 | 每个工况内先算 MAE，再对工况等权平均，单位 dB |
| 最小效果 | 每个 seed 改善 ≥0.2 dB；这是待批准的工程采用门槛，不是业务/听感标定值 |
| 不确定性 | 对 seed 平均的配对工况损失抽样；10,000 次完整工况 bootstrap，seed 20261107，95% 区间；下界须 >0 |
| 时延 | 每个拟合模型对整批留出预测五次取中位数；候选包含变换及数组转换；三个 seed 的中位时延之和比 ≤1.1 |
| 执行顺序 | seed 11/33 先 baseline，seed 22 先 candidate；没有根据时延结果换顺序 |

数据分组沿用 A1 的迎角、弦长、流速三元组，不把一个工况内不同频率当作独立样本。种子代表固定训练集上的随机训练变异，不等于新数据重复。公开历史数据、未知批次依赖和只有 21 个代理工况限制推断范围；bootstrap 区间不证明独立性或排除公开数据污染。

冻结协议调用既有配对效果/区间/时延判定函数，抽样单位改为完整工况；没有修改 SR/Abalone 的旧评价和阈值。报告所有 seed、均值、标准差、工况效应和全部成本，不只报告最好 seed。

## 所有结果的事先决定

- 三项门槛和全部 seed 效果均通过：CONTINUE，仅允许另行设计外部数据复现；不自动部署、重跑或作人类替代声明。
- 任一有效结果低于门槛：STOP，关闭这个 Strouhal 追加特征路线；不能改常数、用 log、加特征、加树、换模型或重划数据来救回。
- 基线复现、输出完整性/有限性、环境/隔离等预定有效性检查失败：阻止执行或记测量无效，保留预留；不把测量无效当科学反证，也不自动重跑。

所有输出通过身份、数值和基线复现检查后，控制器才使用隐藏目标评分。候选一旦启动，即使复现失败而未评分，留出特征已暴露，整组仍预留；中断留下的预留也不释放。换目录/ID 无法绕过本机预留；已发布的消费/停止记录也会阻止新 clone。尚未同步的两个 checkout 之间没有全局锁，因此必须只指定一个执行位置。

## 隔离和费用

沿用 macOS Seatbelt / Linux Bubblewrap，无无隔离回退。worker 只看到训练标签、验证特征和留出特征，不能读取控制目录、验证/留出标签，不能联网或修改输入。先通过实际内核探针，再预留和启动。

固定 Python 3.12 和 tabular 锁定依赖，CPU 单线程，worker 最长 240 秒，输出监测上限 16 MiB，一次尝试。报告六次 fit、训练特征构造、30 次预测计时、墙钟、峰值 RSS 和保留字节。模型 API/付费云调用为零；下载、安装、存储、能源/硬件及人工审查成本仍未计价，没有新增硬内存配额。

## 审核与命令

原 A1 完整证据以只读副本纳入 A2 审查目录；实际训练使用的是拟执行的新代码，二者均绑定摘要。待审索引见 [A2 审查包](../tasks/airfoil_noise/a2/README.md)。

```sh
# 已完成，不能覆盖已有目录：
.venv-tabular/bin/python -m research_harness airfoil prepare-trial \
  --baseline reviews/airfoil-baseline-020 \
  --proposal tasks/airfoil_noise/a2/proposal.json --out reviews/airfoil-a2-strouhal-021-final
# 只有用户批准具体冻结摘要后：
.venv-tabular/bin/python -m research_harness airfoil approve-trial \
  --review reviews/airfoil-a2-strouhal-021-final --sha256 EXACT_SHA --reviewer REVIEWER
.venv-tabular/bin/python -m research_harness airfoil execute-trial --review reviews/airfoil-a2-strouhal-021-final
.venv-tabular/bin/python -m research_harness airfoil audit-trial --review reviews/airfoil-a2-strouhal-021-final
```

需要用户审核的是：是否接受这一候选及文献解释、0.2 dB/区间/1.1 时延门槛，以及**一次消耗全部 285 条最终留出**。A1 的批准只覆盖基线资格，不能用于 A2 留出实验；沿用既有精确摘要审批机制，准备阶段没有生成 A2 审批记录。
