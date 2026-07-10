# EU TARIC 关税配额数据看板

公开查看钢铁产品类别 **1A、2、4A、4B** 的 EU TARIC 配额数据。看板覆盖 55 个 Order Number，并计算：

- 当前配额余额与剩余比例
- Total awaiting allocation（indicative）
- 待分配倍数
- 最近分配比例与 Critical 状态
- 预估配额外比例
- 预估分摊税率

## 预估分摊税率

```text
配额外比例 = max(待分配量 - 当前配额余额, 0) / 待分配量
预估分摊税率 = 配额外比例 × 50%
```

待分配量为 0 时，预估分摊税率取 0%。这是按比例分配的期望值，不代表海关最终确定的实际税率。

## 自动更新

GitHub Actions 使用 `Europe/Berlin` 时区，每天 07:17 自动运行，也支持在 Actions 页面手动运行。工作流会：

1. 查询欧盟委员会 TARIC 官方页面；
2. 更新 `data/current.json`；
3. 保存 `data/history/YYYY-MM-DD.json`；
4. 重新部署 GitHub Pages。

若部分编号查询失败，看板会沿用上一次成功数据并明确标记；若全部失败，工作流终止，不覆盖上一次已部署结果。

## 数据来源

[European Commission - Tariff quota consultation](https://ec.europa.eu/taxation_customs/dds2/taric/quota_consultation.jsp?Lang=en)

