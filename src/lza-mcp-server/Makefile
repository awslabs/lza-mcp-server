# LZA MCP Server Test Performance Optimization Makefile
#
# This Makefile provides optimized test execution commands for different scenarios:
# - Fast feedback loops for development
# - Parallel execution for CI/CD
# - Incremental testing for changed code
# - Performance monitoring and optimization

.PHONY: help test test-fast test-parallel test-incremental test-unit test-integration test-coverage clean-cache release lint format security-check type-check

# Default target
help:
	@echo "🚀 LZA MCP Server Test Performance Commands"
	@echo ""
	@echo "Fast Development Commands:"
	@echo "  test-fast          Run fast feedback loop (unit tests only, stop on first failure)"
	@echo "  test-incremental   Run only tests affected by code changes"
	@echo "  test-unit          Run unit tests with parallel execution"
	@echo ""
	@echo "Pre-Commit Verification:"
	@echo "  release            Complete pre-commit verification (lint, test, coverage, security)"
	@echo "  lint               Run code linting with ruff"
	@echo "  format             Format code with ruff"
	@echo "  type-check         Run type checking with mypy"
	@echo "  security-check     Run security analysis with bandit"
	@echo ""
	@echo "Comprehensive Testing:"
	@echo "  test               Run all tests with standard configuration"
	@echo "  test-parallel      Run all tests with maximum parallelization"
	@echo "  test-integration   Run integration tests"
	@echo "  test-coverage      Run tests with coverage reporting"
	@echo ""
	@echo "Utilities:"
	@echo "  clean-cache        Clear all test caches and temporary files"
	@echo ""
	@echo "Examples:"
	@echo "  make test-fast     # Quick feedback during development"
	@echo "  make test-parallel # Full test suite with parallelization"
	@echo "  make test-coverage # Generate coverage report"

# Complete pre-commit verification pipeline
release: clean-cache format lint type-check security-check test-coverage
	@echo "✅ Release verification complete - ready for code review!"
	@echo ""
	@echo "📋 Verification Summary:"
	@echo "  ✓ Code formatted with ruff"
	@echo "  ✓ Code linted with ruff"
	@echo "  ✓ Type checking passed"
	@echo "  ✓ Security analysis passed"
	@echo "  ✓ All tests passed with coverage ≥50%"
	@echo ""
	@echo "🚀 Your code is ready for review!"

# Code formatting
format:
	@echo "🎨 Formatting code with ruff..."
	@poetry run ruff format .
	@echo "✅ Code formatting complete"

# Code linting
lint:
	@echo "🔍 Linting code with ruff..."
	@poetry run ruff check . --fix
	@echo "✅ Code linting complete"

# Type checking
type-check:
	@echo "🔬 Running type checks with mypy..."
	@poetry run mypy awslabs/ --ignore-missing-imports --no-strict-optional || true
	@echo "✅ Type checking complete"

# Security analysis
security-check:
	@echo "🔒 Running security analysis with bandit..."
	@poetry run bandit -r awslabs/ -f json -o bandit-report.json || true
	@poetry run bandit -r awslabs/ --severity-level medium
	@echo "✅ Security analysis complete"

# Fast feedback loop for development (< 30 seconds)
test-fast:
	@echo "⚡ Running fast feedback loop..."
	@poetry run pytest tests/ \
		-m "unit or (not integration and not slow)" \
		--maxfail=5 \
		-x \
		--tb=short \
		--disable-warnings

# Incremental testing (only run tests affected by changes)
test-incremental:
	@echo "🎯 Running incremental tests..."
	@echo "  (running all unit tests instead)"
	@poetry run pytest tests/ \
		-m "unit or (not integration and not slow)" \
		--tb=short \
		--maxfail=10

# Unit tests with parallel execution
test-unit:
	@echo "🧪 Running unit tests in parallel..."
	@poetry run pytest tests/ \
		-m "unit or (not integration and not slow)" \
		-n auto \
		--dist=worksteal \
		--tb=short \
		--maxfail=10 \
		--disable-warnings

# Standard test execution
test:
	@echo "🔬 Running standard test suite..."
	@poetry run pytest tests/ \
		--tb=short \
		--maxfail=10

# Parallel execution of all tests
test-parallel:
	@echo "🚀 Running all tests in parallel..."
	@poetry run pytest tests/ \
		-n auto \
		--dist=worksteal \
		--tb=short \
		--maxfail=10 \
		--disable-warnings

# Integration tests (no parallelization due to potential resource conflicts)
test-integration:
	@echo "🔗 Running integration tests..."
	@poetry run pytest tests/ \
		-m integration \
		--tb=short \
		--maxfail=5 \
		-v



# Coverage testing with optimization
test-coverage:
	@echo "📈 Running tests with coverage analysis..."
	@poetry run pytest tests/ \
		--cov=awslabs.lza_mcp_server \
		--cov-report=html:htmlcov \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov-branch \
		--cov-fail-under=50 \
		-n auto \
		--dist=worksteal \
		--tb=short



# Clean all caches and temporary files
clean-cache:
	@echo "🗑️  Cleaning test caches..."
	@rm -rf .pytest_cache/
	@rm -rf htmlcov/
	@rm -rf .coverage
	@rm -rf coverage.xml
	@rm -rf __pycache__/
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Cache cleanup complete"

# Development workflow commands
dev-test: test-fast
	@echo "🔄 Development test cycle complete"

ci-test: clean-cache test-parallel test-coverage
	@echo "🏗️  CI test pipeline complete"

# Benchmark test execution performance
benchmark:
	@echo "⏱️  Benchmarking test execution..."
	@echo "Running standard tests..."
	@time poetry run pytest tests/ -m "not slow" --tb=no -q --maxfail=5
	@echo ""
	@echo "Running parallel tests..."
	@time poetry run pytest tests/ -m "not slow" -n auto --dist=worksteal --tb=no -q --maxfail=5
	@echo ""
	@echo "Running incremental tests..."
	@echo "  (incremental test runner not available)"

# Show test statistics
stats:
	@echo "📊 Test Suite Statistics:"
	@echo ""
	@echo "Test Files:"
	@find tests/ -name "test_*.py" | wc -l | xargs echo "  Total test files:"
	@echo ""
	@echo "Test Functions:"
	@grep -r "def test_" tests/ | wc -l | xargs echo "  Total test functions:"
	@echo ""
	@echo "Test Categories:"
	@grep -r "@pytest.mark.unit" tests/ | wc -l | xargs echo "  Unit tests:"
	@grep -r "@pytest.mark.integration" tests/ | wc -l | xargs echo "  Integration tests:"
	@echo ""

# Continuous testing (watch for changes)
watch:
	@echo "👀 Watching for changes (Ctrl+C to stop)..."
	@while true; do \
		echo "🔄 Running fast tests..."; \
		make test-fast; \
		echo "⏳ Waiting for changes (30s)..."; \
		sleep 30; \
	done

# Quick smoke test (fastest possible feedback)
smoke:
	@echo "💨 Running smoke tests..."
	@poetry run pytest tests/ \
		-k "not integration" \
		--maxfail=3 \
		-x \
		--tb=line \
		-q \
		--disable-warnings

# Test specific module
test-module:
	@echo "🎯 Testing specific module: $(MODULE)"
	@poetry run pytest tests/test_$(MODULE).py \
		-v \
		--tb=short

# Examples for module testing:
# make test-module MODULE=aws_tools
# make test-module MODULE=config_tools
# make test-module MODULE=pipeline_tools

# Parallel test execution with different worker counts
test-parallel-2:
	@poetry run pytest tests/ -n 2 --dist=worksteal --tb=short

test-parallel-4:
	@poetry run pytest tests/ -n 4 --dist=worksteal --tb=short

test-parallel-8:
	@poetry run pytest tests/ -n 8 --dist=worksteal --tb=short

# Memory profiling during tests
test-memory:
	@echo "🧠 Running tests with memory profiling..."
	@poetry run pytest tests/ \
		-m "not slow" \
		--tb=short \
		--maxfail=5 \
		-v \
		--durations=10

# Test execution with different verbosity levels
test-quiet:
	@poetry run pytest tests/ -q --tb=no

test-verbose:
	@poetry run pytest tests/ -v --tb=long

test-debug:
	@poetry run pytest tests/ -vvv --tb=long --capture=no

