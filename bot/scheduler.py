"""Promemoria giornalieri. I job vivono in memoria, quindi vanno ricreati
a ogni avvio leggendo il DB: su Railway il container riparte spesso."""

from __future__ import annotations

import datetime as dt
import logging
from zoneinfo import ZoneInfo

from telegram.ext import Application, ContextTypes

from .config import settings
from .db import all_users_with_reminder, get_user
from .domain import DAY_ORDER
from .render import render_today
from .schemas import Plan

logger = logging.getLogger(__name__)


async def _send_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id: int = context.job.chat_id
    user = await get_user(chat_id)
    if user is None or not user.plan:
        return

    try:
        plan = Plan.model_validate(user.plan)
    except Exception:
        logger.exception("Piano illeggibile per %s", chat_id)
        return

    today_key = DAY_ORDER[dt.datetime.now(ZoneInfo(user.tz)).weekday()]
    await context.bot.send_message(
        chat_id, render_today(plan, today_key), parse_mode="HTML"
    )


def job_name(chat_id: int) -> str:
    return f"reminder_{chat_id}"


def schedule_reminder(app: Application, chat_id: int, hour: int, tz: str | None = None) -> None:
    """Crea (o sostituisce) il job giornaliero dell'utente."""
    for job in app.job_queue.get_jobs_by_name(job_name(chat_id)):
        job.schedule_removal()

    tzinfo = ZoneInfo(tz or settings.default_tz)
    app.job_queue.run_daily(
        _send_reminder,
        time=dt.time(hour=hour, minute=0, tzinfo=tzinfo),
        name=job_name(chat_id),
        chat_id=chat_id,
    )


def cancel_reminder(app: Application, chat_id: int) -> None:
    for job in app.job_queue.get_jobs_by_name(job_name(chat_id)):
        job.schedule_removal()


async def restore_reminders(app: Application) -> None:
    """Chiamata al post_init: ripristina i job dopo un riavvio."""
    users = await all_users_with_reminder()
    for user in users:
        schedule_reminder(app, user.chat_id, user.reminder_hour, user.tz)
    logger.info("Ripristinati %s promemoria", len(users))
