"""Tests for Contaspiccioli v2.0 models."""
import pytest
from datetime import date, datetime
from decimal import Decimal

from app.models_v2 import (
    # Enums
    TaxRegime, AdvanceMethod, CategoryType, LineType,
    TransactionSource, DeadlineType, AccountType,
    # Models
    Account, Pillar, Category, ForecastMonth, ForecastLine,
    Transaction, TaxSettings, TaxDeadline, PlannedExpense, UserSettings,
)


class TestEnums:
    """Test enum values."""

    def test_tax_regime_values(self):
        assert TaxRegime.FORFETTARIO.value == "forfettario"
        assert TaxRegime.ORDINARIO.value == "ordinario"
        assert TaxRegime.DIPENDENTE.value == "dipendente"

    def test_category_type_values(self):
        assert CategoryType.INCOME.value == "income"
        assert CategoryType.FIXED.value == "fixed"
        assert CategoryType.VARIABLE.value == "variable"

    def test_line_type_values(self):
        assert LineType.INCOME.value == "income"
        assert LineType.FIXED_COST.value == "fixed_cost"
        assert LineType.VARIABLE_COST.value == "variable_cost"

    def test_transaction_source_values(self):
        assert TransactionSource.BANK_IMPORT.value == "bank_import"
        assert TransactionSource.MANUAL.value == "manual"

    def test_deadline_type_values(self):
        assert DeadlineType.SALDO.value == "saldo"
        assert DeadlineType.ACCONTO_1.value == "acconto_1"
        assert DeadlineType.ACCONTO_2.value == "acconto_2"


class TestAccount:
    """Test Account model."""

    def test_create_account(self, db_session):
        account = Account(
            name="BBVA",
            account_type=AccountType.CHECKING,
            balance=Decimal("5000.00"),
        )
        db_session.add(account)
        db_session.commit()

        assert account.id is not None
        assert account.name == "BBVA"
        assert account.account_type == AccountType.CHECKING
        assert account.balance == Decimal("5000.00")
        assert account.is_active is True

    def test_account_types(self, db_session):
        accounts = [
            Account(name="BBVA", account_type=AccountType.CHECKING),
            Account(name="Fineco", account_type=AccountType.BROKER),
            Account(name="Fideuram", account_type=AccountType.TAX_ONLY),
        ]
        db_session.add_all(accounts)
        db_session.commit()

        assert len(db_session.query(Account).all()) == 3


class TestPillar:
    """Test Pillar model."""

    def test_create_pillar(self, db_session):
        pillar = Pillar(
            number=1,
            name="liquidita",
            display_name="Liquidità",
            description="Conto corrente principale",
            current_balance=Decimal("5958.00"),
            target_balance=Decimal("10500.00"),
            target_months=3,
            instrument="Conto corrente",
            account_name="BBVA",
            priority=1,
        )
        db_session.add(pillar)
        db_session.commit()

        assert pillar.id is not None
        assert pillar.number == 1
        assert pillar.target_months == 3

    def test_pillar_completion_percentage(self, db_session):
        pillar = Pillar(
            number=2,
            name="emergenza",
            display_name="Emergenza",
            current_balance=Decimal("5000.00"),
            target_balance=Decimal("10000.00"),
        )
        db_session.add(pillar)
        db_session.commit()

        assert pillar.completion_percentage == 50.0

    def test_pillar_completion_zero_target(self, db_session):
        pillar = Pillar(
            number=4,
            name="investimenti",
            display_name="Investimenti",
            current_balance=Decimal("1000.00"),
            target_balance=Decimal("0.00"),
        )
        db_session.add(pillar)
        db_session.commit()

        assert pillar.completion_percentage == 100.0

    def test_pillar_completion_over_target(self, db_session):
        pillar = Pillar(
            number=1,
            name="liquidita",
            display_name="Liquidità",
            current_balance=Decimal("12000.00"),
            target_balance=Decimal("10000.00"),
        )
        db_session.add(pillar)
        db_session.commit()

        assert pillar.completion_percentage == 100.0  # Capped at 100%


class TestCategory:
    """Test Category model."""

    def test_create_category(self, db_session):
        category = Category(
            name="Alimentari",
            type=CategoryType.VARIABLE,
            icon="🍕",
            color="#10B981",
            monthly_budget=Decimal("350.00"),
            keywords=["ESSELUNGA", "CARREFOUR", "COOP"],
        )
        db_session.add(category)
        db_session.commit()

        assert category.id is not None
        assert category.type == CategoryType.VARIABLE
        assert category.keywords == ["ESSELUNGA", "CARREFOUR", "COOP"]

    def test_category_pillar_relationship(self, db_session):
        pillar = Pillar(number=1, name="liquidita", display_name="Liquidità")
        db_session.add(pillar)
        db_session.commit()

        category = Category(
            name="Affitto",
            type=CategoryType.FIXED,
            pillar_id=pillar.id,
        )
        db_session.add(category)
        db_session.commit()

        assert category.pillar.name == "liquidita"
        assert len(pillar.categories) == 1


class TestForecastMonth:
    """Test ForecastMonth model."""

    def test_create_forecast_month(self, db_session):
        forecast = ForecastMonth(
            year=2026,
            month=1,
            opening_balance=Decimal("5958.00"),
            expected_income=Decimal("3500.00"),
            expected_fixed_costs=Decimal("1350.00"),
            expected_variable_costs=Decimal("1150.00"),
        )
        db_session.add(forecast)
        db_session.commit()

        assert forecast.id is not None
        assert forecast.year == 2026
        assert forecast.month == 1

    def test_forecast_month_properties(self, db_session):
        forecast = ForecastMonth(
            year=2026,
            month=1,
            opening_balance=Decimal("5958.00"),
            expected_income=Decimal("3500.00"),
            actual_income=Decimal("3500.00"),
            expected_fixed_costs=Decimal("1350.00"),
            actual_fixed_costs=Decimal("1350.00"),
            expected_variable_costs=Decimal("1150.00"),
            actual_variable_costs=Decimal("1200.00"),  # 50€ over budget
        )
        db_session.add(forecast)
        db_session.commit()

        assert forecast.expected_total_costs == Decimal("2500.00")
        assert forecast.actual_total_costs == Decimal("2550.00")
        assert forecast.expected_balance == Decimal("6958.00")  # 5958 + 3500 - 2500
        assert forecast.actual_balance == Decimal("6908.00")    # 5958 + 3500 - 2550
        assert forecast.variance == Decimal("-50.00")            # 6908 - 6958


class TestForecastLine:
    """Test ForecastLine model."""

    def test_create_forecast_line(self, db_session):
        forecast = ForecastMonth(year=2026, month=1)
        db_session.add(forecast)
        db_session.commit()

        line = ForecastLine(
            forecast_month_id=forecast.id,
            line_type=LineType.FIXED_COST,
            description="Affitto",
            expected_amount=Decimal("700.00"),
            actual_amount=Decimal("700.00"),
            is_recurring=True,
            recurrence_day=1,
        )
        db_session.add(line)
        db_session.commit()

        assert line.id is not None
        assert line.variance == Decimal("0.00")

    def test_forecast_line_relationship(self, db_session):
        forecast = ForecastMonth(year=2026, month=1)
        db_session.add(forecast)
        db_session.commit()

        line = ForecastLine(
            forecast_month_id=forecast.id,
            line_type=LineType.INCOME,
            description="Ufficio Furore",
            expected_amount=Decimal("3500.00"),
        )
        db_session.add(line)
        db_session.commit()

        assert len(forecast.lines) == 1
        assert forecast.lines[0].description == "Ufficio Furore"


class TestTransaction:
    """Test Transaction model."""

    def test_create_manual_transaction(self, db_session):
        tx = Transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-45.20"),
            description="Spesa Esselunga",
            source=TransactionSource.MANUAL,
            is_income=False,
        )
        db_session.add(tx)
        db_session.commit()

        assert tx.id is not None
        assert tx.source == TransactionSource.MANUAL

    def test_create_bank_import_transaction(self, db_session):
        tx = Transaction(
            date=date(2026, 1, 10),
            amount=Decimal("3500.00"),
            description="Fattura Ufficio Furore",
            source=TransactionSource.BANK_IMPORT,
            original_description="BONIFICO DA UFFICIO FURORE SRL - FATT 2026/001",
            is_income=True,
            is_taxable=True,
        )
        db_session.add(tx)
        db_session.commit()

        assert tx.source == TransactionSource.BANK_IMPORT
        assert tx.is_taxable is True


class TestTaxSettings:
    """Test TaxSettings model."""

    def test_create_tax_settings(self, db_session):
        settings = TaxSettings(
            year=2026,
            regime=TaxRegime.FORFETTARIO,
            coefficient=Decimal("0.78"),
            inps_rate=Decimal("0.2607"),
            tax_rate=Decimal("0.15"),
            advance_method=AdvanceMethod.STORICO,
        )
        db_session.add(settings)
        db_session.commit()

        assert settings.id is not None
        assert settings.regime == TaxRegime.FORFETTARIO

    def test_calculate_tax(self, db_session):
        settings = TaxSettings(
            year=2026,
            regime=TaxRegime.FORFETTARIO,
            coefficient=Decimal("0.78"),
            inps_rate=Decimal("0.2607"),
            tax_rate=Decimal("0.15"),
        )
        db_session.add(settings)
        db_session.commit()

        result = settings.calculate_tax(Decimal("42000.00"))

        # Taxable income: 42000 * 0.78 = 32760
        assert result["taxable_income"] == Decimal("32760.00")

        # INPS: 32760 * 0.2607 = 8540.532 ≈ 8540.53
        expected_inps = Decimal("32760.00") * Decimal("0.2607")
        assert result["inps"] == expected_inps

        # IRPEF base: 32760 - INPS
        # IRPEF: (32760 - INPS) * 0.15
        irpef_base = Decimal("32760.00") - expected_inps
        expected_irpef = irpef_base * Decimal("0.15")
        assert result["irpef"] == expected_irpef

    def test_tax_thresholds(self, db_session):
        settings = TaxSettings(
            year=2026,
            min_threshold=Decimal("52.00"),
            single_payment_threshold=Decimal("258.00"),
        )
        db_session.add(settings)
        db_session.commit()

        assert settings.min_threshold == Decimal("52.00")
        assert settings.single_payment_threshold == Decimal("258.00")


class TestTaxDeadline:
    """Test TaxDeadline model."""

    def test_create_tax_deadline(self, db_session):
        deadline = TaxDeadline(
            year=2026,
            deadline_type=DeadlineType.SALDO,
            name="Saldo 2025 + 1° Acconto 2026",
            due_date=date(2026, 7, 21),
            amount_due=Decimal("7527.00"),
        )
        db_session.add(deadline)
        db_session.commit()

        assert deadline.id is not None
        assert deadline.remaining == Decimal("7527.00")
        assert deadline.is_paid is False

    def test_tax_deadline_partial_payment(self, db_session):
        deadline = TaxDeadline(
            year=2026,
            deadline_type=DeadlineType.ACCONTO_1,
            name="1° Acconto",
            due_date=date(2026, 7, 21),
            amount_due=Decimal("5000.00"),
            amount_paid=Decimal("2000.00"),
            installments_paid=2,
        )
        db_session.add(deadline)
        db_session.commit()

        assert deadline.remaining == Decimal("3000.00")
        assert deadline.is_paid is False

    def test_tax_deadline_fully_paid(self, db_session):
        deadline = TaxDeadline(
            year=2025,
            deadline_type=DeadlineType.ACCONTO_2,
            name="2° Acconto 2025",
            due_date=date(2025, 11, 30),
            amount_due=Decimal("5460.00"),
            amount_paid=Decimal("5460.00"),
        )
        db_session.add(deadline)
        db_session.commit()

        assert deadline.remaining == Decimal("0.00")
        assert deadline.is_paid is True


class TestPlannedExpense:
    """Test PlannedExpense model."""

    def test_create_planned_expense(self, db_session):
        expense = PlannedExpense(
            name="Dentista",
            target_amount=Decimal("500.00"),
            current_amount=Decimal("0.00"),
            target_date=date(2026, 3, 31),
        )
        db_session.add(expense)
        db_session.commit()

        assert expense.id is not None
        assert expense.remaining == Decimal("500.00")
        assert expense.completion_percentage == 0.0

    def test_planned_expense_partial_funded(self, db_session):
        expense = PlannedExpense(
            name="Bicicletta",
            target_amount=Decimal("1000.00"),
            current_amount=Decimal("400.00"),
            target_date=date(2026, 6, 30),
        )
        db_session.add(expense)
        db_session.commit()

        assert expense.remaining == Decimal("600.00")
        assert expense.completion_percentage == 40.0

    def test_calculate_monthly_contribution(self, db_session):
        # Target: 500€ by March 2026, starting from January 2026
        expense = PlannedExpense(
            name="Dentista",
            target_amount=Decimal("500.00"),
            current_amount=Decimal("0.00"),
            target_date=date(2026, 3, 31),
        )
        db_session.add(expense)
        db_session.commit()

        # Calculate from January 1st, 2026 → 2 months to March (Jan→Feb, Feb→Mar)
        contribution = expense.calculate_monthly_contribution(date(2026, 1, 1))

        # 500 / 2 = 250.00
        assert contribution == Decimal("250.00")

    def test_calculate_monthly_contribution_past_date(self, db_session):
        expense = PlannedExpense(
            name="Test",
            target_amount=Decimal("500.00"),
            current_amount=Decimal("200.00"),
            target_date=date(2025, 12, 31),  # Past date
        )
        db_session.add(expense)
        db_session.commit()

        # If target date is past, return remaining amount
        contribution = expense.calculate_monthly_contribution(date(2026, 1, 1))
        assert contribution == Decimal("300.00")


class TestUserSettings:
    """Test UserSettings model."""

    def test_create_user_settings(self, db_session):
        settings = UserSettings(
            monthly_income=Decimal("3500.00"),
            income_type=TaxRegime.FORFETTARIO,
            average_monthly_expenses=Decimal("2500.00"),
            setup_completed=True,
        )
        db_session.add(settings)
        db_session.commit()

        assert settings.id is not None
        assert settings.income_type == TaxRegime.FORFETTARIO
        assert settings.setup_completed is True


class TestRelationships:
    """Test model relationships."""

    def test_pillar_tax_deadlines(self, db_session):
        pillar = Pillar(number=3, name="spese_previste", display_name="Spese Previste")
        db_session.add(pillar)
        db_session.commit()

        deadlines = [
            TaxDeadline(
                year=2026,
                deadline_type=DeadlineType.SALDO,
                name="Saldo 2025",
                due_date=date(2026, 7, 21),
                amount_due=Decimal("5000.00"),
                pillar_id=pillar.id,
            ),
            TaxDeadline(
                year=2026,
                deadline_type=DeadlineType.ACCONTO_2,
                name="2° Acconto 2026",
                due_date=date(2026, 11, 30),
                amount_due=Decimal("3000.00"),
                pillar_id=pillar.id,
            ),
        ]
        db_session.add_all(deadlines)
        db_session.commit()

        assert len(pillar.tax_deadlines) == 2

    def test_pillar_planned_expenses(self, db_session):
        pillar = Pillar(number=3, name="spese_previste", display_name="Spese Previste")
        db_session.add(pillar)
        db_session.commit()

        expenses = [
            PlannedExpense(
                name="Dentista",
                target_amount=Decimal("500.00"),
                target_date=date(2026, 3, 31),
                pillar_id=pillar.id,
            ),
            PlannedExpense(
                name="Bicicletta",
                target_amount=Decimal("1000.00"),
                target_date=date(2026, 6, 30),
                pillar_id=pillar.id,
            ),
        ]
        db_session.add_all(expenses)
        db_session.commit()

        assert len(pillar.planned_expenses) == 2

    def test_category_transactions(self, db_session):
        category = Category(name="Alimentari", type=CategoryType.VARIABLE)
        db_session.add(category)
        db_session.commit()

        transactions = [
            Transaction(
                date=date(2026, 1, 5),
                amount=Decimal("-45.20"),
                description="Esselunga",
                category_id=category.id,
            ),
            Transaction(
                date=date(2026, 1, 12),
                amount=Decimal("-32.80"),
                description="Carrefour",
                category_id=category.id,
            ),
        ]
        db_session.add_all(transactions)
        db_session.commit()

        assert len(category.transactions) == 2
