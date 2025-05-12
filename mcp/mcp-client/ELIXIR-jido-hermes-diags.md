Okay, let's create a series of architectural diagrams visualizing your new vision, focusing specifically on the integrations and data flows involving **Hermes MCP**, **Jido**, **Jido.AI**, and **LangChain.ex**.

We'll start high-level and drill down into the specific interactions between these components.

---

### Diagram 1: High-Level System Overview

This diagram shows the main subsystems and their primary interactions for a user request involving both LLM reasoning and MCP tool use.

```mermaid
graph TD
    A["User (CLI / Web UI)"] -->|"1 Request (Query)"| B{"Phoenix Backend / Jido Controller"}
    B -->|2 Route to Workflow Agent| C["Workflow Agent Process<br>(Jido.AI.Agent / GenServer)"]

    subgraph "Core Agent Logic (Elixir)"
        C -->|3 Prepare LangChain Call| D[LangChain.ex LLMChain]
        D -->|4 LLM API Call| E["External LLM API (e.g., Gemini)"]
        E -->|"5 LLM Response (Text or Tool Call)"| D
        D -->|"6 Tool Call Request (if needed)"| C
    end

    subgraph "Tool Execution (via Hermes)"
        C -->|7 Plan & Run Tool Action| F["HermesMcpToolAction (Jido.Action)"]
        F -->|8 Lookup Hermes Client PID| G[Process Registry / Naming]
        F -->|9 Call Tool via Hermes API| H["Hermes.Client Process (GenServer)"]
        H -->|"10 Send MCP Message (JSON-RPC)"| I["External MCP Server Process (e.g., Python Script)"]
        I -->|11 Send MCP Response| H
        H -->|12 Return Tool Result| F
        F -->|13 Return Action Result| C
    end

    C -->|14 Process Tool Result / Format Final| D 
    %% Optional: Send result back to LLM via LangChain
    D -->|"15 Final LLM Response (if step 14 used)"| C
    C -->|16 Send Final Response| B
    B -->|17 Return Result to User| A

    classDef user fill:#c9f,stroke:#333,color:#000;
    classDef phoenix fill:#f9c,stroke:#333,color:#000;
    classDef agent fill:#aef,stroke:#333,color:#000;
    classDef langchain fill:#ffc,stroke:#333,color:#000;
    classDef jidoaction fill:#bfa,stroke:#333,color:#000;
    classDef hermes fill:#fdb,stroke:#333,color:#000;
    classDef external fill:#eee,stroke:#666,color:#000;

    class A user;
    class B phoenix;
    class C,G agent;
    class D langchain;
    class F jidoaction;
    class H hermes;
    class E,I external;
```

**Explanation (Level 1):**

1.  A user interacts via a CLI or Web UI, sending a request to the Phoenix backend.
2.  The backend identifies the target workflow and routes the request to the corresponding `Workflow Agent` process (a `Jido.AI.Agent`).
3.  The `Workflow Agent` prepares the interaction for the LLM using `LangChain.ex` components (`LLMChain`, `Messages`).
4.  `LLMChain` calls the external LLM API (e.g., Gemini via `ChatGoogle`).
5.  The LLM API responds, either with a direct textual answer or a request to use a tool.
6.  If a tool is requested, `LLMChain` passes this back to the `Workflow Agent` (or handles it internally depending on `mode`).
7.  The `Workflow Agent` identifies the correct `Jido.Action` (`HermesMcpToolAction`) configured for the specific MCP tool requested. It plans and executes this action.
8.  `HermesMcpToolAction` needs the PID of the `Hermes.Client` responsible for the target MCP server. It looks this up (e.g., via `Process.whereis` using a known registration name).
9.  The action calls the `Hermes.Client` API (e.g., `Hermes.Client.call_tool/3`).
10. `Hermes.Client` formats the request according to the Hermes MCP specification and sends it to the external MCP server process via the configured transport (stdio, SSE, etc.).
11. The external MCP server processes the request and sends back an MCP response.
12. `Hermes.Client` receives, parses the response, and returns the result to the `HermesMcpToolAction`.
13. The `HermesMcpToolAction` formats the result and returns it to the `Workflow Agent`.
14. The `Workflow Agent` adds the tool result to the conversation history and may send it back to the LLM via `LLMChain` for summarization or further reasoning.
15. The LLM provides a final response (if step 14 occurred).
16. The `Workflow Agent` sends the final response back to the Phoenix backend.
17. The backend returns the result to the user.

---

### Diagram 2: Elixir OTP Supervision Tree

This diagram shows how the core components are supervised within the Elixir application.

```mermaid
graph TD
    App[McpLangchainApp.Application] --> MainSup{"McpLangchainApp.MainSupervisor<br>(one_for_one)"}

    MainSup --> Keyring["Jido.AI.Keyring<br>(GenServer)"]
    MainSup --> Config["McpLangchainApp.ConfigLoader<br>(GenServer)"]
    MainSup --> HermesSup{"McpLangchainApp.HermesClientSupervisor<br>(one_for_one)"}
    MainSup --> WorkflowSup{"cpLangchainApp.Workflow.Supervisor<br>(one_for_one)"}

    HermesSup -->|Starts & Supervises| HC1["Hermes.Client (ToolServerA)<br>(GenServer)"]
    HermesSup -->|Starts & Supervises| HC2["Hermes.Client (ToolServerB)<br>(GenServer)"]
    HermesSup -->|...| HCN[...]

    WorkflowSup --> WorkflowReg["McpLangchainApp.Workflow.Registry<br>(Registry)"]
    WorkflowSup -->|Starts & Supervises| WA1["WorkflowAgent (Workflow1)<br>(Jido.AI.Agent / GenServer)"]
    WorkflowSup -->|Starts & Supervises| WA2["WorkflowAgent (Workflow2)<br>(Jido.AI.Agent / GenServer)"]
    WorkflowSup -->|...| WAN[...]

    WA1 -->|Registers with| WorkflowReg
    WA2 -->|Registers with| WorkflowReg

    style App fill:#6c9,stroke:#333,color:#000;
    style MainSup fill:#9cf,stroke:#333,color:#000;
    style Keyring fill:#fc9,stroke:#333,color:#000;
    style Config fill:#fc9,stroke:#333,color:#000;
    style HermesSup fill:#9cf,stroke:#333,color:#000;
    style WorkflowSup fill:#9cf,stroke:#333,color:#000;
    style HC1,HC2,HCN fill:#fdb,stroke:#333,color:#000;
    style WorkflowReg fill:#ccc,stroke:#333,color:#000;
    style WA1,WA2,WAN fill:#aef,stroke:#333,color:#000;
```

**Explanation (Level 2):**

*   The main OTP `Application` starts the `MainSupervisor`.
*   `MainSupervisor` starts and supervises critical singleton components (`Keyring`, `ConfigLoader`) and the main service supervisors (`HermesClientSupervisor`, `Workflow.Supervisor`). A `one_for_one` strategy is common here.
*   `HermesClientSupervisor` uses a `one_for_one` strategy to manage individual `Hermes.Client` processes. Each client connects to a specific external MCP server configured in `config.exs`. If one client crashes, only it is restarted.
*   `Workflow.Supervisor` uses a `one_for_one` strategy to manage the actual `WorkflowAgent` processes. It also typically starts a `Registry` for naming and discovering these agents. Each agent represents a defined workflow (e.g., from `workflows.json`).

---

### Diagram 3: Workflow Agent - LangChain.ex Integration Detail

This sequence diagram focuses on how the `WorkflowAgent` uses `LangChain.ex` to interact with the LLM and handle tool calls initiated by the LLM.

```mermaid
graph TD
    subgraph UserInteraction ["User Interaction Context"]
        direction TB
        UserInput["User Query (via Signal)"]
        AgentResponse["Agent Response (to Caller)"]
    end

    subgraph WorkflowAgentProcess ["WorkflowAgent Process (Jido.AI.Agent / GenServer)"]
        direction TB
        AgentState["Agent State<br>(workflow_config, llm_chain_instance, available_lc_tools)"]
        AgentLogic["Agent Logic<br>(handle_signal, prepare_messages, format_response)"]
        ToolDiscovery["Tool Discovery<br>(Loads MCP tool defs -> LangChain.Function structs)"]
    end

    subgraph LangChainExecution ["LangChain.ex Execution Context"]
        direction TB
        LLMChain["LLMChain Instance<br>(Manages state, runs logic)"]
        Messages["LangChain.Message History"]
        LCFunctions["Collection of LangChain.Function<br>(Wrappers for HermesMcpToolAction)"]
        ChatModel["ChatGoogle Instance<br>(Interface to LLM API)"]
    end

    subgraph ExternalServices ["External Services"]
        direction TB
        ExtLLM["External LLM API (e.g., Gemini)"]
        ToolExecution["Tool Execution Flow<br>(via HermesMcpToolAction - See Diagram 4)"]
    end

    UserInput --> AgentLogic
    AgentLogic --> AgentState
    AgentState --> AgentLogic
    AgentLogic --> LLMChain  

    LLMChain -- Uses --> AgentState  
    LLMChain -- Manages --> Messages
    LLMChain -- Uses --> LCFunctions  

    ToolDiscovery -- Populates --> AgentState 
    AgentState -- Provides tools --> LLMChain  

    LLMChain -- Uses --> ChatModel
    ChatModel -- Calls --> ExtLLM
    ExtLLM -- Returns response --> ChatModel
    ChatModel -- Returns result --> LLMChain

    LLMChain -- Invokes --> LCFunctions  
    LCFunctions -- Triggers --> ToolExecution 

    ToolExecution -- Returns result --> LCFunctions  
    LCFunctions -- Returns result --> LLMChain  

    LLMChain -- Updates --> Messages  
    LLMChain -- Returns Final State --> AgentLogic

    AgentLogic -- Formats --> AgentResponse

    classDef user fill:#c9f,stroke:#333,color:#000;
    classDef agent fill:#aef,stroke:#333,color:#000;
    classDef agentState fill:#dcf,stroke:#333,stroke-dasharray: 5 5,color:#000;
    classDef langchain fill:#ffc,stroke:#333,color:#000;
    classDef external fill:#eee,stroke:#666,color:#000;
    classDef toolExecution fill:#bfa,stroke:#333,color:#000;

    class UserInput,AgentResponse user;
    class AgentState,AgentLogic,ToolDiscovery agent;
    class LLMChain,Messages,LCFunctions,ChatModel langchain;
    class ExtLLM external;
    class ToolExecution toolExecution;
```

**Explanation (Level 3):**

1.  The `WorkflowAgent` receives the user query.
2.  It prepares the initial list of `LangChain.Message` structs.
3.  It retrieves the pre-configured list of `LangChain.Function` structs (`available_langchain_mcp_tools`) representing the MCP tools for this workflow. Each of these structs points to `&HermesMcpToolAction.run/2` as its execution function and contains the specific context (`hermes_client_id`, `mcp_tool_name`) needed by `run/2`.
4.  It adds the messages and tools to its `LLMChain` instance.
5.  It calls `LLMChain.run` with `mode: :while_needs_response`.
6.  `LLMChain` internally calls the `ChatModel` (e.g., `ChatGoogle`).
7.  `ChatModel` makes the actual API call to the LLM.
8.  The LLM responds, potentially requesting a tool call.
9.  `LLMChain` receives the response. If a tool is requested, it finds the matching `LangChain.Function` (`LcFunc`) from the tools added earlier.
10. `LLMChain` invokes the `.function` field of the `LangChain.Function` struct, which is `&HermesMcpToolAction.run/2`, passing the arguments extracted from the LLM response and the `context` stored in the `LangChain.Function` struct.
11. `HermesMcpToolAction.run/2` executes the actual tool call via Hermes (detailed in Diagram 4) and returns the result (`{:ok, content}` or `{:error, reason}`) back to `LLMChain`.
12. `LLMChain` formats this result as a `LangChain.Message` (tool result role) and adds it to the conversation history.
13. `LLMChain` calls the `ChatModel` again with the updated history.
14. The LLM responds with the final text answer.
15. `LLMChain` receives this final response. Since no more tools are requested, the `:while_needs_response` loop completes.
16. `LLMChain` returns the final state (`{:ok, final_chain_state}`) to the `WorkflowAgent`.
17. The `WorkflowAgent` extracts the final textual answer and sends it back to the original caller.

---

### Diagram 4: Hermes MCP Tool Execution Detail

This sequence diagram drills down into step 10/11 of Diagram 3, showing how `HermesMcpToolAction` interacts with `Hermes.Client`.

```mermaid
graph TD
    subgraph LangChainContext ["LangChain Runtime Context"]
        direction TB
        LCExec["LLMChain Execution Logic"]
        LCFunction["LangChain.Function Struct<br>(name, desc, schema, function: &HAction.run/2, context: {hc_id, tool_name})"]
    end

    subgraph ElixirHermesAction ["Elixir Process (Executing Tool Action)"]
        direction TB
        HActionRun["HermesMcpToolAction.run/2<br>(Receives params, context)"]
        PIDLookup["PID Lookup Logic"]
        HermesAPICall["Hermes.Client API Call<br>(call_tool/3)"]
    end

    subgraph ElixirHermesClient ["Elixir Process (Hermes Client)"]
        direction TB
        HClientProcess["Hermes.Client GenServer"]
        HClientState["Hermes.Client State<br>(config, transport_ref, requests)"]
        HClientLogic["handle_call / handle_info<br>(Formats JSON-RPC, Manages Transport)"]
        HTransport["Hermes Transport Module<br>(e.g., Hermes.Transport.STDIO)"]
    end

    subgraph ProcessManagement ["Elixir OTP Infrastructure"]
        direction TB
        Registry["Process Registry"]
        PortDriver["Port Driver (if stdio)"]
    end

    subgraph ExternalProcess ["External MCP Server Process"]
        direction TB
        ExtMCP["External MCP Server<br>(e.g., Python Script)"]
    end

    LCExec -- Invokes function --> HActionRun
    LCFunction -- Provides context --> HActionRun 
    LCFunction -- Provides args (params) --> HActionRun

    HActionRun -- Uses --> PIDLookup
    PIDLookup -- Looks up --> Registry 
    Registry -- Returns PID --> PIDLookup
    PIDLookup -- Returns PID --> HActionRun

    HActionRun -- Makes call --> HermesAPICall
    HermesAPICall -- Sends GenServer.call --> HClientProcess

    HClientProcess -- Uses --> HClientState
    HClientProcess -- Executes --> HClientLogic
    HClientLogic -- Uses --> HClientState
    HClientLogic -- Uses --> HTransport
    HTransport -- Interacts with --> PortDriver

    PortDriver -- Communicates (stdin/stdout) --> ExtMCP
    ExtMCP -- Communicates (stdout/stdin) --> PortDriver

    PortDriver -- Delivers response --> HClientProcess
    HClientProcess -- Replies to call --> HermesAPICall
    HermesAPICall -- Returns result --> HActionRun

    HActionRun -- Formats result --> LCExec 

    classDef langchain fill:#ffc,stroke:#333,color:#000;
    classDef action fill:#bfa,stroke:#333,color:#000;
    classDef hermes fill:#fdb,stroke:#333,color:#000;
    classDef otp fill:#ccc,stroke:#666,color:#000;
    classDef external fill:#eee,stroke:#666,color:#000;

    class LCExec,LCFunction langchain;
    class HActionRun,PIDLookup,HermesAPICall action;
    class HClientProcess,HClientState,HClientLogic,HTransport hermes;
    class Registry,PortDriver otp;
    class ExtMCP external;
```

**Explanation (Level 4):**

1.  `LLMChain` invokes `HermesMcpToolAction.run/2`.
2.  The action extracts the target `hermes_client_id` (atom) and `mcp_tool_name` (string) from the context passed by `LangChain.Function`.
3.  It uses `Process.whereis/1` with the expected registration name (`{Hermes.Client, hermes_client_id}`) to find the PID of the correct `Hermes.Client` GenServer.
4.  It calls the public API function `Hermes.Client.call_tool/3`.
5.  This triggers the `handle_call` callback inside the `Hermes.Client` GenServer.
6.  The `Hermes.Client` creates a unique request ID, stores the caller (`HAction`'s process), formats the MCP JSON-RPC `call_tool` request payload according to Hermes spec.
7.  It sends the payload via the appropriate `Hermes.Transport` mechanism (e.g., `Port.command`).
8.  The transport delivers the message to the external MCP server process.
9.  The external MCP server executes the tool and sends back a standard MCP JSON-RPC response.
10. The transport delivers the response back to the `Hermes.Client` process (e.g., via `handle_info` for a Port).
11. `Hermes.Client` parses the response, matches it to the original request using the ID, and extracts the result or error.
12. `Hermes.Client` replies to the original `GenServer.call` from `HAction` with a structured `Hermes.MCP.Response` or error tuple.
13. `HAction` receives the reply.
14. It formats the result into the `{:ok, content}` or `{:error, reason}` format expected by LangChain.ex's `Function` execution logic.
15. It returns this formatted result to the `LLMChain` runtime.

---

These diagrams illustrate the flow of control and data, emphasizing how Jido, Jido.AI, LangChain.ex, and Hermes MCP integrate within an Elixir/OTP architecture to create your advanced AI assistant.
