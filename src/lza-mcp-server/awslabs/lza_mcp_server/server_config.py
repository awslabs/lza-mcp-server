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


def is_resource_tools_disabled() -> bool:
    """Check if resource workaround tools should be disabled.

    The ``listResources`` and ``readResource`` tools are registered by
    default.  Set ``DISABLE_RESOURCE_TOOLS`` to ``true``, ``1``, or
    ``yes`` to suppress them (e.g. when the MCP client supports native
    resources).

    Returns:
        bool: True if resource tools should be disabled
    """
    return os.environ.get("DISABLE_RESOURCE_TOOLS", "false").lower() in (
        "true",
        "1",
        "yes",
    )


def is_s3_diff_enabled() -> bool:
    """Check if S3 diff retrieval should be enabled.

    When enabled, the tool infers the S3 diff bucket name from the
    deployment context using the naming convention:
    {pipeline-prefix}-diff-{account_id}-{region}

    This supports a planned future LZA feature that exports deployment
    diffs to S3. Since the feature does not exist in any current LZA
    version, this defaults to disabled.

    Returns:
        bool: True if S3 diff retrieval is enabled, False otherwise
    """
    return os.environ.get("ENABLE_S3_DIFF", "false").lower() in (
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


def get_workspace_instructions() -> str:
    """Get workspace instructions.

    Returns:
        str: Workspace instructions text
    """
    return load_instruction_content("workspace_instructions.md")


def get_resource_instructions() -> str:
    """Get resource instructions.

    Returns:
        str: Resource instructions text
    """
    return load_instruction_content("resource_instructions.md")


def build_instructions(
    include_uc_merge: bool | None = None,
    include_workspaces: bool = True,
    include_resources: bool | None = None,
) -> str:
    """Build complete server instructions.

    Args:
        include_uc_merge: Whether to include UC Merge instructions.
                         If None, checks environment variable.
        include_workspaces: Whether to include workspace instructions.
                           Always True since workspaces are always active.
        include_resources: Whether to include resource instructions.
                          If None, True when resource tools are enabled
                          OR when MCP native resources are registered
                          (i.e. always, since native resources are always on).

    Returns:
        str: Complete instructions text
    """
    if include_uc_merge is None:
        include_uc_merge = is_uc_merge_enabled()
    if include_resources is None:
        # Resources are always available — either as native MCP resources
        # or via the fallback listResources/readResource tools.
        include_resources = True

    if is_guidance_disabled():
        return ""

    instructions = get_base_instructions()

    if include_uc_merge:
        instructions += get_uc_merge_instructions()

    if include_workspaces:
        instructions += get_workspace_instructions()

    if include_resources:
        instructions += get_resource_instructions()

    instructions += get_workflow_instructions()

    # Log instructions if enabled
    if is_instruction_logging_enabled():
        logger.info("=" * 80)
        logger.info("MCP SERVER INSTRUCTIONS")
        logger.info("=" * 80)
        logger.info(instructions)
        logger.info("=" * 80)

    return instructions
