# EU TARIC 关税配额数据看板

[![Update TARIC dashboard](https://github.com/Davidzhu511/eu-taric-quota-dashboard/actions/workflows/update-and-deploy.yml/badge.svg)](https://github.com/Davidzhu511/eu-taric-quota-dashboard/actions/workflows/update-and-deploy.yml)

公开看板：<https://davidzhu511.github.io/eu-taric-quota-dashboard/>

看板展示钢铁产品类别 **1A、2、4A、4B** 的 55 个 EU TARIC Order Number，并提供筛选、搜索、历史快照、CSV 和 JSON 导出。

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
5. 部署 GitHub Pages。

若部分编号暂时查询失败，看板会沿用上一次成功数据并明确标记；若全部失败，工作流终止且不会覆盖已部署结果。若官方页面未能解析出官方更新日期，脚本不会用当天日期冒充官方日期。

## 官方来源

[European Commission — Tariff quota consultation](https://ec.europa.eu/taxation_customs/dds2/taric/quota_consultation.jsp?Lang=en)
