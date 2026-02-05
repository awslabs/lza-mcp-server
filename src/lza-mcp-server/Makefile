# LZA MCP Server Test Performance Optimization Makefile
#
# This Makefile provides optimized test execution commands for different scenarios:
# - Fast feedback loops for development
# - Parallel execution for CI/CD
# - Incremental testing for changed code
# - Performance monitoring and optimization

# Configuration variables
# Auto-detect container runtime: docker or finch
CONTAINER_RUNTIME ?= $(shell \
	if command -v docker >/dev/null 2>&1; then \
		echo "docker"; \
	elif command -v finch >/dev/null 2>&1; then \
		echo "finch"; \
	else \
		echo "none"; \
	fi)

LZA_MIN_VERSION ?= v1.12.0
LZA_MAX_VERSION ?=
DOCKER_IMAGE_NAME ?= lza-mcp-server:local

.PHONY: help test test-fast test-parallel test-incremental test-unit test-integration test-coverage clean-cache release lint format security-check type-check py-compile build

# Default target
help:
	@echo "🚀 LZA MCP Server Test Performance Commands"
	@echo ""
	@echo "Configuration:"
	@echo "  CONTAINER_RUNTIME=$(CONTAINER_RUNTIME)  (auto-detected: docker > finch > none)"
	@echo "  LZA_MIN_VERSION=$(LZA_MIN_VERSION)  (override with: make build LZA_MIN_VERSION=v1.10.0)"
	@echo "  LZA_MAX_VERSION=$(LZA_MAX_VERSION)  (empty = latest)"
	@echo "  DOCKER_IMAGE_NAME=$(DOCKER_IMAGE_NAME)"
	@echo ""
	@echo "Fast Development Commands:"
	@echo "  test-fast          Run fast feedback loop (unit tests only, stop on first failure)"
	@echo "  test-unit          Run unit tests with parallel execution"
	@echo ""
	@echo "Pre-Commit Verification:"
	@echo "  release            Complete pre-commit verification (lint, test, coverage, security)"
	@echo "  lint               Run code linting with ruff"
	@echo "  format             Format code with ruff"
	@echo "  type-check         Run type checking with mypy"
	@echo "  security-check     Run security analysis with bandit"
	@echo "  scan-container     Scan Docker image for vulnerabilities with Trivy (optional)"
	@echo ""
	@echo "Docker Commands:"
	@echo "  build              Build Docker image"
	@echo ""
	@echo "Comprehensive Testing:"
	@echo "  test               Run all tests with standard configuration"
	@echo "  test-parallel      Run all tests with maximum parallelization"
	@echo "  test-integration   Run integration tests"
	@echo "  test-coverage      Run tests with coverage reporting"
	@echo ""
	@echo "Utilities:"
	@echo "  clean-cache        Clear all test caches and temporary files"
	@echo "  clean-lock         Remove poetry.lock for fresh dependency resolution"
	@echo "  update-deps        Update dependencies to latest compatible versions"
	@echo ""
	@echo "Examples:"
	@echo "  make test-fast     # Quick feedback during development"
	@echo "  make test-parallel # Full test suite with parallelization"
	@echo "  make test-coverage # Generate coverage report"
	@echo "  make build LZA_MIN_VERSION=v1.10.0  # Build with custom version"

# Python syntax validation
py-compile:
	@echo "🔍 Validating Python syntax..."
	@python3 -m py_compile awslabs/**/*.py
	@echo "✅ Python syntax validation complete"

# Complete pre-commit verification pipeline
release: clean-cache clean-lock update-deps py-compile format lint type-check security-check test-coverage
	@echo "🔒 Running dependency vulnerability scan..."
	@poetry run pip-audit
	@echo "✅ Release verification complete - ready for code review!"
	@echo ""
	@echo "📋 Verification Summary:"
	@echo "  ✓ Dependencies updated to latest compatible versions"
	@echo "  ✓ Python syntax validated"
	@echo "  ✓ Code formatted with ruff"
	@echo "  ✓ Code linted with ruff"
	@echo "  ✓ Type checking passed"
	@echo "  ✓ Security analysis passed"
	@echo "  ✓ Dependency vulnerabilities checked"
	@echo "  ✓ All tests passed with coverage ≥59%"
	@echo ""
	@echo "🚀 Your code is ready for review!"

# Build Docker image
build:
	@if [ "$(CONTAINER_RUNTIME)" = "none" ]; then \
		echo "❌ Error: No container runtime found!"; \
		echo ""; \
		echo "Please install either Docker or Finch:"; \
		echo "  Docker: https://docs.docker.com/get-docker/"; \
		echo "  Finch: https://github.com/runfinch/finch"; \
		exit 1; \
	fi
	@echo "🐳 Building container image with $(CONTAINER_RUNTIME)..."
	@echo "  LZA_MIN_VERSION: $(LZA_MIN_VERSION)"
	@echo "  LZA_MAX_VERSION: $(LZA_MAX_VERSION)"
	@echo "  This will clone LZA versions and generate schemas during build"
	@$(CONTAINER_RUNTIME) build -f Dockerfile \
		--build-arg LZA_MIN_VERSION=$(LZA_MIN_VERSION) \
		$(if $(LZA_MAX_VERSION),--build-arg LZA_MAX_VERSION=$(LZA_MAX_VERSION),) \
		-t $(DOCKER_IMAGE_NAME) .
	@echo "✅ Container image built successfully with $(CONTAINER_RUNTIME)"
	@echo ""
	@echo "📋 Build Info:"
	@echo "  Image: $(DOCKER_IMAGE_NAME)"
	@echo "  Runtime: $(CONTAINER_RUNTIME)"
	@echo "  Schemas: /app/json-schemas/{version}/"
	@echo "  Min Version: $(LZA_MIN_VERSION)"
	@echo "  Max Version: $(if $(LZA_MAX_VERSION),$(LZA_MAX_VERSION),latest)"
	@echo ""
	@echo "💡 Custom build examples:"
	@echo "  make build LZA_MIN_VERSION=v1.10.0"
	@echo "  make build LZA_MIN_VERSION=v1.10.0 LZA_MAX_VERSION=v1.13.0"
	@echo "  make build CONTAINER_RUNTIME=finch  # Force specific runtime"

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
	@poetry run mypy awslabs/ --ignore-missing-imports --no-strict-optional
	@echo "✅ Type checking complete"

# Security analysis
security-check:
	@echo "🔒 Running security analysis with bandit..."
	@poetry run bandit -r awslabs/ -f json -o bandit-report.json || true
	@poetry run bandit -r awslabs/ --severity-level medium
	@echo "✅ Security analysis complete"

# Container vulnerability scanning (optional)
scan-container:
	@if [ "$(CONTAINER_RUNTIME)" = "none" ]; then \
		echo "❌ Error: No container runtime found!"; \
		exit 1; \
	fi
	@echo "🔍 Scanning container for vulnerabilities with Trivy..."
	@echo "  Image: $(DOCKER_IMAGE_NAME)"
	@if command -v trivy >/dev/null 2>&1; then \
		trivy image --severity HIGH,CRITICAL $(DOCKER_IMAGE_NAME); \
	else \
		echo "⚠️  Trivy not installed. Install with: brew install trivy"; \
		echo "   Or run via $(CONTAINER_RUNTIME): $(CONTAINER_RUNTIME) run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest image $(DOCKER_IMAGE_NAME)"; \
	fi
	@echo "✅ Container scan complete"

# Fast feedback loop for development (< 30 seconds)
test-fast:
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
		--cov-fail-under=59 \
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

# Clean lock file to ensure fresh dependency resolution
clean-lock:
	@echo "🔓 Removing poetry.lock for fresh dependency resolution..."
	@rm -f poetry.lock
	@echo "✅ Lock file removed"

# Update dependencies to latest compatible versions
update-deps: clean-lock
	@echo "📦 Updating dependencies to latest compatible versions..."
	@poetry lock
	@poetry install
	@echo "✅ Dependencies updated"
	@echo ""
	@echo "📋 Updated Dependencies:"
	@poetry show --outdated || echo "  All dependencies are up to date!"

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

