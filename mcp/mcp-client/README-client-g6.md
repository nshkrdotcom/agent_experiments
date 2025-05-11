# MCP Client (client-g6.py)

Below is a comprehensive `README.md` for your `client-g6.py` MCP client, which connects to MCP servers like the provided `weather.py` server using a configuration-driven approach. The README includes:

* An overview of the client and its purpose.
* Use cases for interacting with MCP servers.
* Detailed commands for running the client.
* A thorough explanation of the `.mcp.json` configuration file structure, including required and optional fields.
* Limitations of the current implementation to clarify compatible server types and potential constraints.
* Installation and setup instructions.

This README is designed to be user-friendly, technically precise, and informative for developers looking to use or extend the client.

## Overview

`client-g6.py` is a Python-based Model Context Protocol (MCP) client that connects to MCP servers, such as the provided weather server (`weather.py`), to execute tools and process queries using the Google Generative AI (GenAI) SDK. The client supports a configuration-driven approach, allowing users to define server connections in a `.mcp.json` file or specify server scripts directly via the command line. It is designed for flexibility, enabling interaction with various MCP servers that provide tools for tasks like fetching weather forecasts, alerts, or documentation.

### Features

* **Configuration-Driven:** Load server configurations from a `.mcp.json` file for easy management of multiple MCP servers.
* **CLI Flexibility:** Connect to servers via configured server names or direct script paths.
* **GenAI Integration:** Uses the Google GenAI SDK to process queries and call MCP tools intelligently.
* **Robust Logging:** Detailed debug logs (`client_debug.log`) for troubleshooting.
* **Extensible Design:** Modular structure supports adding new transport types or server configurations.

## Use Cases

* **Weather Information Retrieval:**
    * Query the weather server for forecasts or alerts, e.g., "What's the forecast for New York?" or "Are there any weather alerts in California?"
    * Tools: `get_forecast (latitude, longitude)` and `get_alerts (state code)`.
* **Documentation Fetching:**
    * Connect to servers like Context7 MCP to retrieve up-to-date library documentation, e.g., "Get documentation for Next.js routing."
* **Custom MCP Servers:**
    * Interact with any MCP server that exposes tools via the `stdio` transport protocol, provided the tools have compatible input schemas.
* **Development and Testing:**
    * Test and debug custom MCP servers by connecting and invoking their tools interactively.

## Installation

### Prerequisites

* **Python:** Version 3.8 or higher.
* **Node.js (optional):** Required for JavaScript-based MCP servers (e.g., Context7).
* **Google API Key:** A valid `GOOGLE_API_KEY` or `GEMINI_API_KEY` for the Google GenAI SDK.

### Setup

1.  **Clone the Repository (if applicable):**
    ```bash
    git clone <repository-url>
    cd mcp-client
    ```
2.  **Create a Virtual Environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```
3.  **Install Dependencies:**
    ```bash
    pip install mcp google-generativeai httpx python-dotenv
    ```
4.  **Set Up Environment Variables:**
    Create a `.env` file in the project directory with your Google API key:
    ```bash
    echo "GOOGLE_API_KEY=your_api_key_here" > .env
    ```
5.  **Prepare the Configuration File:**
    Create a `.mcp.json` file in the project directory (`mcp-client/.mcp.json`) or in `~/.mcp/mcp.json`. See Configuration File Structure (#configuration-file-structure) for details.

## Usage

### Commands

The client can be run in two modes: configuration-driven (using a server name from `.mcp.json`) or script-based (specifying a server script directly).

* **Run with a Configured Server:**
    Connect to a server defined in `.mcp.json`:
    ```bash
    python client-g6.py --server weather
    ```
    Example output:
    ```
    Available servers: ['weather', 'context7']
    Connected to server with tools: ['get_alerts', 'get_forecast']

    MCP Client (Google GenAI SDK Edition) Started!
    Using Gemini model: gemini-2.5-flash-preview-04-17
    Type your queries or 'quit' to exit.

    Query:
    ```
* **Run with a Script Path:**
    Connect to a server by specifying its script directly (legacy mode):
    ```bash
    python client-g6.py --script ../weather/weather.py
    ```
    This bypasses `.mcp.json` and runs the specified script (Python or JavaScript).
* **Use a Custom Configuration File:**
    Specify a custom `.mcp.json` file:
    ```bash
    python client-g6.py --server weather --config /path/to/custom/.mcp.json
    ```

### Interactive Queries

Once connected, enter queries like:
* "What's the weather forecast for 40.7128,-74.0060?" (New York City coordinates).
* "Are there any weather alerts in CA?"

Type `quit` to exit.

### Example Workflow

1.  Ensure `.mcp.json` is set up with the weather server:
    ```json
    {
      "mcpServers": {
        "weather": {
          "command": "python",
          "args": ["../weather/weather.py"],
          "env": {
            "PYTHONPATH": "."
          },
          "transportType": "stdio",
          "description": "Weather MCP server for fetching forecasts and alerts"
        }
      }
    }
    ```
2.  Run the client:
    ```bash
    python client-g6.py --server weather
    ```
3.  Query the server:
    ```
    Query: What's the weather in New York?
    [LLM wants to call tool 'get_forecast' with args: {'latitude': 40.7128, 'longitude': -74.0060}]
    [Tool 'get_forecast' executed. Result: <forecast details>]
    The weather forecast for New York is: <formatted forecast>
    ```

## Configuration File Structure

The `.mcp.json` file defines MCP server configurations. It can be placed in:

* The project directory (`mcp-client/.mcp.json` or `mcp-client/mcp.json`).
* The user home directory (`~/.mcp/mcp.json`).

### Structure

```json
{
  "mcpServers": {
    "<server_name>": {
      "command": "<executable>",
      "args": ["<arg1>", "<arg2>", ...],
      "env": {
        "<key>": "<value>",
        ...
      },
      "transportType": "<transport>",
      "description": "<description>"
    },
    ...
  }
}
```

### Fields

* **Required**
    * `mcpServers`: A dictionary mapping server names (e.g., `weather`, `context7`) to their configurations.
    * `command` (per server): The executable to run the server (e.g., `python`, `node`, `npx`).
    * `args` (per server): A list of arguments to pass to the command (e.g., `["../weather/weather.py"]`).
* **Optional**
    * `env` (per server): A dictionary of environment variables to set when running the server (e.g., `{"PYTHONPATH": "."}`).
    * `transportType` (per server): The transport protocol for communication. Defaults to `stdio`. Currently, only `stdio` is supported.
    * `description` (per server): A human-readable description of the server (e.g., "Weather MCP server for fetching forecasts and alerts").

### Example

```json
{
  "mcpServers": {
    "weather": {
      "command": "python",
      "args": ["../weather/weather.py"],
      "env": {
        "PYTHONPATH": "."
      },
      "transportType": "stdio",
      "description": "Weather MCP server for fetching forecasts and alerts"
    },
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp@latest"],
      "env": {
        "DEFAULT_MINIMUM_TOKENS": "10000"
      },
      "transportType": "stdio",
      "description": "Context7 MCP server for up-to-date documentation"
    }
  }
}
```

### Notes

* **Server Names:** Must be unique within `mcpServers`.
* **File Locations:** The client searches for `.mcp.json` or `mcp.json` in the current directory, then `~/.mcp/mcp.json`. A custom path can be specified with `--config`.
* **Validation:** The client validates the JSON structure and required fields, logging errors to `client_debug.log` if issues are found.

## Limitations

The current implementation of `client-g6.py` has some constraints that affect the types of MCP servers it can interact with and its overall functionality. These are important to understand when deploying or extending the client.

* **Transport Protocol:**
    * **Limitation:** Only supports the `stdio` transport protocol.
    * **Impact:** Servers using other transports (e.g., `tcp`, `websocket`) are not compatible without extending the `connect_to_server` method.
    * **Compatible Servers:** Servers like `weather.py` (Python, stdio) or Context7 (JavaScript, stdio via npx).
* **Tool Schema Compatibility:**
    * **Limitation:** The `_convert_mcp_tool_to_genai_function_declaration` method assumes MCP tools have a JSON Schema-compatible `inputSchema` with `properties` and `required` fields.
    * **Impact:** Servers with non-standard or malformed tool schemas may cause warnings or failures when converting to GenAI function declarations.
    * **Workaround:** The client logs warnings for invalid schemas and defaults to string types, but complex schemas may require manual adjustments.
* **Single Server Connection:**
    * **Limitation:** The client connects to one server at a time.
    * **Impact:** Cannot route queries across multiple servers or use tools from different servers in a single session.
    * **Future Enhancement:** Add support for multiple concurrent server connections and tool routing.
* **GenAI Dependency:**
    * **Limitation:** Relies on the Google GenAI SDK and a specific model (`gemini-2.5-flash-preview-04-17`).
    * **Impact:** Requires a valid API key and internet access. Model availability or deprecation could break the client.
    * **Workaround:** Update `DEFAULT_GEMINI_MODEL` if the model changes, or extend to support other LLMs.
* **Error Handling:**
    * **Limitation:** While robust, some edge cases (e.g., server crashes, malformed tool responses) may result in generic error messages.
    * **Impact:** Debugging complex issues requires checking `client_debug.log`.
    * **Workaround:** Enhance error handling for specific MCP protocol errors.
* **Platform Dependencies:**
    * **Limitation:** Assumes `python` or `node` executables are available for running server scripts.
    * **Impact:** Servers requiring other runtimes (e.g., Deno, Bun) or Docker containers are not supported without modifying the configuration.
    * **Workaround:** Extend `connect_to_server` to support additional runtimes or Docker.
* **Cleanup Issues:**
    * **Limitation:** Occasional anyio errors during cleanup (`RuntimeError: Attempted to exit cancel scope in a different task`) indicate potential issues with `AsyncExitStack` management.
    * **Impact:** May leave resources open in rare cases.
    * **Workaround:** The cleanup method includes error handling, but further investigation into `mcp` and `anyio` interactions may be needed.

## Compatible Servers

The client works with MCP servers that:

* Use the `stdio` transport protocol.
* Expose tools with JSON Schema-compatible `inputSchema` (e.g., `properties`, `required` fields).
* Are executable via `python` or `node` (or other runtimes if configured).

Examples:

* `weather.py`: A Python-based server providing `get_alerts` and `get_forecast` tools.
* Context7 MCP: A JavaScript-based server (via `npx`) for documentation retrieval.

## Troubleshooting

* **Configuration Not Found:**
    * Ensure `.mcp.json` or `mcp.json` exists in `mcp-client/` or `~/.mcp/`.
    * Verify the server name matches an entry in `mcpServers`.
* **Connection Refused:**
    * Check that the server script (e.g., `../weather/weather.py`) exists and is executable.
    * Confirm dependencies (`mcp`, `httpx`) are installed for the server.
* **GenAI Errors:**
    * Verify `GOOGLE_API_KEY` is set in `.env` or the environment.
    * Ensure the Gemini model is accessible with your API key.
* **Logs:**
    * Check `client_debug.log` in the project directory for detailed error messages.

## Development

### Extending the Client

To support additional features:

* **New Transport Types:**
    * Modify `connect_to_server` to handle `tcp` or other transports.
    * Example: Add logic for TCP connections using `asyncio.open_connection`.
* **Multiple Servers:**
    * Extend `MCPClient` to manage multiple `ClientSession` instances and route queries based on tool availability.
* **Custom LLMs:**
    * Replace or augment the Google GenAI SDK with other LLM providers (e.g., OpenAI, Anthropic).

### Testing

* Test with the included weather server:
    ```bash
    python client-g6.py --server weather
    ```
    Query examples:
    * "Get weather alerts for CA"
    * "Forecast for 37.7749,-122.4194" (San Francisco coordinates)
* Test with a script path:
    ```bash
    python client-g6.py --script ../weather/weather.py
    ```

### Debugging

* Enable verbose logging by ensuring `logging.basicConfig(level=logging.DEBUG)` in `client-g6.py`.
* Inspect `client_debug.log` for detailed traces.
* Use `--config` to test alternative `.mcp.json` files.

## License

MIT
