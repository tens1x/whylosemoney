# WhyLoseMoney

A CLI-based personal expense tracker and analyzer that helps you understand where your money goes.

## Features

- Interactive TUI with colored tables and menu navigation
- Add, list, analyze, and delete expenses
- CSV batch import with checkpoint resume
- Configurable settings (currency, date format, page size)
- Audit history logging
- Cross-platform support (macOS, Linux, Windows)

## Installation

### From PyPI (recommended)

```bash
pip install whylosemoney
```

### With pipx (isolated environment)

```bash
pipx install whylosemoney
```

### From source

```bash
git clone https://github.com/tens1x/whylosemoney.git
cd whylosemoney
pip install -e .[dev]
```

## Usage

### Interactive Mode

```bash
whylosemoney
```

Launches the interactive TUI with menu navigation, paginated lists, and colored output.

### CLI Mode

```bash
# Add an expense
whylosemoney add --amount 35.6 --category food --note "lunch" --date 2026-03-11

# List expenses with optional date range
whylosemoney list --from 2026-03-01 --to 2026-03-31

# Analyze spending
whylosemoney analyze --period monthly

# Import from CSV
whylosemoney import --file expenses.csv
whylosemoney import --file expenses.csv --resume

# Delete an expense
whylosemoney delete --id <expense-uuid>
```

### CSV Import Format

```csv
amount,category,date,note
35.6,food,2026-03-11,lunch
12.0,transport,2026-03-12,metro
```

## Configuration

Settings are stored in `~/.whylosemoney/config.json`:

| Setting | Default | Description |
|---------|---------|-------------|
| currency | CNY | Display currency |
| date_format | %Y-%m-%d | Date display format |
| page_size | 20 | Items per page in list view |
| default_category | other | Default expense category |
| custom_categories | [] | User-defined categories |

Edit settings interactively via the TUI Settings menu, or manually edit the config file.

## Data Storage

- Expenses: `~/.whylosemoney/data.json`
- Configuration: `~/.whylosemoney/config.json`
- Audit log: `~/.whylosemoney/history.jsonl`

## Development

```bash
pip install -e .[dev]
pytest -v
```

## License

MIT
