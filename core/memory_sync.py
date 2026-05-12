"""Sync resolved StockSage outcomes into TradingAgents memory."""

import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from config import Settings
from config import settings as _default_settings
from core.models import Analysis, Outcome

MEMORY_ENTRY_SEPARATOR = "\n\n<!-- ENTRY_END -->\n\n"


@dataclass(frozen=True)
class MemorySyncReport:
    resolved_rows: int
    appended: int
    updated: int
    unchanged: int

    @property
    def changed(self) -> int:
        return self.appended + self.updated


def sync_resolved_outcomes_to_memory(
    db: Session,
    cfg: Settings = _default_settings,
) -> MemorySyncReport:
    rows = (
        db.query(Analysis)
        .join(Outcome)
        .filter(Analysis.status == "completed")
        .order_by(Analysis.trade_date.asc(), Analysis.id.asc())
        .all()
    )
    if not rows:
        return MemorySyncReport(resolved_rows=0, appended=0, updated=0, unchanged=0)

    log_path = Path(cfg.memory_log_path).expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    update_blocks = {_analysis_key(row): _render_resolved_entry(row) for row in rows}
    existing_blocks = _read_blocks(log_path)

    appended = 0
    updated = 0
    unchanged = 0
    replaced: set[tuple[str, str]] = set()
    new_blocks: list[str] = []

    for block in existing_blocks:
        key = _entry_key(block)
        if key not in update_blocks:
            new_blocks.append(block)
            continue

        if key in replaced:
            continue

        replacement = update_blocks[key]
        replaced.add(key)
        if _normalise_block(block) == _normalise_block(replacement):
            unchanged += 1
            new_blocks.append(block)
        else:
            updated += 1
            new_blocks.append(replacement)

    for key, block in update_blocks.items():
        if key in replaced:
            continue
        appended += 1
        new_blocks.append(block)

    if appended or updated or len(new_blocks) != len(existing_blocks):
        _write_blocks(log_path, new_blocks)

    return MemorySyncReport(
        resolved_rows=len(rows),
        appended=appended,
        updated=updated,
        unchanged=unchanged,
    )


def _read_blocks(log_path: Path) -> list[str]:
    if not log_path.exists():
        return []
    text = log_path.read_text(encoding="utf-8")
    return [block.strip() for block in text.split(MEMORY_ENTRY_SEPARATOR) if block.strip()]


def _write_blocks(log_path: Path, blocks: list[str]) -> None:
    text = MEMORY_ENTRY_SEPARATOR.join(block.strip() for block in blocks if block.strip())
    if text:
        text = f"{text}{MEMORY_ENTRY_SEPARATOR}"
    tmp_path = log_path.with_suffix(".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(log_path)


def _analysis_key(row: Analysis) -> tuple[str, str]:
    return str(row.trade_date), row.ticker.upper()


def _entry_key(block: str) -> tuple[str, str] | None:
    first_line = block.strip().splitlines()[0].strip() if block.strip() else ""
    if not (first_line.startswith("[") and first_line.endswith("]")):
        return None
    fields = [field.strip() for field in first_line[1:-1].split("|")]
    if len(fields) < 2:
        return None
    return fields[0], fields[1].upper()


def _render_resolved_entry(row: Analysis) -> str:
    outcome = row.outcome
    rating = row.rating or "Unknown"
    raw_pct = f"{outcome.raw_return:+.1%}"
    alpha_pct = f"{outcome.alpha_return:+.1%}"
    reflection = outcome.reflection or (
        f"StockSage resolved this call at raw {raw_pct}, alpha {alpha_pct} over "
        f"{outcome.holding_days} trading day(s)."
    )
    tag = (
        f"[{row.trade_date} | {row.ticker} | {rating} | {raw_pct} | {alpha_pct} | "
        f"{outcome.holding_days}d]"
    )
    return f"{tag}\n\nDECISION:\n{_decision_text(row)}\n\nREFLECTION:\n{reflection}"


def _decision_text(row: Analysis) -> str:
    from_state = _decision_from_full_state(row)
    if from_state:
        return from_state

    parts = [f"**Rating**: {row.rating or 'Unknown'}"]
    if row.executive_summary:
        parts.append(f"**Executive Summary**: {row.executive_summary}")
    if row.investment_thesis:
        parts.append(f"**Investment Thesis**: {row.investment_thesis}")
    if row.price_target is not None:
        parts.append(f"**Price Target**: {row.price_target}")
    if row.time_horizon:
        parts.append(f"**Time Horizon**: {row.time_horizon}")
    return "\n\n".join(parts)


def _decision_from_full_state(row: Analysis) -> str | None:
    raw = row.detail.full_state_json if row.detail is not None else None
    if not raw:
        return None
    try:
        full_state = json.loads(raw)
    except json.JSONDecodeError:
        return None
    decision = full_state.get("final_trade_decision")
    if isinstance(decision, str) and decision.strip():
        return decision.strip()
    return None


def _normalise_block(block: str) -> str:
    return block.strip().replace("\r\n", "\n")
