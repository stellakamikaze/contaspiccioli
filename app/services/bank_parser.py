"""Bank statement parser service for expense analysis."""
import csv
import io
import re
from datetime import datetime
from typing import Dict, List, Tuple
from collections import defaultdict


# Category keywords for auto-classification
CATEGORY_KEYWORDS = {
    "Affitto": ["affitto", "rent", "locazione", "canone"],
    "Spesa alimentare": ["supermercato", "conad", "esselunga", "lidl", "eurospin", "coop", "carrefour", "pam", "despar", "penny", "aldi", "simply", "market"],
    "Ristoranti": ["ristorante", "pizzeria", "bar ", "caffe", "mcdonald", "burger", "sushi", "delivery", "just eat", "deliveroo", "glovo", "uber eats"],
    "Trasporti": ["treno", "trenitalia", "italo", "atm", "metro", "bus", "taxi", "uber", "bolt", "benzina", "eni", "q8", "ip ", "tamoil", "autostrada", "telepass"],
    "Salute": ["farmacia", "medico", "dottore", "ospedale", "dentista", "ottico", "palestra", "gym", "fitness"],
    "Shopping": ["amazon", "zalando", "h&m", "zara", "ikea", "decathlon", "mediaworld", "unieuro", "apple", "negozio"],
    "Servizi Digitali": ["netflix", "spotify", "disney", "prime", "cloud", "google", "apple", "microsoft", "adobe", "openai", "chatgpt"],
    "Utenze": ["enel", "eni gas", "a2a", "hera", "iren", "edison", "sorgenia", "tim", "vodafone", "wind", "iliad", "fastweb", "sky"],
    "Contanti": ["prelievo", "atm", "bancomat", "cash"],
}


def parse_bank_statement(content: str, file_type: str = "csv") -> List[Dict]:
    """
    Parse bank statement content and return list of transactions.

    Supports common Italian bank CSV formats.
    """
    transactions = []

    if file_type == "csv":
        transactions = _parse_csv(content)

    return transactions


def _parse_csv(content: str) -> List[Dict]:
    """Parse CSV bank statement."""
    transactions = []

    # Try different delimiters
    for delimiter in [";", ",", "\t"]:
        try:
            reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
            rows = list(reader)
            if rows and len(rows[0]) > 2:
                for row in rows:
                    trans = _parse_row(row)
                    if trans:
                        transactions.append(trans)
                break
        except:
            continue

    # If DictReader fails, try positional parsing
    if not transactions:
        transactions = _parse_csv_positional(content)

    return transactions


def _parse_csv_positional(content: str) -> List[Dict]:
    """Parse CSV by position when headers are missing or non-standard."""
    transactions = []
    lines = content.strip().split("\n")

    for line in lines[1:]:  # Skip header
        for delimiter in [";", ",", "\t"]:
            parts = line.split(delimiter)
            if len(parts) >= 3:
                trans = _extract_transaction(parts)
                if trans:
                    transactions.append(trans)
                    break

    return transactions


def _parse_row(row: Dict) -> Dict:
    """Parse a single row from CSV."""
    # Common column name variations
    date_cols = ["data", "date", "data operazione", "data contabile", "data valuta"]
    desc_cols = ["descrizione", "description", "causale", "movimento", "dettaglio"]
    amount_cols = ["importo", "amount", "dare", "avere", "entrate", "uscite", "movimento"]

    date_val = None
    desc_val = None
    amount_val = None

    row_lower = {k.lower().strip(): v for k, v in row.items()}

    for col in date_cols:
        if col in row_lower and row_lower[col]:
            date_val = _parse_date(row_lower[col])
            break

    for col in desc_cols:
        if col in row_lower and row_lower[col]:
            desc_val = row_lower[col].strip()
            break

    for col in amount_cols:
        if col in row_lower and row_lower[col]:
            amount_val = _parse_amount(row_lower[col])
            if amount_val != 0:
                break

    if date_val and amount_val:
        return {
            "date": date_val,
            "description": desc_val or "",
            "amount": abs(amount_val),
            "is_income": amount_val > 0,
            "category": _categorize(desc_val or ""),
        }

    return None


def _extract_transaction(parts: List[str]) -> Dict:
    """Extract transaction from positional CSV parts."""
    date_val = None
    amount_val = None
    desc_val = ""

    for part in parts:
        part = part.strip().strip('"')

        if not date_val:
            date_val = _parse_date(part)
            if date_val:
                continue

        if not amount_val:
            amount_val = _parse_amount(part)
            if amount_val != 0:
                continue

        if part and not part.replace("-", "").replace(".", "").replace(",", "").isdigit():
            desc_val = part if not desc_val else f"{desc_val} {part}"

    if date_val and amount_val:
        return {
            "date": date_val,
            "description": desc_val.strip(),
            "amount": abs(amount_val),
            "is_income": amount_val > 0,
            "category": _categorize(desc_val),
        }

    return None


def _parse_date(val: str) -> datetime:
    """Parse date from various formats."""
    val = val.strip()
    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y",
        "%d/%m/%y", "%d-%m-%y", "%Y/%m/%d"
    ]

    for fmt in formats:
        try:
            return datetime.strptime(val, fmt).date()
        except:
            continue

    return None


def _parse_amount(val: str) -> float:
    """Parse amount from various formats."""
    val = val.strip().strip('"')

    if not val:
        return 0

    # Handle Italian format (1.234,56) and US format (1,234.56)
    val = val.replace(" ", "").replace("€", "").replace("EUR", "")

    # Detect format
    if "," in val and "." in val:
        if val.rfind(",") > val.rfind("."):
            # Italian: 1.234,56
            val = val.replace(".", "").replace(",", ".")
        else:
            # US: 1,234.56
            val = val.replace(",", "")
    elif "," in val:
        # Could be Italian decimal or US thousands
        if len(val.split(",")[-1]) == 2:
            val = val.replace(",", ".")
        else:
            val = val.replace(",", "")

    try:
        return float(val)
    except:
        return 0


def _categorize(description: str) -> str:
    """Auto-categorize transaction based on description."""
    desc_lower = description.lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in desc_lower:
                return category

    return "Altro"


def analyze_spending(transactions: List[Dict]) -> Dict:
    """
    Analyze transactions and generate spending summary.

    Returns:
    - Total spending by category
    - Monthly averages
    - Suggested budgets
    """
    if not transactions:
        return {"error": "Nessuna transazione trovata"}

    # Filter expenses only
    expenses = [t for t in transactions if not t["is_income"]]
    incomes = [t for t in transactions if t["is_income"]]

    # Group by category
    by_category = defaultdict(list)
    for t in expenses:
        by_category[t["category"]].append(t)

    # Group by month
    by_month = defaultdict(list)
    for t in expenses:
        month_key = t["date"].strftime("%Y-%m")
        by_month[month_key].append(t)

    num_months = len(by_month) or 1

    # Calculate summaries
    category_summary = {}
    for cat, trans in by_category.items():
        total = sum(t["amount"] for t in trans)
        category_summary[cat] = {
            "total": total,
            "count": len(trans),
            "monthly_avg": total / num_months,
            "suggested_budget": round(total / num_months * 1.1, -1),  # +10% buffer, rounded
        }

    # Sort by total spending
    sorted_categories = sorted(
        category_summary.items(),
        key=lambda x: x[1]["total"],
        reverse=True
    )

    total_expenses = sum(t["amount"] for t in expenses)
    total_income = sum(t["amount"] for t in incomes)

    return {
        "period_months": num_months,
        "total_expenses": total_expenses,
        "total_income": total_income,
        "monthly_avg_expenses": total_expenses / num_months,
        "monthly_avg_income": total_income / num_months if incomes else 0,
        "categories": dict(sorted_categories),
        "transaction_count": len(transactions),
        "expense_count": len(expenses),
        "income_count": len(incomes),
    }


def generate_budget_suggestions(analysis: Dict) -> Dict:
    """
    Generate budget suggestions based on analysis.

    Uses 50/30/20 rule as baseline with adjustments.
    """
    if "error" in analysis:
        return analysis

    monthly_income = analysis.get("monthly_avg_income", 0)
    monthly_expenses = analysis.get("monthly_avg_expenses", 0)

    # If no income data, estimate from expenses
    if monthly_income == 0:
        monthly_income = monthly_expenses * 1.3  # Assume 30% savings potential

    # 50/30/20 rule targets
    needs_target = monthly_income * 0.50  # Fixed expenses
    wants_target = monthly_income * 0.30  # Variable expenses
    savings_target = monthly_income * 0.20  # Savings/investments

    # Classify categories
    fixed_cats = ["Affitto", "Utenze", "Trasporti"]

    current_fixed = sum(
        data["monthly_avg"]
        for cat, data in analysis["categories"].items()
        if cat in fixed_cats
    )

    current_variable = sum(
        data["monthly_avg"]
        for cat, data in analysis["categories"].items()
        if cat not in fixed_cats
    )

    return {
        "monthly_income": monthly_income,
        "rule_50_30_20": {
            "needs": needs_target,
            "wants": wants_target,
            "savings": savings_target,
        },
        "current": {
            "fixed": current_fixed,
            "variable": current_variable,
            "total": current_fixed + current_variable,
        },
        "savings_potential": monthly_income - current_fixed - current_variable,
        "category_budgets": {
            cat: data["suggested_budget"]
            for cat, data in analysis["categories"].items()
        },
    }
