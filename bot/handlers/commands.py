"""Comandi fuori dall'onboarding: consultazione, rigenerazione, promemoria."""

from __future__ import annotations

import datetime as dt
import logging
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from ..db import delete_user, get_user, upsert_user
from ..domain import DAY_ORDER
from ..keyboards import hours_keyboard
from ..planner import generate_plan
from ..render import render_plan, render_today
from ..scheduler import cancel_reminder, schedule_reminder
from ..schemas import Plan

logger = logging.getLogger(__name__)

NO_PLAN = "Non hai ancora un piano. Comincia con /start."


async def _load_plan(chat_id: int) -> Plan | None:
    user = await get_user(chat_id)
    if user is None or not user.plan:
        return None
    try:
        return Plan.model_validate(user.plan)
    except Exception:
        logger.exception("Piano non validabile per %s", chat_id)
        return None


async def cmd_piano(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    plan = await _load_plan(update.effective_chat.id)
    if plan is None:
        await update.message.reply_text(NO_PLAN)
        return
    for message in render_plan(plan):
        await update.message.reply_text(message, parse_mode="HTML")


async def cmd_oggi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = await get_user(chat_id)
    plan = await _load_plan(chat_id)
    if plan is None or user is None:
        await update.message.reply_text(NO_PLAN)
        return
    today_key = DAY_ORDER[dt.datetime.now(ZoneInfo(user.tz)).weekday()]
    await update.message.reply_text(
        render_today(plan, today_key), parse_mode="HTML"
    )


async def cmd_rigenera(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user = await get_user(chat_id)
    if user is None or not user.profile:
        await update.message.reply_text(NO_PLAN)
        return

    await update.message.reply_text("🧪 Rigenero il piano…")
    await context.bot.send_chat_action(chat_id, ChatAction.TYPING)
    try:
        plan = await generate_plan(user.profile)
    except Exception:
        logger.exception("Rigenerazione fallita per %s", chat_id)
        await update.message.reply_text("😕 Non ci sono riuscito. Riprova fra poco.")
        return

    await upsert_user(chat_id, plan=plan.model_dump())
    for message in render_plan(plan):
        await update.message.reply_text(message, parse_mode="HTML")


async def cmd_promemoria(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "A che ora vuoi il promemoria?", reply_markup=hours_keyboard("setr")
    )


async def on_set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    raw = query.data.split(":", 1)[1]
    chat_id = query.message.chat_id

    if raw == "off":
        cancel_reminder(context.application, chat_id)
        await upsert_user(chat_id, reminder_hour=None)
        await query.edit_message_text("🔕 Promemoria disattivato.")
        return

    hour = int(raw)
    user = await upsert_user(chat_id, reminder_hour=hour)
    schedule_reminder(context.application, chat_id, hour, user.tz)
    await query.edit_message_text(f"⏰ Promemoria impostato alle {hour:02d}:00.")


async def cmd_cancella(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    cancel_reminder(context.application, chat_id)
    await delete_user(chat_id)
    await update.message.reply_text(
        "Ho cancellato tutti i tuoi dati. Se vuoi ricominciare: /start."
    )


async def cmd_aiuto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "<b>Comandi disponibili</b>\n\n"
        "/start — configurazione iniziale\n"
        "/oggi — cosa fare oggi\n"
        "/piano — piano settimanale completo\n"
        "/rigenera — nuova versione del piano, stesso profilo\n"
        "/modifica — rifai la configurazione\n"
        "/promemoria — orario della notifica\n"
        "/dimentica — azzera il filo del discorso\n"
        "/cancella — elimina i tuoi dati\n\n"
        "Puoi anche scrivermi liberamente: conosco il tuo piano, quindi posso "
        "dirti cosa saltare se sei di fretta o spiegarti perché un trattamento "
        "sta in un certo giorno.\n\n"
        "<i>Questo bot non sostituisce il parere di un dermatologo.</i>",
        parse_mode="HTML",
    )


def register(app) -> None:
    app.add_handler(CommandHandler("piano", cmd_piano))
    app.add_handler(CommandHandler("oggi", cmd_oggi))
    app.add_handler(CommandHandler("rigenera", cmd_rigenera))
    app.add_handler(CommandHandler("promemoria", cmd_promemoria))
    app.add_handler(CommandHandler("cancella", cmd_cancella))
    app.add_handler(CommandHandler(["aiuto", "help"], cmd_aiuto))
    app.add_handler(CallbackQueryHandler(on_set_reminder, pattern=r"^setr:"))
