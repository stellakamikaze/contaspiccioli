# Handoff: Contaspiccioli v2.0 Refactoring

**Data**: 2026-01-11
**Sessione**: Pianificazione refactoring completo

---

## Contesto

Contaspiccioli passa da "pillar tracker" a **cash flow planner a 12+ mesi**.

### Vision
- Previsionale 12 mesi (replica Excel Federico)
- Confronto previsto vs effettivo (stile Sibill)
- Import estratto conto → Claude categorizza
- Suggerimenti allocazione surplus tra pilastri

### Decisioni Chiave Prese

1. **4 Pilastri Mantenuti** (da guida Coletti/Magri):
   - P1: Liquidità (3+ mesi) → BBVA
   - P2: Emergenza (3-12 mesi) → Fineco XEON
   - P3: Spese Previste (tasse + programmate) → Fineco XEON → Fideuram F24
   - P4: Investimenti (10+ anni) → Fineco

2. **P3 Esteso**: Include tasse + spese programmate (dentista, bici, etc.) con accantonamento automatico

3. **Calcolo Tasse Verificato**:
   - Imposta sostitutiva: 15%
   - Coefficiente: 78%
   - INPS: 26.07% (gestione separata)
   - Acconti: 100% imposta (50+50), 80% INPS (40+40)
   - Soglia esonero: < 52€

---

## Prossima Sessione

### Task Pronto: `contaspiccioli-88b`
**Phase 0: Preparazione**

```bash
cd /Users/federico/Documents/ClaudeCode/contaspiccioli
bd update contaspiccioli-88b --status=in_progress

# Azioni:
git tag v1.0-legacy
git checkout -b refactor/v2-pillar-cashflow
cp /Users/federico/Downloads/Guida\ Educati\ e\ Finanziati.pdf docs/
# Backup DB
```

### Poi: `contaspiccioli-ffg`
**Phase 1: Nuovo Schema Database**

Vedi `IMPLEMENTATION_PLAN.md` sezione 1.1-1.6 per tutti i modelli.

---

## File Importanti

| File | Contenuto |
|------|-----------|
| `IMPLEMENTATION_PLAN.md` | Piano completo 6 fasi con modelli e API |
| `CLAUDE.md` | Overview progetto + dati fiscali |
| `Bilancio Personale - Federico.xlsx` | Template previsionale di riferimento |
| `docs/Guida Educati e Finanziati.pdf` | 4 pilastri Coletti (da copiare) |

---

## Beads Status

```
contaspiccioli-3jg: Feature principale refactoring v2.0
├── contaspiccioli-88b: Phase 0 (PRONTO)
├── contaspiccioli-ffg: Phase 1 (blocked by 88b)
├── contaspiccioli-dyy: Phase 2 (blocked by ffg)
├── contaspiccioli-weh: Phase 3 (blocked by ffg)
└── contaspiccioli-eee: Phase 4 (blocked by weh)
```

---

## Note per Claude

- NON toccare issues legacy (97r, cui, at9, etc.) - saranno chiuse dopo refactoring
- Il codebase attuale ha bug in `_months_elapsed()` - ignorare, sarà riscritto
- Federico usa XEON su Fineco per P2+P3, poi bonifico su Fideuram solo per F24
- Estratto conto verrà fornito mensilmente per categorizzazione
