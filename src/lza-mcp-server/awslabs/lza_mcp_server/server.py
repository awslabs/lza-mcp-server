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

"""AWS Landing Zone Accelerator (LZA) MCP Server implementation."""

import logging
from mcp.server.fastmcp import FastMCP

from .server_config import build_instructions, is_uc_merge_enabled
from .server_registry import register_all_components
from .server_startup import (
    configure_logging,
    get_schema_directory,
    validate_schema_integrity,
)

logger = logging.getLogger(__name__)


def create_mcp_server() -> FastMCP:
    """Create and configure the FastMCP server instance.

    Returns:
        FastMCP: Configured server instance
    """
    instructions = build_instructions()

    return FastMCP(
        "awslabs.lza-mcp-server",
        instructions=instructions,
        dependencies=["pydantic", "PyYAML", "boto3"],
    )


def main():
    """Run the LZA MCP server."""
    # Configure logging
    configure_logging()

    logger.info("Starting LZA MCP Server")

    # Validate schema integrity on startup (T-015)
    schema_dir = get_schema_directory()

    try:
        validate_schema_integrity(schema_dir=schema_dir, fail_on_error=True)
    except ImportError:
        logger.warning("Schema integrity validation module not available")
    except Exception as e:
        logger.error(f"Schema integrity validation failed: {e}")
        raise

    # Create MCP server
    mcp = create_mcp_server()

    # Register all components
    enable_uc_merge = is_uc_merge_enabled()
    register_all_components(mcp, enable_uc_merge)

    # Run the server
    mcp.run()


def runserver():
    """Alternative entry point for the server."""
    main()


if __name__ == "__main__":
    main()
