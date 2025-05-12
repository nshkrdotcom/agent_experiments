Okay, this is a great exercise! Redesigning this *simpler* Python system using OTP principles will highlight how Elixir's concurrency and supervision model can inherently provide robustness even for less complex applications.

The Python system has a clear `WorkflowEngine` that orchestrates `LLMService` and `MCPService` instances based on configuration. We'll map these to OTP components.

## Project Name: `FlowBeam` (or `SimpleBeamAgent`)

**Core Idea:**
Each distinct "service" (`MCPService` per server, `LLMService` per LLM type) will be a `GenServer`. Each active user interaction with a "workflow" will also be a `GenServer` (`WorkflowInstance`), which holds the conversation state and orchestrates calls to the service `GenServer`s.

---

### 1. High-Level System Architecture

```
+------------------------+      +---------------------------+
| Phoenix Web Interface  |----->|  FlowBeam.Application     |
| (API / Channels for    |<-----|   (OTP Application)       |
| user interaction)      |      +---------------------------+
+------------------------+                |
                                         v
                                +---------------------------+
                                | FlowBeam.CoreSupervisor   |
                                +---------------------------+
                                  |          |           |
                                  v          v           v
                      +---------------+ +-----------------+ +------------------------+
                      | FlowBeam.Config | | FlowBeam.Service| | FlowBeam.Workflow      |
                      | (GenServer for  | | .Supervisor     | | .Supervisor            |
                      | config access)  | +-----------------+ +------------------------+
                      +---------------+          |                       | (DynamicSupervisor)
                                                 v                       v
                                    +-----------------------+   +------------------------+
                                    | FlowBeam.MCP.Manager  |   | WorkflowInstanceProcess|
                                    | (DynamicSupervisor)   |   | (GenServer, one per    |
                                    +-----------------------+   |  active user workflow) |
                                            |                     +------------------------+
                                            v                             |  |  ^
                               +-------------------------+                |  v  |
                               | FlowBeam.MCP.Connection |----------------|     | Calls Services
                               | (GenServer, one per     |<---------------|
                               | configured MCP Server)  |
                               +-------------------------+
                                         |
                                         v
                               +-------------------------+
                               | External MCP Tool       |
                               | (Managed via Port)      |
                               +-------------------------+

                                (LLMService would be a similar supervised GenServer
                                 or a simple module if state/pooling is not complex)
```

---

### 2. Configuration (`FlowBeam.Config`)

*   **Module:** `FlowBeam.Config`
*   **Type:** `GenServer` (supervised by `FlowBeam.CoreSupervisor`).
*   **Responsibilities:**
    *   On `init`, loads `mcp_servers.json` and `workflows.json` (or their Elixir equivalents, e.g., from `config.exs` or dedicated `.exs` files).
    *   Stores the configurations in its state (or an ETS table for very frequent access, though GenServer state is likely fine for this scale).
    *   Provides `handle_call` functions to retrieve:
        *   Specific MCP server configuration by name.
        *   Specific workflow configuration by name.
        *   Google API key (fetched from environment variables on init or by a function).
*   **Logging:** Uses `Logger.info` on successful load, `Logger.error` on failures.

---

### 3. MCP Service Management (`FlowBeam.MCP.*`)

*   **Supervisor:** `FlowBeam.MCP.Supervisor` (a `Supervisor` under `FlowBeam.Service.Supervisor`).
    *   Manages `FlowBeam.MCP.Connection` processes using a `DynamicSupervisor` strategy (or one-for-one if all known MCP servers are started at app boot).
*   **Connection Process:** `FlowBeam.MCP.Connection` (`GenServer`).
    *   **`start_link(server_name, server_config)`:** Called by the `WorkflowInstanceProcess` when it needs this MCP server, or by the `MCP.Supervisor` at app start.
    *   **State:** `server_name`, `server_config`, `port` (the Elixir Port to the external MCP server process), `mcp_session_state` (if managing sequence IDs or other session details; an actual MCP client library in Elixir would handle this internally).
    *   **`init/1`:**
        *   Receives `server_name` and `server_config`.
        *   Registers itself with `FlowBeam.Registry` (an Elixir `Registry` for PIDs by name, supervised by `CoreSupervisor`).
        *   Opens an Elixir `Port` to execute `server_config["command"]` with `server_config["args"]`. Stdout/Stderr of the port are handled for JSON-RPC.
        *   Sends the MCP `initialize` call to the external process.
        *   Logs connection attempt and success/failure.
    *   **API (`handle_call`):**
        *   `{:list_tools, caller}`: Sends `tools/list` via Port, awaits response, replies to `caller`.
        *   `{:call_tool, tool_name, args, caller}`: Sends `tools/call` via Port, awaits response, replies to `caller`.
    *   **Fault Tolerance:** If the `Port` crashes, the `MCP.Connection` GenServer can be restarted by its supervisor, which would re-attempt to start the external process.

---

### 4. LLM Service (`FlowBeam.LLM.GoogleGenAI`)

*   **Module:** `FlowBeam.LLM.GoogleGenAI`
*   **Type:** Can be a simple module if the Elixir Google GenAI library handles its own state/client lifecycle, OR a `GenServer` if we need to manage an API key, pooling, or rate limiting. For simplicity similar to the Python, a module is often sufficient initially.
    *   If it becomes stateful (e.g., managing a pool of Finch HTTP clients):
        *   Supervised by `FlowBeam.LLM.Supervisor` (under `FlowBeam.Service.Supervisor`).
        *   **State:** `api_key`, `model_name_default`, Finch pool reference.
        *   **`init/1`:** Gets API key from `FlowBeam.Config` or environment.
*   **Functions/API (`handle_call` if GenServer):**
    *   `prepare_tools_for_llm(mcp_tools :: list(MCP.Tool.t())) :: GenAI.GenerateContentConfig.t() | nil`
        *   Takes a list of Elixir structs representing `MCP.Tool`.
        *   Converts them to the `FunctionDeclaration` format expected by Google GenAI.
        *   Returns a `GenAI.Types.GenerateContentConfig` struct or `nil`.
    *   `generate_response(conversation_history :: list(GenAI.Types.Content.t()), tool_config :: GenAI.GenerateContentConfig.t() | nil) :: {:ok, GenAI.Types.GenerateContentResponse.t()} | {:error, any()}`
        *   Uses an Elixir Google GenAI client library (e.g., `google_gax`, `ex_google_api_producer_portal`) or direct HTTP calls (using Finch/Tesla) to call the Gemini API.
*   **Logging:** Uses `Logger.info/debug/error` for operations.

---

### 5. Workflow Engine (`FlowBeam.Workflow.*`)

*   **Supervisor:** `FlowBeam.Workflow.Supervisor` (a `DynamicSupervisor` under `FlowBeam.CoreSupervisor`).
    *   Starts `FlowBeam.Workflow.InstanceProcess` GenServers on demand.
*   **Instance Process:** `FlowBeam.Workflow.InstanceProcess` (`GenServer`).
    *   One instance is spawned for each user query that needs to be processed by a specific workflow. This allows concurrent, isolated workflow executions.
    *   **`start_link(workflow_name, initial_user_query, reply_to_pid_or_channel)`:**
        *   `reply_to_pid_or_channel`: The PID of the calling process (e.g., a Phoenix Channel process, or another GenServer) to which the final answer should be sent.
    *   **State:**
        *   `workflow_name :: atom()`
        *   `workflow_config :: map()` (fetched from `FlowBeam.Config` on init)
        *   `llm_service_module_or_pid :: atom() | pid()`
        *   `mcp_services_pids :: map()` (map of `server_name_atom => mcp_connection_pid`)
        *   `all_mcp_tools :: list()` (list of `MCP.Tool.t()` structs, gathered on init)
        *   `conversation_history :: list()` (list of `GenAI.Types.Content` structs)
        *   `reply_to :: pid() | {atom(), any()}` (for replying to channel/process)
    *   **`init/1 ({workflow_name, initial_user_query, reply_to})`:**
        1.  Fetches `workflow_config` and `google_api_key` from `FlowBeam.Config`.
        2.  Initializes `llm_service_module_or_pid`.
        3.  For each `server_name` in `workflow_config["mcp_servers_used"]`:
            *   Asks `FlowBeam.MCP.Supervisor` (or directly looks up in `Registry` if started globally) to start/get the `FlowBeam.MCP.Connection` GenServer for that `server_name`. Stores the PID.
            *   Calls `FlowBeam.MCP.Connection.list_tools` for each service and aggregates them into `all_mcp_tools`.
        4.  Constructs the initial prompt using `initial_prompt_template` and `initial_user_query`.
        5.  Initializes `conversation_history` with the first user message.
        6.  Sends `{:continue_processing}` message to `self()` to start the ReAct loop.
        7.  Logs initialization.
    *   **`handle_info({:continue_processing}, state)` (implements the ReAct loop):**
        1.  `tool_config = FlowBeam.LLM.GoogleGenAI.prepare_tools_for_llm(state.all_mcp_tools)`
        2.  `{:ok, llm_response} | {:error, reason} = FlowBeam.LLM.GoogleGenAI.generate_response(state.conversation_history, tool_config)`
        3.  Handle LLM response:
            *   Append `llm_response.candidates[0].content` to `state.conversation_history`.
            *   Extract text parts and function calls.
            *   Log text parts to user via `reply_to` (if interactive).
            *   **If function call:**
                *   Find `mcp_service_pid` from `state.mcp_services_pids`.
                *   `GenServer.call(mcp_service_pid, {:call_tool, tool_name, tool_args})`.
                *   Convert MCP tool result to `GenAI.Types.Part.from_function_response`.
                *   Append this tool response to `state.conversation_history`.
                *   Send `{:continue_processing}` to `self()`.
            *   **If no function call (final text response):**
                *   Send final text response to `reply_to`.
                *   `{:stop, :normal, new_state}` (terminates this GenServer instance).
            *   Handle max turns or errors by stopping and replying with error/status.
    *   **Fault Tolerance:** If an `MCP.Connection` process it's using crashes, this `WorkflowInstanceProcess` might receive an error or timeout. It can log this and terminate, or attempt a retry based on its workflow config. If this process itself crashes, its supervisor will handle it (e.g., log and give up for a single user query).

---

### 6. Logging (`Logger` and `FlowBeam.Logger`)

*   Utilize Elixir's standard `Logger`.
*   The `app_logger.py` structure can be mapped to:
    *   Setting `Logger` level in `config/config.exs`.
    *   Custom `Logger` backend for the console to achieve "quiet", "user", "normal", "verbose" by filtering metadata or log levels.
    *   `Logger.Formatter` can customize log line appearance.
    *   `Config.CONFIG_LOGGER` becomes `Logger.debug/info/error/warn` calls within the `FlowBeam.Config` module, potentially with `[source: :config]` metadata. Similarly for `:service`, `:engine`, `:cli`.
    *   The custom log level `LOG_LEVEL_USER_INTERACTION` can be implemented by logging at `Logger.info` but with specific metadata, e.g., `[type: :user_interaction]`, which the console backend can then format differently or be the sole message type displayed for the "user" level.

---

### 7. CLI / Entry Point (`mix flow_beam.run`)

*   A Mix task (e.g., `mix flow_beam.run my_workflow --query "..."`) would replace `cli.py`.
*   The Mix task would:
    *   Parse command-line arguments.
    *   Start the `FlowBeam.Application` if not already running (or connect to a running instance if designed for that).
    *   Call `DynamicSupervisor.start_child(FlowBeam.Workflow.Supervisor, {FlowBeam.Workflow.InstanceProcess, {workflow_name, query, self()}})` to start a workflow instance.
    *   Wait for a reply from the spawned `WorkflowInstanceProcess`.
    *   Print the final response.
    *   For an interactive loop, the Mix task could itself become a `GenServer` or manage a loop, repeatedly spawning `WorkflowInstanceProcess` GenServers per query.

---

### 8. Phoenix Integration (Example for a web-based chat)

*   **`FlowBeamWeb.ChatChannel`:**
    *   User joins channel, `handle_in("start_workflow", %{"workflow_name" => name}, socket)`.
    *   Channel process calls `DynamicSupervisor.start_child(FlowBeam.Workflow.Supervisor, {FlowBeam.Workflow.InstanceProcess, {workflow_name, "User connected.", self()}})` to start a workflow. It stores the PID of the `WorkflowInstanceProcess` in the socket assigns.
    *   User sends message `handle_in("user_message", %{"text" => text}, socket)`.
    *   Channel process sends `GenServer.cast(workflow_pid, {:user_input, text})`.
    *   `FlowBeam.Workflow.InstanceProcess` on `handle_cast({:user_input, text}, state)`:
        *   Adds user input to its `conversation_history`.
        *   Sends `{:continue_processing}` to `self()`.
    *   When `WorkflowInstanceProcess` has intermediate (LLM text) or final responses, it sends a message back to the `ChatChannel` PID, e.g., `send(channel_pid, {:workflow_update, text_part})`.
    *   `ChatChannel`'s `handle_info({:workflow_update, text_part}, socket)` pushes the text to the client.
    *   On channel close, it can `GenServer.stop(workflow_pid)`.

---

### High-Level Diagram: Workflow Instance Processing Loop

```mermaid
sequenceDiagram
    participant UserViaPhoenixChannel
    participant WorkflowInstance (GenServer)
    participant ConfigService (GenServer)
    participant MCPConnection_A (GenServer)
    participant MCPConnection_B (GenServer)
    participant LLMService (Module/GenServer)
    participant ExternalGeminiAPI
    participant ExternalMCP_A
    participant ExternalMCP_B

    UserViaPhoenixChannel->>WorkflowInstance: User Query ("Tell me about X using tool_from_A and tool_from_B")
    WorkflowInstance->>ConfigService: Get Workflow Config for 'self.workflow_name'
    ConfigService-->>WorkflowInstance: Workflow Config (LLM model, MCP servers to use, initial prompt)
    WorkflowInstance->>WorkflowInstance: tools_a = GenServer.call(MCPConn_A, :list_tools)
    WorkflowInstance->>WorkflowInstance: tools_b = GenServer.call(MCPConn_B, :list_tools)
    WorkflowInstance->>WorkflowInstance: self.all_mcp_tools = tools_a ++ tools_b

    loop ReAct Cycle (Max N Turns)
        WorkflowInstance->>LLMService: prepare_tools_for_llm(self.all_mcp_tools)
        LLMService-->>WorkflowInstance: genai_tool_config

        WorkflowInstance->>LLMService: generate_response(self.history, genai_tool_config)
        LLMService->>ExternalGeminiAPI: HTTP Call
        ExternalGeminiAPI-->>LLMService: LLM Response (Text or FunctionCall)
        LLMService-->>WorkflowInstance: Parsed LLM Response

        WorkflowInstance->>WorkflowInstance: Update self.history (with LLM model turn)
        WorkflowInstance-->>UserViaPhoenixChannel: Push LLM Text Part (if any)

        alt LLM requests Function Call (e.g., tool_from_A)
            WorkflowInstance->>MCPConnection_A: GenServer.call(:call_tool, "tool_name_A", args)
            MCPConnection_A->>ExternalMCP_A: JSON-RPC via Port
            ExternalMCP_A-->>MCPConnection_A: Tool Result
            MCPConnection_A-->>WorkflowInstance: Tool Output for tool_from_A
            WorkflowInstance->>WorkflowInstance: Update self.history (with "user" role and tool output part)
            WorkflowInstance-->>UserViaPhoenixChannel: Push Tool Execution Info
        else No Function Call (Final Answer)
            WorkflowInstance-->>UserViaPhoenixChannel: Push Final Answer
            WorkflowInstance->>WorkflowInstance: Terminate self
            break
        end
    end
    WorkflowInstance-->>UserViaPhoenixChannel: Push "Max turns reached" or final error.
```

This simpler design focuses on the core components and maps them directly to OTP behaviours. It relies on Elixir's built-in Registry for service discovery and `DynamicSupervisor`s for managing lifecycles of on-demand processes like `MCPConnection`s and `WorkflowInstanceProcess`es. This already gives a lot of the "OTP goodness" without the more complex abstractions of the full `fast-agent` design.
