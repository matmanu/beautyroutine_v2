"""Testo libero. Senza questo handler PTB scarta silenziosamente i messaggi
che non sono comandi né callback: nessun errore, nessuna riga di log,
e per l'utente il bot sembra semplicemente muto."""

from __future__ import annotations

import datetime as dt
import json
import logging
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import ContextTypes, MessageHandler, filters

from ..db import get_user
from ..domain import (
    ACTIVES,
    CONCERNS,
    DAY_ORDER,
    DAYS,
    SAFETY_FLAGS,
    SKIN_TYPES,
    TOOLS,
    label,
)
from ..llm.client import get_client

logger = logging.getLogger(__name__)

HISTORY_KEY = "chat_history"
MAX_TURNS = 6  # 6 scambi = 12 messaggi tenuti in memoria


SYSTEM_TEMPLATE = """Sei l'assistente che ha costruito la beauty routine di questa
persona e ora la segue nel quotidiano. Conosci il suo profilo e il suo piano attivo.

ADESSO
{adesso}
Quando parla di "oggi", "stasera", "domani", riferisciti a questa data.

PROFILO
{profile}

PIANO ATTIVO (JSON)
{plan}

COME RISPONDI
- In italiano, diretta e concreta, massimo 120 parole.
- Ti riferisci al piano reale quando serve: se chiede "cosa faccio stasera",
  guardi il giorno giusto invece di dare consigli generici.
- Sai adattare: "sono stanca, cosa posso saltare?", "posso spostare il giovedì
  a venerdì?", "quanto gel conduttivo serve?".
- Spieghi il perché di una scelta se te lo chiede, richiamando frequenze e
  incompatibilità (retinoide e sauna la stessa sera, un solo trattamento
  aggressivo per volta, e così via).
- Se vuole cambiare il piano in modo stabile, ricordi /rigenera (stesso profilo)
  oppure /modifica (per cambiare strumenti, giorni o durata).
- Non fai diagnosi e non consigli farmaci. Per problemi di pelle che persistono,
  rimandi al dermatologo.
- Niente formattazione markdown: scrivi in testo semplice."""


def _profile_summary(profile: dict) -> str:
    tools = ", ".join(
        [TOOLS.get(t, t) for t in profile.get("tools", [])]
        + profile.get("custom_tools", [])
    )
    return (
        f"Strumenti: {tools or '—'}\n"
        f"Giorni dedicati: {label(DAYS, profile.get('days'))}\n"
        f"Minuti a sessione: {profile.get('minutes', '—')}\n"
        f"Pelle: {SKIN_TYPES.get(profile.get('skin_type', ''), '—')}\n"
        f"Obiettivi: {label(CONCERNS, profile.get('concerns'))}\n"
        f"Attivi in uso: {label(ACTIVES, profile.get('actives'))}\n"
        f"Condizioni di sicurezza dichiarate: "
        f"{label(SAFETY_FLAGS, profile.get('safety'))}"
    )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Se l'onboarding è in corso, il testo libero non deve dirottare il flusso.
    if any(key.startswith("sel_") for key in context.user_data):
        await update.message.reply_text(
            "Stiamo ancora configurando la routine: usa i bottoni qui sopra, "
            "oppure /annulla per uscire."
        )
        return

    chat_id = update.effective_chat.id
    user = await get_user(chat_id)
    if user is None or not user.plan:
        await update.message.reply_text(
            "Non ho ancora un piano su cui ragionare. Partiamo da /start."
        )
        return

    await context.bot.send_chat_action(chat_id, ChatAction.TYPING)

    history: list[dict[str, str]] = context.user_data.setdefault(HISTORY_KEY, [])
    history.append({"role": "user", "content": update.message.text})
    del history[: -MAX_TURNS * 2]  # tiene solo gli scambi recenti

    now = dt.datetime.now(ZoneInfo(user.tz))
    today_key = DAY_ORDER[now.weekday()]
    system = SYSTEM_TEMPLATE.format(
        adesso=f"È {DAYS[today_key]} {now:%d/%m/%Y}, ore {now:%H:%M}.",
        profile=_profile_summary(user.profile or {}),
        plan=json.dumps(user.plan, ensure_ascii=False),
    )

    try:
        answer = await get_client().complete_text(system, history)
    except Exception:
        logger.exception("Risposta libera fallita per %s", chat_id)
        history.pop()  # non sporchiamo lo storico con un turno andato a vuoto
        await update.message.reply_text(
            "😕 Non sono riuscito a rispondere. Riprova fra un momento."
        )
        return

    history.append({"role": "assistant", "content": answer})

    # Il modello potrebbe produrre caratteri che rompono il parser HTML:
    # se succede, ripieghiamo sul testo semplice invece di perdere la risposta.
    try:
        await update.message.reply_text(answer, parse_mode="HTML")
    except BadRequest:
        await update.message.reply_text(answer)


async def cmd_dimentica(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(HISTORY_KEY, None)
    await update.message.reply_text("Ho dimenticato la conversazione. Ripartiamo da qui.")


def register(app) -> None:
    from telegram.ext import CommandHandler

    app.add_handler(CommandHandler("dimentica", cmd_dimentica))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
