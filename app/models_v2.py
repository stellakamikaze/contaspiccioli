"""SQLAlchemy models for Contaspiccioli v2.0 - Cash Flow Planner."""
import enum
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date,
    ForeignKey, Text, Numeric, Enum as SQLEnum, JSON
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base


# ==================== ENUMS ====================

class TaxRegime(str, enum.Enum):
    """Tax regime types."""
    FORFETTARIO = "forfettario"
    ORDINARIO = "ordinario"
    DIPENDENTE = "dipendente"


class AdvanceMethod(str, enum.Enum):
    """Tax advance calculation method."""
    STORICO = "storico"      # Based on previous year
    PREVISIONALE = "previsionale"  # Based on current year estimate


class CategoryType(str, enum.Enum):
    """Category types."""
    INCOME = "income"
    FIXED = "fixed"
    VARIABLE = "variable"


class LineType(str, enum.Enum):
    """Forecast line types."""
    INCOME = "income"
    FIXED_COST = "fixed_cost"
    VARIABLE_COST = "variable_cost"


class TransactionSource(str, enum.Enum):
    """Transaction source types."""
    BANK_IMPORT = "bank_import"
    MANUAL = "manual"


class DeadlineType(str, enum.Enum):
    """Tax deadline types."""
    SALDO = "saldo"
    ACCONTO_1 = "acconto_1"
    ACCONTO_2 = "acconto_2"


class AccountType(str, enum.Enum):
    """Bank account types."""
    CHECKING = "checking"  # C/C principale
    BROKER = "broker"      # Broker/conto titoli
    TAX_ONLY = "tax_only"  # Solo per F24


# ==================== MODELS ====================

class Account(Base):
    """Bank account - simplified for Federico's structure."""
    __tablename__ = "accounts_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # "BBVA", "Fineco", "Fideuram"
    account_type: Mapped[AccountType] = mapped_column(SQLEnum(AccountType), nullable=False)

    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    notes: Mapped[Optional[str]] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Pillar(Base):
    """I 4 pilastri di allocazione patrimonio (Coletti/Magri)."""
    __tablename__ = "pillars_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)  # 1, 2, 3, 4
    name: Mapped[str] = mapped_column(String(50), nullable=False)  # "liquidita", "emergenza", "spese_previste", "investimenti"
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)  # "Liquidità", "Emergenza", etc.
    description: Mapped[str] = mapped_column(Text, default="")

    # Balances
    current_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    target_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))

    # Configuration
    target_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # For P1/P2: months of expenses
    instrument: Mapped[str] = mapped_column(String(100), default="")  # "Conto corrente", "Conto deposito", "BTP", "ETF"
    account_name: Mapped[str] = mapped_column(String(100), default="")  # Associated account name

    # Status
    is_funded: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)  # Fill order

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    categories: Mapped[List["Category"]] = relationship("Category", back_populates="pillar")
    tax_deadlines: Mapped[List["TaxDeadline"]] = relationship("TaxDeadline", back_populates="pillar")
    planned_expenses: Mapped[List["PlannedExpense"]] = relationship("PlannedExpense", back_populates="pillar")

    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage."""
        if self.target_balance == 0:
            return 100.0 if self.current_balance >= 0 else 0.0
        return min(100.0, float(self.current_balance / self.target_balance * 100))


class Category(Base):
    """Expense/income category with auto-categorization keywords."""
    __tablename__ = "categories_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[CategoryType] = mapped_column(SQLEnum(CategoryType), nullable=False)
    icon: Mapped[str] = mapped_column(String(10), default="")
    color: Mapped[str] = mapped_column(String(7), default="#6B7280")  # Hex color

    # Budget
    monthly_budget: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))

    # Auto-categorization keywords (stored as JSON array)
    keywords: Mapped[Optional[str]] = mapped_column(JSON, default=list)  # ["ESSELUNGA", "CARREFOUR"]

    # Pillar association
    pillar_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pillars_v2.id"), nullable=True)

    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    pillar: Mapped[Optional["Pillar"]] = relationship("Pillar", back_populates="categories")
    transactions: Mapped[List["Transaction"]] = relationship("Transaction", back_populates="category")
    forecast_lines: Mapped[List["ForecastLine"]] = relationship("ForecastLine", back_populates="category")


class ForecastMonth(Base):
    """Monthly forecast (replica Excel structure)."""
    __tablename__ = "forecast_months_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)

    # Opening balance (inherited from previous month)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))

    # Income
    expected_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    actual_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))

    # Fixed costs
    expected_fixed_costs: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    actual_fixed_costs: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))

    # Variable costs
    expected_variable_costs: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    actual_variable_costs: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))

    notes: Mapped[Optional[str]] = mapped_column(Text, default="")
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)  # Month finalized
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lines: Mapped[List["ForecastLine"]] = relationship("ForecastLine", back_populates="forecast_month")

    @property
    def expected_total_costs(self) -> Decimal:
        return self.expected_fixed_costs + self.expected_variable_costs

    @property
    def actual_total_costs(self) -> Decimal:
        return self.actual_fixed_costs + self.actual_variable_costs

    @property
    def expected_balance(self) -> Decimal:
        """Expected end-of-month balance."""
        return self.opening_balance + self.expected_income - self.expected_total_costs

    @property
    def actual_balance(self) -> Decimal:
        """Actual end-of-month balance (if actuals are filled)."""
        return self.opening_balance + self.actual_income - self.actual_total_costs

    @property
    def variance(self) -> Decimal:
        """Difference between expected and actual."""
        return self.actual_balance - self.expected_balance


class ForecastLine(Base):
    """Single line in monthly forecast (income or expense)."""
    __tablename__ = "forecast_lines_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    forecast_month_id: Mapped[int] = mapped_column(ForeignKey("forecast_months_v2.id"), nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories_v2.id"), nullable=True)

    line_type: Mapped[LineType] = mapped_column(SQLEnum(LineType), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)

    expected_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))

    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Day of month

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    forecast_month: Mapped["ForecastMonth"] = relationship("ForecastMonth", back_populates="lines")
    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="forecast_lines")

    @property
    def variance(self) -> Decimal:
        return self.actual_amount - self.expected_amount


class Transaction(Base):
    """Financial transaction (from bank import or manual)."""
    __tablename__ = "transactions_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="")

    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories_v2.id"), nullable=True)
    forecast_line_id: Mapped[Optional[int]] = mapped_column(ForeignKey("forecast_lines_v2.id"), nullable=True)

    # Metadata
    source: Mapped[TransactionSource] = mapped_column(
        SQLEnum(TransactionSource),
        default=TransactionSource.MANUAL
    )
    original_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Raw from CSV
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)

    # For P.IVA
    is_income: Mapped[bool] = mapped_column(Boolean, default=False)
    is_taxable: Mapped[bool] = mapped_column(Boolean, default=False)  # If it's invoice income

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="transactions")


class TaxSettings(Base):
    """P.IVA tax configuration (per year)."""
    __tablename__ = "tax_settings_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    regime: Mapped[TaxRegime] = mapped_column(SQLEnum(TaxRegime), default=TaxRegime.FORFETTARIO)

    # Forfettario settings
    coefficient: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0.78"))  # 78%
    inps_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.2607"))  # 26.07%
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0.15"))  # 15% or 5%

    # Advance calculation
    advance_method: Mapped[AdvanceMethod] = mapped_column(
        SQLEnum(AdvanceMethod),
        default=AdvanceMethod.STORICO
    )
    # Thresholds
    min_threshold: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("52.00"))
    single_payment_threshold: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("258.00"))

    # Previous year data for advance calculation
    prior_year_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    prior_year_tax_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    prior_year_inps_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))

    notes: Mapped[Optional[str]] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def calculate_tax(self, gross_income: Decimal) -> dict:
        """Calculate taxes for given gross income."""
        taxable_income = gross_income * self.coefficient
        inps = taxable_income * self.inps_rate
        # IRPEF is calculated on income MINUS INPS contributions
        irpef_base = taxable_income - inps
        irpef = irpef_base * self.tax_rate
        return {
            "gross_income": gross_income,
            "taxable_income": taxable_income,
            "inps": inps,
            "irpef": irpef,
            "total": inps + irpef,
        }


class TaxDeadline(Base):
    """Tax payment deadline (calculated or manual)."""
    __tablename__ = "tax_deadlines_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    deadline_type: Mapped[DeadlineType] = mapped_column(SQLEnum(DeadlineType), nullable=False)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)

    amount_due: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    installments_paid: Mapped[int] = mapped_column(Integer, default=0)  # If split in installments

    is_calculated: Mapped[bool] = mapped_column(Boolean, default=True)
    is_manual_override: Mapped[bool] = mapped_column(Boolean, default=False)

    pillar_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pillars_v2.id"), nullable=True)  # Always P3

    notes: Mapped[Optional[str]] = mapped_column(Text, default="")
    notified_7d: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_1d: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    pillar: Mapped[Optional["Pillar"]] = relationship("Pillar", back_populates="tax_deadlines")

    @property
    def remaining(self) -> Decimal:
        return self.amount_due - self.amount_paid

    @property
    def is_paid(self) -> bool:
        return self.amount_paid >= self.amount_due


class PlannedExpense(Base):
    """Planned expense for P3 (beyond taxes)."""
    __tablename__ = "planned_expenses_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # "Dentista", "Bicicletta"

    target_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    current_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    target_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Auto-calculated monthly contribution
    monthly_contribution: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))

    pillar_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pillars_v2.id"), nullable=True)  # P3

    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    pillar: Mapped[Optional["Pillar"]] = relationship("Pillar", back_populates="planned_expenses")

    @property
    def remaining(self) -> Decimal:
        return self.target_amount - self.current_amount

    @property
    def completion_percentage(self) -> float:
        if self.target_amount == 0:
            return 100.0
        return min(100.0, float(self.current_amount / self.target_amount * 100))

    def calculate_monthly_contribution(self, from_date: date = None) -> Decimal:
        """Calculate required monthly contribution to reach target."""
        from_date = from_date or date.today()
        if from_date >= self.target_date:
            return self.remaining

        months_remaining = (
            (self.target_date.year - from_date.year) * 12
            + (self.target_date.month - from_date.month)
        )
        if months_remaining <= 0:
            return self.remaining

        return self.remaining / Decimal(months_remaining)


class UserSettings(Base):
    """User settings and profile (replaces UserProfile)."""
    __tablename__ = "user_settings_v2"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Basic info
    monthly_income: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    income_type: Mapped[TaxRegime] = mapped_column(SQLEnum(TaxRegime), default=TaxRegime.FORFETTARIO)

    # Monthly expense averages (for pillar target calculation)
    average_monthly_expenses: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("3500.00"))

    # Onboarding status
    setup_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    setup_step: Mapped[int] = mapped_column(Integer, default=1)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
