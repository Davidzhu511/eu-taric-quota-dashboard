# EU TARIC 关税配额数据看板

[![Update TARIC dashboard](https://github.com/Davidzhu511/eu-taric-quota-dashboard/actions/workflows/update-and-deploy.yml/badge.svg)](https://github.com/Davidzhu511/eu-taric-quota-dashboard/actions/workflows/update-and-deploy.yml)

英文版：[EU English](https://davidzhu511.github.io/eu-taric-quota-dashboard/en.html) · [UK English](https://davidzhu511.github.io/eu-taric-quota-dashboard/uk-en.html)。页面顶部可切换语言和地区，两种语言共用数据、计算和历史证据。

顶部“本季度中国适用配额”表由 `scripts/build_quarterly_summary.py` 从当前季度历史快照重建，保存到 `data/quarterly-summary.json`。仅在开季申报接受日、耗尽日及有效期一致，且记录有效、历史获配比例无冲突时展示 `(100%-获配比例)×50%`。这只是对应有效分配批次在相同单位完税价格下的加权配额关税，不是全季度统一税率，不含其他税费；最终以每票海关分配及税单为准。后续最近比例为0不会覆盖开季正比例。缺失、冲突或季度切换后无证据时显示无法计算。UK CSV没有同日获配比例，不能从Fill rate或余额推算，表内明确显示未提供。

英文页面由 `scripts/build_english_pages.py` 从同一UI源码生成；未翻译中文UI会让构建失败，避免中英文漂移。共享主题、地区及语言导航由 `scripts/inject_uk_nav.py` 生成。

公开看板：<https://davidzhu511.github.io/eu-taric-quota-dashboard/>

看板展示钢铁产品类别 **1A、2、4A、4B** 的 55 个 EU TARIC Order Number，并提供筛选、搜索、历史快照、CSV 和 JSON 导出。

同一项目的 [英国 Category 4 看板](https://davidzhu511.github.io/eu-taric-quota-dashboard/uk.html) 跟踪法规 Table 4 的五个编号（058604–058608）。两个看板按选定业务范围展示，并非 EU/UK 官方全部钢铁配额的完整列表。

临近季度交替时，EU 页面另列 TARIC 已公布的下一有效期初始额度；UK 页面列出官方 CSV 中的下一季度五个额度。**未来额度与当前余额分开**。UK `Future` 记录的 `#NA` 余额显示为“尚未公布”；英国季度未用额度可结转，下一季度初始额度不等于开季实际余额。

UK Category 4 结转在季度结束后的第 20 个工作日生效，仅限同一配额年度；前一季度申请窗口截至随后月份第 19 个工作日。旧合同过渡豁免仅覆盖 2026-07-01 至 2026-09-30 的进口。HMRC 通知季度额度已分配 90% 时指定为 Critical，须提供全额税款担保。50% 为本钢铁措施的配额外税率，适用的反倾销/反补贴税另计。依据：[GOV.UK 实施说明](https://www.gov.uk/government/publications/uks-steel-trade-measure-from-1-july-2026/implementation-notifications-on-the-transitional-exemption-quota-administration-and-the-ukraine-exclusion)。

UK 页面区分官方 `Fill rate`、`余额 / 初始额度` 和 `初始额度与余额差`。兼容保留 JSON 的 `used_amount`、`used_percentage` 字段，但它们只是 `initial - balance` 的派生值，**结转后不能代表累计使用量**；余额大于初始额度时差值为空。未知、未来、过期和沿用旧记录不进入当前余额概览及排序指标。UK CSV 导出使用明确的差值字段名，并保留官方状态、封锁/暂停期和产品编码。

## GitHub 与 ChatGPT 分工

GitHub Actions 负责 EU／UK 官方采集、计算、历史快照、有限补抓和 Pages 发布校验。EU 和 UK 各自判断采集成功；单地失败时，可发布另一地的合格数据，失败地沿用上次快照并在运行日志中保留真实失败。补抓工作流同时检查最近刷新时段和线上发布清单。

ChatGPT 优先读取 [配额变化清单](data/quota-events.json)，根据官方原文判断报价、排船和报关影响。清单保留最近 45 天的事件及稳定编号，含辖区数据来源、日期、前后值和规则核验状态。同季度内对比余额；换季产生单独事件。待分配压力跨越 70% 或 100%、显著余额下降、耗尽、状态变化、初始额度调整及开季分配证据等均可进入清单。余额回升或超过初始额度需要结合官方规则判断原因及是否可申请。

`checked_at` 是抓取时间，`official_update_date` 是官方资料日期。周末或官方未更新时两者可以不同。EU 的缺失待分配量保持未知，真实余额仍可展示。看板中的未来期初始额度来自 TARIC；[已核验分配规则](data/quota-policy.json)按明确有效期维护，期满待核对后续法规与逐票适用资格。

## 数据和计算

- 原产地使用法规 PDF 的 Order Number 映射；TARIC 原始 Origin 单独保留。
- 待分配量为官方 `Total awaiting allocation (indicative)`，不会从余额中直接扣除。
- 预计超量的唯一判断是：`待分配量 > 当前余额`。
- 配额外比例 = `max(待分配量 - 当前余额, 0) / 待分配量`。
- 预估分摊税率 = `配额外比例 × 50%`。

待分配量为 0 时，页面与导出不显示分摊税率，标记“无待分配申请”；兼容保留源 JSON 的历史派生字段。余额为零时，新增申请应按配额外 50% 评估，不能将无待分配申请理解为免税。上述估算把已知待分配申请合并计算，不是季度税率：不同申报接受日期按先后顺序，同日超额申请按比例分配，最终以海关实际获配结果为准。“最近分配比例”只适用于官方最近一次分配批次，不是季度使用率。

## 自动刷新与发布

| 德国时间（Europe/Berlin） | 刷新目标 |
| --- | --- |
| 每天 07:50 | 晨间 EU／UK 刷新 |
| 工作日 14:20 | 捕捉同日后续官方更新 |
| 季度首月 1–10 日、22 日至月底及次月 1–3 日 11:20、16:10 | 加密检查开季分配及结转发布 |
| 每天 08:37、12:37、15:37、17:37 | 检查最近应执行时段，按需要补抓或重新发布 |

实际触发时间受 Actions 排队影响。每个源独立对照最近应执行时段的抓取时间、法规有效期及完整性。完整的上午快照可继续展示，下午按新时段检查。工作流记录官方日期并验证线上发布清单与关键文件指纹。EU 开季正比例证据即使被同日新快照覆盖也会独立保留。

## 官方来源

[European Commission — Tariff quota consultation](https://ec.europa.eu/taxation_customs/dds2/taric/quota_consultation.jsp?Lang=en)
