# TODO - Contaspiccioli

## Bug da Fixare

### Priorità Alta
- [ ] **Reset mensile checkbox**: `tax_paid_this_month` e `investment_paid_this_month` non si resettano automaticamente a inizio mese
- [ ] **Integrare `prior_year_tax_advance`**: il campo è salvato ma non usato nei calcoli delle scadenze di giugno
- [ ] **Sincronizzazione pilastri continua**: i saldi pilastri si aggiornano solo al primo setup, non quando si modifica la configurazione

### Priorità Media
- [ ] **Tooltip mobile**: i tooltip hover non funzionano su touch - convertire in click/tap
- [ ] **Tabella transazioni mobile**: la tabella non è responsive, servono card su mobile

## Funzionalità da Aggiungere

### Dashboard
- [ ] **Quick expense**: pulsante "+ Spesa" per registrare spese velocemente dal dashboard
- [ ] **Breakdown categorie**: mostrare dettaglio spese variabili per categoria con barre progresso
- [ ] **Grafici trend**: andamento spese mensili, distribuzione categorie (pie chart)

### P.IVA Forfettaria
- [ ] **Scelta aliquota**: 5% (primi 5 anni) vs 15% (standard)
- [ ] **Riduzione INPS 35%/50%**: opzione per artigiani/commercianti con riduzione contributi
- [ ] **Codice ATECO**: selezione codice per coefficiente redditività corretto (non tutti sono 78%)
- [ ] **Gestione Separata vs Artigiani**: differenziare calcoli INPS

### Proiezioni
- [ ] **Multi-year view**: confronto anno su anno
- [ ] **Proiezione interattiva**: slider per vedere scenari "what if" con introiti diversi
- [ ] **Export CSV/Excel**: per portare dati su Google Sheets

### UX/UI
- [ ] **Transazioni ricorrenti**: auto-popolamento spese fisse ogni mese
- [ ] **Dark/Light mode toggle**: attualmente solo dark
- [ ] **PWA**: installabile come app su mobile
- [ ] **Onboarding progress**: salvare progresso parziale del wizard

## Refactoring Tecnico
- [ ] **Test**: aggiungere pytest per le funzioni di calcolo
- [ ] **Validazione form**: aggiungere validazione lato client con feedback
- [ ] **Error handling**: pagine errore personalizzate (404, 500)
- [ ] **Logging strutturato**: migliorare logging per debug

## Note dalla Ricerca UX Fintech
- Microinterazioni e animazioni per feedback
- AI personalization per suggerimenti budget
- Biometric login (fuori scope per ora)
- Real-time alerts per budget superato
