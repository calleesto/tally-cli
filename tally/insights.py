import logging
import os
import re
from contextlib import contextmanager

from tally.storage import budget_period, parse_started

MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"

_tokenizer = None
_model = None
_device = None


def _spent_ratio(category):
    if category["allocated"] <= 0:
        return None
    return category["spent"] / category["allocated"]


def _pace(category, time_ratio):
    spent_ratio = _spent_ratio(category)
    if spent_ratio is None:
        return "No allocation is set, so there is no pace to judge."
    transactions = category["transactions"]
    paid_as_one_bill = (
        len(transactions) == 1
        and transactions[0]["amount"] >= category["allocated"] * 0.9
    )
    if paid_as_one_bill:
        return "Settled. This looks like one bill paid up front, not daily overspending."
    if spent_ratio >= 1 and time_ratio < 0.95:
        return "Used up before the period ends. Spending here has to stop."
    if spent_ratio >= time_ratio + 0.15:
        return "Ahead of the calendar. Too much of this category is gone for how many days remain."
    if spent_ratio <= time_ratio - 0.15:
        return "Behind the calendar. There is room left for the rest of the period."
    return "Close to the calendar."


def advice_lines(state, today=None):
    started = parse_started(state.get("started"))
    if started is None:
        return ["Save a monthly budget before asking for advice."]

    period = budget_period(started, today)
    if period["finished"]:
        return ["This month is over. Save a new budget before judging the next one."]

    lines = []
    warnings = []
    for category in state["categories"]:
        spent_ratio = _spent_ratio(category)
        if spent_ratio is None:
            continue
        spent_percent = int(round(spent_ratio * 100))
        pace = _pace(category, period["time_ratio"])
        if pace.startswith("Ahead") or pace.startswith("Used up"):
            warnings.append(category["name"])
            lines.append(
                f"{category['name']} has used {spent_percent}% and the month is not over. "
                f"Slow this spending down or it will run out."
            )
        elif pace.startswith("Settled"):
            lines.append(f"{category['name']} is one bill that is already paid. Do not change it.")
        elif pace.startswith("Behind"):
            lines.append(f"{category['name']} has spending left for the rest of this month.")
    if not state["categories"]:
        lines.append("Add a category before asking for spending advice.")
    elif not warnings:
        lines.append("No category is being spent too fast for this point in the month.")
    return lines


def timeline_lines(state, today=None):
    from datetime import timedelta

    started = parse_started(state.get("started"))
    if started is None:
        return ["  Save a monthly budget to set when this month starts."]
    period = budget_period(started, today)
    last = period["end"] - timedelta(days=1)
    start_label = f"{period['start'].day} {period['start'].strftime('%B')}"
    end_label = f"{last.day} {last.strftime('%B')}"
    if period["finished"]:
        return [f"  This month ran from {start_label} through {end_label}. It is over."]
    return [
        f"  This month started on {start_label}.",
        f"  Today is day {period['elapsed_days']} of {period['total_days']}.",
        f"  {period['remaining_days']} days are left, through {end_label}.",
    ]


def spending_brief(state, today=None):
    return "\n".join(advice_lines(state, today))


def _numbers(text):
    return set(re.findall(r"\d+(?:\.\d+)?", text))


def _usable(text, brief):
    if not text:
        return False
    lowered = text.casefold()
    blocked = ("until the start", "before the", "timeline", "scheduled", "not started", "september")
    if any(phrase in lowered for phrase in blocked):
        return False
    return _numbers(text) <= _numbers(brief)


@contextmanager
def _hidden_stderr():
    """PyTorch prints a macOS note onto the screen while the model loads."""
    stream = os.dup(2)
    sink = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(sink, 2)
        yield
    finally:
        os.dup2(stream, 2)
        os.close(stream)
        os.close(sink)


def write_insight(state):
    with _hidden_stderr():
        return _write_insight(state)


def _write_insight(state):
    _load_model()
    import torch

    brief = spending_brief(state)
    messages = [
        {
            "role": "system",
            "content": (
                "Rewrite the advice as two or three plain sentences. No slang. "
                "Do not mention dates, days, or a timeline. "
                "Do not say the month has not started. "
                "Keep every warning. Do not add any number that is not already written."
            ),
        },
        {"role": "user", "content": brief},
    ]
    prompt = _tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = _tokenizer(prompt, return_tensors="pt").to(_device)
    for _attempt in range(3):
        with torch.no_grad():
            output = _model.generate(
                **inputs,
                max_new_tokens=120,
                do_sample=True,
                temperature=0.8,
                top_p=0.9,
            )
        new_tokens = output[0][inputs["input_ids"].shape[-1]:]
        text = _tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        if _usable(text, brief):
            return text
    return brief.replace("\n", " ")


def _load_model():
    global _tokenizer, _model, _device
    if _model is not None:
        return

    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    logging.getLogger("torch").setLevel(logging.ERROR)
    logging.getLogger("torch.distributed").setLevel(logging.ERROR)
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ModuleNotFoundError as error:
        missing = error.name or "transformers"
        raise ModuleNotFoundError(
            f"Install {missing} with: python3 -m pip install -r requirements.txt"
        ) from error

    if torch.cuda.is_available():
        _device = "cuda"
        dtype = torch.float16
    elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        _device = "mps"
        dtype = torch.float16
    else:
        _device = "cpu"
        dtype = torch.float32

    _tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    _model = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=dtype)
    _model.to(_device)
    _model.eval()
