# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Timeout utilities for preventing hanging operations (T-005, T-012 mitigation).

This module provides utilities to enforce timeouts on async operations,
preventing indefinite hangs and ensuring responsive behavior.
"""

import asyncio
import functools
import logging
from typing import Any, Callable, TypeVar, Optional

from ..constants import ASYNC_OPERATION_TIMEOUT, FILE_OPERATION_TIMEOUT

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TimeoutError(Exception):
    """Raised when an operation exceeds its timeout limit."""

    pass


async def with_timeout(
    coro: Any, timeout: float, operation_name: str = "operation"
) -> Any:
    """
    Execute an async operation with a timeout.

    Args:
        coro: Coroutine to execute
        timeout: Maximum seconds to wait
        operation_name: Name of operation for error messages

    Returns:
        Result of the coroutine

    Raises:
        TimeoutError: If operation exceeds timeout
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        error_msg = f"{operation_name} exceeded timeout of {timeout} seconds"
        logger.error(error_msg)
        raise TimeoutError(error_msg)


def timeout_decorator(
    timeout: Optional[float] = None, operation_name: Optional[str] = None
):
    """
    Decorator to add timeout protection to async functions.

    Args:
        timeout: Maximum seconds to wait (defaults to ASYNC_OPERATION_TIMEOUT)
        operation_name: Name of operation for error messages (defaults to function name)

    Example:
        @timeout_decorator(timeout=30, operation_name="S3 upload")
        async def upload_file(ctx, file_path):
            # Function implementation
            pass
    """
    timeout_value = timeout or ASYNC_OPERATION_TIMEOUT

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs), timeout=timeout_value
                )
            except asyncio.TimeoutError:
                error_msg = f"{op_name} exceeded timeout of {timeout_value} seconds"
                logger.error(error_msg)
                raise TimeoutError(error_msg)

        return wrapper

    return decorator


async def run_with_file_timeout(coro: Any, operation_name: str = "file operation") -> Any:
    """
    Execute a file I/O operation with appropriate timeout.

    Args:
        coro: Coroutine to execute
        operation_name: Name of operation for error messages

    Returns:
        Result of the coroutine

    Raises:
        TimeoutError: If operation exceeds FILE_OPERATION_TIMEOUT
    """
    return await with_timeout(coro, FILE_OPERATION_TIMEOUT, operation_name)


async def run_with_aws_timeout(coro: Any, operation_name: str = "AWS operation") -> Any:
    """
    Execute an AWS operation with appropriate timeout.

    Args:
        coro: Coroutine to execute
        operation_name: Name of operation for error messages

    Returns:
        Result of the coroutine

    Raises:
        TimeoutError: If operation exceeds ASYNC_OPERATION_TIMEOUT
    """
    return await with_timeout(coro, ASYNC_OPERATION_TIMEOUT, operation_name)


class TimeoutContext:
    """
    Context manager for operations that need timeout protection.

    Example:
        async with TimeoutContext(30, "database query") as ctx:
            result = await perform_query()
    """

    def __init__(self, timeout: float, operation_name: str = "operation"):
        """
        Initialize timeout context.

        Args:
            timeout: Maximum seconds to wait
            operation_name: Name of operation for error messages
        """
        self.timeout = timeout
        self.operation_name = operation_name
        self._task = None

    async def __aenter__(self):
        """Enter the context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the context and check for timeout."""
        if exc_type is asyncio.TimeoutError:
            error_msg = (
                f"{self.operation_name} exceeded timeout of {self.timeout} seconds"
            )
            logger.error(error_msg)
            raise TimeoutError(error_msg)
        return False
