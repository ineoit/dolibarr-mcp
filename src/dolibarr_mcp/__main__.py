#!/usr/bin/env python3
"""Main entry point for the Dolibarr MCP server module."""

import os
import sys

# Add the src directory to the Python path if needed
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import asyncio

from dolibarr_mcp.dolibarr_mcp_server import main

if __name__ == "__main__":
    asyncio.run(main())
