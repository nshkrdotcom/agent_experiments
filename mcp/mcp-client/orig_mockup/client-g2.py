import asyncio
import os
from typing import Optional, Dict, Any, List
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Use the new google.genai SDK
from google import genai
from google.genai import types # Correct import for types

from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env

# Recommended model from the docs provided by user, known to support function calling.
# Can be overridden if needed.
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash" # As per user-provided docs
# For more advanced capabilities or if "gemini-2.0-flash" is not found,
# "gemini-1.5-pro-latest" or "gemini-1.5-flash-latest" are good alternatives.

class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()

        # Initialize Google GenAI client using the new SDK
        # The API key is typically read from GOOGLE_API_KEY or GEMINI_API_KEY env vars
        try:
            self.genai_client = genai.Client()
            # You can test connectivity or list models if desired, e.g.:
            # print("Available models:", [m.name for m in self.genai_client.models.list()])
        except Exception as e:
            print(f"Failed to initialize Google GenAI Client: {e}")
            print("Please ensure your GOOGLE_API_KEY or GEMINI_API_KEY environment variable is set correctly.")
            raise

    async def connect_to_server(self, server_script_path: str):
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(command=command, args=[server_script_path], env=None)

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

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
        """Process a query using Gemini and available tools with google.genai SDK"""

        mcp_tools_response = await self.session.list_tools()
        available_mcp_tools = mcp_tools_response.tools

        # Prepare history for GenAI
        # For each process_query, we start a new logical "turn" sequence.
        # If you need a persistent chat session, manage 'conversation_history' outside this method.
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
        else:
            final_text_parts.append("[No MCP tools available for this query]")


        # Initial GenAI API call
        try:
            response = await self.genai_client.models.generate_content(
                model=DEFAULT_GEMINI_MODEL,
                contents=conversation_history,
                config=genai_tool_config # Use generation_config for tools
            )
        except Exception as e:
            return f"Error calling Gemini API (initial call): {str(e)}"


        # Process response: check for text or function call
        # According to google.genai docs, response can have multiple candidates. We use the first.
        if not response.candidates:
            return "Gemini API returned no candidates."

        # The model's response (text or function call) is in the first part of the first candidate's content
        # This structure might vary slightly if streaming or multi-part responses are expected.
        # For standard function calling, this is typical.
        if not response.candidates[0].content or not response.candidates[0].content.parts:
             if response.text: # Fallback to response.text if parts are empty but text exists
                final_text_parts.append(response.text)
                return "\n".join(final_text_parts)
             return "Gemini API response is empty or malformed."

        llm_part = response.candidates[0].content.parts[0]

        if llm_part.function_call:
            # Append the model's turn (that includes the function_call) to history
            conversation_history.append(response.candidates[0].content)

            function_call = llm_part.function_call
            tool_name = function_call.name
            tool_args_dict = dict(function_call.args) # Convert to plain dict

            final_text_parts.append(f"[LLM wants to call tool '{tool_name}' with args: {tool_args_dict}]")

            tool_result_content_for_llm: Dict[str, Any]
            try:
                # Execute tool call via MCP
                mcp_tool_result = await self.session.call_tool(tool_name, tool_args_dict)
                # Ensure result.content is something serializable (string, dict, list, etc.)
                tool_result_payload = mcp_tool_result.content
                final_text_parts.append(f"[Tool '{tool_name}' executed. Result: {tool_result_payload}]")
                # Gemini expects the result for the function in a specific way, often a dict.
                # If tool_result_payload is a simple string, wrap it.
                if isinstance(tool_result_payload, str):
                    tool_result_content_for_llm = {"output": tool_result_payload}
                elif isinstance(tool_result_payload, dict):
                    tool_result_content_for_llm = tool_result_payload # Assume it's already good
                else: # attempt to make it a string if it's some other type
                    tool_result_content_for_llm = {"output": str(tool_result_payload)}

            except Exception as e:
                error_message = f"Error calling MCP tool '{tool_name}': {str(e)}"
                final_text_parts.append(f"[{error_message}]")
                tool_result_content_for_llm = {"error": error_message}

            # Prepare the function response part for GenAI
            tool_response_part = types.Part.from_function_response(
                name=tool_name,
                response=tool_result_content_for_llm
            )
            # Append the tool's response to the conversation history
            conversation_history.append(types.Content(parts=[tool_response_part], role="user"))
            # The role="user" for the function response part is consistent with google.genai examples for function calling.
            # The SDK's from_function_response might also imply the "tool" role to the API internally.

            # Get next response from Gemini using the tool's output
            try:
                follow_up_response = await self.genai_client.models.generate_content(
                    model=DEFAULT_GEMINI_MODEL,
                    contents=conversation_history,
                    config=genai_tool_config # Pass tools again
                )
                if follow_up_response.text:
                    final_text_parts.append(follow_up_response.text)
                elif follow_up_response.candidates and follow_up_response.candidates[0].content.parts[0].text:
                    final_text_parts.append(follow_up_response.candidates[0].content.parts[0].text)
                else:
                    final_text_parts.append("[LLM did not provide further text after tool use.]")
            except Exception as e:
                final_text_parts.append(f"Error in follow-up call to Gemini: {str(e)}")

        elif llm_part.text:
            final_text_parts.append(llm_part.text)
        elif response.text: # Fallback if parts[0] had no text but response.text does
             final_text_parts.append(response.text)
        else:
            final_text_parts.append("[LLM did not provide a text response or a function call in the expected part.]")

        return "\n".join(final_text_parts)


    async def chat_loop(self):
        print("\nMCP Client (Google GenAI SDK Edition) Started!")
        print(f"Using Gemini model: {DEFAULT_GEMINI_MODEL}")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()
                if query.lower() == 'quit':
                    break
                if not self.session:
                    print("Not connected to any server. Please connect first using a command if available, or restart.")
                    continue
                response_text = await self.process_query(query)
                print("\n" + response_text)
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"\nError in chat loop: {str(e)}")

    async def cleanup(self):
        if self.exit_stack:
            await self.exit_stack.aclose()
        print("MCP Client cleaned up.")

async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

    client = MCPClient()
    server_script_path = sys.argv[1] # input("Enter path to the MCP server script (e.g., ./server.py or ./mcp_js_server/server.js): ").strip()
    if not server_script_path:
        print("No server script path provided. Exiting.")
        return

    try:
        await client.connect_to_server(server_script_path)
        await client.chat_loop()
    except ValueError as ve:
        print(f"Configuration error: {ve}")
    except ConnectionRefusedError:
        print(f"Connection refused. Ensure the server script '{server_script_path}' is runnable and correctly configured.")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
    finally:
        await client.cleanup()

if __name__ == "__main__":
    try:
        import sys
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted by user. Exiting gracefully.")
