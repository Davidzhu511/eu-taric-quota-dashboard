# EU TARIC 关税配额数据看板

[![Update TARIC dashboard](https://github.com/Davidzhu511/eu-taric-quota-dashboard/actions/workflows/update-and-deploy.yml/badge.svg)](https://github.com/Davidzhu511/eu-taric-quota-dashboard/actions/workflows/update-and-deploy.yml)

公开看板：<https://davidzhu511.github.io/eu-taric-quota-dashboard/>

看板展示钢铁产品类别 **1A、2、4A、4B** 的 55 个 EU TARIC Order Number，并提供筛选、搜索、历史快照、CSV 和 JSON 导出。

同一项目的 [英国 Category 4 看板](https://davidzhu511.github.io/eu-taric-quota-dashboard/uk.html) 跟踪法规 Table 4 的五个编号（058604–058608）。两个看板按选定业务范围展示，并非 EU/UK 官方全部钢铁配额的完整列表。

临近季度交替时，EU 页面另列 TARIC 已公布的下一有效期初始额度；UK 页面列出官方 CSV 中的下一季度五个额度。**未来额度与当前余额分开**。UK `Future` 记录的 `#NA` 余额显示为“尚未公布”；英国季度未用额度可结转，下一季度初始额度不等于开季实际余额。

UK Category 4 结转在季度结束后的第 20 个工作日生效，仅限同一配额年度；前一季度申请窗口截至随后月份第 19 个工作日。旧合同过渡豁免仅覆盖 2026-07-01 至 2026-09-30 的进口。HMRC 通知季度额度已分配 90% 时指定为 Critical，须提供全额税款担保。50% 为本钢铁措施的配额外税率，适用的反倾销/反补贴税另计。依据：[GOV.UK 实施说明](https://www.gov.uk/government/publications/uks-steel-trade-measure-from-1-july-2026/implementation-notifications-on-the-transitional-exemption-quota-administration-and-the-ukraine-exclusion)。

UK 页面区分官方 `Fill rate`、`余额 / 初始额度` 和 `初始额度与余额差`。兼容保留 JSON 的 `used_amount`、`used_percentage` 字段，但它们只是 `initial - balance` 的派生值，**结转后不能代表累计使用量**；余额大于初始额度时差值为空。未知、未来、过期和沿用旧记录不进入当前余额概览及排序指标。UK CSV 导出使用明确的差值字段名，并保留官方状态、封锁/暂停期和产品编码。

## 数据和计算

- 原产地使用法规 PDF 的 Order Number 映射；TARIC 原始 Origin 单独保留。
- 待分配量为官方 `Total awaiting allocation (indicative)`，不会从余额中直接扣除。
- 预计超量的唯一判断是：`待分配量 > 当前余额`。
- 配额外比例 = `max(待分配量 - 当前余额, 0) / 待分配量`。
- 预估分摊税率 = `配额外比例 × 50%`。

待分配量为 0 时，预估分摊税率取 0%。该结果是按比例分配的期望值，不代表海关最终确定的实际税率。

## 每日自动更新

目标时间为每天 **07:50（Europe/Berlin，自动兼容 CET/CEST）**。

GitHub Actions 的 `schedule` 可能受平台排队影响，不能保证精确到分钟。为提高可靠性，工作流使用明确的 UTC 候选时刻，并由运行时按 `Europe/Berlin` 本地时间判断：

1. 07:45 候选任务可提前进入队列，并等待至 07:50；
2. 07:50 是主触发；
3. 后续 UTC 候选时刻用于恢复触发（冬令时最晚 08:50、夏令时最晚 09:50）；
4. 只有当天已经完成 **55/55 且 0 失败** 时，后续触发才会跳过；部分失败会自动重试。

手动运行和源代码更新不受定时门禁限制。每次有效运行会：

1. 只查询欧盟委员会 TARIC 官方页面；
2. 更新 `data/current.json`；
3. 按官方更新日期保存 `data/history/YYYY-MM-DD.json`；
4. 校验 55 个编号、计算公式和官方链接；
5. 同时获取英国官方 CSV 并校验五个 Category 4 编号；
6. 部署 GitHub Pages。

若部分编号暂时查询失败，看板会沿用上一次成功数据并明确标记；若全部失败，工作流终止且不会覆盖已部署结果。若官方页面未能解析出官方更新日期，脚本不会用当天日期冒充官方日期。

## 官方来源

[European Commission — Tariff quota consultation](https://ec.europa.eu/taxation_customs/dds2/taric/quota_consultation.jsp?Lang=en)
