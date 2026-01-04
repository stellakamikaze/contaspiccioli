# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Contaspiccioli** - Personal finance manager for Italian freelancers (P.IVA forfettaria).

**Stack:** FastAPI + SQLite + Jinja2 + HTMX + TailwindCSS

**Port:** 8001 (to avoid conflict with Phoibos on 8000)

## Quick Start

```bash
# Start
colima start --cpu 4 --memory 6 --disk 80
docker compose up -d --build

# Access
open http://localhost:8001

# Logs
docker compose logs -f contaspiccioli
```

## Architecture

```
app/
├── main.py           # FastAPI app, routes, templates
├── config.py         # Pydantic settings
├── database.py       # SQLAlchemy setup
├── models.py         # Transaction, Category, Pillar, TaxDeadline
├── routers/
│   └── api.py        # REST API endpoints
└── services/
    ├── budget.py     # Budget calculations
    └── telegram.py   # Notifications
```

## Key Models

| Model | Purpose |
|-------|---------|
| `Transaction` | Income/expense records |
| `Category` | Expense categories (fissa/variabile) |
| `Pillar` | 4 financial pillars (emergenza, tasse, investimenti) |
| `TaxDeadline` | Tax payment deadlines |

## Budget Model (4 Pillars)

Based on 3.500/month income:

| Pillar | % | /month |
|--------|---|--------|
| Spese fisse | 33.37% | 1.168 |
| Spese variabili | 25.46% | 891 |
| XEON tasse | 31.43% | 1.100 |
| ETF investimenti | 9.74% | 341 |

## API Endpoints

```
GET    /api/transactions      # List with filters
POST   /api/transactions      # Create
DELETE /api/transactions/{id} # Delete

GET    /api/categories        # List active
POST   /api/categories        # Create

GET    /api/pillars           # List all
PUT    /api/pillars/{id}/reconcile  # Update actual balance

GET    /api/budget/summary    # Monthly summary
GET    /api/budget/forecast   # Yearly forecast
GET    /api/deadlines         # Tax deadlines
```

## Environment Variables

| Variable | Required | Default |
|----------|----------|---------|
| `SECRET_KEY` | Yes | - |
| `DATABASE_URL` | No | sqlite:///data/contaspiccioli.db |
| `TELEGRAM_BOT_TOKEN` | No | - |
| `TELEGRAM_CHAT_ID` | No | - |
| `DEFAULT_INCOME` | No | 3500 |

## Development

```bash
# Syntax check
python -c "import ast; ast.parse(open('app/main.py').read())"

# Rebuild
docker compose restart contaspiccioli
```

## Files

- `Contaspiccioli_2026.xlsx` - Excel version for Google Sheets
- `La guida di Contaspiccioli.md` - Original documentation

## Language

UI and communication in **Italian**.
