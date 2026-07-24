# Beauty Routine Bot

Agente Telegram che costruisce un piano di beauty routine settimanale personalizzato,
usando un LLM (Claude o OpenAI) vincolato da una knowledge base sugli strumenti.

L'utente dichiara strumenti, giorni e minuti disponibili; il bot restituisce una
routine base quotidiana (mattina/sera) più trattamenti mirati nei giorni scelti,
e manda un promemoria all'ora concordata.

## Struttura

```
bot/
├── main.py           entrypoint, registrazione handler, polling o webhook
├── config.py         variabili d'ambiente
├── db.py             SQLAlchemy async, tabella users con profilo e piano in JSON
├── domain.py         strumenti, giorni, controindicazioni, opzioni dei menu
├── keyboards.py      tastiere inline a selezione multipla e singola
├── schemas.py        schema Pydantic del piano
├── auth.py           allowlist: blocca gli update da utenti non autorizzati
├── planner.py        genera + valida, con un retry
├── render.py         piano → messaggi HTML Telegram
├── scheduler.py      promemoria giornalieri via JobQueue
├── handlers/
│   ├── onboarding.py ConversationHandler a 9 stati
│   └── commands.py   /piano /oggi /rigenera /promemoria /cancella
└── llm/
    ├── client.py     interfaccia comune, implementazioni Anthropic e OpenAI
    └── prompts.py    system prompt + knowledge base
```

## Come funziona l'onboarding

Telegram non ha veri menù a tendina: l'equivalente è una griglia di bottoni inline
che fanno toggle. Il flusso è:

1. **Strumenti** — multi-selezione, con "➕ Aggiungi altro" per inserirne di propri via testo
2. **Giorni** — multi-selezione lun-dom
3. **Durata** — selezione singola (10-15 / 20-30 / 30-45 / 45-60+ min)
4. **Tipo di pelle** — selezione singola
5. **Obiettivi** — multi-selezione
6. **Attivi già in uso** — multi-selezione, serve a evitare sovrapposizioni
7. **Screening di sicurezza** — appare solo se sono stati scelti strumenti elettrici
   o il vapore. Gli strumenti controindicati vengono esclusi dal piano prima ancora
   di chiamare l'LLM (`planner.filter_contraindicated_tools`)
8. **Orario del promemoria**

## Perché il piano è "calibrato"

La qualità dell'output dipende quasi interamente dal prompt. In `llm/prompts.py`
la knowledge base impone frequenze e sequenze note: LED fino a quotidiano su pelle
pulita, sauna facciale 1-2 volte a settimana e mai la sera del retinoide, NuFACE
5 minuti a zona con gel conduttivo in fase intensiva per 60 giorni e poi mantenimento,
un solo trattamento aggressivo per sessione, e così via.

Il modello risponde in JSON, che viene validato con Pydantic. Se lo schema non torna,
`planner.py` rimanda l'errore al modello e ritenta una volta.

## Setup locale

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # e compila TELEGRAM_BOT_TOKEN + la chiave LLM
python -m bot.main
```

Senza `DATABASE_URL` usa SQLite in locale, quindi non serve installare Postgres
per provarlo.

## Deploy su Railway

1. **Crea il bot** su Telegram con [@BotFather](https://t.me/BotFather), tieni il token.
2. **Nuovo progetto** su Railway → *Deploy from GitHub repo*, puntando a questo repo.
3. **Aggiungi Postgres**: nel progetto, *New* → *Database* → *PostgreSQL*.
   Railway inietta `DATABASE_URL` automaticamente; `config.py` la converte nel
   formato asyncpg.
4. **Variabili d'ambiente** nel servizio (tab *Variables*):

   | Variabile | Valore |
   |---|---|
   | `TELEGRAM_BOT_TOKEN` | il token di BotFather |
   | `LLM_PROVIDER` | `anthropic` oppure `openai` |
   | `ANTHROPIC_API_KEY` | la tua chiave (se provider anthropic) |
   | `ANTHROPIC_MODEL` | `claude-sonnet-5` |
   | `OPENAI_API_KEY` | la tua chiave (se provider openai) |
   | `ALLOWED_USER_IDS` | i tuoi ID Telegram, separati da virgola |
   | `DEFAULT_TZ` | `Europe/Rome` |

5. **Deploy.** Il `Procfile` avvia il processo come `worker`, quindi in polling:
   nessun dominio pubblico necessario.

### Se preferisci il webhook

Genera un dominio pubblico dal tab *Settings* → *Networking* → *Generate Domain*,
poi imposta `WEBHOOK_URL=https://tuo-servizio.up.railway.app`. `main.py` passa
automaticamente a `run_webhook` sulla porta che Railway espone in `PORT`.

Il polling è più semplice e per un bot personale va benissimo. Il webhook conviene
solo se punti a molti utenti concorrenti.

## Limitare l'accesso a pochi utenti

L'username del bot è pubblico e indovinabile: senza un controllo esplicito chiunque
può scrivergli e consumare le tue chiamate API. Imposta `ALLOWED_USER_IDS` con gli
ID numerici autorizzati:

```
ALLOWED_USER_IDS=123456789,987654321
```

Per scoprire il tuo ID: scrivi a [@userinfobot](https://t.me/userinfobot), oppure
lascia la variabile vuota al primo avvio, manda `/start` al tuo bot e leggi l'ID
nei log di Railway.

`auth.py` registra un `TypeHandler` nel gruppo `-1`, che intercetta ogni update —
comandi, testo libero e tap sui bottoni inline — prima di qualsiasi altro handler,
e interrompe la catena con `ApplicationHandlerStop`. Chi non è autorizzato riceve
un messaggio che include il proprio ID, così non ti chiudi fuori per errore: se
sbagli a copiarlo, ti basta leggerlo nella risposta e correggere la variabile.

Se lasci `ALLOWED_USER_IDS` vuota il gate non viene installato e il bot risponde a
tutti, con un warning nei log all'avvio.

Due accorgimenti complementari lato BotFather:

- `/setjoingroups` → *Disable*, così il bot non può essere aggiunto ai gruppi
- `/setdescription` neutra: non serve pubblicizzare cosa fa

## Note

- I job del promemoria vivono in memoria: `restore_reminders` li ricrea a ogni avvio
  leggendo il DB, perché su Railway il container riparte a ogni deploy.
- I fusi orari sono per utente (campo `tz`), ma l'onboarding non li chiede ancora:
  tutti ereditano `DEFAULT_TZ`. È il primo punto naturale da estendere.
- Il bot non sostituisce il parere di un dermatologo, e il prompt glielo fa dire
  esplicitamente in `regole_sicurezza`.
