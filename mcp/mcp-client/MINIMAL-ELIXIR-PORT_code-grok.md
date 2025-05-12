Below is a detailed guide to porting the provided Python-based system (`services.py`, `engine.py`, `config.py`, `cli.py`, and `app_logger.py`) to Elixir/Phoenix, with a focus on leveraging OTP principles and establishing a clean supervision structure suitable for this system. This response translates the core components into Elixir equivalents, ensuring fault tolerance, concurrency, and maintainability using OTP constructs like Supervisors and GenServers.

## Overview of the Python System

The Python system consists of several key components:

* `AppConfig` (`config.py`): Loads and validates JSON configuration files for MCP servers and workflows.
* `MCPService` (`services.py`): Manages connections to MCP servers and executes tool calls.
* `LLMService` (`services.py`): Interfaces with the Google GenAI API for language model interactions.
* `WorkflowEngine` (`engine.py`): Orchestrates interactions between the LLM and MCP tools based on workflow configurations.
* `CLI` (`cli.py`): Provides a command-line interface for user interaction.
* `Logging` (`app_logger.py`): Handles configurable logging across components.

In Elixir, we'll map these components to OTP constructs, ensuring a robust supervision tree for fault tolerance and leveraging Elixir's concurrency model.

## Supervision Tree Design

A clean supervision tree is essential for fault tolerance and modularity in Elixir. Here's the proposed structure:

* **Top-Level Supervisor** (`MyApp.Supervisor`): Oversees the entire application.
* **Config Supervisor**: Manages configuration loading and state.
* **MCP Supervisor**: Dynamically supervises MCP server connections.
* **LLM Supervisor**: Manages the LLM service.
* **Workflow Supervisor**: Dynamically supervises workflow instances (optional for CLI-driven sessions).

This structure isolates failures (e.g., an MCP connection crash won't affect the LLM service) and supports dynamic process creation for scalability.

## Component Implementation in Elixir

### 1. AppConfig

* **Purpose**: Loads and validates configuration files (`mcp_servers.json` and `workflows.json`) and provides access to them.
* **Elixir Approach**: Use a `GenServer` to manage configuration state, loaded at application startup. This allows dynamic access and potential updates.
* **Code**:

```elixir
defmodule MyApp.AppConfig do
  use GenServer
  require Logger

  def start_link(config_path) do
    GenServer.start_link(__MODULE__, config_path, name: __MODULE__)
  end

  def init(config_path) do
    mcp_servers = load_json(Path.join(config_path, "mcp_servers.json"), "mcpServers")
    workflows = load_json(Path.join(config_path, "workflows.json"), "workflows")
    validate_configs(mcp_servers, workflows)
    Logger.info("Application configuration loaded successfully")
    {:ok, %{mcp_servers: mcp_servers, workflows: workflows}}
  end

  def get_mcp_server_config(server_name) do
    GenServer.call(__MODULE__, {:get_mcp_server, server_name})
  end

  def get_workflow_config(workflow_name) do
    GenServer.call(__MODULE__, {:get_workflow, workflow_name})
  end

  # Call handlers
  def handle_call({:get_mcp_server, server_name}, _from, state) do
    case Map.get(state.mcp_servers, server_name) do
      nil ->
        Logger.warn("MCP Server '#{server_name}' not defined")
        {:reply, {:error, :not_found}, state}
      config ->
        {:reply, {:ok, config}, state}
    end
  end

  def handle_call({:get_workflow, workflow_name}, _from, state) do
    case Map.get(state.workflows, workflow_name) do
      nil ->
        Logger.warn("Workflow '#{workflow_name}' not defined")
        {:reply, {:error, :not_found}, state}
      config ->
        {:reply, {:ok, config}, state}
    end
  end

  defp load_json(file_path, expected_key) do
    with {:ok, body} <- File.read(file_path),
         {:ok, data} <- Jason.decode(body, keys: :atoms),
         config when is_map(config) <- Map.get(data, String.to_atom(expected_key)) do
      config
    else
      _ ->
        Logger.error("Failed to load or parse #{file_path}")
        raise "Configuration loading failed"
    end
  end

  defp validate_configs(mcp_servers, workflows) do
    # Validate MCP servers
    Enum.each(mcp_servers, fn {name, config} ->
      unless Map.has_key?(config, :command) && is_list(config.command),
        do: raise("Invalid MCP server config for '#{name}'")
    end)

    # Validate workflows
    Enum.each(workflows, fn {name, config} ->
      required = [:llm_model, :mcp_servers_used, :initial_prompt_template, :max_conversation_turns]
      Enum.each(required, fn key ->
        unless Map.has_key?(config, key),
          do: raise("Workflow '#{name}' missing '#{key}'")
      end)
    end)
  end
end
```

* **Notes**:
    * Uses `Jason` for JSON parsing (add `{ :jason, "~> 1.4" }` to `mix.exs`).
    * Configuration is stored in a `GenServer` state, accessible via synchronous calls.
    * Validation ensures required fields are present, mirroring Python logic.

### 2. MCPService

* **Purpose**: Manages connections to individual MCP servers and executes tool calls.
* **Elixir Approach**: Each MCP connection becomes a `GenServer`, dynamically supervised by a `DynamicSupervisor`. This isolates connections and allows independent restarts.

* **MCP Connection GenServer**:

```elixir
defmodule MyApp.MCPConnection do
  use GenServer
  require Logger

  def start_link(server_config) do
    GenServer.start_link(__MODULE__, server_config)
  end

  def init(server_config) do
    Logger.info("Connecting to MCP server: #{server_config.server_name}")
    {:ok, port} = connect_to_mcp(server_config)
    {:ok, %{config: server_config, port: port, tools: nil}}
  end

  def call_tool(pid, tool_name, args) do
    GenServer.call(pid, {:call_tool, tool_name, args})
  end

  def get_tools(pid) do
    GenServer.call(pid, :get_tools)
  end

  def handle_call(:get_tools, _from, state) do
    if state.tools do
      {:reply, state.tools, state}
    else
      tools = fetch_tools(state.port)
      {:reply, tools, %{state | tools: tools}}
    end
  end

  def handle_call({:call_tool, tool_name, args}, _from, state) do
    Logger.info("Calling tool '#{tool_name}' on '#{state.config.server_name}'")
    result = execute_tool(state.port, tool_name, args)
    {:reply, result, state}
  end

  defp connect_to_mcp(config) do
    # Example using Port for stdio; adjust for actual MCP protocol
    command = Enum.join([config.command | config.args], " ")
    port = Port.open({:spawn, command}, [:binary, :exit_status])
    {:ok, port}
  end

  defp fetch_tools(port) do
    # Placeholder: Implement MCP protocol to list tools
    []
  end

  defp execute_tool(port, tool_name, args) do
    # Placeholder: Implement MCP tool call
    # Send command to port and receive response
  end
end
```

* **Dynamic Supervisor**:

```elixir
defmodule MyApp.MCPSupervisor do
  use DynamicSupervisor

  def start_link(_) do
    DynamicSupervisor.start_link(__MODULE__, nil, name: __MODULE__)
  end

  def init(_) do
    DynamicSupervisor.init(strategy: :one_for_one)
  end

  def start_mcp_connection(server_config) do
    spec = {MyApp.MCPConnection, server_config}
    DynamicSupervisor.start_child(__MODULE__, spec)
  end
end
```

* **Notes**:
    * Each `MyApp.MCPConnection` is a `GenServer` managing its own port connection.
    * The `DynamicSupervisor` allows creating connections as needed, supporting scalability.
    * Actual MCP protocol implementation (e.g., stdio communication) requires additional libraries or custom logic.

### 3. LLMService

* **Purpose**: Interfaces with the Google GenAI API to generate responses.
* **Elixir Approach**: A `GenServer` to manage API state (e.g., API key), though API calls can be stateless if no persistent client is needed.
* **Code**:

```elixir
defmodule MyApp.LLMService do
  use GenServer
  require Logger

  def start_link(api_key) do
    GenServer.start_link(__MODULE__, api_key, name: __MODULE__)
  end

  def init(api_key) do
    Logger.info("LLM Service initialized")
    {:ok, %{api_key: api_key}}
  end

  def generate_response(conversation_history, tool_config) do
    GenServer.call(__MODULE__, {:generate_response, conversation_history, tool_config})
  end

  def handle_call({:generate_response, history, tool_config}, _from, state) do
    Logger.info("Sending request to LLM. History length: #{length(history)}")
    response = call_genai_api(state.api_key, history, tool_config)
    {:reply, response, state}
  end

  defp call_genai_api(api_key, history, tool_config) do
    # Use HTTP client (e.g., Tesla) to call Google GenAI API
    # Placeholder implementation
    %{"text" => "Sample response"}
  end
end
```

* **Notes**:
    * Requires an HTTP client like Tesla (add `{ :tesla, "~> 1.4" }` to `mix.exs`).
    * Tool schema conversion from MCP to GenAI format would occur here, similar to Python’s `_convert_mcp_tool_to_genai_function`.
    * For simplicity, this assumes stateless API calls; add state if caching or client persistence is needed.

### 4. WorkflowEngine

* **Purpose**: Orchestrates interactions between LLM and MCP tools for a user session.
* **Elixir Approach**: A `GenServer` per workflow instance, managing conversation state and coordinating LLM/tool interactions.
* **Code**:

```elixir
defmodule MyApp.WorkflowEngine do
  use GenServer
  require Logger

  def start_link({workflow_name, config_path}) do
    GenServer.start_link(__MODULE__, {workflow_name, config_path})
  end

  def init({workflow_name, config_path}) do
    {:ok, workflow_config} = MyApp.AppConfig.get_workflow_config(workflow_name)

    mcp_pids =
      Enum.map(workflow_config.mcp_servers_used, fn server_name ->
        {:ok, server_config} = MyApp.AppConfig.get_mcp_server_config(server_name)
        {:ok, pid} = MyApp.MCPSupervisor.start_mcp_connection(server_config)
        {server_name, pid}
      end) |> Map.new()

    state = %{
      workflow_name: workflow_name,
      config: workflow_config,
      mcp_pids: mcp_pids,
      conversation_history: []
    }

    Logger.info("WorkflowEngine initialized for '#{workflow_name}'")
    {:ok, state}
  end

  def process_query(pid, query) do
    GenServer.call(pid, {:process_query, query})
  end

  def handle_call({:process_query, query}, _from, state) do
    Logger.info("Processing query: '#{String.slice(query, 0, 70)}...'")
    {response, new_state} = process_query_internal(state, query)
    {:reply, response, new_state}
  end

  defp process_query_internal(state, query) do
    prompt = String.replace(state.config.initial_prompt_template, "{query}", query)
    history = [%{role: "user", parts: [%{text: prompt}]} | state.conversation_history]
    max_turns = state.config.max_conversation_turns

    # Simplified loop for brevity; implement full logic as in Python
    response = MyApp.LLMService.generate_response(history, nil)

    {response["text"], %{state | conversation_history: [response | history]}}
  end
end
```

* **Notes**:
    * Each instance manages its own state, suitable for CLI-driven sessions.
    * The full Python logic (tool calls, multi-turn reasoning) would need async handling and pattern matching, omitted here for brevity.
    * Dynamic supervision could be added if multiple workflows run concurrently.

### 5. CLI

* **Purpose**: Provides a command-line interface for user interaction.
* **Elixir Approach**: A standalone module that parses arguments and interacts with the `WorkflowEngine`.
* **Code**:

```elixir
defmodule MyApp.CLI do
  require Logger

  def main(args) do
    {opts, _, _} = OptionParser.parse(args, switches: [workflow: :string, query: :string])
    workflow_name = opts[:workflow]
    query = opts[:query]
    config_path = "config" # Adjust as needed

    Application.ensure_all_started(:my_app)

    if workflow_name do
      {:ok, engine_pid} = MyApp.WorkflowEngine.start_link({workflow_name, config_path})

      if query do
        response = MyApp.WorkflowEngine.process_query(engine_pid, query)
        IO.puts(response)
      else
        IO.puts("Interactive mode not implemented yet.")
      end
    else
      IO.puts("Workflow name required")
    end
  end
end
```

* **Notes**:
    * Uses `OptionParser` for basic argument parsing.
    * Interactive mode would require a loop with `IO.gets/1`, potentially running in a separate task.

## Application Module and Supervision Tree

* **Code**:

```elixir
defmodule MyApp.Application do
  use Application

  def start(_type, _args) do
    children = [
      {MyApp.AppConfig, "config"},
      {MyApp.MCPSupervisor, nil},
      {MyApp.LLMService, System.get_env("GOOGLE_API_KEY")}
    ]

    opts = [strategy: :one_for_one, name: MyApp.Supervisor]
    Supervisor.start_link(children, opts)
  end
end
```

* **Notes**:
    * Defines the top-level supervisor.
    * `WorkflowEngine` instances are started dynamically by the CLI or another supervisor if needed.

## Logging

* **Elixir Approach**: Use Elixir’s built-in `Logger` module, configured in `config/config.exs`.

* **Configuration** (in `config/config.exs`):

```elixir
config :logger,
  level: :info,
  backends: [:console, {LoggerFileBackend, :file_log}],
  format: "$time - $level - $metadata$message\n"

config :logger, :file_log,
  path: "app_client.log",
  level: :debug
```

* **Usage**:

```elixir
Logger.info("Message from #{__MODULE__}")
Logger.debug("Detailed debug info")
```

* **Notes**:
    * Replaces Python’s custom logging with Elixir’s native system.
    * File logging requires `{ :logger_file_backend, "~> 0.0.13" }` in `mix.exs`.

## Final Notes

* **Dependencies**: Add to `mix.exs`:

```elixir
defp deps do
  [
    {:jason, "~> 1.4"},
    {:tesla, "~> 1.4"},
    {:logger_file_backend, "~> 0.0.13"}
  ]
end
```

* **MCP Protocol**: The Python code uses stdio; Elixir’s `Port` can replicate this, but specifics depend on the MCP implementation.
* **Phoenix**: Not fully utilized here as the system is CLI-driven. For a web interface, Phoenix could serve API endpoints or channels, integrating with this OTP structure.

This port leverages OTP for fault tolerance and concurrency, providing a robust foundation suitable for the system’s needs while maintaining clean supervision.


# Setting Up an Elixir System from Scratch with Context7

This guide provides step-by-step instructions to set up an Elixir-based system from scratch, integrating Context7 as an MCP (Message Control Protocol) server. We'll cover installing Elixir, creating a new project, configuring dependencies, setting up configuration files, implementing core components, and running the system with Context7.

## Step 1: Install Elixir and Erlang

Elixir runs on the Erlang Virtual Machine (VM), so you need both installed on your system.

### Installation Commands

**macOS (using Homebrew):**

```bash
brew install erlang elixir
```

**Ubuntu/Debian:**

```bash
sudo apt-get update
sudo apt-get install erlang elixir
```

**Windows:**

* Download and install Erlang from erlang.org/downloads.
* Download and install Elixir from elixir-lang.org/install.html#windows.

### Verify Installation

Run the following command to confirm Elixir is installed:

```bash
elixir --version
```

You should see output showing the versions of Elixir and Erlang.

## Step 2: Create a New Elixir Project

We'll use Mix, Elixir's build tool, to create a new project with a supervision tree (OTP-ready).

### Create the Project

```bash
mix new my_app --sup
```

`--sup` adds a supervision tree, which aligns with OTP principles for fault tolerance.

### Navigate to the Project Directory

```bash
cd my_app
```

## Step 3: Add Dependencies

Edit the `mix.exs` file in your project root to include necessary dependencies for JSON parsing, HTTP requests, and logging.

### Update mix.exs

Open `mix.exs` and modify the `deps` function:

```elixir
defp deps do
  [
    {:jason, "~> 1.4"},            # For JSON parsing
    {:tesla, "~> 1.4"},            # HTTP client for API calls
    {:logger_file_backend, "~> 0.0.13"} # File-based logging
  ]
end
```

### Install Dependencies

Run the following command to fetch and install the dependencies:

```bash
mix deps.get
```

## Step 4: Configure Logging

Set up logging to write to both the console and a file, similar to a typical application setup.

### Edit config/config.exs

Modify `config/config.exs` to configure the logger:

```elixir
config :logger,
  level: :info,
  backends: [:console, {LoggerFileBackend, :file_log}],
  format: "$time - $level - $metadata$message\n"

config :logger, :file_log,
  path: "app_client.log",
  level: :debug
```

This sets up:

* Console logging at info level.
* File logging to `app_client.log` at debug level.

## Step 5: Set Up Configuration Files

Create configuration files for MCP servers and workflows in a `config/` directory.

### Create the Config Directory

```bash
mkdir config
```

### Create mcp_servers.json

In `config/mcp_servers.json`, define the MCP servers, including Context7:

```json
{
  "mcpServers": {
    "context7": {
      "command": "context7",
      "args": ["--port", "4040"],
      "transportType": "stdio"
    },
    "weather": {
      "command": "weather_server",
      "args": ["--port", "5050"],
      "transportType": "stdio"
    }
  }
}
```

Replace `"context7"` command and `args` with the actual command to run Context7 if different.

### Create workflows.json

In `config/workflows.json`, define the workflows:

```json
{
  "workflows": {
    "default": {
      "llm_model": "gemini-pro",
      "mcp_servers_used": ["context7", "weather"],
      "initial_prompt_template": "You are a helpful assistant. User query: {query}",
      "max_conversation_turns": 5
    }
  }
}
```

This workflow uses Context7 and a hypothetical weather server.

## Step 6: Implement AppConfig

Create a module to load and manage configuration data using a `GenServer`.

### Create lib/my_app/app_config.ex

```elixir
defmodule MyApp.AppConfig do
  use GenServer
  require Logger

  def start_link(config_path) do
    GenServer.start_link(__MODULE__, config_path, name: __MODULE__)
  end

  def init(config_path) do
    mcp_servers = load_json(Path.join(config_path, "mcp_servers.json"), "mcpServers")
    workflows = load_json(Path.join(config_path, "workflows.json"), "workflows")
    validate_configs(mcp_servers, workflows)
    Logger.info("Application configuration loaded successfully")
    {:ok, %{mcp_servers: mcp_servers, workflows: workflows}}
  end

  def get_mcp_server_config(server_name) do
    GenServer.call(__MODULE__, {:get_mcp_server, server_name})
  end

  def get_workflow_config(workflow_name) do
    GenServer.call(__MODULE__, {:get_workflow, workflow_name})
  end

  def handle_call({:get_mcp_server, server_name}, _from, state) do
    case Map.get(state.mcp_servers, server_name) do
      nil -> {:reply, {:error, :not_found}, state}
      config -> {:reply, {:ok, config}, state}
    end
  end

  def handle_call({:get_workflow, workflow_name}, _from, state) do
    case Map.get(state.workflows, workflow_name) do
      nil -> {:reply, {:error, :not_found}, state}
      config -> {:reply, {:ok, config}, state}
    end
  end

  defp load_json(file_path, expected_key) do
    with {:ok, body} <- File.read(file_path),
         {:ok, data} <- Jason.decode(body, keys: :atoms),
         config when is_map(config) <- Map.get(data, String.to_atom(expected_key)) do
      config
    else
      _ -> raise "Configuration loading failed for #{file_path}"
    end
  end

  defp validate_configs(mcp_servers, workflows) do
    unless is_map(mcp_servers) and is_map(workflows), do: raise "Invalid config format"
  end
end
```

This module loads and validates the JSON configs and provides access via GenServer calls.

## Step 7: Implement MCPConnection

Create a module to manage connections to MCP servers like Context7.

### Create lib/my_app/mcp_connection.ex

```elixir
defmodule MyApp.MCPConnection do
  use GenServer
  require Logger

  def start_link(server_config) do
    GenServer.start_link(__MODULE__, server_config)
  end

  def init(server_config) do
    Logger.info("Connecting to MCP server: #{server_config.server_name}")
    {:ok, port} = connect_to_mcp(server_config)
    {:ok, %{config: server_config, port: port, tools: nil}}
  end

  def call_tool(pid, tool_name, args) do
    GenServer.call(pid, {:call_tool, tool_name, args})
  end

  def get_tools(pid) do
    GenServer.call(pid, :get_tools)
  end

  def handle_call(:get_tools, _from, state) do
    tools = fetch_tools(state.port)
    {:reply, tools, %{state | tools: tools}}
  end

  def handle_call({:call_tool, tool_name, args}, _from, state) do
    result = execute_tool(state.port, tool_name, args)
    {:reply, result, state}
  end

  defp connect_to_mcp(config) do
    command = Enum.join([config.command | config.args], " ")
    port = Port.open({:spawn, command}, [:binary, :exit_status])
    {:ok, port}
  end

  defp fetch_tools(port) do
    # Placeholder: Implement Context7's MCP protocol to fetch tools
    []
  end

  defp execute_tool(port, tool_name, args) do
    # Placeholder: Implement tool execution via Context7's MCP protocol
    %{}
  end
end
```

**Note**: You’ll need to implement `Workspace_tools/1` and `execute_tool/3` based on Context7’s specific MCP protocol.

## Step 8: Implement LLMService

Create a module to interact with the Google GenAI API (assumed as the LLM backend).

### Create lib/my_app/llm_service.ex

```elixir
defmodule MyApp.LLMService do
  use GenServer
  require Logger

  def start_link(api_key) do
    GenServer.start_link(__MODULE__, api_key, name: __MODULE__)
  end

  def init(api_key) do
    Logger.info("LLM Service initialized")
    {:ok, %{api_key: api_key}}
  end

  def generate_response(conversation_history, tool_config) do
    GenServer.call(__MODULE__, {:generate_response, conversation_history, tool_config})
  end

  def handle_call({:generate_response, history, tool_config}, _from, state) do
    response = call_genai_api(state.api_key, history, tool_config)
    {:reply, response, state}
  end

  defp call_genai_api(api_key, history, _tool_config) do
    # Placeholder: Implement Google GenAI API call using Tesla
    %{"text" => "Sample response from LLM"}
  end
end
```

**Note**: Replace the placeholder in `call_genai_api/3` with an actual HTTP call to the Google GenAI API using the Tesla library.

## Step 9: Implement WorkflowEngine

Create a module to manage user sessions and process queries.

### Create lib/my_app/workflow_engine.ex

```elixir
defmodule MyApp.WorkflowEngine do
  use GenServer
  require Logger

  def start_link({workflow_name, config_path}) do
    GenServer.start_link(__MODULE__, {workflow_name, config_path})
  end

  def init({workflow_name, config_path}) do
    {:ok, workflow_config} = MyApp.AppConfig.get_workflow_config(workflow_name)

    mcp_pids =
      Enum.map(workflow_config.mcp_servers_used, fn server_name ->
        {:ok, server_config} = MyApp.AppConfig.get_mcp_server_config(server_name)
        {:ok, pid} = MyApp.MCPSupervisor.start_mcp_connection(server_config)
        {server_name, pid}
      end) |> Map.new()

    state = %{
      workflow_name: workflow_name,
      config: workflow_config,
      mcp_pids: mcp_pids,
      conversation_history: []
    }

    Logger.info("WorkflowEngine initialized for '#{workflow_name}'")
    {:ok, state}
  end

  def process_query(pid, query) do
    GenServer.call(pid, {:process_query, query})
  end

  def handle_call({:process_query, query}, _from, state) do
    prompt = String.replace(state.config.initial_prompt_template, "{query}", query)
    history = [%{role: "user", parts: [%{text: prompt}]} | state.conversation_history]
    response = MyApp.LLMService.generate_response(history, nil)
    new_state = %{state | conversation_history: [response | history]}
    {:reply, response["text"], new_state}
  end
end
```

## Step 10: Set Up Supervision Tree

Update the application module to define the supervision tree.

### Edit lib/my_app/application.ex

```elixir
defmodule MyApp.Application do
  use Application

  def start(_type, _args) do
    children = [
      {MyApp.AppConfig, "config"},
      {DynamicSupervisor, strategy: :one_for_one, name: MyApp.MCPSupervisor},
      {MyApp.LLMService, System.get_env("GOOGLE_API_KEY")}
    ]

    opts = [strategy: :one_for_one, name: MyApp.Supervisor]
    Supervisor.start_link(children, opts)
  end
end
```

This sets up:

* `AppConfig` for configuration management.
* A `DynamicSupervisor` for MCP connections.
* `LLMService` with the Google API key from the environment.

## Step 11: Implement CLI

Create a command-line interface to interact with the system.

### Create lib/my_app/cli.ex

```elixir
defmodule MyApp.CLI do
  require Logger

  def main(args) do
    {opts, _, _} = OptionParser.parse(args, switches: [workflow: :string, query: :string])
    workflow_name = opts[:workflow]
    query = opts[:query]

    if workflow_name do
      {:ok, engine_pid} = MyApp.WorkflowEngine.start_link({workflow_name, "config"})

      if query do
        response = MyApp.WorkflowEngine.process_query(engine_pid, query)
        IO.puts(response)
      else
        IO.puts("Please provide a query with --query")
      end
    else
      IO.puts("Workflow name required with --workflow")
    end
  end
end
```

## Step 12: Configure Environment Variables

Set the Google API key in your environment for the LLM service.

### Set the API Key

```bash
export GOOGLE_API_KEY=your_api_key_here
```

Replace `your_api_key_here` with your actual Google GenAI API key.

## Step 13: Run the Application

Use the CLI to run the application with a sample query.

### Run Command

```bash
mix run --no-halt -e "MyApp.CLI.main(['--workflow', 'default', '--query', 'What is the weather like today?'])"
```

This starts the application and processes the query using the default workflow, which includes Context7.

## Step 14: Testing

* **Start Context7**: Ensure Context7 is running as specified in `mcp_servers.json` (e.g., `context7 --port 4040`).
* **Test Queries**: Run the application with different queries to verify Context7 integration and LLM responses.
* **Check Logs**: Inspect `app_client.log` for debug information.

## Additional Notes

* **Context7 Integration**: Verify that Context7’s MCP protocol is correctly implemented in `MCPConnection`. Update `Workspace_tools/1` and `execute_tool/3` according to its documentation.
* **Error Handling**: Add more robust error handling for production use, especially for API calls and MCP connections.
* **Interactive Mode**: Extend the CLI with a loop for interactive querying if desired.

By following these steps, you’ll have a fully functional Elixir system set up from scratch, leveraging OTP principles and integrating Context7 as an MCP server.
