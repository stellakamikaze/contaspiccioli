"""Pillar service - Manage the 4 financial pillars (Coletti method)."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Pillar, PlannedExpense, TaxDeadline, UserSettings


@dataclass
class PillarStatus:
    """Status of a single pillar."""
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

    @property
    def shortfall(self) -> Decimal:
        """Amount needed to reach target."""
        return max(Decimal("0.00"), self.target_balance - self.current_balance)

    @property
    def surplus(self) -> Decimal:
        """Amount over target."""
        return max(Decimal("0.00"), self.current_balance - self.target_balance)


@dataclass
class AllocationSuggestion:
    """Suggestion for allocating surplus."""
    pillar_id: int
    pillar_name: str
    amount: Decimal
    reason: str
    priority: int


@dataclass
class Transfer:
    """Record of a transfer between pillars."""
    from_pillar_id: int
    to_pillar_id: int
    amount: Decimal
    date: date
    notes: str


def get_pillar_status(db: Session) -> list[PillarStatus]:
    """
    Get status of all 4 pillars with completion percentage.
    """
    pillars = db.query(Pillar).order_by(Pillar.number).all()

    statuses = []
    for p in pillars:
        status = PillarStatus(
            id=p.id,
            number=p.number,
            name=p.name,
            display_name=p.display_name,
            current_balance=p.current_balance,
            target_balance=p.target_balance,
            completion_percentage=p.completion_percentage,
            is_funded=p.is_funded,
            instrument=p.instrument,
            account_name=p.account_name,
            priority=p.priority,
        )
        statuses.append(status)

    return statuses


def calculate_target_balances(
    db: Session,
    average_monthly_expenses: Decimal
) -> dict[int, Decimal]:
    """
    Calculate target balance for each pillar based on expenses.

    - P1: 3 months of expenses (minimum)
    - P2: 6 months of expenses (default, configurable 3-12)
    - P3: Sum of upcoming tax deadlines + planned expenses
    - P4: User-defined (no automatic target)
    """
    targets = {}

    pillars = db.query(Pillar).all()
    for p in pillars:
        if p.number == 1:
            # P1: Liquidità - at least 3 months
            months = p.target_months or 3
            targets[p.id] = average_monthly_expenses * months

        elif p.number == 2:
            # P2: Emergenza - 3-12 months, default 6
            months = p.target_months or 6
            targets[p.id] = average_monthly_expenses * months

        elif p.number == 3:
            # P3: Spese previste - sum of all upcoming obligations
            today = date.today()

            # Tax deadlines - sum of remaining amounts
            tax_sum = sum(
                td.remaining for td in db.query(TaxDeadline).filter(
                    TaxDeadline.due_date >= today
                ).all()
            )

            # Planned expenses
            expense_sum = sum(
                pe.remaining for pe in db.query(PlannedExpense).filter(
                    PlannedExpense.is_completed == False
                ).all()
            )

            targets[p.id] = tax_sum + expense_sum

        elif p.number == 4:
            # P4: Investimenti - keep current target (user-defined)
            targets[p.id] = p.target_balance

    return targets


def update_pillar_targets(
    db: Session,
    average_monthly_expenses: Decimal
) -> list[Pillar]:
    """Update target balances for all pillars."""
    targets = calculate_target_balances(db, average_monthly_expenses)

    pillars = db.query(Pillar).all()
    for p in pillars:
        if p.id in targets:
            p.target_balance = targets[p.id]
            p.is_funded = p.current_balance >= p.target_balance

    db.commit()
    return pillars


def suggest_allocation(
    db: Session,
    surplus: Decimal
) -> list[AllocationSuggestion]:
    """
    Given a surplus, suggest how to allocate it across pillars.

    Priority order (Coletti method):
    1. P2 (Emergenza) if not fully funded
    2. P3 (Spese Previste) if deadlines approaching
    3. P4 (Investimenti) with remainder
    """
    suggestions = []
    remaining = surplus

    if remaining <= 0:
        return suggestions

    # Get pillar statuses
    p2 = db.query(Pillar).filter(Pillar.number == 2).first()
    p3 = db.query(Pillar).filter(Pillar.number == 3).first()
    p4 = db.query(Pillar).filter(Pillar.number == 4).first()

    # 1. P2 Emergency Fund
    if p2 and p2.current_balance < p2.target_balance:
        needed = p2.target_balance - p2.current_balance
        allocation = min(remaining, needed)
        if allocation > 0:
            suggestions.append(AllocationSuggestion(
                pillar_id=p2.id,
                pillar_name=p2.display_name,
                amount=allocation,
                reason=f"Fondo emergenza sotto target ({p2.completion_percentage:.0f}%)",
                priority=1,
            ))
            remaining -= allocation

    # 2. P3 Spese Previste (if deadlines in next 3 months)
    if p3 and remaining > 0:
        today = date.today()
        near_deadlines = db.query(TaxDeadline).filter(
            TaxDeadline.due_date >= today,
            TaxDeadline.due_date < date(
                today.year if today.month <= 9 else today.year + 1,
                (today.month + 3 - 1) % 12 + 1,
                1
            )
        ).all()

        near_total = sum(d.remaining for d in near_deadlines)
        if near_total > p3.current_balance:
            needed = near_total - p3.current_balance
            allocation = min(remaining, needed)
            if allocation > 0:
                suggestions.append(AllocationSuggestion(
                    pillar_id=p3.id,
                    pillar_name=p3.display_name,
                    amount=allocation,
                    reason=f"Scadenze fiscali nei prossimi 3 mesi: {near_total:.2f}€",
                    priority=2,
                ))
                remaining -= allocation

    # 3. P4 Investments with remainder
    if p4 and remaining > 0:
        suggestions.append(AllocationSuggestion(
            pillar_id=p4.id,
            pillar_name=p4.display_name,
            amount=remaining,
            reason="Investimenti a lungo termine",
            priority=3,
        ))

    return suggestions


def update_pillar_balance(
    db: Session,
    pillar_id: int,
    new_balance: Decimal,
    notes: str = ""
) -> Pillar:
    """Update a pillar's current balance."""
    pillar = db.query(Pillar).filter(Pillar.id == pillar_id).first()
    if not pillar:
        raise ValueError(f"Pillar {pillar_id} not found")

    pillar.current_balance = new_balance
    pillar.is_funded = pillar.current_balance >= pillar.target_balance

    db.commit()
    return pillar


def record_transfer(
    db: Session,
    from_pillar_id: int,
    to_pillar_id: int,
    amount: Decimal,
    transfer_date: date = None,
    notes: str = ""
) -> tuple[Pillar, Pillar]:
    """
    Record a transfer between pillars.
    Updates both pillar balances.
    """
    if amount <= 0:
        raise ValueError("Transfer amount must be positive")

    from_pillar = db.query(Pillar).filter(Pillar.id == from_pillar_id).first()
    to_pillar = db.query(Pillar).filter(Pillar.id == to_pillar_id).first()

    if not from_pillar:
        raise ValueError(f"Source pillar {from_pillar_id} not found")
    if not to_pillar:
        raise ValueError(f"Destination pillar {to_pillar_id} not found")

    if from_pillar.current_balance < amount:
        raise ValueError(
            f"Insufficient balance in {from_pillar.display_name}: "
            f"{from_pillar.current_balance:.2f}€ < {amount:.2f}€"
        )

    # Update balances
    from_pillar.current_balance -= amount
    to_pillar.current_balance += amount

    # Update funded status
    from_pillar.is_funded = from_pillar.current_balance >= from_pillar.target_balance
    to_pillar.is_funded = to_pillar.current_balance >= to_pillar.target_balance

    db.commit()
    return from_pillar, to_pillar


def get_pillar_summary(db: Session) -> dict:
    """Get summary of all pillars for dashboard."""
    statuses = get_pillar_status(db)

    total_balance = sum(s.current_balance for s in statuses)
    total_target = sum(s.target_balance for s in statuses)
    overall_completion = (total_balance / total_target * 100) if total_target > 0 else 0

    return {
        'pillars': statuses,
        'total_balance': total_balance,
        'total_target': total_target,
        'overall_completion': overall_completion,
        'all_funded': all(s.is_funded for s in statuses),
    }


@dataclass
class MonthlyBudgetBreakdown:
    """Monthly budget breakdown showing how income is allocated."""
    gross_income: Decimal
    # Allocations to pillars
    tax_provision: Decimal          # P3 - Accantonamento tasse (~31%)
    emergency_contribution: Decimal  # P2 - Fondo emergenza (se sotto target)
    investment_contribution: Decimal # P4 - Investimenti
    # Available for spending (P1)
    available_for_p1: Decimal        # Liquidità totale
    fixed_costs: Decimal             # Costi fissi
    variable_budget: Decimal         # Budget disponibile per costi variabili
    # Percentages
    tax_rate_effective: Decimal
    investment_rate: Decimal
    emergency_rate: Decimal


def calculate_monthly_budget(
    db: Session,
    investment_percentage: Decimal = Decimal("0.10"),  # 10% default
    emergency_contribution_if_underfunded: Decimal = Decimal("0.05"),  # 5% extra if P2 underfunded
) -> MonthlyBudgetBreakdown:
    """
    Calculate how monthly income should be allocated across pillars.

    Priority order (Coletti method):
    1. Tasse (obbligatorio ~31% del reddito) → P3
    2. Fondo Emergenza (se sotto target) → P2
    3. Investimenti (% configurabile) → P4
    4. Spese quotidiane (resto) → P1 (fissi + variabili)
    """
    from app.models import Category, CategoryType
    from app.services.taxes import get_or_create_tax_settings, calculate_annual_taxes

    # Get user settings
    settings = db.query(UserSettings).first()
    if not settings:
        gross_income = Decimal("3500.00")
    else:
        gross_income = settings.monthly_income

    # 1. Calculate tax provision (INPS + IRPEF)
    year = date.today().year
    tax_settings = get_or_create_tax_settings(db, year)
    annual_taxes = calculate_annual_taxes(gross_income * 12, tax_settings)
    tax_provision = annual_taxes.monthly_provision
    tax_rate_effective = (tax_provision / gross_income * 100) if gross_income > 0 else Decimal("0")

    # 2. Check if P2 (Emergency) is underfunded
    p2 = db.query(Pillar).filter(Pillar.number == 2).first()
    emergency_contribution = Decimal("0.00")
    emergency_rate = Decimal("0.00")
    if p2 and not p2.is_funded:
        # Add extra contribution until funded
        emergency_contribution = gross_income * emergency_contribution_if_underfunded
        emergency_rate = emergency_contribution_if_underfunded * 100

    # 3. Investment contribution
    investment_contribution = gross_income * investment_percentage
    investment_rate = investment_percentage * 100

    # 4. Calculate what's left for P1 (daily expenses)
    available_for_p1 = gross_income - tax_provision - emergency_contribution - investment_contribution

    # 5. Calculate fixed costs from category budgets
    fixed_categories = db.query(Category).filter(
        Category.type == CategoryType.FIXED,
        Category.is_active == True
    ).all()
    fixed_costs = sum(cat.monthly_budget for cat in fixed_categories if cat.monthly_budget)

    # 6. Variable budget is what remains after fixed costs
    variable_budget = available_for_p1 - fixed_costs

    return MonthlyBudgetBreakdown(
        gross_income=gross_income,
        tax_provision=tax_provision,
        emergency_contribution=emergency_contribution,
        investment_contribution=investment_contribution,
        available_for_p1=available_for_p1,
        fixed_costs=fixed_costs,
        variable_budget=variable_budget,
        tax_rate_effective=tax_rate_effective,
        investment_rate=investment_rate,
        emergency_rate=emergency_rate,
    )
