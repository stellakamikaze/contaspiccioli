"""Budget calculation service."""
from datetime import date
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.models import Transaction, Category, Pillar, MonthlyForecast
from app.config import settings


def get_monthly_summary(db: Session, year: int, month: int) -> Dict:
    """Get budget summary for a specific month."""
    # Get all transactions for the month
    transactions = db.query(Transaction).filter(
        extract('year', Transaction.date) == year,
        extract('month', Transaction.date) == month
    ).all()

    income = sum(t.amount for t in transactions if t.is_income)
    expenses = sum(t.amount for t in transactions if not t.is_income)

    # Get expenses by category
    category_spending = {}
    for t in transactions:
        if not t.is_income and t.category:
            cat_name = t.category.name
            if cat_name not in category_spending:
                category_spending[cat_name] = {
                    'budget': t.category.monthly_budget,
                    'spent': 0,
                    'icon': t.category.icon,
                    'type': t.category.type
                }
            category_spending[cat_name]['spent'] += t.amount

    # Calculate percentages and alerts
    for cat_name, data in category_spending.items():
        if data['budget'] > 0:
            data['percentage'] = (data['spent'] / data['budget']) * 100
            data['exceeded'] = data['spent'] > data['budget']
        else:
            data['percentage'] = 0
            data['exceeded'] = False

    # Get fixed vs variable totals
    fixed_spent = sum(
        data['spent'] for data in category_spending.values()
        if data['type'] == 'fissa'
    )
    variable_spent = sum(
        data['spent'] for data in category_spending.values()
        if data['type'] == 'variabile'
    )

    return {
        'year': year,
        'month': month,
        'income': income,
        'expenses': expenses,
        'balance': income - expenses,
        'fixed_spent': fixed_spent,
        'variable_spent': variable_spent,
        'categories': category_spending,
        'expected_income': settings.default_income,
        'expected_fixed': settings.default_income * settings.fixed_percentage,
        'expected_variable': settings.default_income * settings.variable_percentage,
    }


def get_pillar_summary(db: Session) -> List[Dict]:
    """Get summary of all financial pillars."""
    pillars = db.query(Pillar).all()
    result = []

    for p in pillars:
        theoretical = p.target_balance + (p.monthly_contribution * _months_elapsed())
        result.append({
            'id': p.id,
            'name': p.name,
            'display_name': p.display_name,
            'target': p.target_balance,
            'theoretical': theoretical,
            'actual': p.actual_balance,
            'difference': p.actual_balance - theoretical,
            'percentage': p.percentage,
            'last_reconciled': p.last_reconciled
        })

    return result


def _months_elapsed() -> int:
    """Calculate months elapsed in current year."""
    today = date.today()
    return today.month


def get_yearly_forecast(db: Session, year: int) -> List[Dict]:
    """Get forecast for all months of a year."""
    forecasts = db.query(MonthlyForecast).filter(
        MonthlyForecast.year == year
    ).order_by(MonthlyForecast.month).all()

    result = []
    cumulative = 0

    for month in range(1, 13):
        forecast = next((f for f in forecasts if f.month == month), None)

        if forecast:
            expected = forecast.expected_income - forecast.expected_fixed - forecast.expected_variable
            actual = forecast.actual_income - forecast.actual_fixed - forecast.actual_variable
        else:
            expected = settings.default_income * (1 - settings.tax_percentage - settings.investment_percentage) - \
                       settings.default_income * settings.fixed_percentage - \
                       settings.default_income * settings.variable_percentage
            actual = 0

        cumulative += actual if forecast else expected

        result.append({
            'month': month,
            'expected_income': forecast.expected_income if forecast else settings.default_income,
            'expected_expenses': (forecast.expected_fixed + forecast.expected_variable) if forecast else \
                                 settings.default_income * (settings.fixed_percentage + settings.variable_percentage),
            'actual_income': forecast.actual_income if forecast else 0,
            'actual_expenses': (forecast.actual_fixed + forecast.actual_variable) if forecast else 0,
            'balance': actual if forecast else expected,
            'cumulative': cumulative
        })

    return result


def calculate_tax_obligations(gross_income: float) -> Dict:
    """Calculate tax obligations for P.IVA forfettaria."""
    taxable_income = gross_income * settings.coefficient
    inps = taxable_income * settings.inps_rate
    irpef = taxable_income * settings.tax_rate
    total_tax = inps + irpef

    return {
        'gross_income': gross_income,
        'taxable_income': taxable_income,
        'inps': inps,
        'irpef': irpef,
        'total_tax': total_tax,
        'net_income': gross_income - total_tax,
        'effective_rate': (total_tax / gross_income) * 100 if gross_income > 0 else 0
    }
