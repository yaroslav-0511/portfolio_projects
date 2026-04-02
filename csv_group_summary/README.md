# CSV group summary (stdlib only)

**Public sample** — aggregates a numeric column **per group** from an input CSV and writes a summary CSV.

**Use case:** same pattern as requests like “group sales by category and output totals.”

## Usage

```bash
python main.py --input sample_sales.csv --group-by category --sum revenue --output summary.csv
```

### Arguments

| Argument | Description |
|----------|-------------|
| `--input` | Path to input `.csv` |
| `--group-by` | Column name to group by |
| `--sum` | Numeric column to sum per group |
| `--output` | Path to write summary CSV (`group`, `total_<column>`, `row_count`) |

Requires UTF-8 CSV with a header row.

## Example

`sample_sales.csv` is included. After running the command above, `summary.csv` lists each category with total revenue and number of rows.

## Requirements

Python 3.10+ (no third-party packages).
