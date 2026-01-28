# Testing Guide

## Running Tests Locally

### Install dependencies
```bash
pip install -e .
pip install pytest pytest-cov pytest-xdist mypy pylint bandit
```

### Run all tests
```bash
pytest tests/ -v
```

### Run with coverage report
```bash
pytest tests/ --cov=src/trading_bot --cov-report=html
# Open htmlcov/index.html in browser to view coverage
```

### Run specific test file
```bash
pytest tests/test_paper_engine.py -v
```

### Run specific test
```bash
pytest tests/test_paper_engine.py::TestPaperBrokerBasics::test_initialization -v
```

### Run tests in parallel (faster)
```bash
pytest tests/ -n auto
```

## Type Checking

```bash
mypy src/trading_bot --ignore-missing-imports
```

## Linting

```bash
pylint src/trading_bot
flake8 src/trading_bot --max-line-length=120
```

## Code Formatting

```bash
black src/ tests/
isort src/ tests/
```

## Security Scanning

```bash
bandit -r src/trading_bot
```

## CI/CD Pipeline

Tests automatically run on every push to `main` or `develop` branches. 

**Workflow steps:**
1. Unit tests with coverage (Python 3.10, 3.11, 3.12)
2. Type checking (mypy)
3. Code linting (pylint, flake8)
4. Security scanning (bandit)
5. Code formatting checks (black, isort)

View results in **GitHub Actions** tab → **Tests and Quality Checks** workflow.

## Test Coverage Goals

- Overall: **90%+**
- Critical modules (broker, engine, risk): **95%+**
- Check current coverage: `pytest tests/ --cov=src/trading_bot --cov-report=term-missing`

## Coverage Report

After running tests with coverage:
```bash
pytest tests/ --cov=src/trading_bot --cov-report=html --cov-report=term-missing
# HTML report: htmlcov/index.html
# Terminal: Shows line-by-line coverage
```

## Adding New Tests

1. Create test file: `tests/test_*.py`
2. Use pytest conventions:
   ```python
   import pytest
   
   class TestFeature:
       @pytest.fixture
       def setup(self):
           # Setup code
           yield resource
       
       def test_something(self, setup):
           assert result == expected
   ```
3. Add docstrings to test functions
4. Mark with `@pytest.mark.unit` or `@pytest.mark.integration` if needed
5. Run: `pytest tests/test_newfile.py -v`
6. Verify coverage: `pytest tests/test_newfile.py --cov=src/trading_bot`

## Test Organization

```
tests/
├── test_paper_engine.py      # Paper trading engine tests (20+ tests)
├── test_broker_alpaca.py     # Broker integration tests (8+ tests)
├── test_lstm_nan_fix.py      # LSTM edge case tests (8+ tests)
├── test_advanced_features.py # Risk & ML tests (25+ tests)
├── test_alpha_vantage.py     # Data provider tests (15+ tests)
└── test_optimization_*.py    # Optimization tests (30+ tests)
```

## Continuous Integration Status

Check **GitHub Actions** for:
- ✅ Unit test pass rate
- ✅ Code coverage percentage
- ✅ Type check results
- ✅ Linting violations
- ✅ Security issues

## Troubleshooting

**Tests fail with import errors:**
```bash
pip install -e .  # Reinstall package in editable mode
```

**Coverage not available:**
```bash
pip install pytest-cov
```

**Performance tests slow:**
```bash
pytest tests/ -k "not slow" -v  # Skip slow tests
pytest tests/ -n auto           # Run in parallel
```

**Need to debug a test:**
```bash
pytest tests/test_file.py::TestClass::test_method -v -s  # -s shows print statements
pytest tests/test_file.py::TestClass::test_method -v --pdb  # Drop to debugger on failure
```
