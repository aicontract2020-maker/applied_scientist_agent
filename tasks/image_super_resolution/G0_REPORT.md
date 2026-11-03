# 研究决策报告：swinir-g0-reproduction

状态：**CONTINUE**

假设：Official SwinIR-S x2 reproduces Set5 mean PSNR-Y 38.14 dB within 0.02 dB on this fixed CPU environment.

基线：Official SwinIR-S x2 DIV2K pretrained weights; source 6545850fbf8df298df73d81f3e8cba638787c8bd; reference Table 3, arXiv:2108.10257v1. This is reproduction, not global SOTA improvement.

原因：Reference reproduced within frozen tolerance.

结论：The baseline pipeline is usable; plan one separately preregistered improvement study with distinct development and held-out data.

完成重复：1/1
平均效应：-0.000590195225242951；样本标准差：None
总声明费用：$0.001896982257021591；预算：$0.2

## 每次测量（不只展示最佳 seed）

| Seed | 基线 | 候选 | 效应 | 原始产物 |
|---|---:|---:|---:|---|
| 0 | 38.14 | 38.13940980477476 | -0.000590195 | /Users/kaimaplespark/git/applied_scientist_agent/runs/swinir-g0-reproduction/attempts/seed-0 |

确定性复现：一次固定权重运行，不代表独立训练重复。
与参考绝对误差：0.000590195225242951；容差：0.02
参考来源：https://arxiv.org/pdf/2108.10257 (v1, Table 3, lightweight x2 Set5)

## 完整成本与延迟

```json
{
  "cost_totals": {
    "compute_seconds": 6.829136125277728,
    "storage_byte_hours": 2094545.818270906,
    "data_usd": 0,
    "tuning_usd": 0,
    "compute_usd": 0.001896982257021591,
    "storage_usd": 0
  },
  "mean_latency_ms": 864.1604579053819,
  "max_latency_ms": 864.1604579053819
}
```

执行失效和预算停止不等于科学假设被否定；请核对原因和账本。
有效性检查仍由执行代码声明；费用依赖配置，未核验云账单。
CONTINUE 不授权追加调参、部署或改变原阈值。

## 本次真实复现的范围与资源

- 全部 5 张图像，CPU / float32 / 4 线程，未训练、未调参、未修改模型。
- 平均 SSIM-Y：0.96112094；单图平均前向耗时约 0.864 秒（单次测量，不是稳定延迟基准）。
- 父进程峰值 RSS 约 1.09 GB；评价子进程另约 0.30 GB，二者不能相加当作同时峰值。
- 源码、模型、依赖及下载缓存的实际文件总量约 1.38 GB；按磁盘块统计约 1.4 GB。
- 单次执行墙钟约 6.829 秒；按预声明的 1 美元/机时代理费率估算约 0.00190 美元。
- 未调用外部模型服务或云 GPU。代理金额不是实际账单；电费、折旧、完整准备时间和
  运行后保留资产的存储成本未计价，不能把上述金额当成完整研究成本。
- 标准差为空是因为这里只有一次确定性复现；不伪装成独立训练重复。

## 可复查证据

本目录 g0-evidence/ 保存原始逐图指标、资源记录、worker 结果和完整账本。
协议在 g0-protocol.json；资产和代码哈希在 assets.lock.json；依赖在 requirements.lock.txt。
源模型与样例来自固定官方仓库，未把第三方源码、模型、数据或环境提交到本仓库。
本地预测图片保留在 runs/swinir-g0-reproduction/attempts/seed-0/predictions/。

## 结论边界

本轮只验证模型基线能在本机复现。没有测试 agent 自主规划、生成改进方案的能力，
没有证明比 SwinIR 更好，也没有证明任何商业收益。下一阶段必须重新预注册。
