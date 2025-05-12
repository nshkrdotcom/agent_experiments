Okay, this is a great direction! Designing around Jido & Jido.AI from the start will give you a solid, extensible, and OTP-compliant foundation.

We'll do this in stages, as requested.

**Stage 0: Project Setup and Dependencies**

1.  **Create the new Elixir project:**
    ```bash
    mix new mcp_jido_app --sup
    cd mcp_jido_app
    ```

2.  **Add dependencies to `mix.exs`:**
    Open `mix.exs` and modify the `deps` function:

    ```elixir
    # mix.exs
    defmodule McpJidoApp.MixProject do
      use Mix.Project

      def project do
        [
          app: :mcp_jido_app,
          version: "0.1.0",
          elixir: "~> 1.15", # Or your preferred Elixir version
          elixirc_paths: elixirc_paths(Mix.env()),
          start_permanent: Mix.env() == :prod,
          deps: deps(),
          aliases: aliases()
        ]
      end

      def application do
        [
          mod: {McpJidoApp.Application, []},
          extra_applications: [:logger, :runtime_tools, :jido, :jido_ai] # Add :jido & :jido_ai
        ]
      end

      defp elixirc_paths(:test), do: ["lib", "test/support"]
      defp elixirc_paths(_), do: ["lib"]

      defp deps do
        [
          # Jido Core & AI
          {:jido, "~> 1.1.0-rc.2"}, # Use the latest compatible Jido version
          {:jido_ai, "~> 0.5.2"},  # Use the latest compatible Jido.AI version

          # JSON parsing
          {:jason, "~> 1.4"},

          # HTTP client for potential direct API calls / MCP server interactions
          # (Jido.AI actions might abstract this away for LLMs)
          {:tesla, "~> 1.7.0"},
          {:hackney, "~> 1.18"}, # Or another Tesla adapter like Finch
          {:castore, "~> 1.0"},  # For Tesla SSL certs

          # For CLI argument parsing
          {:optimus, "~> 0.2.0"}, # Or use OptionParser

          # For development and testing
          {:credo, "~> 1.7", only: [:dev, :test], runtime: false},
          {:dialyxir, "~> 1.4", only: [:dev, :test], runtime: false}
        ]
      end

      defp aliases do
        [
          # Example alias for running a CLI script
          "run.cli": "run lib/mcp_jido_app/cli.exs"
        ]
      end
    end
    ```

3.  **Fetch dependencies:**
    ```bash
    mix deps.get
    ```

**Stage 1: Configuration and Core Application Setup**

This stage sets up the basic OTP application, configuration loading, and the main supervisor.

*   **`config/config.exs`** (Base Application Configuration)

    ```elixir
    # config/config.exs
    import Config

    config :logger,
      level: :info,
      format: "$time $metadata[$level] $message\n",
      metadata: [:module, :line]

    # Define where to find custom JSON configuration files
    config :mcp_jido_app,
      mcp_servers_path: Path.expand("config/mcp_servers.json", __DIR__),
      workflows_path: Path.expand("config/workflows.json", __DIR__)

    # Import environment-specific configs
    import_config "#{config_env()}.exs"
    ```

*   **`config/dev.exs`** (Development Specific Configuration)

    ```elixir
    # config/dev.exs
    import Config

    config :logger, level: :debug

    # Jido AI Keyring - will load .env files by default
    # Ensure your GOOGLE_API_KEY (or GEMINI_API_KEY) is in .env or system env
    # For explicit key setting for dev (not recommended for production):
    # config :jido_ai, Jido.AI.Keyring,
    #   google_api_key: "your-dev-google-api-key" # Better to use .env

    # If you have local mock MCP servers for development:
    # config :mcp_jido_app, :mcp_server_overrides, %{
    #   "local_weather_tool" => %{"command" => "./scripts/mock_mcp_weather", "args" => []}
    # }
    ```

*   **Create `config/mcp_servers.json`** (Example - adapt to your needs)

    ```json
    // config/mcp_servers.json
    {
      "mcpServers": {
        "generic_stdio_tool": {
          "description": "A generic tool accessible via stdio.",
          "command": "python3",
          "args": ["-u", "path/to/your/mcp_tool_script.py"],
          "env": {
            "PYTHONUNBUFFERED": "1"
          },
          "tools_provided": [
            {
              "name": "do_example_task",
              "description": "Performs an example task.",
              "inputSchema": {
                "type": "object",
                "properties": {
                  "param1": {"type": "string", "description": "First parameter"},
                  "param2": {"type": "integer", "description": "Second parameter"}
                },
                "required": ["param1"]
              }
            }
          ]
        }
      }
    }
    ```
    *Note: The `tools_provided` structure is a bit different from your Python setup. In Jido, each `Jido.Action` defines its schema. We'll load this to help create specific `Jido.Action` modules dynamically or to inform the Workflow Agent.*

*   **Create `config/workflows.json`** (Example)

    ```json
    // config/workflows.json
    {
      "workflows": {
        "simple_mcp_workflow": {
          "description": "A simple workflow that uses one MCP tool and Gemini.",
          "llm_model_provider": "google", // Using Jido.AI.Model provider ID
          "llm_model_name": "gemini-1.5-flash-latest", // Specific model string
          "mcp_servers_used": ["generic_stdio_tool"], // Names from mcp_servers.json
          "initial_prompt_template": "You are a helpful assistant. You have access to a tool named 'do_example_task'. Given the query: {query}, decide if you need to use the tool. If so, call it. Otherwise, answer directly.",
          "max_conversation_turns": 5
        }
      }
    }
    ```

*   **Create `.env` file in the project root:**
    ```
    # .env
    GOOGLE_API_KEY=your_actual_google_api_key_here
    # or GEMINI_API_KEY=your_actual_google_api_key_here
    ```

*   **`lib/mcp_jido_app/application.ex`** (Main OTP Application)

    ```elixir
    # lib/mcp_jido_app/application.ex
    defmodule McpJidoApp.Application do
      use Application
      require Logger

      @impl true
      def start(_type, _args) do
        Logger.info("Starting McpJidoApp...")

        # Jido.AI.Keyring will load .env automatically
        children = [
          Jido.AI.Keyring, # Must be started for Jido.AI.Model to get keys
          McpJidoApp.ConfigLoader, # Loads custom JSON configs
          McpJidoApp.CoreSupervisor
        ]

        opts = [strategy: :one_for_one, name: McpJidoApp.MainSupervisor]
        result = Supervisor.start_link(children, opts)
        Logger.info("McpJidoApp started successfully.")
        result
      end
    end
    ```

*   **`lib/mcp_jido_app/core_supervisor.ex`** (Top-level Supervisor for services)

    ```elixir
    # lib/mcp_jido_app/core_supervisor.ex
    defmodule McpJidoApp.CoreSupervisor do
      use Supervisor
      require Logger

      def start_link(init_arg) do
        Supervisor.start_link(__MODULE__, init_arg, name: __MODULE__)
      end

      @impl true
      def init(_init_arg) do
        Logger.info("CoreSupervisor initializing...")

        # Fetch loaded configuration. ConfigLoader puts it in app env.
        app_config = Application.get_env(:mcp_jido_app, :app_config, %{})
        mcp_server_configs = Map.get(app_config, :mcp_servers, %{})
        workflow_configs = Map.get(app_config, :workflows, %{})

        children = [
          {McpJidoApp.MCP.Supervisor, mcp_server_configs},
          {McpJidoApp.Workflow.Supervisor, workflow_configs}
        ]

        Supervisor.init(children, strategy: :one_for_one)
      end
    end
    ```

*   **`lib/mcp_jido_app/config_loader.ex`** (GenServer to load JSON configs)
    *This GenServer loads configs and puts them into the Application environment. Simpler than full `AppConfig` class behavior for now but effective.*

    ```elixir
    # lib/mcp_jido_app/config_loader.ex
    defmodule McpJidoApp.ConfigLoader do
      use GenServer
      require Logger

      def start_link(_opts) do
        GenServer.start_link(__MODULE__, :ok, name: __MODULE__)
      end

      @impl true
      def init(:ok) do
        Logger.info("ConfigLoader initializing...")
        mcp_path = Application.fetch_env!(:mcp_jido_app, :mcp_servers_path)
        workflows_path = Application.fetch_env!(:mcp_jido_app, :workflows_path)

        with {:ok, mcp_servers_raw} <- File.read(mcp_path),
             {:ok, mcp_data} <- Jason.decode(mcp_servers_raw),
             mcp_servers = Map.get(mcp_data, "mcpServers", %{}),
             # TODO: Add validation for mcp_servers structure here

             {:ok, workflows_raw} <- File.read(workflows_path),
             {:ok, workflows_data} <- Jason.decode(workflows_raw),
             workflows = Map.get(workflows_data, "workflows", %{})
             # TODO: Add validation for workflows structure here
        do
          app_config = %{
            mcp_servers: mcp_servers,
            workflows: workflows
          }
          Application.put_env(:mcp_jido_app, :app_config, app_config)
          Logger.info("Custom JSON configurations loaded and validated.")
          {:ok, :no_state_needed}
        else
          {:error, reason} ->
            Logger.error("Failed to load JSON configurations: #{inspect(reason)}")
            {:stop, {:config_load_failed, reason}}
        end
      end
    end
    ```

At this point, your application should compile: `mix compile`

**Stage 2: MCP Server Abstraction and Jido Actions**

We'll define how MCP servers are managed and how their tools are represented as Jido Actions.

*   **`lib/mcp_jido_app/mcp/server.ex`** (`GenServer` for each MCP server process)

    ```elixir
    # lib/mcp_jido_app/mcp/server.ex
    defmodule McpJidoApp.MCP.Server do
      use GenServer
      require Logger

      @request_timeout 15_000 # 15 seconds

      defstruct server_name: nil,
                config: nil,
                port_process: nil, # Holds the Port
                requests: %{}, # ref => {caller, timer_ref}
                tools_cache: nil,
                initialized: false

      # Client API
      def start_link(opts) do
        server_name = Keyword.fetch!(opts, :server_name)
        config = Keyword.fetch!(opts, :config)
        GenServer.start_link(__MODULE__, {server_name, config}, name: via_registry_name(server_name))
      end

      def list_tools(pid_or_name) do
        GenServer.call(pid_or_name, :list_tools, @request_timeout)
      end

      def call_tool(pid_or_name, tool_name, args) do
        GenServer.call(pid_or_name, {:call_tool, tool_name, args}, @request_timeout * 2)
      end

      def via_registry_name(server_name) do
        {:via, Registry, {McpJidoApp.MCP.Registry, server_name}}
      end


      # Server Callbacks
      @impl true
      def init({server_name, config}) do
        Logger.info("[MCP Server #{server_name}] Initializing with config: #{inspect(config)}")
        # Simplified: Port opening and initialization command would happen here
        # For now, we assume it's "connected" and tools are from config for simplicity.
        # In a real scenario, you'd open Port, send "initialize", "list_tools".

        tools_from_config = Map.get(config, "tools_provided", [])
        # Convert to a map for easier lookup by Jido Actions
        tools_cache =
          Enum.into(tools_from_config, %{}, fn tool_def ->
            {tool_def["name"], tool_def}
          end)


        state = %__MODULE__{
          server_name: server_name,
          config: config,
          tools_cache: tools_cache, # Populate from config for now
          initialized: true # Assume initialized for now
        }
        {:ok, state}
      end

      @impl true
      def handle_call(:list_tools, _from, state = %{initialized: true, tools_cache: tools}) do
        Logger.debug("[MCP Server #{state.server_name}] Responding with cached tools.")
        # Return tools as a list of maps as defined in config for now
        tool_list = Map.values(tools)
        {:reply, {:ok, tool_list}, state}
      end
      def handle_call(:list_tools, _from, state) do
        Logger.warning("[MCP Server #{state.server_name}] Attempted to list tools before initialized.")
        {:reply, {:error, :not_initialized}, state}
      end

      @impl true
      def handle_call({:call_tool, tool_name, args}, _from, state = %{initialized: true}) do
        Logger.info("[MCP Server #{state.server_name}] Calling tool '#{tool_name}' with args: #{inspect(args)}")
        # Placeholder: In a real implementation, send to Port and await response.
        # For now, simulate success.
        # A more complex response might be:
        # {:ok, %{result_data: "Tool #{tool_name} executed with #{inspect(args)}", details: %{}}}
        response_content = %{"output" => "Tool '#{tool_name}' on '#{state.server_name}' called with #{inspect(args)}"}
        {:reply, {:ok, response_content}, state}
      end
      def handle_call({:call_tool, _tool_name, _args}, _from, state) do
         Logger.warning("[MCP Server #{state.server_name}] Attempted to call tool before initialized.")
        {:reply, {:error, :not_initialized}, state}
      end

      @impl true
      def terminate(reason, state) do
        Logger.info("[MCP Server #{state.server_name}] Terminating. Reason: #{inspect(reason)}")
        if state.port_process, do: Port.close(state.port_process)
        :ok
      end
    end
    ```

*   **`lib/mcp_jido_app/mcp/supervisor.ex`**

    ```elixir
    # lib/mcp_jido_app/mcp/supervisor.ex
    defmodule McpJidoApp.MCP.Supervisor do
      use Supervisor
      require Logger

      def start_link(mcp_server_configs) do
        Supervisor.start_link(__MODULE__, mcp_server_configs, name: __MODULE__)
      end

      @impl true
      def init(mcp_server_configs) do
        Logger.info("MCP.Supervisor initializing with #{map_size(mcp_server_configs)} servers.")
        children = [
          {Registry, keys: :unique, name: McpJidoApp.MCP.Registry}
          | Enum.map(mcp_server_configs, fn {server_name, config} ->
              Supervisor.child_spec(
                {McpJidoApp.MCP.Server, server_name: server_name, config: config},
                id: :"mcp_server_#{server_name}" # Unique ID for supervision
              )
            end)
        ]
        Supervisor.init(children, strategy: :one_for_one)
      end
    end
    ```

*   **`lib/mcp_jido_app/actions/mcp_tool_action.ex`** (A Generic Jido Action for MCP Tools)
    *This Action will be dynamically configured at runtime by the Agent based on the workflow.*

    ```elixir
    # lib/mcp_jido_app/actions/mcp_tool_action.ex
    defmodule McpJidoApp.Actions.McpToolAction do
      use Jido.Action # Will dynamically set name, description, schema later

      alias McpJidoApp.MCP.Server

      # This Action is generic. An Agent will configure specific instances of it
      # for each actual MCP tool, providing the correct name, description, and schema.

      @impl true
      def run(params, context) do
        # Context is expected to provide :mcp_server_name and :mcp_tool_name
        # This context will be set by the Agent when it plans this action.
        mcp_server_name = Map.fetch!(context, :mcp_server_name)
        mcp_tool_name = Map.fetch!(context, :mcp_tool_name) # This is the Jido.Action name

        # The Jido.Action `params` are the validated inputs for the specific MCP tool
        Logger.info("[McpToolAction for #{mcp_tool_name} on #{mcp_server_name}] Running with params: #{inspect(params)}")

        # Resolve the MCP Server GenServer PID
        mcp_server_pid = Server.via_registry_name(mcp_server_name)

        case Server.call_tool(mcp_server_pid, mcp_tool_name, params) do
          {:ok, result} ->
            Logger.debug("[McpToolAction for #{mcp_tool_name}] Result: #{inspect(result)}")
            {:ok, result} # Jido.Action expects {:ok, map_of_outputs}

          {:error, reason} ->
            Logger.error("[McpToolAction for #{mcp_tool_name}] Error: #{inspect(reason)}")
            {:error, Jido.Error.execution_error("MCP tool call failed: #{inspect(reason)}")}
        end
      end
    end
    ```

**Stage 3: Workflow Agent (Jido.AI.Agent)**

This is where the core logic of your Python `WorkflowEngine` will reside.

*   **`lib/mcp_jido_app/workflow/agent.ex`**

    ```elixir
    # lib/mcp_jido_app/workflow/agent.ex
    defmodule McpJidoApp.Workflow.Agent do
      use Jido.AI.Agent # Using Jido.AI.Agent for its AI-centric features

      alias Jido.Instruction
      alias Jido.AI.Model
      alias Jido.AI.Prompt
      alias Jido.AI.Actions.OpenaiEx # For LLM calls
      alias McpJidoApp.MCP.Server
      alias McpJidoApp.Actions.McpToolAction

      require Logger

      # Define agent state struct specific to this workflow agent
      defstruct workflow_config: %{},
                current_conversation_history: [], # List of Jido.AI.Prompt.MessageItem
                llm_model_struct: nil,
                available_mcp_actions: %{} # tool_name => %Jido.Action instance_config

      # --- Jido.Agent Callbacks ---
      @impl Jido.Agent
      def init(opts) do
        workflow_name = Keyword.fetch!(opts, :workflow_name)
        app_config = Application.get_env(:mcp_jido_app, :app_config, %{})
        workflow_config = Map.get(app_config.workflows, workflow_name)

        unless workflow_config do
          Logger.error("Workflow '#{workflow_name}' not found in configuration.")
          # This should ideally be caught before Agent.start_link
          # Returning an error from init can be tricky with Jido.Agent.Server
          # For now, log and proceed with an empty config which will likely fail later.
          # A more robust approach is to validate workflow_name before starting the agent.
          {:ok, %__MODULE__{}}
        else
          Logger.info("[WorkflowAgent #{workflow_name}] Initializing.")
          Logger.debug("Workflow config: #{inspect(workflow_config)}")

          # Prepare LLM Model struct
          llm_provider = String.to_atom(workflow_config["llm_model_provider"])
          llm_model_name = workflow_config["llm_model_name"]
          # API key will be fetched from Jido.AI.Keyring by the Jido.AI.Model.from/1 function

          case Model.from({llm_provider, [model: llm_model_name]}) do
            {:ok, llm_model_struct} ->
              Logger.info("LLM Model for #{workflow_name} prepared: #{inspect(llm_model_struct.name)}")

              # Prepare available MCP actions for this workflow
              available_mcp_actions =
                Enum.reduce(workflow_config["mcp_servers_used"], %{}, fn server_name, acc ->
                  mcp_server_config = Map.get(app_config.mcp_servers, server_name)
                  # `tools_provided` is from our mcp_servers.json
                  Enum.reduce(mcp_server_config["tools_provided"], acc, fn tool_def, inner_acc ->
                    action_config = %{
                      # Jido.Action expects :name, :description, :schema
                      name: tool_def["name"],
                      description: tool_def["description"],
                      schema: convert_json_schema_to_nimble(tool_def["inputSchema"])
                    }
                    Map.put(inner_acc, tool_def["name"], action_config)
                  end)
                end)

              initial_state = %__MODULE__{
                workflow_config: workflow_config,
                llm_model_struct: llm_model_struct,
                available_mcp_actions: available_mcp_actions
              }

              # The agent's state here is what `use Jido.Agent` manages internally.
              # The `initial_state` above is for *our* struct within the agent's GenServer state.
              # Jido.Agent's `cmd` will merge our `initial_state` into its `:state` field.
              {:ok, initial_state}

            {:error, reason} ->
              Logger.error("Failed to prepare LLM Model for #{workflow_name}: #{inspect(reason)}")
              # This init error needs to be handled correctly by the caller or supervisor
              {:error, {:llm_model_init_failed, reason}}
          end
        end
      end

      @impl Jido.Agent
      def actions(_agent_struct) do
        # This agent will dynamically plan instructions for McpToolAction or the LLM action.
        # So, we don't need to "register" them in the classic Jido.Agent sense here if
        # we construct Instructions manually.
        # However, Jido.AI.Agent might require registering the LLM actions.
        # For now, let's list the generic types we might invoke.
        [
          McpToolAction, # For MCP tool calls
          OpenaiEx       # For LLM calls via Jido.AI.Actions.OpenaiEx
        ]
      end

      # --- Public API (called via Agent.Server.call/cast or Jido.AI.Agent helpers) ---

      # This will be our main entry point, analogous to Python's process_user_query
      # We will trigger this via a signal to the GenServer.
      def process_user_query(agent_pid_or_name, user_query) do
        # We'll define a custom signal type for this.
        signal = %Signal{type: "mcp_workflow.user_query", data: %{query: user_query}}
        Jido.Agent.Server.call(agent_pid_or_name, signal, 60_000) # 60s timeout
      end

      # --- GenServer Callbacks (handle_signal) ---
      @impl Jido.Agent
      def handle_signal(%Signal{type: "mcp_workflow.user_query", data: %{query: user_query}}, agent_struct) do
        Logger.info("[#{agent_struct.id}] Received user query: #{user_query}")

        # Use the agent_struct.state which holds our %__MODULE__{} struct
        workflow_state = agent_struct.state
        workflow_config = workflow_state.workflow_config

        initial_prompt_text =
          String.replace(workflow_config["initial_prompt_template"], "{query}", user_query)

        # Initialize conversation history
        initial_prompt =
          Prompt.new()
          |> Prompt.add_message(:user, initial_prompt_text)

        conversation_result =
          run_conversation_loop(
            agent_struct.id, # For logging
            workflow_state.llm_model_struct,
            initial_prompt,
            workflow_state.available_mcp_actions, # Map of tool_name -> Jido Action config
            workflow_config["mcp_servers_used"],   # List of MCP server names to find PIDs
            workflow_config["max_conversation_turns"]
          )

        # The result of run_conversation_loop will be the final response string or an error
        # Jido.Agent handle_signal expects {:ok, new_signal} or {:error, reason}
        # For a chat-like interaction, the "result" is the agent's reply.
        # We might wrap this in a signal or return it directly if Jido.AI.Agent handles it.
        # For now, we return the final text as the result data of a new signal.
        final_response_signal_data =
          case conversation_result do
            {:ok, text_response} -> %{response: text_response}
            {:error, reason} -> %{error: inspect(reason)}
          end

        response_signal = %Signal{
          type: "mcp_workflow.final_response",
          data: final_response_signal_data,
          source: agent_struct.id # The agent is the source of this final response
        }

        # The `agent_struct` here is what Jido.Agent behavior expects.
        # The `workflow_state` changes (like conversation history) would ideally be
        # updated within the `agent_struct.state` if we were using `cmd` or directives
        # that modify agent state. For a simple `handle_signal` that returns a result,
        # we don't modify the agent_struct itself unless a Jido Runner pattern is used.
        {:ok, response_signal}
      end

      # --- Private Helper Functions ---
      defp run_conversation_loop(
             agent_id,
             llm_model_struct,
             current_prompt_history, # Jido.AI.Prompt struct
             available_mcp_actions_config, # tool_name -> Jido Action config
             mcp_server_names_used, # List of strings
             max_turns,
             current_turn \\ 1
           ) do
        if current_turn > max_turns do
          Logger.warning("[#{agent_id}] Max turns reached.")
          final_text = current_prompt_history |> Prompt.to_text() |> String.split("\n") |> List.last() |> String.trim_leading("[assistant] ")
          {:ok, final_text <> "\n[Max interaction turns reached.]"}
        else
          Logger.info("[#{agent_id}] Conversation turn #{current_turn}/#{max_turns}")

          # Prepare tools for LLM
          # Convert Jido Action schemas to GenAI tool format
          llm_tools_param =
            available_mcp_actions_config
            |> Enum.map(fn {_tool_name, action_config} ->
              # McpToolAction.to_tool/0 would typically use the action's actual schema.
              # Here, `action_config` is the schema itself.
              %{
                "type" => "function",
                "function" => %{
                  "name" => action_config.name,
                  "description" => action_config.description,
                  "parameters" => convert_nimble_schema_to_openai_params(action_config.schema)
                }
              }
            end)

          # Create LLM Instruction using Jido.AI.Actions.OpenaiEx
          llm_instruction_params = %{
            model: llm_model_struct,
            # messages: Prompt.render(current_prompt_history), # Convert Jido.AI.Prompt to list of maps
            prompt: current_prompt_history, # OpenaiEx action can take a Jido.AI.Prompt struct
            tools: llm_tools_param # This is now in OpenAI tool format
          }

          # Execute LLM call (simulated for now, should use Jido.Exec)
          case Jido.Exec.run(OpenaiEx, llm_instruction_params) do
            {:ok, llm_response_data} -> # llm_response_data from OpenaiEx is already a map %{content: ..., tool_results: ...}
              llm_text_content = llm_response_data.content
              llm_tool_calls = llm_response_data.tool_results # This will be a list of %{name: "tool_name", arguments: %{...}, result: nil}

              new_prompt_history =
                if llm_text_content do
                  Logger.info("[#{agent_id}] LLM Response Text: #{llm_text_content}")
                  Prompt.add_message(current_prompt_history, :assistant, llm_text_content)
                else
                  current_prompt_history
                end

              if llm_tool_calls && !Enum.empty?(llm_tool_calls) do
                # Assume one tool call per turn for simplicity, like Gemini
                tool_call = List.first(llm_tool_calls) # %{name: "tool_name", arguments: %{arg1: val1}, result: nil}
                tool_name_to_call = tool_call.name
                tool_args = tool_call.arguments # Already a map of atoms to values

                Logger.info("[#{agent_id}] LLM wants to call tool: #{tool_name_to_call} with args: #{inspect(tool_args)}")

                # Find the MCP server for this tool
                # This is a simplification; a real system needs a map of tool_name -> server_name
                # For now, try all associated MCP servers.
                # The `context` for McpToolAction needs `mcp_server_name` and `mcp_tool_name`.
                # The action_config for the specific tool is in `available_mcp_actions_config`.

                # Find the server that provides this tool
                found_server_name =
                  Enum.find_value(mcp_server_names_used, fn server_name ->
                    server_config_tools =
                      Application.get_env(:mcp_jido_app, :app_config, %{})
                      |> Map.get(:mcp_servers, %{})
                      |> Map.get(server_name, %{})
                      |> Map.get("tools_provided", [])
                      |> Enum.map(& &1["name"])

                    if tool_name_to_call in server_config_tools, do: server_name, else: nil
                  end)

                if found_server_name do
                  tool_action_config = Map.get(available_mcp_actions_config, tool_name_to_call)

                  mcp_tool_instruction = %Instruction{
                    action: McpToolAction, # The generic action
                    # Params are the validated args for the *specific* MCP tool
                    params: tool_args,
                    context: %{
                      mcp_server_name: found_server_name,
                      mcp_tool_name: tool_name_to_call, # Pass the Jido Action name
                      original_action_schema: tool_action_config.schema # For McpToolAction to use if needed
                    }
                  }

                  case Jido.Exec.run(mcp_tool_instruction) do
                    {:ok, tool_result_map} -> # McpToolAction returns a map like %{"output" => "..."}
                      # For Gemini, function response needs to be a map with a single "content" key or structured data.
                      # OpenAI expects a string or serializable object.
                      # Let's assume our McpToolAction returns a map with an "output" key
                      # which contains the actual content.
                      tool_output_for_llm =
                        if is_map(tool_result_map) and Map.has_key?(tool_result_map, "output") do
                          tool_result_map["output"] # Send just the content
                        else
                          inspect(tool_result_map) # Fallback
                        end

                      Logger.info("[#{agent_id}] Tool '#{tool_name_to_call}' executed. Result: #{inspect(tool_output_for_llm)}")

                      # Add tool call and result to prompt history
                      # The exact format depends on the LLM API (OpenAI vs Gemini).
                      # Jido.AI.Actions.OpenaiEx will handle converting its :messages format for the LLM.
                      # For our `current_prompt_history` (a Jido.AI.Prompt), we add structured messages.
                      updated_history_after_tool =
                        new_prompt_history
                        |> Prompt.add_message(:assistant, nil, # No text content for the assistant part of the tool call
                            # Jido.AI.Prompt does not have direct support for OpenAI's :tool_calls field.
                            # We simulate by adding a user message with function response.
                            # A more sophisticated Jido.AI.Prompt might handle this better.
                            # For OpenaiEx, we should add a `tool_call_id` and content to a :tool role message
                            # For now, we model it as Gemini requires, which is a "user" role function response.
                            # This part is tricky as Jido.AI.Prompt is generic.

                            # If using OpenaiEx directly with OpenAI tools, the prompt structure is different.
                            # For Gemini with Jido.AI.Actions.OpenaiEx, OpenaiEx should translate the function response for Gemini.
                            # The :tool_calls result from OpenaiEx gives the function *name* and *arguments*.
                            # The function *response* from the tool then needs to be added to the prompt history
                            # with the correct role.
                            #
                            # Gemini expects tool responses in a 'user' role part like:
                            # { "role": "user", "parts": [ { "functionResponse": { "name": "tool_name", "response": { "content": "..." } } } ] }

                            # Simulate this structure for our generic Jido.AI.Prompt for now.
                            # This is a placeholder for proper message construction for the specific LLM via Jido.AI.Actions.
                             content: %{ # This would need custom rendering if not string
                                function_response: %{
                                  name: tool_name_to_call,
                                  response: %{"output" => tool_output_for_llm} # Or just tool_output_for_llm if string
                                }
                             }
                           )

                      run_conversation_loop(
                        agent_id,
                        llm_model_struct,
                        updated_history_after_tool,
                        available_mcp_actions_config,
                        mcp_server_names_used,
                        max_turns,
                        current_turn + 1
                      )

                    {:error, tool_err} ->
                      Logger.error("[#{agent_id}] Error executing tool '#{tool_name_to_call}': #{inspect(tool_err)}")
                      # Add error message to history and continue
                      error_history = Prompt.add_message(new_prompt_history, :user, "[Error executing tool #{tool_name_to_call}: #{inspect(tool_err)}]")
                      run_conversation_loop(
                        agent_id,
                        llm_model_struct,
                        error_history,
                        available_mcp_actions_config,
                        mcp_server_names_used,
                        max_turns,
                        current_turn + 1
                      )
                  end
                else
                  Logger.error("[#{agent_id}] Tool '#{tool_name_to_call}' not found in any configured MCP server.")
                  error_history = Prompt.add_message(new_prompt_history, :user, "[Tool '#{tool_name_to_call}' not found.]")
                  run_conversation_loop(
                    agent_id,
                    llm_model_struct,
                    error_history,
                    available_mcp_actions_config,
                    mcp_server_names_used,
                    max_turns,
                    current_turn + 1
                  )
                end
              else
                # No tool call, LLM provided a text response. This is the final answer.
                final_text =
                  if llm_text_content,
                    do: llm_text_content,
                    else: "[AI model provided no text and no function call.]"
                {:ok, final_text}
              end

            {:error, llm_err} ->
              Logger.error("[#{agent_id}] Error communicating with LLM: #{inspect(llm_err)}")
              {:error, llm_err}
          end
        end
      end


      # Helper to convert JSON schema from config to NimbleOptions format
      # This is a simplified version. A real one would be more robust.
      defp convert_json_schema_to_nimble(json_schema) do
        properties = Map.get(json_schema, "properties", %{})
        required_keys = Map.get(json_schema, "required", []) |> Enum.map(&String.to_atom/1)

        Enum.map(properties, fn {name, prop_schema} ->
          type_str = Map.get(prop_schema, "type", "string")

          nimble_type =
            case type_str do
              "string" -> :string
              "integer" -> :integer
              "number" -> :float # Or handle integer/float distinction
              "boolean" -> :boolean
              "array" -> {:list, :any} # Basic list type
              "object" -> :map       # Basic map type
              _ -> :string # Default
            end

          required = String.to_atom(name) in required_keys
          description = Map.get(prop_schema, "description")

          config = [type: nimble_type]
          config = if required, do: Keyword.put(config, :required, true), else: config
          config = if description, do: Keyword.put(config, :doc, description), else: config
          {String.to_atom(name), config}
        end)
      end

      # Helper for converting Jido Action Nimble schema to OpenAI/GenAI function parameter schema
      defp convert_nimble_schema_to_openai_params(nimble_schema) when is_list(nimble_schema) do
        properties =
          Enum.reduce(nimble_schema, %{}, fn {name_atom, opts}, acc ->
            name_str = Atom.to_string(name_atom)
            json_type =
              case Keyword.get(opts, :type) do
                :string -> "string"
                :integer -> "integer"
                :float -> "number"
                :boolean -> "boolean"
                {:list, _} -> "array" # Simplified
                :map -> "object" # Simplified
                _ -> "string" # Default
              end
            prop_schema = %{"type" => json_type}
            prop_schema =
              if desc = Keyword.get(opts, :doc),
                do: Map.put(prop_schema, "description", desc),
                else: prop_schema
            Map.put(acc, name_str, prop_schema)
          end)

        required_fields =
          nimble_schema
          |> Enum.filter(fn {_name, opts} -> Keyword.get(opts, :required, false) end)
          |> Enum.map(fn {name, _opts} -> Atom.to_string(name) end)

        %{
          "type" => "object",
          "properties" => properties,
          "required" => if(Enum.empty?(required_fields), do: nil, else: required_fields) # OpenAI expects nil/omitted if no required
        }
        |> Enum.reject(fn {_k, v} -> is_nil(v) end) # Remove nil 'required' field
        |> Map.new()
      end

    end
    ```

*   **`lib/mcp_jido_app/workflow/supervisor.ex`**

    ```elixir
    # lib/mcp_jido_app/workflow/supervisor.ex
    defmodule McpJidoApp.Workflow.Supervisor do
      use Supervisor
      require Logger

      def start_link(workflow_configs) do
        Supervisor.start_link(__MODULE__, workflow_configs, name: __MODULE__)
      end

      @impl true
      def init(workflow_configs) do
        Logger.info("Workflow.Supervisor initializing with #{map_size(workflow_configs)} workflows.")
        children = [
          {Registry, keys: :unique, name: McpJidoApp.Workflow.Registry} # Registry for Agent PIDs
          | Enum.map(workflow_configs, fn {workflow_name, _config_data} ->
              # Jido.AI.Agent.start_link itself returns a GenServer.on_start()
              # which is what Supervisor.child_spec expects.
              {McpJidoApp.Workflow.Agent, # The Module of the Jido.AI.Agent
               [
                 name: {:via, Registry, {McpJidoApp.Workflow.Registry, workflow_name}},
                 workflow_name: workflow_name
                 # Other Jido.Agent.Server options like :log_level can go here
               ]}
            end)
        ]
        Supervisor.init(children, strategy: :one_for_one)
      end
    end
    ```

**Stage 4: Basic CLI for Interaction**

*   **`lib/mcp_jido_app/cli.exs`** (A simple script to run workflows)

    ```elixir
    # lib/mcp_jido_app/cli.exs
    defmodule McpJidoApp.CLI do
      require Logger

      alias McpJidoApp.Workflow.Agent # Our specific agent module

      def main(args) do
        # Ensure the main application (including Jido & Jido.AI) is started.
        # `mix run` usually handles this if :mod is set in mix.exs application.
        Application.ensure_all_started(:mcp_jido_app)
        # Also Jido's own application for TaskSupervisor etc.
        Application.ensure_all_started(:jido)
        Application.ensure_all_started(:jido_ai)


        {opts, [workflow_name | query_parts], _} =
          OptionParser.parse(args,
            strict: [list_workflows: :boolean, workflow_name: :string, query: :string]
          )

        cond do
          opts[:list_workflows] ->
            list_workflows()

          workflow_name && !Enum.empty?(query_parts) ->
            query = Enum.join(query_parts, " ")
            run_single_query(workflow_name, query)

          workflow_name ->
            run_chat_loop(workflow_name)

          true ->
            print_usage()
            System.stop(1)
        end
      end

      defp print_usage do
        IO.puts("""
        McpJidoApp CLI

        Usage:
          mix run.cli <workflow_name> <query_string>
          mix run.cli --list-workflows
        """)
      end

      defp list_workflows do
        app_config = Application.get_env(:mcp_jido_app, :app_config, %{})
        workflows = Map.get(app_config, :workflows, %{})
        IO.puts("\nAvailable workflows:")
        if Map.is_empty(workflows) do
          IO.puts("  No workflows defined in config/workflows.json")
        else
          Enum.each(workflows, fn {name, config} ->
            IO.puts("  - #{name}: #{config["description"] || "No description"}")
          end)
        end
      end

      defp run_single_query(workflow_name, query) do
        IO.puts("Processing query for workflow '#{workflow_name}': \"#{query}\"")

        # Agent PIDs are registered via Registry
        agent_pid = Jido.Util.whereis({workflow_name, McpJidoApp.Workflow.Registry})

        if agent_pid == {:error, :not_found} || is_nil(agent_pid) || (is_tuple(agent_pid) && elem(agent_pid,0) == :error) do
          IO.puts("Error: Workflow Agent '#{workflow_name}' not found or not running.")
          IO.inspect(agent_pid, label: "Agent PID lookup result")
          System.stop(1)
        else
          # Ensure it's a PID if not an error tuple
          actual_pid = if is_pid(agent_pid), do: agent_pid, else: elem(agent_pid, 1)

          case Agent.process_user_query(actual_pid, query) do
            # Assuming handle_signal now returns {:ok, response_signal}
            {:ok, %Jido.Signal{data: %{response: response_text}}} ->
              IO.puts("\nResponse:\n#{response_text}")

            {:ok, %Jido.Signal{data: %{error: error_reason}}} ->
               IO.puts("\nError processing query: #{error_reason}")

            {:error, reason} ->
              IO.puts("\nError calling workflow agent: #{inspect(reason)}")

            other ->
              IO.puts("\nUnexpected response from agent: #{inspect(other)}")
          end
        end
      end

      defp run_chat_loop(workflow_name) do
        agent_pid_or_error = Jido.Util.whereis({workflow_name, McpJidoApp.Workflow.Registry})

        case agent_pid_or_error do
         {:ok, agent_pid} ->
            IO.puts("\nChatting with workflow: '#{workflow_name}'. Type 'quit' to exit.")
            Stream.repeatedly(fn -> IO.gets("> ") |> String.trim() end)
            |> Enum.reduce_while(:ok, fn
              "quit", _ ->
                {:halt, :ok}
              "", _ ->
                {:cont, :ok} # Skip empty input
              query_str, _ ->
                case Agent.process_user_query(agent_pid, query_str) do
                  {:ok, %Jido.Signal{data: %{response: response_text}}} -> IO.puts(response_text)
                  {:ok, %Jido.Signal{data: %{error: error_reason}}} -> IO.puts("Error: #{error_reason}")
                  {:error, reason} -> IO.puts("Error: #{inspect(reason)}")
                  other -> IO.puts("Unexpected: #{inspect(other)}")
                end
                {:cont, :ok}
            end)
            IO.puts("Exiting chat.")
          _ ->
            IO.puts("Error: Workflow Agent '#{workflow_name}' not found or not running.")
            System.stop(1)
        end
      end
    end

    # Ensure it only runs when called directly
    if System.get_env("__MIX_ENV__") != "test" and System.get_env("MIX_TASK") == "run.cli" do
      McpJidoApp.CLI.main(System.argv())
    end
    ```

---

**To make this fully compilable and runnable (with caveats):**

1.  **Placeholders & Simplifications:**
    *   The `McpJidoApp.MCP.Server` currently uses hardcoded tool info from the config and simulates tool calls. Real stdio port management (`Port.open`, `Port.command`, async message handling) is needed.
    *   The `McpJidoApp.Actions.McpToolAction` assumes its `run/2` context will be populated with `:mcp_server_name` and `:mcp_tool_name` by the `Workflow.Agent`. Its `schema` would ideally be dynamically set when the Agent "instantiates" it for a specific tool.
    *   The conversion from NimbleOptions schema to OpenAI/GenAI tool schema (`convert_nimble_schema_to_openai_params`) is a basic placeholder. A robust implementation is complex.
    *   Error handling is basic.
    *   The `run_conversation_loop` in `Workflow.Agent` is a simplified synchronous loop within a `handle_signal`. For true concurrency and complex state management within the loop (e.g., waiting for tool calls without blocking the agent GenServer), you might use `Task.async` and `Task.await` or even a more dedicated `Jido.Runner.Chain` approach if the conversation steps can be mapped to a sequence of Jido Instructions.

2.  **Create a dummy MCP tool script:**
    For `generic_stdio_tool`, create `path/to/your/mcp_tool_script.py`:

    ```python
    # path/to/your/mcp_tool_script.py
    import sys
    import json
    import time

    # In a real script, this would be dynamic based on an "initialize" message
    TOOLS_AVAILABLE = {
        "do_example_task": {
            "description": "Performs an example task.",
            "inputSchema": {
                "type": "object",
                "properties": {
                  "param1": {"type": "string", "description": "First parameter"},
                  "param2": {"type": "integer", "description": "Second parameter"}
                },
                "required": ["param1"]
            }
        }
    }

    def main():
        # Simulate initialization or handshake if your protocol needs it
        # For example, you might expect an "initialize" message first.
        # print(json.dumps({"type": "ready"}), flush=True)

        for line in sys.stdin:
            try:
                request = json.loads(line.strip())
                # print(f"Python script received: {request}", file=sys.stderr, flush=True) # Debug

                response_id = request.get("id", "no_id")
                method = request.get("method")
                params = request.get("params", {})

                if method == "list_tools":
                    response = {"id": response_id, "result": list(TOOLS_AVAILABLE.values()), "method_echo": "list_tools"}
                elif method == "call_tool":
                    tool_name = params.get("tool_name")
                    args = params.get("args", {})
                    if tool_name == "do_example_task":
                        # Simulate tool execution
                        time.sleep(0.1)
                        param1_val = args.get("param1", "N/A")
                        param2_val = args.get("param2", 0)
                        tool_output = f"Example task done with param1='{param1_val}' and param2={param2_val}"
                        response = {"id": response_id, "result": {"output": tool_output}, "method_echo": "call_tool"}
                    else:
                        response = {"id": response_id, "error": {"message": f"Tool '{tool_name}' not found"}, "method_echo": "call_tool"}
                elif method == "initialize": # Handle Jido's MCP server init message
                    response = {"id": response_id, "result": {"status": "initialized", "tools": list(TOOLS_AVAILABLE.values())}, "method_echo": "initialize"}
                else:
                    response = {"id": response_id, "error": {"message": f"Unknown method '{method}'"}, "method_echo": method}

                print(json.dumps(response), flush=True)
            except json.JSONDecodeError:
                print(json.dumps({"id": "error", "error": {"message": "Invalid JSON request"}}), flush=True)
            except Exception as e:
                print(json.dumps({"id": "error", "error": {"message": f"Script error: {str(e)}"}}), flush=True)

    if __name__ == "__main__":
        main()
    ```
    *Make sure this script is executable (`chmod +x ...`) and the path in `mcp_servers.json` is correct.*

3.  **Run the CLI:**
    *   First compile: `mix compile`
    *   List workflows: `mix run.cli --list-workflows`
    *   Run a query: `mix run.cli simple_mcp_workflow "What can you do with param1 being test and param2 being 123?"`
        (This will likely fail if `McpJidoApp.MCP.Server` isn't fully implemented to send and receive from the port, or if the tool schema handling/conversion isn't perfect.)

**Key Jido/Jido.AI Concepts Used or Implied:**

*   **`Jido.Action`:** `McpJidoApp.Actions.McpToolAction` is a generic action for calling MCP tools. `Jido.AI.Actions.OpenaiEx` is used for LLM calls.
*   **`Jido.Agent` (via `Jido.AI.Agent`):** `McpJidoApp.Workflow.Agent` defines the core workflow logic.
*   **`Jido.AI.Model`:** Used to configure the Gemini LLM.
*   **`Jido.AI.Prompt`:** Used to manage the conversation history.
*   **`Jido.Instruction`:** While not explicitly created and queued via `Jido.Agent.plan/3` in this simplified `handle_signal` loop, the calls to `Jido.Exec.run` with an action module and params are effectively creating and running an instruction. A more advanced implementation using `Jido.Runner.Chain` would make this more explicit.
*   **Supervision:** The OTP application, `CoreSupervisor`, `MCP.Supervisor`, and `Workflow.Supervisor` set up the supervision tree.
*   **Registry:** Used to look up `MCP.Server` and `Workflow.Agent` PIDs.
*   **`Jido.AI.Keyring`**: For API key management.

This structure provides a solid foundation. The next steps would involve:
1.  Fully implementing the stdio communication in `McpJidoApp.MCP.Server`.
2.  Refining the tool schema conversion and handling within `McpJidoApp.Workflow.Agent` and `McpToolAction`.
3.  Potentially refactoring the `run_conversation_loop` to use a `Jido.Runner` for better state management and control flow if the interactions become more complex.
4.  Adding more robust error handling and recovery.
5.  Writing tests for each component.

This is a substantial starting point that directly leverages Jido's strengths for your Elixir-based AI agent system.
