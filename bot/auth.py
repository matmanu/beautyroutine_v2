"""Controllo accessi.

Il filtro va messo in un gruppo di handler negativo, così intercetta *ogni* update
prima di chiunque altro: comandi, testo libero e callback dei bottoni inline.
`ApplicationHandlerStop` interrompe la propagazione a tutti gli altri gruppi.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    ContextTypes,
    TypeHandler,
)

from .config import settings

logger = logging.getLogger(__name__)

DENIED = (
    "🔒 Questo è un bot privato e non sei fra gli utenti autorizzati.\n\n"
    "Se dovresti esserlo, comunica al proprietario il tuo ID Telegram: <code>{uid}</code>"
)


async def _guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        raise ApplicationHandlerStop

    if user.id in settings.allowed_user_ids:
        return  # autorizzato: l'update prosegue verso gli handler normali

    logger.warning(
        "Accesso negato a user_id=%s (@%s)", user.id, user.username or "senza username"
    )

    # Rispondiamo comunque, altrimenti il bot sembra rotto a chi lo trova per caso.
    if update.callback_query is not None:
        await update.callback_query.answer("Bot privato.", show_alert=True)
    elif update.effective_message is not None:
        await update.effective_message.reply_text(
            DENIED.format(uid=user.id), parse_mode="HTML"
        )

    raise ApplicationHandlerStop


def install(app: Application) -> None:
    """Registra il gate solo se l'allowlist è configurata."""
    if not settings.allowed_user_ids:
        logger.warning(
            "ALLOWED_USER_IDS non impostata: il bot risponde a CHIUNQUE. "
            "In produzione imposta la variabile con il tuo ID Telegram."
        )
        return

    app.add_handler(TypeHandler(Update, _guard), group=-1)
    logger.info("Allowlist attiva su %s utenti", len(settings.allowed_user_ids))
