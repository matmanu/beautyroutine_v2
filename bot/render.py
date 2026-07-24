"""Piano -> messaggi Telegram. Usiamo parse_mode HTML: l'escaping è molto
meno doloroso di MarkdownV2."""

from __future__ import annotations

from html import escape

from .domain import DAY_ORDER, DAYS
from .schemas import DayPlan, Plan, RoutineBlock, Step

MAX_LEN = 3800  # margine sotto il limite Telegram di 4096


def _step_line(step: Step) -> str:
    head = f"<b>{step.ordine}.</b> {escape(step.nome)}"
    meta = [f"{step.durata_min} min"]
    if step.strumento:
        meta.append(escape(step.strumento))
    line = f"{head} <i>({' · '.join(meta)})</i>"
    if step.note:
        line += f"\n   <i>{escape(step.note)}</i>"
    return line


def render_daily(blocks: list[RoutineBlock]) -> str:
    icons = {"mattina": "🌅", "sera": "🌙"}
    parts = ["<b>ROUTINE QUOTIDIANA</b>\nOgni giorno, anche fuori dai giorni dedicati."]
    for block in sorted(blocks, key=lambda b: b.momento != "mattina"):
        parts.append(
            f"\n{icons.get(block.momento, '•')} <b>{block.momento.upper()}</b> "
            f"— {block.durata_totale_min} min"
        )
        parts.extend(_step_line(step) for step in block.passaggi)
    return "\n".join(parts)


def render_day(day: DayPlan) -> str:
    parts = [
        f"📅 <b>{DAYS.get(day.giorno, day.giorno).upper()}</b> — {escape(day.focus)}",
        f"<i>Durata: {day.durata_totale_min} min</i>\n",
    ]
    parts.extend(_step_line(step) for step in day.trattamenti)
    return "\n".join(parts)


def render_week(week: list[DayPlan]) -> list[str]:
    ordered = sorted(
        week,
        key=lambda d: DAY_ORDER.index(d.giorno) if d.giorno in DAY_ORDER else 99,
    )
    chunks: list[str] = []
    current = "<b>GIORNI DEDICATI</b>\n"
    for day in ordered:
        block = render_day(day) + "\n"
        if len(current) + len(block) > MAX_LEN:
            chunks.append(current.rstrip())
            current = ""
        current += block + "\n"
    if current.strip():
        chunks.append(current.rstrip())
    return chunks


def render_footer(plan: Plan) -> str:
    rules = "\n".join(f"• {escape(rule)}" for rule in plan.regole_sicurezza)
    return (
        f"⚠️ <b>DA TENERE A MENTE</b>\n{rules}\n\n"
        f"📈 <b>COME EVOLVERE</b>\n{escape(plan.progressione)}"
    )


def render_plan(plan: Plan) -> list[str]:
    """Restituisce la lista dei messaggi da inviare in sequenza."""
    messages = [
        f"✨ <b>{escape(plan.titolo)}</b>\n\n{escape(plan.razionale)}",
        render_daily(plan.routine_quotidiana),
    ]
    messages.extend(render_week(plan.settimana))
    messages.append(render_footer(plan))
    return messages


def render_today(plan: Plan, weekday_key: str) -> str:
    """Messaggio del promemoria giornaliero."""
    evening = next(
        (b for b in plan.routine_quotidiana if b.momento == "sera"), None
    )
    today = next((d for d in plan.settimana if d.giorno == weekday_key), None)

    if today is None:
        base = f"🌙 <b>{DAYS.get(weekday_key, '')}</b> — giorno leggero, solo routine base.\n"
        if evening:
            base += "\n" + "\n".join(_step_line(s) for s in evening.passaggi)
        return base

    return (
        f"🔔 <b>{DAYS.get(weekday_key, '')}</b> — oggi tocca a: {escape(today.focus)}\n"
        f"<i>Circa {today.durata_totale_min} minuti</i>\n\n"
        + "\n".join(_step_line(s) for s in today.trattamenti)
    )
