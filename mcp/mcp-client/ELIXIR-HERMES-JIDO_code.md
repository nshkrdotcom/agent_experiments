Okay, this is a fascinating direction! Using Hermes MCP directly as the underlying transport and communication layer for your MCP client concepts (which Jido Actions will wrap) is a smart move. It should indeed simplify the Elixir port significantly in terms of raw network/process communication for the MCP part.

Here's how we'll approach the staged buildout, focusing on leveraging Hermes MCP and integrating Jido/Jido.AI on top.

**Stage 0: Project Setup & Dependencies (using Hermes)**

1.  **Create the new Elixir project:**
    ```bash
    mix new mcp_hermes_app --sup
    cd mcp_hermes_app
    ```

2.  **Add dependencies to `mix.exs`:**
    This is crucial. We'll add `hermes_mcp`, `jido`, and `jido_ai`.

    ```elixir
    # mix.exs
    defmodule McpكيrmesApp.MixProject do # Corrected typo here McpHermesApp
      use Mix.Project

      def project do
        [
          app: :mcp_hermes_app, # Corrected typo here
          version: "0.1.0",
          elixir: "~> 1.17", # Ensure compatibility with Hermes, Jido
          elixirc_paths: elixirc_paths(Mix.env()),
          start_permanent: Mix.env() == :prod,
          deps: deps(),
          aliases: aliases()
        ]
      end

      def application do
        [
          mod: {McpHermesApp.Application, []},
          extra_applications: [:logger, :runtime_tools, :hermes_mcp, :jido, :jido_ai]
        ]
      end

      defp elixirc_paths(:test), do: ["lib", "test/support"]
      defp elixirc_paths(_), do: ["lib"]

      defp deps do
        [
          # Hermes MCP for handling the MCP communication protocol
          {:hermes_mcp, "~> 0.4.0"}, # Or latest compatible version

          # Jido Core & AI for agent framework
          {:jido, "~> 1.1.0-rc.2"},
          {:jido_ai, "~> 0.5.2"},

          # JSON parsing (Jido likely brings Jason, but good to be explicit if needed)
          {:jason, "~> 1.4"},

          # For CLI argument parsing (if building a custom CLI beyond Jido's/Hermes' examples)
          # {:optimus, "~> 0.2.0"},

          # For development and testing
          {:credo, "~> 1.7", only: [:dev, :test], runtime: false},
          {:dialyxir, "~> 1.4", only: [:dev, :test], runtime: false}
        ]
      end

      defp aliases do
        [
          "run.cli": "run lib/mcp_hermes_app/cli.exs"
        ]
      end
    end
    ```

3.  **Fetch dependencies:**
    ```bash
    mix deps.get
    mix compile # Important to compile Hermes, Jido first
    ```

**Stage 1: Configuration, Core App, and Hermes Client Setup**

*   **`config/config.exs`** (Base Application Configuration)

    ```elixir
    # config/config.exs
    import Config

    config :logger,
      level: :info,
      format: "$time $metadata[$level] $message\n",
      metadata: [:module, :line]

    # Define where to find custom JSON configuration files
    # These will now primarily define Jido Workflows and which Hermes Clients to use.
    config :mcp_hermes_app,
      # No longer mcp_servers.json in the same way, Hermes manages connections.
      # We'll define "Hermes Clients" in app config which map to MCP server instances.
      workflows_path: Path.expand("config/workflows.json", __DIR__)

    # Configure Hermes MCP Clients (one per actual MCP server instance)
    # This replaces the Python AppConfig's mcp_servers loading for connection details.
    # The actual 'tools' provided by these servers will be queried via Hermes.
    config :mcp_hermes_app, :hermes_clients,
      # Example for a stdio server:
      generic_stdio_tool: [
        transport: :stdio, # :stdio, :sse, :websocket
        transport_opts: [
          command: "python3", # Make sure this is in PATH
          args: ["-u", "path/to/your/mcp_tool_script.py"] # Ensure script is executable and path is correct
          # env: %{"PYTHONUNBUFFERED" => "1"} # If needed
        ],
        client_info: %{
          "name" => "McpHermesApp.StdioClient.GenericTool",
          "version" => "0.1.0"
        }
        # capabilities: %{} # Client capabilities if needed
      ]
      # Add more client configurations here for other MCP servers
      # e.g., another_tool: [transport: :sse, transport_opts: [base_url: "..."], client_info: %{...}]

    # Jido.AI Keyring configuration
    config :jido_ai, Jido.AI.Keyring,
      # Environment variables will be loaded from .env by default by Jido.AI.Keyring itself.
      # You can provide direct fallbacks here if needed:
      # google_api_key: "your_fallback_google_api_key" # Not recommended for prod
      # Ensure GEMINI_API_KEY or GOOGLE_API_KEY is in .env or system env

    import_config "#{config_env()}.exs"
    ```

*   **`config/dev.exs`**

    ```elixir
    # config/dev.exs
    import Config

    config :logger, level: :debug

    # If you have a specific dev script for the generic_stdio_tool:
    # config :mcp_hermes_app, :hermes_clients,
    #   generic_stdio_tool: [
    #     transport: :stdio,
    #     transport_opts: [
    #       command: "python3",
    #       args: ["-u", "priv/dev/mcp_tool_script.py"] # Correct path for dev
    #     ],
    #     client_info: %{ "name" => "DevGenericTool", "version" => "dev"}
    #   ]
    ```

*   **Create `config/workflows.json`** (Adjusted for Hermes Client names)

    ```json
    // config/workflows.json
    {
      "workflows": {
        "simple_mcp_workflow_hermes": {
          "description": "A simple workflow that uses a Hermes-managed MCP tool and Gemini.",
          "llm_model_provider": "google",
          "llm_model_name": "gemini-1.5-flash-latest",
          "hermes_clients_used": ["generic_stdio_tool"], // Names from config :mcp_hermes_app, :hermes_clients
          "initial_prompt_template": "You are a helpful assistant. Based on the query: {query}, decide if you need to use any of your available tools. If so, provide the tool name and arguments. Available tools and their descriptions will be provided if you ask. Your primary tool for example tasks is 'do_example_task'.",
          "max_conversation_turns": 5
        }
      }
    }
    ```

*   **Create `.env` file in the project root (if not already there):**
    ```
    # .env
    GEMINI_API_KEY=your_actual_google_api_key_here
    # or GOOGLE_API_KEY=your_actual_google_api_key_here
    ```
    *Ensure `path/to/your/mcp_tool_script.py` (from Stage 0, Step 2 in the previous response) exists and is correctly pathed in `config/config.exs` or `config/dev.exs`.*

*   **`lib/mcp_hermes_app/application.ex`**

    ```elixir
    # lib/mcp_hermes_app/application.ex
    defmodule McpHermesApp.Application do
      use Application
      require Logger

      @impl true
      def start(_type, _args) do
        Logger.info("Starting McpHermesApp...")

        children = [
          Jido.AI.Keyring,          # For Jido.AI.Model API keys
          McpHermesApp.ConfigLoader, # Loads workflows.json
          McpHermesApp.HermesClientSupervisor, # Manages Hermes.Client instances
          McpHermesApp.Workflow.Supervisor # Manages Jido.AI.Agent (workflow) instances
        ]

        opts = [strategy: :one_for_one, name: McpHermesApp.MainSupervisor]
        result = Supervisor.start_link(children, opts)
        Logger.info("McpHermesApp started successfully.")
        result
      end
    end
    ```

*   **`lib/mcp_hermes_app/config_loader.ex`** (Simplified: only loads workflows)

    ```elixir
    # lib/mcp_hermes_app/config_loader.ex
    defmodule McpHermesApp.ConfigLoader do
      use GenServer
      require Logger

      def start_link(_opts) do
        GenServer.start_link(__MODULE__, :ok, name: __MODULE__)
      end

      @impl true
      def init(:ok) do
        Logger.info("ConfigLoader initializing...")
        workflows_path = Application.fetch_env!(:mcp_hermes_app, :workflows_path)

        with {:ok, workflows_raw} <- File.read(workflows_path),
             {:ok, workflows_data} <- Jason.decode(workflows_raw),
             workflows = Map.get(workflows_data, "workflows", %{})
        do
          Application.put_env(:mcp_hermes_app, :workflow_configs, workflows)
          Logger.info("Workflow configurations loaded.")
          {:ok, :no_state_needed}
        else
          {:error, reason} ->
            Logger.error("Failed to load workflow configurations: #{inspect(reason)}")
            {:stop, {:workflow_config_load_failed, reason}}
        end
      end
    end
    ```

**Stage 2: Hermes Client Management & Jido Action for Hermes MCP Tools**

*   **`lib/mcp_hermes_app/hermes_client_supervisor.ex`**

    ```elixir
    # lib/mcp_hermes_app/hermes_client_supervisor.ex
    defmodule McpHermesApp.HermesClientSupervisor do
      use Supervisor
      require Logger

      def start_link(_init_arg) do
        # Fetches client configs from app environment
        hermes_client_configs = Application.get_env(:mcp_hermes_app, :hermes_clients, %{})
        Supervisor.start_link(__MODULE__, hermes_client_configs, name: __MODULE__)
      end

      @impl true
      def init(hermes_client_configs) do
        Logger.info("HermesClientSupervisor initializing with #{map_size(hermes_client_configs)} clients.")

        children =
          Enum.map(hermes_client_configs, fn {client_id_atom, config_list} ->
            client_name = # Construct a unique name for the Hermes.Client GenServer
              case Keyword.get(config_list, :name) do
                nil -> {Hermes.Client, client_id_atom} # Register globally if no name
                name -> name
              end

            # Ensure config_list is a keyword list for Hermes.Client.start_link
            client_opts =
              config_list
              |> Keyword.put_new(:name, client_name) # Ensure name is in opts
              |> Keyword.put_new_lazy(:capabilities, fn -> %{} end) # Default client capabilities

            Logger.debug("Starting Hermes.Client '#{inspect(client_id_atom)}' with name: #{inspect(client_name)} and opts: #{inspect(client_opts)}")
            Supervisor.child_spec({Hermes.Client, client_opts}, id: client_id_atom)
          end)

        Supervisor.init(children, strategy: :one_for_one)
      end
    end
    ```
    *Note: The `client_id_atom` will be used to look up the `Hermes.Client` PID.*

*   **`lib/mcp_hermes_app/actions/hermes_mcp_tool_action.ex`**
    *(This Jido.Action now interacts with a `Hermes.Client` GenServer instead of a custom MCP.Server)*

    ```elixir
    # lib/mcp_hermes_app/actions/hermes_mcp_tool_action.ex
    defmodule McpHermesApp.Actions.HermesMcpToolAction do
      use Jido.Action
      require Logger

      alias Hermes.Client # Using the Hermes MCP library's client

      # This Action is generic. An Agent will configure specific instances of it
      # for each actual MCP tool, providing the correct name, description, and schema.
      # The `name` of this action instance will be the actual MCP tool name.

      @impl true
      def run(params, context) do
        # Context is expected to provide :hermes_client_id (atom) which is the key
        # from our :hermes_clients config and the ID of the Hermes.Client GenServer.
        # The `Jido.Action` name (accessible via __MODULE__.name()) is the MCP tool_name.
        hermes_client_id = Map.fetch!(context, :hermes_client_id) # e.g., :generic_stdio_tool
        mcp_tool_name = __MODULE__.name() # This is the actual tool name like "do_example_task"

        Logger.info(
          "[HermesMcpToolAction for #{mcp_tool_name} via Hermes Client #{hermes_client_id}] Running with params: #{inspect(params)}"
        )

        # Resolve the Hermes.Client GenServer PID.
        # Hermes.Client supervisor should register children by their `client_id_atom`.
        # We need a way to get this PID. Using `Process.whereis/1` assuming registration.
        hermes_client_pid = Process.whereis(Hermes.Client.via_tuple(hermes_client_id)) # Using Hermes helper for registered name

        if !is_pid(hermes_client_pid) do
          Logger.error("Hermes.Client PID for '#{hermes_client_id}' not found.")
          {:error, Jido.Error.config_error("Hermes Client not found: #{hermes_client_id}")}
        else
          # `params` are the validated inputs for the specific MCP tool (the Jido Action's schema)
          case Client.call_tool(hermes_client_pid, mcp_tool_name, params) do
            {:ok, %Hermes.MCP.Response{result: tool_result_map, is_error: false}} ->
              Logger.debug("[HermesMcpToolAction #{mcp_tool_name}] Result: #{inspect(tool_result_map)}")
              # Jido.Action expects {:ok, map_of_outputs}
              # Hermes tool_call returns %{"content" => ..., "isError" => false}
              # We need to extract the actual content/output.
              # Assuming the meaningful output is under a specific key like "output" or directly the result.
              # Let's assume Hermes returns a map, and we pass it on.
              # The LLM expects a map of {"output" => value} or just the value if it's a simple type.
              # For function calling, it needs to be a map compatible with the tool's JSON schema output.
              output_content = Map.get(tool_result_map, "content", tool_result_map)
              {:ok, %{"output" => output_content}} # Wrap in "output" for consistency

            {:ok, %Hermes.MCP.Response{result: error_result, is_error: true}} ->
              Logger.error("[HermesMcpToolAction #{mcp_tool_name}] MCP Domain Error: #{inspect(error_result)}")
              {:error, Jido.Error.execution_error("MCP tool returned domain error: #{inspect(error_result)}")}

            {:error, %Hermes.MCP.Error{} = hermes_error} ->
              Logger.error("[HermesMcpToolAction #{mcp_tool_name}] Hermes Client Error: #{inspect(hermes_error)}")
              {:error, Jido.Error.execution_error("Hermes Client MCP call failed: #{inspect(hermes_error.reason)}")}

            {:error, reason} -> # Other GenServer call errors
              Logger.error("[HermesMcpToolAction #{mcp_tool_name}] GenServer Error: #{inspect(reason)}")
               {:error, Jido.Error.execution_error("Error calling Hermes Client: #{inspect(reason)}")}
          end
        end
      end
    end
    ```

**Stage 3: Workflow Agent (using Hermes Actions)**

*   **`lib/mcp_hermes_app/workflow/agent.ex`**
    *(This is similar to Stage 3 in the previous response, but adapted to use `HermesMcpToolAction` and Hermes client IDs)*

    ```elixir
    # lib/mcp_hermes_app/workflow/agent.ex
    defmodule McpHermesApp.Workflow.Agent do
      use Jido.AI.Agent

      alias Jido.Instruction
      alias Jido.AI.Model
      alias Jido.AI.Prompt
      alias Jido.AI.Actions.OpenaiEx # Using OpenaiEx action for LLM
      alias McpHermesApp.Actions.HermesMcpToolAction

      require Logger

      # Agent state struct
      defstruct workflow_name: nil, # For identification/logging
                workflow_config: %{},
                llm_model_struct: nil,
                # Maps tool_name (string) to its Jido.Action configuration (name, schema, desc)
                # And also the hermes_client_id that provides it.
                available_mcp_actions: %{}
                # No current_conversation_history; Jido.AI.Prompt will be managed per interaction

      @impl Jido.Agent
      def init(opts) do
        workflow_name = Keyword.fetch!(opts, :workflow_name)
        all_workflow_configs = Application.get_env(:mcp_hermes_app, :workflow_configs, %{})
        workflow_config = Map.get(all_workflow_configs, workflow_name)

        unless workflow_config do
          Logger.error("Workflow '#{workflow_name}' not found.")
          # Return a state that will likely cause errors downstream, or handle more gracefully.
          {:ok, %__MODULE__{workflow_name: workflow_name}}
        else
          Logger.info("[Workflow.Agent #{workflow_name}] Initializing with config: #{inspect(workflow_config)}")

          llm_provider_str = workflow_config["llm_model_provider"]
          llm_model_name_str = workflow_config["llm_model_name"]
          llm_provider = if llm_provider_str, do: String.to_atom(llm_provider_str), else: :google # default

          case Model.from({llm_provider, [model: llm_model_name_str]}) do
            {:ok, llm_model_struct} ->
              Logger.info("LLM Model for #{workflow_name} prepared: #{inspect(llm_model_struct.model)}")

              # Dynamically build action configurations from Hermes client's tools
              # This requires Hermes clients to be up and running.
              # This part is tricky in init, as Hermes Clients might not be ready.
              # It's better to fetch tools on-demand or in a :continue callback.
              # For now, we'll assume this happens later or is simplified.

              # Let's define a helper for later tool discovery:
              initial_state = %__MODULE__{
                workflow_name: workflow_name,
                workflow_config: workflow_config,
                llm_model_struct: llm_model_struct,
                available_mcp_actions: %{} # To be populated
              }
              # Agent.Server will merge this into its internal :state key
              {:ok, initial_state}

            {:error, reason} ->
              Logger.error("LLM Model init failed for #{workflow_name}: #{inspect(reason)}")
              {:error, {:llm_model_init_failed, reason}}
          end
        end
      end

      @impl Jido.Agent
      def actions(_agent_struct) do
        # The Jido.AI.Agent behavior might automatically register some of Jido.AI.Actions.*
        # For explicit control or other actions:
        [
          HermesMcpToolAction, # The generic action for calling any MCP tool via Hermes
          OpenaiEx            # For our LLM interactions
        ]
      end


      # --- Public API for the agent (e.g., called via Jido.AI.Agent.chat_response) ---
      # Or handle specific signals like in the previous example.
      # Jido.AI.Agent often uses default signal handlers like "jido.ai.chat.response".

      @impl Jido.Agent
      def handle_signal(%Signal{type: "jido.ai.chat.response", data: %{message: user_query}}, agent_struct) do
        # agent_struct.state is our %McpHermesApp.Workflow.Agent{} struct
        workflow_agent_state = agent_struct.state
        workflow_name = workflow_agent_state.workflow_name
        workflow_config = workflow_agent_state.workflow_config
        Logger.info("[Workflow.Agent #{workflow_name}] Received user query via chat.response signal: #{user_query}")

        initial_prompt_text =
          String.replace(workflow_config["initial_prompt_template"], "{query}", user_query)

        initial_prompt =
          Prompt.new()
          |> Prompt.add_message(:user, initial_prompt_text)

        # We need to fetch available MCP tools for this workflow dynamically.
        # This should happen after Hermes Clients are initialized.
        # Let's assume this is done now, or that Workflow.Agent's state gets updated.
        # For this example, we will try to fetch them now.

        hermes_client_ids_used = workflow_config["hermes_clients_used"] # e.g., [:generic_stdio_tool]
                               |> Enum.map(&String.to_atom/1)

        # Dynamically get available tools and their schemas
        # This part is complex as Jido Actions are usually defined at compile time.
        # We are creating "instances" of a generic Jido Action dynamically.
        available_mcp_actions_config_now =
          Enum.reduce(hermes_client_ids_used, %{}, fn hermes_client_id, acc_actions ->
            hermes_client_pid = Process.whereis(Hermes.Client.via_tuple(hermes_client_id))
            if is_pid(hermes_client_pid) do
              case Hermes.Client.list_tools(hermes_client_pid) do
                {:ok, %Hermes.MCP.Response{result: %{"tools" => mcp_tools_list}}} ->
                  Enum.reduce(mcp_tools_list, acc_actions, fn mcp_tool_def, inner_acc ->
                    tool_name_str = mcp_tool_def["name"]
                    action_instance_config = %{
                      name: tool_name_str,
                      description: mcp_tool_def["description"],
                      schema: convert_json_schema_to_nimble(mcp_tool_def["inputSchema"]),
                      # Add context needed by HermesMcpToolAction
                      _hermes_client_id: hermes_client_id
                    }
                    Map.put(inner_acc, tool_name_str, action_instance_config)
                  end)
                {:error, reason} ->
                  Logger.error("Failed to list tools for Hermes client #{hermes_client_id}: #{inspect(reason)}")
                  acc_actions # Continue with what we have
                _ -> acc_actions
              end
            else
              Logger.warning("Hermes client #{hermes_client_id} not found for tool discovery.")
              acc_actions
            end
          end)

        if map_size(available_mcp_actions_config_now) == 0 && !Enum.empty?(hermes_client_ids_used) do
           Logger.warning("[Workflow.Agent #{workflow_name}] No MCP tools discovered from Hermes clients. LLM may not be able to use tools.")
        end

        conversation_result =
          run_conversation_loop(
            agent_struct.id, # Jido Agent's own ID
            workflow_agent_state.llm_model_struct,
            initial_prompt,
            available_mcp_actions_config_now, # Fetched dynamically
            max_turns = workflow_config["max_conversation_turns"]
          )

        final_response_data =
          case conversation_result do
            {:ok, text_response} -> %{response: text_response} # Jido.AI.Skill expects :response
            {:error, reason} -> %{error: inspect(reason)}
          end

        # Jido.AI.Agent will wrap this in a signal
        {:ok, final_response_data, []} # No further directives from this top-level handler
      end

      # Fallback for other signals if not handled by Jido.AI.Agent defaults
      @impl Jido.Agent
      def handle_signal(signal, _agent_struct) do
        Logger.info("Workflow.Agent unhandled signal: #{inspect(signal.type)}")
        {:error, :unhandled_signal}
      end


      # --- Conversation Loop (similar to previous, but uses HermesMcpToolAction) ---
      defp run_conversation_loop(
            agent_id,
            llm_model_struct,
            current_prompt_history,
            available_mcp_actions_config, # map of tool_name -> Jido action config with :_hermes_client_id
            max_turns,
            current_turn \\ 1
          ) do

        if current_turn > max_turns do
          Logger.warning("[#{agent_id}] Max turns reached.")
          final_text = current_prompt_history |> Prompt.to_text() |> String.split("\n") |> List.last() |> String.trim_leading("[assistant] ")
          {:ok, final_text <> "\n[Max interaction turns reached.]"}
        else
          Logger.info("[#{agent_id}] Conversation turn #{current_turn}/#{max_turns}")

          # Prepare tools for LLM (OpenAI format for Jido.AI.Actions.OpenaiEx)
          llm_tools_param =
            available_mcp_actions_config
            |> Enum.map(fn {_tool_name, action_config} ->
              %{
                "type" => "function",
                "function" => %{
                  "name" => action_config.name,
                  "description" => action_config.description,
                  "parameters" => convert_nimble_schema_to_openai_params(action_config.schema)
                }
              }
            end)

          llm_instruction_params = %{
            model: llm_model_struct,
            prompt: current_prompt_history,
            tools: llm_tools_param
          }

          # Execute LLM call via Jido.Exec and Jido.AI.Actions.OpenaiEx
          case Jido.Exec.run(OpenaiEx, llm_instruction_params) do
            {:ok, llm_exec_result_map} ->
              # OpenaiEx Action returns %{content: "text", tool_results: [%{name: ..., arguments: ...}]}
              llm_text_content = Map.get(llm_exec_result_map, :content)
              llm_tool_calls   = Map.get(llm_exec_result_map, :tool_results, []) # List of %{name: "...", arguments: %{...}}

              new_prompt_history =
                if llm_text_content && String.trim(llm_text_content) != "" do
                  Logger.info("[#{agent_id}] LLM Text: #{llm_text_content}")
                  Prompt.add_message(current_prompt_history, :assistant, llm_text_content)
                else
                  current_prompt_history
                end

              if llm_tool_calls && !Enum.empty?(llm_tool_calls) do
                # For simplicity, process one tool call from the LLM response
                tool_call = List.first(llm_tool_calls)
                tool_name_to_call = tool_call.name     # string
                tool_args_from_llm = tool_call.arguments # map with string keys

                Logger.info("[#{agent_id}] LLM wants to call tool: #{tool_name_to_call} with args: #{inspect(tool_args_from_llm)}")

                # Find the specific action config for this tool
                case Map.get(available_mcp_actions_config, tool_name_to_call) do
                  nil ->
                    Logger.error("[#{agent_id}] LLM requested unknown tool: #{tool_name_to_call}")
                    error_history = Prompt.add_message(new_prompt_history, :tool, %{tool_call_id: "error", name: tool_name_to_call, content: "[Tool not found]"})
                    run_conversation_loop(agent_id, llm_model_struct, error_history, available_mcp_actions_config, max_turns, current_turn + 1)

                  tool_action_instance_config ->
                    hermes_client_id_for_tool = tool_action_instance_config._hermes_client_id

                    # The HermesMcpToolAction needs :hermes_client_id and :mcp_tool_name in its context
                    # Its `name` and `schema` are set by the Jido.Agent when it uses `Jido.Instruction.new`
                    # Here, we are crafting the Jido.Instruction manually.
                    # The *params* for McpToolAction.run/2 are the tool_args_from_llm
                    # but they need to be keyed by atoms based on the tool's actual schema.
                    # `convert_json_schema_to_nimble` gave us NimbleOptions schema.
                    # `convert_params_using_schema` (from your `Jido.Action.Tool` example) is useful here.

                    atom_keyed_params = McpHermesApp.Actions.HermesMcpToolAction.Tool.convert_params_using_schema(tool_args_from_llm, tool_action_instance_config.schema)

                    mcp_instruction = %Instruction{
                      action: HermesMcpToolAction, # The generic Jido Action
                      params: atom_keyed_params,
                      context: %{
                        # Jido Action's `name` and `description` are defined by `tool_action_instance_config`
                        # These are usually set when a Jido.Agent plans an action from its list.
                        # Since we are manually constructing an Instruction, we need to pass it along.
                        # Jido.Action uses __MODULE__.name() which won't work here.
                        # The `context` is where we pass specifics for the *generic* HermesMcpToolAction.
                        action_metadata: Map.take(tool_action_instance_config, [:name, :description, :schema]), # Make sure McpToolAction uses this.
                        hermes_client_id: hermes_client_id_for_tool,
                        mcp_tool_name:    tool_action_instance_config.name # The *actual* MCP tool name
                      }
                    }

                    # Execute the MCP tool call via Jido.Exec
                    case Jido.Exec.run(mcp_instruction) do
                      {:ok, mcp_tool_result_map} -> # e.g., %{"output" => "..."}
                        tool_output_str = Jason.encode!(mcp_tool_result_map) # LLM expects JSON string typically for tool output content
                        Logger.info("[#{agent_id}] Tool '#{tool_name_to_call}' executed. Output for LLM: #{tool_output_str}")

                        # Add tool execution result to history. Jido.AI.Actions.OpenaiEx expects this to be in the 'tool' role.
                        history_after_tool =
                          Prompt.add_message(new_prompt_history, :tool, %{
                            # OpenAI format: tool_call_id, name, content (string)
                            # Jido.AI.Actions.OpenaiEx might need these structured in its :messages input.
                            # For now, assume tool_call_id is just the tool name for simplicity if not provided by LLM
                            tool_call_id: Map.get(tool_call, :id, tool_name_to_call),
                            name: tool_name_to_call,
                            content: tool_output_str
                          })

                        run_conversation_loop(agent_id, llm_model_struct, history_after_tool, available_mcp_actions_config, max_turns, current_turn + 1)

                      {:error, %Jido.Error{} = tool_err} ->
                        Logger.error("[#{agent_id}] Error executing tool '#{tool_name_to_call}': #{inspect(tool_err)}")
                        error_content = "[Error executing tool #{tool_name_to_call}: #{tool_err.message}]"
                        history_after_error = Prompt.add_message(new_prompt_history, :tool, %{tool_call_id: "error", name: tool_name_to_call, content: error_content})
                        run_conversation_loop(agent_id, llm_model_struct, history_after_error, available_mcp_actions_config, max_turns, current_turn + 1)
                    end
                end
              else
                # No tool call, LLM provided a text response. This is the final answer.
                final_text =
                  if llm_text_content && String.trim(llm_text_content) != "" do
                    llm_text_content
                  else
                    "[AI model provided no text and no further actions.]"
                  end
                {:ok, final_text}
              end

            {:error, llm_err} ->
              Logger.error("[#{agent_id}] Error calling LLM: #{inspect(llm_err)}")
              {:error, llm_err}
          end
        end
      end


      # Helper to convert JSON schema from config to NimbleOptions format
      defp convert_json_schema_to_nimble(json_schema) when is_map(json_schema) do
        properties = Map.get(json_schema, "properties", %{})
        required_keys_str = Map.get(json_schema, "required", [])

        Enum.map(properties, fn {name_str, prop_schema} ->
          type_str = Map.get(prop_schema, "type", "string")

          nimble_type =
            case type_str do
              "string" -> :string
              "integer" -> :integer
              "number" -> :float # Or handle integer/float distinction more granularly
              "boolean" -> :boolean
              "array" -> {:list, :any} # Basic list type, could be more specific
              "object" -> :map       # Basic map type
              _ -> :string # Default
            end

          required = name_str in required_keys_str
          description = Map.get(prop_schema, "description")

          config = [type: nimble_type]
          config = if required, do: Keyword.put(config, :required, true), else: config
          config = if description, do: Keyword.put(config, :doc, description), else: config
          {String.to_atom(name_str), config}
        end)
      end
      defp convert_json_schema_to_nimble(_other), do: [] # Return empty if not a map

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
                {:list, _inner_type} -> "array" # Simplified, OpenAI might want items schema
                :map -> "object" # Simplified
                _ -> "string" # Default for unknown or complex types
              end
            prop_schema = %{"type" => json_type}
            prop_schema =
              if desc = Keyword.get(opts, :doc),
                do: Map.put(prop_schema, "description", desc),
                else: prop_schema

            # Handle enums for OpenAI tools
            if enums = Keyword.get(opts, :values) when is_list(enums) do
              Map.put(prop_schema, "enum", enums)
            # Handle NimbleOption :in for enums
            else if {:in, enums_in} = Keyword.get(opts, :type) when is_list(enums_in) do
                Map.put(prop_schema, "enum", enums_in)
              else
                prop_schema
              end
            end
            |> (&(Map.put(acc, name_str, &1))).() # Apply the enum logic result to acc

          end)

        required_fields_str =
          nimble_schema
          |> Enum.filter(fn {_name, opts} -> Keyword.get(opts, :required, false) end)
          |> Enum.map(fn {name, _opts} -> Atom.to_string(name) end)

        schema = %{
          "type" => "object",
          "properties" => properties
        }
        if !Enum.empty?(required_fields_str), do: Map.put(schema, "required", required_fields_str), else: schema
      end
      defp convert_nimble_schema_to_openai_params(_), do: %{"type" => "object", "properties" => %{}}
    end
    ```
    *The `McpHermesApp.Actions.HermesMcpToolAction.Tool.convert_params_using_schema` is a copy from your `jido/lib/jido/workflow/tool.ex` for convenience. You'd centralize this.*

*   **`lib/mcp_hermes_app/workflow/supervisor.ex`**

    ```elixir
    # lib/mcp_hermes_app/workflow/supervisor.ex
    defmodule McpHermesApp.Workflow.Supervisor do
      use Supervisor
      require Logger

      def start_link(_init_arg) do
        workflow_configs = Application.get_env(:mcp_hermes_app, :workflow_configs, %{})
        Supervisor.start_link(__MODULE__, workflow_configs, name: __MODULE__)
      end

      @impl true
      def init(workflow_configs_map) do
        Logger.info("Workflow.Supervisor initializing with #{map_size(workflow_configs_map)} workflows.")
        children =
          Enum.map(workflow_configs_map, fn {workflow_name_str, _config_data} ->
            # Workflow agents are named for lookup. Ensure unique names for Jido.Agent.Server.
            agent_name_for_registry = String.to_atom("workflow_agent_#{workflow_name_str}")

            # Jido.AI.Agent.start_link takes a keyword list of opts
            # These opts are passed to the init/1 callback of our McpHermesApp.Workflow.Agent
            {McpHermesApp.Workflow.Agent, # The Module of the Jido.AI.Agent implementation
             [
               # Jido.Agent.Server opts:
               name: {:via, Registry, {McpHermesApp.Workflow.Registry, agent_name_for_registry}},
               # Opts for McpHermesApp.Workflow.Agent.init/1:
               workflow_name: workflow_name_str
               # other_opts_for_workflow_agent_init: ...
             ]}
          end) ++ [{Registry, keys: :unique, name: McpHermesApp.Workflow.Registry}]

        Supervisor.init(children, strategy: :one_for_one)
      end
    end
    ```

**Stage 4: Basic CLI (similar to previous, just needs to ensure the target Agent name matches)**

*   **`lib/mcp_hermes_app/cli.exs`**

    ```elixir
    # lib/mcp_hermes_app/cli.exs
    defmodule McpHermesApp.CLI do
      require Logger

      alias McpHermesApp.Workflow.Agent # Our Jido.AI.Agent implementation

      def main(args) do
        Application.ensure_all_started(:mcp_hermes_app)
        Application.ensure_all_started(:jido)
        Application.ensure_all_started(:jido_ai)

        # Using Optimus for more robust parsing
        parse_result = Optimus.new!(
          name: "mcp_cli",
          description: "Interact with MCP Workflows via Jido and Hermes.",
          version: Mix.Project.config()[:version],
          allow_unknown_args: true, # To capture the query as trailing args
          specs: [
            list_workflows: [
              value_name: "list-workflows",
              type: :boolean,
              short: :l,
              help: "List available workflows and exit."
            ],
            workflow: [
              value_name: "WORKFLOW_NAME",
              type: :string,
              help: "Name of the workflow to run.",
              required: false # Not required if --list-workflows is used
            ]
          ]
        ) |> Optimus.parse(args)

        case parse_result do
          {:ok, opts, [query | rest_query]} -> # Single query mode
            workflow_name = opts[:workflow]
            full_query = Enum.join([query | rest_query], " ")
            if workflow_name && full_query != "" do
              run_single_query(workflow_name, full_query)
            else
              print_usage()
            end

          {:ok, %{list_workflows: true}, _} -> list_workflows()

          {:ok, %{workflow: workflow_name}, []} when not is_nil(workflow_name) -> # Interactive mode
            run_chat_loop(workflow_name)

          _ -> print_usage()
        end
      end

      defp print_usage do
        IO.puts("""
        McpHermesApp CLI (Jido & Hermes Version)

        Usage:
          mix run.cli --list-workflows
          mix run.cli <WORKFLOW_NAME>                     (starts interactive chat)
          mix run.cli <WORKFLOW_NAME> <your query here>   (runs a single query)
        """)
        Optimus.print_help(Optimus.new!(specs: [list_workflows: :boolean, workflow: :string]))
      end

      defp list_workflows do
        workflows = Application.get_env(:mcp_hermes_app, :workflow_configs, %{})
        IO.puts("\nAvailable workflows:")
        if Map.is_empty(workflows) do
          IO.puts("  No workflows defined in config/workflows.json")
        else
          Enum.each(workflows, fn {name, config} ->
            IO.puts("  - #{name}: #{config["description"] || "No description"}")
          end)
        end
      end

      defp run_single_query(workflow_name_str, query_str) do
        IO.puts("Processing query for workflow '#{workflow_name_str}': \"#{query_str}\"")
        agent_registry_name = String.to_atom("workflow_agent_#{workflow_name_str}")

        case Jido.Util.whereis({agent_registry_name, McpHermesApp.Workflow.Registry}) do
         {:ok, agent_pid} ->
            # Jido.AI.Agent provides chat_response which sends a "jido.ai.chat.response" signal
            case Jido.AI.Agent.chat_response(agent_pid, query_str) do
              {:ok, %Jido.Signal{data: %{response: response_text}}} -> IO.puts("\nResponse:\n#{response_text}")
              {:ok, %Jido.Signal{data: %{error: error_reason}}}    -> IO.puts("\nWorkflow Error: #{error_reason}")
              {:error, reason} -> IO.puts("\nError calling workflow agent: #{inspect(reason)}")
              other -> IO.puts("\nUnexpected response: #{inspect(other)}")
            end
         {:error, :not_found} ->
            IO.puts("Error: Workflow Agent '#{workflow_name_str}' (as #{agent_registry_name}) not found.")
        end
      end

      defp run_chat_loop(workflow_name_str) do
        agent_registry_name = String.to_atom("workflow_agent_#{workflow_name_str}")
        case Jido.Util.whereis({agent_registry_name, McpHermesApp.Workflow.Registry}) do
         {:ok, agent_pid} ->
            IO.puts("\nChatting with workflow: '#{workflow_name_str}'. Type 'quit' to exit.")
            Stream.repeatedly(fn -> IO.gets("> ") |> String.trim() end)
            |> Enum.reduce_while(:ok, fn
              "quit", _ -> {:halt, :ok}
              "", _ -> {:cont, :ok}
              query_str, _ ->
                case Jido.AI.Agent.chat_response(agent_pid, query_str) do
                  {:ok, %Jido.Signal{data: %{response: response_text}}} -> IO.puts(response_text)
                  {:ok, %Jido.Signal{data: %{error: error_reason}}} -> IO.puts("Error: #{error_reason}")
                  {:error, reason} -> IO.puts("Error: #{inspect(reason)}")
                  other -> IO.puts("Unexpected: #{inspect(other)}")
                end
                {:cont, :ok}
            end)
            IO.puts("Exiting chat.")
          _ ->
            IO.puts("Error: Workflow Agent '#{workflow_name_str}' (as #{agent_registry_name}) not found.")
        end
      end
    end

    if System.get_env("__MIX_ENV__") != "test" and System.get_env("MIX_TASK") == "run.cli" do
      McpHermesApp.CLI.main(System.argv())
    end
    ```

**Running:**

1.  **Ensure `mcp_tool_script.py` exists and is configured.**
    (Copied from previous answer, `priv/dev/mcp_tool_script.py` is a good place, adjust `config/dev.exs`).
2.  **Set `GEMINI_API_KEY`** in `.env`.
3.  Compile: `mix compile`
4.  Run CLI:
    *   `mix run.cli --list-workflows`
    *   `mix run.cli simple_mcp_workflow_hermes "Can you run the example task with param1=hello and param2=100"`
    *   `mix run.cli simple_mcp_workflow_hermes` (for interactive chat)

**Key changes and benefits with Hermes MCP:**

*   **No Manual Port Management:** `Hermes.Client` (using `Hermes.Transport.STDIO` or others) handles the low-level process management and JSON-RPC communication with the MCP server. This removes the need for `McpJidoApp.MCP.Server` and its associated complexity.
*   **Simplified MCP Interaction:** The `HermesMcpToolAction` now calls `Hermes.Client.call_tool/3`, which is a higher-level abstraction provided by the Hermes library.
*   **Configuration Shift:** Instead of defining command/args for MCP servers in `mcp_servers.json` and loading that into a custom config struct, you now configure `Hermes.Client` instances directly in your Elixir `config/*.exs` files (under `:mcp_hermes_app, :hermes_clients`).
*   **Tool Discovery:** The `Workflow.Agent` dynamically discovers tools by calling `Hermes.Client.list_tools/1` on the configured Hermes client instances for that workflow. This makes it more adaptable.

This approach leverages Hermes MCP for the protocol-level details and Jido/Jido.AI for the agentic framework, resulting in a cleaner separation of concerns and less custom code for MCP communication. The `McpToolAction` acts as a bridge, making Hermes-managed tools available to the Jido agent.
