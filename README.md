# Libertas

A modern Python project with best practices.

## Installation

### Development Installation

```bash
# Clone the repository
git clone https://github.com/Naruki-Ichihara/libertas.git
cd libertas

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### Production Installation

```bash
pip install libertas
```

## Usage

```python
import libertas

print(libertas.__version__)
```

## Development

### Running Tests

```bash
pytest
```

### Code Quality

```bash
# Format code
black libertas tests

# Lint code
ruff check libertas tests

# Type check
mypy libertas
```

## Project Structure

```
libertas/
├── libertas/            # Main package code
│   ├── __init__.py
│   └── py.typed         # PEP 561 marker for type hints
├── tests/               # Test files
│   ├── __init__.py
│   └── test_libertas.py
├── docs/                # Documentation
├── pyproject.toml       # Project configuration
└── README.md
```

## License

MIT
