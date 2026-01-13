"""Tax service - P.IVA forfettaria tax calculations."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import TaxSettings, TaxDeadline, TaxRegime, AdvanceMethod, DeadlineType, Pillar


@dataclass
class TaxBreakdown:
    """Detailed tax calculation breakdown."""
    gross_income: Decimal
    coefficient: Decimal
    taxable_income: Decimal
    inps: Decimal
    inps_rate: Decimal
    irpef: Decimal
    tax_rate: Decimal
    total_tax: Decimal
    net_income: Decimal
    effective_rate: Decimal
    monthly_provision: Decimal


@dataclass
class TaxCoverage:
    """Tax coverage status for dashboard."""
    accrued: Decimal          # Amount set aside
    total_owed: Decimal       # Total upcoming deadlines
    coverage_percentage: float
    shortfall: Decimal
    surplus: Decimal
    next_deadline: Optional[TaxDeadline]
    monthly_reserve_needed: Decimal


def get_or_create_tax_settings(db: Session, year: int) -> TaxSettings:
    """Get tax settings for year, creating defaults if needed."""
    settings = db.query(TaxSettings).filter(TaxSettings.year == year).first()

    if not settings:
        # Create default settings for P.IVA forfettaria
        settings = TaxSettings(
            year=year,
            regime=TaxRegime.FORFETTARIO,
            coefficient=Decimal("0.78"),
            inps_rate=Decimal("0.2607"),
            tax_rate=Decimal("0.15"),
            advance_method=AdvanceMethod.STORICO,
            min_threshold=Decimal("52.00"),
            single_payment_threshold=Decimal("258.00"),
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return settings


def calculate_annual_taxes(
    gross_income: Decimal,
    settings: TaxSettings
) -> TaxBreakdown:
    """
    Calculate annual taxes for P.IVA forfettaria.

    Formula:
    - Imponibile = Fatturato × Coefficiente (78%)
    - INPS = Imponibile × 26.07%
    - IRPEF = (Imponibile - INPS) × 15%
    - Totale = INPS + IRPEF
    """
    taxable_income = (gross_income * settings.coefficient).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    inps = (taxable_income * settings.inps_rate).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    # IRPEF is calculated on taxable income MINUS INPS
    irpef_base = taxable_income - inps
    irpef = (irpef_base * settings.tax_rate).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    total_tax = inps + irpef
    net_income = gross_income - total_tax
    effective_rate = (total_tax / gross_income * 100) if gross_income > 0 else Decimal("0")
    monthly_provision = (total_tax / 12).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return TaxBreakdown(
        gross_income=gross_income,
        coefficient=settings.coefficient,
        taxable_income=taxable_income,
        inps=inps,
        inps_rate=settings.inps_rate,
        irpef=irpef,
        tax_rate=settings.tax_rate,
        total_tax=total_tax,
        net_income=net_income,
        effective_rate=effective_rate,
        monthly_provision=monthly_provision,
    )


def generate_tax_deadlines(
    db: Session,
    year: int,
    estimated_income: Decimal
) -> list[TaxDeadline]:
    """
    Generate tax deadlines for a year based on estimated income.

    Italian tax calendar (P.IVA forfettaria):
    - June/July: Saldo anno precedente + 1° Acconto (50%)
    - November: 2° Acconto (50%)

    Thresholds:
    - < 52€: No advances required
    - 52-258€: Single payment in November
    - > 258€: Split 50/50 between June and November
    """
    settings = get_or_create_tax_settings(db, year)
    taxes = calculate_annual_taxes(estimated_income, settings)

    # Clear existing deadlines for the year
    db.query(TaxDeadline).filter(TaxDeadline.year == year).delete()

    # Get P3 pillar for association
    p3 = db.query(Pillar).filter(Pillar.number == 3).first()
    p3_id = p3.id if p3 else None

    deadlines = []

    # Calculate advances based on method
    if settings.advance_method == AdvanceMethod.STORICO:
        # Historic method: 100% of previous year tax, 80% of INPS
        prior_tax = settings.prior_year_tax_paid
        prior_inps = settings.prior_year_inps_paid
        tax_advance = prior_tax  # 100%
        inps_advance = prior_inps * Decimal("0.80")  # 80%
        total_advance = tax_advance + inps_advance
    else:
        # Previsional method: based on current year estimate
        total_advance = taxes.total_tax

    # Check thresholds
    if total_advance < settings.min_threshold:
        # Below 52€: exempt from advances
        return deadlines

    # July deadline (Saldo + 1° Acconto)
    # Note: Date can vary! 2025 was July 21 due to postponement
    july_date = date(year, 7, 16)  # Standard date, may need adjustment

    if total_advance < settings.single_payment_threshold:
        # 52-258€: Single payment in November
        deadline = TaxDeadline(
            year=year,
            deadline_type=DeadlineType.ACCONTO_2,
            name=f"Acconto Unico {year}",
            due_date=date(year, 11, 30),
            amount_due=total_advance,
            pillar_id=p3_id,
            is_calculated=True,
        )
        db.add(deadline)
        deadlines.append(deadline)
    else:
        # > 258€: Split 50/50
        first_half = (total_advance / 2).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        second_half = total_advance - first_half

        # First deadline: Saldo + 1° Acconto
        deadline1 = TaxDeadline(
            year=year,
            deadline_type=DeadlineType.SALDO,
            name=f"Saldo {year-1} + 1° Acconto {year}",
            due_date=july_date,
            amount_due=first_half,
            pillar_id=p3_id,
            is_calculated=True,
        )
        db.add(deadline1)
        deadlines.append(deadline1)

        # Second deadline: 2° Acconto
        deadline2 = TaxDeadline(
            year=year,
            deadline_type=DeadlineType.ACCONTO_2,
            name=f"2° Acconto {year}",
            due_date=date(year, 11, 30),
            amount_due=second_half,
            pillar_id=p3_id,
            is_calculated=True,
        )
        db.add(deadline2)
        deadlines.append(deadline2)

    db.commit()
    return deadlines


def calculate_monthly_reserve(
    db: Session,
    year: int
) -> Decimal:
    """
    Calculate how much to set aside monthly to cover upcoming taxes.
    """
    today = date.today()

    # Get all unpaid deadlines
    deadlines = db.query(TaxDeadline).filter(
        TaxDeadline.due_date >= today,
        TaxDeadline.year == year
    ).all()

    total_remaining = sum(d.remaining for d in deadlines)

    if not deadlines:
        return Decimal("0.00")

    # Calculate months until last deadline
    last_deadline = max(d.due_date for d in deadlines)
    months_remaining = (
        (last_deadline.year - today.year) * 12
        + (last_deadline.month - today.month)
    )

    if months_remaining <= 0:
        return total_remaining

    return (total_remaining / Decimal(months_remaining)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def get_tax_coverage(db: Session) -> TaxCoverage:
    """
    Get tax coverage status for dashboard.
    Shows how much is accrued vs how much is owed.
    """
    today = date.today()

    # Get P3 pillar balance
    p3 = db.query(Pillar).filter(Pillar.number == 3).first()
    accrued = p3.current_balance if p3 else Decimal("0.00")

    # Get upcoming deadlines
    deadlines = db.query(TaxDeadline).filter(
        TaxDeadline.due_date >= today
    ).order_by(TaxDeadline.due_date).all()

    total_owed = sum(d.remaining for d in deadlines)
    coverage = (accrued / total_owed * 100) if total_owed > 0 else 100
    shortfall = max(Decimal("0.00"), total_owed - accrued)
    surplus = max(Decimal("0.00"), accrued - total_owed)
    next_deadline = deadlines[0] if deadlines else None

    # Monthly reserve calculation
    if deadlines:
        months_to_last = max(1, (
            (max(d.due_date for d in deadlines).year - today.year) * 12
            + (max(d.due_date for d in deadlines).month - today.month)
        ))
        monthly_reserve = (shortfall / Decimal(months_to_last)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ) if shortfall > 0 else Decimal("0.00")
    else:
        monthly_reserve = Decimal("0.00")

    return TaxCoverage(
        accrued=accrued,
        total_owed=total_owed,
        coverage_percentage=float(coverage),
        shortfall=shortfall,
        surplus=surplus,
        next_deadline=next_deadline,
        monthly_reserve_needed=monthly_reserve,
    )


def update_tax_deadline(
    db: Session,
    deadline_id: int,
    amount_due: Decimal = None,
    amount_paid: Decimal = None,
    due_date: date = None,
    notes: str = None
) -> TaxDeadline:
    """
    Manually update a tax deadline (override calculated values).
    """
    deadline = db.query(TaxDeadline).filter(TaxDeadline.id == deadline_id).first()
    if not deadline:
        raise ValueError(f"Tax deadline {deadline_id} not found")

    if amount_due is not None:
        deadline.amount_due = amount_due
        deadline.is_manual_override = True

    if amount_paid is not None:
        deadline.amount_paid = amount_paid

    if due_date is not None:
        deadline.due_date = due_date
        deadline.is_manual_override = True

    if notes is not None:
        deadline.notes = notes

    db.commit()
    return deadline


def record_tax_payment(
    db: Session,
    deadline_id: int,
    amount: Decimal,
    installment_number: int = None
) -> TaxDeadline:
    """Record a payment against a tax deadline."""
    deadline = db.query(TaxDeadline).filter(TaxDeadline.id == deadline_id).first()
    if not deadline:
        raise ValueError(f"Tax deadline {deadline_id} not found")

    deadline.amount_paid += amount
    if installment_number:
        deadline.installments_paid = installment_number

    db.commit()
    return deadline
