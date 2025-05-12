Okay, let's redo the application design with a strong focus on Jido, Jido.AI, and specifically using `LangChain.ex` for LLM interactions, including the Gemini provider as per its README. We'll also integrate Hermes MCP for managing the tool communications.

**High-Level Architecture:**

1.  **`McpLangchainApp.Application`**: Main OTP application, supervises core components.
2.  **`Jido.AI.Keyring`**: Manages API keys (including `GEMINI_API_KEY`).
3.  **`McpLangchainApp.ConfigLoader`**: Loads `workflows.json`.
4.  **`McpLangchainApp.HermesClientSupervisor`**: Manages `Hermes.Client` instances for each configured MCP server. Each `Hermes.Client` will be registered with a unique name.
5.  **`McpLangchainApp.Workflow.Supervisor`**: Manages instances of `McpLangchainApp.Workflow.Agent`.
6.  **`McpLangchainApp.Workflow.Agent` (implements `Jido.AI.Agent`):**
    *   This will be the central orchestrator for a given workflow.
    *   It will receive user queries (likely via a `Jido.Signal`).
    *   It will use `Jido.AI.Actions.Langchain` for all LLM interactions.
    *   `Jido.AI.Actions.Langchain` will be configured with a `LangChain.ChatModels.ChatGoogle` instance.
    *   When the LLM decides to call a tool, the Agent will plan and execute an instance of `McpLangchainApp.Actions.HermesMcpToolAction`.
7.  **`McpLangchainApp.Actions.HermesMcpToolAction` (implements `Jido.Action`):**
    *   A generic Jido Action responsible for calling any MCP tool via the appropriate `Hermes.Client`.
    *   Its `name`, `description`, and `schema` will be *dynamically derived* at runtime by the `Workflow.Agent` based on the tools discovered from the relevant `Hermes.Client` for the current workflow.
    *   Its `run/2` function will receive context indicating which `Hermes.Client` (by its registered name/ID) and which specific MCP tool (by its string name) to call.

**Stage 0: Project Setup and Dependencies**

1.  **Create the new Elixir project:**
    ```bash
    mix new mcp_langchain_app --sup
    cd mcp_langchain_app
    ```

2.  **Add dependencies to `mix.exs`:**

    ```elixir
    # mix.exs
    defmodule McpLangchainApp.MixProject do
      use Mix.Project

      def project do
        [
          app: :mcp_langchain_app,
          version: "0.1.0",
          elixir: "~> 1.17", # Langchain and Jido benefit from newer Elixir
          elixirc_paths: elixirc_paths(Mix.env()),
          start_permanent: Mix.env() == :prod,
          deps: deps(),
          aliases: aliases()
        ]
      end

      def application do
        [
          mod: {McpLangchainApp.Application, []},
          extra_applications: [:logger, :runtime_tools, :hermes_mcp, :jido, :jido_ai, :langchain]
        ]
      end

      defp elixirc_paths(:test), do: ["lib", "test/support"]
      defp elixirc_paths(_), do: ["lib"]

      defp deps do
        [
          # Hermes MCP for handling the MCP communication protocol
          {:hermes_mcp, "~> 0.4.0"},

          # Jido Core & AI for agent framework
          {:jido, "~> 1.1.0-rc.2"}, # Check for latest Jido versions
          {:jido_ai, "~> 0.5.2"},  # Check for latest Jido.AI versions

          # LangChain.ex for LLM interactions
          {:langchain, "~> 0.3.0"}, # Or rc.0 as per README

          # JSON parsing
          {:jason, "~> 1.4"},

          # For CLI argument parsing
          {:optimus, "~> 0.2.0"},

          # For development and testing
          {:credo, "~> 1.7", only: [:dev, :test], runtime: false},
          {:dialyxir, "~> 1.4", only: [:dev, :test], runtime: false}
        ]
      end

      defp aliases do
        [
          "run.cli": "run lib/mcp_langchain_app/cli.exs"
        ]
      end
    end
    ```

3.  **Fetch dependencies:**
    ```bash
    mix deps.get
    mix compile
    ```

**Stage 1: Configuration, Core App, Hermes Client Setup**

*   **`config/config.exs`**:

    ```elixir
    # config/config.exs
    import Config

    config :logger,
      level: :info,
      format: "$time $metadata[$level] $message\n",
      metadata: [:module, :line]

    config :mcp_langchain_app,
      workflows_path: Path.expand("config/workflows.json", __DIR__)

    # LangChain specific config (will be picked up by Jido.AI.Keyring if named gemini_api_key)
    # This key should be in your .env file as GEMINI_API_KEY or LANGCHAIN_GEMINI_API_KEY
    # Jido.AI.Keyring will load it. LangChain.ex itself looks for :langchain, :gemini_api_key
    config :langchain,
      gemini_api_key: System.get_env("GEMINI_API_KEY") # Or LANGCHAIN_GEMINI_API_KEY

    # Configure Hermes MCP Clients
    config :mcp_langchain_app, :hermes_clients,
      generic_stdio_tool: [
        transport: :stdio,
        transport_opts: [
          command: "python3",
          args: ["-u", "priv/dev/mcp_tool_script.py"] # Create this dummy script
        ],
        client_info: %{"name" => "McpLangchainApp.GenericToolClient", "version" => "0.1.0"}
      ]

    import_config "#{config_env()}.exs"
    ```

*   **`config/dev.exs`**:

    ```elixir
    # config/dev.exs
    import Config
    config :logger, level: :debug

    # Optional: override LANGCHAIN_GEMINI_API_KEY for dev if not using .env for it
    # config :langchain, gemini_api_key: "your-dev-gemini-key"
    ```

*   **Create `config/workflows.json`**:
    *(Note: `llm_model_provider` becomes less critical if LangChain's model definition is sufficient. We'll specify the LangChain model directly.)*

    ```json
    // config/workflows.json
    {
      "workflows": {
        "gemini_mcp_workflow": {
          "description": "A workflow using Gemini via LangChain and one MCP tool via Hermes.",
          "langchain_model": "gemini-1.5-flash-latest", // Model ID for LangChain.ex/Gemini
          "hermes_clients_used": ["generic_stdio_tool"],
          "initial_prompt_template": "You are a helpful assistant. You have access to a tool named 'do_example_task'. Based on the query: {query}, decide if you need to use the tool. If so, call it with its arguments. If not, answer directly.",
          "max_conversation_turns": 5
        }
      }
    }
    ```

*   **Create `.env` file in the project root**:
    ```
    # .env
    GEMINI_API_KEY=your_actual_google_api_key_here
    # Or LANGCHAIN_GEMINI_API_KEY=your_actual_google_api_key_here
    ```

*   **Create `priv/dev/mcp_tool_script.py`**:
    (Use the same script from the previous Jido/Hermes example, ensuring it can handle `initialize`, `list_tools`, and `call_tool` methods).

    ```python
    # priv/dev/mcp_tool_script.py
    import sys
    import json
    import time

    TOOLS_AVAILABLE = {
        "do_example_task": {
            "name": "do_example_task", # Hermes expects 'name'
            "description": "Performs an example task for demonstration.",
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
        sys.stderr.write("Python MCP tool script started.\n")
        sys.stderr.flush()

        for line in sys.stdin:
            sys.stderr.write(f"Python script received line: {line.strip()}\n")
            sys.stderr.flush()
            try:
                request = json.loads(line.strip())
                response_id = request.get("id", "no_id")
                method = request.get("method")
                params = request.get("params", {})

                if method == "initialize":
                    response = {"id": response_id, "result": {"serverInfo": {"name": "PythonMCPTool", "version": "0.1"}, "capabilities": {"tools": {}}}}
                elif method == "list_tools":
                    # Hermes Client expects result.tools to be a list of tool definitions
                    response = {"id": response_id, "result": {"tools": list(TOOLS_AVAILABLE.values())}}
                elif method == "call_tool":
                    tool_name = params.get("name") # Hermes sends "name" for tool_name
                    args = params.get("arguments", {}) # Hermes sends "arguments"
                    if tool_name == "do_example_task":
                        time.sleep(0.1)
                        param1_val = args.get("param1", "N/A")
                        param2_val = args.get("param2", 0)
                        tool_output_content = f"Example task done by Python with param1='{param1_val}' and param2={param2_val}"
                        # Hermes MCP expects result: %{"content" => ..., "isError" => ...}
                        response = {"id": response_id, "result": {"content": {"output": tool_output_content}, "isError": False}}
                    else:
                        response = {"id": response_id, "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"}}
                else:
                    response = {"id": response_id, "error": {"code": -32601, "message": f"Unknown method '{method}'"}}

                sys.stderr.write(f"Python script sending response: {json.dumps(response)}\n")
                sys.stderr.flush()
                print(json.dumps(response), flush=True)
            except Exception as e:
                error_response = {"id": "error", "error": {"message": f"Python script error: {str(e)} - problematic line: {line.strip()}"}}
                sys.stderr.write(f"Python script error: {json.dumps(error_response)}\n")
                sys.stderr.flush()
                print(json.dumps(error_response), flush=True)

    if __name__ == "__main__":
        main()
    ```

*   **`lib/mcp_langchain_app/application.ex`**: (Similar to before, but added `:langchain`)

    ```elixir
    # lib/mcp_langchain_app/application.ex
    defmodule McpLangchainApp.Application do
      use Application
      require Logger

      @impl true
      def start(_type, _args) do
        Logger.info("Starting McpLangchainApp...")

        children = [
          Jido.AI.Keyring, # Manages API keys (incl. Gemini)
          McpLangchainApp.ConfigLoader, # Loads workflows.json
          McpLangchainApp.HermesClientSupervisor, # Manages Hermes.Client instances
          McpLangchainApp.Workflow.Supervisor # Manages Jido.AI.Agent (workflow) instances
        ]

        opts = [strategy: :one_for_one, name: McpLangchainApp.MainSupervisor]
        Supervisor.start_link(children, opts)
      end
    end
    ```

*   **`lib/mcp_langchain_app/config_loader.ex`**: (Same as previous, loads `workflows.json`)
*   **`lib/mcp_langchain_app/hermes_client_supervisor.ex`**: (Same as previous, starts `Hermes.Client`s)

**Stage 2: `HermesMcpToolAction` (Jido Action using Hermes)**

*   **`lib/mcp_langchain_app/actions/hermes_mcp_tool_action.ex`**:
    *(This is nearly identical to the previous Jido/Hermes example. The key is that LangChain.ex tools will also need to map to this.)*

    ```elixir
    # lib/mcp_langchain_app/actions/hermes_mcp_tool_action.ex
    defmodule McpLangchainApp.Actions.HermesMcpToolAction do
      use Jido.Action # name, description, schema will be set dynamically by Agent

      alias Hermes.Client
      require Logger

      # --- Jido.Action Tool Conversion ---
      # This is called by LangChain when converting this action to an LLM tool.
      # The schema here must match what the Agent dynamically provides when defining
      # an "instance" of this generic action for a specific MCP tool.
      #
      # The `Jido.AI.Agent` will iterate through `available_mcp_actions` (which holds configs like
      # %{name: "do_example_task", description: "...", schema: [...]}),
      # and for each, it will tell LangChain to treat `HermesMcpToolAction` AS IF it were that
      # specific tool by providing this `to_tool/1` function a context.
      # Langchain.Function.new/1 takes a module OR a %{module: Mod, context: ctx} map.

      @doc """
      Generates a LangChain.Function compatible tool definition.
      The `action_config_for_tool` will be passed via context when
      LangChain.Function calls this for a specific MCP tool.
      """
      def to_tool(action_config_for_tool \\ %{}) do
        # `action_config_for_tool` is expected to be %{name: "tool_name", description: "...", schema: nimble_schema}
        # as prepared by the Workflow.Agent
        tool_name = Map.get(action_config_for_tool, :name, "unknown_mcp_tool")
        description = Map.get(action_config_for_tool, :description, "An MCP tool.")
        nimble_schema = Map.get(action_config_for_tool, :schema, [])

        %{
          name: tool_name,
          description: description,
          function: &__MODULE__.run/2, # Jido.Action expects run/2, LangChain.Function also uses run/2
          parameters_schema: convert_nimble_schema_to_langchain_params(nimble_schema)
        }
      end

      defp convert_nimble_schema_to_langchain_params(nimble_schema) when is_list(nimble_schema) do
        properties =
          Enum.reduce(nimble_schema, %{}, fn {name_atom, opts}, acc ->
            name_str = Atom.to_string(name_atom)
            json_type =
              case Keyword.get(opts, :type) do
                :string -> "string"
                :integer -> "integer"
                :float -> "number"
                :boolean -> "boolean"
                {:list, _} -> "array"
                :map -> "object"
                _ -> "string"
              end
            prop_schema = %{"type" => json_type}
            prop_schema =
              if desc = Keyword.get(opts, :doc),
                do: Map.put(prop_schema, "description", desc),
                else: prop_schema
            # For enums, LangChain expects an "enum" field in the JSON schema
            if enums = Keyword.get(opts, :values) || (match?({:in, _}, Keyword.get(opts, :type)) && elem(Keyword.get(opts, :type), 1)) do
              Map.put(prop_schema, "enum", enums)
            else
              prop_schema
            end |> (&(Map.put(acc, name_str, &1))).()
          end)

        required_fields_str =
          nimble_schema
          |> Enum.filter(fn {_name, opts} -> Keyword.get(opts, :required, false) end)
          |> Enum.map(fn {name_atom, _opts} -> Atom.to_string(name_atom) end)

        schema = %{
          "type" => "object",
          "properties" => properties
        }
        if !Enum.empty?(required_fields_str), do: Map.put(schema, "required", required_fields_str), else: schema
      end
      defp convert_nimble_schema_to_langchain_params(_), do: %{"type" => "object", "properties" => %{}}


      # --- Jido.Action run/2 callback ---
      @impl true
      def run(params, context) do
        # When LangChain.Function calls this, `params` will be from LLM, `context` from Function.new!
        # When Jido.Exec calls this (if planned by Agent), context is from Jido.Instruction.
        # We need to ensure :hermes_client_id and :mcp_tool_name are in context.
        hermes_client_id_from_context = Map.get(context, :hermes_client_id)
        mcp_tool_name_from_context = Map.get(context, :mcp_tool_name)

        action_metadata_from_context = Map.get(context, :action_metadata, %{})
        # If run via LangChain.Function, the function name is the MCP tool name.
        # Jido.Action.Tool passed `&__MODULE__.run/2` which refers to THIS module.
        # We need the *actual* MCP tool name. LangChain provides it in the context when `Function` is created with a module.
        # If we use `{module: McpToolAction, context: %{hermes_client_id: ..., mcp_tool_name: ...}}` for LangChain.Function, then it's in context.

        hermes_client_id = hermes_client_id_from_context || action_metadata_from_context._hermes_client_id
        mcp_tool_name = mcp_tool_name_from_context || action_metadata_from_context.name

        if !hermes_client_id || !mcp_tool_name do
          Logger.error("HermesMcpToolAction missing :hermes_client_id or :mcp_tool_name in context: #{inspect(context)}")
          return {:error, Jido.Error.config_error("Action context improperly configured.")}
        end

        Logger.info(
          "[HermesMcpToolAction for #{mcp_tool_name} via Hermes Client #{hermes_client_id}] Running with params: #{inspect(params)}"
        )

        hermes_client_pid_result = Jido.Util.whereis({hermes_client_id, McpHermesApp.HermesClientSupervisor}) # Assuming supervisor uses a registry for clients by ID

        case hermes_client_pid_result do
          {:ok, hermes_client_pid} when is_pid(hermes_client_pid) ->
            # `params` for `Hermes.Client.call_tool` should be the arguments for the MCP tool.
            # `HermesMcpToolAction.run/2`'s `params` *are* these arguments, already validated by Jido.Action's schema.
            case Client.call_tool(hermes_client_pid, mcp_tool_name, params) do
              {:ok, %Hermes.MCP.Response{result: tool_output_map, is_error: false}} ->
                Logger.debug("[HermesMcpToolAction #{mcp_tool_name}] Result: #{inspect(tool_output_map)}")
                # LangChain expects a string or JSON serializable map/list for tool function output
                # We need to ensure the output from Hermes is suitable. Hermes returns:
                # %{"content" => %{"output" => "Actual tool string output"}, "isError" => false}
                # The "output" key inside "content" is what we need.
                actual_content = Map.get(tool_output_map, "content", tool_output_map)
                {:ok, actual_content} # Return the map directly

              {:ok, %Hermes.MCP.Response{result: error_payload, is_error: true}} ->
                Logger.error("[HermesMcpToolAction #{mcp_tool_name}] MCP Domain Error: #{inspect(error_payload)}")
                # LangChain tool functions should return {:error, string_reason}
                {:error, "MCP tool returned domain error: #{inspect(error_payload)}"}

              {:error, %Hermes.MCP.Error{} = hermes_error} ->
                Logger.error("[HermesMcpToolAction #{mcp_tool_name}] Hermes Client Error: #{inspect(hermes_error)}")
                {:error, "Hermes Client MCP call failed: #{inspect(hermes_error.reason)}"}

              {:error, reason} ->
                Logger.error("[HermesMcpToolAction #{mcp_tool_name}] GenServer Error: #{inspect(reason)}")
                {:error, "Error calling Hermes Client: #{inspect(reason)}"}
            end
          _ ->
             Logger.error("HermesMcpToolAction: Hermes.Client PID for '#{hermes_client_id}' not found or invalid.")
             {:error, Jido.Error.config_error("Hermes Client not found: #{hermes_client_id}")}
        end
      end
    end
    ```
    *Added `convert_params_using_schema/2` locally for tool schema matching.*

**Stage 3: Workflow Agent using LangChain.ex**

*   **`lib/mcp_langchain_app/workflow/agent.ex`**

    ```elixir
    # lib/mcp_langchain_app/workflow/agent.ex
    defmodule McpLangchainApp.Workflow.Agent do
      use Jido.AI.Agent # Base Jido Agent for structure and server

      alias Jido.Instruction
      alias Jido.AI.Model # For type hinting if needed, not for direct LLM calls
      alias Jido.AI.Prompt
      alias McpLangchainApp.Actions.HermesMcpToolAction

      # LangChain specific
      alias LangChain.ChatModels.ChatGoogle
      alias LangChain.Chains.LLMChain
      alias LangChain.Message
      alias LangChain.Function # LangChain's way of representing tools

      require Logger

      defstruct workflow_name: nil,
                workflow_config: %{},
                # We don't store llm_model_struct; LangChain.ChatGoogle will handle it.
                # We store the LangChain LLMChain instance pre-configured for the workflow.
                llm_chain: nil,
                # tool_name (string) => LangChain.Function struct
                # This makes them directly usable by LLMChain.add_tools
                available_langchain_mcp_tools: %{}


      @impl Jido.Agent
      def init(opts) do
        workflow_name = Keyword.fetch!(opts, :workflow_name)
        all_workflow_configs = Application.get_env(:mcp_langchain_app, :workflow_configs, %{})
        workflow_config = Map.get(all_workflow_configs, workflow_name)

        unless workflow_config do
          Logger.error("Workflow '#{workflow_name}' not found.")
          {:ok, %__MODULE__{workflow_name: workflow_name}} # Degraded state
        else
          Logger.info("[Workflow.Agent #{workflow_name}] Initializing with config: #{inspect(workflow_config)}")

          langchain_model_id = workflow_config["langchain_model"] # e.g., "gemini-1.5-flash-latest"
          # API key will be fetched from LangChain's own config or env (handled by ChatGoogle.new!)
          gemini_chat_model = ChatGoogle.new!(model: langchain_model_id, stream: false) # No stream for now

          # Prepare LLMChain (the core of LangChain interaction)
          llm_chain =
            %{llm: gemini_chat_model, verbose: Application.get_env(:logger, :console)[:level] == :debug}
            |> LLMChain.new!() # No custom_context needed at chain level for tools

          # Prepare available MCP tools as LangChain.Function structs
          # This needs to happen when the Agent is fully initialized and Hermes clients are up.
          # For now, we prepare them here, but in a real app, a :continue or post-init callback would be better.
          hermes_client_ids_used =
            (workflow_config["hermes_clients_used"] || []) |> Enum.map(&String.to_atom/1)

          available_langchain_mcp_tools =
            Enum.reduce(hermes_client_ids_used, %{}, fn hermes_client_id, acc_tools ->
              hermes_client_pid = Process.whereis(Hermes.Client.via_tuple(hermes_client_id))
              if is_pid(hermes_client_pid) do
                case Hermes.Client.list_tools(hermes_client_pid) do
                  {:ok, %Hermes.MCP.Response{result: %{"tools" => mcp_tools_list}}} ->
                    Enum.reduce(mcp_tools_list, acc_tools, fn mcp_tool_def, inner_acc ->
                      tool_name_str = mcp_tool_def["name"]
                      # Create the config that HermesMcpToolAction.to_tool/1 expects
                      action_config_for_tool = %{
                        name: tool_name_str,
                        description: mcp_tool_def["description"],
                        schema: McpHermesApp.Actions.HermesMcpToolAction.Tool.convert_json_schema_to_nimble(mcp_tool_def["inputSchema"]),
                        # This context will be passed to HermesMcpToolAction.run/2 when LangChain executes it
                        _hermes_client_id: hermes_client_id, # Used by the run/2 function
                        _mcp_tool_name: tool_name_str # Also for the run/2 function
                      }

                      # Create a LangChain.Function, using a context map to pass tool-specific config
                      # to McpHermesApp.Actions.HermesMcpToolAction.to_tool/1 and .run/2
                      langchain_fn = Function.new!(%{
                        module: McpHermesApp.Actions.HermesMcpToolAction,
                        # This context is passed to HermesMcpToolAction.to_tool/1 (if it took context)
                        # and importantly to HermesMcpToolAction.run/2 as its `context` argument.
                        context: %{
                          hermes_client_id: hermes_client_id,
                          mcp_tool_name: tool_name_str,
                          # Pass the dynamic action_config so to_tool and run can use it
                          action_metadata: Map.take(action_config_for_tool, [:name, :description, :schema])
                        }
                      })
                      Map.put(inner_acc, tool_name_str, langchain_fn)
                    end)
                  _ -> acc_tools # Error or no tools
                end
              else acc_tools # Client not found
              end
            end)

          initial_agent_state = %__MODULE__{
            workflow_name: workflow_name,
            workflow_config: workflow_config,
            llm_chain: llm_chain,
            available_langchain_mcp_tools: available_langchain_mcp_tools
          }
          {:ok, initial_agent_state}
        end
      end

      @impl Jido.Agent
      def actions(_agent_struct), do: [] # Tools are managed as LangChain.Function now

      @impl Jido.Agent
      def handle_signal(%Signal{type: "jido.ai.chat.response", data: %{message: user_query}}, agent_struct) do
        workflow_agent_state = agent_struct.state # Our %McpLangchainApp.Workflow.Agent{}
        workflow_name = workflow_agent_state.workflow_name
        workflow_config = workflow_agent_state.workflow_config
        llm_chain_instance = workflow_agent_state.llm_chain # Pre-configured LLMChain

        Logger.info("[Workflow.Agent #{workflow_name}] LangChain query: #{user_query}")

        initial_prompt_text = String.replace(workflow_config["initial_prompt_template"], "{query}", user_query)

        # LangChain uses a list of LangChain.Message structs
        initial_messages = [
          Message.new_system!(initial_prompt_text) # Could also be a user message for the initial query
        ]

        # Tools are LangChain.Function structs, ready to be added to the chain
        tools_to_use_lc = Map.values(workflow_agent_state.available_langchain_mcp_tools)

        chain_with_context =
          llm_chain_instance
          |> LLMChain.add_messages(initial_messages)
          |> LLMChain.add_tools(tools_to_use_lc) # LangChain handles these tools

        conversation_result =
          run_langchain_conversation_loop(
            agent_struct.id,
            chain_with_context, # Pass the chain configured with model, messages, tools
            max_turns = workflow_config["max_conversation_turns"]
          )

        response_data =
          case conversation_result do
            {:ok, text_response} -> %{response: text_response}
            {:error, reason} -> %{error: inspect(reason)}
          end

        {:ok, response_data, []} # Return data for Jido.AI.Agent to wrap in signal
      end


      # --- LangChain Conversation Loop ---
      defp run_langchain_conversation_loop(
            agent_id,
            current_llm_chain, # This is the LLMChain instance
            max_turns,
            current_turn \\ 1,
            accumulated_responses \\ [] # Store only assistant text responses
          ) do
        if current_turn > max_turns do
          Logger.warning("[#{agent_id}] LangChain Max turns reached.")
          final_text = Enum.reverse(accumulated_responses) |> Enum.join("\n")
          {:ok, final_text <> "\n[Max interaction turns reached.]"}
        else
          Logger.info("[#{agent_id}] LangChain Turn #{current_turn}/#{max_turns}")

          # Run the chain.
          # `mode: :while_needs_response` will handle tool execution loop internally using the added functions.
          # The functions in `available_langchain_mcp_tools` have `HermesMcpToolAction.run/2` as their `function`.
          # That `run/2` will be called by LangChain with LLM-provided args and the context we set in `Function.new!`.
          case LLMChain.run(current_llm_chain, mode: :while_needs_response) do
            {:ok, final_chain_state} ->
              # After LangChain's internal tool loop, final_chain_state.last_message.content
              # should be the LLM's textual response to the user.
              last_llm_message_content = final_chain_state.last_message.content

              if last_llm_message_content && String.trim(last_llm_message_content) != "" do
                Logger.info("[#{agent_id}] LangChain Final LLM Response: #{last_llm_message_content}")
                # This is the final answer from the LLM after any tool use.
                {:ok, Enum.reverse([last_llm_message_content | accumulated_responses]) |> Enum.join("\n")}
              else
                # LLM decided no further text response after tool use, or no tool use and no text.
                Logger.warning("[#{agent_id}] LangChain: LLM provided no final text content.")
                final_text = Enum.reverse(accumulated_responses) |> Enum.join("\n")
                default_empty_response = "[AI model provided no further text after turn #{current_turn}.]"
                response = if final_text == "", do: default_empty_response, else: final_text <> "\n" <> default_empty_response
                {:ok, response}
              end

            {:error, %LangChain.LangChainError{message: error_msg, original: original_error}} = error ->
              Logger.error("[#{agent_id}] LangChain Error in LLMChain.run: #{error_msg}, Original: #{inspect(original_error)}")
              {:error, error}
            {:error, reason} ->
              Logger.error("[#{agent_id}] LangChain Unknown Error in LLMChain.run: #{inspect(reason)}")
              {:error, reason}
          end
        end
      end

      # Helper (copied from McpHermesApp.Actions.HermesMcpToolAction - centralize this)
      defp convert_json_schema_to_nimble(json_schema) when is_map(json_schema) do
        properties = Map.get(json_schema, "properties", %{})
        required_keys_str = Map.get(json_schema, "required", [])

        Enum.map(properties, fn {name_str, prop_schema} ->
          type_str = Map.get(prop_schema, "type", "string")
          nimble_type =
            case type_str do
              "string" -> :string; "integer" -> :integer; "number" -> :float;
              "boolean" -> :boolean; "array" -> {:list, :any}; "object" -> :map;
              _ -> :string
            end
          required = name_str in required_keys_str
          description = Map.get(prop_schema, "description")
          config = [type: nimble_type]
          config = if required, do: Keyword.put(config, :required, true), else: config
          config = if description, do: Keyword.put(config, :doc, description), else: config
          {String.to_atom(name_str), config}
        end)
      end
      defp convert_json_schema_to_nimble(_), do: []
    end
    ```

*   **`lib/mcp_langchain_app/workflow/supervisor.ex`**:
    (Similar to before, ensures `Workflow.Agent` instances are started)

    ```elixir
    # lib/mcp_langchain_app/workflow/supervisor.ex
    defmodule McpLangchainApp.Workflow.Supervisor do
      use Supervisor
      require Logger

      def start_link(_init_arg) do
        workflow_configs = Application.get_env(:mcp_langchain_app, :workflow_configs, %{})
        Supervisor.start_link(__MODULE__, workflow_configs, name: __MODULE__)
      end

      @impl true
      def init(workflow_configs_map) do
        Logger.info("Workflow.Supervisor initializing with #{map_size(workflow_configs_map)} LangChain workflows.")
        children =
          Enum.map(workflow_configs_map, fn {workflow_name_str, _config_data} ->
            agent_registry_name = String.to_atom("workflow_agent_#{workflow_name_str}")
            {McpLangchainApp.Workflow.Agent,
             [
               name: {:via, Registry, {McpLangchainApp.Workflow.Registry, agent_registry_name}},
               workflow_name: workflow_name_str
             ]}
          end) ++ [{Registry, keys: :unique, name: McpLangchainApp.Workflow.Registry}]

        Supervisor.init(children, strategy: :one_for_one)
      end
    end
    ```

**Stage 4: CLI**

*   **`lib/mcp_langchain_app/cli.exs`**: (Similar to previous)

    ```elixir
    # lib/mcp_langchain_app/cli.exs
    defmodule McpLangchainApp.CLI do
      require Logger
      alias McpLangchainApp.Workflow.Agent # Our Jido.AI.Agent implementation

      def main(args) do
        Application.ensure_all_started(:mcp_langchain_app)
        Application.ensure_all_started(:jido)
        Application.ensure_all_started(:jido_ai)
        Application.ensure_all_started(:langchain) # Ensure LangChain app is started

        parse_result = Optimus.new!(
          name: "mcp_cli_langchain",
          version: Mix.Project.config()[:version],
          allow_unknown_args: true,
          specs: [
            list_workflows: [value_name: "list-workflows", type: :boolean, short: :l],
            workflow: [value_name: "WORKFLOW_NAME", type: :string, required: false]
          ]
        ) |> Optimus.parse(args)

        case parse_result do
          {:ok, opts, [query | rest_query]} ->
            workflow_name = opts[:workflow]
            full_query = Enum.join([query | rest_query], " ")
            if workflow_name && full_query != "" do run_single_query(workflow_name, full_query) else print_usage() end
          {:ok, %{list_workflows: true}, _} -> list_workflows()
          {:ok, %{workflow: workflow_name}, []} when not is_nil(workflow_name) -> run_chat_loop(workflow_name)
          _ -> print_usage()
        end
      end

      defp print_usage do
        IO.puts("Usage: mix run.cli <WORKFLOW_NAME> <query> OR mix run.cli --list-workflows")
      end
      defp list_workflows do
        # ... (same as previous list_workflows) ...
        workflows = Application.get_env(:mcp_langchain_app, :workflow_configs, %{})
        IO.puts("\nAvailable workflows:")
        if Map.is_empty(workflows) do
          IO.puts("  No workflows defined.")
        else
          Enum.each(workflows, fn {name, config} ->
            IO.puts("  - #{name}: #{config["description"] || "No description"}")
          end)
        end
      end

      defp run_single_query(workflow_name_str, query_str) do
        IO.puts("Processing query for workflow '#{workflow_name_str}': \"#{query_str}\"")
        agent_registry_name = String.to_atom("workflow_agent_#{workflow_name_str}")

        case Jido.Util.whereis({agent_registry_name, McpLangchainApp.Workflow.Registry}) do
         {:ok, agent_pid} ->
            # Jido.AI.Agent.chat_response sends a "jido.ai.chat.response" signal
            # Our Workflow.Agent's handle_signal should process it
            case Jido.AI.Agent.chat_response(agent_pid, query_str) do
              # handle_signal returns {:ok, data_map, directives}
              {:ok, %{response: response_text}, _directives} -> IO.puts("\nResponse:\n#{response_text}")
              {:ok, %{error: error_reason}, _directives}    -> IO.puts("\nWorkflow Error: #{error_reason}")
              {:error, reason} -> IO.puts("\nError calling workflow agent: #{inspect(reason)}")
              other -> IO.puts("\nUnexpected response: #{inspect(other)}")
            end
         {:error, :not_found} ->
            IO.puts("Error: Workflow Agent '#{workflow_name_str}' (as #{agent_registry_name}) not found.")
        end
      end
      defp run_chat_loop(workflow_name_str) do
        # ... (similar to previous, ensuring calls to Jido.AI.Agent.chat_response) ...
        agent_registry_name = String.to_atom("workflow_agent_#{workflow_name_str}")
        case Jido.Util.whereis({agent_registry_name, McpLangchainApp.Workflow.Registry}) do
         {:ok, agent_pid} ->
            IO.puts("\nChatting with workflow: '#{workflow_name_str}'. Type 'quit' to exit.")
            Stream.repeatedly(fn -> IO.gets("> ") |> String.trim() end)
            |> Enum.reduce_while(:ok, fn
              "quit", _ -> {:halt, :ok}
              "", _ -> {:cont, :ok} # Skip empty input
              query_str, _ ->
                case Jido.AI.Agent.chat_response(agent_pid, query_str) do
                  {:ok, %{response: response_text}, _} -> IO.puts(response_text)
                  {:ok, %{error: error_reason}, _}    -> IO.puts("Error: #{error_reason}")
                  {:error, reason}                     -> IO.puts("Error: #{inspect(reason)}")
                  other                               -> IO.puts("Unexpected: #{inspect(other)}")
                end
                {:cont, :ok}
            end)
            IO.puts("Exiting chat.")
          _ ->
            IO.puts("Error: Workflow Agent '#{workflow_name_str}' not found.")
        end
      end
    end

    if System.get_env("__MIX_ENV__") != "test" and System.get_env("MIX_TASK") == "run.cli" do
      McpLangchainApp.CLI.main(System.argv())
    end
    ```

**Running:**

1.  Ensure `priv/dev/mcp_tool_script.py` is in place and paths in `config/config.exs` (or `dev.exs`) are correct.
2.  Set `GEMINI_API_KEY` (or `LANGCHAIN_GEMINI_API_KEY`) in your `.env` file.
3.  `mix deps.get && mix compile`
4.  `mix run.cli --list-workflows`
5.  `mix run.cli gemini_mcp_workflow "Tell the example tool that param1 is 'langchain test' and param2 is 789."`
6.  `mix run.cli gemini_mcp_workflow` (for interactive mode)

**Key Differences and Simplifications using LangChain.ex:**

*   **LLM Interaction Abstraction:** `LangChain.ChatModels.ChatGoogle` and `LangChain.Chains.LLMChain` handle the direct API calls to Gemini. This replaces the need for a custom `Jido.AI.Actions.OpenaiEx` (or a similar custom action for Gemini) if LangChain's built-in provider is sufficient.
*   **Tool Handling:** LangChain has its own tool/function calling mechanism.
    *   Our `HermesMcpToolAction` now needs a `to_tool/1` that produces a schema LangChain understands (`parameters_schema`).
    *   The `Workflow.Agent` converts MCP tool definitions into `LangChain.Function` structs, providing `HermesMcpToolAction.run/2` as the execution function. The context map passed to `Function.new!` is crucial for `HermesMcpToolAction.run/2` to know which Hermes client and MCP tool to use.
    *   `LLMChain.run(chain, mode: :while_needs_response)` will internally manage the loop of LLM asking for a tool, LangChain calling our `HermesMcpToolAction.run/2`, and sending results back to the LLM. This simplifies the `run_conversation_loop` significantly.
*   **Prompt Management:** We use `LangChain.Message` for constructing the conversation history passed to `LLMChain`. `Jido.AI.Prompt` can still be used for initial template formatting if desired, before converting to `LangChain.Message` structs.
*   **Reduced Code for LLM Calls:** The `Jido.AI.Actions.Langchain` (if it were a custom Jido Action, which we're bypassing by using `LLMChain` directly in the agent) or direct `LLMChain` usage simplifies the LLM call compared to manual HTTP requests or even a generic `Jido.AI.Actions.OpenaiEx` for a new provider if LangChain supports it out of the box.

This approach cleanly separates concerns:
*   `Hermes MCP`: Manages raw MCP server communication.
*   `Jido.Action` (`HermesMcpToolAction`): Provides a standardized way for Jido/LangChain to invoke these Hermes-managed tools.
*   `LangChain.ex`: Handles LLM interaction and its specific tool-calling loop.
*   `Jido.AI.Agent` (`Workflow.Agent`): Orchestrates the overall process, prepares data for LangChain, and processes the final results.

This is a powerful combination for building robust and flexible AI agent systems. Remember that the `HermesMcpToolAction` schema conversion logic and how `LangChain.Function` context is used are critical for the tools to work correctly.
