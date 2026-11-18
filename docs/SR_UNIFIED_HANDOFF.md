# SR 约束与统一交接 v4

0.31.0 默认导出 v4，包含五个组件：回归排除、数据暂停、Airfoil 占用/终局、
回归提案占用，以及固定 SwinIR-S ×2 / Urban100 修订的 SR 研究记忆。
SR 保留已评分原图、未评分预留、已读文献 ID、停止/被拒绝路线及冻结研究身份。
沿用旧 SR memory v1 合并规则，不把提案失败或无效测量改写成科学 STOP。

## 交接

双方升级至 0.31.0 或兼容版本。使用实际开展工作的 checkout；`--root` 默认
为安装所在仓库，不随 shell 工作目录变化。状态与预览不启动研究。

```sh
python3 -m research_harness handoff --root /path/to/sender status
python3 -m research_harness handoff --root /path/to/sender export --out /private/state-v4.json
python3 -m research_harness handoff --root /path/to/receiver verify /private/state-v4.json
python3 -m research_harness handoff --root /path/to/receiver preview /private/state-v4.json
# 审阅变化后填写该接收方刚得到的摘要
python3 -m research_harness handoff --root /path/to/receiver import /private/state-v4.json --expect-preview SHA_FROM_PREVIEW
```

`tabular handoff` 是同一入口的旧别名。五组件完整检查与合并在原 checkout
锁内完成，仍一次原子发布，不会先启用一部分。重复导入幂等，旧/空快照不会
释放预留、降级终局、清除数据暂停或重开路线。

`sr_studies`、`sr_scored_originals`、`sr_reserved_originals`、`sr_papers` 和
`sr_routes` 分别显示研究、已评分原图、未评分预留、已读文献与路线数。
`changes.sr_memory` 使用 `study:`、`image:`、`paper:`、`route:` 身份前缀；
其总数是不同类型记录的合计，不是独立实验数。预留→已评分会显示图像更新，
同数量的终局/绑定变化也可见。新增 SR 约束会使旧预览摘要失效，需重新核对。

## 兼容与停止规则

- 统一 v1/v2/v3 继续可读，明确显示 `sr_memory` 缺项和空值计数；缺项不等于
  没有历史。旧包不删除已有 SR 约束。旧软件拒绝 v4，双方须升级。
- 旧 `memory` 入口仍读写 SR memory v1，并能看见统一导入的 SR 记录。既有
  `new-study` / `research` 准备入口沿用这个读取器，排除图像、研究 ID、
  文献和停止路线，冻结到原有材料；不得用同名研究或已用图像重开失败路线。
- 冻结身份或终局冲突、不同研究图像重叠，均拒绝整个交接。没有自动解决冲突、
  解除预留或放宽研究门槛的选项。`PROPOSAL_FAILURE` 保持已评分和提案拒绝，
  `INVALID/INCOMPLETE/REJECTED` 保持原有预留语义。
- 尚无 SR 模板或本地 SR 历史的接收目录可保存已知约束，但不是可执行研究
  环境。若模板部分缺失、已有 SR 历史却缺模板、空预留缺少 policy，或已知
  材料损坏/链接，则统一快照拒绝；不能以缺失信息证明图像未用。

每组件仍最多 4 MiB；v1/v2/v3 的总上限保持 12/16/20 MiB，v4 为 24 MiB。
合并结果也受限，不能删历史腾空间。输出不可覆盖、权限 0600；原子发布需要
文件系统支持硬链接，不承诺断电后的持久性或防御恶意本地文件修改。

## 边界

包可能含候选源码、机制文字、图像/文献 ID、身份摘要、审查者姓名与暂停原因，
分享前核对敏感内容。没有图像数组、标签、论文全文、原始事件或执行批准；
完整私有证据仍通过各任务的 evidence 入口单独交接。摘要不是签名，所有来源
仍是未认证声明，不证明研究真实发生或有科学效果。

导入不授予执行、恢复或重新使用留出的权限。五组件覆盖的是当前已实现的任务
约束，不是任意任务适配、跨机器实时锁或对旧历史文件所有直接执行方式的新增
授权检查。既有隔离、预注册、数据资格及单次执行批准保持；没有新的研究实验。
