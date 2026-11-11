# Airfoil 记忆与统一交接 v2（C9）

0.27 将 Airfoil 基线资格尝试、候选留出消费和停止机制纳入保守记忆。换 checkout
后，同事可继续遵守已知的尝试记录，而不会因本地缺少旧目录误认为数据尚未使用。

## 交接方法

双方使用 0.27 或更新的兼容版本，在实际执行研究的 checkout 中操作：

```sh
python3 -m research_harness handoff status
python3 -m research_harness handoff export --out /private/path/state-v2.json
# 接收者：验证只读；导入明确改变本地约束状态
python3 -m research_harness handoff verify /private/path/state-v2.json
python3 -m research_harness handoff import /private/path/state-v2.json
python3 -m research_harness handoff status
```

原 `tabular handoff` 是同一实现的兼容入口，也导出 v2。`--root PATH` 放在入口
与子命令之间；默认读取安装所在 checkout，不随 shell 当前目录切换。

v2 同时包含：回归试验排除记忆、C7 数据暂停、Airfoil 基线／候选排除记忆。
仍用单文件原子发布，任一组件或本地合并冲突时不导入任何一部分；重复幂等。
三个组件各最多 4 MiB，完整包最多 16 MiB；Airfoil 合并后最多 1000 个阶段／
作用域记录，其他限制不变。没有更换失败包内容、清空旧状态或拆开导入的回退。

## Airfoil 状态如何保留

- 从已发布的 A1 审查摘要及 reservation-decision、A2 trial-history 读取已知记录，
  校验元数据绑定，不训练或重新评估科学结果。新 clone 也保留 A1 的基线占用。
- 从本地 `.research-memory/airfoil-baseline` 与 `airfoil-trial` 读取预留、终局和
  摘要。即使只创建了空预留目录，也保留其作用域占用；缺失的审查摘要记为未知，
  不编造。若有终局但没有相应预留绑定，或材料损坏，则拒绝读取／导出。
- 已发布的旧候选索引没有结果摘要时保留 `null`，不把未知当成独立审计通过。
  后续一致的详细记录可以补全；冲突的审查、机制、结果或终局拒绝合并。
- RESERVED 只能被一致终局补全，陈旧包不能将终局降回 RESERVED。INVALID
  表示无效测量，仍占用该数据，但不伪装成科学 STOP。STOP 会关闭同一候选机制，
  不能靠更换数据或数字恢复已停止路线。
- 基线和候选按不同阶段／作用域记录：已做过基线不等于已消费候选留出；已做过
  候选也不能通过改方案 ID、分区或复制目录再执行。

基线 prepare 在解析公共原始数据前检查已有消费；准备、批准、只读 preflight
及 execute 都消费相应记忆。候选复用原入口检查。执行器在隔离探针后再检查当前
状态，再进行原预留和一次执行。原资格、精确批准、隔离与数值门槛没有改变。
历史只读审计继续读取冻结证据，不因为当前占用或暂停而改写旧结果。

## 版本兼容与边界

C8 v1 包仍可校验和导入，输出 `airfoil_records: null` 及 `Airfoil NOT_INCLUDED`。
这代表该包**没有携带** Airfoil 状态，不代表发送者没有做过 Airfoil 研究。导入 v1
不会清除接收方的 Airfoil 记录，随后导出 v2 会带上接收方当前已知的三类状态。
v2 缺少第三组件时会拒绝，不能自动按 v1 降级。

旧 0.26 及更早程序不支持 v2；双方必须升级再交接和执行。v2 沿用版本化协议的
旧 kind 和存储目录名称以便发现并拒绝不兼容状态，文件名仍为完整包摘要。不要
通过删文件或降级软件绕过版本拒绝。版本兼容读取不证明历史记录已完整提供。

包不含原始行、标签、完整资格／论文证据或执行批准，但包括机制文字、特征指纹、
审查者及暂停原因，分享前仍需审查。完整私有研究证据单独保管；本轮没有新增
Airfoil 私有证据解包功能，也不批准任何新的研究。

SR 记忆、proposer 会话预留和跨机器实时协调尚未纳入。发送方的新记录要再次
同步；共用数据池必须串行接手。没有身份签名、断电持久性保证或解除暂停流程。
未知数据别名和新 adapter 的作用域映射仍需另行设计。合成检查必须使用独立
测试状态目录，不能将合成 STOP 或预留当成真实研究证据导入生产 checkout。
