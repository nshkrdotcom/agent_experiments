# import logging # No longer needed directly
from typing import Dict, Any, List, Optional, Tuple
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters, Tool
from mcp.client.stdio import stdio_client
from google import genai
from google.genai import types as genai_types

# Use the new logger
from app_logger import service_log_debug, service_log_info, service_log_warning, service_log_error

# logger = logging.getLogger(__name__) # REMOVE

class MCPService:
    def __init__(self, server_name: str, server_config: Dict[str, Any], exit_stack: AsyncExitStack):
        self.server_name = server_name
        self.server_config = server_config
        self.exit_stack = exit_stack
        self.session: Optional[ClientSession] = None
        self.stdio = None
        self.input = None

    async def connect(self):
        service_log_info(f"Connecting to MCP server: {self.server_name}")
        params = StdioServerParameters(
            command=self.server_config["command"],
            args=self.server_config["args"],
            env=self.server_config.get("env")
        )
        try:
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(params))
            self.stdio, self.input = stdio_transport
            self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.input))
            await self.session.initialize()
            tools = await self.get_tools()
            service_log_info(f"Connected to {self.server_name} with tools: {[tool.name for tool in tools]}")
        except Exception as e:
            service_log_error(f"Failed to connect to MCP server {self.server_name}: {e}", exc_info=True)
            raise

    async def get_tools(self) -> List[Tool]:
        if not self.session:
            # This is an internal error state, should be caught before user sees it
            service_log_error(f"Attempted to get tools from unconnected MCP server {self.server_name}")
            raise ConnectionError(f"Not connected to MCP server {self.server_name}")
        response = await self.session.list_tools()
        service_log_debug(f"Listed tools for {self.server_name}: {[t.name for t in response.tools]}")
        return response.tools

    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        if not self.session:
            service_log_error(f"Attempted to call tool on unconnected MCP server {self.server_name}")
            raise ConnectionError(f"Not connected to MCP server {self.server_name}")
        service_log_info(f"Calling tool '{tool_name}' on server '{self.server_name}' with args: {args}")
        # For VERBOSE, log full args. For NORMAL, maybe just tool_name.
        service_log_debug(f"Full args for '{tool_name}': {args}")
        try:
            result = await self.session.call_tool(tool_name, args)
            service_log_debug(f"Raw tool result content for '{tool_name}': {str(result.content)[:200]}...")
            return result.content
        except Exception as e:
            service_log_error(f"Error calling tool '{tool_name}' on MCP server {self.server_name}: {e}", exc_info=True)
            raise


class LLMService:
    def __init__(self, model_name: str, api_key: str):
        self.model_name = model_name
        try:
            self.genai_client = genai.Client(api_key=api_key)
            service_log_info(f"Google GenAI Client initialized for model: {self.model_name}")
        except Exception as e:
            service_log_error(f"Failed to initialize Google GenAI Client: {e}", exc_info=True)
            raise

    def _convert_mcp_tool_to_genai_function(self, mcp_tool: Tool) -> Dict[str, Any]:
        service_log_debug(f"Converting MCP tool '{mcp_tool.name}' to GenAI function declaration.")
        parameters_schema: Dict[str, Any] = {"type": "object", "properties": {}}
        if mcp_tool.inputSchema and isinstance(mcp_tool.inputSchema, dict):
            genai_properties: Dict[str, Any] = {}
            for name, schema_prop in mcp_tool.inputSchema.get("properties", {}).items():
                if not isinstance(schema_prop, dict): 
                    service_log_warning(f"Skipping malformed property {name} in tool {mcp_tool.name}")
                    continue
                prop_type_str = schema_prop.get("type", "string").lower()
                valid_types = ["string", "number", "integer", "boolean", "array", "object"]
                if prop_type_str not in valid_types: 
                    service_log_warning(f"Invalid type {prop_type_str} for {name} in tool {mcp_tool.name}, defaulting to string")
                    prop_type_str = "string"
                
                current_prop_schema: Dict[str, Any] = {"type": prop_type_str}
                if "description" in schema_prop:
                    current_prop_schema["description"] = schema_prop["description"]
                if "enum" in schema_prop and isinstance(schema_prop["enum"], list):
                    current_prop_schema["enum"] = schema_prop["enum"]
                if prop_type_str == "array":
                    current_prop_schema["items"] = schema_prop.get("items", {"type": "string"}) 
                    if "items" not in schema_prop or not isinstance(schema_prop.get("items"),dict) :
                         service_log_debug(f"Array property '{name}' in tool '{mcp_tool.name}' missing or has invalid 'items'. Defaulting to string items.")
                genai_properties[name] = current_prop_schema
            parameters_schema["properties"] = genai_properties
            required = mcp_tool.inputSchema.get("required", [])
            if required and isinstance(required, list) and all(isinstance(p, str) for p in required):
                parameters_schema["required"] = required
        else:
            service_log_warning(f"No input schema or malformed schema for tool {mcp_tool.name}. Tool will have no parameters.")

        description = mcp_tool.description
        if not description or not isinstance(description, str) or not description.strip():
            description = f"Tool to perform {mcp_tool.name}"
            service_log_warning(f"Tool '{mcp_tool.name}' has missing/empty description, using default.")
        
        return {
            "name": mcp_tool.name,
            "description": description,
            "parameters": parameters_schema,
        }

    def prepare_tools_for_llm(self, mcp_tools: List[Tool]) -> Optional[genai_types.GenerateContentConfig]:
        if not mcp_tools:
            service_log_debug("No MCP tools provided to prepare for LLM.")
            return None
        
        service_log_debug(f"Preparing {len(mcp_tools)} MCP tools for LLM.")
        genai_tool_declarations = []
        for tool in mcp_tools:
            if hasattr(tool, 'name') and tool.name:
                try:
                    decl = self._convert_mcp_tool_to_genai_function(tool)
                    genai_tool_declarations.append(decl)
                except Exception as e:
                    service_log_error(f"Failed to convert MCP tool '{getattr(tool, 'name', 'UNKNOWN')}' for LLM: {e}", exc_info=True)
            else:
                service_log_warning(f"Skipping an invalid/unnamed MCP tool: {tool}")

        if not genai_tool_declarations:
            service_log_info("No MCP tools were successfully converted for LLM.")
            return None
            
        gemini_tools = [genai_types.Tool(function_declarations=genai_tool_declarations)]
        service_log_info(f"LLM tools configured: {[fd['name'] for fd in genai_tool_declarations]}")
        return genai_types.GenerateContentConfig(tools=gemini_tools)

    async def generate_response(
        self,
        conversation_history: List[genai_types.Content],
        tool_config: Optional[genai_types.GenerateContentConfig]
    ) -> genai_types.GenerateContentResponse:
        # Normal level should log the start of an LLM call
        service_log_info(f"Sending request to LLM model: {self.model_name}. History length: {len(conversation_history)}.")
        # Verbose level can log the actual content being sent (careful with PII/size)
        service_log_debug(f"LLM request contents (last message): {conversation_history[-1] if conversation_history else 'None'}")
        if tool_config:
             service_log_debug(f"LLM tool_config: {[(tool.function_declarations[0].name if tool.function_declarations else 'N/A') for tool in tool_config.tools]}")


        try:
            response = await self.genai_client.aio.models.generate_content(
                model=self.model_name,
                contents=conversation_history,
                config=tool_config
            )
            service_log_info(f"LLM API call successful to model {self.model_name}.")
            service_log_debug(f"LLM response object: {str(response)[:500]}...") # Log snippet of raw response
            return response
        except Exception as e:
            service_log_error(f"Error calling Gemini API ({self.model_name}): {e}", exc_info=True)
            raise
