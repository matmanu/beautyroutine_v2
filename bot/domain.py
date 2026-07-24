"""Costanti di dominio condivise fra handler, prompt e rendering."""

from __future__ import annotations

# --- Strumenti preimpostati -------------------------------------------------
TOOLS: dict[str, str] = {
    "led": "Maschera a LED",
    "sauna": "Sauna facciale",
    "nuface": "NuFACE Mini (microcorrente)",
    "gua_sha": "Gua sha / roller",
    "dermaroller": "Dermaroller / microneedling",
    "spazzola": "Spazzola detergente sonica",
}

# --- Giorni della settimana -------------------------------------------------
DAYS: dict[str, str] = {
    "lun": "Lunedì",
    "mar": "Martedì",
    "mer": "Mercoledì",
    "gio": "Giovedì",
    "ven": "Venerdì",
    "sab": "Sabato",
    "dom": "Domenica",
}
DAY_ORDER = list(DAYS.keys())
# python: Monday = 0
DAY_TO_WEEKDAY = {key: index for index, key in enumerate(DAY_ORDER)}

# --- Durata sessione --------------------------------------------------------
DURATIONS: dict[str, str] = {
    "10": "10-15 min (express)",
    "25": "20-30 min (standard)",
    "40": "30-45 min (completa)",
    "60": "45-60+ min (spa a casa)",
}

# --- Profilo pelle ----------------------------------------------------------
SKIN_TYPES: dict[str, str] = {
    "normale": "Normale",
    "secca": "Secca",
    "grassa": "Grassa",
    "mista": "Mista",
    "sensibile": "Sensibile / reattiva",
}

CONCERNS: dict[str, str] = {
    "rughe": "Rughe e lassità",
    "macchie": "Macchie e discromie",
    "acne": "Acne e impurità",
    "rossori": "Rossori / couperose",
    "disidratazione": "Disidratazione",
    "pori": "Pori dilatati",
    "occhiaie": "Occhiaie e borse",
    "opacita": "Colorito spento",
}

ACTIVES: dict[str, str] = {
    "retinoidi": "Retinoidi (retinolo, tretinoina...)",
    "acidi": "Esfolianti chimici (AHA/BHA/PHA)",
    "vitc": "Vitamina C",
    "niacinamide": "Niacinamide",
    "peptidi": "Peptidi",
    "nessuno": "Nessuno / non lo so",
}

# Screening di sicurezza: mostrato solo se si selezionano strumenti elettrici
SAFETY_FLAGS: dict[str, str] = {
    "pacemaker": "Pacemaker o dispositivi impiantati",
    "gravidanza": "Gravidanza o allattamento",
    "epilessia": "Epilessia",
    "impianti": "Impianti metallici nel viso",
    "filler": "Filler o tossina botulinica < 2 settimane",
    "rosacea": "Rosacea / couperose in fase attiva",
    "nessuna": "Nessuna delle precedenti",
}

# Flag che rendono controindicato un dato strumento
TOOL_CONTRAINDICATIONS: dict[str, set[str]] = {
    "nuface": {"pacemaker", "gravidanza", "epilessia", "impianti", "filler"},
    "sauna": {"rosacea"},
    "dermaroller": {"filler", "rosacea"},
}


def label(mapping: dict[str, str], keys: list[str] | None) -> str:
    """Trasforma una lista di chiavi in etichette leggibili separate da virgola."""
    if not keys:
        return "—"
    return ", ".join(mapping.get(key, key) for key in keys)
