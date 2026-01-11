"""Tests for Contaspiccioli v2.0 API endpoints."""
import pytest
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models_v2 import (
    Pillar, Category, CategoryType, Transaction, TaxSettings,
    TaxDeadline, PlannedExpense, ForecastMonth, TransactionSource
)
from app.seed_v2 import seed_pillars, seed_categories, seed_tax_settings


@pytest.fixture
def api_client(db_session):
    """Create test client with database session."""
    from fastapi import FastAPI
    from app.routers.api_v2 import router
    from app.database import get_db

    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture
def seeded_client(api_client, db_session):
    """API client with seeded data."""
    seed_pillars(db_session)
    p1 = db_session.query(Pillar).filter(Pillar.number == 1).first()
    seed_categories(db_session, pillar_p1_id=p1.id)
    seed_tax_settings(db_session, year=2026)
    return api_client


# ==================== PILLARS API ====================

class TestPillarsAPI:
    """Test pillars API endpoints."""

    def test_list_pillars(self, seeded_client):
        response = seeded_client.get("/api/v2/pillars")
        assert response.status_code == 200
        pillars = response.json()
        assert len(pillars) == 4
        assert pillars[0]["number"] == 1

    def test_get_pillar(self, seeded_client, db_session):
        p1 = db_session.query(Pillar).filter(Pillar.number == 1).first()
        response = seeded_client.get(f"/api/v2/pillars/{p1.id}")
        assert response.status_code == 200
        assert response.json()["name"] == "liquidita"

    def test_get_pillar_not_found(self, seeded_client):
        response = seeded_client.get("/api/v2/pillars/9999")
        assert response.status_code == 404

    def test_get_pillars_status(self, seeded_client):
        response = seeded_client.get("/api/v2/pillars/status")
        assert response.status_code == 200
        statuses = response.json()
        assert len(statuses) == 4
        assert "shortfall" in statuses[0]
        assert "surplus" in statuses[0]

    def test_pillars_summary(self, seeded_client):
        response = seeded_client.get("/api/v2/pillars/summary")
        assert response.status_code == 200
        summary = response.json()
        assert "total_balance" in summary
        assert "overall_completion" in summary
        assert len(summary["pillars"]) == 4

    def test_update_pillar(self, seeded_client, db_session):
        p1 = db_session.query(Pillar).filter(Pillar.number == 1).first()
        response = seeded_client.put(
            f"/api/v2/pillars/{p1.id}",
            json={"current_balance": "5000.00"}
        )
        assert response.status_code == 200
        assert Decimal(response.json()["current_balance"]) == Decimal("5000.00")

    def test_reconcile_pillar_balance(self, seeded_client, db_session):
        p1 = db_session.query(Pillar).filter(Pillar.number == 1).first()
        response = seeded_client.put(
            f"/api/v2/pillars/{p1.id}/balance",
            params={"new_balance": "8000.00"}
        )
        assert response.status_code == 200
        assert Decimal(response.json()["current_balance"]) == Decimal("8000.00")

    def test_transfer_between_pillars(self, seeded_client, db_session):
        p1 = db_session.query(Pillar).filter(Pillar.number == 1).first()
        p2 = db_session.query(Pillar).filter(Pillar.number == 2).first()
        p1.current_balance = Decimal("10000.00")
        p2.current_balance = Decimal("0.00")
        db_session.commit()

        response = seeded_client.post(
            "/api/v2/pillars/transfer",
            json={
                "from_pillar_id": p1.id,
                "to_pillar_id": p2.id,
                "amount": "2000.00"
            }
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_transfer_insufficient_funds(self, seeded_client, db_session):
        p1 = db_session.query(Pillar).filter(Pillar.number == 1).first()
        p2 = db_session.query(Pillar).filter(Pillar.number == 2).first()
        p1.current_balance = Decimal("100.00")
        db_session.commit()

        response = seeded_client.post(
            "/api/v2/pillars/transfer",
            json={
                "from_pillar_id": p1.id,
                "to_pillar_id": p2.id,
                "amount": "500.00"
            }
        )
        assert response.status_code == 400

    def test_allocation_suggestions(self, seeded_client, db_session):
        p2 = db_session.query(Pillar).filter(Pillar.number == 2).first()
        p2.current_balance = Decimal("0.00")
        p2.target_balance = Decimal("10000.00")
        db_session.commit()

        response = seeded_client.get(
            "/api/v2/pillars/allocation-suggestions",
            params={"surplus": "2000.00"}
        )
        assert response.status_code == 200
        suggestions = response.json()
        assert len(suggestions) > 0


# ==================== CATEGORIES API ====================

class TestCategoriesAPI:
    """Test categories API endpoints."""

    def test_list_categories(self, seeded_client):
        response = seeded_client.get("/api/v2/categories")
        assert response.status_code == 200
        categories = response.json()
        assert len(categories) > 0

    def test_list_categories_by_type(self, seeded_client):
        response = seeded_client.get("/api/v2/categories", params={"type": "fixed"})
        assert response.status_code == 200
        categories = response.json()
        assert all(c["type"] == "fixed" for c in categories)

    def test_create_category(self, seeded_client):
        response = seeded_client.post(
            "/api/v2/categories",
            json={
                "name": "Test Category",
                "type": "variable",
                "monthly_budget": "100.00",
                "keywords": ["TEST", "PROVA"]
            }
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Test Category"

    def test_update_category(self, seeded_client, db_session):
        cat = db_session.query(Category).first()
        response = seeded_client.put(
            f"/api/v2/categories/{cat.id}",
            json={"monthly_budget": "500.00"}
        )
        assert response.status_code == 200
        assert Decimal(response.json()["monthly_budget"]) == Decimal("500.00")

    def test_delete_category(self, seeded_client, db_session):
        cat = db_session.query(Category).first()
        response = seeded_client.delete(f"/api/v2/categories/{cat.id}")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        # Verify soft delete
        db_session.refresh(cat)
        assert cat.is_active == False


# ==================== TRANSACTIONS API ====================

class TestTransactionsAPI:
    """Test transactions API endpoints."""

    def test_create_transaction(self, seeded_client, db_session):
        cat = db_session.query(Category).first()
        response = seeded_client.post(
            "/api/v2/transactions",
            json={
                "date": "2026-01-15",
                "amount": "-45.50",
                "description": "Test transaction",
                "category_id": cat.id
            }
        )
        assert response.status_code == 200
        assert response.json()["description"] == "Test transaction"

    def test_list_transactions(self, seeded_client, db_session):
        # Create a transaction first
        tx = Transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-50.00"),
            description="Test",
            source=TransactionSource.MANUAL
        )
        db_session.add(tx)
        db_session.commit()

        response = seeded_client.get("/api/v2/transactions")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_list_transactions_filtered(self, seeded_client, db_session):
        tx = Transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-50.00"),
            description="Test",
            source=TransactionSource.MANUAL
        )
        db_session.add(tx)
        db_session.commit()

        response = seeded_client.get(
            "/api/v2/transactions",
            params={"year": 2026, "month": 1}
        )
        assert response.status_code == 200

    def test_update_transaction(self, seeded_client, db_session):
        tx = Transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-50.00"),
            description="Original",
            source=TransactionSource.MANUAL
        )
        db_session.add(tx)
        db_session.commit()

        response = seeded_client.put(
            f"/api/v2/transactions/{tx.id}",
            json={"description": "Updated"}
        )
        assert response.status_code == 200
        assert response.json()["description"] == "Updated"

    def test_delete_transaction(self, seeded_client, db_session):
        tx = Transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-50.00"),
            description="To delete",
            source=TransactionSource.MANUAL
        )
        db_session.add(tx)
        db_session.commit()
        tx_id = tx.id

        response = seeded_client.delete(f"/api/v2/transactions/{tx_id}")
        assert response.status_code == 200


# ==================== FORECAST API ====================

class TestForecastAPI:
    """Test forecast API endpoints."""

    def test_generate_forecast(self, seeded_client):
        response = seeded_client.post(
            "/api/v2/forecast/generate",
            json={
                "year": 2026,
                "base_income": "3500.00",
                "opening_balance": "5000.00"
            }
        )
        assert response.status_code == 200
        forecasts = response.json()
        assert len(forecasts) == 12

    def test_get_yearly_forecast(self, seeded_client):
        # Generate first
        seeded_client.post(
            "/api/v2/forecast/generate",
            json={
                "year": 2026,
                "base_income": "3500.00",
                "opening_balance": "5000.00"
            }
        )

        response = seeded_client.get("/api/v2/forecast/2026")
        assert response.status_code == 200
        assert len(response.json()) == 12

    def test_get_month_forecast(self, seeded_client):
        # Generate first
        seeded_client.post(
            "/api/v2/forecast/generate",
            json={
                "year": 2026,
                "base_income": "3500.00",
                "opening_balance": "5000.00"
            }
        )

        response = seeded_client.get("/api/v2/forecast/2026/1")
        assert response.status_code == 200
        assert response.json()["month"] == 1

    def test_get_balance_projection(self, seeded_client):
        # Generate forecast first
        seeded_client.post(
            "/api/v2/forecast/generate",
            json={
                "year": 2026,
                "base_income": "3500.00",
                "opening_balance": "5000.00"
            }
        )

        response = seeded_client.get(
            "/api/v2/forecast/projection",
            params={"months": 6}
        )
        assert response.status_code == 200
        assert len(response.json()) == 6


# ==================== TAXES API ====================

class TestTaxesAPI:
    """Test taxes API endpoints."""

    def test_get_tax_settings(self, seeded_client):
        response = seeded_client.get("/api/v2/taxes/settings/2026")
        assert response.status_code == 200
        settings = response.json()
        assert settings["year"] == 2026
        assert settings["regime"] == "forfettario"

    def test_update_tax_settings(self, seeded_client):
        response = seeded_client.put(
            "/api/v2/taxes/settings/2026",
            json={"tax_rate": "0.05"}
        )
        assert response.status_code == 200
        assert Decimal(response.json()["tax_rate"]) == Decimal("0.05")

    def test_calculate_taxes(self, seeded_client):
        response = seeded_client.get(
            "/api/v2/taxes/calculate",
            params={"gross_income": "42000.00", "year": 2026}
        )
        assert response.status_code == 200
        breakdown = response.json()
        assert "taxable_income" in breakdown
        assert "total_tax" in breakdown

    def test_generate_tax_deadlines(self, seeded_client, db_session):
        # Set prior year payments
        settings = db_session.query(TaxSettings).filter(TaxSettings.year == 2026).first()
        settings.prior_year_tax_paid = Decimal("5000.00")
        settings.prior_year_inps_paid = Decimal("8000.00")
        db_session.commit()

        response = seeded_client.post(
            "/api/v2/taxes/deadlines/generate",
            params={"year": 2026, "estimated_income": "42000.00"}
        )
        assert response.status_code == 200
        deadlines = response.json()
        assert len(deadlines) >= 2

    def test_get_tax_deadlines(self, seeded_client, db_session):
        from app.models_v2 import DeadlineType
        # Create a deadline
        deadline = TaxDeadline(
            year=2026,
            deadline_type=DeadlineType.SALDO,
            name="Saldo 2025",
            due_date=date(2026, 6, 30),
            amount_due=Decimal("5000.00")
        )
        db_session.add(deadline)
        db_session.commit()

        response = seeded_client.get("/api/v2/taxes/deadlines/2026")
        assert response.status_code == 200

    def test_pay_tax_deadline(self, seeded_client, db_session):
        from app.models_v2 import DeadlineType
        deadline = TaxDeadline(
            year=2026,
            deadline_type=DeadlineType.SALDO,
            name="Saldo 2025",
            due_date=date(2026, 6, 30),
            amount_due=Decimal("5000.00")
        )
        db_session.add(deadline)
        db_session.commit()

        response = seeded_client.put(
            f"/api/v2/taxes/deadlines/{deadline.id}/pay",
            json={"amount": "1000.00"}
        )
        assert response.status_code == 200
        assert Decimal(response.json()["amount_paid"]) == Decimal("1000.00")


# ==================== BANK IMPORT API ====================

class TestBankImportAPI:
    """Test bank import API endpoints."""

    def test_import_bank_csv(self, seeded_client):
        csv_content = """Data;Descrizione;Importo
15/01/2026;ESSELUNGA MILANO;-45,20
18/01/2026;BONIFICO DA UFFICIO FURORE SRL;3500,00
"""
        response = seeded_client.post(
            "/api/v2/bank/import",
            json={
                "content": csv_content,
                "year": 2026,
                "month": 1
            }
        )
        assert response.status_code == 200
        result = response.json()
        assert result["imported"] == 2
        assert result["total_rows"] == 2

    def test_get_uncategorized(self, seeded_client, db_session):
        # Create uncategorized transaction
        tx = Transaction(
            date=date(2026, 1, 15),
            amount=Decimal("-50.00"),
            description="Unknown transaction",
            source=TransactionSource.BANK_IMPORT
        )
        db_session.add(tx)
        db_session.commit()

        response = seeded_client.get("/api/v2/bank/uncategorized")
        assert response.status_code == 200
        assert response.json()["count"] >= 1


# ==================== PLANNED EXPENSES API ====================

class TestPlannedExpensesAPI:
    """Test planned expenses API endpoints."""

    def test_create_planned_expense(self, seeded_client):
        response = seeded_client.post(
            "/api/v2/expenses/planned",
            json={
                "name": "Vacanza estiva",
                "target_date": "2026-08-01",
                "target_amount": "2000.00"
            }
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Vacanza estiva"

    def test_list_planned_expenses(self, seeded_client, db_session):
        expense = PlannedExpense(
            name="Test expense",
            target_date=date(2026, 6, 1),
            target_amount=Decimal("1000.00")
        )
        db_session.add(expense)
        db_session.commit()

        response = seeded_client.get("/api/v2/expenses/planned")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_update_planned_expense(self, seeded_client, db_session):
        expense = PlannedExpense(
            name="Test expense",
            target_date=date(2026, 6, 1),
            target_amount=Decimal("1000.00")
        )
        db_session.add(expense)
        db_session.commit()

        response = seeded_client.put(
            f"/api/v2/expenses/planned/{expense.id}",
            json={"current_amount": "500.00"}
        )
        assert response.status_code == 200
        assert Decimal(response.json()["current_amount"]) == Decimal("500.00")

    def test_delete_planned_expense(self, seeded_client, db_session):
        expense = PlannedExpense(
            name="To delete",
            target_date=date(2026, 6, 1),
            target_amount=Decimal("1000.00")
        )
        db_session.add(expense)
        db_session.commit()
        exp_id = expense.id

        response = seeded_client.delete(f"/api/v2/expenses/planned/{exp_id}")
        assert response.status_code == 200


# ==================== USER SETTINGS API ====================

class TestUserSettingsAPI:
    """Test user settings API endpoints."""

    def test_get_settings(self, seeded_client):
        response = seeded_client.get("/api/v2/settings")
        assert response.status_code == 200

    def test_update_settings(self, seeded_client):
        response = seeded_client.put(
            "/api/v2/settings",
            json={
                "monthly_income": "4000.00",
                "average_monthly_expenses": "3000.00"
            }
        )
        assert response.status_code == 200
        assert Decimal(response.json()["monthly_income"]) == Decimal("4000.00")
