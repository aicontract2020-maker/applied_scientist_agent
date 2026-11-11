# 数据使用暂停（C7）

已接受的资格材料是冻结快照。如果后来发现许可、来源、泄漏或数据条件问题，
可登记本地暂停，阻止这份数据的新准备、批准、提案与执行。原资格决定、执行
批准和历史结论不改写；暂停不是科学 STOP，也不会释放任何留出或停止路线。

## 登记与查看

在实际执行研究的 checkout 根目录操作：

```sh
python3 -m research_harness data-blocks status
python3 -m research_harness data-review inspect /private/path/packet.json
python3 -m research_harness data-blocks add /private/path/packet.json \
  --sha256 EXACT_QUALIFICATION_SHA256 --reviewer YOUR_NAME \
  --reason '记录新发现的问题及可追溯依据；避免粘贴不必要的私密内容'
```

输入是 C4 `packet.json`，不是 `bundle.json` 或 `trial.json`。需要包的精确摘要，
但无需其已被接受：尚未解决的来源也可以暂停。重复提交完全相同的记录幂等。
审查者名称是本地记录，不是身份认证；系统不判断原因的事实或法律真实性。

暂停以包内 `dataset.id/version/source` 三字段精确匹配，覆盖同一身份的四个
现有 adapter，不限于原用途或原资格摘要。更换方案 ID、用途、基线／候选作用域、
重新接受资格不会解除暂停。封闭 adapter 仍锁定原数据身份，不能任意改版本绕过。
系统不识别不同网址或 ID 指向同一数据的别名；新 adapter 必须另行审核身份映射。

## 执行行为

- 两套基线在公共 prepare 解析原始数据之前检查；内部 fixture 准备也检查。
- 两套候选在准备和批准时检查；统一回归提案入口及直接 proposer 在输出、预留、
  模型调用之前检查。proposer 在隔离探针后再次检查资格、暂停与停止/占用记忆。
- 四个执行入口的只读 preflight 和正式 execute 都检查；隔离探针后再次检查，
  通过才进入原预留、注册和一次执行。旧批准不能绕过暂停。
- `DATA_USE_BLOCKED` 表示当前数据使用被暂停，不产生新科学结果；状态文件损坏、
  非法格式、符号链接或非普通文件也会阻止活动操作。
- 历史只读审计仍可复核原证据，带资格的历史包仍校验内嵌资格完整性。历史读取
  可能包括控制器已有数据／标签，但不会训练、重新评分新数据或改变历史状态。

入口先将操作者指定的 checkout 根路径规范化（兼容 macOS `/var`、`/tmp` 等目录别名），
再拒绝状态目录及状态文件中的链接。状态保存在当前安装所在 checkout 的 `.research-memory/data-blocks.json`。
没有文件只表示“没有本地暂停记录”，绝不表示已经获得数据许可或实验批准。
`data-blocks --root /path/to/checkout status` 可指定另一份本地状态；普通执行命令
使用安装所在 checkout，不能靠运行时目录选择无记录的状态。交接必须导入到
接收方实际执行的那一份 checkout。

## 与同事交接

```sh
python3 -m research_harness data-blocks export --out /private/path/data-blocks.json
# 同事在自己的 checkout 中：
python3 -m research_harness data-blocks import /private/path/data-blocks.json
python3 -m research_harness data-blocks status
```

包只含数据身份、资格摘要、审查者及原因，不嵌入资格证据全文、邮件、标签或凭据。
原因和身份本身仍可能敏感，分享前人工审查；不要把真实暂停包直接提交到公共仓库。
摘要仅验证完整性，不能验证发送者身份。只导入可信来源的记录。

导入验证整包后合并并集，原子保存；重复幂等，空包或较旧快照不能删除本地暂停。
未知字段、错误摘要、重复记录、超限、链接等拒绝，失败不能部分合并。
单包和合并后均至多 256 条、4 MiB；超限则阻止写入，须另行设计扩容而非删除记录。
此包与原研究排除记忆、私有证据包**分别交接**；这三类包不能相互替代。

## 边界

没有解除／恢复命令。如果未来要恢复使用，需先审核专门的恢复规则；不可手动删
文件或换 checkout 作为恢复流程。本轮不自动发现作者撤回许可、不提供跨机器实时
同步，也不改变 SR 或通用可信本地 run 的访问规则。

所有登记／导入与研究操作使用同一个 checkout 锁。研究正在执行时，暂停命令会
报告锁冲突，**这次登记没有生效**；需操作员处理当前进程并在锁释放后重新登记。
暂停不是紧急中断按钮，不承诺停止已启动的 actor 或 worker。探针后复查能发现
已发生的状态变化，但不能抵御有权限删除／替换整个状态库或修改源码的操作者。
离线交接必须先同步再串行接手；不同 checkout 的陈旧状态不能证明可用。

框架升级改变源码摘要，旧未执行审查包仍需按原规则重新准备及审查，不能直接更新
摘要保留批准。科学配方、阈值、隔离、预注册与失败停止规则保持不变。

## 0.26 的统一状态交接入口

双方升级到 0.26 后，可使用 [tabular handoff](UNIFIED_STATE_HANDOFF.md) 一次性交接
回归排除记忆与全部数据暂停，不再需要分别传这两个状态包。旧命令仍可用并读取
合并状态；完整私有证据仍独立交接。该格式不包含 Airfoil/SR 预留或 proposer
预留，不是所有任务的完整记忆迁移。旧版接收程序不认识新增状态目录，须先升级。

## 0.27 的覆盖更新

[C9 统一交接 v2](AIRFOIL_MEMORY_HANDOFF.md)已将 Airfoil 基线／候选排除记忆作为
第三组件纳入；推荐使用 `handoff`，原 `tabular handoff` 别名也导出 v2。上文
关于 C8 不携带 Airfoil 的限制仅适用于 v1。v1 仍可读但明确标示 Airfoil 缺项；
双方使用 0.27 或更新的兼容版本。SR/proposer 预留及私有证据仍单独处理。
