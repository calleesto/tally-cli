import sys

from datetime import date

from tally.insights import timeline_lines, write_insight
from tally.storage import (
    budget_period,
    category_left,
    format_amount,
    load_state,
    name_taken,
    parse_started,
    save_state,
    totals,
)
from tally.ui import (
    ExitApp,
    Terminal,
    ask_amount,
    ask_text,
    banner,
    bar_width,
    heading,
    meter,
    money_row,
    screen_width,
)


def budget_lines(state):
    allocated, spent = totals(state)
    budget = state["budget"]
    lines = [
        heading("Account"),
        f"  {state['name']}",
        "",
        heading("Monthly budget"),
    ]
    if budget is None:
        lines.append("  Not set")
        lines.append(money_row([("Spent", spent)]))
        return lines
    lines.append(f"  {format_amount(budget)}")
    started = parse_started(state.get("started"))
    if started:
        period = budget_period(started)
        lines.append(f"  Started {started.day} {started.strftime('%B')}")
        lines.append(f"  Day {period['elapsed_days']} of {period['total_days']}")
    lines.append("  " + meter(round(budget - spent, 2), budget, bar_width()))
    lines.append(money_row([
        ("Spent", spent),
        ("Unspent", round(budget - spent, 2)),
    ]))
    lines.append(money_row([
        ("Allocated", allocated),
        ("Unallocated", round(budget - allocated, 2)),
    ]))
    if allocated > budget:
        lines.append("  Allocations exceed the monthly budget.")
    return lines


def category_board(state):
    lines = [heading("Categories")]
    if not state["categories"]:
        lines.append("  None yet.")
        return lines
    width = bar_width()
    for category in state["categories"]:
        left = category_left(category)
        lines.extend([
            "",
            f"  {category['name']}",
            "  " + meter(left, category["allocated"], width),
            money_row([("Allocated", category["allocated"])]),
            money_row([("Spent", category["spent"])]),
            money_row([("Left", left)]),
        ])
    return lines


def category_lines(category):
    left = category_left(category)
    lines = [
        heading("Category"),
        f"  {category['name']}",
        "",
        heading("Remaining"),
        "  " + meter(left, category["allocated"], bar_width()),
        money_row([("Allocated", category["allocated"])]),
        money_row([("Spent", category["spent"])]),
        money_row([("Left", left)]),
    ]
    transactions = category["transactions"][-8:]
    lines.append("")
    lines.append(heading("Expenses"))
    if transactions:
        for entry in transactions:
            note = f"    {entry['note']}" if entry["note"] else ""
            lines.append(f"  {format_amount(entry['amount'])}{note}")
    else:
        lines.append("  None yet.")
    return lines


def choose_category(ui, state):
    while state["categories"]:
        labels = [category["name"] for category in state["categories"]]
        labels.append("Back")
        choice = ui.menu([heading("Select a category")], labels)
        if choice is None or choice == len(state["categories"]):
            return
        manage_category(ui, state, state["categories"][choice])
    ui.notice = "Add a category before selecting one."


def manage_category(ui, state, category):
    options = [
        "Record an expense",
        "Set allocation",
        "Rename category",
        "Remove category",
        "Back",
    ]
    while category in state["categories"]:
        choice = ui.menu(category_lines(category), options)
        if choice is None or choice == 4:
            return
        if choice == 0:
            record_expense(ui, state, category)
        elif choice == 1:
            set_allocation(ui, state, category)
        elif choice == 2:
            rename_category(ui, state, category)
        elif remove_category(ui, state, category):
            return


def record_expense(ui, state, category):
    header = [category["name"], "Record an expense"]
    amount = ask_amount(ui, header, "Expense amount", allow_zero=False)
    if amount is None:
        ui.notice = "Cancelled."
        return
    note = ask_text(ui, header, "Note (optional)", allow_empty=True)
    if note is None:
        ui.notice = "Cancelled."
        return
    category["spent"] = round(category["spent"] + amount, 2)
    category["transactions"].append({"amount": amount, "note": note})
    save_state(state)
    detail = f" ({note})" if note else ""
    ui.notice = f"Recorded {format_amount(amount)}{detail} under {category['name']}."
    if category["spent"] > category["allocated"]:
        over = round(category["spent"] - category["allocated"], 2)
        ui.notice += f" Over allocation by {format_amount(over)}."


def set_allocation(ui, state, category):
    amount = ask_amount(
        ui,
        [category["name"], f"Current allocation  {format_amount(category['allocated'])}"],
        "Allocation",
    )
    if amount is None:
        ui.notice = "Cancelled."
        return
    category["allocated"] = amount
    save_state(state)
    ui.notice = f"Allocation for {category['name']} set to {format_amount(amount)}."


def rename_category(ui, state, category):
    error = ""
    initial = category["name"]
    while True:
        name = ui.edit(
            [f"Rename {category['name']}"],
            "Category name",
            initial,
            error,
        )
        if name is None:
            ui.notice = "Cancelled."
            return
        initial = name
        if not name:
            error = "This field cannot be empty."
            continue
        if name_taken(state, name, ignore=category):
            error = "A category with that name already exists."
            continue
        category["name"] = name
        save_state(state)
        ui.notice = f"Category renamed to {name}."
        return


def remove_category(ui, state, category):
    choice = ui.menu(
        [f"Remove {category['name']} and its recorded spending?"],
        ["Cancel", "Remove"],
    )
    if choice != 1:
        ui.notice = "Cancelled."
        return False
    state["categories"].remove(category)
    save_state(state)
    ui.notice = f"Removed {category['name']}."
    return True


def add_category(ui, state):
    error = ""
    initial = ""
    while True:
        name = ui.edit(["New category"], "Category name", initial, error)
        if name is None:
            ui.notice = "Cancelled."
            return
        initial = name
        if not name:
            error = "This field cannot be empty."
            continue
        if name_taken(state, name):
            error = "A category with that name already exists."
            continue
        break
    allocated = ask_amount(
        ui,
        ["New category", name],
        "Allocation (0 if undecided)",
    )
    if allocated is None:
        ui.notice = "Cancelled."
        return
    state["categories"].append({
        "name": name,
        "allocated": allocated,
        "spent": 0.0,
        "transactions": [],
    })
    save_state(state)
    ui.notice = f"Added {name} with an allocation of {format_amount(allocated)}."


def set_budget(ui, state, required=False):
    header = ["Monthly budget"]
    if state["budget"] is not None:
        header.append(f"Current budget  {format_amount(state['budget'])}")
    elif required:
        header.append("Set a monthly budget before recording spending.")
    amount = ask_amount(ui, header, "Monthly budget", allow_escape=not required)
    if amount is None:
        ui.notice = "Cancelled."
        return
    state["budget"] = amount
    if not state.get("started"):
        state["started"] = date.today().isoformat()
    save_state(state)
    ui.notice = f"Monthly budget set to {format_amount(amount)}."


def clear_categories(ui, state):
    if not state["categories"]:
        ui.notice = "There are no categories to clear."
        return
    choice = ui.menu(
        ["This removes every category and its recorded spending."],
        ["Cancel", "Clear all categories"],
    )
    if choice != 1:
        ui.notice = "Cancelled."
        return
    state["categories"] = []
    save_state(state)
    ui.notice = "All categories have been removed."


def insight_lines(state, text):
    lines = [heading("This month"), ""]
    lines.extend(timeline_lines(state))
    lines.append("")
    lines.append(heading("Suggestion"))
    lines.append("")
    if not text:
        lines.append("  No suggestion yet.")
        lines.append("  Analyze spending for advice on the days still left.")
        return lines
    width = screen_width()
    for paragraph in text.splitlines():
        lines.extend(_wrap(paragraph, width))
    return lines


def _wrap(text, width):
    words = text.split()
    if not words:
        return [""]
    lines = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= width - 2:
            current = candidate
        else:
            lines.append(f"  {current}")
            current = word
    if current:
        lines.append(f"  {current}")
    return lines


def analyze_spending(ui, state):
    ui.render(banner("insights") + [
        "",
        heading("Insights"),
        "",
        "  Analyzing spending.",
        "  The first run downloads Qwen and can take several minutes.",
    ])
    try:
        return write_insight(state)
    except ModuleNotFoundError as error:
        ui.notice = str(error)
    except Exception as error:
        ui.notice = f"Could not write an insight. {error}"
    return None


def _neighbor(screen, key):
    order = ["budget", "categories", "insights"]
    step = 1 if key == "right" else -1
    return order[(order.index(screen) + step) % len(order)]


def show_menu(ui, state):
    screen = "budget"
    insight = ""
    while True:
        if screen == "budget":
            choice = ui.menu(
                budget_lines(state),
                ["Set monthly budget", "Exit"],
                allow_escape=False,
                screen="budget",
            )
            if choice in ("left", "right"):
                screen = _neighbor(screen, choice)
                continue
            if choice == 1:
                save_state(state)
                return
            set_budget(ui, state)
            continue

        if screen == "categories":
            choice = ui.menu(
                category_board(state),
                ["Manage a category", "Add a category", "Clear all categories"],
                allow_escape=True,
                screen="categories",
            )
            if choice in ("left", "right"):
                screen = _neighbor(screen, choice)
                continue
            if choice is None:
                screen = "budget"
                continue
            if choice == 0:
                choose_category(ui, state)
            elif choice == 1:
                add_category(ui, state)
            else:
                clear_categories(ui, state)
            continue

        choice = ui.menu(
            insight_lines(state, insight),
            ["Analyze spending"],
            allow_escape=True,
            screen="insights",
        )
        if choice in ("left", "right"):
            screen = _neighbor(screen, choice)
            continue
        if choice is None:
            screen = "budget"
            continue
        note = analyze_spending(ui, state)
        if note:
            insight = note


def run(ui):
    state = load_state()
    if not state["name"]:
        name = ask_text(
            ui,
            ["Create an account to store your budget on this computer."],
            "Account name",
            allow_escape=False,
        )
        state["name"] = name
        save_state(state)
        ui.notice = f"Account created for {name}."
    else:
        ui.notice = f"Welcome back, {state['name']}."

    if state["budget"] is None:
        set_budget(ui, state, required=True)

    show_menu(ui, state)


def main():
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("Tally runs in a terminal. Open it there and start it again.")
        return

    ui = Terminal()
    try:
        ui.enter()
        ui.install_signals()
        run(ui)
    except ExitApp:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        ui.leave()
    print("Session saved.")
