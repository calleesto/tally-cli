# Tally

Tally is a terminal budget. PyTorch runs [Qwen/Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct) locally and turns the month's spending pace into a short suggestion.

## Run

```bash
python3 -m pip install -r requirements.txt
python3 main.py
```

The first analysis downloads the model. The example account is in `state.json`.

## Screens

**Budget** shows the account, the monthly total, and the day of the period.

![Budget screen](<assets/Screenshot 2026-10-19 at 16.57.11.png>)

**Categories** shows each category and how much of it is left. Bars start full and shrink as money is spent.

![Categories screen](<assets/Screenshot 2026-10-19 at 16.58.45.png>)

**Insights** is where PyTorch runs. **Analyze spending** asks Qwen for advice based on how much of the month is left.

![Insights screen](<assets/Screenshot 2026-10-19 at 17.51.48.png>)

| Key | Action |
| --- | --- |
| ↑ ↓ | Move through the actions |
| ← → | Switch between Budget, Categories, and Insights |
| Enter | Select |
| Esc | Go back, or cancel what you are typing |

## Example

The sample budget is 2,000.00 for Alex, starting 1 October.

| Category | Allocated | Spent | Left |
| --- | ---: | ---: | ---: |
| Rent | 900.00 | 900.00 | 0.00 |
| Groceries | 400.00 | 160.00 | 240.00 |
| Transport | 200.00 | 50.00 | 150.00 |
