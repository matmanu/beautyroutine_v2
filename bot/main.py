"""Entrypoint. Polling di default: su Railway gira come processo worker,
senza bisogno di dominio pubblico né certificati."""

from __future__ import annotations

import logging
import os

from telegram import BotCommand
from telegram.ext import Application, ApplicationBuilder, ContextTypes

from .config import settings
from .db import init_db
from . import auth
from .handlers import commands
from .handlers.onboarding import build_onboarding_handler
from .scheduler import restore_reminders

logging.basicConfig(
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

COMMANDS = [
    BotCommand("start", "Configura la tua routine"),
    BotCommand("oggi", "Cosa fare oggi"),
    BotCommand("piano", "Piano settimanale completo"),
    BotCommand("rigenera", "Rigenera il piano"),
    BotCommand("modifica", "Cambia strumenti, giorni o durata"),
    BotCommand("promemoria", "Orario della notifica"),
    BotCommand("cancella", "Elimina i tuoi dati"),
    BotCommand("aiuto", "Elenco dei comandi"),
]


async def post_init(app: Application) -> None:
    await init_db()
    await app.bot.set_my_commands(COMMANDS)
    await restore_reminders(app)
    logger.info("Bot avviato con provider LLM: %s", settings.llm_provider)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Senza questo, PTB logga l'eccezione e l'utente resta a fissare il vuoto."""
    logger.error("Errore non gestito", exc_info=context.error)

    chat = getattr(getattr(update, "effective_chat", None), "id", None)
    if chat is None:
        return
    try:
        await context.bot.send_message(
            chat, "😕 Qualcosa è andato storto. Riprova, o scrivi /aiuto."
        )
    except Exception:  # se anche l'avviso fallisce, non insistiamo
        logger.debug("Impossibile notificare l'errore a %s", chat)


def build_app() -> Application:
    app = (
        ApplicationBuilder()
        .token(settings.telegram_token)
        .post_init(post_init)
        .build()
    )
    app.add_handler(build_onboarding_handler())
    commands.register(app)
    app.add_error_handler(on_error)
    auth.install(app)  # gruppo -1: intercetta tutto prima degli handler normali
    return app


def main() -> None:
    app = build_app()
    webhook_url = os.getenv("WEBHOOK_URL")

    if webhook_url:
        # Railway espone PORT quando il servizio ha un dominio pubblico.
        port = int(os.getenv("PORT", "8080"))
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=settings.telegram_token,
            webhook_url=f"{webhook_url.rstrip('/')}/{settings.telegram_token}",
            drop_pending_updates=True,
        )
    else:
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
