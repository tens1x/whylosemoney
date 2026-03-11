# WhyLoseMoney

`WhyLoseMoney` is a Python CLI for tracking personal expenses and generating simple spending analysis.

## Install

```bash
pip install -e .[dev]
```

## Usage

```bash
whylosemoney add --amount 35.6 --category food --note lunch --date 2026-03-11
whylosemoney list --from 2026-03-01 --to 2026-03-31
whylosemoney analyze --period monthly
whylosemoney delete --id 5f0f6f99-8d77-4282-9e47-a1f6c1f1e2d1
```

Expenses are stored in `~/.whylosemoney/data.json`.
