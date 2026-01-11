# CLAUDE.md - Contaspiccioli v2.0

Cash flow planner a 12+ mesi basato sui 4 pilastri di Coletti/Magri.

## Vision

**Domanda chiave**: "Quanto ho? Quanto avrò? Dove sto sforando?"

- Previsionale 12 mesi (come Excel Federico)
- Confronto previsto vs effettivo (stile Sibill)
- Import estratto conto → categorizzazione automatica
- Suggerimenti allocazione surplus tra pilastri

## Stack

- **Backend**: FastAPI + SQLite
- **Frontend**: Jinja2 + HTMX + TailwindCSS
- **Port**: 8001

## Comandi

```bash
docker compose up -d --build
docker compose logs -f contaspiccioli
curl http://localhost:8001/health
```

## I 4 Pilastri

| # | Nome | Target | Strumento | Account Federico |
|---|------|--------|-----------|------------------|
| P1 | Liquidità | 3+ mesi spese | C/C | BBVA |
| P2 | Emergenza | 3-12 mesi | Conto deposito | Fineco (XEON) |
| P3 | Spese Previste | Tasse + programmate | BTP/obbligazioni | Fineco (XEON) → Fideuram (F24) |
| P4 | Investimenti | Lungo termine | ETF azionari | Fineco |

## Dati Fiscali Federico

```
Codice ATECO: 70.20.09 (Consulenza aziendale)
Regime: Forfettario
Imposta sostitutiva: 15%
Coefficiente redditività: 78%
Cassa: Gestione Separata INPS (26.07%)
Inizio attività: 21/09/2021
```

### Scadenze Tasse

- **Luglio**: Saldo anno precedente + 1° acconto (50%)
- **Novembre**: 2° acconto (50%)
- **Soglia esonero**: < 52€
- **Metodo**: Storico (100% imposta, 80% INPS)

## Struttura Progetto

```
app/
├── main.py          # FastAPI + HTML routes
├── models.py        # Pillar, ForecastMonth, Transaction, PlannedExpense
├── routers/api.py   # REST API
├── services/
│   ├── forecast.py  # Previsionale 12 mesi
│   ├── pillars.py   # Gestione 4 pilastri
│   ├── taxes.py     # Calcolo tasse P.IVA
│   └── bank_import.py # Import CSV estratto conto
```

## Piano Implementazione

Vedi `IMPLEMENTATION_PLAN.md` per il piano completo v2.0.

**Status**: Refactoring da v1 (pillar-based) a v2 (cash flow planner)

### Bug Noti da Fixare

- `_months_elapsed()` in budget.py ignora anno
- Dual income tracking (MonthlyIncome + Transaction)
- Tax % hardcoded in config.py

## Sicurezza

- Dati finanziari sensibili: mai loggare importi
- Backup regolari del database
- Validare input su tutte le transazioni

## Riferimenti

- `docs/Guida Educati e Finanziati.pdf` - 4 pilastri Coletti
- `Bilancio Personale - Federico.xlsx` - Template previsionale
- `La guida di Contaspiccioli.md` - Documentazione utente
