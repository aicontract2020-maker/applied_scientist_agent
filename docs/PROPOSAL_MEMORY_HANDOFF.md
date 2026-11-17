# 回归自主提案占用与统一交接 v3（C10）

0.29 新增[只读合并预览及绑定导入](HANDOFF_PREVIEW.md)，接收方可先查看本地
合并冲突和恢复限制，再按预览摘要导入。v3 包及以下占用语义保持不变。

0.28 让回归自主提案的一次会话预留随交接包迁移。此前只保存在发送方本机的
`.research-memory/tabular-proposer` 不会随普通 clone 出现，接收方可能重复调用
模型。双方升级到 0.28 或更新的兼容版本，再交接执行 checkout 的当前状态。

```sh
python3 -m research_harness handoff status
python3 -m research_harness handoff export --out /private/path/state-v3.json
# 接收者先只读验证，再显式导入约束
python3 -m research_harness handoff verify /private/path/state-v3.json
python3 -m research_harness handoff import /private/path/state-v3.json
python3 -m research_harness handoff status
```

旧 `tabular handoff` 仍是同一入口。需要指定 checkout 时，将 `--root PATH`
放在 `handoff` 后、子命令前；默认读取安装所在 checkout。文件不可覆盖。

## 记录的含义

提案组件只保留 scope 与可空的 baseline_sha256，最多 1000 条。scope 沿用原
基线的数据来源和分区摘要，不含研究 ID 或输出目录，因此改名不能释放占用。
仅创建了空预留目录也保留占用，未知基线摘要为 null；一致的已知摘要可补全，
不同摘要拒绝合并。损坏、链接或非目录预留拒绝读取，不按“没有做过”处理。

无论原提案已完成、被拒绝、未完成或做过原有启动恢复，预留都不释放。此组件
不读取/导出 decision、模型文本或恢复证据，也不宣称提案的完成状态。它不是
科学 STOP，不表示留出已消费，不证明论文或研究结论有效；这些仍由原有试验
记忆、审计和审批处理。没有从缺少提案元数据的已发表结果推造历史会话记录。

直接 `tabular propose` 与统一 `research --stage propose` 在研究输出或模型
调用前检查占用；直接执行器在隔离探针后再次检查。当前暂停、资格、科研 STOP
和留出限制仍独立生效。不修改候选准备/批准/单次执行入口，因此现有已生成
提案仍可交给人审查，并在独立批准后按原规则执行。

## 恢复边界

原有 macOS 本机的一次 Node 初始化失败恢复仍需原始零事件/无提案证据、本地
预留与结果绑定，且未消耗恢复机会；隔离探针后再查。普通失败不获得重试权。
导入占用一律不携带恢复权；即使接收方另有相同失败文件，也不能用
`--recover-launch` 绕过。将自己的导出包导回原 checkout 同样会施加此限制，
这是保守约束，不提供删记录或取消导入的回退。

## 原子交接与旧包

v3 同时携带回归试验排除、数据暂停、Airfoil 排除、回归提案占用四个必需组件。
校验和本地合并检查全部通过后一次发布，失败不导入一半，重复幂等。每组件
4 MiB，v3 整包 20 MiB；v1 的 12 MiB 和 v2 的 16 MiB 上限保持不变。

v1/v2 仍可读，但显示 `proposal_records: null` 和 `proposer NOT_INCLUDED`，
表示未携带而非没有历史。导入旧包或空组件不清除接收方已知占用；再导出 v3
包含接收方当前已知状态。v3 缺第四组件拒绝，不自动降级。0.27 及更早程序
不能读取 v3，双方需升级；原 kind、存储目录和完整包摘要文件名继续使用。

不包含 SR 预留、跨机器实时同步、签名、自动重试或通用新数据 adapter。发送方
后续有新记录必须再次交接，共享数据池仍需串行接手。哈希是完整性检查，不是
身份认证或完整历史证明。分享包前审查其中原有机制、特征指纹和暂停原因；
完整私有证据继续独立保管。合成材料只能导入专用测试状态目录。
