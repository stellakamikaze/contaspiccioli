"""API endpoints for Contaspiccioli v2.0."""
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import extract

from app.database import get_db
from app.models_v2 import (
    Account, Pillar, Category, Transaction, TaxSettings, TaxDeadline,
    PlannedExpense, ForecastMonth, UserSettings, TransactionSource
)
from app.schemas_v2 import (
    # Accounts
    AccountCreate, AccountResponse,
    # Pillars
    PillarResponse, PillarUpdate, PillarStatusResponse, TransferRequest,
    AllocationSuggestionResponse, PillarSummaryResponse,
    # Categories
    CategoryCreate, CategoryUpdate, CategoryResponse,
    # Transactions
    TransactionCreate, TransactionUpdate, TransactionResponse,
    TransactionCategorizeRequest,
    # Forecast
    ForecastMonthResponse, ForecastGenerateRequest, ForecastComparisonResponse,
    BalanceProjectionResponse,
    # Taxes
    TaxSettingsCreate, TaxSettingsUpdate, TaxSettingsResponse,
    TaxBreakdownResponse, TaxDeadlineResponse, TaxPaymentRequest, TaxCoverageResponse,
    # Bank Import
    BankImportRequest, BankImportResponse, UncategorizedTransactionsResponse,
    # Planned Expenses
    PlannedExpenseCreate, PlannedExpenseUpdate, PlannedExpenseResponse,
    # User Settings
    UserSettingsUpdate, UserSettingsResponse,
)
from app.services.pillars_v2 import (
    get_pillar_status, get_pillar_summary, update_pillar_balance,
    record_transfer, suggest_allocation, calculate_target_balances,
    update_pillar_targets
)
from app.services.forecast_v2 import (
    generate_yearly_forecast, get_forecast_comparison,
    update_forecast_actuals, project_balance, get_month_name
)
from app.services.taxes_v2 import (
    get_or_create_tax_settings, calculate_annual_taxes,
    generate_tax_deadlines, calculate_monthly_reserve,
    get_tax_coverage, record_tax_payment
)
from app.services.bank_import_v2 import (
    import_bank_statement, categorize_transaction, learn_keyword,
    get_uncategorized_transactions, BankFormat
)


router = APIRouter(prefix="/api/v2", tags=["api-v2"])


# ==================== ACCOUNTS ====================

@router.get("/accounts", response_model=list[AccountResponse])
def list_accounts(db: Session = Depends(get_db)):
    """List all active accounts."""
    return db.query(Account).filter(Account.is_active == True).all()


@router.post("/accounts", response_model=AccountResponse)
def create_account(data: AccountCreate, db: Session = Depends(get_db)):
    """Create a new account."""
    account = Account(**data.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


# ==================== PILLARS ====================

@router.get("/pillars", response_model=list[PillarResponse])
def list_pillars(db: Session = Depends(get_db)):
    """List all pillars."""
    return db.query(Pillar).order_by(Pillar.number).all()


@router.get("/pillars/status", response_model=list[PillarStatusResponse])
def get_pillars_status(db: Session = Depends(get_db)):
    """Get status of all pillars with shortfall/surplus."""
    statuses = get_pillar_status(db)
    return [
        PillarStatusResponse(
            id=s.id,
            number=s.number,
            name=s.name,
            display_name=s.display_name,
            current_balance=s.current_balance,
            target_balance=s.target_balance,
            completion_percentage=s.completion_percentage,
            is_funded=s.is_funded,
            instrument=s.instrument,
            account_name=s.account_name,
            priority=s.priority,
            shortfall=s.shortfall,
            surplus=s.surplus,
        )
        for s in statuses
    ]


@router.get("/pillars/summary", response_model=PillarSummaryResponse)
def pillars_summary(db: Session = Depends(get_db)):
    """Get complete summary of all pillars."""
    summary = get_pillar_summary(db)
    return PillarSummaryResponse(
        pillars=[
            PillarStatusResponse(
                id=s.id,
                number=s.number,
                name=s.name,
                display_name=s.display_name,
                current_balance=s.current_balance,
                target_balance=s.target_balance,
                completion_percentage=s.completion_percentage,
                is_funded=s.is_funded,
                instrument=s.instrument,
                account_name=s.account_name,
                priority=s.priority,
                shortfall=s.shortfall,
                surplus=s.surplus,
            )
            for s in summary['pillars']
        ],
        total_balance=summary['total_balance'],
        total_target=summary['total_target'],
        overall_completion=summary['overall_completion'],
        all_funded=summary['all_funded'],
    )


@router.get("/pillars/allocation-suggestions", response_model=list[AllocationSuggestionResponse])
def get_allocation_suggestions(
    surplus: float = Query(..., description="Amount to allocate"),
    db: Session = Depends(get_db)
):
    """Get suggestions for allocating surplus funds."""
    suggestions = suggest_allocation(db, Decimal(str(surplus)))
    return [
        AllocationSuggestionResponse(
            pillar_id=s.pillar_id,
            pillar_name=s.pillar_name,
            amount=s.amount,
            reason=s.reason,
            priority=s.priority,
        )
        for s in suggestions
    ]


@router.get("/pillars/{pillar_id}", response_model=PillarResponse)
def get_pillar(pillar_id: int, db: Session = Depends(get_db)):
    """Get a specific pillar."""
    pillar = db.query(Pillar).filter(Pillar.id == pillar_id).first()
    if not pillar:
        raise HTTPException(status_code=404, detail="Pillar not found")
    return pillar


@router.put("/pillars/{pillar_id}", response_model=PillarResponse)
def update_pillar(pillar_id: int, data: PillarUpdate, db: Session = Depends(get_db)):
    """Update a pillar."""
    pillar = db.query(Pillar).filter(Pillar.id == pillar_id).first()
    if not pillar:
        raise HTTPException(status_code=404, detail="Pillar not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(pillar, key, value)

    # Recalculate is_funded
    pillar.is_funded = pillar.current_balance >= pillar.target_balance

    db.commit()
    db.refresh(pillar)
    return pillar


@router.put("/pillars/{pillar_id}/balance", response_model=PillarResponse)
def reconcile_pillar_balance(
    pillar_id: int,
    new_balance: float = Query(...),
    db: Session = Depends(get_db)
):
    """Update pillar balance (reconciliation)."""
    return update_pillar_balance(db, pillar_id, Decimal(str(new_balance)))


@router.post("/pillars/transfer", response_model=dict)
def transfer_between_pillars(data: TransferRequest, db: Session = Depends(get_db)):
    """Transfer funds between pillars."""
    try:
        from_p, to_p = record_transfer(
            db, data.from_pillar_id, data.to_pillar_id, data.amount, notes=data.notes
        )
        return {
            "status": "success",
            "from_pillar": {"id": from_p.id, "balance": from_p.current_balance},
            "to_pillar": {"id": to_p.id, "balance": to_p.current_balance},
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/pillars/update-targets", response_model=list[PillarResponse])
def recalculate_pillar_targets(
    average_monthly_expenses: float = Query(...),
    db: Session = Depends(get_db)
):
    """Recalculate target balances based on expenses."""
    return update_pillar_targets(db, Decimal(str(average_monthly_expenses)))


# ==================== CATEGORIES ====================

@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(
    type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all active categories."""
    query = db.query(Category).filter(Category.is_active == True)
    if type:
        query = query.filter(Category.type == type)
    return query.order_by(Category.display_order).all()


@router.post("/categories", response_model=CategoryResponse)
def create_category(data: CategoryCreate, db: Session = Depends(get_db)):
    """Create a new category."""
    category = Category(**data.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.get("/categories/{category_id}", response_model=CategoryResponse)
def get_category(category_id: int, db: Session = Depends(get_db)):
    """Get a specific category."""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.put("/categories/{category_id}", response_model=CategoryResponse)
def update_category(category_id: int, data: CategoryUpdate, db: Session = Depends(get_db)):
    """Update a category."""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(category, key, value)

    db.commit()
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    """Soft delete a category."""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    category.is_active = False
    db.commit()
    return {"status": "deleted", "id": category_id}


# ==================== TRANSACTIONS ====================

@router.get("/transactions", response_model=list[TransactionResponse])
def list_transactions(
    year: Optional[int] = None,
    month: Optional[int] = None,
    category_id: Optional[int] = None,
    is_income: Optional[bool] = None,
    uncategorized: bool = False,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List transactions with filters."""
    query = db.query(Transaction)

    if year:
        query = query.filter(extract('year', Transaction.date) == year)
    if month:
        query = query.filter(extract('month', Transaction.date) == month)
    if category_id:
        query = query.filter(Transaction.category_id == category_id)
    if is_income is not None:
        query = query.filter(Transaction.is_income == is_income)
    if uncategorized:
        query = query.filter(Transaction.category_id == None)

    return query.order_by(Transaction.date.desc()).offset(offset).limit(limit).all()


@router.post("/transactions", response_model=TransactionResponse)
def create_transaction(data: TransactionCreate, db: Session = Depends(get_db)):
    """Create a new transaction."""
    transaction = Transaction(**data.model_dump())
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    """Get a specific transaction."""
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.put("/transactions/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    data: TransactionUpdate,
    db: Session = Depends(get_db)
):
    """Update a transaction."""
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(transaction, key, value)

    db.commit()
    db.refresh(transaction)
    return transaction


@router.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    """Delete a transaction."""
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    db.delete(transaction)
    db.commit()
    return {"status": "deleted", "id": transaction_id}


@router.post("/transactions/{transaction_id}/categorize", response_model=CategoryResponse)
def categorize_transaction_endpoint(
    transaction_id: int,
    category_id: int = Query(...),
    learn: bool = Query(default=True, description="Learn keyword from this categorization"),
    db: Session = Depends(get_db)
):
    """Categorize a transaction and optionally learn the keyword."""
    if learn:
        try:
            return learn_keyword(db, transaction_id, category_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
    else:
        transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        transaction.category_id = category_id
        db.commit()
        return db.query(Category).filter(Category.id == category_id).first()


# ==================== FORECAST ====================

def _forecast_to_response(f: ForecastMonth) -> ForecastMonthResponse:
    """Helper to convert ForecastMonth model to response schema."""
    return ForecastMonthResponse(
        id=f.id,
        year=f.year,
        month=f.month,
        month_name=get_month_name(f.month),
        opening_balance=f.opening_balance,
        expected_income=f.expected_income,
        actual_income=f.actual_income,
        expected_fixed_costs=f.expected_fixed_costs,
        actual_fixed_costs=f.actual_fixed_costs,
        expected_variable_costs=f.expected_variable_costs,
        actual_variable_costs=f.actual_variable_costs,
        expected_balance=f.expected_balance,
        actual_balance=f.actual_balance,
        is_closed=f.is_closed,
    )


@router.get("/forecast/projection", response_model=list[BalanceProjectionResponse])
def get_balance_projection(
    months: int = Query(default=12, le=24),
    starting_balance: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """Project balance for next N months."""
    starting_bal = Decimal(str(starting_balance)) if starting_balance else None
    projections = project_balance(db, months, starting_bal)

    return [
        BalanceProjectionResponse(
            month=p['month'],
            year=p['year'],
            month_name=p['month_name'],
            opening=p['opening'],
            income=p['income'],
            expenses=p['costs'],
            closing=p['closing'],
        )
        for p in projections
    ]


@router.get("/forecast/{year}", response_model=list[ForecastMonthResponse])
def get_yearly_forecast(year: int, db: Session = Depends(get_db)):
    """Get forecast for entire year."""
    forecasts = db.query(ForecastMonth).filter(
        ForecastMonth.year == year
    ).order_by(ForecastMonth.month).all()

    return [_forecast_to_response(f) for f in forecasts]


@router.get("/forecast/{year}/{month}", response_model=ForecastMonthResponse)
def get_month_forecast(year: int, month: int, db: Session = Depends(get_db)):
    """Get forecast for a specific month."""
    forecast = db.query(ForecastMonth).filter(
        ForecastMonth.year == year,
        ForecastMonth.month == month
    ).first()

    if not forecast:
        raise HTTPException(status_code=404, detail=f"Forecast for {month}/{year} not found")

    return _forecast_to_response(forecast)


@router.post("/forecast/generate", response_model=list[ForecastMonthResponse])
def generate_forecast(data: ForecastGenerateRequest, db: Session = Depends(get_db)):
    """Generate 12-month forecast."""
    forecasts = generate_yearly_forecast(
        db, data.year, data.base_income, data.opening_balance
    )

    return [_forecast_to_response(f) for f in forecasts]


@router.get("/forecast/{year}/{month}/comparison", response_model=ForecastComparisonResponse)
def compare_forecast_vs_actual(year: int, month: int, db: Session = Depends(get_db)):
    """Compare planned vs actual for a month."""
    comparison = get_forecast_comparison(db, year, month)
    if not comparison:
        raise HTTPException(status_code=404, detail=f"No forecast data for {month}/{year}")

    return ForecastComparisonResponse(
        month=comparison.month,
        year=comparison.year,
        planned_income=comparison.planned_income,
        actual_income=comparison.actual_income,
        planned_expenses=comparison.planned_expenses,
        actual_expenses=comparison.actual_expenses,
        variance_income=comparison.variance_income,
        variance_expenses=comparison.variance_expenses,
        status=comparison.status,
    )


@router.post("/forecast/{year}/{month}/update-actuals", response_model=ForecastMonthResponse)
def sync_forecast_actuals(year: int, month: int, db: Session = Depends(get_db)):
    """Update forecast with actual transaction data."""
    forecast = update_forecast_actuals(db, year, month)

    return _forecast_to_response(forecast)


# ==================== TAXES ====================

@router.get("/taxes/settings/{year}", response_model=TaxSettingsResponse)
def get_tax_settings(year: int, db: Session = Depends(get_db)):
    """Get tax settings for a year."""
    return get_or_create_tax_settings(db, year)


@router.put("/taxes/settings/{year}", response_model=TaxSettingsResponse)
def update_tax_settings(
    year: int,
    data: TaxSettingsUpdate,
    db: Session = Depends(get_db)
):
    """Update tax settings."""
    settings = db.query(TaxSettings).filter(TaxSettings.year == year).first()
    if not settings:
        raise HTTPException(status_code=404, detail=f"Tax settings for {year} not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(settings, key, value)

    db.commit()
    db.refresh(settings)
    return settings


@router.get("/taxes/calculate", response_model=TaxBreakdownResponse)
def calculate_taxes(
    gross_income: float = Query(...),
    year: int = Query(default=None),
    db: Session = Depends(get_db)
):
    """Calculate tax obligations."""
    if not year:
        year = date.today().year

    settings = get_or_create_tax_settings(db, year)
    breakdown = calculate_annual_taxes(Decimal(str(gross_income)), settings)

    return TaxBreakdownResponse(
        gross_income=breakdown.gross_income,
        taxable_income=breakdown.taxable_income,
        inps=breakdown.inps,
        irpef=breakdown.irpef,
        total_tax=breakdown.total_tax,
        effective_rate=breakdown.effective_rate,
        net_income=breakdown.net_income,
        monthly_provision=breakdown.monthly_provision,
    )


@router.get("/taxes/deadlines/{year}", response_model=list[TaxDeadlineResponse])
def get_tax_deadlines(year: int, db: Session = Depends(get_db)):
    """Get tax deadlines for a year."""
    deadlines = db.query(TaxDeadline).filter(
        TaxDeadline.year == year
    ).order_by(TaxDeadline.due_date).all()

    today = date.today()
    return [
        TaxDeadlineResponse(
            id=d.id,
            year=d.year,
            deadline_type=d.deadline_type,
            due_date=d.due_date,
            amount_due=d.amount_due,
            amount_paid=d.amount_paid,
            remaining=d.remaining,
            is_paid=d.is_paid,
            name=d.name,
            days_remaining=(d.due_date - today).days,
            pillar_id=d.pillar_id,
        )
        for d in deadlines
    ]


@router.post("/taxes/deadlines/generate", response_model=list[TaxDeadlineResponse])
def generate_deadlines(
    year: int = Query(...),
    estimated_income: float = Query(...),
    db: Session = Depends(get_db)
):
    """Generate tax deadlines for a year."""
    deadlines = generate_tax_deadlines(db, year, Decimal(str(estimated_income)))

    today = date.today()
    return [
        TaxDeadlineResponse(
            id=d.id,
            year=d.year,
            deadline_type=d.deadline_type,
            due_date=d.due_date,
            amount_due=d.amount_due,
            amount_paid=d.amount_paid,
            remaining=d.remaining,
            is_paid=d.is_paid,
            name=d.name,
            days_remaining=(d.due_date - today).days,
            pillar_id=d.pillar_id,
        )
        for d in deadlines
    ]


@router.put("/taxes/deadlines/{deadline_id}/pay", response_model=TaxDeadlineResponse)
def pay_tax_deadline(
    deadline_id: int,
    data: TaxPaymentRequest,
    db: Session = Depends(get_db)
):
    """Record a payment for a tax deadline."""
    try:
        deadline = record_tax_payment(db, deadline_id, data.amount)
        today = date.today()
        return TaxDeadlineResponse(
            id=deadline.id,
            year=deadline.year,
            deadline_type=deadline.deadline_type,
            due_date=deadline.due_date,
            amount_due=deadline.amount_due,
            amount_paid=deadline.amount_paid,
            remaining=deadline.remaining,
            is_paid=deadline.is_paid,
            name=deadline.name,
            days_remaining=(deadline.due_date - today).days,
            pillar_id=deadline.pillar_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/taxes/monthly-reserve/{year}", response_model=dict)
def get_monthly_reserve(year: int, db: Session = Depends(get_db)):
    """Get recommended monthly tax reserve."""
    reserve = calculate_monthly_reserve(db, year)
    return {"year": year, "monthly_reserve": reserve}


@router.get("/taxes/coverage", response_model=TaxCoverageResponse)
def get_coverage(db: Session = Depends(get_db)):
    """Get tax coverage status."""
    coverage = get_tax_coverage(db)
    today = date.today()

    return TaxCoverageResponse(
        total_due=coverage.total_due,
        total_reserved=coverage.total_reserved,
        coverage_percentage=coverage.coverage_percentage,
        monthly_reserve_needed=coverage.monthly_reserve_needed,
        is_covered=coverage.is_covered,
        deadlines=[
            TaxDeadlineResponse(
                id=d.id,
                year=d.year,
                deadline_type=d.deadline_type,
                due_date=d.due_date,
                amount_due=d.amount_due,
                amount_paid=d.amount_paid,
                remaining=d.remaining,
                is_paid=d.is_paid,
                name=d.name,
                days_remaining=(d.due_date - today).days,
                pillar_id=d.pillar_id,
            )
            for d in coverage.deadlines
        ],
    )


# ==================== BANK IMPORT ====================

@router.post("/bank/import", response_model=BankImportResponse)
def import_bank_csv(data: BankImportRequest, db: Session = Depends(get_db)):
    """Import bank statement CSV."""
    try:
        bank_format = BankFormat(data.bank_format)
    except ValueError:
        bank_format = BankFormat.GENERIC

    result = import_bank_statement(
        db, data.content, data.year, data.month, bank_format
    )

    return BankImportResponse(
        total_rows=result.total_rows,
        imported=result.imported,
        skipped=result.skipped,
        errors=result.errors,
        uncategorized_count=result.uncategorized_count,
        transactions=[
            TransactionResponse(
                id=tx.id,
                date=tx.date,
                amount=tx.amount,
                description=tx.description,
                original_description=tx.original_description,
                category_id=tx.category_id,
                is_income=tx.is_income,
                is_taxable=tx.is_taxable,
                source=tx.source,
                created_at=tx.created_at,
            )
            for tx in result.transactions
        ],
    )


@router.get("/bank/uncategorized", response_model=UncategorizedTransactionsResponse)
def list_uncategorized(
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get uncategorized transactions for review."""
    transactions = get_uncategorized_transactions(db, year, month)
    return UncategorizedTransactionsResponse(
        transactions=[
            TransactionResponse(
                id=tx.id,
                date=tx.date,
                amount=tx.amount,
                description=tx.description,
                original_description=tx.original_description,
                category_id=tx.category_id,
                is_income=tx.is_income,
                is_taxable=tx.is_taxable,
                source=tx.source,
                created_at=tx.created_at,
            )
            for tx in transactions
        ],
        count=len(transactions),
    )


# ==================== PLANNED EXPENSES ====================

@router.get("/expenses/planned", response_model=list[PlannedExpenseResponse])
def list_planned_expenses(
    completed: bool = Query(default=False),
    db: Session = Depends(get_db)
):
    """List planned expenses."""
    query = db.query(PlannedExpense)
    if not completed:
        query = query.filter(PlannedExpense.is_completed == False)
    return query.order_by(PlannedExpense.target_date).all()


@router.post("/expenses/planned", response_model=PlannedExpenseResponse)
def create_planned_expense(data: PlannedExpenseCreate, db: Session = Depends(get_db)):
    """Create a planned expense."""
    expense = PlannedExpense(**data.model_dump())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.put("/expenses/planned/{expense_id}", response_model=PlannedExpenseResponse)
def update_planned_expense(
    expense_id: int,
    data: PlannedExpenseUpdate,
    db: Session = Depends(get_db)
):
    """Update a planned expense."""
    expense = db.query(PlannedExpense).filter(PlannedExpense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Planned expense not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(expense, key, value)

    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/expenses/planned/{expense_id}")
def delete_planned_expense(expense_id: int, db: Session = Depends(get_db)):
    """Delete a planned expense."""
    expense = db.query(PlannedExpense).filter(PlannedExpense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Planned expense not found")

    db.delete(expense)
    db.commit()
    return {"status": "deleted", "id": expense_id}


# ==================== USER SETTINGS ====================

@router.get("/settings", response_model=UserSettingsResponse)
def get_user_settings(db: Session = Depends(get_db)):
    """Get user settings."""
    settings = db.query(UserSettings).first()
    if not settings:
        settings = UserSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.put("/settings", response_model=UserSettingsResponse)
def update_user_settings(data: UserSettingsUpdate, db: Session = Depends(get_db)):
    """Update user settings."""
    settings = db.query(UserSettings).first()
    if not settings:
        settings = UserSettings(**data.model_dump())
        db.add(settings)
    else:
        for key, value in data.model_dump().items():
            setattr(settings, key, value)

    db.commit()
    db.refresh(settings)
    return settings
