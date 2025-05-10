import asyncio
import os
from typing import Optional, Dict, Any, List
from contextlib import AsyncExitStack
import logging
import sys
import traceback
import json
from pathlib import Path
import argparse

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('client_debug.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

DEFAULT_GEMINI_MODEL = "gemini-1.5-flash-latest"

class ConfigManager:
    def __init__(self, config_path: Optional[str] = None):
        self.config: Dict[str, Any] = {}
        self.config_path = config_path or self._find_config_path()
        self.load_config()

    def _find_config_path(self) -> str:
        possible_paths = [
            Path.cwd() / ".mcp.json",
            Path.cwd() / "mcp.json",
            Path.home() / ".config" / "mcp" / "mcp.json",
            Path.home() / ".mcp" / "mcp.json",
        ]
        for path in possible_paths:
            if path.exists():
                logger.debug(f"Found configuration file at {path}")
                return str(path)
        logger.warning("No mcp.json or .mcp.json found. Using default configuration.")
        return ""

    def load_config(self):
        if not self.config_path or not Path(self.config_path).exists():
            logger.debug("No configuration file provided or found.")
            self.config = {"mcpServers": {}}
            return

        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            self._validate_config()
            logger.info(f"Loaded configuration from {self.config_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {self.config_path}: {str(e)}")
            raise ValueError(f"Invalid JSON in {self.config_path}: {str(e)}")
        except Exception as e:
            logger.error(f"Error loading {self.config_path}: {str(e)}")
            raise

    def _validate_config(self):
        if "mcpServers" not in self.config:
            self.config["mcpServers"] = {}
            logger.warning("Configuration 'mcpServers' key missing, initialized to empty.")
        
        for server_name, server_config in self.config.get("mcpServers", {}).items():
            if not isinstance(server_config, dict):
                raise ValueError(f"Server config for '{server_name}' must be a dictionary")
            if "command" not in server_config:
                raise ValueError(f"Server '{server_name}' missing 'command'")
            if "args" not in server_config or not isinstance(server_config["args"], list):
                raise ValueError(f"Server '{server_name}' missing or invalid 'args'")
            if "transportType" not in server_config:
                server_config["transportType"] = "stdio"
            if server_config["transportType"] != "stdio":
                raise ValueError(f"Unsupported transportType for '{server_name}': {server_config['transportType']}")
            if "env" in server_config and not isinstance(server_config["env"], dict):
                raise ValueError(f"Invalid 'env' for '{server_name}': must be a dictionary")

    def get_server_config(self, server_name: str) -> Optional[Dict[str, Any]]:
        return self.config.get("mcpServers", {}).get(server_name)

    def list_servers(self) -> List[str]:
        return list(self.config.get("mcpServers", {}).keys())

class MCPClient:
    def __init__(self, config_path: Optional[str] = None):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.config_manager = ConfigManager(config_path)
        self.genai_client: Optional[genai.Client] = None

        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GOOGLE_API_KEY or GEMINI_API_KEY not found in environment.")
            print("ERROR: GOOGLE_API_KEY or GEMINI_API_KEY environment variable is not set.")
            raise ValueError("API key not found. Please set GOOGLE_API_KEY or GEMINI_API_KEY.")

        try:
            self.genai_client = genai.Client(api_key=api_key)
            logger.info("Google GenAI Client initialized successfully (using genai.Client).")
        except Exception as e:
            logger.error(f"Failed to initialize Google GenAI Client: {str(e)}", exc_info=True)
            print("Please ensure your GOOGLE_API_KEY or GEMINI_API_KEY environment variable is set correctly and the SDK is installed.")
            raise

    async def connect_to_server(self, server_name: Optional[str] = None, server_script_path: Optional[str] = None):
        if server_name and server_script_path:
            raise ValueError("Cannot specify both server_name and server_script_path")
        if not server_name and not server_script_path:
            raise ValueError("Must specify either server_name or server_script_path")

        server_params: StdioServerParameters
        if server_name:
            config = self.config_manager.get_server_config(server_name)
            if not config:
                raise ValueError(f"No configuration found for server '{server_name}'")
            logger.debug(f"Using configuration for server: {server_name}")
            server_params = StdioServerParameters(
                command=config["command"],
                args=config["args"],
                env=config.get("env")
            )
        else:
            logger.debug(f"Attempting to connect to server with script: {server_script_path}")
            abs_script_path = str(Path(server_script_path).resolve())
            if not Path(abs_script_path).exists():
                 raise FileNotFoundError(f"Server script not found at {abs_script_path}")
            is_python = abs_script_path.endswith('.py')
            is_js = abs_script_path.endswith('.js')
            if not (is_python or is_js):
                logger.error(f"Invalid server script extension: {abs_script_path}")
                raise ValueError("Server script must be a .py or .js file")
            command = sys.executable if is_python else "node"
            server_params = StdioServerParameters(command=command, args=[abs_script_path], env=None)

        try:
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            self.stdio, self.input = stdio_transport
            self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.input))
            await self.session.initialize()
            response = await self.session.list_tools()
            tools = response.tools
            logger.info(f"Connected to server with tools: {[tool.name for tool in tools]}")
            print("\nConnected to server with tools:", [tool.name for tool in tools])
        except Exception as e:
            logger.error(f"Failed to connect to server: {str(e)}", exc_info=True)
            raise

    def _convert_mcp_tool_to_genai_function_declaration(self, mcp_tool: Any) -> Dict[str, Any]:
        logger.debug(f"Converting MCP tool to GenAI function declaration: {mcp_tool.name}")
        parameters_schema: Dict[str, Any] = {"type": "object", "properties": {}}
        
        if mcp_tool.inputSchema and isinstance(mcp_tool.inputSchema, dict):
            genai_properties: Dict[str, Any] = {}
            for name, schema_prop in mcp_tool.inputSchema.get("properties", {}).items():
                if not isinstance(schema_prop, dict):
                    logger.warning(f"Skipping malformed property {name} in tool {mcp_tool.name}")
                    continue
                prop_type_str = schema_prop.get("type", "string").lower()
                valid_types = ["string", "number", "integer", "boolean", "array", "object"]
                if prop_type_str not in valid_types:
                    logger.warning(f"Invalid type {prop_type_str} for {name} in tool {mcp_tool.name}, defaulting to string")
                    prop_type_str = "string"
                current_prop_schema: Dict[str, Any] = {"type": prop_type_str}
                if "description" in schema_prop:
                    current_prop_schema["description"] = schema_prop["description"]
                if "enum" in schema_prop and isinstance(schema_prop["enum"], list):
                    current_prop_schema["enum"] = schema_prop["enum"]
                if prop_type_str == "array":
                    if "items" in schema_prop and isinstance(schema_prop["items"], dict):
                        current_prop_schema["items"] = schema_prop["items"]
                    else: # Default items for array if not specified or invalid
                        current_prop_schema["items"] = {"type": "string"} 
                        logger.debug(f"Array property '{name}' in tool '{mcp_tool.name}' missing or has invalid 'items'. Defaulting to string items.")
                genai_properties[name] = current_prop_schema

            parameters_schema["properties"] = genai_properties
            required_params_list = mcp_tool.inputSchema.get("required", [])
            if isinstance(required_params_list, list) and all(isinstance(p, str) for p in required_params_list):
                if required_params_list:
                    parameters_schema["required"] = required_params_list
        else:
            logger.warning(f"No input schema or malformed schema for tool {mcp_tool.name}. Tool will have no parameters.")

        description = mcp_tool.description
        if not description or not isinstance(description, str) or not description.strip():
            description = f"Tool to perform {mcp_tool.name}"
            logger.warning(f"Tool '{mcp_tool.name}' has missing/empty description, using default.")
        
        return {
            "name": mcp_tool.name,
            "description": description,
            "parameters": parameters_schema,
        }

    async def process_query(self, query: str) -> str:
        if not self.genai_client:
            logger.error("GenAI client not initialized.")
            return "Error: GenAI client not available."
        if not self.session:
            logger.error("MCP session not initialized.")
            return "Error: MCP session not active."
            
        logger.debug(f"Processing query: {query}")
        final_response_text_parts = []

        try:
            mcp_tools_response = await self.session.list_tools()
            available_mcp_tools = mcp_tools_response.tools
            logger.debug(f"Available MCP tools: {[tool.name for tool in available_mcp_tools]}")

            genai_tool_declarations_for_api = []
            if available_mcp_tools:
                for tool in available_mcp_tools:
                    if hasattr(tool, 'name') and tool.name:
                        try:
                            decl = self._convert_mcp_tool_to_genai_function_declaration(tool)
                            genai_tool_declarations_for_api.append(decl)
                        except Exception as e:
                            logger.error(f"Failed to convert MCP tool '{getattr(tool, 'name', 'UNKNOWN')}' to GenAI declaration: {e}", exc_info=True)
                    else:
                        logger.warning(f"Skipping an invalid/unnamed MCP tool: {tool}")
            
            current_tool_config: Optional[types.GenerateContentConfig] = None
            if genai_tool_declarations_for_api:
                gemini_tools = [types.Tool(function_declarations=genai_tool_declarations_for_api)]
                current_tool_config = types.GenerateContentConfig(tools=gemini_tools)
                logger.debug(f"GenAI tools configured for API call: {[fd['name'] for fd in genai_tool_declarations_for_api]}")
            else:
                logger.info("No MCP tools available or converted for this query.")

            conversation_history: List[types.Content] = [
                types.Content(parts=[types.Part(text=query)], role="user")
            ]
            
            max_turns = 5 

            for turn_count in range(max_turns):
                logger.info(f"Conversation turn {turn_count + 1}/{max_turns}")
                logger.debug(f"Sending to Gemini. History length: {len(conversation_history)}")

                try:
                    # THIS IS THE CORRECTED LINE from the previous error
                    response = await self.genai_client.aio.models.generate_content(
                        model=DEFAULT_GEMINI_MODEL,
                        contents=conversation_history,
                        config=current_tool_config
                    )
                    logger.debug(f"Gemini API call successful. Response: {response}")

                except Exception as e:
                    logger.error(f"Error calling Gemini API (turn {turn_count + 1}): {str(e)}", exc_info=True)
                    final_response_text_parts.append(f"\n[Error communicating with AI model: {str(e)}]")
                    break

                if not response.candidates:
                    logger.warning("Gemini API returned no candidates.")
                    if hasattr(response, 'text') and response.text: # Fallback for older API behavior
                         final_response_text_parts.append(response.text)
                    else:
                        final_response_text_parts.append("\n[AI model returned no response candidates.]")
                    break

                # Process the first candidate's content
                model_response_content = response.candidates[0].content
                
                # Add model's response (which might contain a function call) to history
                conversation_history.append(model_response_content)
                logger.debug(f"Model response content parts: {model_response_content.parts}")

                has_function_call_in_this_model_response = False
                
                for part in model_response_content.parts:
                    if part.text:
                        logger.debug(f"LLM text part: '{part.text}'")
                        final_response_text_parts.append(part.text)
                        if len(part.text.strip()) > 10: # Print substantive intermediate text
                             print(f"\n{part.text.strip()}")

                    if part.function_call:
                        has_function_call_in_this_model_response = True
                        function_call = part.function_call
                        tool_name = function_call.name
                        tool_args_dict = dict(function_call.args) if function_call.args else {}
                        
                        fc_log_msg = f"LLM requested function call: {tool_name} with args: {tool_args_dict}"
                        logger.info(fc_log_msg)
                        print(f"[LLM wants to call tool '{tool_name}' with args: {tool_args_dict}]")

                        tool_result_content_for_llm: Dict[str, Any]
                        try:
                            mcp_tool_result = await self.session.call_tool(tool_name, tool_args_dict)
                            tool_result_payload = mcp_tool_result.content
                            
                            result_snippet = str(tool_result_payload)
                            if len(result_snippet) > 200: result_snippet = result_snippet[:200] + "..."
                            print(f"[Tool '{tool_name}' executed by MCP. Result snippet: {result_snippet}]")
                            logger.debug(f"Full tool result payload for '{tool_name}': {tool_result_payload}")
                            
                            if isinstance(tool_result_payload, dict):
                                tool_result_content_for_llm = tool_result_payload
                            elif isinstance(tool_result_payload, (str, int, float, bool, list)):
                                tool_result_content_for_llm = {"output": tool_result_payload}
                            else:
                                tool_result_content_for_llm = {"output": str(tool_result_payload)}

                        except Exception as e:
                            error_message = f"Error calling MCP tool '{tool_name}': {str(e)}"
                            logger.error(error_message, exc_info=True)
                            print(f"[{error_message}]")
                            tool_result_content_for_llm = {"error": error_message, "details": traceback.format_exc()}
                        
                        # As per your first script's logic (and common patterns for multi-turn with this client style):
                        # The model's function_call part is already in history.
                        # Now add the function_response part.
                        # The genai.Client docs (function calling section, MCP example) shows adding the
                        # function response part with role="user". Let's adhere to that.
                        tool_response_part_for_history = types.Part.from_function_response(
                            name=tool_name,
                            response=tool_result_content_for_llm
                        )
                        conversation_history.append(types.Content(parts=[tool_response_part_for_history], role="user"))
                        logger.debug(f"Tool response for '{tool_name}' added to history with role 'user': {tool_result_content_for_llm}")
                        break # Process one function call per LLM response cycle

                if not has_function_call_in_this_model_response:
                    logger.info("No function call in this model response. Assuming final textual response.")
                    # If no text parts were directly added from model_response_content.parts,
                    # but response.text (top-level) has content, use it.
                    # This was the pattern in your original script.
                    if not any(p.strip() for p in final_response_text_parts) and hasattr(response, 'text') and response.text:
                        logger.debug(f"No text parts collected from model_response_content, using response.text: {response.text}")
                        final_response_text_parts.append(response.text)
                    
                    if not any(p.strip() for p in final_response_text_parts): # If still nothing
                        logger.warning("LLM provided no text and no function call. Ending turn.")
                        final_response_text_parts.append("[AI model provided no further text or actions.]")
                    break # Exit the loop

            else: # max_turns reached
                logger.warning(f"Max interaction turns ({max_turns}) reached.")
                if not any(p.strip() for p in final_response_text_parts): # If loop finished and no text gathered
                    final_response_text_parts.append("\n[Max interaction turns reached with AI model. No final text generated.]")
                else:
                    final_response_text_parts.append("\n[Max interaction turns reached with AI model.]")

            return "".join(final_response_text_parts).strip()

        except Exception as e:
            logger.error(f"Critical error in process_query: {str(e)}", exc_info=True)
            return f"Error in query processing: {str(e)}"

    async def chat_loop(self):
        logger.info("Starting chat loop")
        print("\nMCP Client (Google GenAI SDK Edition - Client API) Started!")
        print(f"Using Gemini model: {DEFAULT_GEMINI_MODEL}")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = await asyncio.to_thread(input, "\nQuery: ") 
                query = query.strip()
                logger.debug(f"Received user query: {query}")

                if query.lower() == 'quit':
                    logger.info("User requested to quit")
                    break
                if not query:
                    print("Please enter a valid query.")
                    continue
                if not self.session:
                    logger.warning("No active MCP session")
                    print("Not connected to any server. Please connect first.")
                    continue
                if not self.genai_client:
                    logger.warning("GenAI client not initialized")
                    print("GenAI client not available. Please check setup.")
                    continue
                
                print("Processing...") 
                response_text = await self.process_query(query)
                print("\n" + response_text if response_text else "\n[No response from AI model]")

            except KeyboardInterrupt:
                logger.info("User interrupted query input (Ctrl+C).")
                print("\nQuery input interrupted. Type 'quit' to exit or enter a new query.")
            except Exception as e:
                logger.error(f"Error in chat loop: {str(e)}", exc_info=True)
                print(f"\nAn error occurred in the chat loop: {str(e)}")


    async def cleanup(self):
        logger.debug("Cleaning up MCP Client")
        try:
            if self.exit_stack:
                await self.exit_stack.aclose()
        except Exception as e:
            logger.error(f"Error during MCP client resource cleanup: {str(e)}", exc_info=True)
        logger.info("MCP Client cleaned up.")
        print("MCP Client cleaned up.")

async def main():
    logger.info("Starting main function")
    parser = argparse.ArgumentParser(
        description="MCP Client for connecting to MCP servers and interacting via Google GenAI (genai.Client).",
        formatter_class=argparse.RawTextHelpFormatter
    )
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--server", help="Name of the configured server (e.g., 'weather') from mcp.json")
    group.add_argument("--script", help="Path to the server script (e.g., 'servers/weather.py')")
    parser.add_argument("--config", help="Path to custom mcp.json configuration file")
    
    args = parser.parse_args()

    if not args.server and not args.script:
        temp_config_mgr = ConfigManager(args.config) 
        available_servers = temp_config_mgr.list_servers()
        
        help_message = f"Usage: python {sys.argv[0]} [ --server <server_name> | --script <path_to_server_script> ] [--config <config_path>]\n\n"
        if available_servers:
            help_message += f"You must specify either --server or --script.\nAvailable configured servers: {available_servers}\n"
        else:
            help_message += "You must specify --script, as no servers are configured in mcp.json (or mcp.json not found/empty).\n"
        parser.print_help()
        print(f"\n{help_message}")
        sys.exit(1)

    client = None
    try:
        client = MCPClient(config_path=args.config) 
        
        if args.server:
            await client.connect_to_server(server_name=args.server)
        elif args.script: 
            await client.connect_to_server(server_script_path=args.script)
        
        await client.chat_loop()

    except (ValueError, FileNotFoundError, ConnectionRefusedError) as e:
        logger.error(f"Setup or Connection error: {str(e)}", exc_info=isinstance(e, ConnectionRefusedError))
        print(f"ERROR: {e}")
    except Exception as e: 
        logger.critical(f"An unexpected critical error occurred: {str(e)}", exc_info=True)
        print(f"CRITICAL ERROR: {e}\nCheck client_debug.log for details.")
        traceback.print_exc()
    finally:
        if client:
            await client.cleanup()
        logger.info("Main function finished.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program interrupted by user (Ctrl+C at top level).")
        print("\nProgram interrupted. Exiting.")
    except Exception as e:
        logger.critical(f"Fatal error during program execution: {str(e)}", exc_info=True)
        print(f"A fatal error occurred: {e}")
        traceback.print_exc()
    finally:
        for handler in logger.handlers: # Ensure logs are flushed
            handler.flush()
            if hasattr(handler, 'close') and callable(handler.close):
                handler.close()