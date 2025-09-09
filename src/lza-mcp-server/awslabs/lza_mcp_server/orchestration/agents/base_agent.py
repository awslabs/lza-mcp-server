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

"""Base agent class for LZA orchestration system."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Callable
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


@dataclass
class AgentCapability:
    """Defines an agent's capability with associated tools and expertise domain."""

    name: str
    description: str
    tools: List[str]
    expertise_domain: str


class BaseAgent(ABC):
    """Abstract base class for all LZA orchestration agents.

    This class provides the core interface and functionality that all specialized
    agents must implement. It handles tool registry initialization from existing
    FastMCP tools and defines the contract for task execution and query handling.
    """

    def __init__(self, name: str, capabilities: List[AgentCapability]):
        """Initialize the base agent.

        Args:
            name: Unique name for this agent
            capabilities: List of capabilities this agent provides
        """
        self.name = name
        self.capabilities = capabilities
        self.tool_registry: Dict[str, Callable] = {}
        self._expertise_domains = [cap.expertise_domain for cap in capabilities]
        self._tool_names = []
        for cap in capabilities:
            self._tool_names.extend(cap.tools)

        logger.info(f"Initialized agent '{name}' with {len(capabilities)} capabilities")

    def initialize_tools(self, mcp_server: FastMCP) -> None:
        """Initialize tool registry from existing FastMCP tools.

        This method extracts the relevant tools from the FastMCP server instance
        and makes them available to the agent for execution.

        Args:
            mcp_server: The FastMCP server instance containing registered tools
        """
        if not hasattr(mcp_server, "_tools"):
            logger.warning(f"MCP server has no tools registered for agent {self.name}")
            return

        # Extract tools that this agent is responsible for
        for tool_name in self._tool_names:
            if tool_name in mcp_server._tools:
                self.tool_registry[tool_name] = mcp_server._tools[tool_name]
                logger.debug(f"Registered tool '{tool_name}' for agent '{self.name}'")
            else:
                logger.warning(
                    f"Tool '{tool_name}' not found in MCP server for agent '{self.name}'"
                )

        logger.info(
            f"Agent '{self.name}' initialized with {len(self.tool_registry)} tools"
        )

    @abstractmethod
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task using the agent's capabilities.

        Args:
            task: Dictionary containing task details including:
                - tool_name: Name of the tool to execute
                - parameters: Parameters to pass to the tool
                - context: Additional context for task execution

        Returns:
            Dictionary containing task execution results

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        pass

    @abstractmethod
    def can_handle(self, query: str) -> float:
        """Determine if this agent can handle the given query.

        Args:
            query: User query or task description

        Returns:
            Confidence score between 0.0 and 1.0 indicating how well
            this agent can handle the query

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        pass

    def get_available_tools(self) -> List[str]:
        """Get list of tools available to this agent.

        Returns:
            List of tool names this agent can execute
        """
        return list(self.tool_registry.keys())

    def get_capabilities(self) -> List[AgentCapability]:
        """Get list of capabilities this agent provides.

        Returns:
            List of AgentCapability objects
        """
        return self.capabilities.copy()

    def get_expertise_domains(self) -> List[str]:
        """Get list of expertise domains this agent covers.

        Returns:
            List of expertise domain names
        """
        return self._expertise_domains.copy()

    async def validate_task(self, task: Dict[str, Any]) -> bool:
        """Validate that a task can be executed by this agent.

        Args:
            task: Task dictionary to validate

        Returns:
            True if task is valid and can be executed, False otherwise
        """
        if not isinstance(task, dict):
            logger.error(f"Task must be a dictionary, got {type(task)}")
            return False

        tool_name = task.get("tool_name")
        if not tool_name:
            logger.error("Task missing required 'tool_name' field")
            return False

        if tool_name not in self.tool_registry:
            logger.error(f"Tool '{tool_name}' not available in agent '{self.name}'")
            return False

        return True

    def __str__(self) -> str:
        """String representation of the agent."""
        return f"{self.__class__.__name__}(name='{self.name}', tools={len(self.tool_registry)})"

    def __repr__(self) -> str:
        """Detailed string representation of the agent."""
        return (
            f"{self.__class__.__name__}("
            f"name='{self.name}', "
            f"capabilities={len(self.capabilities)}, "
            f"tools={list(self.tool_registry.keys())})"
        )
