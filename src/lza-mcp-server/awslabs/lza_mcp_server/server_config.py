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

"""Server configuration and instructions builder."""

import logging
import os

from awslabs.lza_mcp_server.utils.guidance_toggle import is_guidance_disabled
from awslabs.lza_mcp_server.utils.load_instruction_content import (
    load_instruction_content,
)

logger = logging.getLogger(__name__)


def is_uc_merge_enabled() -> bool:
    """Check if UC Merge tools should be enabled.

    Returns:
        bool: True if UC Merge is enabled, False otherwise
    """
    return os.environ.get("ENABLE_UC_MERGE", "false").lower() in (
        "true",
        "1",
        "yes",
    )


def is_instruction_logging_enabled() -> bool:
    """Check if instruction logging should be enabled.

    Returns:
        bool: True if instruction logging is enabled, False otherwise
    """
    return os.environ.get("LOG_INSTRUCTIONS", "false").lower() in (
        "true",
        "1",
        "yes",
    )


def get_base_instructions() -> str:
    """Get base server instructions.

    Returns:
        str: Base instructions text
    """
    return load_instruction_content("base_instructions.md")


def get_uc_merge_instructions() -> str:
    """Get UC Merge tools instructions.

    Returns:
        str: UC Merge instructions text
    """
    return load_instruction_content("uc_merge_instructions.md")


def get_workflow_instructions() -> str:
    """Get workflow instructions.

    Returns:
        str: Workflow instructions text
    """
    return load_instruction_content("workflow_instructions.md")


def build_instructions(include_uc_merge: bool = None) -> str:
    """Build complete server instructions.

    Args:
        include_uc_merge: Whether to include UC Merge instructions.
                         If None, checks environment variable.

    Returns:
        str: Complete instructions text
    """
    if include_uc_merge is None:
        include_uc_merge = is_uc_merge_enabled()

    if is_guidance_disabled():
        return ""

    instructions = get_base_instructions()

    if include_uc_merge:
        instructions += get_uc_merge_instructions()

    instructions += get_workflow_instructions()

    # Log instructions if enabled
    if is_instruction_logging_enabled():
        logger.info("=" * 80)
        logger.info("MCP SERVER INSTRUCTIONS")
        logger.info("=" * 80)
        logger.info(instructions)
        logger.info("=" * 80)

    return instructions
