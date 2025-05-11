# Composable MCP Client with Workflows

This project demonstrates a modular Python client for interacting with MCP (Model Context Protocol) servers. It uses a configuration-driven approach to define workflows that leverage an LLM (Google Gemini via `google-genai`) and various MCP tools.

## Features

*   **Modular Design:** Code is split into logical components for configuration, services, workflow engine, CLI, and logging.
*   **Configuration-Driven:**
    *   `mcp_servers.json`: Define connection details for MCP servers (e.g., weather, Context7).
    *   `workflows.json`: Define different "personalities" or task-specific setups for the LLM, specifying which model to use, which MCP servers (tools) are available, an initial prompt, and conversation turn limits.
*   **MCP Integration:** Connects to and utilizes tools exposed by MCP servers.
*   **LLM Integration:** Uses Google Gemini for natural language understanding and function calling.
*   **Flexible Logging:**
    *   Configurable console log verbosity (`quiet`, `user`, `normal`, `verbose`).
    *   Detailed file logging (`app_client.log`).
    *   Control over third-party library log noise.
*   **Asynchronous Operations:** Built with `asyncio` for efficient I/O.

