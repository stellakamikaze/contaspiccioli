"""SQLAlchemy models for Contaspiccioli."""
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Category(Base):
    """Expense/income category."""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False)  # 'fissa' | 'variabile' | 'entrata'
    monthly_budget = Column(Float, default=0.0)
    icon = Column(String(10), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    transactions = relationship("Transaction", back_populates="category")


class Transaction(Base):
    """Financial transaction."""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(String(255), default="")
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    pillar = Column(String(20), default="corrente")  # 'corrente' | 'emergenza' | 'tasse' | 'investimenti'
    is_income = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    category = relationship("Category", back_populates="transactions")


class Pillar(Base):
    """Financial pillar (savings bucket)."""
    __tablename__ = "pillars"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)  # 'emergenza' | 'tasse' | 'investimenti'
    display_name = Column(String(100), nullable=False)
    target_balance = Column(Float, default=0.0)
    actual_balance = Column(Float, default=0.0)
    monthly_contribution = Column(Float, default=0.0)
    percentage = Column(Float, default=0.0)
    last_reconciled = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TaxDeadline(Base):
    """Tax payment deadline."""
    __tablename__ = "tax_deadlines"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    due_date = Column(Date, nullable=False)
    amount = Column(Float, nullable=False)
    paid = Column(Float, default=0.0)
    notified_7d = Column(Boolean, default=False)
    notified_1d = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    @property
    def residuo(self) -> float:
        return self.amount - self.paid

    @property
    def is_paid(self) -> bool:
        return self.paid >= self.amount


class MonthlyForecast(Base):
    """Monthly budget forecast and actuals."""
    __tablename__ = "monthly_forecasts"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    expected_income = Column(Float, default=0.0)
    expected_fixed = Column(Float, default=0.0)
    expected_variable = Column(Float, default=0.0)
    actual_income = Column(Float, default=0.0)
    actual_fixed = Column(Float, default=0.0)
    actual_variable = Column(Float, default=0.0)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Settings(Base):
    """Application settings stored in DB."""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), nullable=False, unique=True)
    value = Column(String(255), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserProfile(Base):
    """User profile with budget configuration from onboarding."""
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)

    # Step 1: Introiti
    monthly_income = Column(Float, default=0.0)
    income_type = Column(String(20), default="piva_forfettario")  # 'piva_forfettario' | 'piva_ordinario' | 'stipendio'
    income_is_fixed = Column(Boolean, default=True)

    # Step 2: Spese Fisse
    rent = Column(Float, default=0.0)
    subscriptions = Column(Float, default=0.0)  # palestra, streaming, etc
    other_fixed = Column(Float, default=0.0)  # commercialista, assicurazioni

    # Step 3: Spese Variabili
    food_budget = Column(Float, default=200.0)
    restaurants_budget = Column(Float, default=290.0)
    transport_budget = Column(Float, default=40.0)
    shopping_budget = Column(Float, default=230.0)

    # Step 4: Obiettivi Pilastri
    emergency_target = Column(Float, default=10000.0)
    tax_percentage = Column(Float, default=0.3143)  # auto-calcolato per P.IVA
    investment_percentage = Column(Float, default=0.10)

    # Step 5: Situazione Attuale (4 Pilastri)
    current_balance = Column(Float, default=0.0)      # 1° Pilastro - Conto corrente
    emergency_balance = Column(Float, default=0.0)    # 2° Pilastro - Fondo emergenza
    tax_balance = Column(Float, default=0.0)          # 3° Pilastro - Conto tasse
    investment_balance = Column(Float, default=0.0)   # 4° Pilastro - Investimenti
    taxes_paid_ytd = Column(Float, default=0.0)

    # P.IVA settings
    inps_rate = Column(Float, default=0.2598)
    coefficient = Column(Float, default=0.78)
    tax_rate = Column(Float, default=0.05)

    # Status
    setup_completed = Column(Boolean, default=False)
    setup_step = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def total_fixed_expenses(self) -> float:
        return self.rent + self.subscriptions + self.other_fixed

    @property
    def total_variable_budget(self) -> float:
        return self.food_budget + self.restaurants_budget + self.transport_budget + self.shopping_budget


class MonthlyIncome(Base):
    """Monthly income entries."""
    __tablename__ = "monthly_incomes"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    source = Column(String(100), nullable=False)  # e.g., "Ufficio Furore", "Cliente X"
    amount = Column(Float, nullable=False)
    is_received = Column(Boolean, default=False)  # True = ricevuto, False = previsto
    received_date = Column(Date, nullable=True)
    notes = Column(String(255), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
