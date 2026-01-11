"""Pydantic schemas for Contaspiccioli v2.0 API."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

from app.models_v2 import (
    CategoryType, LineType, TransactionSource, TaxRegime,
    AdvanceMethod, DeadlineType, AccountType
)


# ==================== ACCOUNTS ====================

class AccountBase(BaseModel):
    name: str
    account_type: AccountType
    notes: str = ""


class AccountCreate(AccountBase):
    pass


class AccountResponse(AccountBase):
    id: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


# ==================== PILLARS ====================

class PillarBase(BaseModel):
    display_name: str
    target_months: Optional[int] = None
    instrument: str = ""
    account_name: str = ""


class PillarUpdate(BaseModel):
    current_balance: Optional[Decimal] = None
    target_balance: Optional[Decimal] = None
    target_months: Optional[int] = None
    instrument: Optional[str] = None
    account_name: Optional[str] = None


class PillarResponse(BaseModel):
    id: int
    number: int
    name: str
    display_name: str
    description: str
    current_balance: Decimal
    target_balance: Decimal
    completion_percentage: float
    is_funded: bool
    target_months: Optional[int]
    instrument: str
    account_name: str
    priority: int
    model_config = ConfigDict(from_attributes=True)


class PillarStatusResponse(BaseModel):
    id: int
    number: int
    name: str
    display_name: str
    current_balance: Decimal
    target_balance: Decimal
    completion_percentage: float
    is_funded: bool
    instrument: str
    account_name: str
    priority: int
    shortfall: Decimal
    surplus: Decimal


class TransferRequest(BaseModel):
    from_pillar_id: int
    to_pillar_id: int
    amount: Decimal = Field(gt=0)
    notes: str = ""


class AllocationSuggestionResponse(BaseModel):
    pillar_id: int
    pillar_name: str
    amount: Decimal
    reason: str
    priority: int


class PillarSummaryResponse(BaseModel):
    pillars: list[PillarStatusResponse]
    total_balance: Decimal
    total_target: Decimal
    overall_completion: float
    all_funded: bool


# ==================== CATEGORIES ====================

class CategoryBase(BaseModel):
    name: str
    type: CategoryType
    icon: str = ""
    color: str = "#6B7280"
    monthly_budget: Decimal = Decimal("0.00")
    keywords: list[str] = []


class CategoryCreate(CategoryBase):
    pillar_id: Optional[int] = None
    display_order: int = 99


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[CategoryType] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    monthly_budget: Optional[Decimal] = None
    keywords: Optional[list[str]] = None
    pillar_id: Optional[int] = None
    display_order: Optional[int] = None


class CategoryResponse(CategoryBase):
    id: int
    pillar_id: Optional[int]
    display_order: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


# ==================== TRANSACTIONS ====================

class TransactionBase(BaseModel):
    date: date
    amount: Decimal
    description: str = ""
    category_id: Optional[int] = None
    is_income: bool = False
    is_taxable: bool = False


class TransactionCreate(TransactionBase):
    source: TransactionSource = TransactionSource.MANUAL


class TransactionUpdate(BaseModel):
    date: Optional[date] = None
    amount: Optional[Decimal] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    is_income: Optional[bool] = None
    is_taxable: Optional[bool] = None


class TransactionResponse(BaseModel):
    id: int
    date: date
    amount: Decimal
    description: str
    category_id: Optional[int]
    is_income: bool
    is_taxable: bool
    original_description: Optional[str]
    source: TransactionSource
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TransactionCategorizeRequest(BaseModel):
    transaction_id: int
    category_id: int


# ==================== FORECAST ====================

class ForecastLineBase(BaseModel):
    name: str
    line_type: LineType
    category_id: Optional[int] = None
    planned_amount: Decimal = Decimal("0.00")


class ForecastLineResponse(ForecastLineBase):
    id: int
    actual_amount: Decimal
    variance: Decimal
    is_locked: bool
    model_config = ConfigDict(from_attributes=True)


class ForecastMonthResponse(BaseModel):
    id: int
    year: int
    month: int
    month_name: str
    opening_balance: Decimal
    expected_income: Decimal
    actual_income: Decimal
    expected_fixed_costs: Decimal
    actual_fixed_costs: Decimal
    expected_variable_costs: Decimal
    actual_variable_costs: Decimal
    expected_balance: Decimal
    actual_balance: Decimal
    is_closed: bool
    model_config = ConfigDict(from_attributes=True)


class ForecastGenerateRequest(BaseModel):
    year: int
    base_income: Decimal
    opening_balance: Decimal


class ForecastComparisonResponse(BaseModel):
    month: int
    year: int
    planned_income: Decimal
    actual_income: Decimal
    planned_expenses: Decimal
    actual_expenses: Decimal
    variance_income: Decimal
    variance_expenses: Decimal
    status: str  # "on_track", "over_budget", "under_budget"


class BalanceProjectionResponse(BaseModel):
    month: int
    year: int
    month_name: str
    opening: Decimal
    income: Decimal
    expenses: Decimal
    closing: Decimal


# ==================== TAXES ====================

class TaxSettingsBase(BaseModel):
    regime: TaxRegime
    coefficient: Decimal
    inps_rate: Decimal
    tax_rate: Decimal
    advance_method: AdvanceMethod
    prior_year_tax_paid: Decimal = Decimal("0.00")
    prior_year_inps_paid: Decimal = Decimal("0.00")


class TaxSettingsCreate(TaxSettingsBase):
    year: int


class TaxSettingsUpdate(BaseModel):
    regime: Optional[TaxRegime] = None
    coefficient: Optional[Decimal] = None
    inps_rate: Optional[Decimal] = None
    tax_rate: Optional[Decimal] = None
    advance_method: Optional[AdvanceMethod] = None
    prior_year_tax_paid: Optional[Decimal] = None
    prior_year_inps_paid: Optional[Decimal] = None


class TaxSettingsResponse(TaxSettingsBase):
    id: int
    year: int
    min_threshold: Decimal
    single_payment_threshold: Decimal
    model_config = ConfigDict(from_attributes=True)


class TaxBreakdownResponse(BaseModel):
    gross_income: Decimal
    taxable_income: Decimal
    inps: Decimal
    irpef: Decimal
    total_tax: Decimal
    effective_rate: Decimal
    net_income: Decimal
    monthly_provision: Decimal


class TaxDeadlineResponse(BaseModel):
    id: int
    year: int
    deadline_type: DeadlineType
    due_date: date
    amount_due: Decimal
    amount_paid: Decimal
    remaining: Decimal
    is_paid: bool
    name: str
    days_remaining: int
    pillar_id: Optional[int]
    model_config = ConfigDict(from_attributes=True)


class TaxPaymentRequest(BaseModel):
    amount: Decimal = Field(gt=0)


class TaxCoverageResponse(BaseModel):
    total_due: Decimal
    total_reserved: Decimal
    coverage_percentage: float
    monthly_reserve_needed: Decimal
    is_covered: bool
    deadlines: list[TaxDeadlineResponse]


# ==================== BANK IMPORT ====================

class BankImportRequest(BaseModel):
    content: str
    year: int
    month: int
    bank_format: str = "generic"


class BankImportResponse(BaseModel):
    total_rows: int
    imported: int
    skipped: int
    errors: list[str]
    uncategorized_count: int
    transactions: list[TransactionResponse]


class UncategorizedTransactionsResponse(BaseModel):
    transactions: list[TransactionResponse]
    count: int


# ==================== PLANNED EXPENSES ====================

class PlannedExpenseBase(BaseModel):
    name: str
    target_date: date
    target_amount: Decimal
    notes: str = ""


class PlannedExpenseCreate(PlannedExpenseBase):
    pillar_id: Optional[int] = None


class PlannedExpenseUpdate(BaseModel):
    name: Optional[str] = None
    target_date: Optional[date] = None
    target_amount: Optional[Decimal] = None
    current_amount: Optional[Decimal] = None
    notes: Optional[str] = None


class PlannedExpenseResponse(BaseModel):
    id: int
    name: str
    target_date: date
    target_amount: Decimal
    current_amount: Decimal
    notes: str
    pillar_id: Optional[int]
    is_completed: bool
    model_config = ConfigDict(from_attributes=True)


# ==================== USER SETTINGS ====================

class UserSettingsBase(BaseModel):
    monthly_income: Decimal = Decimal("0.00")
    average_monthly_expenses: Decimal = Decimal("3500.00")


class UserSettingsUpdate(UserSettingsBase):
    pass


class UserSettingsResponse(BaseModel):
    id: int
    monthly_income: Decimal
    average_monthly_expenses: Decimal
    setup_completed: bool
    setup_step: int
    model_config = ConfigDict(from_attributes=True)
