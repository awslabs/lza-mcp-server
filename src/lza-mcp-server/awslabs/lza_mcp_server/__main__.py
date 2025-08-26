#!/usr/bin/env python3
"""
Main entry point for the LZA MCP Server package when executed with -m
"""

import sys
import os
from loguru import logger

# Configure logging
log_level = os.environ.get("FASTMCP_LOG_LEVEL", "INFO")
logger.remove()
logger.add(sys.stderr, level=log_level)

if __name__ == "__main__":
    # Call the main function from server.py
    main()