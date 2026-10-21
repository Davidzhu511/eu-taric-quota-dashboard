#!/usr/bin/env python3
"""Keep the public CBAM research JSON fresh without inventing an AI research score.

GitHub Actions runs this after the V2 public-layer update.  A verified, same-day
research submission is preserved; otherwise a transparently labelled
public-data-only status replaces yesterday's stale research.  This fallback is
not a substitute for a researched 30-point overlay.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "cbam/data/current.json"
RESEARCH = ROOT / "cbam/data/research.json"
BERLIN = ZoneInfo("Europe/Berlin")

REQUIRED = ("updated_at", "status", "confidence")


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: JSON root must be an object")
    return data


def utc_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, AttributeError, TypeError):
        return None


def valid_same_day_research(research: dict, current: dict, now: datetime) -> bool:
    """Keep verified, current research rather than replacing it with fallback."""
    meta = research.get("meta") or {}
    public_meta = current.get("meta") or {}
    score = research.get("overlay_score")
    if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 30:
        return False
    if meta.get("status") not in ("scored", "validated"):
        return False
    if meta.get("confidence") not in ("medium", "high"):
        return False
    if not public_meta.get("data_date") or meta.get("public_data_date") != public_meta["data_date"]:
        return False
    researched = utc_timestamp(meta.get("updated_at", ""))
    public_checked = utc_timestamp(public_meta.get("checked_at", ""))
    if not researched or not public_checked:
        return False
    if researched < public_checked:
        return False
    if researched.astimezone(BERLIN).date() != now.astimezone(BERLIN).date():
        return False
    return True


def create_fallback(current: dict, now: datetime) -> dict:
    meta = current.get("meta") or {}
    public = current.get("public_score") or {}
    stats = (current.get("auction_analytics") or {}).get("stats") or {}
    score = public.get("score")
    score_label = f"{float(score):.1f}/70" if type(score) in (int, float) and math.isfinite(score) and 0 <= score <= 70 else "不可用"
    last = stats.get("latest_price")
    price_label = f"€{float(last):.2f}/tCO₂" if type(last) in (int, float) and math.isfinite(last) else "不可用"
    data_date = meta.get("data_date") or "未知"
    stale = meta.get("status") != "ok" or bool(meta.get("errors"))
    quality = "公共数据存在异常，详见公共层数据状态；" if stale else ""
    result = {
        "meta": {
            "updated_at": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
            "status": "public_only_fallback",
            "confidence": quality + "仅核实V2公共层；EUA远期曲线、能源基本面及持仓资金流未得到足够交叉验证，研究层不可评分",
            "producer": "github_actions",
            "public_data_date": data_date,
            "public_checked_at": meta.get("checked_at"),
            "research_completed": False,
        },
        "overlay_score": None,
        "headline": "公共数据已同步；30分研究层尚未完成可靠量化",
        "summary": (
            f"公共层V2数据日期为{data_date}，评分{score_label}，"
            f"最近一级拍卖价{price_label}。"
            "GitHub Actions已维护本次数据状态，但这不是ChatGPT完整研究报告。"
            "在远期曲线、政策、能源及仓位数据充分核实前，不给出100分总分、采购覆盖率或加速采购指令。"
        ),
        "bullets": [
            "公共层70分保留V2原始得分，不重复计算或用价格下跌直接加分。",
            "研究层30分依次为：EUA期限结构12分、ETS/CBAM/MSR/CCP政策8分、能源与工业排放6分、技术面和市场持仓4分；缺失可靠数据时不评分。",
            "2026进口义务按进口季度固定价格管理，不进行周度择时；2027及以后当年义务才按周度价格择时。",
            "Article 22(2)季度底仓需按独立法定口径和企业实际数据核算；公开网页无法验证企业义务及实际持仓。",
            "CCP购买限制、交易费用、付款锁价、回购与注销规则必须以正式生效文件为准，不把草案参数当作确定规则。",
            "如果ChatGPT研究任务写入被阻止，本自动兜底仍能更新公开状态；研究层结论缺失不代表出现采购机会。",
        ],
        "sources": [
            "https://www.eex.com/en/markets/environmentals/eu-ets1-eu-ets2-auctions/eu-ets1-auctions",
            "https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism/price-cbam-certificates_en",
        ],
    }
    return result


def main() -> None:
    now = datetime.now(timezone.utc)
    current = read_json(CURRENT)
    previous = read_json(RESEARCH) if RESEARCH.exists() else {}
    if valid_same_day_research(previous, current, now):
        print("CBAM research: preserving independently verified same-day overlay")
        return
    result = create_fallback(current, now)
    missing = [k for k in REQUIRED if not result["meta"].get(k)]
    assert not missing, f"missing research meta fields: {missing}"
    assert result["overlay_score"] is None
    RESEARCH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"CBAM research fallback written: status={result['meta']['status']}, "
          f"public_data_date={result['meta']['public_data_date']}, overlay_score=null")


if __name__ == "__main__":
    main()
