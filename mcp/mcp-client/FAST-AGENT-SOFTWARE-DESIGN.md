Okay, let's break down the `fast-agent` software design through a series of Mermaid diagrams, starting from a high level and drilling down.

## Diagram Series: Fast-Agent Software Design

### 1. Level 1: High-Level System Architecture

This diagram shows the major components of the Fast-Agent ecosystem and how they relate to each other and external services.

```mermaid
graph TD
    subgraph UserInteraction["User Interaction"]
        direction LR
        CLI["CLI (fast-agent go/setup/...)"]
        PythonScript["User Python Script (e.g., examples/*.py)"]
    end

    subgraph FastAgentAppCore["FastAgent Application Core"]
        direction TB
        FastAgentFacade["FastAgent Facade (@fast.agent decorators)"]
        MCPAppCore["MCPApp Core (Manages Context & Lifecycle)"]
        ContextCore["Context (Global State, Config, Registries)"]
        AgentRegistry["Agent/Workflow Registry (User Definitions)"]
        LLMIntegration["LLM Integration (AugmentedLLM & Providers)"]
        MCPServerIntegration["MCP Server Integration (MCPAggregator & ConnectionManager)"]
        Executor["Async Executor (Task Runner)"]
    end

    subgraph Configuration["Configuration"]
        direction TB
        ConfigFile["fastagent.config.yaml"]
        SecretsFile["fastagent.secrets.yaml"]
        EnvVars["Environment Variables"]
    end

    subgraph ExternalServices["External / Pluggable Services"]
        direction TB
        LLMProviders["LLM Providers (OpenAI, Anthropic, etc.)"]
        MCPServers["MCP Servers (Filesystem, Fetch, Interpreter, Custom)"]
        LoggingTelemetry["Logging & Telemetry (OTEL, File/Console Logger)"]
    end

    UserInteraction --> FastAgentFacade
    FastAgentFacade --> MCPAppCore
    MCPAppCore --> ContextCore
    ContextCore --> AgentRegistry
    ContextCore --> LLMIntegration
    ContextCore --> MCPServerIntegration
    ContextCore --> Executor

    Configuration --> ContextCore

    LLMIntegration --> LLMProviders
    MCPServerIntegration --> MCPServers
    ContextCore --> LoggingTelemetry

    classDef userInteraction fill:#c9f,stroke:#333,stroke-width:2px,color:#000;
    classDef appCore fill:#9cf,stroke:#333,stroke-width:2px,color:#000;
    classDef configFiles fill:#f9c,stroke:#333,stroke-width:2px,color:#000;
    classDef externalSvc fill:#cf9,stroke:#333,stroke-width:2px,color:#000;

    class CLI,PythonScript userInteraction;
    class FastAgentFacade,MCPAppCore,ContextCore,AgentRegistry,LLMIntegration,MCPServerIntegration,Executor appCore;
    class ConfigFile,SecretsFile,EnvVars configFiles;
    class LLMProviders,MCPServers,LoggingTelemetry externalSvc;
```

**Explanation (Level 1):**

*   **User Interaction**: Users interact with the system either via the CLI or by writing Python scripts that utilize the `FastAgent` framework.
*   **FastAgent Application Core**: This is the heart of the system.
    *   `FastAgent Facade`: The primary interface for developers (e.g., using `@fast.agent` decorators).
    *   `MCPApp Core`: Manages the application lifecycle and the central `Context`.
    *   `Context`: Holds global state like configuration, server/task registries, and the executor.
    *   `Agent/Workflow Registry`: Stores definitions of agents and workflows provided by the user.
    *   `LLM Integration`: Handles communication with various LLM providers through an `AugmentedLLM` abstraction.
    *   `MCP Server Integration`: Manages connections and interactions with MCP (Model Context Protocol) servers.
    *   `Async Executor`: Responsible for running asynchronous tasks.
*   **Configuration**: The system's behavior is configured through YAML files (`fastagent.config.yaml` for general settings, `fastagent.secrets.yaml` for sensitive data) and environment variables.
*   **External / Pluggable Services**:
    *   `LLM Providers`: External services like OpenAI, Anthropic, etc., that provide language model capabilities.
    *   `MCP Servers`: These can be external services or locally run processes (like the Python interpreter or filesystem server examples) that expose tools, resources, or prompts via MCP.
    *   `Logging & Telemetry`: Systems for logging application events and (optionally) collecting telemetry data (e.g., OpenTelemetry).

### 2. Level 2: FastAgent Application Core - Internal Structure

This diagram drills into the `FastAgent Application Core`, showing how its main internal components are structured and interact.

```mermaid
graph LR
    subgraph UserCode ["User Code (e.g., agent.py)"]
        direction TB
        DefineAgent["@fast.agent(...) def my_agent(): ..."]
        DefineWorkflow["@fast.orchestrator(...) def my_workflow(): ..."]
    end

    subgraph FastAgentFramework["FastAgent Framework"]
        direction TB
        FastAgentFacade["FastAgent(name, config_path)"] -- Manages --> AgentConfigsDict["AgentConfigsDict {name: config_data}"]
        FastAgentFacade -- Creates & Runs --> MCPAppInstance["MCPApp Instance"]

        MCPAppInstance -- Owns --> AppContext["Context"]
        subgraph ContextDetails ["Context Internals"]
            direction TB
            AppContext -- Holds --> SettingsObj["Settings (from config files)"]
            AppContext -- Holds --> ServerRegistryObj["ServerRegistry"]
            AppContext -- Holds --> TaskRegistryObj["TaskRegistry (for executor)"]
            AppContext -- Holds --> ExecutorInstance["Executor (AsyncioExecutor)"]
            AppContext -- Holds --> HumanInputHandler["HumanInputHandler (optional)"]
            AppContext -- Holds --> LoggerInstance["Logger"]
            AppContext -- Holds --> OTELTracer["OTEL Tracer (optional)"]
        end

        FastAgentFacade -- "Uses during fast.run()" --> AgentFactory["Agent Factory (create_agents_in_dependency_order)"]
        AgentFactory -- Uses --> AgentConfigsDict
        AgentFactory -- Uses --> ModelFactory["ModelFactory"]
        AgentFactory -- Creates & Initializes --> ActiveAgents["Active Agents (Agent, OrchestratorAgent, etc.)"]
        ModelFactory -- Creates --> LLMFactories["Provider-Specific LLM Factories"]
        LLMFactories -- Used by AgentFactory to create --> LLMInstances["AugmentedLLM Instances"]
        ActiveAgents -- "Each Agent/Workflow has an" --> LLMInstances
        ActiveAgents -- "Each Agent/Workflow can use an" --> MCPAggregatorInstance["MCPAggregator"]

        MCPAppInstance -- "Yields from fast.run()" --> RuntimeAgentApp["AgentApp (Runtime Wrapper)"]
        RuntimeAgentApp -- Provides access to --> ActiveAgents
    end

    DefineAgent --> FastAgentFacade
    DefineWorkflow --> FastAgentFacade

    classDef userCode fill:#c9f,stroke:#333,stroke-width:2px,color:#000;
    classDef framework fill:#9cf,stroke:#333,stroke-width:2px,color:#000;
    classDef runtime fill:#9fc,stroke:#333,stroke-width:2px,color:#000;
    classDef contextInternals fill:#aec,stroke:#333,color:#000,stroke-width:1px,stroke-dasharray: 5 5;

    class DefineAgent,DefineWorkflow userCode;
    class FastAgentFacade,AgentConfigsDict,MCPAppInstance,AppContext,AgentFactory,ModelFactory,LLMFactories framework;
    class SettingsObj,ServerRegistryObj,TaskRegistryObj,ExecutorInstance,HumanInputHandler,LoggerInstance,OTELTracer contextInternals;
    class ActiveAgents,LLMInstances,MCPAggregatorInstance,RuntimeAgentApp runtime;
```

**Explanation (Level 2):**

*   **User Code**: Developers define agents and workflows using decorators (`@fast.agent`, `@fast.orchestrator`, etc.) on functions.
*   **FastAgent Framework**:
    *   The `FastAgent` instance acts as a facade. It collects configurations from these decorators into an `AgentConfigsDict`.
    *   When `fast.run()` is called, it creates an `MCPApp Instance`.
    *   The `MCPApp` owns the central `Context`, which holds:
        *   `Settings`: Parsed configuration from YAML files and environment variables.
        *   `ServerRegistry`: Manages configurations and connections for MCP servers.
        *   `TaskRegistry`: Used by the `Executor`.
        *   `Executor`: Handles asynchronous task execution.
        *   Optional `HumanInputHandler`, `Logger`, and `OTEL Tracer`.
    *   The `Agent Factory` (`create_agents_in_dependency_order`) is responsible for instantiating the actual agent objects.
        *   It uses the `AgentConfigsDict` and a `ModelFactory`.
        *   `ModelFactory` provides factories for creating specific `AugmentedLLM` instances (e.g., for OpenAI, Anthropic) based on model strings.
        *   The factory creates `ActiveAgents` (concrete instances of `Agent`, `OrchestratorAgent`, etc.), attaches the appropriate `LLMInstances` to them, and initializes them (which often involves connecting to MCP servers via an `MCPAggregator`).
    *   Finally, `fast.run()` yields an `AgentApp` instance, which is a runtime wrapper providing easy access to the `ActiveAgents`.

### 3. Level 3: Agent Definition and Initialization Flow (`fast.run()`)

This sequence diagram details the process from agent definition by the user to the point where agents are initialized and ready for interaction within the `fast.run()` context.

```mermaid
sequenceDiagram
    participant User
    participant FastAgentDecorator["@fast.agent / @fast.orchestrator etc."]
    participant FastAgent
    participant MCPApp
    participant ContextModule["context.py"]
    participant AgentFactoryModule["agent_factory.py"]
    participant AgentClasses["Agent / WorkflowAgent Classes"]
    participant LLMClasses["AugmentedLLM & ProviderLLM Classes"]
    participant MCPAggregator
    participant MCPConnManager["MCPConnectionManager"]
    participant ServerRegistryMod["mcp_server_registry.py"]

    User->>FastAgentDecorator: Defines agent `my_agent` (e.g., `@fast.agent("my_agent", ...)`)
    FastAgentDecorator->>FastAgent: Stores `my_agent` config in `FastAgent.agents` dictionary

    User->>FastAgent: Calls `async with fast.run() as app_runtime:`
    FastAgent->>MCPApp: Creates `MCPApp` instance
    FastAgent->>MCPApp: `await app.initialize()`
    MCPApp->>ContextModule: `await initialize_context(config_path_or_settings)`
    ContextModule->>ContextModule: Loads `Settings` (from YAML, secrets, env)
    ContextModule->>ContextModule: Configures Logger, OTEL (optional)
    ContextModule->>ContextModule: Creates `Executor`
    ContextModule->>ServerRegistryMod: Creates `ServerRegistry`
    ContextModule-->>MCPApp: Returns initialized `Context` object
    MCPApp-->>FastAgent: `MCPApp` and `Context` initialized

    FastAgent->>AgentFactoryModule: `await create_agents_in_dependency_order(mcp_app, FastAgent.agents, model_factory_fn)`
    AgentFactoryModule->>AgentFactoryModule: Determines agent initialization order based on dependencies
    loop For each agent_config in dependency order
        AgentFactoryModule->>AgentFactoryModule: `create_agents_by_type(...)` for current agent (e.g., `my_agent`)
        AgentFactoryModule->>ModelFactory: `get_model_factory(agent_config.model)` (from `llm.model_factory.py`)
        ModelFactory-->>AgentFactoryModule: Returns `llm_factory_function` (e.g., for OpenAI)
        
        AgentFactoryModule->>AgentClasses: Instantiates `Agent("my_agent", agent_config, context)` (or specific workflow agent class)
        AgentClasses-->>AgentFactoryModule: `my_agent_instance`
        
        AgentFactoryModule->>AgentClasses: `await my_agent_instance.attach_llm(llm_factory_function, agent_config.default_request_params)`
        AgentClasses->>LLMClasses: `llm_factory_function` creates `AugmentedLLM` instance (e.g., `OpenAIAugmentedLLM`)
        LLMClasses-->>AgentClasses: `llm_instance`
        AgentClasses-->>AgentFactoryModule: `llm_instance` attached to `my_agent_instance`
        
        AgentFactoryModule->>AgentClasses: `await my_agent_instance.initialize()` (calls `__aenter__` on `BaseAgent`/`MCPAggregator`)
        AgentClasses->>MCPAggregator: `await self.load_servers()` (if not already initialized by another agent via context)
        MCPAggregator->>ServerRegistryMod: Gets server configurations from `Context.server_registry`
        opt Persistent MCP Connections (self.connection_persistence is True)
            MCPAggregator->>MCPConnManager: `await self._persistent_connection_manager.get_server(server_name)`
            MCPConnManager->>MCPConnManager: Launches server process task if new (e.g., stdio server)
            MCPConnManager->>ServerRegistryMod: Uses `transport_context_factory` (stdio_client, sse_client)
            MCPConnManager-->>MCPAggregator: `ServerConnection` (with `ClientSession`)
        end
        MCPAggregator->>MCPAggregator: Fetches tools/prompts from all connected servers (via `ClientSession.list_tools()`, etc.)
        MCPAggregator-->>AgentClasses: Servers loaded and tools/prompts indexed
        AgentClasses-->>AgentFactoryModule: `my_agent_instance` fully initialized
    end
    AgentFactoryModule-->>FastAgent: Returns `active_agents` (dictionary of initialized agent instances)
    FastAgent->>AgentAppRuntime: Creates `AgentApp(active_agents)` runtime wrapper
    FastAgent-->>User: Yields `app_runtime` (AgentApp instance)

    User->>AgentAppRuntime: Interacts with agents (e.g., `app_runtime.my_agent.send()`)

    Note right of User: When `fast.run()` context exits (end of `async with` block)
    FastAgent->>MCPApp: `await app.cleanup()`
    MCPApp->>ContextModule: `await cleanup_context()` (e.g., shuts down logger)
    loop For each agent in `active_agents`
        FastAgent->>AgentClasses: `await agent.shutdown()` (calls `__aexit__` on `BaseAgent`/`MCPAggregator`)
        AgentClasses->>MCPAggregator: `await self.close()`
        opt Persistent MCP Connections
            MCPAggregator->>MCPConnManager: `await self._persistent_connection_manager.disconnect_all()`
        end
    end
```

## Simplified:

```mermaid
sequenceDiagram
    participant User
    participant FastAPI as Fast Agent Framework
    participant AppCore as App Core Components
    participant AgentLayer as Agent Components
    participant LLMLayer as LLM Components
    participant MCPLayer as MCP Connectivity
    
    User->>FastAPI: Define agent with @fast.agent decorator
    Note right of FastAPI: Stores agent config in FastAgent.agents dictionary
    
    User->>FastAPI: async with fast.run() as app_runtime:
    
    FastAPI->>AppCore: Initialize application
    Note right of AppCore: - Creates MCPApp instance<br>- Loads Settings (YAML, secrets, env)<br>- Configures Logger, OTEL<br>- Creates Executor<br>- Creates ServerRegistry<br>- Returns Context object
    
    FastAPI->>AgentLayer: Create agents in dependency order
    Note right of AgentLayer: - Determines initialization order<br>- For each agent:<br>  * Get model factory<br>  * Instantiate Agent class<br>  * Return agent instance
    
    AgentLayer->>LLMLayer: Attach LLM to agent
    Note right of LLMLayer: - Creates AugmentedLLM instance<br>- Returns LLM instance to agent
    
    AgentLayer->>MCPLayer: Initialize MCP connections
    Note right of MCPLayer: - Loads servers via MCPAggregator<br>- For persistent connections:<br>  * Uses ConnectionManager<br>  * Launches server processes<br>  * Creates ServerConnection with ClientSession<br>- Fetches tools/prompts from servers<br>- Indexes all available tools
    
    FastAPI-->>User: Returns app_runtime (AgentApp instance)
    
    User->>FastAPI: Interact with agents (app_runtime.my_agent.send())
    
    rect rgb(240, 240, 250)
        Note over User,MCPLayer: Context Manager Exit Flow
        
        User->>FastAPI: Exit async with block
        FastAPI->>AppCore: Cleanup application
        
        FastAPI->>AgentLayer: Shutdown all agents
        AgentLayer->>MCPLayer: Close MCP connections
        Note right of MCPLayer: For persistent connections:<br>Disconnect all servers
        
        AppCore->>AppCore: Cleanup context (shutdown logger)
    end
```

**Explanation (Level 3):**

1.  **Agent Definition**: The user defines an agent (e.g., `my_agent`) using a decorator like `@fast.agent`. The decorator captures the agent's configuration (name, instruction, model, servers it uses) and stores it in the `FastAgent` instance's internal registry (`FastAgent.agents`).
2.  **`fast.run()` Invocation**: The user calls `async with fast.run() as app_runtime:`.
3.  **MCPApp Initialization**:
    *   The `FastAgent` creates an `MCPApp` instance.
    *   `MCPApp.initialize()` is called, which in turn calls `context.initialize_context()`.
    *   `initialize_context` loads settings from configuration files (`fastagent.config.yaml`, `fastagent.secrets.yaml`, environment variables) into a `Settings` object. It then creates and populates the `Context` object with these settings, and initializes logging, OpenTelemetry (if enabled), the `Executor`, and the `ServerRegistry` (which knows about MCP server configurations).
4.  **Agent Instantiation (`create_agents_in_dependency_order`)**:
    *   The `FastAgent` calls the agent factory module.
    *   The factory determines the correct order to initialize agents if there are dependencies between them (e.g., an orchestrator depends on its worker agents).
    *   For each agent configuration:
        *   It gets an LLM factory function from `ModelFactory` based on the `agent_config.model` string (e.g., `"openai.gpt-4.1"` or `"anthropic.claude-3-haiku"`).
        *   It instantiates the appropriate `Agent` class (e.g., `Agent`, `OrchestratorAgent`).
        *   It calls `agent.attach_llm()`, which uses the LLM factory to create a specific `AugmentedLLM` instance (e.g., `OpenAIAugmentedLLM`) and attaches it to the agent.
        *   It calls `await agent.initialize()`. This is crucial:
            *   The `Agent`'s `initialize` (often via `BaseAgent.__aenter__`) calls `MCPAggregator.load_servers()`.
            *   `MCPAggregator` (if it hasn't already loaded servers for this context) iterates through its configured `server_names`.
            *   For each server, if `connection_persistence` is true, it uses the `MCPConnectionManager` to get or establish a connection. The `MCPConnectionManager` might launch local MCP server processes (like `stdio_client` for an interpreter) and manages the `ClientSession`.
            *   The `MCPAggregator` then uses these sessions to `list_tools` and `list_prompts` from each server, building an internal index.
5.  **Runtime `AgentApp` Yielded**:
    *   Once all agents are instantiated and initialized, the factory returns a dictionary of these `active_agents`.
    *   `FastAgent` wraps these active agents in an `AgentApp` instance.
    *   This `AgentApp` instance (`app_runtime`) is yielded to the user's `async with` block.
6.  **User Interaction**: The user can now interact with the agents via `app_runtime.agent_name.send()`, etc.
7.  **Shutdown**: When the `async with` block exits:
    *   `MCPApp.cleanup()` is called (e.g., shuts down logging).
    *   Each active agent's `shutdown()` method is called. This typically involves the `MCPAggregator.close()`, which, if using persistent connections, tells the `MCPConnectionManager` to disconnect from servers and terminate any managed processes.

### 4. Level 4: Agent Interaction - A Single Agent Call Data Flow (e.g., `agent.send()`)

This diagram shows the data flow when a user makes a simple call to an agent, including potential tool usage.

```mermaid
sequenceDiagram
    participant UserApp as User Application Code
    participant AgentApp as AgentApp (Runtime Wrapper)
    participant ConcreteAgent as Agent Instance (e.g., MyAgent)
    participant AugmentedLLM as Agent's AugmentedLLM
    participant ProviderConverter as Provider-Specific Converter
    participant LLMProviderAPI as LLM Provider API (e.g., OpenAI)
    participant MCPAggregator as MCP Aggregator
    participant MCPConnManager as MCPConnectionManager
    participant MCPServer as MCP Server (e.g., Filesystem)
    participant ConsoleDisplay as Console Display

    UserApp->>AgentApp: await agent_app.my_agent.send("User prompt")
    AgentApp->>ConcreteAgent: await self.send("User prompt")
    ConcreteAgent->>ConcreteAgent: _normalize_message_input("User prompt") -> prompt_msg_multipart
    ConcreteAgent->>AugmentedLLM: await self.generate([prompt_msg_multipart], request_params)

    AugmentedLLM->>AugmentedLLM: _precall([prompt_msg_multipart])
    AugmentedLLM->>ConsoleDisplay: Display user message (if enabled)
    AugmentedLLM->>AugmentedLLM: Append user message to self._message_history

    AugmentedLLM->>AugmentedLLM: _apply_prompt_provider_specific([prompt_msg_multipart], effective_request_params)
    AugmentedLLM->>AugmentedLLM: self.history.extend(provider_formatted_user_messages)
    AugmentedLLM->>ProviderConverter: convert_to_provider_format(prompt_msg_multipart)
    ProviderConverter-->>AugmentedLLM: provider_messages_list

    AugmentedLLM->>MCPAggregator: await self.aggregator.list_tools()
    MCPAggregator-->>AugmentedLLM: list_tools_result
    AugmentedLLM->>ProviderConverter: Convert list_tools_result to provider's tool format
    ProviderConverter-->>AugmentedLLM: provider_tools_param

    AugmentedLLM->>LLMProviderAPI: client.chat.completions.create(messages=provider_messages, tools=provider_tools_param, ...)
    LLMProviderAPI-->>AugmentedLLM: llm_api_response

    alt LLM requests tool calls
        AugmentedLLM->>AugmentedLLM: Parse tool call(s) from llm_api_response
        AugmentedLLM->>ConsoleDisplay: show_assistant_message("Assistant wants to use tool X") (if applicable)
        loop For each tool call
            AugmentedLLM->>ConsoleDisplay: show_tool_call(tool_name, tool_args) (if enabled)
            AugmentedLLM->>MCPAggregator: await self.aggregator.call_tool(tool_name, tool_args)
            MCPAggregator->>MCPConnManager: Get/Create ClientSession
            MCPConnManager-->>MCPAggregator: client_session
            MCPAggregator->>MCPServer: client_session.call_tool(local_tool_name, tool_args)
            MCPServer-->>MCPAggregator: tool_call_result_mcp
            MCPAggregator-->>AugmentedLLM: tool_call_result_mcp
            AugmentedLLM->>ConsoleDisplay: show_tool_result(tool_call_result_mcp) (if enabled)
            AugmentedLLM->>ProviderConverter: Convert tool_call_result_mcp to provider's tool result format
            ProviderConverter-->>AugmentedLLM: provider_tool_response_message_part
            AugmentedLLM->>AugmentedLLM: Add provider_tool_response_message_part to list
        end
        AugmentedLLM->>AugmentedLLM: self.history.append(provider_tool_call_request_message)
        AugmentedLLM->>AugmentedLLM: self.history.append(provider_tool_response_messages)
        AugmentedLLM->>LLMProviderAPI: client.chat.completions.create(messages_with_tool_results, ...)
        LLMProviderAPI-->>AugmentedLLM: final_llm_api_response
    else LLM returns final text
        AugmentedLLM->>AugmentedLLM: final_llm_api_response = llm_api_response
    end

    AugmentedLLM->>ProviderConverter: convert_from_provider_format(final_llm_api_response)
    ProviderConverter-->>AugmentedLLM: assistant_response_multipart
    AugmentedLLM->>ConsoleDisplay: await show_assistant_message(assistant_response_multipart, ...) (if enabled)
    AugmentedLLM->>AugmentedLLM: self._message_history.append(assistant_response_multipart)
    AugmentedLLM-->>ConcreteAgent: assistant_response_multipart
    ConcreteAgent-->>AgentApp: assistant_response_multipart.all_text()
    AgentApp-->>UserApp: Final string response
```

### Simplified:

```mermaid
sequenceDiagram
    participant UserApp as User Application
    participant AgentApp as AgentApp Runtime
    participant Agent as Agent Instance
    participant LLM as AugmentedLLM
    participant Converter as Provider Converter
    participant API as LLM Provider API
    participant MCP as MCP Aggregator
    participant Console as Console Display

    UserApp->>AgentApp: send("User prompt")
    AgentApp->>Agent: send("User prompt")
    Agent->>LLM: generate(prompt)

    LLM->>Console: Display user message
    LLM->>Converter: Convert prompt to provider format
    Converter-->>LLM: Provider messages

    LLM->>MCP: List available tools
    MCP-->>LLM: Tool list
    LLM->>Converter: Convert tools to provider format
    Converter-->>LLM: Provider tools

    LLM->>API: Call API with messages and tools
    API-->>LLM: API response

    alt Tool call requested
        LLM->>Console: Display tool call
        LLM->>MCP: Call tool
        MCP-->>LLM: Tool result
        LLM->>Converter: Convert tool result
        Converter-->>LLM: Provider tool response
        LLM->>API: Call API with tool results
        API-->>LLM: Final response
    else Final text response
        LLM->>LLM: Use API response as final
    end

    LLM->>Converter: Convert response to internal format
    Converter-->>LLM: Assistant response
    LLM->>Console: Display assistant response
    LLM-->>Agent: Return assistant response
    Agent-->>AgentApp: Return response text
    AgentApp-->>UserApp: Return final response
```

**Explanation (Level 4):**

1.  **User Call**: The user's application code calls a method like `send()` on an agent accessed through the `AgentApp` runtime wrapper.
2.  **Agent Processing**: The `Agent` instance normalizes the input to `PromptMessageMultipart`. It then calls `generate()` on its `AugmentedLLM` instance.
3.  **AugmentedLLM Pre-call**: The `AugmentedLLM` performs pre-call actions:
    *   Displays the user's message to the console (if enabled).
    *   Adds the user's message to its internal `_message_history` (the generic, framework-level history).
4.  **Provider-Specific Logic (`_apply_prompt_provider_specific`)**: This is where the specific LLM provider's logic (e.g., in `OpenAIAugmentedLLM` or `AnthropicAugmentedLLM`) takes over.
    *   **History Management**: The provider-specific LLM extends its own internal history (`self.history`), which often stores messages in the provider's native format.
    *   **Message Conversion**: Incoming `PromptMessageMultipart` objects are converted to the LLM provider's specific message format (e.g., OpenAI's list of message dictionaries) using a `ProviderConverter`.
    *   **Tool Listing**: The `MCPAggregator.list_tools()` is called to get all available tools. These are also converted to the provider's tool format.
    *   **LLM API Call**: An API call is made to the external LLM provider with the formatted messages and tools.
5.  **Tool Handling Loop (if LLM requests tools)**:
    *   If the LLM's response indicates a tool call is needed:
        *   The `AugmentedLLM` parses these requests.
        *   It displays the assistant's intention to call a tool (if enabled).
        *   For each requested tool:
            *   It displays the tool call details (if enabled).
            *   It calls `MCPAggregator.call_tool()`. The aggregator resolves the (potentially namespaced) tool name to the correct MCP server and local tool name.
            *   The `MCPAggregator` uses the `MCPConnectionManager` (for persistent connections) or `gen_client` (for temporary ones) to get a `ClientSession` to the target MCP Server.
            *   The `ClientSession` executes the tool call on the `MCPServer`.
            *   The `MCPServer` returns the `tool_call_result`.
            *   The `AugmentedLLM` displays this result (if enabled).
            *   The result is converted back into the LLM provider's format for a tool response message.
            *   This tool response is added to the provider-specific history.
        *   The `AugmentedLLM` makes another API call to the LLM provider, now including the tool call results. This loop can continue for multiple tool calls up to `max_iterations`.
6.  **Final LLM Response**: Once the LLM provides a final text response (not a tool call):
    *   This provider-specific response is converted back to a `PromptMessageMultipart` (`assistant_response_multipart`).
    *   The assistant's response is displayed (if enabled).
    *   The `assistant_response_multipart` is added to the generic `_message_history`.
7.  **Return**: The `assistant_response_multipart` is returned up the call stack, eventually becoming a string response for the user.

### 5. Level 5: Orchestrator Agent Workflow

This diagram illustrates how an `OrchestratorAgent` processes a task, plans, delegates to child agents, and synthesizes results.

```mermaid
sequenceDiagram
    participant UserApp
    participant OrchestratorAgent
    participant OrchestratorLLM as "Orchestrator's AugmentedLLM"
    participant ChildAgent1 as "Finder"
    participant ChildAgent2 as "Writer"

    UserApp->>OrchestratorAgent: await orchestrator.send("Objective: Create report")
    OrchestratorAgent->>OrchestratorAgent: generate(["User: Objective..."], ...)
    OrchestratorAgent->>OrchestratorAgent: _execute_plan("Objective...", effective_request_params)

    alt Full Plan (plan_type="full")
        OrchestratorAgent->>OrchestratorLLM: _get_full_plan()
        Note over OrchestratorLLM: Uses _llm.structured(Plan) or _planner_generate_str()<br>Prompt: objective, agents, progress
        OrchestratorLLM-->>OrchestratorAgent: Return Plan (multiple steps)
    else Iterative Plan (plan_type="iterative")
        loop Until plan.is_complete
            OrchestratorAgent->>OrchestratorLLM: _get_next_step()
            Note over OrchestratorLLM: Uses _llm.structured(NextStep) or _planner_generate_str()<br>Prompt: objective, agents, progress
            OrchestratorLLM-->>OrchestratorAgent: Return NextStep (Step with is_complete flag)
            OrchestratorAgent->>OrchestratorAgent: Append NextStep to PlanResult
            OrchestratorAgent->>OrchestratorAgent: Execute single step
            Note over OrchestratorAgent: Break if NextStep.is_complete
        end
    end

    OrchestratorAgent->>OrchestratorAgent: Store Plan in self.plan_result

    loop For each Step in Plan
        OrchestratorAgent->>OrchestratorAgent: _execute_step(step, plan_result, ...)
        Note over OrchestratorAgent: Tasks executed concurrently via asyncio.gather
        par Agent Tasks
            OrchestratorAgent->>ChildAgent1: Format task_prompt_for_agent1<br>(objective, task, context)
            OrchestratorAgent->>ChildAgent1: await agent1.generate([task_prompt_for_agent1])
            ChildAgent1-->>OrchestratorAgent: Return agent1_task_result_text<br>(PromptMessageMultipart, .all_text())
        and
            OrchestratorAgent->>ChildAgent2: Format task_prompt_for_agent2<br>(objective, task, context)
            OrchestratorAgent->>ChildAgent2: await agent2.generate([task_prompt_for_agent2])
            ChildAgent2-->>OrchestratorAgent: Return agent2_task_result_text
        end
        OrchestratorAgent->>OrchestratorAgent: Create TaskWithResult for each task
        OrchestratorAgent->>OrchestratorAgent: Aggregate into StepResult.result (text)
        OrchestratorAgent->>OrchestratorAgent: Append StepResult to plan_result.step_results
    end

    alt Plan completed or max_iterations reached
        OrchestratorAgent->>OrchestratorLLM: _planner_generate_str(SYNTHESIZE_PLAN_PROMPT_TEMPLATE or SYNTHESIZE_INCOMPLETE_PLAN_TEMPLATE, ...)
        Note over OrchestratorLLM: Prompt includes plan_result (objective, step results)
        OrchestratorLLM-->>OrchestratorAgent: Return final_synthesized_text
        OrchestratorAgent->>OrchestratorAgent: Update plan_result.result with final_synthesized_text
    end

    OrchestratorAgent-->>UserApp: Return PromptMessageMultipart(role="assistant", content=[TextContent(text=final_synthesized_text)])
```

### Simplified:

```mermaid
sequenceDiagram
    participant UserApp as User Application
    participant Orchestrator as Orchestrator Agent
    participant OrchestratorLLM as Orchestrator LLM
    participant ChildAgent1 as Child Agent 1
    participant ChildAgent2 as Child Agent 2

    UserApp->>Orchestrator: send("Objective: Create report")
    Orchestrator->>OrchestratorLLM: Generate plan
    OrchestratorLLM-->>Orchestrator: Plan or next step

    alt Full plan
        OrchestratorLLM-->>Orchestrator: Complete plan
    else Iterative plan
        OrchestratorLLM-->>Orchestrator: Next step
    end

    loop For each step
        Orchestrator->>ChildAgent1: Execute task
        ChildAgent1-->>Orchestrator: Task result
        Orchestrator->>ChildAgent2: Execute task
        ChildAgent2-->>Orchestrator: Task result
        Orchestrator->>Orchestrator: Aggregate step results
    end

    Orchestrator->>OrchestratorLLM: Synthesize final result
    OrchestratorLLM-->>Orchestrator: Final text
    Orchestrator-->>UserApp: Return final response
```

### Simplified more:

```mermaid
sequenceDiagram
    participant UserApp
    participant OrchestratorAgent
    participant OrchestratorLLM
    participant ChildAgent1 as Finder
    participant ChildAgent2 as Writer

    UserApp->>OrchestratorAgent: Send "Objective: Create report"
    OrchestratorAgent->>OrchestratorLLM: Request plan for objective
    Note over OrchestratorLLM: Uses objective and agent info
    OrchestratorLLM-->>OrchestratorAgent: Return Plan (steps)

    loop For each step in Plan
        OrchestratorAgent->>ChildAgent1: Send task (e.g., find data)
        ChildAgent1-->>OrchestratorAgent: Return task result
        OrchestratorAgent->>ChildAgent2: Send task (e.g., write report)
        ChildAgent2-->>OrchestratorAgent: Return task result
        OrchestratorAgent->>OrchestratorAgent: Aggregate step results
    end

    OrchestratorAgent->>OrchestratorLLM: Synthesize final result
    Note over OrchestratorLLM: Uses all step results
    OrchestratorLLM-->>OrchestratorAgent: Return final text
    OrchestratorAgent-->>UserApp: Return final report
```

### Somewhat simplified:

```mermaid
sequenceDiagram
    participant UserApp
    participant OrchestratorAgent
    participant OrchestratorLLM
    participant ChildAgent1 as Finder
    participant ChildAgent2 as Writer

    UserApp->>OrchestratorAgent: Send "Objective: Create report"
    OrchestratorAgent->>OrchestratorLLM: Request plan for objective
    Note over OrchestratorLLM: Uses objective, available agents, progress

    alt Full Plan (plan_type="full")
        OrchestratorLLM-->>OrchestratorAgent: Return complete Plan (multiple steps)
    else Iterative Plan (plan_type="iterative")
        loop Until plan complete
            OrchestratorLLM-->>OrchestratorAgent: Return NextStep (single step)
            OrchestratorAgent->>OrchestratorAgent: Append NextStep to Plan
        end
    end

    OrchestratorAgent->>OrchestratorAgent: Store Plan

    loop For each Step in Plan
        par Concurrent Tasks
            OrchestratorAgent->>ChildAgent1: Send task (e.g., find data)
            Note over ChildAgent1: Task includes objective, context
            ChildAgent1-->>OrchestratorAgent: Return task result
        and
            OrchestratorAgent->>ChildAgent2: Send task (e.g., write report)
            Note over ChildAgent2: Task includes objective, context
            ChildAgent2-->>OrchestratorAgent: Return task result
        end
        OrchestratorAgent->>OrchestratorAgent: Aggregate task results into StepResult
        OrchestratorAgent->>OrchestratorAgent: Store StepResult in Plan
    end

    OrchestratorAgent->>OrchestratorLLM: Synthesize final result
    Note over OrchestratorLLM: Uses objective, all step results
    OrchestratorLLM-->>OrchestratorAgent: Return final synthesized text
    OrchestratorAgent-->>UserApp: Return final report
```

**Explanation (Level 5):**

1.  **User Request**: The user sends an objective to the `OrchestratorAgent`.
2.  **Plan Execution Start**: The `OrchestratorAgent.generate()` method calls `_execute_plan()`.
3.  **Planning Phase**:
    *   **Full Plan**: If `plan_type` is "full", `_get_full_plan()` is called. This method itself uses the orchestrator's LLM (via `_llm.structured(Plan)` or `_planner_generate_str` if structured parsing fails) to generate a complete multi-step `Plan`. The prompt to the LLM includes the main objective, descriptions of available child agents, and any progress so far.
    *   **Iterative Plan**: If `plan_type` is "iterative", the orchestrator enters a loop. In each iteration, `_get_next_step()` is called, which again uses the orchestrator's LLM to generate just the single `NextStep`. This step is then executed. The loop continues until the `NextStep` indicates the plan is complete or `max_iterations` is reached.
4.  **Step Execution (`_execute_step`)**:
    *   For each `Step` in the generated plan (or the single `NextStep` in iterative mode):
        *   The tasks within that `Step` are executed concurrently using `asyncio.gather`.
        *   For each `AgentTask`:
            *   The orchestrator constructs a detailed prompt for the designated child agent. This prompt includes the overall objective, the specific task description for that agent, and context from previously executed steps (formatted from `PlanResult`).
            *   It calls `child_agent.generate()` with this prompt.
            *   The child agent processes its task (which might involve its own LLM calls or tool uses) and returns a result text.
        *   The results from all tasks in the step are collected into `TaskWithResult` objects and added to a `StepResult`.
        *   The `StepResult` itself might have its `result` field (a textual summary of the step) populated (though current implementation seems to rely more on the final synthesis).
        *   This `StepResult` is appended to the main `PlanResult`.
5.  **Final Synthesis**:
    *   Once the plan is marked as complete (either by a full plan or the last iterative step) or `max_iterations` is reached:
        *   The `OrchestratorAgent` calls its own LLM one last time using `_planner_generate_str()`.
        *   The prompt for this synthesis step (e.g., `SYNTHESIZE_PLAN_PROMPT_TEMPLATE`) includes the entire `PlanResult` (objective, all step descriptions, and all task results).
        *   The LLM generates a final, cohesive response based on all the work done. If `max_iterations` was reached without completion, a different template (`SYNTHESIZE_INCOMPLETE_PLAN_TEMPLATE`) is used to frame the response.
6.  **Return to User**: The `final_synthesized_text` is wrapped in a `PromptMessageMultipart` and returned, which `send()` then typically converts to a plain string for the user.

### 6. Level 6: MCP Server Interaction (Focus on `MCPAggregator.call_tool()`)

This diagram details how an `MCPAggregator` (used by an `Agent`) interacts with an MCP Server to execute a tool.

```mermaid
graph TD
    subgraph AgentLogic ["Agent Logic"]
        A_AugmentedLLM["AugmentedLLM"]
    end
    
    subgraph MCPAggregatorCore ["MCPAggregator"]
        Agg_MCPAggregator["MCPAggregator Instance"]
        Agg_ToolMap["_namespaced_tool_map (tool_name -> NamespacedTool)"]
        Agg_ServerToToolMap["_server_to_tool_map (server_name -> List[NamespacedTool])"]
    end
    
    subgraph MCPConnectionManagement ["MCP Connection Management"]
        CM_ConnectionManager["MCPConnectionManager (Optional, for persistent connections)"]
        SR_ServerRegistry["ServerRegistry (Holds MCPServerSettings)"]
        GC_GenClient["gen_client() (For non-persistent connections)"]
    end
        
    subgraph MCPServerProcess ["MCP Server (External Process/Service)"]
        direction TB
        Server_Process["MCP Server Process (e.g., Python script running FastMCP)"]
        Server_TransportHandler["Transport Handler (stdio, sse, http)"]
        Server_ClientSessionHandler["Server-Side ClientSession Handler"]
        Server_ToolImpl["Actual Tool Implementation (e.g., @mcp.tool decorated function)"]
    end
    
    A_AugmentedLLM -- "1 await self.aggregator.call_tool(tool_name, args)" --> Agg_MCPAggregator
    
    Agg_MCPAggregator -- "2 _parse_resource_name(tool_name) (Uses Agg_ToolMap, Agg_ServerToToolMap)" --> Agg_MCPAggregator
    Agg_MCPAggregator -- "3 Resolves to server_name & local_tool_name" --> Agg_MCPAggregator
        
    %% Connection type decision point
    Agg_MCPAggregator -- "4 Check connection_persistence" --> ConnectionDecision{"connection_persistence?"}
    
    %% Persistent Connection Path
    ConnectionDecision -- "True" --> CM_ConnectionManager
    CM_ConnectionManager -- "5a Gets/Launches server if needed" --> SR_ServerRegistry
    SR_ServerRegistry -- "Provides MCPServerSettings" --> CM_ConnectionManager
    CM_ConnectionManager -- "6a Manages transport & creates ServerConnection" --> CM_ConnectionManager
    CM_ConnectionManager -- "7a Returns ServerConnection (with ClientSession)" --> Agg_MCPAggregator
    
    %% Non-Persistent Connection Path
    ConnectionDecision -- "False" --> GC_GenClient
    GC_GenClient -- "5b Uses" --> SR_ServerRegistry
    SR_ServerRegistry -- "Provides MCPServerSettings" --> GC_GenClient
    GC_GenClient -- "6b Manages transport & creates ClientSession" --> GC_GenClient
    GC_GenClient -- "7b Yields ClientSession" --> Agg_MCPAggregator
    
    %% Common path after session acquisition
    Agg_MCPAggregator -- "8 client_session.call_tool(local_tool_name, args)" --> Server_TransportHandler
    Server_TransportHandler -- "9 Forwards MCP Request" --> Server_ClientSessionHandler
    Server_ClientSessionHandler -- "10 Invokes" --> Server_ToolImpl
    Server_ToolImpl -- "11 Executes tool logic" --> Server_ToolImpl
    Server_ToolImpl -- "12 Returns result" --> Server_ClientSessionHandler
    Server_ClientSessionHandler -- "13 Sends MCP Response (CallToolResult)" --> Server_TransportHandler
    Server_TransportHandler -- "14 Transmits MCP Response" --> Agg_MCPAggregator
    Agg_MCPAggregator -- "15 Returns CallToolResult" --> A_AugmentedLLM

    %% Notes
    classDef note fill:#ffffcc,stroke:#999,stroke-width:1px,color:#000;
    class ConnectionDecision note
    
    %% Add note about ServerConnection
    ServerConnectionNote["ServerConnection holds the ClientSession.<br>If new, starts _server_lifecycle_task."]
    CM_ConnectionManager --> ServerConnectionNote
    class ServerConnectionNote note
```

**Explanation (Level 6):**

1.  **Agent Request**: The `AugmentedLLM` (on behalf of an agent) decides to call a tool and invokes `self.aggregator.call_tool(tool_name, args)`.
2.  **Tool Resolution**: The `MCPAggregator` uses its internal maps (`_namespaced_tool_map`, `_server_to_tool_map`) via `_parse_resource_name` to determine which `server_name` hosts the `tool_name` and what the `local_tool_name` is on that server.
3.  **Connection Handling**:
    *   **Persistent**: If `connection_persistence` is true, the aggregator uses its `MCPConnectionManager`.
        *   `get_server()` is called. If a healthy connection to `server_name` doesn't exist, the manager launches/connects to it.
        *   Launching involves using `ServerRegistry` to get `MCPServerSettings` (command, transport type, URL, etc.).
        *   The `MCPConnectionManager` uses the appropriate transport client (e.g., `stdio_client`, `sse_client`) to establish communication streams and creates a `ServerConnection` object, which holds the `ClientSession`. A background task (`_server_lifecycle_task`) manages this connection.
        *   The `ClientSession` is returned.
    *   **Non-Persistent**: If `connection_persistence` is false (or `gen_client` is used directly), a temporary connection is established.
        *   `gen_client` also uses `ServerRegistry` and the transport clients.
        *   It yields an active `ClientSession` for the duration of the `async with` block.
4.  **Tool Invocation**: The `MCPAggregator` uses the obtained `ClientSession` to call `client_session.call_tool(local_tool_name, args)`. This sends an MCP `tools/call` request over the established transport to the `MCPServer`.
5.  **Server-Side Execution**:
    *   The `MCPServer`'s transport handler (e.g., stdio, SSE listener) receives the request.
    *   It passes the MCP message to its server-side `ClientSession` handler.
    *   The server-side session identifies the tool request and invokes the actual tool implementation function (the one decorated with `@mcp.tool` in the server's code).
    *   The tool function executes and returns its result.
6.  **Response**:
    *   The server-side session handler packages the tool's result into an MCP `CallToolResult` response.
    *   This response is sent back over the transport to the `MCPAggregator`'s `ClientSession`.
7.  **Return to Agent**: The `MCPAggregator` receives the `CallToolResult` and returns it to the `AugmentedLLM`.

### 7. Configuration Data Flow (Overview)

This diagram shows how configuration is loaded and utilized by different parts of the application.

```mermaid
graph TD
    subgraph ConfigSources ["Configuration Sources"]
        direction TB
        File_Config["fastagent.config.yaml"]
        File_Secrets["fastagent.secrets.yaml"]
        Env_Vars["Environment Variables"]
    end

    subgraph ConfigLoading ["Configuration&nbsp;Loading&nbsp;(config.py)"]
        direction TB
        GetSettings["get_settings(config_path)"]
        SettingsModelDef["Settings (Pydantic Model Definition)"]
        YAMLParser["YAML Parser"]
        DeepMerge["Deep Merge Logic (Secrets over Config)"]
    end

    subgraph AppContextSetup ["Application&nbsp;Context&nbsp;Setup&nbsp;(context.py)"]
        direction TB
        InitializeContext["initialize_context()"]
        ContextInstance["Context Object (Holds final Settings)"]
    end

    subgraph AppCoreUsage ["Application Core Usage"]
        direction LR
        Core_MCPApp["MCPApp"]
        Core_ServerRegistry["ServerRegistry"]
        Core_LLMProviders["LLM Provider Instances"]
        Core_MCPAggregator["MCPAggregator"]
        Core_Logger["Logger / OTEL"]
    end

    File_Config --> YAMLParser
    File_Secrets --> YAMLParser
    
    YAMLParser -- "Raw dict from config.yaml" --> GetSettings
    YAMLParser -- "Raw dict from secrets.yaml" --> GetSettings
    Env_Vars -- "Read by Pydantic" --> SettingsModelDef

    GetSettings -- "Uses" --> SettingsModelDef
    GetSettings -- "Merges YAML dicts using" --> DeepMerge
    DeepMerge -- "Produces merged dict" --> GetSettings
    GetSettings -- "Instantiates SettingsModelDef with merged dict & env vars" --> SettingsModelInstance["settings_instance: Settings"]
    
    SettingsModelInstance --> InitializeContext
    InitializeContext -- "Stores settings_instance in" --> ContextInstance
    
    ContextInstance -- "Provides Settings to" --> Core_MCPApp
    Core_MCPApp -- "Provides Context to its components" --> Core_ServerRegistry
    Core_MCPApp -- "Provides Context to" --> Core_LLMProviders
    Core_MCPApp -- "Provides Context to" --> Core_MCPAggregator
    Core_MCPApp -- "Provides Context to" --> Core_Logger
    
    Core_ServerRegistry -- "Reads mcp.servers from Settings" --> ContextInstance
    Core_LLMProviders -- "Reads provider keys (e.g., openai.api_key) from Settings" --> ContextInstance
    Core_MCPAggregator -- "Uses ServerRegistry (which uses Settings)" --> Core_ServerRegistry
    Core_Logger -- "Reads logger & otel sections from Settings" --> ContextInstance

    classDef source fill:#f9c,stroke:#333,stroke-width:2px,color:#000;
    classDef loading fill:#fec,stroke:#333,stroke-width:2px,color:#000;
    classDef contextSetup fill:#9de,stroke:#333,stroke-width:2px,color:#000;
    classDef usage fill:#cf9,stroke:#333,stroke-width:2px,color:#000;

    class File_Config,File_Secrets,Env_Vars source;
    class GetSettings,SettingsModelDef,YAMLParser,DeepMerge,SettingsModelInstance loading;
    class InitializeContext,ContextInstance contextSetup;
    class Core_MCPApp,Core_ServerRegistry,Core_LLMProviders,Core_MCPAggregator,Core_Logger usage;
```

**Explanation (Configuration Data Flow):**

1.  **Sources**: Configuration comes from `fastagent.config.yaml` (general settings), `fastagent.secrets.yaml` (API keys, sensitive data), and environment variables.
2.  **Loading (`config.py:get_settings`)**:
    *   The `get_settings` function is the main entry point for loading configuration.
    *   It uses a `YAMLParser` to read `fastagent.config.yaml` and `fastagent.secrets.yaml`.
    *   `DeepMerge` logic combines these, with `secrets.yaml` values overriding those in `config.yaml` for the same keys.
    *   The `Settings` Pydantic model definition (which also specifies environment variable mappings like `FASTAGENT_OPENAI__API_KEY` for `openai.api_key`) is instantiated with this merged dictionary. Pydantic handles parsing, validation, and incorporating environment variables (which typically have the highest precedence over file-based settings for a given field if both are present, though `get_settings`'s manual merge gives file secrets precedence).
3.  **Context Setup (`context.py:initialize_context`)**:
    *   `initialize_context` takes the loaded `Settings` instance.
    *   It creates a `Context` object and stores the `settings_instance` within it.
4.  **Application Core Usage**:
    *   The `MCPApp` instance holds this `Context`.
    *   Various core components access the `Settings` object via the `Context`:
        *   `ServerRegistry` reads the `mcp.servers` section to know about available MCP servers.
        *   LLM Provider instances (e.g., `OpenAIAugmentedLLM`) read their specific sections (e.g., `openai.api_key`, `anthropic.base_url`) for API keys and other configurations.
        *   `MCPAggregator` uses the `ServerRegistry` to interact with configured MCP servers.
        *   The `Logger` and OpenTelemetry setup read the `logger` and `otel` sections respectively.

This series of diagrams should provide a comprehensive overview of the `fast-agent` software architecture and its key data flows and operational sequences.Okay, this is a comprehensive task! Based on the provided files, here's a series of Mermaid diagrams describing the `fast-agent` software architecture and data flows, starting from a high level and drilling down.
