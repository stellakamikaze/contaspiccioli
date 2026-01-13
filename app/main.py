"""Main FastAPI application for Contaspiccioli."""
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Optional

from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import init_db, get_db, SessionLocal
from app.routers import api
from app.seed import seed_all as seed_data
from app.utils import format_currency, format_percentage, format_date, month_name

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    logger.info("Starting Contaspiccioli...")
    init_db()

    # Seed default data
    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()

    yield
    logger.info("Shutting down Contaspiccioli...")


app = FastAPI(
    title="Contaspiccioli",
    description="Cash Flow Planner - 4 Pilastri",
    version="2.0.0",
    lifespan=lifespan
)

# Mount static files
app.mount("/static", StaticFiles(directory=settings.base_dir / "static"), name="static")

# Setup templates
templates = Jinja2Templates(directory=settings.base_dir / "templates")

# Register template filters
templates.env.filters["currency"] = format_currency
templates.env.filters["percentage"] = format_percentage
templates.env.filters["date"] = format_date

# Include API router
app.include_router(api.router)


# ============ HTML Routes ============

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Dashboard with 4 pillars and cash flow projection."""
    from app.services.pillars import get_pillar_summary
    from app.services.forecast import project_balance, get_forecast_comparison
    from app.models import TaxDeadline, UserSettings

    today = date.today()

    # Get pillars summary
    pillars_summary = get_pillar_summary(db)

    # Get balance projection for next 6 months
    projections = project_balance(db, months_ahead=6)

    # Get monthly comparison (current month budget vs actual)
    comparison = get_forecast_comparison(db, today.year, today.month)
    budget_comparison = None
    if comparison:
        # Build comparison data for template
        all_costs = []
        for c in (comparison.fixed_costs or []):
            all_costs.append({
                'name': c.category_name,
                'icon': c.category_icon,
                'expected': float(c.expected),
                'actual': float(c.actual),
                'variance': float(c.variance),
                'is_over': c.is_over_budget,
                'type': 'fixed',
            })
        for c in (comparison.variable_costs or []):
            all_costs.append({
                'name': c.category_name,
                'icon': c.category_icon,
                'expected': float(c.expected),
                'actual': float(c.actual),
                'variance': float(c.variance),
                'is_over': c.is_over_budget,
                'type': 'variable',
            })
        budget_comparison = {
            'income': {
                'expected': float(comparison.income.expected) if comparison.income else 0,
                'actual': float(comparison.income.actual) if comparison.income else 0,
                'variance': float(comparison.income.variance) if comparison.income else 0,
            },
            'costs': all_costs,
            'total_expected': float(comparison.total_expected_costs),
            'total_actual': float(comparison.total_actual_costs),
            'expected_balance': float(comparison.expected_balance),
            'actual_balance': float(comparison.actual_balance),
        }

    # Get upcoming tax deadlines
    deadlines_query = db.query(TaxDeadline).filter(
        TaxDeadline.due_date >= today
    ).order_by(TaxDeadline.due_date).limit(3).all()

    deadlines = []
    for d in deadlines_query:
        deadlines.append({
            'name': d.name,
            'due_date': d.due_date,
            'amount_due': d.amount_due,
            'amount_paid': d.amount_paid,
            'remaining': d.remaining,
            'days_remaining': (d.due_date - today).days,
        })

    # Get user settings
    user_settings = db.query(UserSettings).first()
    monthly_income = user_settings.monthly_income if user_settings else 3500

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "pillars": pillars_summary['pillars'],
        "total_balance": pillars_summary['total_balance'],
        "total_target": pillars_summary['total_target'],
        "overall_completion": pillars_summary['overall_completion'],
        "projections": projections,
        "deadlines": deadlines,
        "monthly_income": monthly_income,
        "month_name": month_name(today.month),
        "year": today.year,
        "comparison": budget_comparison,
    })


@app.get("/cashflow", response_class=HTMLResponse)
async def cashflow(request: Request, year: Optional[int] = None, db: Session = Depends(get_db)):
    """Cash Flow spreadsheet view (Sibill-style)."""
    from app.services.forecast import MONTH_NAMES
    from app.routers.api import get_cashflow_spreadsheet

    today = date.today()
    if not year:
        year = today.year

    # Fetch data from API endpoint
    data = get_cashflow_spreadsheet(year, db)

    return templates.TemplateResponse("cashflow.html", {
        "request": request,
        "year": year,
        "months": data["months"],
        "sections": data["sections"],
        "budget": data["budget"],
        "opening_balance": data["opening_balance"],
        "current_month": today.month,
    })


@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    """About/Landing page explaining the app."""
    return templates.TemplateResponse("about.html", {"request": request})


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
