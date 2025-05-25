# Makefile for Voice Module
# Can be used when voice module is standalone or part of larger project

.PHONY: test test-event-based test-input-handler test-workflow test-publisher clean help

# Default target
help:
	@echo "Voice Module Test Commands"
	@echo "========================="
	@echo "make test              - Run all tests"
	@echo "make test-event-based  - Run all event-based tests"
	@echo "make test-input-handler - Run input handler tests only"
	@echo "make test-workflow     - Run workflow tests only"
	@echo "make test-publisher    - Run signal publisher tests only"
	@echo "make clean             - Clean test artifacts"
	@echo ""
	@echo "Requirements:"
	@echo "- pytest installed"
	@echo "- temporalio installed (for workflow tests)"
	@echo "- Run from voice/ directory"

# Run all tests
test: test-event-based

# Run all event-based tests
test-event-based:
	@echo "🧪 Running Event-Based Voice Recording Tests"
	@echo "============================================="
	PYTHONPATH=. pytest tests/event_based/ -v --tb=short --disable-warnings --asyncio-mode=auto

# Run specific test files
test-input-handler:
	@echo "🧪 Running Input Handler Tests"
	@echo "==============================="
	PYTHONPATH=. pytest tests/event_based/test_input_handler.py -v --tb=short --disable-warnings

test-workflow:
	@echo "🧪 Running Workflow Tests"
	@echo "=========================="
	PYTHONPATH=. pytest tests/event_based/test_recording_workflow.py -v --tb=short --disable-warnings --asyncio-mode=auto

test-publisher:
	@echo "🧪 Running Signal Publisher Tests"
	@echo "=================================="
	PYTHONPATH=. pytest tests/event_based/test_recording_signal_publisher.py -v --tb=short --disable-warnings --asyncio-mode=auto

# Test with coverage (if coverage is installed)
test-coverage:
	@echo "🧪 Running Tests with Coverage"
	@echo "==============================="
	PYTHONPATH=. pytest tests/event_based/ --cov=event_based --cov-report=html --cov-report=term -v

# Clean test artifacts
clean:
	@echo "🧹 Cleaning test artifacts"
	rm -rf .pytest_cache/
	rm -rf tests/__pycache__/
	rm -rf tests/event_based/__pycache__/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Quick test (minimal output)
test-quick:
	@echo "🧪 Quick Test Run"
	@echo "=================="
	PYTHONPATH=. pytest tests/event_based/ -q --disable-warnings

# Test with verbose output and no capture (for debugging)
test-debug:
	@echo "🧪 Debug Test Run"
	@echo "=================="
	PYTHONPATH=. pytest tests/event_based/ -v -s --tb=long --disable-warnings --asyncio-mode=auto

# Install test dependencies (if using pip/uv)
install-test-deps:
	@echo "📦 Installing test dependencies"
	@echo "==============================="
	uv pip install pytest pytest-asyncio temporalio

# Show test structure
show-tests:
	@echo "📁 Test Structure"
	@echo "=================="
	@find tests/ -name "*.py" -type f | sort 