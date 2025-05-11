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
        logging.FileHandler('client_debug.log')
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-preview-04-17"

class ConfigManager:
    def __init__(self, config_path: Optional[str] = None):
        self.config: Dict[str, Any] = {}
        self.config_path = config_path or self._find_config_path()
        self.load_config()

    def _find_config_path(self) -> str:
        """Search for mcp.json or .mcp.json in standard locations."""
        possible_paths = [
            Path.cwd() / ".mcp.json",
            Path.cwd() / "mcp.json",
            Path.home() / ".mcp" / "mcp.json",
        ]
        for path in possible_paths:
            if path.exists():
                logger.debug(f"Found configuration file at {path}")
                return str(path)
        logger.warning("No mcp.json or .mcp.json found. Using default configuration.")
        return ""

    def load_config(self):
        """Load and validate the configuration file."""
        if not self.config_path or not Path(self.config_path).exists():
            logger.debug("No configuration file provided or found.")
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
        """Validate the configuration structure."""
        if "mcpServers" not in self.config:
            raise ValueError("Configuration must contain 'mcpServers' key")
        
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
        """Retrieve configuration for a specific server."""
        return self.config.get("mcpServers", {}).get(server_name)

    def list_servers(self) -> List[str]:
        """List all configured server names."""
        return list(self.config.get("mcpServers", {}).keys())

class MCPClient:
    def __init__(self, config_path: Optional[str] = None):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.config_manager = ConfigManager(config_path)
        try:
            self.genai_client = genai.Client()
            logger.info("Google GenAI Client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google GenAI Client: {str(e)}", exc_info=True)
            print("Please ensure your GOOGLE_API_KEY or GEMINI_API_KEY environment variable is set correctly.")
            raise

    async def connect_to_server(self, server_name: Optional[str] = None, server_script_path: Optional[str] = None):
        """Connect to an MCP server using a configuration or script path."""
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
            is_python = server_script_path.endswith('.py')
            is_js = server_script_path.endswith('.js')
            if not (is_python or is_js):
                logger.error(f"Invalid server script extension: {server_script_path}")
                raise ValueError("Server script must be a .py or .js file")
            command = "python" if is_python else "node"
            server_params = StdioServerParameters(command=command, args=[server_script_path], env=None)

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
        """Convert an MCP tool to a GenAI function declaration."""
        logger.debug(f"Converting MCP tool to GenAI function declaration: {mcp_tool.name}")
        parameters_schema: Dict[str, Any] = {"type": "object", "properties": {}}
        required_params: List[str] = []

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
                if prop_type_str == "array" and "items" in schema_prop and isinstance(schema_prop["items"], dict):
                    current_prop_schema["items"] = schema_prop["items"]
                genai_properties[name] = current_prop_schema

            parameters_schema["properties"] = genai_properties
            required_params = mcp_tool.inputSchema.get("required", [])
            if isinstance(required_params, list):
                parameters_schema["required"] = required_params
        else:
            logger.warning(f"No input schema found for tool {mcp_tool.name}")

        logger.debug(f"Generated parameters schema for {mcp_tool.name}: {parameters_schema}")
        return {
            "name": mcp_tool.name,
            "description": mcp_tool.description or f"Tool {mcp_tool.name}",
            "parameters": parameters_schema,
        }

    async def process_query(self, query: str) -> str:
        """Process a user query using the connected MCP server and GenAI."""
        logger.debug(f"Processing query: {query}")
        try:
            mcp_tools_response = await self.session.list_tools()
            available_mcp_tools = mcp_tools_response.tools
            logger.debug(f"Available MCP tools: {[tool.name for tool in available_mcp_tools]}")

            conversation_history: List[types.Content] = [
                types.Content(parts=[types.Part(text=query)], role="user")
            ]
            final_text_parts = []
            genai_tool_config = None

            if available_mcp_tools:
                genai_function_declarations = [
                    self._convert_mcp_tool_to_genai_function_declaration(tool)
                    for tool in available_mcp_tools
                ]
                if genai_function_declarations:
                    genai_tools = types.Tool(function_declarations=genai_function_declarations)
                    genai_tool_config = types.GenerateContentConfig(tools=[genai_tools])
                    logger.debug("GenAI tools configured")
            else:
                final_text_parts.append("[No MCP tools available for this query]")
                logger.warning("No MCP tools available")

            # Initial GenAI API call
            logger.debug(f"Calling async Gemini API with model {DEFAULT_GEMINI_MODEL}")
            try:
                response = await self.genai_client.aio.models.generate_content(
                    model=DEFAULT_GEMINI_MODEL,
                    contents=conversation_history,
                    config=genai_tool_config
                )
                logger.debug("Gemini API call successful")
                logger.debug(f"Response structure: {response.__dict__}")
            except Exception as e:
                logger.error(f"Error calling async Gemini API (initial call): {str(e)}", exc_info=True)
                return f"Error calling async Gemini API (initial call): {str(e)}"

            # Process response: check for text or function call
            if not response.candidates:
                logger.warning("Gemini API returned no candidates")
                return "Gemini API returned no candidates."

            logger.debug(f"Candidates: {[c.__dict__ for c in response.candidates]}")
            if not response.candidates[0].content or not response.candidates[0].content.parts:
                if response.text:
                    final_text_parts.append(response.text)
                    logger.debug("Using response.text as fallback")
                    return "\n".join(final_text_parts)
                logger.warning("Gemini API response is empty or malformed")
                return "Gemini API response is empty or malformed."

            llm_part = response.candidates[0].content.parts[0]
            logger.debug(f"LLM part: {llm_part.__dict__}")

            if llm_part.function_call:
                logger.debug(f"LLM requested function call: {llm_part.function_call.name}")
                conversation_history.append(response.candidates[0].content)

                function_call = llm_part.function_call
                tool_name = function_call.name
                tool_args_dict = dict(function_call.args)
                logger.debug(f"Function call args: {tool_args_dict}")

                final_text_parts.append(f"[LLM wants to call tool '{tool_name}' with args: {tool_args_dict}]")

                tool_result_content_for_llm: Dict[str, Any]
                try:
                    mcp_tool_result = await self.session.call_tool(tool_name, tool_args_dict)
                    tool_result_payload = mcp_tool_result.content
                    final_text_parts.append(f"[Tool '{tool_name}' executed. Result: {tool_result_payload}]")
                    logger.debug(f"Tool result payload: {tool_result_payload}")
                    if isinstance(tool_result_payload, str):
                        tool_result_content_for_llm = {"output": tool_result_payload}
                    elif isinstance(tool_result_payload, dict):
                        tool_result_content_for_llm = tool_result_payload
                    else:
                        tool_result_content_for_llm = {"output": str(tool_result_payload)}
                except Exception as e:
                    error_message = f"Error calling MCP tool '{tool_name}': {str(e)}"
                    logger.error(error_message, exc_info=True)
                    final_text_parts.append(f"[{error_message}]")
                    tool_result_content_for_llm = {"error": error_message}

                tool_response_part = types.Part.from_function_response(
                    name=tool_name,
                    response=tool_result_content_for_llm
                )
                conversation_history.append(types.Content(parts=[tool_response_part], role="user"))

                # Follow-up GenAI API call
                logger.debug("Making follow-up async Gemini API call")
                try:
                    follow_up_response = await self.genai_client.aio.models.generate_content(
                        model=DEFAULT_GEMINI_MODEL,
                        contents=conversation_history,
                        config=genai_tool_config
                    )
                    logger.debug(f"Follow-up response: {follow_up_response.__dict__}")
                    if follow_up_response.text:
                        final_text_parts.append(follow_up_response.text)
                    elif follow_up_response.candidates and follow_up_response.candidates[0].content.parts[0].text:
                        final_text_parts.append(follow_up_response.candidates[0].content.parts[0].text)
                    else:
                        final_text_parts.append("[LLM did not provide further text after tool use.]")
                        logger.debug("No further text from LLM after tool use")
                except Exception as e:
                    logger.error(f"Error in follow-up async call to Gemini: {str(e)}", exc_info=True)
                    final_text_parts.append(f"Error in follow-up async call to Gemini: {str(e)}")

            elif llm_part.text:
                final_text_parts.append(llm_part.text)
                logger.debug("Received text response from LLM")
            elif response.text:
                final_text_parts.append(response.text)
                logger.debug("Using response.text as fallback")
            else:
                final_text_parts.append("[LLM did not provide a text response or a function call in the expected part.]")
                logger.warning("No valid response from LLM")

            return "\n".join(final_text_parts)
        except Exception as e:
            logger.error(f"Error in process_query: {str(e)}", exc_info=True)
            return f"Error in process_query: {str(e)}"

    async def chat_loop(self):
        """Run an interactive chat loop with the user."""
        logger.info("Starting chat loop")
        print("\nMCP Client (Google GenAI SDK Edition) Started!")
        print(f"Using Gemini model: {DEFAULT_GEMINI_MODEL}")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()
                logger.debug(f"Received user query: {query}")
                if query.lower() == 'quit':
                    logger.info("User requested to quit")
                    break
                if not query.strip():
                    print("Please enter a valid query.")
                    continue
                if not self.session:
                    logger.warning("No active session")
                    print("Not connected to any server. Please connect first.")
                    continue
                response_text = await self.process_query(query)
                print("\n" + response_text)
            except Exception as e:
                logger.error(f"Error in chat loop: {str(e)}", exc_info=True)
                print(f"\nError in chat loop: {str(e)}")

    async def cleanup(self):
        """Clean up resources used by the MCP client."""
        logger.debug("Cleaning up MCP Client")
        try:
            if self.exit_stack:
                await self.exit_stack.aclose()
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}", exc_info=True)
        logger.info("MCP Client cleaned up.")
        print("MCP Client cleaned up.")

async def main():
    logger.info("Starting main function")
    parser = argparse.ArgumentParser(description="MCP Client for connecting to MCP servers")
    parser.add_argument("--server", help="Name of the configured server (e.g., 'weather')")
    parser.add_argument("--script", help="Path to the server script (e.g., 'weather/weather.py')")
    parser.add_argument("--config", help="Path to custom mcp.json configuration file")
    args = parser.parse_args()

    if args.server and args.script:
        logger.error("Cannot specify both --server and --script")
        print("Error: Cannot specify both --server and --script")
        sys.exit(1)
    if not args.server and not args.script:
        logger.error("Must specify either --server or --script")
        print("Usage: python client-g5.py --server <server_name> | --script <path_to_server_script> [--config <config_path>]")
        sys.exit(1)

    client = MCPClient(config_path=args.config)
    try:
        if args.server:
            print(f"Available servers: {client.config_manager.list_servers()}")
            await client.connect_to_server(server_name=args.server)
        else:
            await client.connect_to_server(server_script_path=args.script)
        await client.chat_loop()
    except ValueError as ve:
        logger.error(f"Configuration error: {str(ve)}", exc_info=True)
        print(f"Configuration error: {ve}")
    except ConnectionRefusedError:
        logger.error(f"Connection refused for server/script", exc_info=True)
        print(f"Connection refused. Ensure the server is runnable.")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        print(f"An unexpected error occurred: {e}")
    finally:
        await client.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program interrupted by user")
        print("\nProgram interrupted by user. Exiting gracefully.")
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}", exc_info=True)
        print(f"Error in main execution: {e}")
