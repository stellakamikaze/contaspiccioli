"""Bank import service v2 - Parse CSV and auto-categorize transactions."""
import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from app.models_v2 import Transaction, Category, TransactionSource


class BankFormat(str, Enum):
    """Supported bank statement formats."""
    GENERIC = "generic"      # Date, Description, Amount columns
    INTESA = "intesa"        # Intesa Sanpaolo
    FINECO = "fineco"        # Fineco Bank
    N26 = "n26"              # N26
    REVOLUT = "revolut"      # Revolut


@dataclass
class RawTransaction:
    """Raw transaction parsed from CSV before categorization."""
    date: date
    amount: Decimal
    description: str
    original_description: str


@dataclass
class ImportResult:
    """Result of importing a bank statement."""
    total_rows: int
    imported: int
    skipped: int
    errors: list[str]
    transactions: list[Transaction]
    uncategorized_count: int


def parse_italian_date(date_str: str) -> Optional[date]:
    """Parse date in Italian formats (DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD)."""
    date_str = date_str.strip()
    formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%d/%m/%y",
        "%d.%m.%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def parse_amount(amount_str: str) -> Optional[Decimal]:
    """Parse amount handling Italian/European number formats."""
    if not amount_str:
        return None

    # Clean the string
    amount_str = amount_str.strip()

    # Remove currency symbols
    amount_str = re.sub(r'[€$£]', '', amount_str).strip()

    # Handle European format: 1.234,56 → 1234.56
    if ',' in amount_str and '.' in amount_str:
        # Check which is the decimal separator (the rightmost one)
        last_comma = amount_str.rfind(',')
        last_dot = amount_str.rfind('.')
        if last_comma > last_dot:
            # European: dots are thousands, comma is decimal
            amount_str = amount_str.replace('.', '').replace(',', '.')
        else:
            # US: commas are thousands, dot is decimal
            amount_str = amount_str.replace(',', '')
    elif ',' in amount_str:
        # Only comma - assume it's decimal separator
        amount_str = amount_str.replace(',', '.')

    try:
        return Decimal(amount_str)
    except InvalidOperation:
        return None


def parse_bank_statement(
    content: str,
    bank_format: BankFormat = BankFormat.GENERIC
) -> list[RawTransaction]:
    """
    Parse CSV bank statement into raw transactions.

    Supports multiple bank formats with auto-detection.
    """
    transactions = []

    # Try to detect encoding and parse
    reader = csv.DictReader(io.StringIO(content), delimiter=detect_delimiter(content))

    # Get column mappings based on format
    date_col, desc_col, amount_col, income_col = get_column_mapping(bank_format, reader.fieldnames)

    for row in reader:
        try:
            # Parse date
            date_value = parse_italian_date(row.get(date_col, ''))
            if not date_value:
                continue

            # Parse description
            description = row.get(desc_col, '').strip()
            if not description:
                continue

            # Parse amount
            amount_str = row.get(amount_col, '')
            amount = parse_amount(amount_str)

            # Some formats have separate income/expense columns
            if amount is None and income_col:
                income_str = row.get(income_col, '')
                expense_str = row.get(amount_col, '')
                income = parse_amount(income_str) if income_str else Decimal("0")
                expense = parse_amount(expense_str) if expense_str else Decimal("0")
                amount = income - expense if income else -expense

            if amount is None:
                continue

            transactions.append(RawTransaction(
                date=date_value,
                amount=amount,
                description=clean_description(description),
                original_description=description,
            ))

        except (KeyError, ValueError):
            continue

    return transactions


def detect_delimiter(content: str) -> str:
    """Detect CSV delimiter (comma, semicolon, tab)."""
    first_line = content.split('\n')[0]
    if ';' in first_line:
        return ';'
    if '\t' in first_line:
        return '\t'
    return ','


def get_column_mapping(
    bank_format: BankFormat,
    fieldnames: list[str]
) -> tuple[str, str, str, Optional[str]]:
    """Get column names for date, description, amount based on bank format."""
    if fieldnames is None:
        fieldnames = []

    # Normalize field names for comparison
    normalized = {f.lower().strip(): f for f in fieldnames}

    # Common mappings to try
    date_candidates = ['data', 'date', 'data operazione', 'data valuta', 'data contabile']
    desc_candidates = ['descrizione', 'description', 'causale', 'descrizione operazione', 'dettagli']
    amount_candidates = ['importo', 'amount', 'dare/avere', 'importo eur', 'uscite', 'entrate']

    date_col = None
    desc_col = None
    amount_col = None
    income_col = None

    for candidate in date_candidates:
        if candidate in normalized:
            date_col = normalized[candidate]
            break

    for candidate in desc_candidates:
        if candidate in normalized:
            desc_col = normalized[candidate]
            break

    for candidate in amount_candidates:
        if candidate in normalized:
            amount_col = normalized[candidate]
            break

    # Check for separate income/expense columns
    if 'entrate' in normalized and 'uscite' in normalized:
        income_col = normalized['entrate']
        amount_col = normalized['uscite']

    # Fallback to first three columns
    if date_col is None and len(fieldnames) > 0:
        date_col = fieldnames[0]
    if desc_col is None and len(fieldnames) > 1:
        desc_col = fieldnames[1]
    if amount_col is None and len(fieldnames) > 2:
        amount_col = fieldnames[2]

    return date_col, desc_col, amount_col, income_col


def clean_description(description: str) -> str:
    """Clean transaction description for display."""
    # Remove excessive whitespace
    description = ' '.join(description.split())

    # Remove common prefixes
    prefixes_to_remove = [
        'PAGAMENTO POS ',
        'ADDEBITO SDD ',
        'BONIFICO ',
        'ACCREDITO ',
    ]
    for prefix in prefixes_to_remove:
        if description.upper().startswith(prefix):
            description = description[len(prefix):]

    return description.strip()


def categorize_transaction(
    db: Session,
    description: str
) -> Optional[Category]:
    """
    Find matching category based on keywords.
    Returns None if no match found (uncategorized).
    """
    description_upper = description.upper()

    # Get all categories with keywords
    categories = db.query(Category).filter(
        Category.is_active == True
    ).all()

    best_match = None
    best_score = 0

    for category in categories:
        if not category.keywords:
            continue

        for keyword in category.keywords:
            if keyword.upper() in description_upper:
                # Simple scoring: longer keyword = better match
                score = len(keyword)
                if score > best_score:
                    best_score = score
                    best_match = category

    return best_match


def categorize_transactions(
    db: Session,
    raw_transactions: list[RawTransaction]
) -> list[Transaction]:
    """
    Categorize a list of raw transactions.
    Uses keywords to auto-assign categories.
    """
    transactions = []

    for raw in raw_transactions:
        category = categorize_transaction(db, raw.original_description)

        # Determine if income or expense
        is_income = raw.amount > 0

        tx = Transaction(
            date=raw.date,
            amount=raw.amount,
            description=raw.description,
            original_description=raw.original_description,
            category_id=category.id if category else None,
            source=TransactionSource.BANK_IMPORT,
            is_income=is_income,
            is_taxable=is_income,  # Assume income is taxable by default
        )
        transactions.append(tx)

    return transactions


def import_bank_statement(
    db: Session,
    content: str,
    year: int,
    month: int,
    bank_format: BankFormat = BankFormat.GENERIC
) -> ImportResult:
    """
    Full import pipeline:
    1. Parse CSV
    2. Filter to specified month
    3. Categorize
    4. Save to database
    5. Return summary
    """
    errors = []

    # Parse CSV
    try:
        raw_transactions = parse_bank_statement(content, bank_format)
    except Exception as e:
        return ImportResult(
            total_rows=0,
            imported=0,
            skipped=0,
            errors=[f"Failed to parse CSV: {str(e)}"],
            transactions=[],
            uncategorized_count=0,
        )

    if not raw_transactions:
        return ImportResult(
            total_rows=0,
            imported=0,
            skipped=0,
            errors=["No transactions found in CSV"],
            transactions=[],
            uncategorized_count=0,
        )

    total_rows = len(raw_transactions)

    # Filter to specified month
    filtered = [
        tx for tx in raw_transactions
        if tx.date.year == year and tx.date.month == month
    ]
    skipped = total_rows - len(filtered)

    if not filtered:
        return ImportResult(
            total_rows=total_rows,
            imported=0,
            skipped=skipped,
            errors=[f"No transactions found for {month}/{year}"],
            transactions=[],
            uncategorized_count=0,
        )

    # Categorize
    transactions = categorize_transactions(db, filtered)

    # Check for duplicates before saving
    imported = []
    for tx in transactions:
        # Simple duplicate check: same date, amount, description
        existing = db.query(Transaction).filter(
            Transaction.date == tx.date,
            Transaction.amount == tx.amount,
            Transaction.original_description == tx.original_description,
        ).first()

        if existing:
            skipped += 1
            continue

        db.add(tx)
        imported.append(tx)

    db.commit()

    # Refresh to get IDs
    for tx in imported:
        db.refresh(tx)

    uncategorized = sum(1 for tx in imported if tx.category_id is None)

    return ImportResult(
        total_rows=total_rows,
        imported=len(imported),
        skipped=skipped,
        errors=errors,
        transactions=imported,
        uncategorized_count=uncategorized,
    )


def learn_keyword(
    db: Session,
    transaction_id: int,
    category_id: int
) -> Category:
    """
    Learn from manual categorization.
    Extracts keywords from transaction description and adds to category.
    """
    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not tx:
        raise ValueError(f"Transaction {transaction_id} not found")

    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise ValueError(f"Category {category_id} not found")

    # Update transaction category
    tx.category_id = category_id

    # Extract potential keyword from original description
    # Use the longest word that's not too common
    words = tx.original_description.upper().split()
    common_words = {'IL', 'LA', 'DI', 'DA', 'IN', 'PER', 'CON', 'SU', 'TRA', 'FRA',
                    'PAGAMENTO', 'BONIFICO', 'ADDEBITO', 'ACCREDITO', 'EUR', 'SRL', 'SPA'}

    candidate_keywords = [
        w for w in words
        if len(w) >= 4 and w not in common_words and w.isalpha()
    ]

    if candidate_keywords:
        # Take the longest word as keyword
        new_keyword = max(candidate_keywords, key=len)

        # Add to category if not already present
        current_keywords = category.keywords or []
        if new_keyword not in current_keywords:
            current_keywords.append(new_keyword)
            category.keywords = current_keywords

    db.commit()
    return category


def get_uncategorized_transactions(
    db: Session,
    year: int = None,
    month: int = None
) -> list[Transaction]:
    """Get transactions without a category for manual review."""
    query = db.query(Transaction).filter(
        Transaction.category_id == None
    )

    if year:
        if month:
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1)
            else:
                end_date = date(year, month + 1, 1)
            query = query.filter(
                Transaction.date >= start_date,
                Transaction.date < end_date
            )
        else:
            query = query.filter(
                Transaction.date >= date(year, 1, 1),
                Transaction.date < date(year + 1, 1, 1)
            )

    return query.order_by(Transaction.date.desc()).all()
