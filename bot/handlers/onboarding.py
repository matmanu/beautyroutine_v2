"""Flusso di onboarding a stati. Ogni step è una tastiera inline;
lo stato temporaneo vive in context.user_data finché non si salva a DB."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from ..db import upsert_user
from ..domain import (
    ACTIVES,
    CONCERNS,
    DAYS,
    DURATIONS,
    SAFETY_FLAGS,
    SKIN_TYPES,
    TOOLS,
)
from ..keyboards import ADD, DONE, multiselect, singleselect, hours_keyboard
from ..planner import generate_plan
from ..render import render_plan
from ..scheduler import schedule_reminder

logger = logging.getLogger(__name__)

TOOLS_STATE, TOOLS_ADD, DAYS_STATE, DURATION, SKIN, CONCERNS_STATE, ACTIVES_STATE, SAFETY, REMINDER = range(9)

# Strumenti che richiedono lo screening di sicurezza
ELECTRIC_TOOLS = {"nuface", "sauna", "dermaroller"}


def _sel(context: ContextTypes.DEFAULT_TYPE, key: str) -> set[str]:
    return context.user_data.setdefault(f"sel_{key}", set())


async def _edit_markup(query, markup) -> None:
    """Telegram rifiuta l'edit se la tastiera risultante è identica a quella
    già a schermo. Succede quando un tap non cambia nulla, ad esempio
    ritoccando "Nessuna" quand'è già l'unica selezione. Non è un errore vero."""
    try:
        await query.edit_message_reply_markup(markup)
    except BadRequest as exc:
        if "not modified" not in str(exc).lower():
            raise


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "✨ <b>Ciao! Costruiamo insieme la tua beauty routine settimanale.</b>\n\n"
        "Ti faccio sei domande veloci, poi genero un piano calibrato su di te: "
        "una routine base per tutti i giorni e trattamenti mirati nei giorni che scegli.\n\n"
        "<b>1/6 — Quali strumenti hai a disposizione?</b>\n"
        "Tocca per selezionare, poi premi Fatto.",
        parse_mode="HTML",
        reply_markup=multiselect(
            TOOLS, set(), "t", add_label="➕ Aggiungi altro"
        ),
    )
    return TOOLS_STATE


async def on_tools(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]
    selected = _sel(context, "tools")

    if choice == ADD:
        await query.edit_message_text(
            "Scrivimi il nome dello strumento che vuoi aggiungere.\n"
            "<i>Puoi elencarne più di uno separandoli con una virgola.</i>",
            parse_mode="HTML",
        )
        return TOOLS_ADD

    if choice == DONE:
        custom = context.user_data.get("custom_tools", [])
        if not selected and not custom:
            await query.answer("Selezionane almeno uno 🙂", show_alert=True)
            return TOOLS_STATE
        return await _ask_days(query, context)

    selected.symmetric_difference_update({choice})
    await _edit_markup(
        query,
        multiselect(
            _tools_with_custom(context), selected, "t", add_label="➕ Aggiungi altro"
        ),
    )
    return TOOLS_STATE


def _tools_with_custom(context: ContextTypes.DEFAULT_TYPE) -> dict[str, str]:
    """Gli strumenti custom vengono mostrati in coda, già spuntati."""
    options = dict(TOOLS)
    for name in context.user_data.get("custom_tools", []):
        options[f"custom_{name}"] = name
    return options


async def on_tools_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    names = [n.strip() for n in update.message.text.split(",") if n.strip()]
    custom = context.user_data.setdefault("custom_tools", [])
    custom.extend(n for n in names if n not in custom)

    selected = _sel(context, "tools")
    selected.update(f"custom_{n}" for n in names)

    await update.message.reply_text(
        f"Aggiunto: <b>{', '.join(names)}</b>\n\nAltro da selezionare?",
        parse_mode="HTML",
        reply_markup=multiselect(
            _tools_with_custom(context), selected, "t", add_label="➕ Aggiungi altro"
        ),
    )
    return TOOLS_STATE


async def _ask_days(query, context) -> int:
    await query.edit_message_text(
        "<b>2/6 — In quali giorni vuoi dedicarti alla routine estesa?</b>\n"
        "<i>Negli altri giorni resterà solo la routine base mattina/sera.</i>",
        parse_mode="HTML",
        reply_markup=multiselect(DAYS, set(), "d", columns=2),
    )
    return DAYS_STATE


async def on_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]
    selected = _sel(context, "days")

    if choice == DONE:
        if not selected:
            await query.answer("Scegli almeno un giorno 🙂", show_alert=True)
            return DAYS_STATE
        await query.edit_message_text(
            "<b>3/6 — Quanto tempo hai per ciascuna sessione?</b>",
            parse_mode="HTML",
            reply_markup=singleselect(DURATIONS, "dur"),
        )
        return DURATION

    selected.symmetric_difference_update({choice})
    await _edit_markup(query, multiselect(DAYS, selected, "d", columns=2))
    return DAYS_STATE


async def on_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["minutes"] = int(query.data.split(":", 1)[1])
    await query.edit_message_text(
        "<b>4/6 — Come descriveresti la tua pelle?</b>",
        parse_mode="HTML",
        reply_markup=singleselect(SKIN_TYPES, "skin"),
    )
    return SKIN


async def on_skin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["skin_type"] = query.data.split(":", 1)[1]
    await query.edit_message_text(
        "<b>5/6 — Su cosa vuoi lavorare?</b>\n<i>Puoi sceglierne più di uno.</i>",
        parse_mode="HTML",
        reply_markup=multiselect(CONCERNS, set(), "c"),
    )
    return CONCERNS_STATE


async def on_concerns(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]
    selected = _sel(context, "concerns")

    if choice == DONE:
        if not selected:
            await query.answer("Scegline almeno uno 🙂", show_alert=True)
            return CONCERNS_STATE
        await query.edit_message_text(
            "<b>6/6 — Usi già qualcuno di questi attivi?</b>\n"
            "<i>Mi serve per non sovrapporli agli strumenti.</i>",
            parse_mode="HTML",
            reply_markup=multiselect(ACTIVES, set(), "a"),
        )
        return ACTIVES_STATE

    selected.symmetric_difference_update({choice})
    await _edit_markup(query, multiselect(CONCERNS, selected, "c"))
    return CONCERNS_STATE


async def on_actives(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]
    selected = _sel(context, "actives")

    if choice == DONE:
        needs_screening = bool(_sel(context, "tools") & ELECTRIC_TOOLS)
        if needs_screening:
            await query.edit_message_text(
                "🩺 <b>Un controllo di sicurezza</b>\n"
                "Alcuni strumenti che hai scelto hanno controindicazioni. "
                "Ti riguarda qualcuna di queste situazioni?",
                parse_mode="HTML",
                reply_markup=multiselect(SAFETY_FLAGS, set(), "s"),
            )
            return SAFETY
        return await _ask_reminder(query, context)

    selected.symmetric_difference_update({choice})
    await _edit_markup(query, multiselect(ACTIVES, selected, "a"))
    return ACTIVES_STATE


async def on_safety(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]
    selected = _sel(context, "safety")

    if choice == DONE:
        return await _ask_reminder(query, context)

    if choice == "nessuna":
        selected.clear()
        selected.add("nessuna")
    else:
        selected.discard("nessuna")
        selected.symmetric_difference_update({choice})

    await _edit_markup(query, multiselect(SAFETY_FLAGS, selected, "s"))
    return SAFETY


async def _ask_reminder(query, context) -> int:
    await query.edit_message_text(
        "⏰ <b>Ultimo passaggio.</b>\nA che ora vuoi il promemoria giornaliero?",
        parse_mode="HTML",
        reply_markup=hours_keyboard("r"),
    )
    return REMINDER


async def on_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    raw = query.data.split(":", 1)[1]
    hour = None if raw == "off" else int(raw)

    await query.edit_message_text(
        "🧪 Sto costruendo il tuo piano… un momento.", parse_mode="HTML"
    )
    await context.bot.send_chat_action(query.message.chat_id, ChatAction.TYPING)

    picked = _sel(context, "tools")
    profile = {
        # le chiavi "custom_*" restano fuori da `tools`: sono già in `custom_tools`
        "tools": sorted(t for t in picked if not t.startswith("custom_")),
        "custom_tools": [
            name
            for name in context.user_data.get("custom_tools", [])
            if f"custom_{name}" in picked
        ],
        "days": sorted(_sel(context, "days")),
        "minutes": context.user_data.get("minutes", 25),
        "skin_type": context.user_data.get("skin_type", "normale"),
        "concerns": sorted(_sel(context, "concerns")),
        "actives": sorted(_sel(context, "actives")),
        "safety": sorted(_sel(context, "safety")),
    }

    chat_id = query.message.chat_id
    try:
        plan = await generate_plan(profile)
    except Exception:
        logger.exception("Generazione piano fallita per %s", chat_id)
        await context.bot.send_message(
            chat_id,
            "😕 Qualcosa è andato storto nella generazione. Riprova con /rigenera.",
        )
        await upsert_user(chat_id, profile=profile)
        return ConversationHandler.END

    await upsert_user(
        chat_id, profile=profile, plan=plan.model_dump(), reminder_hour=hour
    )
    if hour is not None:
        schedule_reminder(context.application, chat_id, hour)

    for message in render_plan(plan):
        await context.bot.send_message(chat_id, message, parse_mode="HTML")

    await context.bot.send_message(
        chat_id,
        "Fatto! 🎉\n\n"
        "/oggi — cosa fare oggi\n"
        "/piano — il piano completo\n"
        "/rigenera — nuova versione del piano\n"
        "/modifica — cambia strumenti, giorni o durata\n"
        "/promemoria — cambia l'orario\n"
        "/reset — ricomincia da zero",
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Annullato. Quando vuoi, /start.")
    return ConversationHandler.END


def build_onboarding_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("modifica", start),
            CommandHandler("reset", start),
        ],
        states={
            TOOLS_STATE: [CallbackQueryHandler(on_tools, pattern=r"^t:")],
            TOOLS_ADD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_tools_custom)
            ],
            DAYS_STATE: [CallbackQueryHandler(on_days, pattern=r"^d:")],
            DURATION: [CallbackQueryHandler(on_duration, pattern=r"^dur:")],
            SKIN: [CallbackQueryHandler(on_skin, pattern=r"^skin:")],
            CONCERNS_STATE: [CallbackQueryHandler(on_concerns, pattern=r"^c:")],
            ACTIVES_STATE: [CallbackQueryHandler(on_actives, pattern=r"^a:")],
            SAFETY: [CallbackQueryHandler(on_safety, pattern=r"^s:")],
            REMINDER: [CallbackQueryHandler(on_reminder, pattern=r"^r:")],
        },
        fallbacks=[CommandHandler("annulla", cancel)],
        allow_reentry=True,
    )
