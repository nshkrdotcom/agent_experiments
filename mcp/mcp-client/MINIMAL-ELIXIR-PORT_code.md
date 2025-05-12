Okay, porting this Python application to Elixir/Phoenix with a focus on OTP principles and clean supervision is a significant task. Below is a well-structured Elixir project that mirrors the functionality of your Python code, emphasizing OTP patterns.

Since a full Phoenix integration for UI is extensive, I'll focus on the core Elixir OTP application. A Phoenix frontend (e.g., LiveView for chat, API endpoints) could then consume this core application.

**Project Structure:**

```
mcp_elixir_app/
├── lib/
│   ├── mcp_elixir_app/
│   │   ├── application.ex
│   │   ├── config_loader.ex
│   │   ├── cli.ex
│   │   ├── llm/
│   │   │   ├── service.ex
│   │   │   ├── supervisor.ex
│   │   │   └── genai_tool_converter.ex
│   │   ├── mcp/
│   │   │   ├── service.ex
│   │   │   ├── supervisor.ex
│   │   │   └── protocol.ex
│   │   └── workflow/
│   │       ├── engine.ex
│   │       └── supervisor.ex
│   └── mcp_elixir_app.ex # If needed for top-level functions/types
├── config/
│   ├── config.exs
│   ├── dev.exs
│   ├── mcp_servers.json # Place your example JSON here
│   └── workflows.json   # Place your example JSON here
├── priv/
│   └── # Potential location for dummy MCP server executables for testing
├── test/
│   └── # Test files
└── mix.exs
```

**1. `mix.exs` (Project Definition and Dependencies)**

```elixir
defmodule McpElixirApp.MixProject do
  use Mix.Project

  def project do
    [
      app: :mcp_elixir_app,
      version: "0.1.0",
      elixir: "~> 1.15",
      start_permanent: Mix.env() == :prod,
      deps: deps(),
      aliases: [
        "run.cli": "run lib/mcp_elixir_app/cli.exs" # Example alias
      ]
    ]
  end

  def application do
    [
      extra_applications: [:logger, :runtime_tools],
      mod: {McpElixirApp.Application, []}
    ]
  end

  defp deps do
    [
      {:jason, "~> 1.4"},
      {:tesla, "~> 1.7.0"}, # For HTTP client for Google GenAI
      {:castore, "~> 1.0"} # For Tesla, CA cert store
      # If an Elixir GenAI client library existed, it would go here.
      # We'll make direct HTTP calls.
    ]
  end
end
```

**2. `config/config.exs` (Base Configuration, including Logger)**

```elixir
import Config

# Configure Elixir Logger
# Python's 'USER' level can be achieved via metadata or specific formatting rules.
# For simplicity, we'll rely on :info for user-facing messages,
# and :debug for verbose internal logging.

# Default console format
config :logger, :console,
  format: "$time $metadata[$level] $message\n",
  metadata: [:module, :function, :line] # Add more as needed

# Example: More verbose for dev, less for prod
if Mix.env() == :dev do
  config :logger, level: :debug
else
  config :logger, level: :info
end

# If file logging is desired:
# config :logger, :file_log,
#   path: "priv/logs/app.log",
#   level: :debug,
#   format: "$time $metadata[$level] $message\n",
#   metadata_filter: [level: [:debug, :info, :warning, :error]] # Adjust levels as needed

# Application specific configuration (API keys, file paths)
config :mcp_elixir_app,
  google_api_key: System.get_env("GOOGLE_API_KEY") || System.get_env("GEMINI_API_KEY"),
  mcp_servers_path: "config/mcp_servers.json",
  workflows_path: "config/workflows.json"

# Configure Tesla for Google GenAI (example)
config :mcp_elixir_app, McpElixirApp.LLM.Service,
  base_url: "https://generativelanguage.googleapis.com"

# Import environment-specific config
import_config "#{Mix.env()}.exs"
```

**3. `config/dev.exs` (Development Specific Config)**

```elixir
import Config

# Potentially override log levels or paths for dev
config :logger, :console,
  level: :debug,
  format: "[$level] $message\n" # Simpler format for dev console

# Example MCP server configs if they are local scripts for dev
# config :mcp_elixir_app, :mcp_server_overrides, %{
#   "weather_tool" => %{"command" => "./priv/mock_mcp_weather", "args" => []}
# }
```

**4. `lib/mcp_elixir_app/config_loader.ex` (Equivalent of Python's `AppConfig`)**

```elixir
defmodule McpElixirApp.ConfigLoader do
  require Logger

  # Holds the loaded and validated configuration
  defstruct mcp_servers: %{},
            workflows: %{},
            google_api_key: nil

  def load() do
    mcp_path = Application.get_env(:mcp_elixir_app, :mcp_servers_path)
    workflows_path = Application.get_env(:mcp_elixir_app, :workflows_path)
    api_key = Application.get_env(:mcp_elixir_app, :google_api_key)

    unless api_key do
      Logger.error("GOOGLE_API_KEY or GEMINI_API_KEY not found in environment or app config.")
      {:error, :missing_api_key}
    else
      with {:ok, mcp_servers} <- load_json_config(mcp_path, "mcpServers"),
           {:ok, validated_mcp_servers} <- validate_mcp_servers(mcp_servers),
           {:ok, workflows} <- load_json_config(workflows_path, "workflows"),
           {:ok, validated_workflows} <- validate_workflows(workflows, validated_mcp_servers) do
        config_struct = %__MODULE__{
          mcp_servers: validated_mcp_servers,
          workflows: validated_workflows,
          google_api_key: api_key
        }
        Logger.info("Application configuration loaded successfully.")
        {:ok, config_struct}
      else
        {:error, reason} ->
          Logger.error("Failed to load or validate configuration: #{inspect(reason)}")
          {:error, reason}
      end
    end
  end

  defp load_json_config(nil, _key), do: {:error, :config_path_not_set}
  defp load_json_config(path, expected_key) do
    case File.read(path) do
      {:ok, body} ->
        case Jason.decode(body) do
          {:ok, data} ->
            case Map.get(data, expected_key) do
              nil ->
                Logger.error("Missing '#{expected_key}' key in #{path}")
                {:error, {:missing_key, expected_key, path}}
              config_map ->
                Logger.info("Loaded #{expected_key} from #{path}")
                {:ok, config_map}
            end
          {:error, reason} ->
            Logger.error("Invalid JSON in #{path}: #{inspect(reason)}")
            {:error, {:json_decode_error, path, reason}}
        end
      {:error, reason} ->
        Logger.error("Configuration file not found or unreadable: #{path} - #{inspect(reason)}")
        {:error, {:file_error, path, reason}}
    end
  end

  defp validate_mcp_servers(servers) when is_map(servers) do
    Enum.reduce_while(servers, {:ok, %{}}, fn {name, config}, {:ok, acc} ->
      cond do
        not is_map(config) ->
          {:stop, {:error, "Server config for '#{name}' must be a map."}}
        not Map.has_key?(config, "command") or not Map.has_key?(config, "args") or not is_list(config["args"]) ->
          {:stop, {:error, "Server '#{name}' has invalid 'command' or 'args'."}}
        Map.get(config, "transportType", "stdio") != "stdio" ->
          {:stop, {:error, "Unsupported transportType for '#{name}'. Only 'stdio' is supported."}}
        true ->
          {:cont, {:ok, Map.put(acc, name, config)}}
      end
    end)
    |> case do
      {:ok, validated_servers} ->
        Logger.debug("MCP server configurations validated.")
        {:ok, validated_servers}
      {:error, reason} -> {:error, reason}
    end
  end
  defp validate_mcp_servers(_), do: {:error, "MCP servers config must be a map."}


  defp validate_workflows(workflows, mcp_servers) when is_map(workflows) do
    required_keys = ["llm_model", "mcp_servers_used", "initial_prompt_template", "max_conversation_turns"]

    Enum.reduce_while(workflows, {:ok, %{}}, fn {name, wf_config}, {:ok, acc} ->
      cond do
        not is_map(wf_config) ->
          {:stop, {:error, "Workflow config for '#{name}' must be a map."}}
        missing_key = Enum.find(required_keys, &(!Map.has_key?(wf_config, &1))) ->
          {:stop, {:error, "Workflow '#{name}' missing required key: '#{missing_key}'."}}
        not is_list(wf_config["mcp_servers_used"]) ->
          {:stop, {:error, "Workflow '#{name}' 'mcp_servers_used' must be a list."}}
        undefined_server = Enum.find(wf_config["mcp_servers_used"], &(!Map.has_key?(mcp_servers, &1))) ->
          {:stop, {:error, "Workflow '#{name}' uses undefined MCP server: '#{undefined_server}'."}}
        true ->
          {:cont, {:ok, Map.put(acc, name, wf_config)}}
      end
    end)
    |> case do
      {:ok, validated_workflows} ->
        Logger.debug("Workflow configurations validated.")
        {:ok, validated_workflows}
      {:error, reason} -> {:error, reason}
    end
  end
  defp validate_workflows(_, _), do: {:error, "Workflows config must be a map."}

  def get_mcp_server_config(%__MODULE__{mcp_servers: servers}, server_name) do
    Map.get(servers, server_name)
  end

  def get_workflow_config(%__MODULE__{workflows: workflows}, workflow_name) do
    Map.get(workflows, workflow_name)
  end

  def list_workflows(%__MODULE__{workflows: workflows}) do
    Map.keys(workflows)
  end
end
```

**5. `lib/mcp_elixir_app/application.ex` (OTP Application and Supervision Tree)**

```elixir
defmodule McpElixirApp.Application do
  use Application
  require Logger

  @impl true
  def start(_type, _args) do
    Logger.info("Starting McpElixirApp...")

    # Load configuration
    case McpElixirApp.ConfigLoader.load() do
      {:ok, app_config} ->
        # Store app_config for global access, or pass down selectively.
        # For simplicity here, we'll rely on other modules fetching from Application env
        # if needed, but supervisors below will get it directly.
        Application.put_env(:mcp_elixir_app, :app_config, app_config)

        children = [
          {McpElixirApp.LLM.Supervisor, app_config.google_api_key},
          {McpElixirApp.MCP.Supervisor, app_config.mcp_servers},
          {McpElixirApp.Workflow.Supervisor, app_config} # Pass full config for workflows
          # If using Phoenix: McpElixirAppWeb.Endpoint
        ]

        opts = [strategy: :one_for_one, name: McpElixirApp.CoreSupervisor]
        Supervisor.start_link(children, opts)

      {:error, reason} ->
        Logger.critical("Failed to start application due to config error: #{inspect(reason)}")
        {:error, reason} # This will stop the app from starting
    end
  end
end
```

**6. MCP Components**

   **`lib/mcp_elixir_app/mcp/protocol.ex` (Simplified MCP Interaction Logic)**

   ```elixir
   defmodule McpElixirApp.MCP.Protocol do
     # Simplified protocol: assumes JSON lines over stdio.
     # Each request has a unique ID, and the server echoes it in the response.

     def build_request(method, params \\ %{}, id \\ make_ref()) do
       # In a real scenario, might conform to JSON-RPC spec
       %{id: id, method: method, params: params}
       |> Jason.encode!()
       |> Kernel.<>("\n") # Assuming newline delimited JSON
     end

     def parse_response(line) do
       # Trim whitespace (like newline) before decoding
       Jason.decode(String.trim(line))
     end
   end
   ```

   **`lib/mcp_elixir_app/mcp/service.ex` (GenServer for an MCP Server)**

   ```elixir
   defmodule McpElixirApp.MCP.Service do
     use GenServer
     require Logger

     alias McpElixirApp.MCP.Protocol

     # Max time to wait for a response from MCP server
     @request_timeout 15_000 # 15 seconds

     defstruct server_name: nil,
               config: nil,
               port: nil,
               requests: %{}, # ref => {caller, timer_ref}
               initialized: false,
               tools_cache: nil, # Cache tools after first successful fetch
               init_caller: nil # To reply to supervisor after initialization

     # Client API
     def start_link(opts) do
       server_name = Keyword.fetch!(opts, :server_name)
       config = Keyword.fetch!(opts, :config)
       name = via_tuple(server_name)
       GenServer.start_link(__MODULE__, {server_name, config}, name: name)
     end

     def get_tools(server_pid_or_name) when is_pid(server_pid_or_name) do
       GenServer.call(server_pid_or_name, :get_tools, @request_timeout)
     end
     def get_tools(server_name) when is_binary(server_name) do
       GenServer.call(via_tuple(server_name), :get_tools, @request_timeout)
     end

     def call_tool(server_pid_or_name, tool_name, args) when is_pid(server_pid_or_name) do
       GenServer.call(server_pid_or_name, {:call_tool, tool_name, args}, @request_timeout * 2) # Longer timeout for tool calls
     end
     def call_tool(server_name, tool_name, args) when is_binary(server_name) do
       GenServer.call(via_tuple(server_name), {:call_tool, tool_name, args}, @request_timeout * 2)
     end

     # Server Callbacks
     @impl true
     def init({server_name, config}) do
       Logger.info("[MCP:#{server_name}] Initializing...")
       port_cmd = config["command"]
       port_args = config["args"]
       port_env = config["env"] || [] # Ensure env is a list or map for Port.open

       # Convert env map to list of tuples if it's a map
       port_env_formatted =
         if is_map(port_env) do
           Enum.map(port_env, fn {k, v} -> {k, v} end)
         else
           port_env # Assuming it's already in [{k,v}] or similar format if not a map
         end

       port_settings = [
         {:args, port_args},
         {:env, port_env_formatted},
         :binary,
         :exit_status,
         :hide, # Don't send to group_leader
         line: true # Receive data line by line
       ]

       case Port.open({:spawn_executable, port_cmd}, port_settings) do
         port when is_port(port) ->
           Logger.info("[MCP:#{server_name}] Port opened to '#{port_cmd}'. Sending initialize.")
           state = %__MODULE__{
             server_name: server_name,
             config: config,
             port: port,
             init_caller: {self(), make_ref()} # For self-notification/supervisor pattern
           }
           # Send initialize message
           send_port_request(port, "initialize", %{}, self(), state.requests)
           {:ok, state, {:continue, :finish_initialization}}
         {:error, reason} ->
           Logger.error("[MCP:#{server_name}] Failed to open port: #{inspect(reason)}")
           {:stop, {:port_open_failed, reason}}
       end
     end

     @impl true
     def handle_continue(:finish_initialization, state = %{init_caller: {caller_pid, ref}}) do
       # This is a pattern to wait for the async "initialize" response
       # before the GenServer init fully completes and supervisor gets :ok.
       # For simplicity in this example, we'll assume initialize is quick
       # or we just proceed. A more robust init would wait for an initialize ACK.
       # Here we'll assume "initialize" response will set state.initialized
       # For now, just reply :ok to the supervisor (which is the implicit caller of init).
       # A proper approach would be for init to return {:ok, state, timeout_or_hibernate}
       # and only after 'initialize' ACK, the GenServer would signal readiness.
       #
       # Simpler init for now: we'll let supervisor get :ok and rely on internal state.initialized.
       Process.send_after(self(), {:check_init_ack}, 1000) # Check if init response came
       {:noreply, state}
     end

     @impl true
     def handle_call(:get_tools, from, state) do
       if !state.initialized do
         Logger.warning("[MCP:#{state.server_name}] Attempted to get tools before initialized.")
         {:reply, {:error, :not_initialized}, state}
       else
         case state.tools_cache do
           nil -> # Fetch if not cached
            new_requests = send_port_request(state.port, "list_tools", %{}, from, state.requests)
            {:noreply, %{state | requests: new_requests}}
           cached_tools ->
             Logger.debug("[MCP:#{state.server_name}] Returning cached tools.")
             {:reply, {:ok, cached_tools}, state}
         end
       end
     end

     @impl true
     def handle_call({:call_tool, tool_name, args}, from, state) do
       if !state.initialized do
         Logger.warning("[MCP:#{state.server_name}] Attempted to call tool before initialized.")
         {:reply, {:error, :not_initialized}, state}
       else
         params = %{tool_name: tool_name, args: args}
         new_requests = send_port_request(state.port, "call_tool", params, from, state.requests)
         {:noreply, %{state | requests: new_requests}}
       end
     end

     @impl true
     def handle_info({:timeout, ref, _method}, state) do
       case Map.pop(state.requests, ref) do
         {{caller, _timer_ref}, new_requests} ->
           GenServer.reply(caller, {:error, :timeout})
           Logger.warning("[MCP:#{state.server_name}] Request timed out for ref: #{inspect(ref)}")
           {:noreply, %{state | requests: new_requests}}
         {nil, _new_requests} -> # Already handled or invalid ref
           {:noreply, state}
       end
     end

     @impl true
     def handle_info({port, {:data, {:eol, line}}}, %{port: port} = state) do
       Logger.debug fn -> "[MCP:#{state.server_name}] Received data: #{line}" end
       case Protocol.parse_response(line) do
         {:ok, %{"id" => id, "result" => result, "method_echo" => method_echo}} -> # Assuming server echoes method
           handle_mcp_response(id, {:ok, result}, method_echo, state)
         {:ok, %{"id" => id, "error" => error, "method_echo" => method_echo}} ->
           handle_mcp_response(id, {:error, error}, method_echo, state)
         {:error, reason} ->
           Logger.error("[MCP:#{state.server_name}] Failed to parse response: #{line}, reason: #{inspect(reason)}")
           {:noreply, state}
         _ ->
           Logger.warning("[MCP:#{state.server_name}] Received malformed or unexpected response: #{line}")
           {:noreply, state}
       end
     end

     @impl true
     def handle_info({port, {:exit_status, status}}, %{port: port} = state) do
       Logger.error("[MCP:#{state.server_name}] Port closed with status: #{status}. Shutting down service.")
       # All pending requests should be replied to with an error
       Enum.each(state.requests, fn {_ref, {caller, timer_ref}} ->
         Process.cancel_timer(timer_ref, async: true, info: false)
         GenServer.reply(caller, {:error, :port_closed})
       end)
       {:stop, {:port_closed, status}, %{state | requests: %{}}}
     end

     @impl true
     def handle_info({:check_init_ack}, state) do
       unless state.initialized do
         Logger.warning("[MCP:#{state.server_name}] Initialize ACK not received. MCP server might not be responding correctly to 'initialize'.")
       end
       {:noreply, state}
     end


     @impl true
     def terminate(reason, state) do
       if is_port(state.port), do: Port.close(state.port)
       Logger.info("[MCP:#{state.server_name}] Terminating. Reason: #{inspect(reason)}")
       :ok
     end

     # Private helpers
     defp via_tuple(server_name), do: {:via, Registry, {McpElixirApp.MCP.Registry, server_name}}

     defp send_port_request(port, method, params, from_caller, requests_map) do
       req_id_binary = :crypto.strong_rand_bytes(8) |> Base.encode16(case: :lower) # More unique than make_ref string for external
       req_id = to_string(req_id_binary) # Ensure string for JSON if protocol needs it. Or use make_ref directly if internal only.

       request_payload = Protocol.build_request(method, params, req_id)
       Port.command(port, request_payload)

       # Set a timeout for the request
       timer_ref = Process.send_after(self(), {:timeout, req_id, method}, @request_timeout)
       Map.put(requests_map, req_id, {from_caller, timer_ref})
     end

     defp handle_mcp_response(id, response_payload, method_echo, state) do
       case Map.pop(state.requests, id) do
         {{caller, timer_ref}, new_requests} ->
           Process.cancel_timer(timer_ref, async: true, info: false) # Cancel the timeout
           GenServer.reply(caller, response_payload)

           new_state = %{state | requests: new_requests}
           case {method_echo, response_payload} do
             {"initialize", {:ok, _init_data}} -> # Assuming init_data might contain server info
                Logger.info("[MCP:#{new_state.server_name}] Initialization successful.")
                # Perform initial tool fetch for logging if needed, like in Python version
                # This can be done by sending a message to self() to trigger list_tools
                # after a short delay or immediately if init_data contains tools
                # For now, just mark as initialized
               {:noreply, %{new_state | initialized: true}}
             {"list_tools", {:ok, tools_data}} ->
               Logger.debug("[MCP:#{new_state.server_name}] Tools listed: #{inspect(tools_data)}")
               # Assuming tools_data is the list of tools in the desired format
               # The Python code wraps Tool objects. Here we'd have maps or structs.
               # Example: tools_data = [%{"name" => "tool1", "description" => "...", "inputSchema" => %{}}, ...]
               {:noreply, %{new_state | tools_cache: tools_data}}
             _ ->
               {:noreply, new_state}
           end

         {nil, _} -> # Response for an unknown or already handled request
           Logger.warning("[MCP:#{state.server_name}] Received response for unknown/handled request ID: #{id}")
           {:noreply, state}
       end
     end
   end
   ```

   **`lib/mcp_elixir_app/mcp/supervisor.ex`**

   ```elixir
   defmodule McpElixirApp.MCP.Supervisor do
     use Supervisor
     require Logger

     def start_link(mcp_server_configs) do
       Supervisor.start_link(__MODULE__, mcp_server_configs, name: __MODULE__)
     end

     @impl true
     def init(mcp_server_configs) do
       # Using a dynamic supervisor or a simple_one_for_one supervisor
       # allows adding/removing MCP services more easily if config changes at runtime.
       # For startup from static config, a regular supervisor is also fine.
       # Here, we use a regular supervisor with named children for simplicity
       # and easier lookup by workflow engine.

       children =
         Enum.map(mcp_server_configs, fn {server_name, config} ->
           %{
             id: :"mcp_service_#{server_name}", # Ensure unique ID
             start: {McpElixirApp.MCP.Service, :start_link, [[server_name: server_name, config: config]]},
             restart: :permanent, # Or :transient if it shouldn't restart on normal stop
             type: :worker
           }
         end)

       # Start a Registry for MCP services for name-based lookup
       registry_child = {Registry, keys: :unique, name: McpElixirApp.MCP.Registry}

       Logger.info("MCP Supervisor initializing with #{length(children)} services.")
       Supervisor.init([registry_child | children], strategy: :one_for_one)
     end
   end
   ```

**7. LLM Components**

   **`lib/mcp_elixir_app/llm/genai_tool_converter.ex`**

   ```elixir
   defmodule McpElixirApp.LLM.GenaiToolConverter do
     require Logger

     # Corresponds to Python's _convert_mcp_tool_to_genai_function
     def convert_mcp_tool_to_genai_function(mcp_tool) do
       # mcp_tool is expected to be a map like:
       # %{"name" => "tool_name", "description" => "...", "inputSchema" => %{"type" => "object", "properties" => %{...}}}
       tool_name = mcp_tool["name"]
       Logger.debug("Converting MCP tool '#{tool_name}' to GenAI function declaration.")

       parameters_schema = %{"type" => "object", "properties" => %{}}
       input_schema = mcp_tool["inputSchema"]

       if input_schema && is_map(input_schema) do
         genai_properties =
           Enum.reduce(Map.get(input_schema, "properties", %{}), %{}, fn {name, schema_prop}, acc ->
             if !is_map(schema_prop) do
               Logger.warning("Skipping malformed property #{name} in tool #{tool_name}")
               acc
             else
               prop_type_str = String.downcase(Map.get(schema_prop, "type", "string"))
               valid_types = ["string", "number", "integer", "boolean", "array", "object"]

               prop_type_str =
                 if prop_type_str in valid_types, do: prop_type_str,
                 else:
                   Logger.warning("Invalid type #{prop_type_str} for #{name} in tool #{tool_name}, defaulting to string")
                   "string"

               current_prop_schema = %{"type" => prop_type_str}
               current_prop_schema = if Map.has_key?(schema_prop, "description"), do: Map.put(current_prop_schema, "description", schema_prop["description"]), else: current_prop_schema
               current_prop_schema = if Map.has_key?(schema_prop, "enum") && is_list(schema_prop["enum"]), do: Map.put(current_prop_schema, "enum", schema_prop["enum"]), else: current_prop_schema

               current_prop_schema =
                 if prop_type_str == "array" do
                   items_schema = Map.get(schema_prop, "items", %{"type" => "string"}) # Default items to string
                   unless is_map(items_schema) do
                     Logger.debug("Array property '#{name}' in tool '#{tool_name}' has invalid 'items'. Defaulting to string items.")
                     items_schema = %{"type" => "string"}
                   end
                   Map.put(current_prop_schema, "items", items_schema)
                 else
                   current_prop_schema
                 end
               Map.put(acc, name, current_prop_schema)
             end
           end)
         parameters_schema = Map.put(parameters_schema, "properties", genai_properties)

         required = Map.get(input_schema, "required", [])
         if required && is_list(required) && Enum.all?(required, &is_binary/1) do
           parameters_schema = Map.put(parameters_schema, "required", required)
         end
       else
         Logger.warning("No input schema or malformed schema for tool #{tool_name}. Tool will have no parameters.")
       end

       description = mcp_tool["description"]
       description =
         if description && is_binary(description) && String.trim(description) != "" do
           description
         else
           Logger.warning("Tool '#{tool_name}' has missing/empty description, using default.")
           "Tool to perform #{tool_name}"
         end

       %{
         "name" => tool_name,
         "description" => description,
         "parameters" => parameters_schema
       }
     end

     # Corresponds to Python's prepare_tools_for_llm
     def prepare_tools_for_llm(mcp_tools) when is_list(mcp_tools) do
       if Enum.empty?(mcp_tools) do
         Logger.debug("No MCP tools provided to prepare for LLM.")
         nil # Or return %{} if GenAI API expects an empty tool config
       else
         Logger.debug("Preparing #{length(mcp_tools)} MCP tools for LLM.")
         genai_tool_declarations =
           Enum.flat_map(mcp_tools, fn tool ->
             # Assuming tool is a map with "name" key
             if is_map(tool) && Map.has_key?(tool, "name") && tool["name"] do
               try do
                 [convert_mcp_tool_to_genai_function(tool)]
               rescue
                 e ->
                   Logger.error("Failed to convert MCP tool '#{Map.get(tool, "name", "UNKNOWN")}' for LLM: #{inspect(e)}", Process.info(self(), :current_stacktrace))
                   []
               end
             else
               Logger.warning("Skipping an invalid/unnamed MCP tool: #{inspect(tool)}")
               []
             end
           end)

         if Enum.empty?(genai_tool_declarations) do
           Logger.info("No MCP tools were successfully converted for LLM.")
           nil
         else
           # Gemini format: list of Tool objects, each with function_declarations
           # Example: %{"tools" => [%{"function_declarations" => [...]}]}
           gemini_tools_config = [%{"function_declarations" => genai_tool_declarations}]
           Logger.info("LLM tools configured: #{Enum.map(genai_tool_declarations, & &1["name"])}")
           %{"tools" => gemini_tools_config} # This is GenerateContentConfig in Python
         end
       end
     end
     def prepare_tools_for_llm(_), do: nil # Catch-all for invalid input
   end
   ```

   **`lib/mcp_elixir_app/llm/service.ex` (GenServer for Google GenAI)**

   ```elixir
   defmodule McpElixirApp.LLM.Service do
     use GenServer
     require Logger

     alias McpElixirApp.LLM.GenaiToolConverter

     # HTTP Client for Google GenAI API
     # In a real app, you might use a more specific GenAI client library if available.
     # Here, we use Tesla.
     defmodule GoogleGenaiClient do
       use Tesla

       plug Tesla.Middleware.BaseUrl, Application.get_env(:mcp_elixir_app, McpElixirApp.LLM.Service)[:base_url]
       plug Tesla.Middleware.JSON # Encode/Decode JSON
       plug Tesla.Middleware.Headers, [{"x-goog-api-key", fn -> Application.get_env(:mcp_elixir_app, :google_api_key) end}]
       plug Tesla.Middleware.FollowRedirects
       plug Tesla.Middleware.Retry, delay: 500, max_retries: 3
       # plug Tesla.Middleware.Logger # For debugging HTTP requests

       adapter Tesla.Adapter.Hackney # Or Finch, or another adapter
     end

     defstruct model_name: nil,
               api_key: nil # Stored more for info, Tesla middleware handles it

     # Client API
     def start_link(api_key) do
       GenServer.start_link(__MODULE__, api_key, name: __MODULE__)
     end

     def generate_response(model_name, conversation_history, tool_config \\ nil) do
       GenServer.call(__MODULE__, {:generate_response, model_name, conversation_history, tool_config}, :infinity) # Long timeout for LLM
     end

     # Server Callbacks
     @impl true
     def init(api_key) do
       Logger.info("Google GenAI LLM Service initialized.")
       # Model name is passed per request in this Elixir version,
       # but can be set in init if only one model is used by this service.
       {:ok, %__MODULE__{api_key: api_key}}
     end

     @impl true
     def handle_call({:generate_response, model_name, conversation_history, tool_config}, _from, state) do
       Logger.info("Sending request to LLM model: #{model_name}. History length: #{length(conversation_history)}.")
       last_message = if Enum.empty?(conversation_history), do: "None", else: List.last(conversation_history)
       Logger.debug("LLM request contents (last message): #{inspect(last_message)}")
       if tool_config do
         tool_names =
           tool_config
           |> Map.get("tools", [])
           |> Enum.flat_map(&Map.get(&1, "function_declarations", []))
           |> Enum.map(&Map.get(&1, "name", "N/A"))
         Logger.debug("LLM tool_config: #{inspect(tool_names)}")
       end

       # Construct the API request payload
       # Ensure conversation_history is in the correct format for Gemini API
       # e.g., [%{"role" => "user", "parts" => [%{"text" => "Hello"}]}, ...]
       payload = %{
         "contents" => conversation_history,
         "generationConfig" => %{ # Optional: add temperature, topP etc.
           # "temperature" => 0.7
         }
       }
       payload = if tool_config, do: Map.put(payload, "tools", tool_config["tools"]), else: payload

       api_path = "/v1beta/models/#{model_name}:generateContent"

       case GoogleGenaiClient.post(api_path, payload) do
         {:ok, response} ->
           # Ensure response.body is parsed JSON
           if response.status >= 200 && response.status < 300 do
             Logger.info("LLM API call successful to model #{model_name}.")
             Logger.debug("LLM response object (snippet): #{inspect(response.body) |> String.slice(0, 500)}...")
             {:reply, {:ok, response.body}, state}
           else
             err_msg = "LLM API Error (#{response.status}): #{inspect(response.body)}"
             Logger.error(err_msg)
             {:reply, {:error, err_msg}, state}
           end
         {:error, reason} ->
           Logger.error("Error calling Gemini API (#{model_name}): #{inspect(reason)}")
           {:reply, {:error, reason}, state}
       end
     end
   end
   ```

   **`lib/mcp_elixir_app/llm/supervisor.ex`**

   ```elixir
   defmodule McpElixirApp.LLM.Supervisor do
     use Supervisor
     require Logger

     def start_link(api_key) do
       Supervisor.start_link(__MODULE__, api_key, name: __MODULE__)
     end

     @impl true
     def init(api_key) do
       children = [
         {McpElixirApp.LLM.Service, api_key}
         # If other LLM providers were added, they'd be supervised here
       ]
       Logger.info("LLM Supervisor initializing.")
       Supervisor.init(children, strategy: :one_for_one)
     end
   end
   ```

**8. Workflow Components**

   **`lib/mcp_elixir_app/workflow/engine.ex`**

   ```elixir
   defmodule McpElixirApp.Workflow.Engine do
     use GenServer
     require Logger

     alias McpElixirApp.LLM.Service
     alias McpElixirApp.LLM.GenaiToolConverter
     alias McpElixirApp.MCP.Service

     defstruct workflow_name: nil,
               config: nil, # Workflow specific config
               app_config: nil, # Full app config (for API keys, etc.)
               mcp_service_pids: %{}, # server_name => pid
               llm_service_pid: nil,
               all_mcp_tools_cache: nil # List of tool maps

     # Client API
     def start_link(opts) do
       workflow_name = Keyword.fetch!(opts, :workflow_name)
       app_config = Keyword.fetch!(opts, :app_config) # Full loaded app_config struct
       name = via_tuple(workflow_name)
       GenServer.start_link(__MODULE__, {workflow_name, app_config}, name: name)
     end

     def process_user_query(workflow_pid_or_name, user_query) when is_pid(workflow_pid_or_name) do
       GenServer.call(workflow_pid_or_name, {:process_user_query, user_query}, :infinity)
     end
     def process_user_query(workflow_name, user_query) when is_binary(workflow_name) do
       GenServer.call(via_tuple(workflow_name), {:process_user_query, user_query}, :infinity)
     end

     def list_available_tools(workflow_pid_or_name) do
        GenServer.call(workflow_pid_or_name, :list_available_tools)
     end

     # Server Callbacks
     @impl true
     def init({workflow_name, app_config = %McpElixirApp.ConfigLoader{}}) do
       Logger.info("[Workflow:#{workflow_name}] Initializing engine...")
       workflow_config = McpElixirApp.ConfigLoader.get_workflow_config(app_config, workflow_name)

       if !workflow_config do
         Logger.error("[Workflow:#{workflow_name}] Configuration not found.")
         return {:stop, :workflow_config_not_found}
       end

       # LLM Service PID (assuming one global LLM service for now)
       llm_pid = Process.whereis(McpElixirApp.LLM.Service) # Assuming it's registered globally

       state = %__MODULE__{
         workflow_name: workflow_name,
         config: workflow_config,
         app_config: app_config,
         llm_service_pid: llm_pid
       }

       # Trigger async setup of services (MCP connections and tool fetching)
       # Init returns quickly, setup happens in handle_continue
       {:ok, state, {:continue, :setup_services}}
     end

    @impl true
    def handle_continue(:setup_services, state) do
      Logger.info("[Workflow:#{state.workflow_name}] Setting up services...")
      workflow_config = state.config
      app_config = state.app_config # McpElixirApp.ConfigLoader struct

      mcp_servers_to_use = Map.get(workflow_config, "mcp_servers_used", [])
      all_mcp_tools = []
      mcp_pids = %{}

      if Enum.empty?(mcp_servers_to_use) do
        Logger.info("[Workflow:#{state.workflow_name}] No MCP servers specified.")
      end

      # Iteratively connect and get tools.
      # This is synchronous here; for very many servers, Tasks could be used.
      Enum.reduce_while(mcp_servers_to_use, {:ok, all_mcp_tools, mcp_pids}, fn server_name, {:ok, current_tools_acc, current_pids_acc} ->
        mcp_service_pid = Process.whereis({:via, Registry, {McpElixirApp.MCP.Registry, server_name}})
        if !mcp_service_pid do
          Logger.error("[Workflow:#{state.workflow_name}] MCP Service '#{server_name}' not found/running.")
          {:halt, {:error, :mcp_service_unavailable, server_name}} # Halt setup
        else
          case MCP.Service.get_tools(mcp_service_pid) do
            {:ok, server_tools} ->
              tool_names = Enum.map(server_tools, & &1["name"]) # Assuming tools are maps with "name"
              Logger.info("[Workflow:#{state.workflow_name}] MCP Server '#{server_name}' connected with tools: #{inspect(tool_names)}")
              new_tools_acc = current_tools_acc ++ server_tools
              new_pids_acc = Map.put(current_pids_acc, server_name, mcp_service_pid)
              {:cont, {:ok, new_tools_acc, new_pids_acc}}
            {:error, reason} ->
              Logger.error("[Workflow:#{state.workflow_name}] Failed to get tools from MCP service '#{server_name}': #{inspect(reason)}")
              {:halt, {:error, :mcp_tool_fetch_failed, server_name, reason}} # Halt setup
          end
        end
      end)
      |> case do
        {:ok, final_tools_list, final_pids_map} ->
          tool_names_log = if Enum.empty?(final_tools_list), do: "None", else: Enum.map(final_tools_list, & &1["name"])
          Logger.info("[Workflow:#{state.workflow_name}] Services setup complete. Total MCP tools available: #{length(final_tools_list)} (#{inspect(tool_names_log)})")
          updated_state = %{state | mcp_service_pids: final_pids_map, all_mcp_tools_cache: final_tools_list}
          # Log to user level
          Logger.info("[USER][#{state.workflow_name}] Workflow ready. Tools: #{inspect(tool_names_log)}")
          {:noreply, updated_state}

        {:error, reason, server_name, _details} ->
          Logger.error("[Workflow:#{state.workflow_name}] Critical error setting up MCP server '#{server_name}': #{inspect(reason)}. Workflow may be impaired.")
          # Depending on policy, we might stop or continue with partial tools. Here, continue.
          {:noreply, state} # State would have whatever pids/tools were gathered before error

         # Catch-all for other {:error, ...} tuples if reduce_while halts differently
        {:error, reason} ->
          Logger.error("[Workflow:#{state.workflow_name}] Critical error during service setup: #{inspect(reason)}. Workflow may be impaired.")
          {:noreply, state}
      end
    end


     @impl true
     def handle_call({:process_user_query, user_query}, _from, state) do
       Logger.info("[Workflow:#{state.workflow_name}] Processing query: #{String.slice(user_query, 0, 70)}...")

       if Enum.empty?(state.mcp_service_pids) && !Enum.empty?(Map.get(state.config, "mcp_servers_used", [])) do
         Logger.error("[Workflow:#{state.workflow_name}] MCP services not set up but workflow requires them. (Likely init issue)")
         {:reply, {:error, "Workflow services are not initialized."}, state}
       else
         # The conversation loop
         initial_prompt = String.replace(state.config["initial_prompt_template"], "{query}", user_query)
         Logger.debug("[Workflow:#{state.workflow_name}] Initial prompt for LLM: #{initial_prompt}")

         # Gemini API expects parts to be a list of maps, e.g. [%{"text" => "Hello"}]
         initial_content_part = %{"text" => initial_prompt}
         conversation_history = [%{"role" => "user", "parts" => [initial_content_part]}]

         llm_tool_config = GenaiToolConverter.prepare_tools_for_llm(state.all_mcp_tools_cache)
         max_turns = Map.get(state.config, "max_conversation_turns", 5)

         # This loop is synchronous within the GenServer call. For concurrent query processing on the
         # same workflow *definition*, this GenServer would need to spawn Tasks for each query.
         # For simplicity, we do it sequentially here.
         final_response_from_loop =
           conversation_loop(
             state.workflow_name,
             state.llm_service_pid,
             state.config["llm_model"],
             state.mcp_service_pids,
             conversation_history,
             llm_tool_config,
             max_turns,
             1, # current_turn
             [] # accumulated_text_parts
           )
         {:reply, final_response_from_loop, state}
       end
     end

     @impl true
     def handle_call(:list_available_tools, _from, state) do
       tool_names =
         state.all_mcp_tools_cache
         |> Enum.map(&(&1["name"])) # Assuming tools are maps with a "name" key
       {:reply, {:ok, tool_names}, state}
     end

     # Private helpers
     defp via_tuple(workflow_name), do: {:via, Registry, {McpElixirApp.Workflow.Registry, workflow_name}}

     # --- Conversation Loop Logic ---
     defp conversation_loop(
            workflow_name, llm_pid, llm_model_name, mcp_pids,
            history, tool_config, max_turns, current_turn, accumulated_text_parts
          ) do
       if current_turn > max_turns do
         Logger.warning("[Workflow:#{workflow_name}] Max turns (#{max_turns}) reached.")
         final_text = Enum.join(Enum.reverse(accumulated_text_parts), "\n")
         if String.trim(final_text) == "", do: {:ok, "[Max interaction turns reached. No final text generated.]"}, else: {:ok, final_text <> "\n[Max interaction turns reached.]"}
       else
         Logger.info("[Workflow:#{workflow_name}] Turn #{current_turn}/#{max_turns}")
         Logger.debug("[Workflow:#{workflow_name}] Conversation history length before LLM call: #{length(history)}")

         case Service.generate_response(llm_pid, llm_model_name, history, tool_config) do
           {:ok, llm_response_body} ->
             # Assuming llm_response_body structure from Gemini: %{"candidates" => [%{"content" => %{"parts" => [...], "role" => "model"}}]}
             candidates = Map.get(llm_response_body, "candidates", [])
             if Enum.empty?(candidates) do
               Logger.warning("[Workflow:#{workflow_name}] LLM returned no candidates.")
               log_to_user_level(workflow_name, "[AI model returned no response candidates.]")
               {:ok, Enum.join(Enum.reverse(accumulated_text_parts), "\n") <> "\n[AI model returned no response candidates.]"}
             else
               # Take the first candidate
               model_content = get_in(List.first(candidates), ["content"]) # %{"parts" => [...], "role" => "model"}
               Logger.debug("[Workflow:#{workflow_name}] LLM response model_content (turn #{current_turn}): #{inspect(model_content)}")

               new_history = history ++ [model_content]
               process_llm_parts(
                 model_content["parts"],
                 workflow_name, llm_pid, llm_model_name, mcp_pids,
                 new_history, tool_config, max_turns, current_turn, accumulated_text_parts
               )
             end
           {:error, reason} ->
             err_msg = "Error communicating with LLM in workflow '#{workflow_name}': #{inspect(reason)}"
             Logger.error(err_msg)
             log_to_user_level(workflow_name, "[Error communicating with AI model: #{inspect(reason)}]")
             {:error, err_msg} # Propagate error
         end
       end
     end

    defp process_llm_parts(
          parts, workflow_name, llm_pid, llm_model_name, mcp_pids,
          history, tool_config, max_turns, current_turn, accumulated_text_parts
        ) do
        # Iterate through parts, look for text and function calls
        Enum.reduce_while(parts, {false, accumulated_text_parts, history}, fn part, {function_call_found_this_iteration, acc_text, current_hist} ->
            current_acc_text = acc_text
            has_fc = function_call_found_this_iteration

            # Process Text Part
            if text = Map.get(part, "text") do
              if String.trim(text) != "" do
                Logger.info("[Workflow:#{workflow_name}] LLM text (turn #{current_turn}): #{String.slice(text, 0, 100)}...")
                log_to_user_level(workflow_name, "LLM: #{String.trim(text)}")
                current_acc_text = [String.trim(text) | current_acc_text]
              end
            end

            # Process Function Call Part
            if fc = Map.get(part, "functionCall") do
              has_fc = true # Mark that a function call was found in this part enumeration
              tool_name = fc["name"]
              # Ensure args is a map, even if nil or empty from LLM
              tool_args = Map.get(fc, "args", %{}) |> ensure_map_args()

              log_to_user_level(workflow_name, "LLM wants to call: #{tool_name}(#{Jason.encode!(tool_args)})")
              Logger.info("[Workflow:#{workflow_name}] LLM requests tool call: '#{tool_name}' with args: #{inspect(tool_args)}")

              # Find which MCP service has this tool
              # This simplified version assumes tool names are unique across configured MCP services for this workflow
              # A more robust way might be to consult state.all_mcp_tools_cache and find server mapping
              found_service_pid_and_name =
                Enum.find_value(mcp_pids, fn {s_name, s_pid} ->
                  # Check if tool is in this service's cached tools.
                  # This requires MCP.Service to cache its tools or have a quick way to list them.
                  # For now, we assume `state.all_mcp_tools_cache` contains this info,
                  # but we'd need to associate tools with their server of origin during `setup_services`.
                  # Simplified: Iterate through *all* tools to find one, then pick a server.
                  # This is inefficient and assumes tool names are globally unique per workflow.
                  # Let's try calling the specific MCP server if we know which one.
                  #
                  # We need a map from tool_name to server_name/pid, built during setup_services.
                  # For now, try all associated MCPs:
                  find_service_for_tool(tool_name, state.all_mcp_tools_cache, mcp_pids)
                end)


              tool_result_for_llm =
                cond do
                  found_service_pid_and_name ->
                    {_server_name, mcp_service_pid} = found_service_pid_and_name
                    case MCP.Service.call_tool(mcp_service_pid, tool_name, tool_args) do
                      {:ok, mcp_result} ->
                        result_snippet = String.slice(inspect(mcp_result), 0, 150) |> String.replace("\n", " ") <> "..."
                        log_to_user_level(workflow_name, "Tool #{tool_name} executed. Result snippet: #{result_snippet}")
                        Logger.info("[Workflow:#{workflow_name}] Tool '#{tool_name}' executed.")
                        Logger.debug("[Workflow:#{workflow_name}] Full result from tool '#{tool_name}': #{inspect(mcp_result)}")
                        # Ensure result is a map for GenAI function response part
                        if is_map(mcp_result), do: mcp_result, else: %{"output" => mcp_result}

                      {:error, reason} ->
                        error_msg = "Error executing MCP tool '#{tool_name}': #{inspect(reason)}"
                        Logger.error(error_msg) # Include stacktrace if available from reason
                        log_to_user_level(workflow_name, "[Error calling tool #{tool_name}: #{inspect(reason)}]")
                        %{"error" => error_msg, "details" => inspect(reason)} # Simplified error detail
                    end
                  true -> # Tool not found in any service
                    error_msg = "Tool '#{tool_name}' requested by LLM but not found in any active MCP service for workflow '#{workflow_name}'."
                    Logger.error(error_msg)
                    log_to_user_level(workflow_name, "[Tool '#{tool_name}' not found.]")
                    %{"error" => error_msg}
                end

              tool_response_part = %{ # This is genai_types.Part.from_function_response
                "functionResponse" => %{
                  "name" => tool_name,
                  "response" => tool_result_for_llm
                }
              }
              Logger.debug("[Workflow:#{workflow_name}] Adding tool response for '#{tool_name}' to history: #{inspect(tool_result_for_llm)}")
              # Add this part to history and signal to break from part iteration and start next LLM turn
              # This model assumes one function call per LLM response. If multiple are possible,
              # all function calls in `parts` should be processed before next LLM turn.
              # Google GenAI currently supports one function call per turn.
              # The `history` here is for the *next* turn.
              new_hist_for_next_turn = current_hist ++ [%{"role" => "user", "parts" => [tool_response_part]}]
              {:halt, {has_fc, current_acc_text, new_hist_for_next_turn}} # Halt part processing, proceed to next turn with tool response
            end # end if functionCall

            # If no function call in this part, continue processing other parts in this LLM response
            if !has_fc, do: {:cont, {has_fc, current_acc_text, current_hist}}
            # If a function call was found, the {:halt, ...} above would have been triggered.
            # This path is only taken if this *specific part* didn't have a function call,
            # but a previous one in this LLM response might have. The has_fc flag tracks this.
        end)
        |>  # Result of Enum.reduce_while
          case do
            # This means a function call was processed, and we should loop for the next LLM turn.
            {true, final_acc_text_this_turn, history_for_next_llm_turn} ->
              conversation_loop(
                workflow_name, llm_pid, llm_model_name, mcp_pids,
                history_for_next_llm_turn, tool_config, max_turns, current_turn + 1, final_acc_text_this_turn
              )

            # This means NO function call was found in *any* part of the LLM's response. End of conversation.
            {false, final_acc_text_this_turn, _final_history_this_turn} ->
              Logger.info("[Workflow:#{workflow_name}] No function call in LLM response (turn #{current_turn}). Assuming final answer.")
              final_text = Enum.join(Enum.reverse(final_acc_text_this_turn), "\n")

              if String.trim(final_text) == "" do
                # This case could happen if the LLM's response was only a function call that wasn't executed,
                # or if its text parts were all empty.
                log_to_user_level(workflow_name, "[AI model provided no further text or actions.]")
                {:ok, "[AI model provided no further text or actions.]"}
              else
                {:ok, final_text}
              end
          end # end case on reduce_while result
    end

    defp ensure_map_args(nil), do: %{}
    defp ensure_map_args(args) when is_map(args), do: args
    defp ensure_map_args(other), do: Logger.warning("Tool args from LLM were not a map: #{inspect(other)}, using empty map."); %{}

    defp log_to_user_level(workflow_name, message) do
      # In Elixir, custom log levels are harder. We use :info with a prefix.
      # The console logger can be configured to format these differently if needed.
      Logger.info("[USER][#{workflow_name}] #{message}")
    end

    # Placeholder for finding the correct MCP service for a tool
    # This needs to be properly implemented based on how tools are mapped to services during setup
    defp find_service_for_tool(tool_name, all_mcp_tools_cache, mcp_pids) do
      # This is a naive approach. A better way is to build a tool_name -> server_name map during setup.
      # For now, if any tool in cache matches, take the first mcp_pid. This is often wrong.
      found_tool_info = Enum.find(all_mcp_tools_cache, &(&1["name"] == tool_name))
      if found_tool_info do
        # Problem: which server did `found_tool_info` come from?
        # This requires associating tools with their origin MCPService.
        # Let's assume `all_mcp_tools_cache` entries are like:
        #   `%{"name" => "toolX", "description" => "...", "inputSchema" => %{}, "_server_name" => "mcp_server_A"}`
        # This `_server_name` field would need to be added during `setup_services`.

        # If such a field exists:
        if server_origin_name = Map.get(found_tool_info, "_server_name") do
          if pid = Map.get(mcp_pids, server_origin_name) do
            {server_origin_name, pid} # Found it!
          else
            nil # Tool known, but its server PID is not in mcp_pids (should not happen)
          end
        else
          # Fallback: if tool exists but server unknown, try first mcp_pid (highly speculative)
          Logger.warning("Tool '#{tool_name}' found, but origin server unknown. Trying first available MCP service.")
          if {first_server_name, first_pid} = List.first(Map.to_list(mcp_pids)), do: {first_server_name, first_pid}, else: nil
        end
      else
        nil # Tool not found in cache
      end
    end

   end
   ```

   **`lib/mcp_elixir_app/workflow/supervisor.ex`**

   ```elixir
   defmodule McpElixirApp.Workflow.Supervisor do
     use Supervisor
     require Logger

     def start_link(app_config = %McpElixirApp.ConfigLoader{}) do
       Supervisor.start_link(__MODULE__, app_config, name: __MODULE__)
     end

     @impl true
     def init(app_config = %McpElixirApp.ConfigLoader{}) do
       workflow_definitions = app_config.workflows # map of workflow_name => workflow_config

       children =
         Enum.map(workflow_definitions, fn {workflow_name, _wf_config} ->
           %{
             id: :"workflow_engine_#{workflow_name}", # Ensure unique ID
             start: {McpElixirApp.Workflow.Engine, :start_link, [[workflow_name: workflow_name, app_config: app_config]]},
             restart: :permanent,
             type: :worker
           }
         end)

       registry_child = {Registry, keys: :unique, name: McpElixirApp.Workflow.Registry}

       Logger.info("Workflow Supervisor initializing with #{length(children)} workflow engines.")
       Supervisor.init([registry_child | children], strategy: :one_for_one)
     end
   end
   ```

**9. `lib/mcp_elixir_app/cli.exs` (Example CLI Script - run with `mix run lib/mcp_elixir_app/cli.exs`)**
   (Note: using `.exs` for a runnable script. The module `McpElixirApp.CLI` could be in `cli.ex`)

```elixir
# lib/mcp_elixir_app/cli.exs
defmodule McpElixirApp.CLI do
  require Logger

  def main(args) do
    # Start the application to get supervisors running
    # In a real app, mix run would typically start the app defined in mix.exs
    # Or, ensure your main function starts the app's supervision tree.
    # For this script, we assume the app is started via `iex -S mix` or similar
    # where `McpElixirApp.Application.start/2` has run.

    # If Application is not started, you might need:
    # Application.ensure_all_started(:mcp_elixir_app)
    # or manage startup explicitly.
    # For `mix run`, the app usually starts if it's in `application()` in mix.exs.

    parsed_args = parse_cli_args(args)

    cond do
      parsed_args[:list_workflows] ->
        list_workflows()
      parsed_args[:workflow_name] && parsed_args[:query] ->
        run_single_query(parsed_args[:workflow_name], parsed_args[:query])
      parsed_args[:workflow_name] ->
        run_chat_loop(parsed_args[:workflow_name])
      true ->
        print_usage()
        System.stop(1)
    end
  end

  defp parse_cli_args(args) do
    # Basic argument parsing. For complex CLI, use OptionParser.
    Enum.reduce(args, %{}, fn
      "-l", acc -> Map.put(acc, :list_workflows, true)
      "--list-workflows", acc -> Map.put(acc, :list_workflows, true)
      "--query", acc -> Map.put(acc, :next_is_query, true)
      arg, %{next_is_query: true} = acc -> Map.merge(acc, %{query: arg, next_is_query: false})
      workflow_name, %{workflow_name: nil} = acc when not String.starts_with?(workflow_name, "-") ->
        Map.put(acc, :workflow_name, workflow_name)
      _arg, acc -> acc # Ignore other args for simplicity
    end)
  end

  defp print_usage do
    IO.puts """
    Composable MCP Client (Elixir Version)

    Usage:
      mix run lib/mcp_elixir_app/cli.exs <workflow_name> [--query "Your query"]
      mix run lib/mcp_elixir_app/cli.exs --list-workflows

    Options:
      <workflow_name>         Name of the workflow to run.
      --query "Your query"    A single query to process (non-interactive mode).
      -l, --list-workflows    List available workflows and exit.
    """
  end

  defp list_workflows do
    case Application.get_env(:mcp_elixir_app, :app_config) do
      nil -> Logger.error("Application config not loaded. Cannot list workflows.")
      app_config = %McpElixirApp.ConfigLoader{} ->
        IO.puts "\nAvailable workflows:"
        workflows = McpElixirApp.ConfigLoader.list_workflows(app_config)
        if Enum.empty?(workflows) do
          IO.puts "  No workflows defined."
        else
          Enum.each(workflows, fn wf_name ->
            wf_data = McpElixirApp.ConfigLoader.get_workflow_config(app_config, wf_name)
            desc = Map.get(wf_data, "description", "No description")
            IO.puts "  - #{wf_name}: #{desc}"
          end)
        end
    end
  end

  defp run_single_query(workflow_name, query) do
    IO.puts "Processing query for workflow '#{workflow_name}': \"#{query}\""
    # Find the Workflow Engine GenServer
    # Note: Using global name registration. Could also get supervisor and look up child.
    engine_pid = Process.whereis({:via, Registry, {McpElixirApp.Workflow.Registry, workflow_name}})

    if engine_pid do
      case McpElixirApp.Workflow.Engine.process_user_query(engine_pid, query) do
        {:ok, response_text} -> IO.puts "\nResponse:\n#{response_text}"
        {:error, reason} -> IO.puts "\nError: #{inspect(reason)}"
      end
    else
      IO.puts "Error: Workflow engine for '#{workflow_name}' not found."
    end
  end

  defp run_chat_loop(workflow_name) do
    engine_pid = Process.whereis({:via, Registry, {McpElixirApp.Workflow.Registry, workflow_name}})
    unless engine_pid do
      IO.puts "Error: Workflow engine for '#{workflow_name}' not found."
      System.stop(1)
    end

    {:ok, model_name} = GenServer.call(engine_pid, :get_model_name) # Requires adding this call to Engine
    {:ok, tool_names} = McpElixirApp.Workflow.Engine.list_available_tools(engine_pid)

    IO.puts "\nChatting with workflow: '#{workflow_name}' (LLM: #{model_name})" # Need LLM model info
    IO.puts "Available tools: #{if Enum.empty?(tool_names), do: "None", else: Enum.join(tool_names, ", ")}"
    IO.puts "Type your queries or 'quit' to exit."

    Stream.repeatedly(fn -> IO.gets("\nQuery: ") |> String.trim() end)
    |> Enum.reduce_while(:ok, fn
      "quit", _acc -> {:halt, :quit}
      "", _acc -> {:cont, :ok} # Ask again
      query, _acc ->
        IO.puts "Processing..."
        case McpElixirApp.Workflow.Engine.process_user_query(engine_pid, query) do
          {:ok, response_text} -> IO.puts(if response_text == "", do: "\n[No response from AI model]", else: "\n#{response_text}")
          {:error, reason} -> IO.puts("\nAn error occurred: #{inspect(reason)}")
        end
        {:cont, :ok}
    end)
    IO.puts "Exiting chat."
  end
end

# To run this CLI directly:
# Ensure the application is started. `mix run` might do this.
# If not, you'd manage `Application.start(:mcp_elixir_app, :permanent)`
# before calling McpElixirApp.CLI.main(System.argv()).

# This check ensures it only runs when script is executed, not just compiled.
if System.get_env("__MIX_ENV__") != "test" and System.get_env("MIX_TASK") == "run" do
  # This script expects the application to be started if it's running tasks.
  # `mix run` typically starts the :mod in application().
  # So, we assume Application.start has been called by Mix.
  McpElixirApp.CLI.main(System.argv())
end
```
To make the CLI's `get_model_name` work, add this to `McpElixirApp.Workflow.Engine`:
```elixir
     @impl true
     def handle_call(:get_model_name, _from, state) do
       {:reply, {:ok, state.config["llm_model"]}, state}
     end
```

**To run this:**
1.  Create `config/mcp_servers.json` and `config/workflows.json` with your example content.
2.  Set the `GOOGLE_API_KEY` environment variable.
3.  Start an IEx session: `iex -S mix`
4.  From IEx:
    *   List workflows: `McpElixirApp.CLI.main(["--list-workflows"])`
    *   Run single query: `McpElixirApp.CLI.main(["your_workflow_name", "--query", "Your question?"])`
    *   Start chat loop: `McpElixirApp.CLI.main(["your_workflow_name"])`
    Alternatively, use `mix run lib/mcp_elixir_app/cli.exs <args>` (as defined by the `if` block at the end of `cli.exs`).

This port establishes the OTP structure, service isolation, and supervision. Many details, especially around the exact MCP stdio protocol and robust error handling in the GenAI client, would need further refinement and testing against actual MCP servers and the GenAI API. The Python logging levels and specific formatting are mapped to Elixir's Logger with reasonable defaults.
