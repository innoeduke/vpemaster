#!/bin/bash
# Quick test runner script
# Usage: ./scripts/test.sh [options]

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🧪 VPEMaster Test Runner${NC}"
echo ""

# Parse arguments
COVERAGE=false
VERBOSE=false
WATCH=false
FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--coverage)
            COVERAGE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -w|--watch)
            WATCH=true
            shift
            ;;
        -f|--file)
            FILE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: ./scripts/test.sh [options]"
            echo ""
            echo "Options:"
            echo "  -c, --coverage    Run with coverage report"
            echo "  -v, --verbose     Run with verbose output"
            echo "  -w, --watch       Run in watch mode (auto-rerun)"
            echo "  -f, --file FILE   Run specific test file"
            echo "  -h, --help        Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./scripts/test.sh                    # Run all tests"
            echo "  ./scripts/test.sh -c                 # Run with coverage"
            echo "  ./scripts/test.sh -v                 # Run with verbose output"
            echo "  ./scripts/test.sh -f tests/test_export_components.py"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Build pytest command
CMD="pytest"

if [ "$VERBOSE" = true ]; then
    CMD="$CMD -v"
fi

if [ "$COVERAGE" = true ]; then
    CMD="$CMD --cov=app --cov-report=term-missing --cov-report=html"
fi

if [ -n "$FILE" ]; then
    CMD="$CMD $FILE"
else
    CMD="$CMD tests/"
fi

# Run tests
echo -e "${YELLOW}Running: $CMD${NC}"
echo ""

if [ "$WATCH" = true ]; then
    ptw tests/ -- -v
else
    if $CMD; then
        echo ""
        echo -e "${GREEN}✅ All tests passed!${NC}"
        
        if [ "$COVERAGE" = true ]; then
            echo ""
            echo -e "${YELLOW}📊 Coverage report: htmlcov/index.html${NC}"
        fi
        exit 0
    else
        echo ""
        echo -e "${RED}❌ Tests failed!${NC}"
        exit 1
    fi
fi
