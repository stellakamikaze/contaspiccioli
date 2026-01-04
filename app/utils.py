"""Shared utility functions for Contaspiccioli."""
from typing import Optional, Union
from datetime import date


def month_name(month: int) -> str:
    """Get Italian month name."""
    months = [
        "", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
        "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"
    ]
    return months[month] if 1 <= month <= 12 else ""


def format_currency(value: Optional[float]) -> str:
    """Format number as Euro currency."""
    if value is None:
        return "0,00"
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_percentage(value: Optional[float]) -> str:
    """Format number as percentage."""
    if value is None:
        return "0%"
    return f"{value:.1f}%"


def format_date(value: Optional[Union[date, str]]) -> str:
    """Format date in Italian style."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.strftime("%d/%m/%Y")
