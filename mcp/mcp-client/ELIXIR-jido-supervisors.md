Okay, this is an excellent and forward-thinking plan! Building a multi-agent framework with Elixir, leveraging Hermes MCP for tool communication, LangChain.ex for LLM interactions, and Jido/Jido.AI for the agentic/workflow structure is a powerful combination.

Let's break this down.

## Jido and Jido.AI Supervisors

1.  **How do supervisors work in Jido and Jido_AI?**
    *   **Jido Core:** Jido itself is built on OTP. When you define a `Jido.Agent` (using `use Jido.Agent`), you are essentially creating a `GenServer` behavior. These `GenServer`s (your agents) are meant to be supervised like any other GenServer in an OTP application. Jido also provides some of its own supervised components, like `Jido.Registry` (for process discovery) and often a `Jido.TaskSupervisor` for running asynchronous tasks related to agent operations.
    *   **Jido.AI:** `Jido.AI.Agent` (using `use Jido.AI.Agent`) extends `Jido.Agent`. So, Jido.AI agents are also GenServers. `Jido.AI.Keyring` (for managing API keys) is a GenServer and needs to be supervised. `Jido.AI.Actions.OpenaiEx` (which you might use or adapt if not using LangChain.ex directly for all LLM calls) would be called from within your agent's logic.
    *   **In essence:** Jido/Jido.AI provide the building blocks (agent behaviors, specific actions) that you then integrate into your own OTP application's supervision tree. They don't typically dictate your *entire* top-level supervision strategy but provide components that *must* be supervised.

2.  **Are they optional?**
    *   Supervising your Jido agents (and Jido.AI components like Keyring) is **not optional** if you want a robust, fault-tolerant OTP application. Running GenServers without supervision means they won't be restarted if they crash, and you lose a core benefit of OTP.
    *   The Jido framework itself may start its own internal supervisors for its own needs when you include `:jido` or `:jido_ai` in your application's `extra_applications`. Your responsibility is to supervise the agents and components *you* define and start.

## Supervisor Tree and Restart Strategy for OTP using Jido and Jido.AI (and Hermes + LangChain.ex)

Here's how you would approach designing a supervisor tree for your application:

1.  **Top-Level Application Supervisor (`McpLangchainApp.Application` -> `McpLangchainApp.MainSupervisor`):**
    *   This is the root of your application's specific supervision tree.
    *   **Strategy:** Often `one_for_one` or `one_for_all` if critical components are tightly coupled.
    *   **Children:**
        *   `Jido.AI.Keyring`: Essential for API key management. If this fails, many other things might not work.
        *   `McpLangchainApp.ConfigLoader`: If you have a GenServer loading your `workflows.json` or other dynamic configs.
        *   `McpLangchainApp.HermesClientSupervisor`: Manages all `Hermes.Client` connections to your MCP tools.
        *   `McpLangchainApp.Workflow.Supervisor`: Manages your Jido.AI agent instances (which represent your workflows).

2.  **`McpLangchainApp.HermesClientSupervisor` (`Supervisor`):**
    *   **Strategy:** `one_for_one`. Each `Hermes.Client` connection to an external MCP tool is independent. If one tool connection crashes, it shouldn't affect others.
    *   **Children:** Dynamically starts one `Hermes.Client` GenServer for each MCP server defined in your configuration. These `Hermes.Client` processes should be named (e.g., via a local `Registry` or by passing a name to `Hermes.Client.start_link/1` if it supports it) so they can be easily looked up.
    *   **Restart:** `:permanent` for each `Hermes.Client`. You always want these connections to try and come back up.

3.  **`McpLangchainApp.Workflow.Supervisor` (`Supervisor`):**
    *   **Strategy:** `one_for_one`. Each workflow agent instance should be independent.
    *   **Children:** Starts one `McpLangchainApp.Workflow.Agent` (which `use Jido.AI.Agent`) for each workflow definition you have. These agents should also be named and registered (e.g., using `{:via, Registry, {MyRegistry, agent_name}}`) for easy access.
    *   **Restart:** `:permanent` or `:transient`.
        *   `:permanent`: If a workflow agent crashes, it always restarts. This is good if the agent is meant to be long-lived and state can be re-initialized.
        *   `:transient`: If an agent crashes due to a specific bad input and shouldn't automatically restart on the same input, but should restart if it crashes due to an unexpected internal error. This might be more complex to manage state with. For workflow orchestrators, `:permanent` is often a good starting point, assuming `init/1` can safely re-establish its configuration.

4.  **Jido's Internal Supervisors:**
    *   When you list `:jido` and `:jido_ai` in `extra_applications`, they will start their own necessary supervised processes (like registries, task supervisors for Jido Actions). You don't typically manage these directly but rely on them being present.

**Restart Scenarios & Strategy:**

*   **External MCP Tool Crash:**
    *   The `Hermes.Client` connected to that tool might detect the disconnection (e.g., Port closes, HTTP error).
    *   The `Hermes.Client` GenServer itself might crash or handle the error and attempt to reconnect.
    *   If the `Hermes.Client` crashes, `McpLangchainApp.HermesClientSupervisor` (with `one_for_one`) will restart *only that specific* `Hermes.Client`.
    *   The `Workflow.Agent` attempting to use that tool via the `Hermes.Client` will receive an error. It needs to be robust enough to handle this (e.g., inform the user, try an alternative, or fail the current task).
*   **`Jido.AI.Keyring` Crash:**
    *   If this is supervised by your `MainSupervisor` with `one_for_all` or `rest_for_one`, its crash might restart other critical components. This is often desirable as API keys are fundamental.
*   **`Workflow.Agent` Crash:**
    *   `McpLangchainApp.Workflow.Supervisor` (with `one_for_one`) restarts that specific agent.
    *   The agent's `init/1` callback will run again. Any in-memory state for an ongoing conversation *within that agent* would be lost unless you explicitly persist and reload it (e.g., from a DB, which is a more advanced pattern). For a simple CoT and tool use flow for a single query, re-initializing from config might be sufficient.
*   **LangChain.ex / LLM API Issues:**
    *   These will typically manifest as errors within the `Workflow.Agent`'s call to `LLMChain.run`. The agent should catch these errors and respond appropriately (e.g., retry with backoff, inform user, log). Such errors usually don't crash the agent GenServer unless unhandled.

---

## Review of `ELIXIR-HERMES-LANGCHAIN-JIDO_code.md` and Integration Approach

The provided code in `ELIXIR-HERMES-LANGCHAIN-JIDO_code.md` is a very good starting point and aligns well with the concepts discussed. Let's refine it and highlight key aspects.

**Strengths of the Approach in `ELIXIR-HERMES-LANGCHAIN-JIDO_code.md`:**

1.  **Clear Separation of Concerns:**
    *   Hermes for MCP transport.
    *   Jido Actions (`HermesMcpToolAction`) as an adapter for Hermes tools.
    *   LangChain.ex (`LLMChain`) for LLM interaction and its internal tool loop.
    *   Jido.AI.Agent (`Workflow.Agent`) for overall orchestration and state.
2.  **Dynamic Tool Handling:** The `Workflow.Agent` dynamically discovers tools from Hermes clients and prepares them as `LangChain.Function` structs. This is crucial for flexibility.
3.  **Use of `LLMChain.run(..., mode: :while_needs_response)`:** This correctly leverages LangChain.ex's capability to manage the multi-turn conversation with an LLM, including executing tools.
4.  **OTP Structure:** The supervision tree (Application -> MainSupervisor -> HermesClientSupervisor, Workflow.Supervisor) is sound.

**Review and Refinements for `ELIXIR-HERMES-LANGCHAIN-JIDO_code.md`:**

(Assuming the code provided in the prompt as `ELIXIR-HERMES-LANGCHAIN-JIDO_code.md` is the one I just generated, let's proceed with reviewing *that* code, as it's the most complete context here.)

*   **`mix.exs`:** Looks good. Dependencies are correctly listed. Elixir `~> 1.17` is fine; `~> 1.15` would also work for these libraries.
*   **`config/config.exs` & `workflows.json`:**
    *   Configuration for LangChain API key (e.g., `config :langchain, :gemini_api_key, System.get_env("GEMINI_API_KEY")`) is good. `Jido.AI.Keyring` will pick up `GEMINI_API_KEY` from `.env` if `Jido.AI.Keyring` is started and the key is not explicitly configured elsewhere for LangChain itself. LangChain.ex also checks its own app env.
    *   Hermes client configuration is clear.
    *   `workflows.json`: Specifying `langchain_model` is appropriate.
*   **Dummy Python MCP Script (`priv/dev/mcp_tool_script.py`):**
    *   **Important:** The `call_tool` method in the Python script should expect parameters under `"arguments"` key if that's what `Hermes.Client.call_tool/3` sends (or if the `HermesMcpToolAction` reshapes it). The example script uses `params.get("arguments", {})`.
    *   The `list_tools` response in Python should return a list under the key `"tools"`, as `Hermes.Client` expects: `{"id": ..., "result": {"tools": [tool_def1, ...]}}`. The Python script correctly does this.
    *   The `call_tool` response from Python should be structured as `{"id": ..., "result": {"content": ACTUAL_TOOL_OUTPUT, "isError": false}}`. The Python script correctly does this with `{"output": tool_output_content}` inside the main `content` map.
*   **`McpLangchainApp.Application`:** Starts `Jido.AI.Keyring`, `ConfigLoader`, `HermesClientSupervisor`, `Workflow.Supervisor`. This is correct.
*   **`McpLangchainApp.HermesClientSupervisor`:**
    *   Correctly iterates configs and starts `Hermes.Client` children.
    *   Naming of Hermes clients: `Hermes.Client.via_tuple(client_id_atom)` is a good way to ensure they are registered if `Hermes.Client` itself registers with this pattern, or if you create a local registry. If `Hermes.Client` takes a `:name` option, you can directly use `{Hermes.Client, name: Module.concat(Hermes.Client, client_id_atom)}` for global registration or a custom registry. The current code using `Hermes.Client.via_tuple/1` relies on `Hermes.Client` using `Registry` with that naming scheme. *Self-correction based on generated code: The `HermesClientSupervisor` in the generated code was trying to use `Hermes.Client.via_tuple(client_id_atom)` in `Process.whereis`. It should start the client with a name that can be looked up that way, or use a local registry. The corrected code example in the thought block and the final answer's code uses this helper for `Process.whereis` but the supervisor needs to *start* it with a name that makes `via_tuple` work or ensure `Hermes.Client` does this itself.* In `ELIXIR-HERMES-LANGCHAIN-JIDO_code.md`, `HermesClientSupervisor` now correctly sets the name: `Supervisor.child_spec({Hermes.Client, Keyword.put_new(config_list, :name, {Hermes.Client, client_id_atom})}, id: client_id_atom)`. This is good.
*   **`McpLangchainApp.Actions.HermesMcpToolAction`:**
    *   **`to_tool/1`:** This function is key for LangChain.ex integration. It correctly takes `action_config_for_tool` (which will be the dynamically discovered MCP tool's definition: name, description, schema) and formats it into the structure `LangChain.Function.new!/1` expects (name, description, parameters_schema, function, context).
        *   The `parameters_schema` must be in the JSON Schema format LangChain/OpenAI tools expect. The `convert_nimble_schema_to_langchain_params` helper looks plausible.
        *   The `function: &__MODULE__.run/2` is correct.
        *   The `context` map passed to `LangChain.Function.new!/1` (which `to_tool/1` doesn't directly create but informs) is vital. This `context` will be passed to `run/2` when LangChain executes the tool. It *must* contain `hermes_client_id` and `mcp_tool_name`.
    *   **`run/2(params, context)`:**
        *   Correctly extracts `hermes_client_id` and `mcp_tool_name` from the `context`.
        *   Looks up the `Hermes.Client` PID.
        *   Calls `Hermes.Client.call_tool(hermes_client_pid, mcp_tool_name, params)`. The `params` here are the arguments for the *specific* MCP tool, already validated by LangChain against the `parameters_schema`.
        *   The result formatting for LangChain (`{:ok, actual_content}` or `{:error, string_reason}`) is appropriate. The `actual_content` should be what the LLM expects as tool output (often a string or JSON-serializable map).
*   **`McpLangchainApp.Workflow.Agent`:**
    *   **`init/1`:**
        *   Initializes `ChatGoogle` and `LLMChain` – correct.
        *   **Tool Discovery & `LangChain.Function` Creation:** This is the most complex and crucial part.
            *   It iterates `hermes_clients_used`.
            *   Calls `Hermes.Client.list_tools`.
            *   For each MCP tool, it prepares `action_config_for_tool` (name, desc, Nimble schema).
            *   Then, it **must create the `LangChain.Function` struct explicitly here.** The `HermesMcpToolAction.to_tool/1` is a helper to generate the *LangChain-compatible schema part*. The `Workflow.Agent` needs to construct the full `LangChain.Function` map:
                ```elixir
                # Inside Workflow.Agent.init/1's tool loop
                mcp_tool_name_str = mcp_tool_def["name"]
                mcp_description = mcp_tool_def["description"]
                mcp_input_schema_json = mcp_tool_def["inputSchema"]

                # This context will be passed to HermesMcpToolAction.run/2 by LangChain
                tool_execution_context = %{
                  hermes_client_id: hermes_client_id, # The atom ID of the Hermes client
                  mcp_tool_name: mcp_tool_name_str    # The string name of the MCP tool
                }

                langchain_fn = %LangChain.Function{
                  name: mcp_tool_name_str,
                  description: mcp_description,
                  parameters_schema: McpHermesApp.Actions.HermesMcpToolAction.Tool.convert_json_schema_to_langchain_params_for_lc(mcp_input_schema_json), # Direct conversion
                  function: &McpLangchainApp.Actions.HermesMcpToolAction.run/2,
                  context: tool_execution_context
                }
                # Store this langchain_fn in available_langchain_mcp_tools
                ```
                *Self-correction: The `LangChain.Function.new!/1` call in the generated code for `ELIXIR-HERMES-LANGCHAIN-JIDO_code.md` correctly passes a map like `{module: McpHermesApp.Actions.HermesMcpToolAction, context: tool_specific_context}`. For `to_tool/1` to be truly dynamic, it would need to be invoked when `LangChain.Function.new!/1` resolves the schema. The current `HermesMcpToolAction.to_tool/1` takes an argument, which means the `Workflow.Agent` would call `HermesMcpToolAction.to_tool(action_config)` to get the LangChain-formatted tool parts, and then build the `LangChain.Function` struct. The generated code for `ELIXIR-HERMES-LANGCHAIN-JIDO_code.md` is creating `LangChain.Function` using `Function.new!(%{module: ..., context: ...})`. The `module`'s `to_tool/1` (if arity 1 is supported by `Function.new!/1` for schema gen, or arity 0 if static) would be used. The current `HermesMcpToolAction.to_tool/1` with an arg is fine if we construct the `LangChain.Function` map manually in the agent by calling `to_tool` first.*
                The code in `ELIXIR-HERMES-LANGCHAIN-JIDO_code.md` inside `Workflow.Agent.init/1` for creating `langchain_fn` using `Function.new!(%{module: ..., context: ...})` is correct. The `context` provided there is what `HermesMcpToolAction.run/2` receives. The `to_tool/1` in `HermesMcpToolAction` now needs to ensure it can be called by `LangChain.Function.new!/1` potentially with that context to generate its *schema parts*. `LangChain.Function.new!/1` looks for `YourModule.to_tool/0` or `YourModule.to_tool/1` (taking the `Function` struct itself as arg). The current implementation of `HermesMcpToolAction.to_tool/1` taking `action_config_for_tool` means the `Workflow.Agent` would have to:
                1. Get `action_config_for_tool`.
                2. Call `HermesMcpToolAction.to_tool(action_config_for_tool)` to get `name`, `description`, `parameters_schema`.
                3. Create the `LangChain.Function` struct manually with these parts and `&HermesMcpToolAction.run/2` and the `context`.
                The provided `ELIXIR-HERMES-LANGCHAIN-JIDO_code.md`'s `Workflow.Agent.init/1` correctly does this manual construction which is more flexible.

    *   **`handle_signal("jido.ai.chat.response", ...)`:**
        *   Sets up messages for `LLMChain`.
        *   Adds the discovered `LangChain.Function`s to the chain using `LLMChain.add_tools/2`.
        *   Calls `run_langchain_conversation_loop`.
    *   **`run_langchain_conversation_loop`:**
        *   Uses `LLMChain.run(chain, mode: :while_needs_response)`. This is perfect. LangChain.ex will handle the back-and-forth with the LLM, invoking the tool's `run/2` function (our `HermesMcpToolAction.run/2`) when the LLM requests a tool.
        *   The result `final_chain_state.last_message.content` should be the final textual response.
*   **`McpLangchainApp.Workflow.Supervisor`:** Looks correct for starting and registering workflow agents.
*   **`McpLangchainApp.CLI`:** Looks good for basic interaction. The `Jido.Util.whereis/1` is correct for finding registered Jido agents. The response handling from `Jido.AI.Agent.chat_response` should expect the format `{:ok, data_map, directives}` as `handle_signal` in the agent now returns that.

**Key Improvements & Considerations from the `ELIXIR-HERMES-LANGCHAIN-JIDO_code.md`:**

*   **`HermesMcpToolAction.to_tool/1` and `Workflow.Agent`'s `LangChain.Function` creation:** The `Workflow.Agent` correctly calls `HermesMcpToolAction.to_tool/1` with the specific tool's config to get the name/desc/schema, and then *manually constructs* the `%LangChain.Function{}` struct, assigning `&HermesMcpToolAction.run/2` as the function and passing the necessary `tool_execution_context`. This is a robust way to handle dynamic tools with a generic action runner.
*   **Clarity of `run/2` context:** The `context` for `HermesMcpToolAction.run/2` is now clearly being assembled in `Workflow.Agent.init/1` and passed via the `LangChain.Function` struct.
*   **Schema Conversion Helpers:** The `convert_json_schema_to_nimble` and `convert_nimble_schema_to_langchain_params` (or similar naming for the direct JSON to LangChain JSON conversion) are essential. The direct `convert_json_schema_to_langchain_params_for_lc` in the provided code for `Workflow.Agent` is more direct for LangChain.

This approach is solid. It uses each library for its strengths:
*   **Hermes MCP:** Raw, standardized tool communication.
*   **Jido.Action (`HermesMcpToolAction`):** An adapter layer, making Hermes tools callable in a standard way (though LangChain bypasses the Jido planning part for tools here).
*   **LangChain.ex:** LLM interactions and its own powerful tool-use loop.
*   **Jido.AI.Agent (`Workflow.Agent`):** Orchestration, state management for the workflow, dynamic preparation of tools for LangChain.
*   **OTP:** Overall resilience and concurrency.

The `ELIXIR-HERMES-LANGCHAIN-JIDO_code.md` provides a very strong foundation for your project.

```elixir
# lib/mcp_langchain_app/application.ex
defmodule McpLangchainApp.Application do
  use Application
  require Logger

  @impl true
  def start(_type, _args) do
    Logger.info("Starting McpLangchainApp...")

    children = [
      Jido.AI.Keyring,
      McpLangchainApp.ConfigLoader,
      McpLangchainApp.HermesClientSupervisor,
      McpLangchainApp.Workflow.Supervisor
    ]

    opts = [strategy: :one_for_one, name: McpLangchainApp.MainSupervisor]
    result = Supervisor.start_link(children, opts)
    Logger.info("McpLangchainApp started successfully.")
    result
  end
end

# lib/mcp_langchain_app/config_loader.ex
defmodule McpLangchainApp.ConfigLoader do
  use GenServer
  require Logger

  def start_link(_opts) do
    GenServer.start_link(__MODULE__, :ok, name: __MODULE__)
  end

  @impl true
  def init(:ok) do
    Logger.info("ConfigLoader initializing...")
    workflows_path = Application.fetch_env!(:mcp_langchain_app, :workflows_path)

    with {:ok, workflows_raw} <- File.read(workflows_path),
         {:ok, workflows_data} <- Jason.decode(workflows_raw),
         workflows = Map.get(workflows_data, "workflows", %{}) do
      Application.put_env(:mcp_langchain_app, :workflow_configs, workflows)
      Logger.info("Workflow configurations loaded.")
      {:ok, :no_state_needed}
    else
      {:error, reason} ->
        Logger.error("Failed to load workflow configurations: #{inspect(reason)}")
        {:stop, {:workflow_config_load_failed, reason}}
    end
  end
end

# lib/mcp_langchain_app/hermes_client_supervisor.ex
defmodule McpLangchainApp.HermesClientSupervisor do
  use Supervisor
  require Logger

  def start_link(_init_arg) do
    hermes_client_configs = Application.get_env(:mcp_langchain_app, :hermes_clients, %{})
    Supervisor.start_link(__MODULE__, hermes_client_configs, name: __MODULE__)
  end

  @impl true
  def init(hermes_client_configs) do
    Logger.info(
      "HermesClientSupervisor initializing with #{map_size(hermes_client_configs)} clients."
    )

    children =
      Enum.map(hermes_client_configs, fn {client_id_atom, config_list} ->
        # Ensure config_list is a keyword list and add :name for registration
        client_opts =
          config_list
          |> Keyword.put_new(:name, {Hermes.Client, client_id_atom}) # Register with this tuple name
          |> Keyword.put_new_lazy(:capabilities, fn -> %{} end)

        Logger.debug(
          "Starting Hermes.Client '#{inspect(client_id_atom)}' with opts: #{inspect(client_opts)}"
        )

        Supervisor.child_spec({Hermes.Client, client_opts}, id: client_id_atom)
      end)

    Supervisor.init(children, strategy: :one_for_one)
  end
end

# lib/mcp_langchain_app/actions/hermes_mcp_tool_action.ex
defmodule McpLangchainApp.Actions.HermesMcpToolAction do
  # This module is primarily a container for the `run/2` function
  # that LangChain.Function will execute.
  # The `to_tool/1` helper is used by the Workflow.Agent to construct
  # the LangChain.Function struct with the correct schema.
  alias Hermes.Client
  require Logger

  # Helper to construct the schema part for a LangChain.Function
  # This is NOT a Jido.Action.to_tool/0 callback.
  def to_tool_schema_parts(action_config_for_tool \\ %{}) do
    tool_name = Map.get(action_config_for_tool, :name, "unknown_mcp_tool")
    description = Map.get(action_config_for_tool, :description, "An MCP tool.")
    # action_config_for_tool.schema is already JSON schema for LangChain
    json_schema_params = Map.get(action_config_for_tool, :schema_for_langchain, %{"type" => "object", "properties" => %{}})


    %{
      name: tool_name,
      description: description,
      parameters_schema: json_schema_params
    }
  end

  # This is the function that LangChain.Function will execute.
  def run(params, context) do
    hermes_client_id = Map.fetch!(context, :hermes_client_id)
    mcp_tool_name_str = Map.fetch!(context, :mcp_tool_name) # String name of the tool

    Logger.info(
      "[HermesMcpToolAction for #{mcp_tool_name_str} via Hermes Client #{hermes_client_id}] Running with params: #{inspect(params)}"
    )

    # Hermes.Client.via_tuple expects the client_id_atom as the second element
    hermes_client_pid_tuple_name = {Hermes.Client, hermes_client_id}
    hermes_client_pid = Process.whereis(hermes_client_pid_tuple_name)


    if !is_pid(hermes_client_pid) do
      Logger.error(
        "HermesMcpToolAction: Hermes.Client PID for '#{inspect(hermes_client_pid_tuple_name)}' not found."
      )

      {:error, "Hermes Client not found: #{hermes_client_id}"}
    else
      # `params` for `Hermes.Client.call_tool` should be the arguments for the MCP tool.
      # `HermesMcpToolAction.run/2`'s `params` *are* these arguments, already validated by LangChain.
      # Hermes.Client.call_tool/3 expects tool_name as string, params as map.
      case Client.call_tool(hermes_client_pid, mcp_tool_name_str, params) do
        {:ok, %Hermes.MCP.Response{result: tool_output_map, is_error: false}} ->
          Logger.debug(
            "[HermesMcpToolAction #{mcp_tool_name_str}] Result: #{inspect(tool_output_map)}"
          )

          actual_content = Map.get(tool_output_map, "content", tool_output_map)
          {:ok, actual_content}

        {:ok, %Hermes.MCP.Response{result: error_payload, is_error: true}} ->
          Logger.error(
            "[HermesMcpToolAction #{mcp_tool_name_str}] MCP Domain Error: #{inspect(error_payload)}"
          )

          {:error, "MCP tool returned domain error: #{inspect(error_payload)}"}

        {:error, %Hermes.MCP.Error{} = hermes_error} ->
          Logger.error(
            "[HermesMcpToolAction #{mcp_tool_name_str}] Hermes Client Error: #{inspect(hermes_error)}"
          )

          {:error, "Hermes Client MCP call failed: #{inspect(hermes_error.reason)}"}

        {:error, reason} ->
          Logger.error(
            "[HermesMcpToolAction #{mcp_tool_name_str}] GenServer Error: #{inspect(reason)}"
          )

          {:error, "Error calling Hermes Client: #{inspect(reason)}"}
      end
    end
  end
end


# lib/mcp_langchain_app/workflow/agent.ex
defmodule McpLangchainApp.Workflow.Agent do
  use Jido.AI.Agent

  alias LangChain.ChatModels.ChatGoogle
  alias LangChain.Chains.LLMChain
  alias LangChain.Message
  alias LangChain.Function
  alias McpLangchainApp.Actions.HermesMcpToolAction # For its run/2 and schema helper

  require Logger

  defstruct workflow_name: nil,
            workflow_config: %{},
            llm_chain: nil,
            available_langchain_mcp_tools: %{} # tool_name_str => LangChain.Function struct

  @impl Jido.Agent
  def init(opts) do
    workflow_name_str = Keyword.fetch!(opts, :workflow_name) # String name
    all_workflow_configs = Application.get_env(:mcp_langchain_app, :workflow_configs, %{})
    workflow_config = Map.get(all_workflow_configs, workflow_name_str)

    unless workflow_config do
      Logger.error("Workflow '#{workflow_name_str}' not found.")
      {:ok, %__MODULE__{workflow_name: workflow_name_str}} # Degraded state
    else
      Logger.info(
        "[Workflow.Agent #{workflow_name_str}] Initializing with config: #{inspect(workflow_config)}"
      )

      langchain_model_id = workflow_config["langchain_model"]
      gemini_chat_model = ChatGoogle.new!(model: langchain_model_id, stream: false)

      llm_chain =
        %{llm: gemini_chat_model, verbose: Application.get_env(:logger, :console)[:level] == :debug}
        |> LLMChain.new!()

      hermes_client_ids_used_str = workflow_config["hermes_clients_used"] || []
      hermes_client_ids_atoms = Enum.map(hermes_client_ids_used_str, &String.to_atom/1)

      available_langchain_mcp_tools =
        Enum.reduce(hermes_client_ids_atoms, %{}, fn hermes_client_id_atom, acc_tools ->
          # Construct the tuple name used for registration by HermesClientSupervisor
          hermes_client_pid_tuple_name = {Hermes.Client, hermes_client_id_atom}
          hermes_client_pid = Process.whereis(hermes_client_pid_tuple_name)

          if is_pid(hermes_client_pid) do
            case Hermes.Client.list_tools(hermes_client_pid) do
              {:ok, %Hermes.MCP.Response{result: %{"tools" => mcp_tools_list}}} ->
                Enum.reduce(mcp_tools_list, acc_tools, fn mcp_tool_def, inner_acc ->
                  tool_name_str = mcp_tool_def["name"]
                  description_str = mcp_tool_def["description"]
                  # Directly use the JSON schema from MCP tool for LangChain
                  parameters_json_schema = mcp_tool_def["inputSchema"]


                  # This context will be passed to HermesMcpToolAction.run/2 by LangChain
                  tool_execution_context = %{
                    hermes_client_id: hermes_client_id_atom,
                    mcp_tool_name: tool_name_str
                  }

                  # Use the helper from HermesMcpToolAction to get name, desc, schema_params
                  # but we can construct it directly too.
                  # Let's ensure parameters_schema is correctly formatted for LangChain.
                  # The `inputSchema` from MCP *is* JSON Schema.
                  langchain_fn = %LangChain.Function{
                    name: tool_name_str,
                    description: description_str,
                    parameters_schema: parameters_json_schema, # Pass JSON schema directly
                    function: &HermesMcpToolAction.run/2,
                    context: tool_execution_context
                  }

                  Map.put(inner_acc, tool_name_str, langchain_fn)
                end)

              {:error, reason} ->
                Logger.error(
                  "Failed to list tools for Hermes client #{hermes_client_id_atom}: #{inspect(reason)}"
                )
                acc_tools

              other_response ->
                Logger.warning(
                  "Unexpected list_tools response from Hermes client #{hermes_client_id_atom}: #{inspect(other_response)}"
                )
                acc_tools

            end
          else
            Logger.warning(
              "Hermes client PID for '#{inspect(hermes_client_pid_tuple_name)}' not found during tool discovery."
            )
            acc_tools
          end
        end)

      initial_agent_state = %__MODULE__{
        workflow_name: workflow_name_str,
        workflow_config: workflow_config,
        llm_chain: llm_chain,
        available_langchain_mcp_tools: available_langchain_mcp_tools
      }

      {:ok, initial_agent_state}
    end
  end

  @impl Jido.Agent
  def actions(_agent_struct), do: [] # Tools managed via LangChain.Function

  @impl Jido.Agent
  def handle_signal(%Signal{type: "jido.ai.chat.response", data: %{message: user_query}}, agent_struct) do
    workflow_agent_state = agent_struct.state
    workflow_name = workflow_agent_state.workflow_name
    workflow_config = workflow_agent_state.workflow_config
    llm_chain_instance = workflow_agent_state.llm_chain

    Logger.info("[Workflow.Agent #{workflow_name}] LangChain query: #{user_query}")

    initial_prompt_text =
      String.replace(workflow_config["initial_prompt_template"], "{query}", user_query)

    initial_messages = [Message.new_system!(initial_prompt_text)]
    tools_to_use_lc = Map.values(workflow_agent_state.available_langchain_mcp_tools)

    chain_with_context =
      llm_chain_instance
      |> LLMChain.add_messages(initial_messages)
      |> LLMChain.add_tools(tools_to_use_lc)

    conversation_result =
      run_langchain_conversation_loop(
        agent_struct.id, # Jido Agent ID for logging
        chain_with_context,
        max_turns = workflow_config["max_conversation_turns"]
      )

    response_data =
      case conversation_result do
        {:ok, text_response} -> %{response: text_response} # Expected by Jido.AI.Agent.chat_response
        {:error, reason} -> %{error: inspect(reason)}
      end

    {:ok, response_data, []}
  end

  defp run_langchain_conversation_loop(
         agent_id,
         current_llm_chain,
         max_turns,
         _current_turn \\ 1, # LangChain handles turns with while_needs_response
         _accumulated_responses \\ [] # LangChain chain state has messages
       ) do
    # No explicit turn counting here as LangChain's :while_needs_response handles the loop.
    # We might add a safety net if LangChain could loop indefinitely without a result.
    # For max_turns, it's more about limiting the entire interaction sequence,
    # which :while_needs_response mode implicitly does by stopping when it has a final answer.
    # If LangChain had a max_iterations option for its tool loop, that would be ideal.
    # For now, we assume LangChain will eventually produce a final response or an error.

    Logger.info("[#{agent_id}] LangChain: Executing LLMChain.run with while_needs_response.")

    case LLMChain.run(current_llm_chain, mode: :while_needs_response, max_iterations: max_turns) do
      {:ok, final_chain_state} ->
        last_llm_message_content = final_chain_state.last_message.content

        if last_llm_message_content && String.trim(last_llm_message_content) != "" do
          Logger.info("[#{agent_id}] LangChain Final LLM Response: #{last_llm_message_content}")
          {:ok, last_llm_message_content}
        else
          Logger.warning("[#{agent_id}] LangChain: LLM provided no final text content.")
          {:ok, "[AI model provided no further text.]"}
        end

      {:error, %LangChain.LangChainError{message: error_msg, original: original_error}} = error ->
        Logger.error(
          "[#{agent_id}] LangChain Error in LLMChain.run: #{error_msg}, Original: #{inspect(original_error)}"
        )
        {:error, error}

      {:error, reason} ->
        Logger.error("[#{agent_id}] LangChain Unknown Error in LLMChain.run: #{inspect(reason)}")
        {:error, reason}
    end
  end
end


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
    Logger.info(
      "Workflow.Supervisor initializing with #{map_size(workflow_configs_map)} LangChain workflows."
    )

    children =
      Enum.map(workflow_configs_map, fn {workflow_name_str, _config_data} ->
        # Jido agent names are atoms usually, workflow_name_str is string from JSON.
        agent_registry_atom_name = String.to_atom("workflow_agent_#{workflow_name_str}")

        {McpLangchainApp.Workflow.Agent,
         [
           name: {:via, Registry, {McpLangchainApp.Workflow.Registry, agent_registry_atom_name}},
           workflow_name: workflow_name_str # Pass the string name to init/1
         ]}
      end) ++
        [
          {Registry, keys: :unique, name: McpLangchainApp.Workflow.Registry}
        ]

    Supervisor.init(children, strategy: :one_for_one)
  end
end


# lib/mcp_langchain_app/cli.exs
defmodule McpLangchainApp.CLI do
  require Logger
  alias McpLangchainApp.Workflow.Agent

  def main(args) do
    Application.ensure_all_started(:mcp_langchain_app)
    Application.ensure_all_started(:jido)
    Application.ensure_all_started(:jido_ai)
    Application.ensure_all_started(:langchain)

    parse_result =
      Optimus.new!(
        name: "mcp_cli_langchain",
        description: "Interact with MCP+LangChain Workflows via Jido.",
        version: Mix.Project.config()[:version],
        allow_unknown_args: true,
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
            help: "Name of the workflow to run (string from workflows.json).",
            required: false
          ]
        ]
      )
      |> Optimus.parse(args)

    case parse_result do
      {:ok, opts, [query | rest_query]} ->
        workflow_name_str = opts[:workflow] # This is a string
        full_query = Enum.join([query | rest_query], " ")

        if workflow_name_str && full_query != "" do
          run_single_query(workflow_name_str, full_query)
        else
          print_usage(parse_result)
        end

      {:ok, %{list_workflows: true}, _} ->
        list_workflows()

      {:ok, %{workflow: workflow_name_str}, []} when not is_nil(workflow_name_str) ->
        run_chat_loop(workflow_name_str)

      _ ->
        print_usage(parse_result)
    end
  end

  defp print_usage(parse_result_or_config) do
    config =
      if is_map(parse_result_or_config) && Map.has_key?(parse_result_or_config, :error) do
        # It's an Optimus error result
        elem(parse_result_or_config, 0).config
      else
        # Assume it's the Optimus config map itself
        parse_result_or_config
      end

    IO.puts("""
    McpLangchainApp CLI (Jido, Hermes & LangChain Version)
    """)

    Optimus.print_help(config) # Print Optimus generated help
  end

  defp list_workflows do
    workflows = Application.get_env(:mcp_langchain_app, :workflow_configs, %{})
    IO.puts("\nAvailable workflows:")

    if Map.is_empty(workflows) do
      IO.puts("  No workflows defined in config/workflows.json")
    else
      Enum.each(workflows, fn {name_str, config} ->
        IO.puts("  - #{name_str}: #{config["description"] || "No description"}")
      end)
    end
  end

  defp run_single_query(workflow_name_str, query_str) do
    IO.puts("Processing query for workflow '#{workflow_name_str}': \"#{query_str}\"")
    agent_registry_atom_name = String.to_atom("workflow_agent_#{workflow_name_str}")

    case Jido.Util.whereis({agent_registry_atom_name, McpLangchainApp.Workflow.Registry}) do
      {:ok, agent_pid} ->
        case Jido.AI.Agent.chat_response(agent_pid, query_str) do
          {:ok, %{response: response_text}, _directives} ->
            IO.puts("\nResponse:\n#{response_text}")

          {:ok, %{error: error_reason}, _directives} ->
            IO.puts("\nWorkflow Error: #{error_reason}")

          {:error, reason} ->
            IO.puts("\nError calling workflow agent: #{inspect(reason)}")

          other ->
            IO.puts("\nUnexpected response: #{inspect(other)}")
        end

      {:error, :not_found} ->
        IO.puts(
          "Error: Workflow Agent '#{workflow_name_str}' (as #{agent_registry_atom_name}) not found."
        )
    end
  end

  defp run_chat_loop(workflow_name_str) do
    agent_registry_atom_name = String.to_atom("workflow_agent_#{workflow_name_str}")

    case Jido.Util.whereis({agent_registry_atom_name, McpLangchainApp.Workflow.Registry}) do
      {:ok, agent_pid} ->
        IO.puts("\nChatting with workflow: '#{workflow_name_str}'. Type 'quit' to exit.")

        Stream.repeatedly(fn -> IO.gets("> ") |> String.trim() end)
        |> Enum.reduce_while(:ok, fn
          "quit", _ ->
            {:halt, :ok}

          "", _ ->
            {:cont, :ok} # Skip empty input

          query_str, _ ->
            case Jido.AI.Agent.chat_response(agent_pid, query_str) do
              {:ok, %{response: response_text}, _} ->
                IO.puts(response_text)

              {:ok, %{error: error_reason}, _} ->
                IO.puts("Error: #{error_reason}")

              {:error, reason} ->
                IO.puts("Error: #{inspect(reason)}")

              other ->
                IO.puts("Unexpected: #{inspect(other)}")
            end

            {:cont, :ok}
        end)

        IO.puts("Exiting chat.")

      _ ->
        IO.puts(
          "Error: Workflow Agent '#{workflow_name_str}' (as #{agent_registry_atom_name}) not found."
        )
    end
  end
end

if System.get_env("__MIX_ENV__") != "test" and System.get_env("MIX_TASK") == "run.cli" do
  McpLangchainApp.CLI.main(System.argv())
end

```
