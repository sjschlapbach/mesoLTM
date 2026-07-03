# mesoLTM

A **mesoscopic traffic flow model** — a Python package (`mesoltm`) modelling traffic between the microscopic (per-vehicle) and macroscopic (continuum) scales.

> _Early development: the package is being scaffolded and is not yet installable from PyPI._

## Requirements

- Python **3.11+**

## Setup

Clone the repository and create an isolated virtual environment:

```bash
git clone <repository-url>
cd mesoLTM

# Create the virtual environment (Python 3.11)
python3.11 -m venv venv

# Activate it
source venv/bin/activate        # macOS / Linux
# .\venv\Scripts\activate       # Windows (PowerShell)
```

Once dependencies are introduced, install them here:

```bash
# pip install -r requirements.txt   # placeholder — no dependencies yet
```

To leave the environment:

```bash
deactivate
```

## Usage

> _Placeholder: how to run the project — to be filled in once there is code._

```bash
# python -m mesoltm ...          # placeholder
```

## Development

- The `venv/` directory is git-ignored — do not commit it.
- Contributor and agent guidance lives in [`CLAUDE.md`](CLAUDE.md); internal project tracking is maintained under [`.ai/`](.ai/).
- User-facing documentation will live under `docs/` (not present yet).

## License

[MIT](LICENSE) © 2026 Julius Schlapbach
