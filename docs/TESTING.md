# Testing Workflow for VPEMaster

This guide explains how to run tests effectively after each code change.

## Quick Start

```bash
# Run all tests
make test

# Run tests with coverage
make test-coverage

# Run specific test file
make test-file FILE=tests/test_export_components.py

# Run tests in watch mode (auto-rerun on file changes)
make test-watch
```

## Test Structure

```
tests/
├── test_export_components.py  # Unit tests for export components
└── test_formatting.py          # Integration test for Excel formatting
```

## Running Tests

### Option 1: Using Make (Recommended)

```bash
# Install test dependencies first
make install-test-deps

# Run all tests
make test

# Run with verbose output
make test-verbose

# Run with coverage report
make test-coverage

# Run specific test file
make test-file FILE=tests/test_export_components.py

# Run specific test class
make test-class CLASS=tests/test_export_components.py::TestAgendaComponent

# Run specific test method
make test-method METHOD=tests/test_export_components.py::TestAgendaComponent::test_project_code_format_level_1
```

### Option 2: Using pytest directly

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific file
pytest tests/test_export_components.py

# Run specific test
pytest tests/test_export_components.py::TestAgendaComponent::test_project_code_format_level_1

# Run with coverage
pytest --cov=app --cov-report=html

# Run in watch mode (requires pytest-watch)
ptw
```

### Option 3: Using unittest

```bash
# Run all tests
python -m unittest discover tests

# Run specific file
python -m unittest tests.test_export_components

# Run specific test
python -m unittest tests.test_export_components.TestAgendaComponent.test_project_code_format_level_1
```

## Integration Testing

Test the actual Excel export with a real meeting:

```bash
# Test export for meeting number 957
python tests/test_formatting.py 957

# This will create test_meeting_957_export.xlsx
# Open it to verify formatting
```

## Continuous Testing Workflow

### 1. Pre-commit Testing

Before committing code:

```bash
# Run all tests
make test

# Check coverage
make test-coverage

# Ensure coverage is above 80%
```

### 2. Watch Mode for Development

While developing, use watch mode to automatically rerun tests:

```bash
# Install pytest-watch first
pip install pytest-watch

# Run in watch mode
make test-watch
```

This will automatically rerun tests whenever you save a file.

### 3. CI/CD Integration

Add to your CI/CD pipeline (e.g., GitHub Actions):

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pip install pytest pytest-cov
      - run: pytest --cov=app --cov-report=xml
```

## Writing New Tests

### Unit Test Example

```python
# tests/test_my_feature.py
import unittest
from app.services.my_service import MyService

class TestMyService(unittest.TestCase):
    def setUp(self):
        """Run before each test."""
        self.service = MyService()
    
    def test_my_function(self):
        """Test my function works correctly."""
        result = self.service.my_function("input")
        self.assertEqual(result, "expected_output")
```

### Integration Test Example

```python
# tests/test_integration.py
from app import create_app

def test_export_integration():
    """Test full export workflow."""
    app = create_app()
    with app.app_context():
        # Test code here
        pass
```

## Test Coverage

View coverage report:

```bash
# Generate HTML coverage report
pytest --cov=app --cov-report=html

# Open in browser
open htmlcov/index.html
```

Target: Maintain >80% code coverage for critical modules.

## Troubleshooting

### Tests fail with import errors

```bash
# Ensure you're in the project root
cd /Users/wmu/workspace/toastmasters/vpemaster

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov
```

### Database-related test failures

```bash
# Set test database environment variable
export FLASK_ENV=testing

# Or create a test configuration
# config.py should have TestConfig class
```

### Module not found errors

```bash
# Add project root to PYTHONPATH
export PYTHONPATH=/Users/wmu/workspace/toastmasters/vpemaster:$PYTHONPATH
```

## Best Practices

1. **Run tests before committing**: Always run `make test` before pushing code
2. **Write tests for new features**: Every new feature should have corresponding tests
3. **Test edge cases**: Include tests for error conditions and edge cases
4. **Keep tests fast**: Unit tests should run in milliseconds
5. **Use fixtures**: Share common test setup using fixtures
6. **Mock external dependencies**: Use mocks for database, API calls, etc.
7. **Descriptive test names**: Test names should describe what they test
8. **One assertion per test**: Keep tests focused and simple

## Quick Reference

| Command | Description |
|---------|-------------|
| `make test` | Run all tests |
| `make test-verbose` | Run with detailed output |
| `make test-coverage` | Run with coverage report |
| `make test-watch` | Auto-rerun on file changes |
| `pytest -v` | Verbose test output |
| `pytest -k "test_name"` | Run tests matching pattern |
| `pytest --lf` | Run last failed tests only |
| `pytest --ff` | Run failed tests first |
| `pytest -x` | Stop on first failure |
