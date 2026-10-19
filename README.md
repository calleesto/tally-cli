# Tally

Tally is a terminal budget. It keeps one monthly budget, splits it across categories, and shows how much is left with bars that start full and shrink as money is spent.

![Budget screen](<assets/Screenshot 2026-10-19 at 16.57.11.png>)

![Categories screen](<assets/Screenshot 2026-10-19 at 16.58.45.png>)

![Insights screen](<assets/Screenshot 2026-10-19 at 17.51.48.png>)

## Run

Open a terminal in this folder and run:

```bash
python3 -m pip install -r requirements.txt
python3 main.py
```

The example account is stored in `state.json`. Insights uses [Qwen/Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct). The first analysis downloads that model.

## Screens

**Budget** shows the account, the monthly total, and what is spent, unspent, allocated, and still unallocated.

**Categories** shows each category, its bar, and the allocated, spent, and remaining amounts.

**Insights** compares spending with how much of the month is left, then says what to change. The period starts on the day the monthly budget is saved. Choose **Analyze spending** on that screen. The side arrows move from Budget to Categories to Insights.

| Key | Action |
| --- | --- |
| ↑ ↓ | Move through the actions |
| ← → | Switch between Budget and Categories |
| Enter | Select |
| Esc | Go back, or cancel what you are typing |

## Example

The sample budget is 2,000.00 for Alex.

| Category | Allocated | Spent | Left |
| --- | ---: | ---: | ---: |
| Rent | 900.00 | 900.00 | 0.00 |
| Groceries | 400.00 | 160.00 | 240.00 |
| Transport | 200.00 | 50.00 | 150.00 |
