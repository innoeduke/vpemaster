# Makefile for VPEMaster Flask Application

.PHONY: help install install-test-deps test test-verbose test-coverage test-watch test-file test-class test-method run clean

# Default target
help:
	@echo "VPEMaster Development Commands"
	@echo "=============================="
	@echo ""
	@echo "Setup:"
	@echo "  make install           - Install production dependencies"
	@echo "  make install-test-deps - Install testing dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  make test              - Run all tests"
	@echo "  make test-verbose      - Run tests with verbose output"
	@echo "  make test-coverage     - Run tests with coverage report"
	@echo "  make test-watch        - Run tests in watch mode (auto-rerun)"
	@echo "  make test-file FILE=<path> - Run specific test file"
	@echo "  make test-class CLASS=<path::class> - Run specific test class"
	@echo "  make test-method METHOD=<path::class::method> - Run specific test"
	@echo ""
	@echo "Running:"
	@echo "  make run               - Run Flask development server"
	@echo "  make run-prod          - Run with Gunicorn (production)"
	@echo ""
	@echo "Database:"
	@echo "  make db-upgrade        - Apply database migrations"
	@echo "  make db-migrate MSG=<message> - Create new migration"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean             - Remove cache files and test artifacts"

# Installation
install:
	pip install -r requirements.txt

install-test-deps:
	pip install pytest pytest-cov pytest-watch

# Testing
test:
	@echo "Running all tests..."
	@pytest tests/ || (echo "❌ Tests failed" && exit 1)
	@echo "✅ All tests passed"

test-verbose:
	@echo "Running tests with verbose output..."
	@pytest -v tests/

test-coverage:
	@echo "Running tests with coverage..."
	@pytest --cov=app --cov-report=term-missing --cov-report=html tests/
	@echo ""
	@echo "📊 Coverage report generated in htmlcov/index.html"
	@echo "Open with: open htmlcov/index.html"

test-watch:
	@echo "Running tests in watch mode..."
	@echo "Tests will auto-rerun when files change"
	@ptw tests/ -- -v

test-file:
	@echo "Running tests in $(FILE)..."
	@pytest -v $(FILE)

test-class:
	@echo "Running test class $(CLASS)..."
	@pytest -v $(CLASS)

test-method:
	@echo "Running test method $(METHOD)..."
	@pytest -v $(METHOD)

# Running the application
run:
	@echo "Starting Flask development server..."
	@flask run --port 5001

run-prod:
	@echo "Starting Gunicorn production server..."
	@gunicorn -w 4 -b 0.0.0.0:5001 run:app

# Database operations
db-upgrade:
	@echo "Applying database migrations..."
	@flask db upgrade

db-migrate:
	@echo "Creating new migration: $(MSG)"
	@flask db migrate -m "$(MSG)"

# Cleanup
clean:
	@echo "Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf htmlcov/ .coverage 2>/dev/null || true
	@rm -f test_meeting_*.xlsx 2>/dev/null || true
	@echo "✅ Cleanup complete"

# Linting (optional - install flake8 first)
lint:
	@echo "Running linter..."
	@flake8 app/ tests/ --max-line-length=120 --exclude=migrations

# Format code (optional - install black first)
format:
	@echo "Formatting code..."
	@black app/ tests/ --line-length=120
