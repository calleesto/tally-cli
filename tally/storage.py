import calendar
import json
from datetime import date
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent.parent / "state.json"


def ensure_json_exists():
    if not STATE_FILE.exists():
        default_data = {"name": None, "budget": None, "categories": []}
        STATE_FILE.write_text(json.dumps(default_data, indent=2) + "\n")


def normalize_category(item):
    if isinstance(item, str):
        return {"name": item.strip(), "allocated": 0.0, "spent": 0.0, "transactions": []}
    name = str(item.get("name", "")).strip() or "Unnamed"
    transactions = []
    for entry in item.get("transactions") or []:
        if not isinstance(entry, dict):
            continue
        transactions.append({
            "amount": _as_amount(entry.get("amount")),
            "note": str(entry.get("note") or "").strip(),
        })
    return {
        "name": name,
        "allocated": _as_amount(item.get("allocated")),
        "spent": _as_amount(item.get("spent")),
        "transactions": transactions,
    }


def _as_amount(value):
    try:
        amount = round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0
    return amount if amount >= 0 else 0.0


def load_state():
    ensure_json_exists()
    try:
        data = json.loads(STATE_FILE.read_text())
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}

    budget = data.get("budget")
    if budget is not None:
        try:
            budget = round(float(budget), 2)
        except (TypeError, ValueError):
            budget = None

    raw_categories = data.get("categories") or []
    if not isinstance(raw_categories, list):
        raw_categories = []

    return {
        "name": (data.get("name") or "").strip() or None,
        "budget": budget,
        "started": _started_text(data.get("started")),
        "categories": [normalize_category(item) for item in raw_categories],
    }


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


def _started_text(value):
    parsed = parse_started(value)
    if parsed is None:
        return None
    return parsed.isoformat()


def parse_started(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def add_months(day, months):
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day.day, last_day))


def budget_period(started, today=None):
    """One month beginning on the day the budget was saved."""
    today = today or date.today()
    end = add_months(started, 1)
    total_days = (end - started).days
    if today < started:
        elapsed = 1
    elif today >= end:
        elapsed = total_days
    else:
        elapsed = (today - started).days + 1
    elapsed = min(total_days, max(1, elapsed))
    return {
        "start": started,
        "end": end,
        "today": today,
        "total_days": total_days,
        "elapsed_days": elapsed,
        "remaining_days": total_days - elapsed,
        "time_ratio": elapsed / total_days,
        "finished": today >= end,
    }


def format_amount(amount):
    return f"{amount:,.2f}"


def parse_amount(raw, allow_zero=True):
    cleaned = raw.replace(",", "").replace("$", "").strip()
    if not cleaned:
        return None, "Enter a number, for example 250 or 250.00."
    try:
        amount = round(float(cleaned), 2)
    except ValueError:
        return None, "Enter a number, for example 250 or 250.00."
    if amount < 0:
        return None, "Amount cannot be negative."
    if amount == 0 and not allow_zero:
        return None, "Enter an amount greater than zero."
    return amount, None


def category_left(category):
    return round(category["allocated"] - category["spent"], 2)


def name_taken(state, name, ignore=None):
    target = name.casefold()
    return any(
        category is not ignore and category["name"].casefold() == target
        for category in state["categories"]
    )


def totals(state):
    allocated = round(sum(category["allocated"] for category in state["categories"]), 2)
    spent = round(sum(category["spent"] for category in state["categories"]), 2)
    return allocated, spent
