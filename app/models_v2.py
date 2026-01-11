"""SQLAlchemy models for Contaspiccioli v2.0 - Cash Flow Planner."""
import enum
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Integer, String, Boolean, DateTime, Date,
    ForeignKey, Text, Numeric, Enum as SQLEnum, JSON
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base_v2 as Base


def utcnow() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


# Enums

class TaxRegime(str, enum.Enum):
    FORFETTARIO = "forfettario"
    ORDINARIO = "ordinario"
    DIPENDENTE = "dipendente"


class AdvanceMethod(str, enum.Enum):
    """Metodo calcolo acconti: storico (anno precedente) o previsionale (stima anno corrente)."""
    STORICO = "storico"
    PREVISIONALE = "previsionale"


class CategoryType(str, enum.Enum):
    INCOME = "income"
    FIXED = "fixed"
    VARIABLE = "variable"


class LineType(str, enum.Enum):
    INCOME = "income"
    FIXED_COST = "fixed_cost"
    VARIABLE_COST = "variable_cost"


class TransactionSource(str, enum.Enum):
    BANK_IMPORT = "bank_import"
    MANUAL = "manual"


class DeadlineType(str, enum.Enum):
    SALDO = "saldo"
    ACCONTO_1 = "acconto_1"
    ACCONTO_2 = "acconto_2"


class AccountType(str, enum.Enum):
    CHECKING = "checking"
    BROKER = "broker"
    TAX_ONLY = "tax_only"


# Models

class Account(Base):
    """Conto bancario (BBVA, Fineco, Fideuram)."""
    __tablename__ = "accounts_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(SQLEnum(AccountType), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    notes: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Pillar(Base):
    """I 4 pilastri di allocazione patrimonio (Coletti/Magri)."""
    __tablename__ = "pillars_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")

    current_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    target_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    target_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    instrument: Mapped[str] = mapped_column(String(100), default="")
    account_name: Mapped[str] = mapped_column(String(100), default="")

    is_funded: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    categories: Mapped[list["Category"]] = relationship("Category", back_populates="pillar")
    tax_deadlines: Mapped[list["TaxDeadline"]] = relationship("TaxDeadline", back_populates="pillar")
    planned_expenses: Mapped[list["PlannedExpense"]] = relationship("PlannedExpense", back_populates="pillar")

    @property
    def completion_percentage(self) -> float:
        if self.target_balance == 0:
            return 100.0 if self.current_balance >= 0 else 0.0
        return min(100.0, float(self.current_balance / self.target_balance * 100))


class Category(Base):
    """Categoria spese/entrate con keywords per auto-categorizzazione."""
    __tablename__ = "categories_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[CategoryType] = mapped_column(SQLEnum(CategoryType), nullable=False)
    icon: Mapped[str] = mapped_column(String(10), default="")
    color: Mapped[str] = mapped_column(String(7), default="#6B7280")
    monthly_budget: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    keywords: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    pillar_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pillars_v2.id"), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    pillar: Mapped[Optional["Pillar"]] = relationship("Pillar", back_populates="categories")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="category")
    forecast_lines: Mapped[list["ForecastLine"]] = relationship("ForecastLine", back_populates="category")


class ForecastMonth(Base):
    """Previsionale mensile (replica struttura Excel Federico)."""
    __tablename__ = "forecast_months_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)

    opening_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    expected_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    actual_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    expected_fixed_costs: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    actual_fixed_costs: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    expected_variable_costs: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    actual_variable_costs: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))

    notes: Mapped[str] = mapped_column(Text, default="")
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    lines: Mapped[list["ForecastLine"]] = relationship("ForecastLine", back_populates="forecast_month")

    @property
    def expected_total_costs(self) -> Decimal:
        return self.expected_fixed_costs + self.expected_variable_costs

    @property
    def actual_total_costs(self) -> Decimal:
        return self.actual_fixed_costs + self.actual_variable_costs

    @property
    def expected_balance(self) -> Decimal:
        return self.opening_balance + self.expected_income - self.expected_total_costs

    @property
    def actual_balance(self) -> Decimal:
        return self.opening_balance + self.actual_income - self.actual_total_costs

    @property
    def variance(self) -> Decimal:
        return self.actual_balance - self.expected_balance


class ForecastLine(Base):
    """Singola riga nel previsionale mensile."""
    __tablename__ = "forecast_lines_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    forecast_month_id: Mapped[int] = mapped_column(ForeignKey("forecast_months_v2.id"), nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories_v2.id"), nullable=True)
    line_type: Mapped[LineType] = mapped_column(SQLEnum(LineType), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    expected_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    forecast_month: Mapped["ForecastMonth"] = relationship("ForecastMonth", back_populates="lines")
    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="forecast_lines")

    @property
    def variance(self) -> Decimal:
        return self.actual_amount - self.expected_amount


class Transaction(Base):
    """Transazione finanziaria (da import banca o manuale)."""
    __tablename__ = "transactions_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="")
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories_v2.id"), nullable=True)
    forecast_line_id: Mapped[Optional[int]] = mapped_column(ForeignKey("forecast_lines_v2.id"), nullable=True)

    source: Mapped[TransactionSource] = mapped_column(
        SQLEnum(TransactionSource), default=TransactionSource.MANUAL
    )
    original_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    is_income: Mapped[bool] = mapped_column(Boolean, default=False)
    is_taxable: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="transactions")


class TaxSettings(Base):
    """Configurazione fiscale P.IVA (per anno)."""
    __tablename__ = "tax_settings_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    regime: Mapped[TaxRegime] = mapped_column(SQLEnum(TaxRegime), default=TaxRegime.FORFETTARIO)

    coefficient: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0.78"))
    inps_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.2607"))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0.15"))

    advance_method: Mapped[AdvanceMethod] = mapped_column(
        SQLEnum(AdvanceMethod), default=AdvanceMethod.STORICO
    )
    min_threshold: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("52.00"))
    single_payment_threshold: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("258.00"))

    prior_year_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    prior_year_tax_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    prior_year_inps_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))

    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    def calculate_tax(self, gross_income: Decimal) -> dict:
        """Calcola tasse per il reddito lordo dato. IRPEF si calcola su imponibile meno INPS."""
        taxable_income = gross_income * self.coefficient
        inps = taxable_income * self.inps_rate
        irpef = (taxable_income - inps) * self.tax_rate
        return {
            "gross_income": gross_income,
            "taxable_income": taxable_income,
            "inps": inps,
            "irpef": irpef,
            "total": inps + irpef,
        }


class TaxDeadline(Base):
    """Scadenza fiscale (calcolata o manuale)."""
    __tablename__ = "tax_deadlines_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    deadline_type: Mapped[DeadlineType] = mapped_column(SQLEnum(DeadlineType), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)

    amount_due: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    installments_paid: Mapped[int] = mapped_column(Integer, default=0)

    is_calculated: Mapped[bool] = mapped_column(Boolean, default=True)
    is_manual_override: Mapped[bool] = mapped_column(Boolean, default=False)
    pillar_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pillars_v2.id"), nullable=True)

    notes: Mapped[str] = mapped_column(Text, default="")
    notified_7d: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_1d: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    pillar: Mapped[Optional["Pillar"]] = relationship("Pillar", back_populates="tax_deadlines")

    @property
    def remaining(self) -> Decimal:
        return self.amount_due - self.amount_paid

    @property
    def is_paid(self) -> bool:
        return self.amount_paid >= self.amount_due


class PlannedExpense(Base):
    """Spesa pianificata per P3 (oltre alle tasse)."""
    __tablename__ = "planned_expenses_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    current_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    monthly_contribution: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    pillar_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pillars_v2.id"), nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    pillar: Mapped[Optional["Pillar"]] = relationship("Pillar", back_populates="planned_expenses")

    @property
    def remaining(self) -> Decimal:
        return self.target_amount - self.current_amount

    @property
    def completion_percentage(self) -> float:
        if self.target_amount == 0:
            return 100.0
        return min(100.0, float(self.current_amount / self.target_amount * 100))

    def calculate_monthly_contribution(self, from_date: Optional[date] = None) -> Decimal:
        """Calcola il contributo mensile necessario per raggiungere il target."""
        from_date = from_date or date.today()
        months_remaining = (
            (self.target_date.year - from_date.year) * 12
            + (self.target_date.month - from_date.month)
        )
        if months_remaining <= 0:
            return self.remaining
        return self.remaining / Decimal(months_remaining)


class UserSettings(Base):
    """Impostazioni utente e profilo."""
    __tablename__ = "user_settings_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    monthly_income: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    income_type: Mapped[TaxRegime] = mapped_column(SQLEnum(TaxRegime), default=TaxRegime.FORFETTARIO)
    average_monthly_expenses: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("3500.00"))
    setup_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    setup_step: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
