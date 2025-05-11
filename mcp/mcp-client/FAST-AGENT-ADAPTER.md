You're asking a great question that gets to the heart of how `fast-agent` abstracts away some of the manual MCP client management you were doing.

In your project, you had:
1.  `mcp_servers.json`: To define how to *start* MCP servers.
2.  `config.py`: To load this JSON.
3.  `services.py` (`MCPService` class): To encapsulate the logic for connecting to a *running* MCP server subprocess, listing its tools, and calling them.
4.  `engine.py` (`WorkflowEngine`): To instantiate `MCPService` objects based on the `mcp_servers_used` in `workflows.json` and then use those services.

`fast-agent` simplifies this by making it more declarative and handling the subprocess management and connection internally.

Here's how you would "add MCP clients" (or rather, configure MCP servers for your agents to use) in `fast-agent`:

**1. Define Your MCP Servers in `fastagent.config.yaml`**

Instead of `mcp_servers.json`, you define your MCP servers in `fastagent.config.yaml` under the `mcp.servers` key. The structure is very similar.

Let's take your `mcp_servers.json`:
```json
{
  "mcpServers": {
    "weather": {
      "command": "python",
      "args": ["../weather/weather.py"],
      "env": {"PYTHONPATH": "."},
      "description": "Weather MCP server"
    },
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp@latest"],
      "env": {"DEFAULT_MINIMUM_TOKENS": "10000"},
      "description": "Context7 MCP server"
    }
  }
}
```

This translates to `fastagent.config.yaml` like this:

```yaml
# fastagent.config.yaml

# ... other configurations (LLM API keys go in fastagent.secrets.yaml) ...

mcp:
  servers:
    weather: # This is the 'server_name' you'll use in your agent decorator
      transport: stdio   # Your project used stdio
      command: python
      args:
        - ../weather/weather.py # Ensure this path is correct relative to where fast-agent runs
      env:
        PYTHONPATH: "."
      # description: "Weather MCP server" # Optional, more for human readability here

    context7: # This is another 'server_name'
      transport: stdio
      command: npx
      args:
        - -y
        - "@upstash/context7-mcp@latest"
      env:
        DEFAULT_MINIMUM_TOKENS: "10000"
      # description: "Context7 MCP server"

    # You can add other types of servers too:
    # my_sse_server:
    //    transport: sse
    //    url: "http://localhost:8001/mcp/sse" # Example SSE server URL
    #    headers:
    //      Authorization: "Bearer your_token_if_needed"

    # my_http_server:
    //    transport: http
    //    url: "http://localhost:8002/mcp" # Example HTTP server URL
```

**Key Points for Configuration:**
*   **`transport: stdio`**: This corresponds to how your `MCPService` was set up (using `StdioServerParameters`). `fast-agent` also supports `sse` and `http`.
*   **`command` and `args`**: Same as your JSON. These tell `fast-agent` how to *start* the MCP server if it's a subprocess.
*   **`env`**: Same as your JSON.
*   **The keys under `servers:` (`weather`, `context7`) are the crucial `server_name` identifiers.**

**2. Tell Your Agent Which Servers to Use**

In your Python file where you define your agent using the `@fast.agent` decorator, you pass the list of server names to the `servers` parameter.

```python
# agent_file.py
import asyncio
from mcp_agent.core.fastagent import FastAgent
from mcp_agent.core.request_params import RequestParams

# Assume you have fastagent.config.yaml and fastagent.secrets.yaml in the same directory or a parent.
fast = FastAgent("MyMCPInteractingApp")

@fast.agent(
    name="multitool_assistant",
    instruction="You are a helpful assistant that can check weather and search docs.",
    model="openai.gpt-4.1-mini", # Or your preferred model
    servers=["weather", "context7"] # <--- THIS IS THE KEY PART
                                    # These names MUST match the keys in fastagent.config.yaml
)
async def run_my_agent():
    async with fast.run() as app:
        # Now app.multitool_assistant can use tools from 'weather' and 'context7'
        response = await app.multitool_assistant.send(
            "What's the weather in London and how do I use the 'phoenix framework'?"
        )
        print(response)

if __name__ == "__main__":
    asyncio.run(run_my_agent())
```

**What `fast-agent` Does Internally (replacing your `MCPService` and parts of `WorkflowEngine`):**

1.  **Loading Config:** When `FastAgent` is initialized, it loads `fastagent.config.yaml`. The `MCPServerRegistry` (part of the `Context`) parses the `mcp.servers` section.
2.  **Agent Initialization (`fast.run()`):**
    *   When an agent like `multitool_assistant` is created (because it's decorated and `fast.run()` is entered), `fast-agent` looks at its `servers=["weather", "context7"]` argument.
    *   For each server name, it uses the `MCPServerRegistry` and `MCPConnectionManager` to:
        *   If `transport: stdio`, start the subprocess defined by `command` and `args`.
        *   Establish a connection (stdio, SSE, or HTTP) to that MCP server.
        *   Perform the MCP `initialize` handshake.
        *   The agent instance internally gets an `MCPAggregator` which holds these active `ClientSession`s.
3.  **Tool Availability & LLM Interaction:**
    *   The `Agent`'s `AugmentedLLM` instance will use its `MCPAggregator` to call `list_tools()` on all connected/configured servers ("weather" and "context7" in this case).
    *   The tools from both servers (e.g., `weather-get_forecast`, `context7-resolve-library-id`) are collected.
    *   The LLM provider (e.g., `OpenAIAugmentedLLM`) converts these tools into the format its API expects (e.g., OpenAI Function Calling JSON schema).
    *   When the LLM decides to call a tool (e.g., `weather-get_forecast`), the `AugmentedLLM` tells its `MCPAggregator` to `call_tool("weather-get_forecast", {...args...})`.
    *   The `MCPAggregator` knows that `weather-get_forecast` belongs to the "weather" server and routes the call to the correct `ClientSession`.

**You DO NOT Need to:**

*   Write a class like your `MCPService`. `fast-agent` handles the connection, subprocess management (for stdio), and session lifecycle.
*   Manually instantiate server connection objects in your agent logic.
*   Manually call `connect()`, `list_tools()`, or `session.initialize()` for each MCP server.

**In essence, you declare *what* MCP servers exist and *which* agents use them in the configuration and decorators, and the `fast-agent` framework handles the *how* of connecting and making them available to the LLM.**

### Mermaid Diagram: `fast-agent` MCP Server Integration

```mermaid
graph TD
    subgraph Configuration ["fastagent.config.yaml"]
        YAML_MCP["mcp:"] --> YAML_Servers["  servers:"];
        YAML_Servers --> YAML_Weather["    weather:<br>      transport: stdio<br>      command: python<br>      args: [...]"];
        YAML_Servers --> YAML_Context7["    context7:<br>      transport: stdio<br>      command: npx<br>      args: [...]"];
    end

    subgraph PythonCode ["agent_file.py"]
        FastAgentInit["fast = FastAgent(...)"] --> Decorator["@fast.agent('my_agent', servers=['weather', 'context7'])"];
        Decorator --> RunBlock["async with fast.run() as app:"];
        RunBlock --> AgentCall["app.my_agent.send(...)"];
    end

    subgraph FastAgentInternals
        Context["Context"]
        MCPRegistry["MCPServerRegistry"]
        MCPConnMgr["MCPConnectionManager"]
        MyAgentInstance["'my_agent' Instance"]
        AugLLM["AugmentedLLM (for 'my_agent')"]
        MCPAgg["MCPAggregator (for 'my_agent')"]
    end

    subgraph ExternalMCP ["External MCP Servers"]
        WeatherServer["Weather Server Process (stdio)"]
        Context7Server["Context7 Server Process (stdio)"]
    end

    FastAgentInit -->|Loads| YAML_MCP;
    RunBlock -->|Triggers Initialization| Context;
    Context -.->|Contains| MCPRegistry;
    Context -.->|Contains| MCPConnMgr;

    Decorator -->|Defines which servers to use| MyAgentInstance;
    MyAgentInstance -->|Uses| AugLLM;
    AugLLM -->|Uses| MCPAgg;

    MCPRegistry -- Reads --> YAML_Servers;
    MCPAgg -- Uses Config from --> MCPRegistry;
    MCPAgg -- Uses Connections via --> MCPConnMgr;

    MCPConnMgr -- Spawns & Connects to --> WeatherServer;
    MCPConnMgr -- Spawns & Connects to --> Context7Server;

    AugLLM -->|Gets Tools for LLM| MCPAgg;
    MCPAgg -->|"list_tools()"| WeatherServer;
    MCPAgg -->|"list_tools()"| Context7Server;

    AgentCall --> MyAgentInstance;
    MyAgentInstance --> AugLLM;
    AugLLM -->|LLM decides tool_call| MCPAgg;
    MCPAgg -->|"call_tool('weather-get_forecast', ...)"| WeatherServer;
    MCPAgg -->|"call_tool('context7-get_library_docs', ...)"| Context7Server;
```

This setup allows you to focus on the agent's instruction and logic, while `fast-agent` handles the underlying MCP plumbing based on your declarative configuration. Your "workflows" from `workflows.json` would translate into different `@fast.agent` (or other workflow decorators like `@fast.orchestrator`) definitions in Python.
