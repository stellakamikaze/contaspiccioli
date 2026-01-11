"""Tests for Contaspiccioli v2.0 services."""
import pytest
from datetime import date
from decimal import Decimal

from app.models_v2 import (
    Pillar, Category, CategoryType, ForecastMonth, ForecastLine,
    Transaction, TaxSettings, TaxDeadline, TaxRegime, AdvanceMethod,
    DeadlineType, TransactionSource, LineType
)
from app.services.forecast_v2 import (
    get_month_name, get_or_create_forecast_month,
    generate_yearly_forecast, get_forecast_comparison,
    update_forecast_actuals, project_balance
)
from app.services.pillars_v2 import (
    get_pillar_status, calculate_target_balances,
    suggest_allocation, update_pillar_balance, record_transfer,
    get_pillar_summary
)
from app.services.taxes_v2 import (
    get_or_create_tax_settings, calculate_annual_taxes,
    generate_tax_deadlines, calculate_monthly_reserve,
    get_tax_coverage, record_tax_payment
)
from app.services.bank_import_v2 import (
    parse_italian_date, parse_amount, categorize_transaction,
    parse_bank_statement, import_bank_statement, BankFormat
)
from app.seed_v2 import seed_pillars, seed_categories, seed_tax_settings


# ==================== FIXTURES ====================

@pytest.fixture
def seeded_db(db_session):
    """Database with seed data."""
    seed_pillars(db_session)
    p1 = db_session.query(Pillar).filter(Pillar.number == 1).first()
    seed_categories(db_session, pillar_p1_id=p1.id)
    seed_tax_settings(db_session, year=2026)
    return db_session


@pytest.fixture
def sample_csv():
    """Sample bank statement CSV."""
    return """Data;Descrizione;Importo
15/01/2026;ESSELUNGA MILANO;-45,20
18/01/2026;BONIFICO DA UFFICIO FURORE SRL;3500,00
20/01/2026;PIZZERIA DA MARIO;-28,50
22/01/2026;AFFITTO GENNAIO;-700,00
25/01/2026;AMAZON EU;-89,90
"""


# ==================== FORECAST SERVICE ====================

class TestForecastService:
    """Test forecast service."""

    def test_get_month_name(self):
        assert get_month_name(1) == "Gennaio"
        assert get_month_name(6) == "Giugno"
        assert get_month_name(12) == "Dicembre"
        assert get_month_name(0) == ""
        assert get_month_name(13) == ""

    def test_get_or_create_forecast_month_creates_new(self, db_session):
        forecast = get_or_create_forecast_month(
            db_session, 2026, 1,
            opening_balance=Decimal("5000.00")
        )

        assert forecast.id is not None
        assert forecast.year == 2026
        assert forecast.month == 1
        assert forecast.opening_balance == Decimal("5000.00")

    def test_get_or_create_forecast_month_returns_existing(self, db_session):
        # Create first
        forecast1 = get_or_create_forecast_month(
            db_session, 2026, 1,
            opening_balance=Decimal("5000.00")
        )

        # Get again
        forecast2 = get_or_create_forecast_month(db_session, 2026, 1)

        assert forecast2.id == forecast1.id

    def test_generate_yearly_forecast(self, seeded_db):
        forecasts = generate_yearly_forecast(
            seeded_db,
            year=2026,
            base_income=Decimal("3500.00"),
            opening_balance=Decimal("5000.00")
        )

        assert len(forecasts) == 12
        assert forecasts[0].year == 2026
        assert forecasts[0].month == 1
        assert forecasts[0].opening_balance == Decimal("5000.00")
        # Check that lines were created
        assert len(forecasts[0].lines) > 0

    def test_project_balance(self, seeded_db):
        # Create some forecast data first
        generate_yearly_forecast(
            seeded_db,
            year=2026,
            base_income=Decimal("3500.00"),
            opening_balance=Decimal("5000.00")
        )

        projections = project_balance(seeded_db, months_ahead=6)

        assert len(projections) == 6
        assert 'month' in projections[0]
        assert 'opening' in projections[0]
        assert 'closing' in projections[0]


# ==================== PILLARS SERVICE ====================

class TestPillarsService:
    """Test pillars service."""

    def test_get_pillar_status(self, seeded_db):
        statuses = get_pillar_status(seeded_db)

        assert len(statuses) == 4
        assert statuses[0].number == 1
        assert statuses[0].name == "liquidita"

    def test_pillar_status_shortfall(self, seeded_db):
        # Set up a pillar with current < target
        p1 = seeded_db.query(Pillar).filter(Pillar.number == 1).first()
        p1.current_balance = Decimal("5000.00")
        p1.target_balance = Decimal("10000.00")
        seeded_db.commit()

        statuses = get_pillar_status(seeded_db)
        p1_status = next(s for s in statuses if s.number == 1)

        assert p1_status.shortfall == Decimal("5000.00")
        assert p1_status.surplus == Decimal("0.00")
        assert p1_status.completion_percentage == 50.0

    def test_calculate_target_balances(self, seeded_db):
        targets = calculate_target_balances(
            seeded_db,
            average_monthly_expenses=Decimal("2500.00")
        )

        # P1: 3 months = 7500
        p1 = seeded_db.query(Pillar).filter(Pillar.number == 1).first()
        assert targets[p1.id] == Decimal("7500.00")

        # P2: 6 months = 15000
        p2 = seeded_db.query(Pillar).filter(Pillar.number == 2).first()
        assert targets[p2.id] == Decimal("15000.00")

    def test_suggest_allocation_emergency_first(self, seeded_db):
        # P2 under target, P4 available
        p2 = seeded_db.query(Pillar).filter(Pillar.number == 2).first()
        p2.current_balance = Decimal("0.00")
        p2.target_balance = Decimal("10000.00")
        seeded_db.commit()

        suggestions = suggest_allocation(seeded_db, Decimal("2000.00"))

        assert len(suggestions) > 0
        assert suggestions[0].pillar_id == p2.id
        assert suggestions[0].amount <= Decimal("2000.00")

    def test_update_pillar_balance(self, seeded_db):
        p1 = seeded_db.query(Pillar).filter(Pillar.number == 1).first()

        updated = update_pillar_balance(seeded_db, p1.id, Decimal("8000.00"))

        assert updated.current_balance == Decimal("8000.00")

    def test_record_transfer(self, seeded_db):
        p1 = seeded_db.query(Pillar).filter(Pillar.number == 1).first()
        p2 = seeded_db.query(Pillar).filter(Pillar.number == 2).first()

        p1.current_balance = Decimal("10000.00")
        p2.current_balance = Decimal("0.00")
        seeded_db.commit()

        from_p, to_p = record_transfer(seeded_db, p1.id, p2.id, Decimal("2000.00"))

        assert from_p.current_balance == Decimal("8000.00")
        assert to_p.current_balance == Decimal("2000.00")

    def test_record_transfer_insufficient_funds(self, seeded_db):
        p1 = seeded_db.query(Pillar).filter(Pillar.number == 1).first()
        p2 = seeded_db.query(Pillar).filter(Pillar.number == 2).first()

        p1.current_balance = Decimal("100.00")
        seeded_db.commit()

        with pytest.raises(ValueError, match="Insufficient balance"):
            record_transfer(seeded_db, p1.id, p2.id, Decimal("500.00"))

    def test_get_pillar_summary(self, seeded_db):
        summary = get_pillar_summary(seeded_db)

        assert 'pillars' in summary
        assert 'total_balance' in summary
        assert 'overall_completion' in summary
        assert len(summary['pillars']) == 4


# ==================== TAXES SERVICE ====================

class TestTaxesService:
    """Test taxes service."""

    def test_get_or_create_tax_settings(self, db_session):
        settings = get_or_create_tax_settings(db_session, 2026)

        assert settings.year == 2026
        assert settings.regime == TaxRegime.FORFETTARIO
        assert settings.coefficient == Decimal("0.78")

    def test_calculate_annual_taxes(self, seeded_db):
        settings = seeded_db.query(TaxSettings).filter(TaxSettings.year == 2026).first()

        breakdown = calculate_annual_taxes(Decimal("42000.00"), settings)

        # 42000 * 0.78 = 32760 taxable
        assert breakdown.taxable_income == Decimal("32760.00")
        # INPS: 32760 * 0.2607 ≈ 8540.53
        assert breakdown.inps > Decimal("8500.00")
        assert breakdown.inps < Decimal("8600.00")
        # Total tax should be reasonable
        assert breakdown.total_tax > Decimal("10000.00")
        assert breakdown.total_tax < Decimal("15000.00")

    def test_generate_tax_deadlines_below_threshold(self, seeded_db):
        settings = seeded_db.query(TaxSettings).filter(TaxSettings.year == 2026).first()
        settings.prior_year_tax_paid = Decimal("40.00")  # Below 52€
        settings.prior_year_inps_paid = Decimal("0.00")
        seeded_db.commit()

        # Need to seed pillars for P3 association
        deadlines = generate_tax_deadlines(seeded_db, 2026, Decimal("1000.00"))

        # Below threshold = no deadlines
        assert len(deadlines) == 0

    def test_generate_tax_deadlines_split_payment(self, seeded_db):
        seed_pillars(seeded_db)
        settings = seeded_db.query(TaxSettings).filter(TaxSettings.year == 2026).first()
        settings.prior_year_tax_paid = Decimal("5000.00")
        settings.prior_year_inps_paid = Decimal("8000.00")
        seeded_db.commit()

        deadlines = generate_tax_deadlines(seeded_db, 2026, Decimal("42000.00"))

        # Above threshold = 2 deadlines (50/50 split)
        assert len(deadlines) == 2
        assert deadlines[0].deadline_type == DeadlineType.SALDO
        assert deadlines[1].deadline_type == DeadlineType.ACCONTO_2

    def test_calculate_monthly_reserve(self, seeded_db):
        seed_pillars(seeded_db)
        settings = seeded_db.query(TaxSettings).filter(TaxSettings.year == 2026).first()
        settings.prior_year_tax_paid = Decimal("5000.00")
        settings.prior_year_inps_paid = Decimal("8000.00")
        seeded_db.commit()

        generate_tax_deadlines(seeded_db, 2026, Decimal("42000.00"))

        reserve = calculate_monthly_reserve(seeded_db, 2026)

        # Should be a positive amount
        assert reserve > Decimal("0.00")

    def test_record_tax_payment(self, seeded_db):
        seed_pillars(seeded_db)
        settings = seeded_db.query(TaxSettings).filter(TaxSettings.year == 2026).first()
        settings.prior_year_tax_paid = Decimal("5000.00")
        settings.prior_year_inps_paid = Decimal("8000.00")
        seeded_db.commit()

        deadlines = generate_tax_deadlines(seeded_db, 2026, Decimal("42000.00"))
        deadline = deadlines[0]
        original_amount = deadline.amount_due

        updated = record_tax_payment(seeded_db, deadline.id, Decimal("1000.00"))

        assert updated.amount_paid == Decimal("1000.00")
        assert updated.remaining == original_amount - Decimal("1000.00")


# ==================== BANK IMPORT SERVICE ====================

class TestBankImportService:
    """Test bank import service."""

    def test_parse_italian_date(self):
        assert parse_italian_date("15/01/2026") == date(2026, 1, 15)
        assert parse_italian_date("15-01-2026") == date(2026, 1, 15)
        assert parse_italian_date("2026-01-15") == date(2026, 1, 15)
        assert parse_italian_date("invalid") is None

    def test_parse_amount_european(self):
        assert parse_amount("1.234,56") == Decimal("1234.56")
        assert parse_amount("-45,20") == Decimal("-45.20")
        assert parse_amount("3500,00") == Decimal("3500.00")
        assert parse_amount("€ 100,00") == Decimal("100.00")

    def test_parse_amount_us(self):
        assert parse_amount("1,234.56") == Decimal("1234.56")
        assert parse_amount("-45.20") == Decimal("-45.20")

    def test_categorize_transaction(self, seeded_db):
        category = categorize_transaction(seeded_db, "PAGAMENTO POS ESSELUNGA MILANO")

        assert category is not None
        assert category.name == "Alimentari"

    def test_categorize_transaction_no_match(self, seeded_db):
        category = categorize_transaction(seeded_db, "RANDOM UNKNOWN TRANSACTION")

        # Should return None for uncategorized
        assert category is None

    def test_parse_bank_statement(self, sample_csv, seeded_db):
        transactions = parse_bank_statement(sample_csv)

        assert len(transactions) == 5
        assert transactions[0].date == date(2026, 1, 15)
        assert transactions[0].amount == Decimal("-45.20")
        assert "ESSELUNGA" in transactions[0].original_description

    def test_import_bank_statement(self, sample_csv, seeded_db):
        result = import_bank_statement(
            seeded_db,
            sample_csv,
            year=2026,
            month=1
        )

        assert result.total_rows == 5
        assert result.imported == 5
        assert result.skipped == 0
        assert len(result.transactions) == 5
        # Some should be categorized
        categorized = sum(1 for tx in result.transactions if tx.category_id is not None)
        assert categorized > 0

    def test_import_bank_statement_wrong_month(self, sample_csv, seeded_db):
        result = import_bank_statement(
            seeded_db,
            sample_csv,
            year=2026,
            month=2  # Wrong month
        )

        assert result.imported == 0
        assert result.skipped == 5

    def test_import_bank_statement_duplicate_detection(self, sample_csv, seeded_db):
        # Import once
        result1 = import_bank_statement(seeded_db, sample_csv, 2026, 1)
        assert result1.imported == 5

        # Import again - should skip duplicates
        result2 = import_bank_statement(seeded_db, sample_csv, 2026, 1)
        assert result2.imported == 0
        assert result2.skipped == 5
