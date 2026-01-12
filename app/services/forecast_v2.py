"""Forecast service v2 - 12-month cash flow projection."""
from datetime import date
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models_v2 import (
    ForecastMonth, ForecastLine, Category, Transaction,
    TaxDeadline, Pillar, UserSettings, LineType, CategoryType
)


MONTH_NAMES = [
    "", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"
]


@dataclass
class MonthlyComparison:
    """Comparison between expected and actual for a category."""
    category_id: int
    category_name: str
    category_icon: str
    expected: Decimal
    actual: Decimal

    @property
    def variance(self) -> Decimal:
        return self.actual - self.expected

    @property
    def is_over_budget(self) -> bool:
        return self.actual > self.expected


@dataclass
class ForecastComparison:
    """Full month forecast comparison."""
    year: int
    month: int
    month_name: str
    opening_balance: Decimal
    income: MonthlyComparison
    fixed_costs: list[MonthlyComparison]
    variable_costs: list[MonthlyComparison]
    total_expected_costs: Decimal
    total_actual_costs: Decimal
    expected_balance: Decimal
    actual_balance: Decimal

    @property
    def variance(self) -> Decimal:
        return self.actual_balance - self.expected_balance


def get_month_name(month: int) -> str:
    """Get Italian month name."""
    return MONTH_NAMES[month] if 1 <= month <= 12 else ""


def get_or_create_forecast_month(
    db: Session,
    year: int,
    month: int,
    opening_balance: Decimal = None
) -> ForecastMonth:
    """Get existing forecast month or create new one."""
    forecast = db.query(ForecastMonth).filter(
        ForecastMonth.year == year,
        ForecastMonth.month == month
    ).first()

    if not forecast:
        # Calculate opening balance from previous month if not provided
        if opening_balance is None:
            prev_month = month - 1 if month > 1 else 12
            prev_year = year if month > 1 else year - 1
            prev_forecast = db.query(ForecastMonth).filter(
                ForecastMonth.year == prev_year,
                ForecastMonth.month == prev_month
            ).first()
            opening_balance = prev_forecast.actual_balance if prev_forecast else Decimal("0.00")

        forecast = ForecastMonth(
            year=year,
            month=month,
            opening_balance=opening_balance
        )
        db.add(forecast)
        db.commit()
        db.refresh(forecast)

    return forecast


def generate_yearly_forecast(
    db: Session,
    year: int,
    base_income: Decimal,
    opening_balance: Decimal
) -> list[ForecastMonth]:
    """
    Generate 12-month forecast for the year.

    Creates ForecastMonth and ForecastLine entries based on:
    - Base income (monthly average)
    - Category budgets
    - Tax deadlines
    """
    forecasts = []
    current_balance = opening_balance

    # Get all categories with budgets
    income_categories = db.query(Category).filter(
        Category.type == CategoryType.INCOME,
        Category.is_active == True
    ).all()

    fixed_categories = db.query(Category).filter(
        Category.type == CategoryType.FIXED,
        Category.is_active == True
    ).all()

    variable_categories = db.query(Category).filter(
        Category.type == CategoryType.VARIABLE,
        Category.is_active == True
    ).all()

    # Get tax deadlines for the year
    tax_deadlines = db.query(TaxDeadline).filter(
        TaxDeadline.year == year
    ).all()

    for month in range(1, 13):
        forecast = get_or_create_forecast_month(db, year, month, current_balance)

        # Clear existing lines (for regeneration)
        db.query(ForecastLine).filter(
            ForecastLine.forecast_month_id == forecast.id
        ).delete()

        total_income = Decimal("0.00")
        total_fixed = Decimal("0.00")
        total_variable = Decimal("0.00")

        # Add income lines
        for cat in income_categories:
            # Use category budget if defined (even if 0), else fall back to base_income
            amount = cat.monthly_budget if cat.monthly_budget is not None else base_income
            if amount > 0:
                line = ForecastLine(
                    forecast_month_id=forecast.id,
                    category_id=cat.id,
                    line_type=LineType.INCOME,
                    description=cat.name,
                    expected_amount=amount,
                    is_recurring=True,
                )
                db.add(line)
                total_income += amount

        # Add fixed cost lines
        for cat in fixed_categories:
            if cat.monthly_budget > 0:
                line = ForecastLine(
                    forecast_month_id=forecast.id,
                    category_id=cat.id,
                    line_type=LineType.FIXED_COST,
                    description=cat.name,
                    expected_amount=cat.monthly_budget,
                    is_recurring=True,
                )
                db.add(line)
                total_fixed += cat.monthly_budget

        # Add tax deadlines for this month
        for deadline in tax_deadlines:
            if deadline.due_date.month == month:
                line = ForecastLine(
                    forecast_month_id=forecast.id,
                    category_id=None,  # Taxes are special
                    line_type=LineType.FIXED_COST,
                    description=deadline.name,
                    expected_amount=deadline.amount_due,
                    is_recurring=False,
                )
                db.add(line)
                total_fixed += deadline.amount_due

        # Add variable cost lines
        for cat in variable_categories:
            if cat.monthly_budget > 0:
                line = ForecastLine(
                    forecast_month_id=forecast.id,
                    category_id=cat.id,
                    line_type=LineType.VARIABLE_COST,
                    description=cat.name,
                    expected_amount=cat.monthly_budget,
                    is_recurring=True,
                )
                db.add(line)
                total_variable += cat.monthly_budget

        # Update forecast totals
        forecast.opening_balance = current_balance
        forecast.expected_income = total_income
        forecast.expected_fixed_costs = total_fixed
        forecast.expected_variable_costs = total_variable

        # Calculate next month's opening balance
        current_balance = forecast.expected_balance
        forecasts.append(forecast)

    db.commit()
    return forecasts


def get_forecast_comparison(
    db: Session,
    year: int,
    month: int
) -> Optional[ForecastComparison]:
    """
    Get detailed comparison of expected vs actual for a month.
    This is the Sibill-style view.
    """
    forecast = db.query(ForecastMonth).filter(
        ForecastMonth.year == year,
        ForecastMonth.month == month
    ).first()

    if not forecast:
        return None

    # Get all lines grouped by type
    lines = db.query(ForecastLine).filter(
        ForecastLine.forecast_month_id == forecast.id
    ).all()

    # Build income comparison
    income_lines = [l for l in lines if l.line_type == LineType.INCOME]
    total_expected_income = sum(l.expected_amount for l in income_lines)
    total_actual_income = sum(l.actual_amount for l in income_lines)

    income_comparison = MonthlyComparison(
        category_id=0,
        category_name="Totale Entrate",
        category_icon="💰",
        expected=total_expected_income,
        actual=total_actual_income
    )

    # Build fixed costs comparisons
    fixed_lines = [l for l in lines if l.line_type == LineType.FIXED_COST]
    fixed_comparisons = []
    for line in fixed_lines:
        cat = line.category
        fixed_comparisons.append(MonthlyComparison(
            category_id=cat.id if cat else 0,
            category_name=line.description,
            category_icon=cat.icon if cat else "📋",
            expected=line.expected_amount,
            actual=line.actual_amount
        ))

    # Build variable costs comparisons
    variable_lines = [l for l in lines if l.line_type == LineType.VARIABLE_COST]
    variable_comparisons = []
    for line in variable_lines:
        cat = line.category
        variable_comparisons.append(MonthlyComparison(
            category_id=cat.id if cat else 0,
            category_name=line.description,
            category_icon=cat.icon if cat else "📦",
            expected=line.expected_amount,
            actual=line.actual_amount
        ))

    total_expected_costs = forecast.expected_total_costs
    total_actual_costs = forecast.actual_total_costs

    return ForecastComparison(
        year=year,
        month=month,
        month_name=get_month_name(month),
        opening_balance=forecast.opening_balance,
        income=income_comparison,
        fixed_costs=fixed_comparisons,
        variable_costs=variable_comparisons,
        total_expected_costs=total_expected_costs,
        total_actual_costs=total_actual_costs,
        expected_balance=forecast.expected_balance,
        actual_balance=forecast.actual_balance
    )


def update_forecast_actuals(
    db: Session,
    year: int,
    month: int
) -> ForecastMonth:
    """
    Update actual values in forecast from transactions.
    Called after importing bank statement.
    """
    forecast = get_or_create_forecast_month(db, year, month)

    # Get all transactions for this month
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    transactions = db.query(Transaction).filter(
        Transaction.date >= start_date,
        Transaction.date < end_date
    ).all()

    # Aggregate by category
    category_totals: dict[int, Decimal] = {}
    for tx in transactions:
        if tx.category_id:
            if tx.category_id not in category_totals:
                category_totals[tx.category_id] = Decimal("0.00")
            category_totals[tx.category_id] += abs(tx.amount)

    # Update forecast lines with actuals
    lines = db.query(ForecastLine).filter(
        ForecastLine.forecast_month_id == forecast.id
    ).all()

    total_actual_income = Decimal("0.00")
    total_actual_fixed = Decimal("0.00")
    total_actual_variable = Decimal("0.00")

    for line in lines:
        if line.category_id and line.category_id in category_totals:
            line.actual_amount = category_totals[line.category_id]

        if line.line_type == LineType.INCOME:
            total_actual_income += line.actual_amount
        elif line.line_type == LineType.FIXED_COST:
            total_actual_fixed += line.actual_amount
        elif line.line_type == LineType.VARIABLE_COST:
            total_actual_variable += line.actual_amount

    # Update forecast totals
    forecast.actual_income = total_actual_income
    forecast.actual_fixed_costs = total_actual_fixed
    forecast.actual_variable_costs = total_actual_variable

    db.commit()
    return forecast


def project_balance(
    db: Session,
    months_ahead: int = 12,
    starting_balance: Decimal = None
) -> list[dict]:
    """
    Project P1 (liquidity) balance for the next N months.

    Returns list of: {month, year, opening, income, costs, closing, cumulative}
    """
    today = date.today()
    projections = []

    if starting_balance is None:
        # Get P1 current balance
        p1 = db.query(Pillar).filter(Pillar.number == 1).first()
        starting_balance = p1.current_balance if p1 else Decimal("0.00")

    cumulative = starting_balance

    for i in range(months_ahead):
        month = (today.month + i - 1) % 12 + 1
        year = today.year + (today.month + i - 1) // 12

        forecast = db.query(ForecastMonth).filter(
            ForecastMonth.year == year,
            ForecastMonth.month == month
        ).first()

        if forecast:
            income = forecast.expected_income
            costs = forecast.expected_total_costs
        else:
            # Use averages if no forecast exists
            income = Decimal("3500.00")  # Default
            costs = Decimal("2500.00")   # Default

        closing = cumulative + income - costs

        projections.append({
            'month': month,
            'year': year,
            'month_name': get_month_name(month),
            'opening': cumulative,
            'income': income,
            'costs': costs,
            'closing': closing,
            'cumulative': closing,
        })

        cumulative = closing

    return projections
