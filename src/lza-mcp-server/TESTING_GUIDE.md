# Testing Guide for LZA MCP Server

This guide documents the testing approach and best practices used in the LZA MCP Server project.

## Testing Philosophy

### High Coverage with Pragmatism
- **Target**: Aim for 90%+ coverage on tested modules
- **Pragmatic Approach**: Don't obsess over unreachable code or complex edge cases
- **Document Gaps**: Always note what's uncovered and why it's acceptable

### Organization by Concern
Tests are split into focused modules based on functional concerns rather than creating monolithic test files. This improves:
- **Readability**: Easier to find specific test scenarios
- **Maintainability**: Changes to one concern don't affect other test files
- **Parallel Execution**: Multiple test files can run concurrently
- **Code Review**: Smaller, focused files are easier to review

## Test File Organization

### Directory Structure
Tests mirror the source code structure:

```
src/lza-mcp-server/
├── awslabs/lza_mcp_server/
│   ├── orchestration/core/
│   │   └── s3_manager.py
│   └── tools/
│       ├── config/
│       │   └── get_config_s3.py
│       └── pipeline/
│           ├── get_pipeline_status.py
│           └── diagnose_pipeline_errors.py
└── tests/
    ├── test_s3_manager_*.py              # For orchestration/core modules
    └── tools/
        ├── config/
        │   └── test_get_config_s3_*.py   # For tools/config modules
        └── pipeline/
            ├── test_get_pipeline_status_*.py
            └── test_diagnose_pipeline_errors_*.py
```

### Naming Convention
Test files follow the pattern: `test_{module_name}_{concern}.py`

Examples:
- `test_s3_manager_init.py` - Initialization and session management
- `test_s3_manager_bucket_verification.py` - Bucket verification logic
- `test_get_config_s3_errors.py` - Error handling scenarios

## Splitting Tests by Concern

### Identify Functional Concerns
Before writing tests, analyze the module to identify distinct functional areas:

**Example: `s3_manager.py`**
1. **Initialization** - Constructor, session/client management
2. **Bucket Name Determination** - Constructing bucket names
3. **Bucket Verification** - Checking if buckets exist
4. **Bucket Validation** - Validating custom bucket names
5. **User Prompts** - Generating user-facing prompts
6. **File Upload** - Uploading files to S3

**Example: `get_pipeline_status.py`**
1. **Helpers** - Helper functions and caching
2. **Validation** - Input validation
3. **Success** - Successful execution paths
4. **Errors** - Error handling
5. **Edge Cases** - Boundary conditions and fallback logic

### Create Focused Test Files
Each concern gets its own test file with a descriptive class:

```python
# test_s3_manager_bucket_verification.py
class TestVerifyBucketExists:
    """Test bucket existence verification."""
    
    @pytest.mark.asyncio
    async def test_verify_bucket_exists_success(self):
        """Test successful bucket verification."""
        # Test implementation
    
    @pytest.mark.asyncio
    async def test_verify_bucket_not_found(self):
        """Test bucket verification when bucket doesn't exist (404)."""
        # Test implementation
```

### Typical Test File Structure

```python
# Copyright header (required)

"""Unit tests for {Module} {concern}."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
# Other imports

from awslabs.lza_mcp_server.{path}.{module} import {Class}


class Test{Concern}:
    """Test {concern description}."""

    @pytest.mark.asyncio  # For async tests
    async def test_{scenario}_success(self):
        """Test successful {scenario}."""
        # Arrange
        # Act
        # Assert
    
    @pytest.mark.asyncio
    async def test_{scenario}_failure(self):
        """Test {scenario} failure."""
        # Arrange
        # Act
        # Assert
```

## Test Implementation Patterns

### Async Tests
Use `@pytest.mark.asyncio` for async functions:

```python
@pytest.mark.asyncio
async def test_async_function(self):
    """Test async function."""
    result = await some_async_function()
    assert result["success"] is True
```

### Mocking AWS SDK Calls
Use `Mock` and `AsyncMock` for AWS SDK operations:

```python
@patch("module.get_aws_session")
async def test_with_aws_mock(self, mock_get_session):
    """Test with mocked AWS session."""
    mock_s3_client = Mock()
    mock_s3_client.head_bucket.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    mock_session = Mock()
    mock_session.client.return_value = mock_s3_client
    mock_get_session.return_value = mock_session
    
    # Test implementation
```

### Testing Error Scenarios
Test both success and error paths:

```python
@pytest.mark.asyncio
async def test_bucket_not_found(self):
    """Test when bucket doesn't exist (404)."""
    mock_s3_client = Mock()
    error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
    mock_s3_client.head_bucket.side_effect = ClientError(error_response, "HeadBucket")
    
    # Verify error handling
    result = await manager.verify_bucket_exists("nonexistent-bucket")
    assert result is False
```

### Testing Custom Exceptions
Verify custom exceptions are raised with correct attributes:

```python
@pytest.mark.asyncio
async def test_access_denied_raises_custom_error(self):
    """Test access denied raises S3UploadError."""
    # Setup mock to raise ClientError
    
    with pytest.raises(S3UploadError) as exc_info:
        await manager.verify_bucket_exists("forbidden-bucket")
    
    assert exc_info.value.error_code == "AccessDenied"
    assert "Access denied" in exc_info.value.message
```

## Running Tests

### Run All Tests
```bash
cd src/lza-mcp-server
poetry run pytest
```

### Run Specific Test Files
```bash
# Single module
poetry run pytest tests/test_s3_manager_init.py -v

# Multiple related files
poetry run pytest tests/test_s3_manager*.py -v

# Specific directory
poetry run pytest tests/tools/config/ -v
```

### Run with Coverage
```bash
# All tests with coverage
poetry run pytest --cov

# Specific module with coverage report
poetry run pytest tests/test_s3_manager*.py -v --cov=awslabs.lza_mcp_server.orchestration.core.s3_manager
```

### Useful Test Options
```bash
# Verbose output
poetry run pytest -v

# Show print statements
poetry run pytest -s

# Stop on first failure
poetry run pytest -x

# Run only failed tests from last run
poetry run pytest --lf

# Show test durations
poetry run pytest --durations=10
```

## Coverage Guidelines

### What to Cover
✅ **High Priority**
- Main execution paths (happy path)
- Error handling and exceptions
- Input validation
- State management
- AWS SDK interactions
- Business logic

✅ **Medium Priority**
- Edge cases with practical impact
- Boundary conditions
- Timeout scenarios
- Retry logic

### What NOT to Worry About
❌ **Low Priority / Acceptable to Skip**
- Unreachable code (dead code that should be removed)
- Complex edge cases that are extremely unlikely
- Defensive programming checks that can't be triggered
- Logging statements
- Pass-through methods with no logic

### Documenting Coverage Gaps
Always document uncovered lines in commit messages:

```
Coverage: 92.82% (138/147 lines covered)
All 28 tests passing

Uncovered lines are edge cases:
- Lines 291-294: Existing directory removal during extraction
- Lines 401-405: Directory listing errors in metadata extraction
- Lines 467-468: Metadata extraction warnings
```

## Example Test Implementations

### Example 1: S3Manager Tests (97.11% coverage)
**Files Created**: 6 test files, 36 tests
- `test_s3_manager_init.py` - Initialization (5 tests)
- `test_s3_manager_bucket_name.py` - Bucket naming (7 tests)
- `test_s3_manager_bucket_verification.py` - Verification (6 tests)
- `test_s3_manager_bucket_validation.py` - Validation (7 tests)
- `test_s3_manager_user_prompts.py` - Prompts (6 tests)
- `test_s3_manager_upload.py` - Upload (5 tests)

**Uncovered**: Size mismatch during verification, verification failure handling

### Example 2: get_config_s3 Tests (92.82% coverage)
**Files Created**: 6 test files, 28 tests
- `test_get_config_s3_init.py` - Initialization (5 tests)
- `test_get_config_s3_connectivity.py` - AWS connectivity (3 tests)
- `test_get_config_s3_validation.py` - Validation (5 tests)
- `test_get_config_s3_success.py` - Success scenarios (2 tests)
- `test_get_config_s3_errors.py` - Error handling (8 tests)
- `test_get_config_s3_metadata.py` - Metadata extraction (5 tests)

**Uncovered**: Directory removal edge cases, metadata extraction warnings

### Example 3: Pipeline Tests (94.71% coverage)
**Files Created**: 5 test files per module, 23 tests each
- `test_{module}_validation.py` - Input validation
- `test_{module}_helpers.py` - Helper functions
- `test_{module}_success.py` - Success scenarios
- `test_{module}_errors.py` - Error handling
- `test_{module}_codebuild.py` - Integration scenarios

**Uncovered**: Unreachable dead code, complex branch conditions

## Best Practices

### 1. Test Isolation
- Each test should be independent
- Use fixtures for common setup
- Clean up resources in teardown or finally blocks

### 2. Clear Test Names
- Use descriptive test method names
- Include the scenario being tested
- Format: `test_{what}_{condition}_{expected_result}`

Examples:
- `test_verify_bucket_exists_success`
- `test_verify_bucket_not_found`
- `test_verify_bucket_access_denied`

### 3. Arrange-Act-Assert Pattern
```python
async def test_example(self):
    """Test example scenario."""
    # Arrange - Set up test data and mocks
    mock_client = Mock()
    mock_client.method.return_value = expected_value
    
    # Act - Execute the code under test
    result = await function_under_test(mock_client)
    
    # Assert - Verify the results
    assert result["success"] is True
    assert result["value"] == expected_value
```

### 4. Mock External Dependencies
- Always mock AWS SDK calls
- Mock file system operations when appropriate
- Mock network calls
- Use `patch` decorator for clean mocking

### 5. Test Error Messages
Verify error messages are helpful:
```python
assert "does not exist" in result["error"]
assert result["error_code"] == "BUCKET_NOT_FOUND"
assert "troubleshooting" in result
```

## Common Pitfalls to Avoid

❌ **Don't**: Create monolithic test files with 100+ tests
✅ **Do**: Split into focused modules by concern

❌ **Don't**: Test implementation details
✅ **Do**: Test behavior and outcomes

❌ **Don't**: Skip error scenarios
✅ **Do**: Test both success and failure paths

❌ **Don't**: Use real AWS resources in tests
✅ **Do**: Mock all AWS SDK calls

❌ **Don't**: Ignore flaky tests
✅ **Do**: Fix or remove unreliable tests

❌ **Don't**: Aim for 100% coverage at all costs
✅ **Do**: Aim for 90%+ with documented gaps

## Continuous Improvement

### When Adding New Features
1. Write tests alongside the feature code
2. Follow the established splitting pattern
3. Aim for 90%+ coverage
4. Document any intentional gaps

### When Fixing Bugs
1. Write a failing test that reproduces the bug
2. Fix the bug
3. Verify the test now passes
4. Add related edge case tests if needed

### When Refactoring
1. Ensure existing tests still pass
2. Update tests if behavior changes
3. Add tests for new code paths
4. Remove tests for deleted code

## Summary

The testing approach in this project prioritizes:
- **Organization**: Split tests by functional concern
- **Coverage**: Aim for 90%+ with pragmatic exceptions
- **Maintainability**: Clear structure and naming
- **Practicality**: Don't obsess over unreachable code
- **Documentation**: Always explain coverage gaps

Follow these patterns for consistent, maintainable, and effective test coverage.
