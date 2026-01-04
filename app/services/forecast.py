"""Forecast and projection service."""
from datetime import date
from typing import Dict, List
from sqlalchemy.orm import Session

from app.models import UserProfile, MonthlyIncome, Pillar, TaxDeadline


def get_monthly_projection(db: Session, profile: UserProfile, months_ahead: int = 12) -> List[Dict]:
    """
    Project cash flow for the next N months based on current income and settings.

    Returns a list of monthly projections with:
    - Expected income
    - Allocations to each pillar
    - Cumulative balances
    """
    today = date.today()
    projections = []

    # Get current incomes for this month
    current_incomes = db.query(MonthlyIncome).filter(
        MonthlyIncome.year == today.year,
        MonthlyIncome.month == today.month
    ).all()

    # Use actual income if available, otherwise use profile default
    base_income = sum(i.amount for i in current_incomes) if current_incomes else profile.monthly_income

    # Get current pillar balances
    emergency_pillar = db.query(Pillar).filter(Pillar.name == "emergenza").first()
    tax_pillar = db.query(Pillar).filter(Pillar.name == "tasse").first()
    invest_pillar = db.query(Pillar).filter(Pillar.name == "investimenti").first()

    # Starting balances
    current_balance = profile.current_balance
    emergency_balance = emergency_pillar.actual_balance if emergency_pillar else profile.emergency_balance
    tax_balance = tax_pillar.actual_balance if tax_pillar else profile.tax_balance
    invest_balance = invest_pillar.actual_balance if invest_pillar else 0

    # Get upcoming tax deadlines
    deadlines = db.query(TaxDeadline).filter(
        TaxDeadline.due_date >= today
    ).order_by(TaxDeadline.due_date).all()

    for i in range(months_ahead):
        month = (today.month + i - 1) % 12 + 1
        year = today.year + (today.month + i - 1) // 12

        # Monthly allocations
        tax_allocation = base_income * profile.tax_percentage
        invest_allocation = base_income * profile.investment_percentage
        fixed_expenses = profile.total_fixed_expenses
        variable_expenses = profile.total_variable_budget

        # Available for spending
        available = base_income - tax_allocation - invest_allocation - fixed_expenses - variable_expenses

        # Update balances
        tax_balance += tax_allocation
        invest_balance += invest_allocation
        current_balance += available

        # Emergency contribution (only if below target)
        emergency_contribution = 0
        if emergency_balance < profile.emergency_target:
            # Use any surplus for emergency fund
            if available > 0:
                emergency_contribution = min(available * 0.5, profile.emergency_target - emergency_balance)
                emergency_balance += emergency_contribution
                current_balance -= emergency_contribution

        # Check for tax payments in this month
        tax_payment = 0
        for deadline in deadlines:
            if deadline.due_date.year == year and deadline.due_date.month == month:
                tax_payment += deadline.residuo
                tax_balance -= deadline.residuo

        projections.append({
            'month': month,
            'year': year,
            'month_name': _month_name(month),
            'income': base_income,
            'allocations': {
                'fixed': fixed_expenses,
                'variable': variable_expenses,
                'tax': tax_allocation,
                'investment': invest_allocation,
            },
            'tax_payment': tax_payment,
            'emergency_contribution': emergency_contribution,
            'balances': {
                'current': current_balance,
                'emergency': emergency_balance,
                'tax': tax_balance,
                'investment': invest_balance,
            },
            'emergency_target_reached': emergency_balance >= profile.emergency_target,
        })

    return projections


def calculate_piva_taxes(profile: UserProfile, annual_income: float) -> Dict:
    """
    Calculate P.IVA forfettaria taxes for a given annual income.

    Formula:
    - Imponibile = Fatturato * Coefficiente (78%)
    - INPS = Imponibile * 25.98%
    - IRPEF = Imponibile * 5% (o 15%)
    - Totale = INPS + IRPEF
    """
    taxable = annual_income * profile.coefficient
    inps = taxable * profile.inps_rate
    irpef = taxable * profile.tax_rate
    total = inps + irpef

    return {
        'gross_income': annual_income,
        'coefficient': profile.coefficient,
        'taxable_income': taxable,
        'inps': inps,
        'inps_rate': profile.inps_rate,
        'irpef': irpef,
        'tax_rate': profile.tax_rate,
        'total_tax': total,
        'net_income': annual_income - total,
        'effective_rate': (total / annual_income) * 100 if annual_income > 0 else 0,
        'monthly_provision': total / 12,
    }


def get_tax_coverage(db: Session, profile: UserProfile) -> Dict:
    """
    Calculate tax coverage status.

    Returns:
    - How much is accrued
    - How much is owed
    - Coverage percentage
    """
    tax_pillar = db.query(Pillar).filter(Pillar.name == "tasse").first()

    # Get upcoming deadlines
    today = date.today()
    deadlines = db.query(TaxDeadline).filter(
        TaxDeadline.due_date >= today
    ).order_by(TaxDeadline.due_date).all()

    total_owed = sum(d.residuo for d in deadlines)
    accrued = tax_pillar.actual_balance if tax_pillar else profile.tax_balance

    return {
        'accrued': accrued,
        'total_owed': total_owed,
        'coverage_percentage': (accrued / total_owed * 100) if total_owed > 0 else 100,
        'shortfall': max(0, total_owed - accrued),
        'surplus': max(0, accrued - total_owed),
        'next_deadline': deadlines[0] if deadlines else None,
    }


def get_yearly_summary(db: Session, profile: UserProfile, year: int) -> Dict:
    """
    Get summary projections for a specific year.
    """
    today = date.today()

    # Get all incomes for the year
    incomes = db.query(MonthlyIncome).filter(
        MonthlyIncome.year == year
    ).all()

    # Actual income received
    actual_income = sum(i.amount for i in incomes if i.is_received)
    expected_income = sum(i.amount for i in incomes if not i.is_received)

    # If no recorded incomes, use profile default
    if not incomes:
        months_passed = today.month if year == today.year else 12
        months_remaining = 12 - months_passed if year == today.year else 0
        actual_income = profile.monthly_income * months_passed
        expected_income = profile.monthly_income * months_remaining

    total_projected = actual_income + expected_income

    # Calculate taxes on projected income
    taxes = calculate_piva_taxes(profile, total_projected)

    return {
        'year': year,
        'actual_income': actual_income,
        'expected_income': expected_income,
        'total_projected': total_projected,
        'monthly_average': total_projected / 12,
        'taxes': taxes,
        'net_yearly': total_projected - taxes['total_tax'],
        'net_monthly': (total_projected - taxes['total_tax']) / 12,
    }


def _month_name(month: int) -> str:
    """Get Italian month name."""
    months = [
        "", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
        "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"
    ]
    return months[month] if 1 <= month <= 12 else ""
