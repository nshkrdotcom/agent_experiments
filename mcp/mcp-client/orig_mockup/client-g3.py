import asyncio
import os
from typing import Optional, Dict, Any, List
from contextlib import AsyncExitStack
import logging  # Add logging import
import sys
import traceback  # Add traceback import for detailed stack traces

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for verbose output
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # Output to console
        logging.FileHandler('client_debug.log')  # Save to a log file
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"

class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        try:
            self.genai_client = genai.Client()
            logger.info("Google GenAI Client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google GenAI Client: {str(e)}", exc_info=True)
            print("Please ensure your GOOGLE_API_KEY or GEMINI_API_KEY environment variable is set correctly.")
            raise

    async def connect_to_server(self, server_script_path: str):
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
        """
        Converts an MCP tool definition to a GenAI FunctionDeclaration dictionary.
        GenAI expects a dictionary matching OpenAPI schema.
        """
        # Ensure mcp_tool.inputSchema is a JSON schema-like dictionary
        parameters_schema: Dict[str, Any] = {"type": "object", "properties": {}}
        required_params: List[str] = []

        if mcp_tool.inputSchema and isinstance(mcp_tool.inputSchema, dict):
            # MCP schema properties to OpenAPI schema
            genai_properties: Dict[str, Any] = {}
            for name, schema_prop in mcp_tool.inputSchema.get("properties", {}).items():
                if not isinstance(schema_prop, dict): continue # Skip malformed properties

                # Basic type mapping - extend as needed for your specific MCP tool schemas
                prop_type_str = schema_prop.get("type", "string").lower()
                # Common JSON schema types: string, number, integer, boolean, array, object
                valid_types = ["string", "number", "integer", "boolean", "array", "object"]
                if prop_type_str not in valid_types:
                    prop_type_str = "string" # Default or handle error more gracefully

                current_prop_schema: Dict[str, Any] = {"type": prop_type_str}
                if "description" in schema_prop:
                    current_prop_schema["description"] = schema_prop["description"]
                if "enum" in schema_prop and isinstance(schema_prop["enum"], list):
                    current_prop_schema["enum"] = schema_prop["enum"]
                # Add more schema conversions if needed (e.g., for array items, object properties)
                if prop_type_str == "array" and "items" in schema_prop and isinstance(schema_prop["items"], dict):
                    current_prop_schema["items"] = schema_prop["items"] # Assuming items schema is compatible

                genai_properties[name] = current_prop_schema

            parameters_schema["properties"] = genai_properties
            required_params = mcp_tool.inputSchema.get("required", [])
            if isinstance(required_params, list):
                 parameters_schema["required"] = required_params


        return {
            "name": mcp_tool.name,
            "description": mcp_tool.description,
            "parameters": parameters_schema,
        }

    async def process_query(self, query: str) -> str:
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
            logger.debug(f"Calling Gemini API with model {DEFAULT_GEMINI_MODEL}")
            try:
                response = await self.genai_client.aio.models.generate_content(
                    model=DEFAULT_GEMINI_MODEL,
                    contents=conversation_history,
                    config=genai_tool_config
                )
                logger.debug("Gemini API call successful")
            except Exception as e:
                logger.error(f"Error calling Gemini API (initial call): {str(e)}", exc_info=True)
                return f"Error calling Gemini API (initial call): {str(e)}"

            # ... (rest of the method unchanged, add logger.debug/error for key steps)
            return "\n".join(final_text_parts)
        except Exception as e:
            logger.error(f"Error in process_query: {str(e)}", exc_info=True)
            return f"Error in process_query: {str(e)}"

    async def chat_loop(self):
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
        logger.debug("Cleaning up MCP Client")
        if self.exit_stack:
            await self.exit_stack.aclose()
        logger.info("MCP Client cleaned up.")
        print("MCP Client cleaned up.")

async def main():
    logger.info("Starting main function")
    if len(sys.argv) < 2:
        logger.error("No server script path provided")
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

    client = MCPClient()
    server_script_path = sys.argv[1]
    logger.debug(f"Server script path: {server_script_path}")

    try:
        await client.connect_to_server(server_script_path)
        await client.chat_loop()
    except ValueError as ve:
        logger.error(f"Configuration error: {str(ve)}", exc_info=True)
        print(f"Configuration error: {ve}")
    except ConnectionRefusedError:
        logger.error(f"Connection refused for script: {server_script_path}", exc_info=True)
        print(f"Connection refused. Ensure the server script '{server_script_path}' is runnable.")
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
