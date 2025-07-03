#!/bin/bash

# Kaspa Knowledge Hub - Code Formatting Verification
# Run this before committing to ensure all files pass linting

echo "🔍 Verifying code formatting..."

# Activate virtual environment if available
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Check Black formatting
echo "▶️  Checking Black formatting..."
if black --check scripts/; then
    echo "✅ Black formatting check passed"
else
    echo "❌ Black formatting issues found - run 'black scripts/' to fix"
    exit 1
fi

# Check flake8 linting
echo "▶️  Checking flake8 linting..."
if flake8 scripts/ --max-line-length=88 --extend-ignore=E203,W503; then
    echo "✅ flake8 linting check passed"
else
    echo "❌ flake8 issues found - see output above"
    exit 1
fi

echo "🎉 All formatting and linting checks passed!"
echo "💡 Safe to commit and push!" 