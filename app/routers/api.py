"""API endpoints for Contaspiccioli."""
from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import extract

from app.database import get_db
from app.models import Transaction, Category, Pillar, TaxDeadline
from app.services import budget

router = APIRouter(prefix="/api", tags=["api"])


# ============ Pydantic Models ============

class CategoryCreate(BaseModel):
    name: str
    type: str = "variabile"
    monthly_budget: float = 0.0
    icon: str = ""


class CategoryResponse(BaseModel):
    id: int
    name: str
    type: str
    monthly_budget: float
    icon: str
    is_active: bool

    class Config:
        from_attributes = True


class TransactionCreate(BaseModel):
    date: date
    amount: float
    description: str = ""
    category_id: Optional[int] = None
    pillar: str = "corrente"
    is_income: bool = False


class TransactionResponse(BaseModel):
    id: int
    date: date
    amount: float
    description: str
    category_id: Optional[int]
    pillar: str
    is_income: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PillarReconcile(BaseModel):
    actual_balance: float


class PillarResponse(BaseModel):
    id: int
    name: str
    display_name: str
    target_balance: float
    actual_balance: float
    monthly_contribution: float
    percentage: float
    last_reconciled: Optional[datetime]

    class Config:
        from_attributes = True


class DeadlinePayment(BaseModel):
    amount: float


# ============ Categories ============

@router.get("/categories", response_model=List[CategoryResponse])
def list_categories(db: Session = Depends(get_db)):
    """List all active categories."""
    return db.query(Category).filter(Category.is_active == True).all()


@router.post("/categories", response_model=CategoryResponse)
def create_category(data: CategoryCreate, db: Session = Depends(get_db)):
    """Create a new category."""
    category = Category(**data.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.put("/categories/{category_id}", response_model=CategoryResponse)
def update_category(category_id: int, data: CategoryCreate, db: Session = Depends(get_db)):
    """Update an existing category."""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    for key, value in data.model_dump().items():
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
    return {"status": "deleted"}


# ============ Transactions ============

@router.get("/transactions", response_model=List[TransactionResponse])
def list_transactions(
    year: int = Query(default=None),
    month: int = Query(default=None),
    category_id: int = Query(default=None),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db)
):
    """List transactions with optional filters."""
    query = db.query(Transaction)

    if year:
        query = query.filter(extract('year', Transaction.date) == year)
    if month:
        query = query.filter(extract('month', Transaction.date) == month)
    if category_id:
        query = query.filter(Transaction.category_id == category_id)

    return query.order_by(Transaction.date.desc()).limit(limit).all()


@router.post("/transactions", response_model=TransactionResponse)
def create_transaction(data: TransactionCreate, db: Session = Depends(get_db)):
    """Create a new transaction."""
    transaction = Transaction(**data.model_dump())
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


@router.put("/transactions/{transaction_id}", response_model=TransactionResponse)
def update_transaction(transaction_id: int, data: TransactionCreate, db: Session = Depends(get_db)):
    """Update an existing transaction."""
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    for key, value in data.model_dump().items():
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
    return {"status": "deleted"}


# ============ Pillars ============

@router.get("/pillars", response_model=List[PillarResponse])
def list_pillars(db: Session = Depends(get_db)):
    """List all financial pillars."""
    return db.query(Pillar).all()


@router.put("/pillars/{pillar_id}/reconcile", response_model=PillarResponse)
def reconcile_pillar(pillar_id: int, data: PillarReconcile, db: Session = Depends(get_db)):
    """Update actual balance for a pillar (reconciliation)."""
    pillar = db.query(Pillar).filter(Pillar.id == pillar_id).first()
    if not pillar:
        raise HTTPException(status_code=404, detail="Pillar not found")

    pillar.actual_balance = data.actual_balance
    pillar.last_reconciled = datetime.utcnow()
    db.commit()
    db.refresh(pillar)
    return pillar


# ============ Budget ============

@router.get("/budget/summary")
def get_budget_summary(
    year: int = Query(default=None),
    month: int = Query(default=None),
    db: Session = Depends(get_db)
):
    """Get budget summary for a specific month."""
    if not year:
        year = date.today().year
    if not month:
        month = date.today().month

    return budget.get_monthly_summary(db, year, month)


@router.get("/budget/pillars")
def get_pillars_summary(db: Session = Depends(get_db)):
    """Get summary of all financial pillars."""
    return budget.get_pillar_summary(db)


@router.get("/budget/forecast")
def get_yearly_forecast(year: int = Query(default=None), db: Session = Depends(get_db)):
    """Get yearly forecast."""
    if not year:
        year = date.today().year
    return budget.get_yearly_forecast(db, year)


@router.get("/budget/tax-calculation")
def calculate_taxes(gross_income: float = Query(...)):
    """Calculate tax obligations for a given gross income."""
    return budget.calculate_tax_obligations(gross_income)


# ============ Tax Deadlines ============

@router.get("/deadlines")
def list_deadlines(db: Session = Depends(get_db)):
    """List all tax deadlines."""
    deadlines = db.query(TaxDeadline).order_by(TaxDeadline.due_date).all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "due_date": d.due_date,
            "amount": d.amount,
            "paid": d.paid,
            "residuo": d.residuo,
            "is_paid": d.is_paid,
            "days_remaining": (d.due_date - date.today()).days
        }
        for d in deadlines
    ]


@router.put("/deadlines/{deadline_id}/pay")
def pay_deadline(deadline_id: int, data: DeadlinePayment, db: Session = Depends(get_db)):
    """Record a payment for a tax deadline."""
    deadline = db.query(TaxDeadline).filter(TaxDeadline.id == deadline_id).first()
    if not deadline:
        raise HTTPException(status_code=404, detail="Deadline not found")

    deadline.paid += data.amount
    db.commit()

    return {
        "id": deadline.id,
        "name": deadline.name,
        "paid": deadline.paid,
        "residuo": deadline.residuo,
        "is_paid": deadline.is_paid
    }
