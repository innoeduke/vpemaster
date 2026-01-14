# Testing Quick Reference

## 🚀 Quick Commands

```bash
# Most common commands
make test                    # Run all tests (use this after every change!)
make test-coverage          # Run tests + see coverage report
./scripts/test.sh -c        # Alternative with coverage

# Run specific tests
make test-file FILE=tests/test_export_components.py
pytest tests/test_export_components.py::TestAgendaComponent::test_project_code_format_level_1

# Manual integration test
python tests/test_formatting.py 957
```

## 📋 Workflow After Code Changes

### 1. Quick Check (30 seconds)
```bash
make test
```
✅ **25 tests** should pass

### 2. Full Check with Coverage (1 minute)
```bash
make test-coverage
open htmlcov/index.html  # View coverage report
```
🎯 **Target**: >80% coverage

### 3. Manual Verification (optional)
```bash
python tests/test_formatting.py 957
# Opens Excel file for visual inspection
```

## 🔄 Development Workflow

### Option A: Manual Testing
```bash
# 1. Make code changes
# 2. Run tests
make test
# 3. If tests pass, commit
git commit -m "Your message"
```

### Option B: Watch Mode (Auto-rerun)
```bash
# Terminal 1: Watch mode
make test-watch

# Terminal 2: Make your changes
# Tests auto-run on save!
```

### Option C: Pre-commit Hook
```bash
# Install once
cp scripts/pre-commit.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

# Now tests run automatically before every commit
git commit -m "Your message"
# → Tests run automatically
# → Commit only if tests pass
```

## 📊 Current Test Status

- ✅ **25 unit tests** passing
- ✅ **Test coverage** configured
- ✅ **Watch mode** available
- ✅ **Pre-commit hook** ready

## 🎯 Best Practices

1. **Always run `make test` before committing**
2. **Add tests for new features**
3. **Keep tests fast** (current: 0.35s for 25 tests)
4. **Use watch mode during development**
5. **Check coverage for new code**

## 📁 Test Files

```
tests/
├── conftest.py                    # Test configuration
├── test_export_components.py      # 25 unit tests
└── test_formatting.py             # Manual integration test
```

## 🔧 Troubleshooting

**Tests fail to import app module?**
```bash
# conftest.py should fix this automatically
# If not, check you're in project root
pwd  # Should show: .../vpemaster
```

**Want to run just one test?**
```bash
pytest tests/test_export_components.py::TestAgendaComponent::test_project_code_format_level_1 -v
```

**Need more verbose output?**
```bash
make test-verbose
```

## 📚 Full Documentation

See [TESTING.md](TESTING.md) for complete documentation.
