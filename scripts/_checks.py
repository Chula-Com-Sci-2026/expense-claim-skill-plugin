"""Field-level checks shared by both validators."""
import datetime
import re

ISO_CURRENCY = re.compile(r"^[A-Z]{3}$")


def is_blank(value):
    return (value or "").strip() == ""


def bad_date(value):
    try:
        datetime.date.fromisoformat((value or "").strip())
    except ValueError:
        return True
    return False


def bad_currency(value):
    return not ISO_CURRENCY.match((value or "").strip())


def number(value):
    """Return the value as a float, or None when it is not a clean decimal."""
    text = (value or "").strip().replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def header_problem(actual, expected):
    if actual == expected:
        return None
    missing = [c for c in expected if c not in actual]
    extra = [c for c in actual if c not in expected]
    if missing or extra:
        parts = []
        if missing:
            parts.append("missing " + ", ".join(missing))
        if extra:
            parts.append("unexpected " + ", ".join(extra))
        return "; ".join(parts)
    return "columns are out of order: expected " + ", ".join(expected)
