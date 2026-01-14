#!/bin/bash
# Pre-commit hook to run tests before allowing commit
# Install: cp scripts/pre-commit.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

echo "🧪 Running pre-commit tests..."

# Run tests
pytest tests/ -q

# Check exit code
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Tests failed! Commit aborted."
    echo "Fix the failing tests and try again."
    echo ""
    echo "To skip this check (not recommended), use:"
    echo "  git commit --no-verify"
    exit 1
fi

echo "✅ All tests passed! Proceeding with commit."
exit 0
