# Implementation Plan: Contaspiccioli v2.0

## Vision

Contaspiccioli è un **cash flow planner a 12+ mesi** basato sui 4 pilastri di Coletti/Magri, con confronto previsto vs effettivo stile Sibill.

**Domanda chiave**: "Quanto ho? Quanto avrò? Dove sto sforando?"

---

## Modello Concettuale

### I 4 Pilastri (Bucket di Patrimonio)

```
┌─────────────────────────────────────────────────────────────────┐
│                    PATRIMONIO TOTALE                            │
├─────────────────────────────────────────────────────────────────┤
│  P1: LIQUIDITÀ        │ Conto corrente principale              │
│  (Spese mensili)      │ Target: ALMENO 3 mesi di spese         │
│                       │ Strumento: C/C                          │
├───────────────────────┼─────────────────────────────────────────┤
│  P2: EMERGENZA        │ Fondo per imprevisti                   │
│  (Da costruire)       │ Target: 3-12 mesi di spese             │
│                       │ Strumento: Conto deposito svincolabile │
├───────────────────────┼─────────────────────────────────────────┤
│  P3: SPESE PREVISTE   │ Tasse + TUTTE spese programmate        │
│  (entro 10 anni)      │ (auto, casa, matrimonio, università)   │
│                       │ Strumento: BTP/obbligazioni scadenzate │
├───────────────────────┼─────────────────────────────────────────┤
│  P4: INVESTIMENTI     │ Capitale lungo termine (10+ anni)      │
│  (Crescita)           │ Target: definito dall'utente           │
│                       │ Strumento: ETF azionari                │
└───────────────────────┴─────────────────────────────────────────┘
```

### Flusso Dati

```
ESTRATTO CONTO (CSV mensile)
    ↓
Claude categorizza automaticamente
    ↓
┌─────────────────────────────────────────┐
│         CONFRONTO MENSILE               │
├─────────────────────────────────────────┤
│ Categoria    │ Previsto │ Effettivo │ Δ │
│ Alimentari   │   350€   │   380€    │-30│
│ Ristoranti   │   200€   │   150€    │+50│
│ Trasporti    │    50€   │    60€    │-10│
│ ...          │   ...    │   ...     │...│
└─────────────────────────────────────────┘
    ↓
PREVISIONALE 12 MESI (come Excel Federico)
    ↓
SUGGERIMENTI ALLOCAZIONE PILASTRI
```

---

## Phase 0: Preparazione

### 0.1 Branch e Backup
- [ ] Tag versione attuale: `git tag v1.0-legacy`
- [ ] Creare branch: `git checkout -b refactor/v2-pillar-cashflow`
- [ ] Backup database attuale

### 0.2 Documentazione Riferimento
- [ ] Salvare copia "Guida Educati e Finanziati.pdf" in `docs/`
- [ ] Screenshot Sibill come riferimento UI in `docs/`
- [ ] Esportare template Excel previsionale come riferimento

**Test**: Branch creato, backup verificato

---

## Phase 1: Nuovo Schema Database

### 1.1 Modello Pilastri

```python
class Pillar(Base):
    """I 4 pilastri di allocazione patrimonio"""
    id: int
    number: int                      # 1, 2, 3, 4
    name: str                        # "Liquidità", "Emergenza", "Tasse", "Investimenti"
    description: str                 # Descrizione da guida Coletti

    # Saldi
    current_balance: Decimal         # Saldo attuale
    target_balance: Decimal          # Target da raggiungere

    # Configurazione
    target_months: int               # Per P1/P2: mesi di spese da coprire
    instrument: str                  # "Conto corrente", "Conto deposito", "BTP", "ETF"
    account_name: str                # Nome conto/broker associato

    # Stato
    is_funded: bool                  # Target raggiunto?
    priority: int                    # Ordine di riempimento (1→2→3→4)
```

### 1.2 Modello Previsionale

```python
class ForecastMonth(Base):
    """Previsionale mensile (replica struttura Excel)"""
    id: int
    year: int
    month: int

    # Eredità (saldo iniziale mese)
    opening_balance: Decimal         # Calcolato da mese precedente

    # Ricavi
    expected_income: Decimal         # Totale entrate previste
    actual_income: Decimal           # Totale entrate effettive

    # Costi Fissi
    expected_fixed_costs: Decimal
    actual_fixed_costs: Decimal

    # Costi Variabili
    expected_variable_costs: Decimal
    actual_variable_costs: Decimal

    # Totali
    expected_balance: Decimal        # opening + income - costs
    actual_balance: Decimal          # Saldo reale a fine mese
    variance: Decimal                # expected - actual


class ForecastLine(Base):
    """Singola riga del previsionale (entrata o uscita)"""
    id: int
    forecast_month_id: FK → ForecastMonth

    category_id: FK → Category
    line_type: LineType              # INCOME | FIXED_COST | VARIABLE_COST

    description: str                 # "Ufficio Furore", "Affitto", "Alimentari"
    expected_amount: Decimal
    actual_amount: Decimal

    is_recurring: bool               # Si ripete ogni mese?
    recurrence_day: int              # Giorno del mese (es. 27 per stipendio)
```

### 1.3 Modello Categorie (con mapping estratto conto)

```python
class Category(Base):
    """Categoria di spesa/entrata con regole di categorizzazione"""
    id: int
    name: str                        # "Alimentari", "Ristoranti", "Affitto"
    type: CategoryType               # INCOME | FIXED | VARIABLE
    icon: str
    color: str

    # Budget
    monthly_budget: Decimal          # Budget mensile target

    # Per categorizzazione automatica estratto conto
    keywords: list[str]              # ["ESSELUNGA", "CARREFOUR", "COOP"]

    # Pilastro associato (per allocazioni)
    pillar_id: FK → Pillar           # Principalmente P1, ma tasse → P3

    display_order: int
    is_active: bool


class Transaction(Base):
    """Singola transazione (da estratto conto o manuale)"""
    id: int
    date: date
    amount: Decimal
    description: str                 # Descrizione originale estratto conto

    category_id: FK → Category
    forecast_line_id: FK → ForecastLine  # Collegamento al previsionale

    # Metadata
    source: TransactionSource        # BANK_IMPORT | MANUAL
    original_description: str        # Descrizione raw da CSV
    is_recurring: bool

    # Per P.IVA
    is_income: bool
    is_taxable: bool                 # Se è ricavo da fattura
```

### 1.4 Modello Tasse P.IVA

```python
class TaxSettings(Base):
    """Configurazione fiscale P.IVA forfettaria"""
    id: int
    regime: TaxRegime                # FORFETTARIO | ORDINARIO | DIPENDENTE
    year: int                        # Anno fiscale di riferimento

    # Solo per forfettario
    coefficient: Decimal             # Coefficiente redditività (es. 0.78)
    inps_rate: Decimal               # Aliquota INPS gestione separata (2025: 26.07%)
    tax_rate: Decimal                # Aliquota imposta sostitutiva (5% o 15%)

    # Acconti (metodo storico)
    # ATTENZIONE: Imposta sostitutiva = 100% anno precedente (50% + 50%)
    #             Contributi INPS = 80% anno precedente (40% + 40%)
    advance_method: AdvanceMethod    # STORICO | PREVISIONALE
    min_threshold: Decimal           # Default 52€ (sotto = esonerato)
    single_payment_threshold: Decimal # Default 258€ (sotto = unica rata novembre)

    # NOTE: Le aliquote cambiano ogni anno! Rendere configurabili.


class TaxDeadline(Base):
    """Scadenza fiscale (calcolata o manuale)"""
    id: int
    year: int                        # Anno fiscale
    deadline_type: DeadlineType      # SALDO | ACCONTO_1 | ACCONTO_2

    name: str                        # "Saldo 2025 + 1° Acconto 2026"
    due_date: date                   # ATTENZIONE: può variare (2025: 21 luglio!)

    amount_due: Decimal              # Importo dovuto
    amount_paid: Decimal             # Già pagato
    installments_paid: int           # Rate pagate (se rateizzato)

    is_calculated: bool              # True = calcolato da sistema
    is_manual_override: bool         # True = utente ha modificato
    notes: str                       # "Posticipato per decreto"

    pillar_id: FK → Pillar           # Sempre P3


class PlannedExpense(Base):
    """Spesa programmata (P3) - oltre le tasse"""
    id: int
    name: str                        # "Nuova bicicletta", "Dentista", "Viaggio Giappone"
    target_amount: Decimal           # Quanto serve
    current_amount: Decimal          # Quanto accantonato
    target_date: date                # Quando serve

    # Accantonamento automatico
    monthly_contribution: Decimal    # Calcolato: (target - current) / mesi_rimanenti

    pillar_id: FK → Pillar           # P3
    is_completed: bool               # Obiettivo raggiunto
    notes: str
```

**Uso**: Quando aggiungi "Dentista 500€ entro Marzo", il sistema calcola automaticamente l'accantonamento mensile necessario (es. 166€/mese per 3 mesi).

### 1.5 Modello Account (Struttura Federico)

```python
class Account(Base):
    """Conto bancario reale - uno per pilastro (semplificato)"""
    id: int
    name: str                        # "BBVA", "Fineco", "Fideuram"
    account_type: AccountType        # CHECKING | BROKER | TAX_ONLY

    # Saldi tracciati
    balance: Decimal                 # Saldo attuale
    last_updated: datetime

    # Metadata
    notes: str
    is_active: bool
```

**Struttura Reale Federico:**
```
┌─────────────────────────────────────────────────────────────┐
│  BBVA (c/c principale)                                      │
│  └── P1: Liquidità + pagamento affitto                      │
├─────────────────────────────────────────────────────────────┤
│  FINECO (broker)                                            │
│  └── P2: Fondo emergenza (XEON ETF monetario)              │
│  └── P3: Accantonamento tasse (XEON, temporaneo)           │
│  └── P4: Investimenti (ETF azionari)                       │
├─────────────────────────────────────────────────────────────┤
│  FIDEURAM (solo F24)                                        │
│  └── Transito per pagamento tasse (non un pilastro)        │
│      Bonifico da Fineco → Fideuram → F24                   │
└─────────────────────────────────────────────────────────────┘
```

**Nota**: I soldi per le tasse (P3) stanno su XEON@Fineco fino al momento del pagamento, poi transitano su Fideuram solo per emettere F24.

### 1.6 Migrazione

- [ ] Script migrazione dati esistenti
- [ ] Seed pilastri default (4 pilastri da guida Coletti)
- [ ] Seed categorie default con keywords
- [ ] **FIX**: Consolidare MonthlyIncome → Transaction (eliminare duplicazione)

**Test**: `pytest tests/test_models.py`

---

## Phase 2: Services Core

### 2.1 Forecast Service

```python
# app/services/forecast.py

def generate_yearly_forecast(db, year: int, profile: UserSettings) -> list[ForecastMonth]:
    """
    Genera previsionale 12 mesi come Excel Federico:
    - Eredità: saldo P1 attuale
    - Ricavi: da IncomeSource + recurring
    - Costi fissi: da recurring transactions + tax deadlines
    - Costi variabili: media ultimi 3 mesi per categoria
    """

def get_forecast_comparison(db, year: int, month: int) -> ForecastComparison:
    """
    Confronto previsto vs effettivo stile Sibill:
    - Per ogni categoria: expected, actual, variance
    - Totali per tipo (fisso/variabile)
    - Saldo fine mese
    """

def update_forecast_actuals(db, year: int, month: int, transactions: list[Transaction]):
    """Aggiorna colonna EFFETTIVO del previsionale con transazioni importate"""

def project_balance(db, months_ahead: int = 12) -> list[BalanceProjection]:
    """
    Proiezione saldo P1 (liquidità) per i prossimi N mesi.
    Ritorna: [{month, opening, income, costs, closing, cumulative}]
    """
```

### 2.2 Pillar Service

```python
# app/services/pillars.py

def get_pillar_status(db) -> list[PillarStatus]:
    """
    Status dei 4 pilastri:
    - current_balance vs target_balance
    - % completamento
    - Priorità di riempimento
    """

def calculate_target_balances(db, profile: UserSettings) -> dict[int, Decimal]:
    """
    Calcola target per ogni pilastro:
    - P1: 1-2 mesi di spese medie
    - P2: 3-6 mesi di spese medie
    - P3: somma scadenze fiscali prossimi 12 mesi
    - P4: definito dall'utente
    """

def suggest_allocation(db, surplus: Decimal) -> list[AllocationSuggestion]:
    """
    Dato un surplus, suggerisce come allocarlo:
    1. Prima riempi P2 (emergenza) se sotto target
    2. Poi P3 (tasse) se scadenze vicine
    3. Infine P4 (investimenti)

    Ritorna: [{pillar_id, amount, reason}]
    """

def record_transfer(db, from_pillar: int, to_pillar: int, amount: Decimal, date: date):
    """Registra trasferimento tra pilastri"""
```

### 2.3 Tax Service

```python
# app/services/taxes.py

def calculate_annual_taxes(income: Decimal, settings: TaxSettings) -> TaxBreakdown:
    """
    Calcola tasse annuali P.IVA forfettaria:
    - Imponibile = income * coefficient
    - INPS = imponibile * inps_rate
    - IRPEF = imponibile * tax_rate
    - Totale = INPS + IRPEF
    """

def generate_tax_deadlines(db, year: int, estimated_income: Decimal) -> list[TaxDeadline]:
    """
    Genera scadenze fiscali:
    - Giugno: Saldo anno precedente + 1° acconto
    - Novembre: 2° acconto
    - Accantonamento mensile suggerito
    """

def calculate_monthly_reserve(db, year: int) -> Decimal:
    """Quanto accantonare ogni mese per coprire tasse"""

def update_tax_deadline(db, deadline_id: int, amount: Decimal):
    """Override manuale importo scadenza"""
```

### 2.4 Bank Import Service

```python
# app/services/bank_import.py

def parse_bank_statement(content: str, format: BankFormat) -> list[RawTransaction]:
    """
    Parse CSV estratto conto.
    Supporta: Intesa, Fineco, N26, Revolut (formati comuni)
    """

def categorize_transactions(db, transactions: list[RawTransaction]) -> list[Transaction]:
    """
    Categorizza automaticamente usando keywords:
    - Match description con Category.keywords
    - Se no match → categoria "Altro" per review manuale
    """

def import_month(db, year: int, month: int, transactions: list[Transaction]):
    """
    Importa transazioni e aggiorna forecast:
    1. Salva transazioni
    2. Aggrega per categoria
    3. Aggiorna ForecastLine.actual_amount
    """
```

**Test**: `pytest tests/test_services.py`

---

## Phase 3: API Endpoints

### 3.1 Pillar API

| Endpoint | Metodo | Descrizione |
|----------|--------|-------------|
| `/api/pillars` | GET | Status 4 pilastri con % completamento |
| `/api/pillars/{id}` | PUT | Aggiorna saldo/target pilastro |
| `/api/pillars/transfer` | POST | Registra trasferimento tra pilastri |
| `/api/pillars/suggest` | GET | Suggerimenti allocazione surplus |

### 3.2 Forecast API

| Endpoint | Metodo | Descrizione |
|----------|--------|-------------|
| `/api/forecast/{year}` | GET | Previsionale 12 mesi |
| `/api/forecast/{year}/{month}` | GET | Dettaglio mese con confronto |
| `/api/forecast/{year}/{month}/lines` | GET | Righe dettaglio (per categoria) |
| `/api/forecast/{year}/{month}/lines/{id}` | PUT | Modifica riga previsionale |
| `/api/forecast/projection` | GET | Proiezione saldo P1 futura |

### 3.3 Transaction API

| Endpoint | Metodo | Descrizione |
|----------|--------|-------------|
| `/api/transactions` | GET | Lista con filtri (year, month, category) |
| `/api/transactions` | POST | Aggiungi manuale |
| `/api/transactions/{id}` | PUT | Modifica (ricategorizza) |
| `/api/transactions/import` | POST | Import CSV estratto conto |
| `/api/transactions/uncategorized` | GET | Transazioni da categorizzare |

### 3.4 Tax API

| Endpoint | Metodo | Descrizione |
|----------|--------|-------------|
| `/api/taxes/settings` | GET/PUT | Configurazione fiscale |
| `/api/taxes/calculate` | POST | Calcola tasse da fatturato |
| `/api/taxes/deadlines` | GET | Scadenze fiscali |
| `/api/taxes/deadlines/{id}` | PUT | Override manuale scadenza |
| `/api/taxes/reserve` | GET | Accantonamento mensile suggerito |

### 3.5 Category API

| Endpoint | Metodo | Descrizione |
|----------|--------|-------------|
| `/api/categories` | GET | Lista categorie |
| `/api/categories` | POST | Crea categoria |
| `/api/categories/{id}` | PUT | Modifica (keywords, budget) |
| `/api/categories/{id}/keywords` | PUT | Aggiorna keywords matching |

**Test**: `curl` per ogni endpoint

---

## Phase 4: Frontend

### 4.1 Dashboard Principale

```
┌─────────────────────────────────────────────────────────────────┐
│  CONTASPICCIOLI                              Gennaio 2026      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  I 4 PILASTRI                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ P1 LIQUID│ │ P2 EMERG │ │ P3 TASSE │ │ P4 INVEST│          │
│  │  5.958€  │ │    0€    │ │  2.500€  │ │  1.200€  │          │
│  │ ████████ │ │ ░░░░░░░░ │ │ ████░░░░ │ │ ██░░░░░░ │          │
│  │ 100%     │ │ 0%       │ │ 45%      │ │ 12%      │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│                                                                 │
│  CONFRONTO MESE (Previsto vs Effettivo)                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Categoria      │ Previsto │ Effettivo │    Δ    │       │   │
│  │ ─────────────────────────────────────────────────────── │   │
│  │ 🏠 Affitto     │   700€   │   700€    │    0€   │ ✓     │   │
│  │ 🍕 Alimentari  │   350€   │   380€    │  -30€   │ ⚠️    │   │
│  │ 🍝 Ristoranti  │   200€   │   150€    │  +50€   │ ✓     │   │
│  │ 🚗 Trasporti   │    50€   │    60€    │  -10€   │ ─     │   │
│  │ 💊 Salute      │   380€   │   380€    │    0€   │ ✓     │   │
│  │ ─────────────────────────────────────────────────────── │   │
│  │ TOTALE USCITE  │  2.500€  │  2.490€   │  +10€   │       │   │
│  │ ENTRATE        │  3.500€  │  3.500€   │    0€   │       │   │
│  │ ─────────────────────────────────────────────────────── │   │
│  │ SALDO MESE     │ +1.000€  │ +1.010€   │  +10€   │       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ⚡ SUGGERIMENTO: Hai un surplus di 1.010€.                    │
│     Suggerisco: 800€ → P2 (Emergenza), 210€ → P4 (Investimenti)│
│                                            [Applica] [Ignora]  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  📅 PROSSIME SCADENZE                                          │
│  • 16 Giu 2026: Saldo IVA 2025 + Acconto → 7.527€             │
│  • 30 Nov 2026: 2° Acconto IVA → 5.460€                        │
│  Accantonamento mensile suggerito: 1.082€                      │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Previsionale 12 Mesi (replica Excel)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  PREVISIONALE 2026                                                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                │ Eredità │ Gen   │ Feb   │ Mar   │ ...  │ Dic   │ TOTALE │
│ ───────────────────────────────────────────────────────────────────────────────│
│ RICAVI         │         │       │       │       │      │       │        │
│ Ufficio Furore │         │ 3.500 │ 3.500 │ 3.500 │ ...  │ 3.500 │ 42.000 │
│ Altri          │         │     0 │     0 │     0 │ ...  │     0 │      0 │
│ TOTALE (R1)    │  5.958  │ 3.500 │ 3.500 │ 3.500 │ ...  │ 3.500 │ 47.958 │
│ ───────────────────────────────────────────────────────────────────────────────│
│ COSTI FISSI    │         │       │       │       │      │       │        │
│ Affitto        │         │   700 │   700 │   700 │ ...  │   700 │  8.400 │
│ IVA 2025       │         │       │       │       │ 7527 │  5460 │ 12.987 │
│ TOTALE (C1)    │       0 │ 1.350 │   700 │   700 │ ...  │   700 │ 22.437 │
│ ───────────────────────────────────────────────────────────────────────────────│
│ COSTI VARIABILI│         │       │       │       │      │       │        │
│ Alimentari     │         │   356 │   230 │   143 │ ...  │   193 │  2.320 │
│ Ristoranti     │         │   416 │   282 │   319 │ ...  │   288 │  3.455 │
│ ...            │         │   ... │   ... │   ... │ ...  │   ... │    ... │
│ TOTALE (C2)    │       0 │ 1.689 │ 1.391 │ 1.155 │ ...  │ 1.272 │ 15.258 │
│ ───────────────────────────────────────────────────────────────────────────────│
│ TOTALE COSTI   │       0 │ 3.039 │ 2.091 │ 1.855 │ ...  │ 1.972 │ 37.695 │
│ SALDO MESE     │  5.958  │  +461 │+1.409 │+1.645 │ ...  │+1.528 │+10.264 │
│ ───────────────────────────────────────────────────────────────────────────────│
│ SALDO CUMUL.   │  5.958  │ 6.420 │ 7.829 │ 9.474 │ ...  │10.264 │ UTILE  │
└─────────────────────────────────────────────────────────────────────────────────┘

[📊 Grafico saldo cumulativo]
```

### 4.3 Import Estratto Conto

```
┌─────────────────────────────────────────────────────────────────┐
│  IMPORTA ESTRATTO CONTO                         Gennaio 2026   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Carica CSV] o trascina qui il file                           │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  TRANSAZIONI IMPORTATE: 47                                     │
│  Categorizzate: 42 (89%)                                       │
│  Da verificare: 5                                              │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Data    │ Descrizione           │ Importo │ Categoria   │   │
│  │ ─────────────────────────────────────────────────────── │   │
│  │ 03/01  │ ESSELUNGA MILANO      │  -45,20 │ 🍕 Aliment. │   │
│  │ 05/01  │ UBER *TRIP            │  -12,50 │ 🚗 Trasporti│   │
│  │ 07/01  │ PIZZERIA DA MARIO     │  -28,00 │ 🍝 Ristorant│   │
│  │ 10/01  │ PAGAMENTO SCONOSCIUTO │  -50,00 │ ❓ [Select] │   │
│  │ ...    │ ...                   │    ...  │ ...         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│                              [Conferma Import] [Annulla]        │
└─────────────────────────────────────────────────────────────────┘
```

### 4.4 Gestione Pilastri

```
┌─────────────────────────────────────────────────────────────────┐
│  PILASTRO 2: FONDO EMERGENZA                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Saldo attuale:     0€                                         │
│  Target:            10.500€ (3 mesi di spese)                  │
│  Completamento:     0%                                         │
│                                                                 │
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  0%        │
│                                                                 │
│  Strumento consigliato: Conto deposito svincolabile            │
│  (es. Illimity, Findomestic, Cherry)                           │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  STORICO TRASFERIMENTI                                         │
│  (nessun trasferimento)                                        │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  Account associato: [Nessuno]  [Collega account]               │
│  Target mesi: [3 ▼]                                            │
│                                                                 │
│                                    [Registra versamento]        │
└─────────────────────────────────────────────────────────────────┘
```

### 4.5 Onboarding (3 step)

**Step 1: Profilo Fiscale**
- Tipo reddito (dipendente/P.IVA forfettario/ordinario)
- Se P.IVA: aliquote, coefficiente
- Fonti di reddito con importi

**Step 2: Situazione Attuale**
- Saldo conto corrente (P1)
- Hai un fondo emergenza? Quanto? (P2)
- Accantonamento tasse attuale (P3)
- Investimenti attuali (P4)

**Step 3: Budget Base**
- Import categorie default
- Modifica budget per categoria
- Keywords personalizzate (opzionale)

**Test**: Verifica visiva browser

---

## Phase 5: Categorizzazione AI-Assisted

### 5.1 Guida Categorizzazione

Creare documento `docs/CATEGORIZATION_GUIDE.md` con:
- Lista categorie standard
- Keywords per ogni categoria
- Regole di matching
- Esempi di edge cases

### 5.2 Learning delle Keywords

```python
def learn_keyword(db, transaction_description: str, category_id: int):
    """
    Quando l'utente categorizza manualmente una transazione,
    estrae keywords dalla descrizione e le aggiunge alla categoria.
    """

def suggest_category(db, description: str) -> tuple[Category, float]:
    """
    Suggerisce categoria con confidence score.
    Se confidence < 0.7, chiede conferma all'utente.
    """
```

---

## Phase 6: Features Avanzate

### 6.1 Notifiche Telegram
- [ ] Alert scadenze fiscali (7gg prima)
- [ ] Alert budget sforato (>100% categoria)
- [ ] Report settimanale spese

### 6.2 Export
- [ ] Export CSV previsionale
- [ ] Export PDF report mensile

### 6.3 Multi-anno
- [ ] Confronto anno su anno
- [ ] Trend categorie

---

## Testing Strategy

### Unit Tests
- Models: validazione, calcoli
- Services: forecast, pillars, taxes, import

### Integration Tests
- API: flow completo import → categorize → forecast
- Database: migrazione, seed

### Manual Testing
- [ ] Onboarding completo
- [ ] Import CSV reale (estratto conto Federico)
- [ ] Confronto risultati con Excel manuale
- [ ] Suggerimenti allocazione pilastri
- [ ] Override tasse manuali

---

## Dipendenze

```
Phase 0 (Prep)
    ↓
Phase 1 (Database) ←── Blocca tutto
    ↓
Phase 2 (Services) ←── Parallelizzabili:
    ↓                   - forecast.py
Phase 3 (API)           - pillars.py
    ↓                   - taxes.py
Phase 4 (Frontend)      - bank_import.py
    ↓
Phase 5 (AI Categorization) ←── Post-MVP
    ↓
Phase 6 (Features Avanzate) ←── Post-MVP
```

---

## Ready to Start

→ **Inizia con Phase 0.1**: Crea branch e tag

```bash
cd /Users/federico/Documents/ClaudeCode/contaspiccioli
git tag v1.0-legacy
git checkout -b refactor/v2-pillar-cashflow
```

---

## Errori Noti e Mitigazioni

### Bug Codebase Esistente (da fixare in Phase 1)

| Bug | File | Problema | Fix |
|-----|------|----------|-----|
| `_months_elapsed()` | `budget.py` | Usa solo `date.today().month`, ignora anno | Riscrivere con calcolo corretto |
| Dual income tracking | `models.py` | `MonthlyIncome` e `Transaction` duplicano dati | Consolidare in `Transaction` con `is_income=True` |
| Tax % hardcoded | `config.py` | Aliquote nel codice sorgente | Spostare in `TaxSettings` con anno |

### Rischi Architetturali

| Rischio | Mitigazione |
|---------|-------------|
| Scadenze fiscali cambiano ogni anno | `TaxDeadline.due_date` modificabile + campo `notes` |
| Aliquote INPS cambiano | `TaxSettings` per anno, non globale |
| Metodo acconti (storico vs previsionale) | Supportare entrambi con flag |
| Rateizzazione complessa | Campo `installments_paid` + UI dedicata |

### Assunzioni Validate con Utente (2026-01-11)

- [x] **P3**: Include tasse + altre spese programmate (dentista, bicicletta, etc.) → Aggiunto `PlannedExpense` model
- [x] **Multi-conto**: NO. Struttura semplificata: BBVA (P1), Fineco (P2+P3+P4), Fideuram (solo F24)
- [x] **Acconti**: Metodo storico (100% anno precedente per imposta, 80% per INPS)

---

## Riferimenti

### Documentazione Locale
- **Guida Coletti/Magri**: `docs/Guida Educati e Finanziati.pdf`
- **Excel Previsionale**: `Bilancio Personale - Federico.xlsx` → foglio "2026 - Previsionale"
- **UI Sibill**: `docs/sibill-screenshot.png` (confronto previsto/effettivo)
- **Guida Originale**: `La guida di Contaspiccioli.md`

### Fonti Online Consultate
- [4 Pilastri Coletti - Investimi](https://investimi.com/4-pilastri-coletti/) - Target e strumenti per pilastro
- [Calcolo Tasse Forfettario - QuickFisco](https://quickfisco.it/blog/regime-forfettario/calcolo-tasse-regime-forfettario-spiegazione-ed-esempi/)
- [Scadenze Acconti 2025-2026 - QuickFisco](https://quickfisco.it/blog/calcolo-acconti-saldo-regime-forfettario-scadenze-esempi/)
- [Versamento Acconti - Regime-Forfettario.it](https://www.regime-forfettario.it/versamento-imposta-acconti-regime-forfettario/)
- [Regime Forfettario 2026 - Flextax](https://flextax.it/regime-forfettario-2026/)

---

## Stato Implementazione (Aggiornato 2026-01-13)

### Phase Status

| Phase | Stato | Note |
|-------|-------|------|
| Phase 0: Preparazione | **COMPLETATA** | Branch creato, tag v1.0-legacy |
| Phase 1: Database | **COMPLETATA** | Schema v2 in `models_v2.py` |
| Phase 2: Services | **COMPLETATA** | 4 servizi: forecast, pillars, taxes, bank_import |
| Phase 3: API | **COMPLETATA** | 1076 righe in `api_v2.py`, 38 endpoint |
| Phase 4: Frontend | **COMPLETATA** | Dashboard v2, Cashflow spreadsheet |
| Phase 5: AI Categorization | **POST-MVP** | Keywords base implementate, learning da fare |
| Phase 6: Features Avanzate | **POST-MVP** | Telegram, Export, Multi-anno |

### Test Coverage

- **116 test passano** (4 file test v2)
- Copertura: models, services, API, seed

### Sistema Dual v1/v2

**ATTENZIONE**: Coesistono due sistemi paralleli.

| Route | Sistema | File |
|-------|---------|------|
| `/`, `/summary`, `/pillars` | v1 (legacy) | models.py, budget.py |
| `/v2`, `/v2/cashflow` | v2 (nuovo) | models_v2.py, *_v2.py |

**Decisione richiesta**: Sunset v1 o coesistenza permanente?

---

## Code Review Completa (2026-01-13)

### Bug Identificati

#### Critical (da fixare subito)

| # | Bug | File | Fix Proposto |
|---|-----|------|--------------|
| 1 | **Calcolo IRPEF errato** | budget.py:136-141 | `irpef = (taxable_income - inps) * tax_rate` |
| 2 | **Catch vuoti** (errori silenziati) | bank_parser.py:53,166,199 | Loggare eccezioni |
| 3 | **Return None non gestito** | api_v2.py:384-386 | Validare category_id esiste |

#### Warning (da pianificare)

| # | Bug | File |
|---|-----|------|
| 4 | IndexError su CSV vuoto | bank_import_v2.py:154 |
| 5 | Calcolo 3 mesi fragile | pillars_v2.py:196-200 |
| 6 | `_months_elapsed()` ignora anno | budget.py:93-96 |
| 7 | Race condition import | bank_import_v2.py:361-376 |
| 8 | KeyError potenziale | api_v2.py:972 |

### Performance Issues

| Priorita | Issue | Impatto | Fix |
|----------|-------|---------|-----|
| **CRITICO** | Query N+1 cashflow | ~240 query/request | Bulk query ForecastLine |
| ALTO | Calcoli senza cache | CPU waste | TTL cache 5 min |
| ALTO | Query ridondanti dashboard | Multiple scans | Consolidare in service |
| MEDIO | Mancano indici compositi | Slow lookups | Migration DB |

### Architecture Issues

| Priorita | Issue | Descrizione |
|----------|-------|-------------|
| **P0** | Sistema dual v1/v2 | Rimuovere v1 o documentare freeze |
| **P1** | God object main.py | Estrarre route in routers/pages.py |
| **P1** | Valori hardcoded | Centralizzare 3500.00 in config.py |
| **P2** | Logica in API | Estrarre 230 righe cashflow in service |

---

## Prossimi Passi (Post-Review)

### Immediato (P0)

1. [ ] **Fix Query N+1** - Precarica ForecastLine con bulk query
2. [ ] **Decisione v1** - Freeze, migrate, o remove?
3. [ ] **Fix Critical Bug #1** - Calcolo IRPEF (se v1 resta attivo)

### Short-term (P1)

4. [ ] **Refactor main.py** - Estrai HTML routes
5. [ ] **Centralizza default** - `DEFAULT_MONTHLY_INCOME` in config
6. [ ] **Indici DB** - `ix_forecast_line_month_cat`

### Medium-term (P2)

7. [ ] **Service cashflow** - Estrai da api_v2.py
8. [ ] **Caching** - calculate_monthly_budget con TTL
9. [ ] **Fix warning bugs** - Race condition, CSV vuoto

### Post-MVP

10. [ ] Phase 5: Learning keywords da categorizzazione manuale
11. [ ] Phase 6.1: Notifiche Telegram scadenze
12. [ ] Phase 6.2: Export CSV/PDF
13. [ ] Phase 6.3: Confronto anno su anno

---

## Changelog Piano

| Data | Modifica |
|------|----------|
| 2026-01-11 | Creazione piano v1 |
| 2026-01-11 | **REVIEW**: Corretto target P1 (3 mesi, non 1-2), P2 (3-12 mesi), P3 (include tutte spese programmate) |
| 2026-01-11 | **REVIEW**: Aggiornato `TaxSettings`: imposta 100% storico, INPS 80%, soglie 52€/258€ |
| 2026-01-11 | **REVIEW**: Aggiunto `PlannedExpense` per spese programmate P3 (dentista, bici, etc.) |
| 2026-01-11 | **REVIEW**: Semplificato `Account`: BBVA=P1, Fineco=P2+P3+P4, Fideuram=solo F24 |
| 2026-01-11 | **REVIEW**: Aggiunta sezione "Errori Noti e Mitigazioni" |
| 2026-01-11 | **VALIDATE**: Confermate assunzioni con utente |
| 2026-01-13 | **COMPLETATO**: Phase 0-4 (refactoring v2) |
| 2026-01-13 | **CODE REVIEW**: Bug hunting (10 bug), Architecture, Performance, Completeness |
| 2026-01-13 | **AGGIUNTO**: Sezione "Stato Implementazione" e "Code Review Completa" |
