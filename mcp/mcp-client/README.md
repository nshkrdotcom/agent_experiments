# Composable MCP Client with Workflows

This project demonstrates a modular Python client for interacting with MCP (Model Context Protocol) servers. It uses a configuration-driven approach to define workflows that leverage an LLM (Google Gemini via `google-genai`) and various MCP tools.

## Features

*   **Modular Design:** Code is split into logical components for configuration, services, workflow engine, CLI, and logging.
*   **Configuration-Driven:**
    *   `mcp_servers.json`: Define connection details for MCP servers (e.g., weather, Context7).
    *   `workflows.json`: Define different "personalities" or task-specific setups for the LLM, specifying which model to use, which MCP servers (tools) are available, an initial prompt, and conversation turn limits.
*   **MCP Integration:** Connects to and utilizes tools exposed by MCP servers.
*   **LLM Integration:** Uses Google Gemini for natural language understanding and function calling.
*   **Flexible Logging:**
    *   Configurable console log verbosity (`quiet`, `user`, `normal`, `verbose`).
    *   Detailed file logging (`app_client.log`).
    *   Control over third-party library log noise.
*   **Asynchronous Operations:** Built with `asyncio` for efficient I/O.

## Project Structure

```bash
.
├── app_logger.py       # Logging abstraction and setup
├── cli.py              # Command-line interface and main entry point
├── config.py           # Handles loading mcp_servers.json and workflows.json
├── engine.py           # Core workflow orchestration logic
├── services.py         # Classes for interacting with MCP servers and LLM
├── mcp_servers.json    # Example MCP server configurations
├── workflows.json      # Example workflow definitions
└── app_client.log      # Log file (generated on run)
```

## Prerequisites

*   Python 3.9+
*   Node.js (if using MCP servers like Context7 that are Node-based, e.g., via `npx`)
*   An environment variable `GOOGLE_API_KEY` (or `GEMINI_API_KEY`) set with your Google AI Studio API key.

## Setup

1.  **Clone the repository (or create the files):**
    ```bash
    # If you have the files already, skip this
    # git clone <repository_url>
    # cd <repository_name>
    ```

2.  **Create Python Virtual Environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install python-dotenv mcp-protocols google-generativeai google-genai
    ```

4.  **Configure API Key:**
    Create a `.env` file in the project root:
    ```env
    GOOGLE_API_KEY="YOUR_API_KEY_HERE"
    ```
    Alternatively, set the environment variable directly in your shell.

5.  **Create Configuration Files:**
    *   **`mcp_servers.json`:**
        (See example content from previous responses or create your own based on the structure)
        Example:
        ```json
        {
          "mcpServers": {
            "weather": {
              "command": "python",
              "args": ["../path/to/your/weather_server.py"],
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
        *Ensure paths in `args` for local servers are correct relative to where `cli.py` is run.*

    *   **`workflows.json`:**
        (See example content from previous responses or create your own)
        Example:
        ```json
        {
          "workflows": {
            "weather_assistant": {
              "description": "Ask about the weather.",
              "llm_model": "gemini-1.5-flash-latest",
              "mcp_servers_used": ["weather"],
              "initial_prompt_template": "You are a helpful weather assistant. User Query: {query}",
              "max_conversation_turns": 5
            },
            "multi_tool_agent": {
              "description": "An agent that can use weather and context7.",
              "llm_model": "gemini-1.5-flash-latest",
              "mcp_servers_used": ["weather", "context7"],
              "initial_prompt_template": "You are a multi-talented assistant. User Query: {query}",
              "max_conversation_turns": 7
            }
          }
        }
        ```

## Usage

All commands are run from the project root directory where `cli.py` is located.

**1. List Available Workflows:**
   ```bash
   python cli.py --list-workflows
   # or
   python cli.py -l
   ```

**2. Run a Workflow (Interactive Chat Mode):**
   ```bash
   python cli.py <workflow_name>
   ```
   Example:
   ```bash
   python cli.py multi_tool_agent
   ```
   Then type your queries at the "Query:" prompt. Type `quit` to exit the chat loop.

**3. Run a Workflow with a Single Query (Non-Interactive):**
   ```bash
   python cli.py <workflow_name> --query "Your question here"
   ```
   Example:
   ```bash
   python cli.py weather_assistant --query "What's the weather in London?"
   ```

**4. Controlling Log Verbosity (Console Output):**
   The `--log-level` option controls how much log information is printed to the console.
   *   `quiet`: Minimal output (mostly just `print` statements from the CLI).
   *   `user`: (Default) Shows key interactions like LLM turns and tool calls.
   *   `normal`: More operational info (INFO level logs).
   *   `verbose`: Detailed debug output.

   Examples:
   ```bash
   # Default (user level)
   python cli.py multi_tool_agent

   # Verbose console output
   python cli.py multi_tool_agent --log-level verbose

   # Normal console output
   python cli.py multi_tool_agent --log-level normal

   # Quiet console output (from the logger)
   python cli.py multi_tool_agent --log-level quiet
   ```

**5. Disabling File Logging:**
   By default, detailed logs are written to `app_client.log`. To disable this:
   ```bash
   python cli.py multi_tool_agent --no-log-file
   ```

**6. Using Custom Configuration File Paths:**
   ```bash
   python cli.py multi_tool_agent \
       --mcp-config /path/to/your/custom_mcp_servers.json \
       --workflows-config /path/to/your/custom_workflows.json
   ```

## Development & Troubleshooting

*   Check `app_client.log` for detailed logs, especially if console output is minimal or errors occur.
*   Use `--log-level verbose` for maximum insight into the application's operations.
*   Ensure MCP server commands specified in `mcp_servers.json` are correct and executable from your environment.
*   Verify your `GOOGLE_API_KEY` is correctly set and has access to the Gemini API.

---

## Architectural Mermaid Diagrams

Here are diagrams focusing on the architecture and interactions, especially around the `engine.py` and its use of MCP/tools.

**Diagram 1: Overall System Architecture & Configuration**

```mermaid
graph TD
    User["User (CLI)"] -- Interacts via --> CLI["cli.py<br>(ArgParse, Chat Loop)"];
    
    CLI -- Initializes & Uses --> AppLogger["app_logger.py<br>(Logging Setup & Control)"];
    CLI -- Instantiates --> AppConfig_Instance["AppConfig Instance<br>(from config.py)"];
    CLI -- Instantiates & Runs --> WorkflowEngine_Instance["WorkflowEngine Instance<br>(from engine.py)"];

    AppConfig_Instance -- Reads --> MCPServersJSON["mcp_servers.json<br>(Server Definitions)"];
    AppConfig_Instance -- Reads --> WorkflowsJSON["workflows.json<br>(Workflow Definitions)"];
    AppConfig_Instance -- Reads Env --> DotEnv[".env / OS Env<br>(API Keys)"];

    subgraph CoreLogic
        WorkflowEngine_Instance -- Uses Config from --> AppConfig_Instance;
        WorkflowEngine_Instance -- Uses --> LLMService_Instance["LLMService Instance<br>(from services.py)"];
        WorkflowEngine_Instance -- Manages --> MCPService_Instances["Dict[str, MCPService Instance]<br>(from services.py)"];
    end
    
    AppLogger -- Configures Logging For --> CLI;
    AppLogger -- Configures Logging For --> AppConfig_Instance;
    AppLogger -- Configures Logging For --> WorkflowEngine_Instance;
    AppLogger -- Configures Logging For --> LLMService_Instance;
    AppLogger -- Configures Logging For --> MCPService_Instances;

    style User fill:#cde,stroke:#333,stroke-width:2px,color:#000
    style CLI fill:#f9d,stroke:#333,stroke-width:2px,color:#000
    style MCPServersJSON fill:#dfd,stroke:#333,stroke-width:1px,color:#000
    style WorkflowsJSON fill:#dfd,stroke:#333,stroke-width:1px,color:#000
    style DotEnv fill:#dfd,stroke:#333,stroke-width:1px,color:#000
    style CoreLogic fill:#fff,stroke:#666,stroke-width:2px,stroke-dasharray: 5 5
```

**Diagram 2: `WorkflowEngine` Initialization and Service Setup**

This diagram shows what happens when `WorkflowEngine` is created and `setup_services()` is called.

```mermaid
sequenceDiagram
    participant CLI as "cli.py (main)"
    participant AppConfig as "AppConfig Instance"
    participant WorkflowEngine as "WorkflowEngine Instance"
    participant LLMService_Class as "LLMService (Class)"
    participant LLMService_Inst as "LLMService (Instance)"
    participant MCPService_Class as "MCPService (Class)"
    participant MCPService_Weather as "MCPService ('weather')"
    participant MCPService_Context7 as "MCPService ('context7')"
    participant ExitStack as "AsyncExitStack<br>(in WorkflowEngine)"
    participant WeatherServerProc as "Weather MCP Server Process"
    participant Context7ServerProc as "Context7 MCP Server Process"

    CLI->>AppConfig: Get Workflow Config ('multi_tool_agent')
    AppConfig-->>CLI: wf_config (model, mcp_servers_used, etc.)
    CLI->>WorkflowEngine: __init__('multi_tool_agent', AppConfig)
    WorkflowEngine->>AppConfig: Get API Key
    AppConfig-->>WorkflowEngine: GOOGLE_API_KEY
    WorkflowEngine->>LLMService_Class: Instantiate LLMService(model, api_key)
    LLMService_Class-->>LLMService_Inst: self.llm_service
    LLMService_Inst-->>WorkflowEngine: LLMService ready

    CLI->>WorkflowEngine: await setup_services()
    WorkflowEngine->>WorkflowEngine: Log "Setting up services..."
    
    loop For each server_name in wf_config['mcp_servers_used'] (e.g., "weather", "context7")
        WorkflowEngine->>AppConfig: Get MCP Server Config (server_name)
        AppConfig-->>WorkflowEngine: server_config (command, args)
        
        WorkflowEngine->>MCPService_Class: Instantiate MCPService(server_name, server_config, self.exit_stack)
        alt server_name is "weather"
            MCPService_Class-->>MCPService_Weather: weather_service instance
            WorkflowEngine->>MCPService_Weather: await connect()
            MCPService_Weather->>ExitStack: Enters stdio_client context (spawns WeatherServerProc)
            MCPService_Weather->>ExitStack: Enters ClientSession context
            MCPService_Weather->>WeatherServerProc: Initialize & List Tools
            WeatherServerProc-->>MCPService_Weather: Tools (e.g., get_forecast)
            MCPService_Weather-->>WorkflowEngine: Connection OK
            WorkflowEngine->>WorkflowEngine: Add weather_service to self.mcp_services
            WorkflowEngine->>WorkflowEngine: Add weather tools to self.all_mcp_tools
        else server_name is "context7"
            MCPService_Class-->>MCPService_Context7: context7_service instance
            WorkflowEngine->>MCPService_Context7: await connect()
            MCPService_Context7->>ExitStack: Enters stdio_client context (spawns Context7ServerProc)
            MCPService_Context7->>ExitStack: Enters ClientSession context
            MCPService_Context7->>Context7ServerProc: Initialize & List Tools
            Context7ServerProc-->>MCPService_Context7: Tools (e.g., resolve-library-id)
            MCPService_Context7-->>WorkflowEngine: Connection OK
            WorkflowEngine->>WorkflowEngine: Add context7_service to self.mcp_services
            WorkflowEngine->>WorkflowEngine: Add context7 tools to self.all_mcp_tools
        end
    end
    WorkflowEngine->>WorkflowEngine: Log "Workflow services setup complete"
    WorkflowEngine-->>CLI: setup_services() complete
```

**Diagram 3: The elusive buggy seq diag:**
```mermaid
graph LR
    subgraph UserInteraction [User Interaction]
        CLI["cli.py<br>(Entry Point, ArgParser, Chat Loop)"]
    end

    subgraph ConfigurationManagement [Configuration Management]
        ConfigPY["config.py<br>(AppConfig: Loads JSONs, Env Vars)"]
        WorkflowsJSON["workflows.json<br>(Workflow Definitions)"]
        MCPServersJSON["mcp_servers.json<br>(MCP Server Definitions)"]
        DotEnv[".env / OS Env<br>(API Keys)"]
    end

    subgraph CoreExecutionEngine [Core Execution Engine]
        EnginePY["engine.py<br>(WorkflowEngine: Orchestrates query processing, turn management, state)"]
    end

    subgraph ServiceAbstractions [Service Abstractions]
        ServicesPY["services.py<br>(LLMService, MCPService)"]
    end
    
    subgraph ExternalServices [External Services]
        direction LR
        GeminiAPI["Google Gemini API<br>(LLM Endpoint)"]
        MCPServer_Weather["Weather MCP Server<br>(e.g., weather.py process)"]
        MCPServer_Context7["Context7 MCP Server<br>(e.g., npx @upstash/context7-mcp process)"]
        %% Add more MCP servers as needed
    end

    subgraph Logging [Logging Subsystem]
        AppLoggerPY["app_logger.py<br>(Logging Setup & Abstraction)"]
    end

    %% Relationships / Data Flow / Control Flow
    CLI -->|Uses for setup & control| AppLoggerPY
    CLI -->|Instantiates & Uses| ConfigPY
    CLI -->|Instantiates & Runs| EnginePY

    ConfigPY -->|Reads| WorkflowsJSON
    ConfigPY -->|Reads| MCPServersJSON
    ConfigPY -->|Reads| DotEnv

    EnginePY -->|Uses config from| ConfigPY
    EnginePY -->|Uses for LLM calls| ServicesPY
    EnginePY -->|Uses for Tool calls| ServicesPY
    EnginePY -->|Uses for logging| AppLoggerPY
    
    ServicesPY -->|Interacts with| GeminiAPI
    ServicesPY -->|Manages connections to & calls| MCPServer_Weather
    ServicesPY -->|Manages connections to & calls| MCPServer_Context7
    ServicesPY -->|Uses for logging| AppLoggerPY

    %% All components can potentially use AppLoggerPY for their logging
    ConfigPY -.->|Uses for logging| AppLoggerPY

    %% Styling (optional, for clarity)
    style UserInteraction fill:#e6e6fa,stroke:#333,stroke-width:2px
    style ConfigurationManagement fill:#f0e68c,stroke:#333,stroke-width:2px
    style CoreExecutionEngine fill:#add8e6,stroke:#333,stroke-width:2px
    style ServiceAbstractions fill:#90ee90,stroke:#333,stroke-width:2px
    style ExternalServices fill:#ffb6c1,stroke:#333,stroke-width:2px
    style Logging fill:#d3d3d3,stroke:#333,stroke-width:2px
```


 **Diagram 4: Class Diagram:**

 ```mermaid
 classDiagram
    class WorkflowEngine {
        -workflow_name: str
        -app_config: AppConfig
        -workflow_config: Dict
        -llm_service: LLMService
        -mcp_services: Dict[str, MCPService]
        -all_mcp_tools: List[Tool]
        -exit_stack: AsyncExitStack
        +__init__(workflow_name, app_config)
        +setup_services() async
        +process_user_query(user_query) async
        +close() async
    }
    
    class MCPService {
        -server_name: str
        -server_config: Dict
        -exit_stack: AsyncExitStack
        -session: ClientSession
        -stdio
        -input
        +__init__(server_name, server_config, exit_stack)
        +connect() async
        +get_tools() async
        +call_tool(tool_name, args) async
    }
    
    class LLMService {
        -model_name: str
        -genai_client
        +__init__(model_name, api_key)
        -_convert_mcp_tool_to_genai_function(mcp_tool)
        +prepare_tools_for_llm(mcp_tools)
        +generate_response(conversation_history, tool_config) async
    }
    
    class AppConfig {
        -mcp_config_path: str
        -workflows_config_path: str
        -mcp_servers: Dict
        -workflows: Dict
        -google_api_key: str
        +__init__(mcp_config_path, workflows_config_path)
        +get_mcp_server_config(server_name)
        +get_workflow_config(workflow_name)
        +list_workflows()
    }
    
    class Tool {
        +name: str
        +description: str
        +inputSchema: Dict
    }
    
    WorkflowEngine --> AppConfig : uses
    WorkflowEngine --> LLMService : uses
    WorkflowEngine --> MCPService : uses multiple
    LLMService ..> Tool : converts
    MCPService ..> Tool : provides
```

**Diagram 5: Component Diagram**

```mermaid
flowchart TB
    subgraph User
        CLI[cli.py]
    end
    
    subgraph AppCore
        Engine[engine.py<br>WorkflowEngine]
        Config[config.py<br>AppConfig]
        AppLogger[app_logger.py]
    end
    
    subgraph Services
        MCPSrv[services.py<br>MCPService]
        LLMSrv[services.py<br>LLMService]
    end
    
    subgraph ExternalSystems
        MCPServers[External MCP Servers]
        GoogleGenAI[Google GenAI API]
    end
    
    CLI -- "1. Starts workflow<br>args parsing" --> Config
    CLI -- "2. Creates engine<br>3. Runs chat loop" --> Engine
    Engine -- "Logging" --> AppLogger
    CLI -- "Logging" --> AppLogger
    Engine -- "Fetches config" --> Config
    Engine -- "Creates & uses" --> LLMSrv
    Engine -- "Creates & uses" --> MCPSrv
    MCPSrv -- "Connects to" --> MCPServers
    MCPSrv -- "Gets tools & calls tools" --> MCPServers
    LLMSrv -- "Makes API requests" --> GoogleGenAI
    MCPSrv -- "Logging" --> AppLogger
    LLMSrv -- "Logging" --> AppLogger
    
    classDef core fill:#f9f,stroke:#333,stroke-width:2px,color:#000;
    classDef services fill:#bbf,stroke:#333,stroke-width:1px,color:#000;
    classDef external fill:#bfb,stroke:#333,stroke-width:1px,color:#000;
    classDef userFacing fill:#fbb,stroke:#333,stroke-width:2px,color:#000;
    
    class Engine,Config,AppLogger core;
    class MCPSrv,LLMSrv services;
    class MCPServers,GoogleGenAI external;
    class CLI userFacing;
```

**Diagram 6: App Startup Sequence Diag**

```mermaid
sequenceDiagram
    participant User
    participant CLI as "cli.py main()"
    participant AppConfig as "AppConfig"
    participant Engine as "WorkflowEngine"
    participant Logger as "app_logger"
    participant MCPServices as "MCPService(s)"
    participant MCPServers as "MCP Server(s)"
    
    User->>CLI: Run with arguments
    CLI->>Logger: setup_logging(level, console_level, log_file)
    Logger-->>CLI: Loggers configured
    
    CLI->>AppConfig: Create(mcp_cfg_path, workflows_cfg_path)
    AppConfig->>AppConfig: Load configs from files/defaults
    AppConfig-->>CLI: app_config instance
    
    alt --list-workflows flag
        CLI->>AppConfig: list_workflows()
        AppConfig-->>CLI: workflows list
        CLI->>User: Display workflows & exit
    else normal operation
        CLI->>Engine: Create(workflow_name, app_config)
        Engine->>AppConfig: get_workflow_config(workflow_name)
        AppConfig-->>Engine: workflow_config
        Engine->>Engine: Init LLMService(model, api_key)
        
        CLI->>Engine: await setup_services()
        
        loop For each MCP server in workflow config
            Engine->>AppConfig: get_mcp_server_config(server_name)
            AppConfig-->>Engine: server_config
            Engine->>MCPServices: Create(server_name, server_config, exit_stack)
            Engine->>MCPServices: await connect()
            MCPServices->>MCPServers: Initialize connection
            MCPServers-->>MCPServices: Connection established
            MCPServices->>MCPServers: list_tools()
            MCPServers-->>MCPServices: Available tools
            MCPServices-->>Engine: Connected service with tools
        end
        
        alt --query argument provided
            CLI->>Engine: await process_user_query(args.query)
            Engine->>User: Display response & exit
        else interactive mode
            CLI->>CLI: await run_chat_loop(engine)
            loop Until user types 'quit'
                CLI->>User: Prompt for query
                User->>CLI: Enter query
                CLI->>Engine: await process_user_query(query)
                Engine-->>CLI: response_text
                CLI->>User: Display response
            end
        end
    end
    
    CLI->>Engine: await engine.close()
    Engine->>MCPServices: Close connections
    CLI->>Logger: shutdown()
```

**Diagram 7: Logging Architecture **

```mermaid
flowchart LR
    classDef appLoggers fill:#f9f,stroke:#333,stroke-width:1px,color:#000;
    classDef handlers fill:#bbf,stroke:#333,stroke-width:1px,color:#000;
    classDef logLevels fill:#bfb,stroke:#333,stroke-width:1px,color:#000;
    classDef helpers fill:#fbb,stroke:#333,stroke-width:1px,color:#000;
    
    Setup[setup_logging<br>function]
    
    subgraph "Logger Instances"
        Root[Root Logger]
        CLI[CLI_LOGGER<br>app.cli]
        CONFIG[CONFIG_LOGGER<br>app.config]
        ENGINE[ENGINE_LOGGER<br>app.engine]
        SERVICE[SERVICE_LOGGER<br>app.service]
        ThirdParty[Third-Party Loggers<br>Google API/httpx]
    end
    
    subgraph "Logger Helpers"
        CLI_Helpers[cli_log_debug<br>cli_log_info<br>cli_log_user<br>cli_log_warning<br>cli_log_error<br>cli_log_critical]
        ENGINE_Helpers[engine_log_debug<br>engine_log_info<br>engine_log_user<br>engine_log_warning<br>engine_log_error<br>engine_log_critical]
        CONFIG_Helpers[config_log_debug<br>config_log_info<br>config_log_warning<br>config_log_error]
        SERVICE_Helpers[service_log_debug<br>service_log_info<br>service_log_warning<br>service_log_error]
    end
    
    subgraph "Handlers"
        ConsoleHandler[Console Handler<br>- Configured by console_level_override<br>- Format varies by level]
        FileHandler["File Handler<br>- Always verbose (DEBUG)<br>- Detailed format"]
        NullHandler[Null Handler<br>- Used when logging disabled]
    end
    
    subgraph "Log Levels"
        LOG_LEVEL_QUIET["LOG_LEVEL_QUIET<br>(CRITICAL + 10)"]
        LOG_LEVEL_USER_INTERACTION["LOG_LEVEL_USER_INTERACTION<br>(INFO + 5)"]
        LOG_LEVEL_NORMAL["LOG_LEVEL_NORMAL<br>(INFO)"]
        LOG_LEVEL_VERBOSE["LOG_LEVEL_VERBOSE<br>(DEBUG)"]
    end
    
    CLI_Helpers --> CLI
    ENGINE_Helpers --> ENGINE
    CONFIG_Helpers --> CONFIG
    SERVICE_Helpers --> SERVICE
    
    Root --> ConsoleHandler
    Root --> FileHandler
    Root --> NullHandler
    
    CLI --> Root
    CONFIG --> Root
    ENGINE --> Root
    SERVICE --> Root
    ThirdParty --> Root
    
    Setup --> ConsoleHandler
    Setup --> FileHandler
    Setup --> NullHandler
    Setup --> Root
    
    LOG_LEVEL_QUIET -.-> Setup
    LOG_LEVEL_USER_INTERACTION -.-> Setup
    LOG_LEVEL_NORMAL -.-> Setup
    LOG_LEVEL_VERBOSE -.-> Setup
    
    class CLI,CONFIG,ENGINE,SERVICE,ThirdParty,Root appLoggers;
    class ConsoleHandler,FileHandler,NullHandler handlers;
    class LOG_LEVEL_QUIET,LOG_LEVEL_USER_INTERACTION,LOG_LEVEL_NORMAL,LOG_LEVEL_VERBOSE logLevels;
    class CLI_Helpers,ENGINE_Helpers,CONFIG_Helpers,SERVICE_Helpers helpers;
```

**Diagram 8: MCP Tool Data Flow**

```mermaid
flowchart TD
    classDef mcpComponents fill:#f9f,stroke:#333,stroke-width:1px,color:#000;
    classDef llmComponents fill:#bbf,stroke:#333,stroke-width:1px,color:#000;
    classDef dataStructure fill:#bfb,stroke:#333,stroke-width:1px,color:#000;
    
    MCPServer[External MCP Server<br>with tool definitions]
    MCPService[MCPService]
    MCPTools[MCP Tools List<br>- name<br>- description<br>- inputSchema]
    
    GenAIFunctions[GenAI Function Declarations]
    LLMService[LLMService]
    LLMToolConfig[GenAI Tool Config]
    
    LLMResponse[LLM Response<br>with function_call]
    FunctionParams[Function Call Parameters]
    ToolResult[Tool Execution Result]
    FunctionResponse[Function Response<br>for LLM]
    
    subgraph "MCP Tool Registration"
        MCPServer -->|"connect()"| MCPService
        MCPService -->|"get_tools()"| MCPTools
    end
    
    subgraph "Tool Conversion for LLM"
        MCPTools -->|"prepare_tools_for_llm()"| LLMService
        LLMService -->|"_convert_mcp_tool_to_genai_function()"| GenAIFunctions
        GenAIFunctions -->|wrapped in Tool objects| LLMToolConfig
    end
    
    subgraph "Tool Execution Flow"
        LLMToolConfig -->|sent with LLM request| LLMResponse
        LLMResponse -->|extracts part.function_call| FunctionParams
        FunctionParams -->|"call_tool(tool_name, args)"| MCPService
        MCPService -->|forwards to MCP server| MCPServer
        MCPServer -->|executes tool<br>returns result| MCPService
        MCPService -->|returns result| ToolResult
        ToolResult -->|formatted as| FunctionResponse
        FunctionResponse -->|added to conversation history| LLMService
    end
    
    class MCPServer,MCPService,MCPTools mcpComponents;
    class GenAIFunctions,LLMService,LLMToolConfig,LLMResponse llmComponents;
    class FunctionParams,ToolResult,FunctionResponse dataStructure;
```

# HIGHER LEVEL DIAGS (MAYBE BETTER FOR YOU)

**Diagram 9: MCP Client Architecture**

```mermaid
flowchart TD
    subgraph Client ["MCP Client Application"]
        CLI[CLI Interface] --> Engine[WorkflowEngine]
        Config[AppConfig] --> Engine
        Engine --> LLM[LLMService]
        Engine --> MCP1[MCPService 1]
        Engine --> MCP2[MCPService 2]
        Engine --> MCPn[MCPService n]
        Logger[AppLogger] --- CLI
        Logger --- Engine
        Logger --- LLM
        Logger --- MCP1
        Logger --- MCP2
        Logger --- MCPn
    end

    subgraph External ["External Systems"]
        GoogleLLM[Google Gemini API]
        MCP_Server1[MCP Server 1]
        MCP_Server2[MCP Server 2]  
        MCP_Servern[MCP Server n]
    end

    %% Data flow connections
    LLM <-->|API calls| GoogleLLM
    MCP1 <-->|Tool calls| MCP_Server1
    MCP2 <-->|Tool calls| MCP_Server2
    MCPn <-->|Tool calls| MCP_Servern
    
    %% User interaction
    User((User)) <-->|Queries & Responses| CLI
    LogFile[(Log File)] <-- Logging --> Logger
```

**Diagram 10: MCP Client Data Flow**

```mermaid
flowchart LR
    subgraph Workflow ["Single Workflow Execution"]
        direction TB
        User((User)) -->|Query| Engine[WorkflowEngine]
        Engine -->|1 Initial prompt| LLM[LLM Service]
        LLM -->|2 Response with tool call| Engine
        Engine -->|3 Tool execution request| MCP[MCP Services]
        MCP -->|4 Tool execution result| Engine
        Engine -->|5 Tool result| LLM
        LLM -->|6 Final response| Engine
        Engine -->|7 Response text| User
    end
    
    subgraph External ["External Services"]
        direction LR
        GoogleLLM[Google Gemini API]
        Tool1[Calculator Server]
        Tool2[Web Search Server]
        Tool3[Data Analysis Server]
    end
    
    LLM <-->|API calls| GoogleLLM
    MCP <-->|Command execution| Tool1
    MCP <-->|Command execution| Tool2
    MCP <-->|Command execution| Tool3
```