"""Day-to-day and cumulative API token and cost usage tracking database engine.

Tracks token consumption, dollar cost, and wasted tokens (retries/parse errors)
per stage and provider in a thread-safe JSON database at data/api_usage.json.
"""
from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config import DATA_DIR
from core.pricing import estimate_llm_cost

log = logging.getLogger(__name__)

USAGE_DB_PATH = DATA_DIR / "api_usage.json"
_LOCK = threading.RLock()


def _get_today() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d")


def _get_timestamp() -> str:
    return datetime.datetime.now().isoformat()


def _empty_stats_dict() -> Dict[str, Any]:
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "wasted_tokens": 0,
        "cost_usd": 0.0,
        "requests": 0,
        "failed_requests": 0,
    }


def _empty_db() -> Dict[str, Any]:
    return {
        "version": 1,
        "created_at": _get_timestamp(),
        "updated_at": _get_timestamp(),
        "daily": {},
        "cumulative": {
            "stages": {},
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "wasted_tokens": 0,
            "cost_usd": 0.0,
            "requests": 0,
            "failed_requests": 0,
        },
    }


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + f".tmp_{os.getpid()}")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    for _ in range(5):
        try:
            os.replace(tmp_path, path)
            return
        except OSError:
            import time
            time.sleep(0.05)
    try:
        if tmp_path.exists():
            tmp_path.unlink()
    except OSError:
        pass


def load_usage_db() -> Dict[str, Any]:
    """Load the token usage JSON database with fallback to an empty schema."""
    with _LOCK:
        if not USAGE_DB_PATH.exists():
            db = _empty_db()
            _atomic_write_json(USAGE_DB_PATH, db)
            return db
        try:
            with open(USAGE_DB_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return _empty_db()
                return data
        except Exception as e:
            log.warning("Failed to parse %s: %s; starting clean database", USAGE_DB_PATH, e)
            return _empty_db()


def _add_stats(target: Dict[str, Any], prompt_tok: int, comp_tok: int, wasted_tok: int, cost: float, is_failure: bool) -> None:
    target["prompt_tokens"] = target.get("prompt_tokens", 0) + prompt_tok
    target["completion_tokens"] = target.get("completion_tokens", 0) + comp_tok
    target["total_tokens"] = target.get("total_tokens", 0) + prompt_tok + comp_tok
    target["wasted_tokens"] = target.get("wasted_tokens", 0) + wasted_tok
    target["cost_usd"] = round(target.get("cost_usd", 0.0) + cost, 6)
    target["requests"] = target.get("requests", 0) + 1
    if is_failure:
        target["failed_requests"] = target.get("failed_requests", 0) + 1


def record_usage(
    stage: str,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    wasted_tokens: int = 0,
    is_failure: bool = False,
    provider_name: str = "",
    project_id: str = "",
    calculated_cost: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Record an LLM call or retry event into the central daily & cumulative database.
    
    If `is_failure` is True or `wasted_tokens` > 0, those tokens are marked as wasted.
    """
    stage_key = (stage or "unknown").lower().strip()
    # Normalize stage alias
    if stage_key in ("scene_planning", "storyboard"):
        stage_key = "scenes"
    elif stage_key in ("prompt_generation", "prompt_translation"):
        stage_key = "prompts"

    model_key = (model or provider_name or "unknown").strip()
    total_tokens = prompt_tokens + completion_tokens

    # Determine dollar cost
    if calculated_cost is not None and calculated_cost >= 0:
        cost = calculated_cost
    else:
        cost, _ = estimate_llm_cost(model_key, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, requests=1)

    today = _get_today()

    with _LOCK:
        db = load_usage_db()
        db["updated_at"] = _get_timestamp()

        # 1. Update Daily Bucket
        daily_map = db.setdefault("daily", {})
        day_bucket = daily_map.setdefault(today, {
            "date": today,
            "stages": {},
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "wasted_tokens": 0,
            "cost_usd": 0.0,
            "requests": 0,
            "failed_requests": 0,
        })

        # Daily overall stats
        _add_stats(day_bucket, prompt_tokens, completion_tokens, wasted_tokens, cost, is_failure)

        # Daily stage stats
        day_stages = day_bucket.setdefault("stages", {})
        stage_entry = day_stages.setdefault(stage_key, _empty_stats_dict())
        stage_entry.setdefault("models", {})
        _add_stats(stage_entry, prompt_tokens, completion_tokens, wasted_tokens, cost, is_failure)

        # Daily model within stage
        model_entry = stage_entry["models"].setdefault(model_key, _empty_stats_dict())
        _add_stats(model_entry, prompt_tokens, completion_tokens, wasted_tokens, cost, is_failure)

        # 2. Update Cumulative Bucket
        cumul = db.setdefault("cumulative", {
            "stages": {},
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "wasted_tokens": 0,
            "cost_usd": 0.0,
            "requests": 0,
            "failed_requests": 0,
        })
        _add_stats(cumul, prompt_tokens, completion_tokens, wasted_tokens, cost, is_failure)

        cumul_stages = cumul.setdefault("stages", {})
        cumul_stage = cumul_stages.setdefault(stage_key, _empty_stats_dict())
        cumul_stage.setdefault("models", {})
        _add_stats(cumul_stage, prompt_tokens, completion_tokens, wasted_tokens, cost, is_failure)

        cumul_model = cumul_stage["models"].setdefault(model_key, _empty_stats_dict())
        _add_stats(cumul_model, prompt_tokens, completion_tokens, wasted_tokens, cost, is_failure)

        _atomic_write_json(USAGE_DB_PATH, db)

    return {
        "stage": stage_key,
        "model": model_key,
        "total_tokens": total_tokens,
        "wasted_tokens": wasted_tokens,
        "cost_usd": cost,
        "is_failure": is_failure,
    }


def get_token_summary(date: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns ranking of stages by accumulative token consumption,
    including wasted token counts, percentages, and costs.
    """
    db = load_usage_db()
    if date:
        scope = db.get("daily", {}).get(date, {})
        scope_title = f"Daily ({date})"
    else:
        scope = db.get("cumulative", {})
        scope_title = "All-Time Cumulative"

    stages_data = scope.get("stages", {})
    ranked_stages = []

    for stage_name, data in stages_data.items():
        tot = data.get("total_tokens", 0)
        wasted = data.get("wasted_tokens", 0)
        cost = round(data.get("cost_usd", 0.0), 4)
        reqs = data.get("requests", 0)
        fails = data.get("failed_requests", 0)
        waste_pct = round((wasted / tot * 100.0), 1) if tot > 0 else 0.0

        ranked_stages.append({
            "stage": stage_name,
            "total_tokens": tot,
            "prompt_tokens": data.get("prompt_tokens", 0),
            "completion_tokens": data.get("completion_tokens", 0),
            "wasted_tokens": wasted,
            "waste_pct": waste_pct,
            "cost_usd": cost,
            "requests": reqs,
            "failed_requests": fails,
            "models": data.get("models", {}),
        })

    # Sort stages by total tokens descending
    ranked_stages.sort(key=lambda s: s["total_tokens"], reverse=True)

    # Calculate overall totals
    tot_tokens = scope.get("total_tokens", 0)
    wasted_tokens = scope.get("wasted_tokens", 0)
    overall_waste_pct = round((wasted_tokens / tot_tokens * 100.0), 1) if tot_tokens > 0 else 0.0

    return {
        "scope": scope_title,
        "updated_at": db.get("updated_at"),
        "total_tokens": tot_tokens,
        "prompt_tokens": scope.get("prompt_tokens", 0),
        "completion_tokens": scope.get("completion_tokens", 0),
        "wasted_tokens": wasted_tokens,
        "waste_pct": overall_waste_pct,
        "cost_usd": round(scope.get("cost_usd", 0.0), 4),
        "total_requests": scope.get("requests", 0),
        "total_failed_requests": scope.get("failed_requests", 0),
        "top_consumer": ranked_stages[0]["stage"] if ranked_stages else "None",
        "stages": ranked_stages,
    }


def get_daily_history(days: int = 14) -> List[Dict[str, Any]]:
    """Get the day-to-day token and cost history for the past N days."""
    db = load_usage_db()
    daily_records = db.get("daily", {})
    sorted_dates = sorted(daily_records.keys(), reverse=True)[:days]

    history = []
    for d in sorted_dates:
        entry = daily_records[d]
        tot = entry.get("total_tokens", 0)
        wasted = entry.get("wasted_tokens", 0)
        waste_pct = round((wasted / tot * 100.0), 1) if tot > 0 else 0.0

        history.append({
            "date": d,
            "total_tokens": tot,
            "wasted_tokens": wasted,
            "waste_pct": waste_pct,
            "cost_usd": round(entry.get("cost_usd", 0.0), 4),
            "requests": entry.get("requests", 0),
            "stages_count": len(entry.get("stages", {})),
        })
    return history


def print_cli_summary(date: Optional[str] = None) -> None:
    """Print an attractive console report showing stage token rankings and wasted tokens."""
    summary = get_token_summary(date=date)
    scope = summary["scope"]
    stages = summary["stages"]

    print("=" * 88)
    print(f"📊  API TOKEN & COST CONSUMPTION REPORT: {scope.upper()}")
    print("=" * 88)
    print(f"  Last Updated: {summary.get('updated_at', 'N/A')}")
    print(f"  Total Tokens:   {summary['total_tokens']:,} (Prompt: {summary['prompt_tokens']:,} | Comp: {summary['completion_tokens']:,})")
    print(f"  Wasted Tokens:  {summary['wasted_tokens']:,} ({summary['waste_pct']}% of all tokens)")
    print(f"  Total Cost:     ${summary['cost_usd']:.4f} USD")
    print(f"  Total Calls:    {summary['total_requests']} (Failed/Retried: {summary['total_failed_requests']})")
    print(f"  Top Stage:      {summary['top_consumer'].upper()}")
    print("-" * 88)

    if not stages:
        print("  No API token activity recorded yet. Run a pipeline stage to begin tracking!")
        print("=" * 88)
        return

    # Table Header
    header = f"{'Rank':<5} | {'Stage':<18} | {'Tokens':<12} | {'Wasted':<10} | {'Waste %':<8} | {'Cost USD':<10} | {'Reqs (Fails)'}"
    print(header)
    print("-" * 88)

    for i, s in enumerate(stages, start=1):
        rank_str = f"#{i}"
        stage_str = s["stage"]
        tok_str = f"{s['total_tokens']:,}"
        wasted_str = f"{s['wasted_tokens']:,}"
        pct_str = f"{s['waste_pct']:.1f}%"
        cost_str = f"${s['cost_usd']:.4f}"
        req_str = f"{s['requests']} ({s['failed_requests']})"

        row = f"{rank_str:<5} | {stage_str:<18} | {tok_str:<12} | {wasted_str:<10} | {pct_str:<8} | {cost_str:<10} | {req_str}"
        print(row)

        # Print model sub-breakdown if multiple
        models = s.get("models", {})
        if len(models) > 0:
            for m_name, m_data in models.items():
                m_tok = f"{m_data.get('total_tokens', 0):,}"
                m_wasted = f"{m_data.get('wasted_tokens', 0):,}"
                m_cost = f"${m_data.get('cost_usd', 0.0):.4f}"
                print(f"      └─ {m_name:<16} : {m_tok} tok (wasted: {m_wasted}, cost: {m_cost})")

    print("=" * 88)


def main() -> None:
    parser = argparse.ArgumentParser(description="API Token & Waste Tracker")
    parser.add_argument("--summary", action="store_true", help="Print all-time cumulative token summary")
    parser.add_argument("--today", action="store_true", help="Print today's token usage summary")
    parser.add_argument("--date", type=str, default=None, help="Print token summary for specific date (YYYY-MM-DD)")
    parser.add_argument("--history", type=int, default=0, help="Print daily history for last N days")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of table")
    parser.add_argument("--reset", action="store_true", help="Reset token usage database")

    args = parser.parse_args()

    if args.reset:
        with _LOCK:
            _atomic_write_json(USAGE_DB_PATH, _empty_db())
        print(f"✅ Reset token database at {USAGE_DB_PATH}")
        return

    if args.history > 0:
        hist = get_daily_history(args.history)
        if args.json:
            print(json.dumps(hist, indent=2))
        else:
            print("=" * 60)
            print(f"📅  DAILY API USAGE HISTORY (LAST {args.history} DAYS)")
            print("=" * 60)
            print(f"{'Date':<12} | {'Tokens':<12} | {'Wasted':<10} | {'Waste %':<8} | {'Cost USD':<10}")
            print("-" * 60)
            for h in hist:
                print(f"{h['date']:<12} | {h['total_tokens']:<12,} | {h['wasted_tokens']:<10,} | {h['waste_pct']:<8.1f}% | ${h['cost_usd']:.4f}")
            print("=" * 60)
        return

    target_date = _get_today() if args.today else args.date
    if args.json:
        print(json.dumps(get_token_summary(target_date), indent=2))
    else:
        print_cli_summary(date=target_date)


if __name__ == "__main__":
    main()
