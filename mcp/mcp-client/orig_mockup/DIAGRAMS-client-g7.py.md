Okay, this is a comprehensive script! Let's break it down into several Mermaid diagrams to illustrate the different flows and component interactions.

I'll provide:

1.  **High-Level System Overview:** Shows the main components and their general interaction.
2.  **Initialization and Connection Flow (Sequence Diagram):** Details the script startup, config loading, and connection to an MCP server.
3.  **`ConfigManager` Logic (Flowchart):** Explains how `mcp.json` is found and parsed.
4.  **`connect_to_server` Logic (Flowchart):** Details the decision-making for connecting via server name or script path.
5.  **Core `process_query` Loop (Sequence Diagram):** This is the heart of the interaction with GenAI and MCP tools. This will be the most detailed.
6.  **Tool Conversion Logic (Simplified Flowchart/Notes):** `_convert_mcp_tool_to_genai_function_declaration`.
7.  **Cleanup Flow (Sequence Diagram):** How resources are released.

Let's include specifics for `weather` and `context7` where applicable.

---

### 1. High-Level System Overview

```mermaid
graph TD
    UserInterface["User (CLI)"] -- query/command --> MainScript["main.py (Async Orchestrator)"];
    MainScript -- instantiates & uses --> MCPClient["MCPClient Instance"];
    
    subgraph Configuration
        MCPClient -- uses --> ConfigManager["ConfigManager"];
        ConfigManager -- reads --> DotMCPJson["(.mcp.json / mcp.json)"];
    end

    subgraph MCP_Communication
        MCPClient -- manages --> MCPSession["mcp.ClientSession"];
        MCPSession -- via stdio_client --> StdioTransport["Stdio Transport"];
        StdioTransport -- communicates with --> MCPServerProcess["MCP Server Process (e.g., weather.py or context7 CLI)"];
        DotMCPJson -- defines --> MCPServerProcess;
    end
    
    subgraph GenAI_Interaction
        MCPClient -- uses --> GenAIClient["google.genai.Client"];
        GenAIClient -- API calls --> GoogleGenAI_API["Google GenAI API (Gemini Model)"];
    end

    MCPClient -- coordinates --> GenAI_Interaction;
    MCPClient -- coordinates --> MCP_Communication;

    style UserInterface fill:#cde,stroke:#333,stroke-width:2px
    style MainScript fill:#f9d,stroke:#333,stroke-width:2px
    style DotMCPJson fill:#dfd,stroke:#333,stroke-width:2px
    style MCPServerProcess fill:#dfd,stroke:#333,stroke-width:2px
    style GoogleGenAI_API fill:#ffd,stroke:#333,stroke-width:2px
```

---

### 2. Initialization and Connection Flow (Sequence Diagram)

This diagram shows the startup, argument parsing, `MCPClient` instantiation, GenAI client setup, and connection to a specific MCP server (e.g., "weather").

```mermaid
sequenceDiagram
    participant User
    participant main_script as "main.py"
    participant argparse
    participant MCPClient_Class as "MCPClient (Class)"
    participant ConfigManager_Class as "ConfigManager (Class)"
    participant mcp_client_instance as "mcp_client (Instance)"
    participant config_manager_instance as "config_manager (Instance)"
    participant OS_Env as "OS Environment"
    participant GenAI_SDK as "google.genai"
    participant MCP_Lib as "mcp Library (stdio_client, ClientSession)"
    participant MCP_Server_Process as "MCP Server Process\n(e.g., weather.py)"
    participant FS as "File System (.mcp.json)"

    User->>main_script: python client.py --server weather
    main_script->>argparse: Parse arguments
    argparse-->>main_script: args (server="weather", config=None)

    alt No --server or --script
        main_script->>ConfigManager_Class: Instantiate (temp_config_mgr)
        ConfigManager_Class->>config_manager_instance: __init__(config_path=None)
        config_manager_instance->>config_manager_instance: _find_config_path()
        config_manager_instance->>FS: Search for .mcp.json
        FS-->>config_manager_instance: Found .mcp.json
        config_manager_instance->>config_manager_instance: load_config()
        config_manager_instance->>FS: Read .mcp.json
        FS-->>config_manager_instance: JSON content
        config_manager_instance->>config_manager_instance: _validate_config()
        config_manager_instance-->>ConfigManager_Class: temp_config_mgr instance
        ConfigManager_Class-->>main_script: temp_config_mgr instance
        main_script->>config_manager_instance: list_servers()
        config_manager_instance-->>main_script: ["weather", "context7"]
        main_script->>User: Print help with available servers & exit
    end

    main_script->>MCPClient_Class: Instantiate MCPClient(config_path=args.config)
    MCPClient_Class->>mcp_client_instance: __init__(config_path=None)
    mcp_client_instance->>ConfigManager_Class: Instantiate ConfigManager(config_path=None)
    ConfigManager_Class->>config_manager_instance: __init__()
    config_manager_instance->>config_manager_instance: _find_config_path()
    config_manager_instance->>FS: Search for .mcp.json
    FS-->>config_manager_instance: Path to .mcp.json
    config_manager_instance->>config_manager_instance: load_config()
    config_manager_instance->>FS: Read .mcp.json
    FS-->>config_manager_instance: JSON content for weather, context7
    config_manager_instance->>config_manager_instance: _validate_config()
    config_manager_instance-->>mcp_client_instance: config_manager ready
    
    mcp_client_instance->>OS_Env: Get GOOGLE_API_KEY
    OS_Env-->>mcp_client_instance: API Key
    mcp_client_instance->>GenAI_SDK: genai.Client(api_key=API_Key)
    GenAI_SDK-->>mcp_client_instance: genai_client (self.genai_client)
    mcp_client_instance-->>main_script: client (MCPClient instance)

    main_script->>mcp_client_instance: connect_to_server(server_name="weather")
    mcp_client_instance->>config_manager_instance: get_server_config("weather")
    config_manager_instance-->>mcp_client_instance: Weather server config (command="python", args=["../weather/weather.py"], ...)
    
    mcp_client_instance->>MCP_Lib: StdioServerParameters(command="python", args=["../weather/weather.py"], env=...)
    MCP_Lib-->>mcp_client_instance: server_params
    
    mcp_client_instance->>MCP_Lib: stdio_client(server_params)
    Note over MCP_Lib, MCP_Server_Process: Spawns 'python ../weather/weather.py'
    MCP_Lib-->>mcp_client_instance: stdio_transport (stdio, input streams)
    mcp_client_instance->>mcp_client_instance: self.stdio, self.input = stdio_transport
    
    mcp_client_instance->>MCP_Lib: ClientSession(self.stdio, self.input)
    MCP_Lib-->>mcp_client_instance: session (self.session)
    
    mcp_client_instance->>mcp_client_instance: self.session.initialize()
    Note over mcp_client_instance, MCP_Server_Process: Handshake with server
    mcp_client_instance-->>mcp_client_instance: Initialization OK
    
    mcp_client_instance->>mcp_client_instance: self.session.list_tools()
    mcp_client_instance-->>MCP_Server_Process: Request for tool list
    MCP_Server_Process-->>mcp_client_instance: Tool list (e.g., get_weather_forecast)
    mcp_client_instance->>main_script: Connection successful, tools listed
    
    main_script->>mcp_client_instance: chat_loop()
    mcp_client_instance->>User: "MCP Client ... Started!"
    mcp_client_instance->>User: "Query: "
```

---

### 3. `ConfigManager` Logic (Flowchart)

Illustrates `__init__`, `_find_config_path`, `load_config`, and `_validate_config`.

```mermaid
graph TD
    Start["ConfigManager.__init__(config_path)"] --> FindPath{config_path provided?};
    FindPath -- Yes --> SetPathProvided["self.config_path = config_path"];
    FindPath -- No --> CallFindConfig["self._find_config_path()"];
    CallFindConfig --> CheckPaths["Iterate possible_paths (cwd/.mcp.json, ..., home/.mcp/mcp.json)"];
    CheckPaths --> PathExists{"Path.exists()?"};
    PathExists -- Yes --> SetFoundPath["self.config_path = found_path\nLog 'Found configuration'"];
    PathExists -- No --> NextPathOrEnd{"More paths to check?"};
    NextPathOrEnd -- Yes --> CheckPaths;
    NextPathOrEnd -- No --> SetEmptyPath["self.config_path = ''\nLog 'No mcp.json found'"];
    
    SetPathProvided --> CallLoadConfig;
    SetFoundPath --> CallLoadConfig["self.load_config()"];
    SetEmptyPath --> CallLoadConfig;

    CallLoadConfig --> CheckConfigPathExists{"self.config_path and Path(self.config_path).exists()?"};
    CheckConfigPathExists -- No --> SetDefaultConfig["self.config = {'mcpServers': {}}\nLog 'No config file'"];
    CheckConfigPathExists -- Yes --> TryLoad["Try open and json.load(f)"];
    TryLoad -- Success --> SetLoadedConfig["self.config = loaded_json\nLog 'Loaded configuration'"];
    TryLoad -- "json.JSONDecodeError" --> ErrorJSON["Log error, raise ValueError"];
    TryLoad -- "Other Exception" --> ErrorLoad["Log error, raise Exception"];
    
    SetLoadedConfig --> CallValidateConfig["self._validate_config()"];
    CallValidateConfig --> CheckMcpServersKey{"'mcpServers' in self.config?"};
    CheckMcpServersKey -- No --> AddMcpServersKey["self.config['mcpServers'] = {}\nLog warning"];
    CheckMcpServersKey -- Yes --> IterateServers;
    AddMcpServersKey --> IterateServers["For server_name, server_config in mcpServers.items()"];
    
    IterateServers --> IsDict{"server_config is dict?"};
    IsDict -- No --> ErrorInvalidServerConfig["Raise ValueError 'must be a dictionary'"];
    IsDict -- Yes --> HasCommand{"'command' in server_config?"};
    HasCommand -- No --> ErrorMissingCommand["Raise ValueError 'missing command'"];
    HasCommand -- Yes --> HasArgs{"'args' in server_config and is list?"};
    HasArgs -- No --> ErrorMissingArgs["Raise ValueError 'missing or invalid args'"];
    HasArgs -- Yes --> HasTransportType{"'transportType' in server_config?"};
    HasTransportType -- No --> SetDefaultTransport["server_config['transportType'] = 'stdio'"];
    HasTransportType -- Yes --> CheckTransportType;
    SetDefaultTransport --> CheckTransportType{"server_config['transportType'] == 'stdio'?"};
    CheckTransportType -- No --> ErrorUnsupportedTransport["Raise ValueError 'Unsupported transportType'"];
    CheckTransportType -- Yes --> HasEnv{"'env' in server_config?"};
    HasEnv -- Yes --> IsEnvDict{"server_config['env'] is dict?"};
    IsEnvDict -- No --> ErrorInvalidEnv["Raise ValueError 'env must be a dictionary'"];
    IsEnvDict -- Yes --> NextServerOrEndValidation;
    HasEnv -- No --> NextServerOrEndValidation{"More servers or end validation loop?"};
    
    NextServerOrEndValidation -- More Servers --> IterateServers;
    NextServerOrEndValidation -- End Validation Loop --> EndConfigInit["ConfigManager Initialized"];
    
    SetDefaultConfig --> EndConfigInit;
    ErrorJSON --> EndWithError["End with Error"];
    ErrorLoad --> EndWithError;
    ErrorInvalidServerConfig --> EndWithError;
    ErrorMissingCommand --> EndWithError;
    ErrorMissingArgs --> EndWithError;
    ErrorUnsupportedTransport --> EndWithError;
    ErrorInvalidEnv --> EndWithError;
```

---

### 4. `connect_to_server` Logic (Flowchart)

```mermaid
graph TD
    Start["MCPClient.connect_to_server(server_name, server_script_path)"] --> CheckBothArgs{server_name AND server_script_path?};
    CheckBothArgs -- Yes --> ErrorBothArgs["Raise ValueError 'Cannot specify both'"];
    CheckBothArgs -- No --> CheckNeitherArg{NOT server_name AND NOT server_script_path?};
    CheckNeitherArg -- Yes --> ErrorNeitherArg["Raise ValueError 'Must specify either'"];
    CheckNeitherArg -- No --> CheckServerName{server_name specified?};

    CheckServerName -- Yes --> GetConfig["config = self.config_manager.get_server_config(server_name)"];
    GetConfig --> ConfigFound{config?};
    ConfigFound -- No --> ErrorNoConfig["Raise ValueError 'No configuration found'"];
    ConfigFound -- Yes --> CreateParamsFromConfig["server_params = StdioServerParameters(\n  command=config['command'],\n  args=config['args'],\n  env=config.get('env')\n)\n(e.g., for 'weather' or 'context7')"];
    CreateParamsFromConfig --> Connect;

    CheckServerName -- No (server_script_path specified) --> ResolvePath["abs_script_path = Path(server_script_path).resolve()"];
    ResolvePath --> ScriptExists{"Path(abs_script_path).exists()?"};
    ScriptExists -- No --> ErrorScriptNotFound["Raise FileNotFoundError"];
    ScriptExists -- Yes --> CheckExtension{abs_script_path ends with '.py' or '.js' ?};
    CheckExtension -- No --> ErrorInvalidExtension["Raise ValueError 'Server script must be .py or .js'"];
    CheckExtension -- Yes --> SetCommand{"command = sys.executable (if .py) or 'node' (if .js)"};
    SetCommand --> CreateParamsFromScript["server_params = StdioServerParameters(\n  command=command,\n  args=[abs_script_path],\n  env=None\n)"];
    CreateParamsFromScript --> Connect["stdio_transport = await stdio_client(server_params)\n(Enters AsyncExitStack context)"];
    
    Connect --> SetStdio["self.stdio, self.input = stdio_transport"];
    SetStdio --> CreateSession["self.session = await ClientSession(self.stdio, self.input)\n(Enters AsyncExitStack context)"];
    CreateSession --> InitializeSession["await self.session.initialize()"];
    InitializeSession --> ListTools["response = await self.session.list_tools()"];
    ListTools --> LogTools["Log/Print connected tools"];
    LogTools --> EndConnect["Connection Successful"];

    ErrorBothArgs --> EndWithError;
    ErrorNeitherArg --> EndWithError;
    ErrorNoConfig --> EndWithError;
    ErrorScriptNotFound --> EndWithError;
    ErrorInvalidExtension --> EndWithError;
    Connect -- Exception --> ErrorConnectFailed["Log 'Failed to connect', Raise Exception"] --> EndWithError["End with Error"];
    EndConnect --> End["End connect_to_server"];
```

---

### 5. Core `process_query` Loop (Sequence Diagram)

This diagram details the interaction between the `MCPClient`, the GenAI API, and the MCP Server during a single query processing, including potential tool calls.

```mermaid
sequenceDiagram
    participant User
    participant MCPClient_instance as "MCPClient"
    participant MCP_Session as "self.session (MCP)"
    participant MCP_Server_Process as "MCP Server\n(e.g., weather or context7)"
    participant GenAI_SDK_aio as "self.genai_client.aio.models"
    participant Google_GenAI_API as "Google GenAI API"

    User->>MCPClient_instance: Enters query (e.g., "What's the weather in London?")
    MCPClient_instance->>MCPClient_instance: process_query(query) initiated
    MCPClient_instance->>MCP_Session: list_tools()
    MCP_Session->>MCP_Server_Process: (Internal: Request tool definitions)
    MCP_Server_Process-->>MCP_Session: (Internal: Tool definitions)
    MCP_Session-->>MCPClient_instance: mcp_tools_response (e.g., [get_weather_forecast_tool])
    
    MCPClient_instance->>MCPClient_instance: For each mcp_tool: _convert_mcp_tool_to_genai_function_declaration(tool)
    Note right of MCPClient_instance: Converts MCP schema to GenAI schema
    MCPClient_instance-->>MCPClient_instance: genai_tool_declarations (list of GenAI function defs)
    
    MCPClient_instance->>GenAI_SDK_aio: types.Tool(function_declarations=genai_tool_declarations)
    GenAI_SDK_aio-->>MCPClient_instance: gemini_tools
    MCPClient_instance->>GenAI_SDK_aio: types.GenerateContentConfig(tools=gemini_tools)
    GenAI_SDK_aio-->>MCPClient_instance: current_tool_config
    
    Note over MCPClient_instance: Initializes conversation_history = [Content(parts=[Part(text=query)], role="user")]

    loop Max 5 Turns
        MCPClient_instance->>GenAI_SDK_aio: generate_content(model, contents=conversation_history, config=current_tool_config)
        GenAI_SDK_aio->>Google_GenAI_API: API Request (query + tools)
        Google_GenAI_API-->>GenAI_SDK_aio: API Response
        GenAI_SDK_aio-->>MCPClient_instance: response (candidates)

        alt No candidates in response
            MCPClient_instance->>MCPClient_instance: Log warning, prepare error message
            MCPClient_instance-->>User: "AI model returned no response candidates."
        else Candidates available
            Note over MCPClient_instance: model_response_content = response.candidates[0].content
            Note over MCPClient_instance: conversation_history.append(model_response_content) (adds LLM's turn)

            opt Text part in model_response_content.parts
                MCPClient_instance->>MCPClient_instance: Extract part.text
                MCPClient_instance->>User: (Prints intermediate text if substantive)
                Note over MCPClient_instance: final_response_text_parts.append(part.text)
            end

            alt Function call part in model_response_content.parts
                MCPClient_instance->>MCPClient_instance: Extract function_call (name, args)
                Note over MCPClient_instance: tool_name="get_weather_forecast", tool_args={"location": "London"}
                MCPClient_instance->>User: "[LLM wants to call tool 'get_weather_forecast'...]"
                
                MCPClient_instance->>MCP_Session: call_tool(tool_name, tool_args_dict)
                MCP_Session->>MCP_Server_Process: Execute "get_weather_forecast" with {"location": "London"}
                MCP_Server_Process-->>MCP_Session: tool_result.content (e.g., {"forecast": "Sunny, 20C"})
                MCP_Session-->>MCPClient_instance: mcp_tool_result
                
                MCPClient_instance->>User: "[Tool 'get_weather_forecast' executed by MCP...]"
                MCPClient_instance->>MCPClient_instance: Prepare tool_result_content_for_llm (e.g., {"forecast": "Sunny, 20C"})
                
                MCPClient_instance->>GenAI_SDK_aio: types.Part.from_function_response(name=tool_name, response=tool_result_content_for_llm)
                GenAI_SDK_aio-->>MCPClient_instance: tool_response_part_for_history
                Note over MCPClient_instance: conversation_history.append(Content(parts=[tool_response_part_for_history], role="user"))
                Note over MCPClient_instance: Continue to next loop iteration
            else No function call
                MCPClient_instance->>MCPClient_instance: Log "No function call... Assuming final textual response."
                opt No text parts collected and response.text exists
                    MCPClient_instance->>MCPClient_instance: final_response_text_parts.append(response.text)
                end
            end
        end
    end
    
    opt Max turns reached and no text gathered
        MCPClient_instance->>MCPClient_instance: final_response_text_parts.append("[Max interaction turns reached...]")
    end

    MCPClient_instance->>MCPClient_instance: final_response = "".join(final_response_text_parts).strip()
    MCPClient_instance-->>User: Displays final_response
```

---

### 6. Tool Conversion Logic (`_convert_mcp_tool_to_genai_function_declaration`)

This is more of a data mapping process. A simplified flowchart/notes:

```mermaid
graph TD
    Start["_convert_mcp_tool_to_genai_function_declaration(mcp_tool)"] --> InitSchema["parameters_schema = {'type': 'object', 'properties': {}}"];
    
    InitSchema --> CheckInputSchema{"mcp_tool.inputSchema and is dict?"};
    CheckInputSchema -- Yes --> IterateProps["For name, schema_prop in mcp_tool.inputSchema.properties.items()"];
    IterateProps --> PropValid{"schema_prop is dict?"};
    PropValid -- No --> SkipProp["Log warning, skip property"] --> NextPropOrEndLoop;
    PropValid -- Yes --> GetType["prop_type_str = schema_prop.get('type', 'string').lower()"];
    GetType --> ValidateType{"prop_type_str in valid_types (string, number, ...)? "};
    ValidateType -- No --> DefaultType["prop_type_str = 'string'\nLog warning"];
    ValidateType -- Yes --> CreateCurrentProp["current_prop_schema = {'type': prop_type_str}"];
    DefaultType --> CreateCurrentProp;
    
    CreateCurrentProp --> AddDescription{"'description' in schema_prop?"};
    AddDescription -- Yes --> SetDescription["current_prop_schema['description'] = schema_prop['description']"];
    AddDescription -- No --> AddEnum;
    SetDescription --> AddEnum{"'enum' in schema_prop and is list?"};
    AddEnum -- Yes --> SetEnum["current_prop_schema['enum'] = schema_prop['enum']"];
    AddEnum -- No --> CheckArray;
    SetEnum --> CheckArray;

    CheckArray{"prop_type_str == 'array'?"};
    CheckArray -- Yes --> CheckArrayItems{"'items' in schema_prop and is dict?"};
    CheckArrayItems -- Yes --> SetArrayItems["current_prop_schema['items'] = schema_prop['items']"];
    CheckArrayItems -- No --> DefaultArrayItems["current_prop_schema['items'] = {'type': 'string'}\nLog debug"];
    SetArrayItems --> AddToGenAIProps;
    DefaultArrayItems --> AddToGenAIProps;
    CheckArray -- No --> AddToGenAIProps["genai_properties[name] = current_prop_schema"];
    
    AddToGenAIProps --> NextPropOrEndLoop{"More properties?"};
    NextPropOrEndLoop -- Yes --> IterateProps;
    NextPropOrEndLoop -- No --> SetGenAIProps["parameters_schema['properties'] = genai_properties"];
    
    SetGenAIProps --> GetRequired["required_list = mcp_tool.inputSchema.get('required', [])"];
    GetRequired --> ValidateRequired{"required_list is list of strings and not empty?"};
    ValidateRequired -- Yes --> SetRequired["parameters_schema['required'] = required_list"];
    ValidateRequired -- No --> SetToolDescription;
    SetRequired --> SetToolDescription;

    CheckInputSchema -- No --> LogNoSchema["Log warning 'No input schema...'"] --> SetToolDescription;

    SetToolDescription --> CheckMCPDesc{"mcp_tool.description valid and not empty?"};
    CheckMCPDesc -- Yes --> UseMCPDesc["description = mcp_tool.description"];
    CheckMCPDesc -- No --> DefaultDesc["description = f'Tool to perform {mcp_tool.name}'\nLog warning"];
    
    UseMCPDesc --> AssembleDeclaration;
    DefaultDesc --> AssembleDeclaration["Return GenAI Function Declaration:\n{\n  'name': mcp_tool.name,\n  'description': description,\n  'parameters': parameters_schema\n}"];
    AssembleDeclaration --> End["End Conversion"];
```

---

### 7. Cleanup Flow (Sequence Diagram)

```mermaid
sequenceDiagram
    participant main_script as "main.py (finally block)"
    participant mcp_client_instance as "MCPClient Instance"
    participant AsyncExitStack as "self.exit_stack"
    participant MCP_Session as "self.session (Managed by ExitStack)"
    participant StdioTransport as "self.stdio/input (Managed by ExitStack)"
    participant MCP_Server_Process as "MCP Server Process"

    main_script->>mcp_client_instance: cleanup()
    mcp_client_instance->>AsyncExitStack: aclose()
    
    Note over AsyncExitStack, MCP_Session: ExitStack calls __aexit__ on ClientSession
    AsyncExitStack->>MCP_Session: (Implicitly) Close/Cleanup
    MCP_Session->>MCP_Server_Process: (Sends shutdown/close if applicable)
    
    Note over AsyncExitStack, StdioTransport: ExitStack calls __aexit__ on stdio_client transport
    AsyncExitStack->>StdioTransport: (Implicitly) Close streams
    StdioTransport->>MCP_Server_Process: (Closes stdin, process might terminate)

    AsyncExitStack-->>mcp_client_instance: Cleanup complete
    mcp_client_instance-->>main_script: Cleanup finished
    main_script->>main_script: Log "Main function finished."
```

---

These diagrams should provide a good understanding of the script's internal flows, decision points, and interactions with external services like the MCP servers and the Google GenAI API. The inclusion of `weather` and `context7` server details from your `.mcp.json` helps ground the examples.
