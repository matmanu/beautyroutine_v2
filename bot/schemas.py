"""Schema del piano. Serve a due cose: descrivere il JSON all'LLM
e validare la risposta prima di salvarla."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Step(BaseModel):
    ordine: int = Field(description="Posizione nella sequenza, a partire da 1")
    nome: str = Field(description="Cosa fare, in una riga")
    strumento: str | None = Field(
        default=None, description="Strumento usato, se ne serve uno"
    )
    durata_min: int = Field(description="Minuti dedicati a questo passaggio")
    note: str | None = Field(
        default=None, description="Dettaglio pratico: come, quanto, cosa evitare"
    )


class RoutineBlock(BaseModel):
    momento: Literal["mattina", "sera"]
    passaggi: list[Step]
    durata_totale_min: int


class DayPlan(BaseModel):
    giorno: Literal["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
    focus: str = Field(description="Il tema della sessione, 3-6 parole")
    trattamenti: list[Step]
    durata_totale_min: int


class Plan(BaseModel):
    titolo: str
    razionale: str = Field(
        description="2-4 frasi che spiegano perché il piano è costruito così"
    )
    routine_quotidiana: list[RoutineBlock]
    settimana: list[DayPlan]
    regole_sicurezza: list[str]
    progressione: str = Field(
        description="Come far evolvere il piano nelle prossime 4-8 settimane"
    )


# Schema testuale iniettato nel prompt: più leggibile del JSON Schema grezzo.
JSON_SHAPE = """{
  "titolo": "string",
  "razionale": "string",
  "routine_quotidiana": [
    {
      "momento": "mattina" | "sera",
      "passaggi": [
        {"ordine": 1, "nome": "string", "strumento": "string|null",
         "durata_min": 2, "note": "string|null"}
      ],
      "durata_totale_min": 8
    }
  ],
  "settimana": [
    {
      "giorno": "lun"|"mar"|"mer"|"gio"|"ven"|"sab"|"dom",
      "focus": "string",
      "trattamenti": [
        {"ordine": 1, "nome": "string", "strumento": "string|null",
         "durata_min": 10, "note": "string|null"}
      ],
      "durata_totale_min": 25
    }
  ],
  "regole_sicurezza": ["string"],
  "progressione": "string"
}"""
