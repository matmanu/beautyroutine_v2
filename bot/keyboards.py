"""Tastiere inline. Telegram non ha veri menù a tendina: l'equivalente idiomatico
è una griglia di bottoni che fanno toggle con ✅ / ⬜ e un bottone 'Fatto'."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

DONE = "done"
ADD = "add"


def multiselect(
    options: dict[str, str],
    selected: set[str],
    prefix: str,
    *,
    columns: int = 1,
    done_label: str = "✅ Fatto",
    add_label: str | None = None,
) -> InlineKeyboardMarkup:
    """Tastiera a selezione multipla. callback_data = f'{prefix}:{key}'."""
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []

    for key, text in options.items():
        mark = "✅" if key in selected else "⬜"
        row.append(
            InlineKeyboardButton(f"{mark} {text}", callback_data=f"{prefix}:{key}")
        )
        if len(row) == columns:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    tail: list[InlineKeyboardButton] = []
    if add_label:
        tail.append(InlineKeyboardButton(add_label, callback_data=f"{prefix}:{ADD}"))
    tail.append(InlineKeyboardButton(done_label, callback_data=f"{prefix}:{DONE}"))
    buttons.append(tail)

    return InlineKeyboardMarkup(buttons)


def singleselect(
    options: dict[str, str], prefix: str, *, columns: int = 1
) -> InlineKeyboardMarkup:
    """Tastiera a selezione singola: il primo tap chiude lo step."""
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for key, text in options.items():
        row.append(InlineKeyboardButton(text, callback_data=f"{prefix}:{key}"))
        if len(row) == columns:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def hours_keyboard(prefix: str) -> InlineKeyboardMarkup:
    """Griglia oraria 6:00-22:00 per il promemoria giornaliero."""
    hours = list(range(6, 23))
    buttons: list[list[InlineKeyboardButton]] = []
    for start in range(0, len(hours), 4):
        buttons.append(
            [
                InlineKeyboardButton(f"{h:02d}:00", callback_data=f"{prefix}:{h}")
                for h in hours[start : start + 4]
            ]
        )
    buttons.append(
        [InlineKeyboardButton("🔕 Nessun promemoria", callback_data=f"{prefix}:off")]
    )
    return InlineKeyboardMarkup(buttons)
