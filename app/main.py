"""Main FastAPI application for Contaspiccioli."""
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Optional

from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import init_db, get_db, SessionLocal
from app.models import Category, Transaction, Pillar, TaxDeadline, UserProfile, MonthlyIncome
from app.routers import api
from app.services import budget
from app.utils import format_currency, format_percentage, format_date, month_name

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_default_data(db: Session):
    """Seed default categories, pillars, and tax deadlines."""
    # Check if already seeded
    if db.query(Category).count() > 0:
        return

    logger.info("Seeding default data...")

    # Default categories - Fixed
    fixed_categories = [
        ("Affitto", 700, "fissa"),
        ("Palestra", 35, "fissa"),
        ("Commercialista", 25, "fissa"),
    ]

    # Default categories - Variable
    variable_categories = [
        ("Spesa alimentare", 200, "variabile"),
        ("Trasporti", 40, "variabile"),
        ("Servizi Digitali", 15, "variabile"),
        ("Ristoranti", 290, "variabile"),
        ("Cultura", 35, "variabile"),
        ("Shopping", 230, "variabile"),
        ("Salute", 380, "variabile"),
        ("Contanti", 100, "variabile"),
    ]

    icons = {
        "Affitto": "", "Palestra": "", "Commercialista": "",
        "Spesa alimentare": "", "Trasporti": "", "Servizi Digitali": "",
        "Ristoranti": "", "Cultura": "", "Shopping": "",
        "Salute": "", "Contanti": ""
    }

    for name, budget_amount, cat_type in fixed_categories + variable_categories:
        cat = Category(
            name=name,
            type=cat_type,
            monthly_budget=budget_amount,
            icon=icons.get(name, "")
        )
        db.add(cat)

    # Income category
    db.add(Category(name="Stipendio/Fatture", type="entrata", monthly_budget=0, icon=""))

    # Default pillars
    pillars = [
        ("emergenza", "XEON Emergenza (2)", 10000, 0, 0),
        ("tasse", "XEON Tasse (3)", 3000, settings.default_income * settings.tax_percentage, settings.tax_percentage),
        ("investimenti", "ETF Investimenti (4)", 0, settings.default_income * settings.investment_percentage, settings.investment_percentage),
    ]

    for name, display, target, contrib, pct in pillars:
        pillar = Pillar(
            name=name,
            display_name=display,
            target_balance=target,
            actual_balance=target,
            monthly_contribution=contrib,
            percentage=pct
        )
        db.add(pillar)

    # Tax deadlines 2026
    deadlines = [
        ("Saldo + 1 acconto 2025", date(2026, 6, 30), 7527),
        ("2 acconto 2025", date(2026, 11, 30), 5460),
    ]

    for name, due, amount in deadlines:
        deadline = TaxDeadline(name=name, due_date=due, amount=amount)
        db.add(deadline)

    db.commit()
    logger.info("Default data seeded successfully")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    logger.info("Starting Contaspiccioli...")
    init_db()

    # Seed default data
    db = SessionLocal()
    try:
        seed_default_data(db)
    finally:
        db.close()

    yield
    logger.info("Shutting down Contaspiccioli...")


app = FastAPI(
    title="Contaspiccioli",
    description="Personal Finance Manager",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static files
app.mount("/static", StaticFiles(directory=settings.base_dir / "static"), name="static")

# Setup templates
templates = Jinja2Templates(directory=settings.base_dir / "templates")


# Register template filters (imported from utils.py)
templates.env.filters["currency"] = format_currency
templates.env.filters["percentage"] = format_percentage
templates.env.filters["date"] = format_date

# Include API router
app.include_router(api.router)


# ============ Helper Functions ============

def get_or_create_profile(db: Session) -> UserProfile:
    """Get existing profile or create a new one."""
    profile = db.query(UserProfile).first()
    if not profile:
        profile = UserProfile()
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


# ============ HTML Routes ============

@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, step: int = 1, db: Session = Depends(get_db)):
    """Onboarding wizard."""
    profile = get_or_create_profile(db)
    return templates.TemplateResponse("onboarding.html", {
        "request": request,
        "step": min(max(step, 1), 5),
        "profile": profile
    })


@app.post("/setup")
async def setup_submit(
    request: Request,
    step: int = Form(...),
    # Step 1
    monthly_income: Optional[float] = Form(None),
    income_type: Optional[str] = Form(None),
    income_is_fixed: Optional[str] = Form(None),
    # Step 2
    rent: Optional[float] = Form(None),
    subscriptions: Optional[float] = Form(None),
    other_fixed: Optional[float] = Form(None),
    # Step 3
    food_budget: Optional[float] = Form(None),
    restaurants_budget: Optional[float] = Form(None),
    transport_budget: Optional[float] = Form(None),
    shopping_budget: Optional[float] = Form(None),
    # Step 4
    emergency_target: Optional[float] = Form(None),
    tax_percentage: Optional[float] = Form(None),
    investment_percentage: Optional[float] = Form(None),
    # Step 5
    current_balance: Optional[float] = Form(None),
    emergency_balance: Optional[float] = Form(None),
    tax_balance: Optional[float] = Form(None),
    investment_balance: Optional[float] = Form(None),
    taxes_paid_ytd: Optional[float] = Form(None),
    prior_year_tax_advance: Optional[float] = Form(None),
    db: Session = Depends(get_db)
):
    """Handle onboarding form submissions."""
    profile = get_or_create_profile(db)

    if step == 1:
        if monthly_income is not None:
            profile.monthly_income = monthly_income
        if income_type:
            profile.income_type = income_type
        profile.income_is_fixed = income_is_fixed == "true"
        profile.setup_step = 2

    elif step == 2:
        if rent is not None:
            profile.rent = rent
        if subscriptions is not None:
            profile.subscriptions = subscriptions
        if other_fixed is not None:
            profile.other_fixed = other_fixed
        profile.setup_step = 3

    elif step == 3:
        if food_budget is not None:
            profile.food_budget = food_budget
        if restaurants_budget is not None:
            profile.restaurants_budget = restaurants_budget
        if transport_budget is not None:
            profile.transport_budget = transport_budget
        if shopping_budget is not None:
            profile.shopping_budget = shopping_budget
        profile.setup_step = 4

    elif step == 4:
        if emergency_target is not None:
            profile.emergency_target = emergency_target
        if tax_percentage is not None:
            profile.tax_percentage = tax_percentage / 100  # Convert from % to decimal
        if investment_percentage is not None:
            profile.investment_percentage = investment_percentage / 100
        profile.setup_step = 5

    elif step == 5:
        if current_balance is not None:
            profile.current_balance = current_balance
        if emergency_balance is not None:
            profile.emergency_balance = emergency_balance
        if tax_balance is not None:
            profile.tax_balance = tax_balance
        if investment_balance is not None:
            profile.investment_balance = investment_balance
        if taxes_paid_ytd is not None:
            profile.taxes_paid_ytd = taxes_paid_ytd
        if prior_year_tax_advance is not None:
            profile.prior_year_tax_advance = prior_year_tax_advance
        profile.setup_completed = True

        # Update pillars with profile data
        _update_pillars_from_profile(db, profile)

    db.commit()

    if step < 5:
        return RedirectResponse(url=f"/setup?step={step + 1}", status_code=303)
    else:
        return RedirectResponse(url="/summary", status_code=303)


def _update_pillars_from_profile(db: Session, profile: UserProfile):
    """Update pillar settings based on user profile."""
    # Single query for all pillars
    pillars = db.query(Pillar).filter(
        Pillar.name.in_(["emergenza", "tasse", "investimenti"])
    ).all()
    pillar_map = {p.name: p for p in pillars}

    # Update emergency pillar
    if "emergenza" in pillar_map:
        pillar_map["emergenza"].target_balance = profile.emergency_target
        pillar_map["emergenza"].actual_balance = profile.emergency_balance

    # Update tax pillar
    if "tasse" in pillar_map:
        pillar_map["tasse"].percentage = profile.tax_percentage
        pillar_map["tasse"].monthly_contribution = profile.monthly_income * profile.tax_percentage
        pillar_map["tasse"].actual_balance = profile.tax_balance

    # Update investment pillar
    if "investimenti" in pillar_map:
        pillar_map["investimenti"].percentage = profile.investment_percentage
        pillar_map["investimenti"].monthly_contribution = profile.monthly_income * profile.investment_percentage
        pillar_map["investimenti"].actual_balance = profile.investment_balance

    db.commit()


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Main dashboard page."""
    # Check if setup is completed
    profile = get_or_create_profile(db)
    if not profile.setup_completed:
        return RedirectResponse(url=f"/setup?step={profile.setup_step}", status_code=303)

    today = date.today()
    summary = budget.get_monthly_summary(db, today.year, today.month)
    pillars = budget.get_pillar_summary(db)

    # Get upcoming deadlines
    deadlines = db.query(TaxDeadline).filter(
        TaxDeadline.due_date >= today
    ).order_by(TaxDeadline.due_date).limit(2).all()

    deadline_info = []
    for d in deadlines:
        days = (d.due_date - today).days
        deadline_info.append({
            "name": d.name,
            "due_date": d.due_date,
            "amount": d.amount,
            "paid": d.paid,
            "residuo": d.residuo,
            "days_remaining": days,
            "urgent": days <= 7
        })

    # Get monthly incomes for this month
    monthly_incomes = db.query(MonthlyIncome).filter(
        MonthlyIncome.year == today.year,
        MonthlyIncome.month == today.month
    ).all()

    total_income = sum(i.amount for i in monthly_incomes) if monthly_incomes else profile.monthly_income

    # Calculate allocations
    allocations = {
        'fixed': profile.total_fixed_expenses,
        'variable': profile.total_variable_budget,
        'tax': total_income * profile.tax_percentage,
        'investment': total_income * profile.investment_percentage,
    }

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "profile": profile,
        "summary": summary,
        "pillars": pillars,
        "deadlines": deadline_info,
        "month_name": month_name(today.month),
        "month": today.month,
        "year": today.year,
        "monthly_incomes": monthly_incomes,
        "total_income": total_income,
        "allocations": allocations
    })


@app.post("/income/add")
async def add_income(
    request: Request,
    source: str = Form(...),
    amount: float = Form(...),
    is_received: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Add monthly income entry."""
    today = date.today()
    income = MonthlyIncome(
        year=today.year,
        month=today.month,
        source=source,
        amount=amount,
        is_received=is_received == "true",
        received_date=today if is_received == "true" else None
    )
    db.add(income)
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/update-monthly-payment")
async def update_monthly_payment(
    request: Request,
    payment_type: str = Form(...),
    year: int = Form(...),
    month: int = Form(...),
    paid: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Update monthly payment checkbox (tax or investment)."""
    profile = get_or_create_profile(db)

    # Checkbox is checked if 'paid' is present in form data
    is_paid = paid is not None

    if payment_type == "tax":
        profile.tax_paid_this_month = is_paid
    elif payment_type == "investment":
        profile.investment_paid_this_month = is_paid

    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.get("/summary", response_class=HTMLResponse)
async def annual_summary(request: Request, year: Optional[int] = None, db: Session = Depends(get_db)):
    """Annual summary with horizontal calendar."""
    profile = get_or_create_profile(db)
    today = date.today()
    if not year:
        year = today.year

    # Get tax deadlines for the year
    deadlines = db.query(TaxDeadline).filter(
        TaxDeadline.due_date >= date(year, 1, 1),
        TaxDeadline.due_date <= date(year, 12, 31)
    ).order_by(TaxDeadline.due_date).all()

    # Build calendar data
    calendar = []
    tax_balance = profile.tax_balance
    investment_balance = profile.investment_balance
    current_balance = profile.current_balance
    emergency_balance = profile.emergency_balance

    for month in range(1, 13):
        month_income = profile.monthly_income
        tax_allocation = month_income * profile.tax_percentage
        investment_allocation = month_income * profile.investment_percentage
        fixed = profile.total_fixed_expenses
        variable = profile.total_variable_budget

        # Check for tax payments this month
        tax_payment = 0
        for d in deadlines:
            if d.due_date.month == month and d.due_date.year == year:
                tax_payment += d.residuo

        # Available after allocations
        available = month_income - fixed - tax_allocation - investment_allocation

        # Update running balances
        tax_balance += tax_allocation - tax_payment
        investment_balance += investment_allocation

        # Emergency contribution if below target
        emergency_contrib = 0
        if emergency_balance < profile.emergency_target:
            emergency_contrib = min(available * 0.3, profile.emergency_target - emergency_balance)
            emergency_balance += emergency_contrib
            available -= emergency_contrib

        current_balance += available - variable

        calendar.append({
            'month': month,
            'name': month_name(month),
            'income': month_income,
            'has_extra': False,
            'tax_allocation': tax_allocation,
            'investment_allocation': investment_allocation,
            'available': month_income - fixed - tax_allocation - investment_allocation,
            'tax_payment': tax_payment,
        })

    # End of year balances
    end_balances = {
        'current': current_balance,
        'emergency': emergency_balance,
        'tax': tax_balance,
        'investment': investment_balance,
    }

    return templates.TemplateResponse("annual_summary.html", {
        "request": request,
        "profile": profile,
        "year": year,
        "calendar": calendar,
        "deadlines": deadlines,
        "end_balances": end_balances,
    })


@app.get("/transactions", response_class=HTMLResponse)
async def transactions_page(
    request: Request,
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Transactions list page."""
    today = date.today()
    if not year:
        year = today.year
    if not month:
        month = today.month

    transactions = db.query(Transaction).filter(
        Transaction.date >= date(year, month, 1)
    ).order_by(Transaction.date.desc()).all()

    categories = db.query(Category).filter(Category.is_active == True).all()

    return templates.TemplateResponse("transactions.html", {
        "request": request,
        "transactions": transactions,
        "categories": categories,
        "year": year,
        "month": month,
        "month_name": month_name(month)
    })


@app.post("/transactions/add")
async def add_transaction_form(
    request: Request,
    date_str: str = Form(...),
    amount: float = Form(...),
    description: str = Form(""),
    category_id: int = Form(...),
    is_income: bool = Form(False),
    db: Session = Depends(get_db)
):
    """Add transaction from form."""
    trans_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    transaction = Transaction(
        date=trans_date,
        amount=amount,
        description=description,
        category_id=category_id if category_id > 0 else None,
        is_income=is_income
    )
    db.add(transaction)
    db.commit()

    return RedirectResponse(
        url=f"/transactions?year={trans_date.year}&month={trans_date.month}",
        status_code=303
    )


@app.get("/pillars", response_class=HTMLResponse)
async def pillars_page(request: Request, db: Session = Depends(get_db)):
    """Pillars management page."""
    pillars = budget.get_pillar_summary(db)

    return templates.TemplateResponse("pillars.html", {
        "request": request,
        "pillars": pillars
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    """Settings and categories page."""
    categories = db.query(Category).filter(Category.is_active == True).all()

    fixed_cats = [c for c in categories if c.type == "fissa"]
    variable_cats = [c for c in categories if c.type == "variabile"]

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "fixed_categories": fixed_cats,
        "variable_categories": variable_cats,
        "config": {
            "default_income": settings.default_income,
            "fixed_percentage": settings.fixed_percentage,
            "variable_percentage": settings.variable_percentage,
            "tax_percentage": settings.tax_percentage,
            "investment_percentage": settings.investment_percentage,
        }
    })


@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    """About/Landing page explaining the app."""
    return templates.TemplateResponse("about.html", {"request": request})


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


