import asyncio
import os
from typing import Optional, Dict, Any, List
from contextlib import AsyncExitStack
import logging
import sys
import traceback

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

#DEFAULT_GEMINI_MODEL = "gemini-2.5-pro-exp-03-25"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-preview-04-17"

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
