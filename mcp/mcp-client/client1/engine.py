# import logging # No longer needed
import traceback
from typing import Dict, Any, List, Optional
from contextlib import AsyncExitStack

from google.genai import types as genai_types

from config import AppConfig
from services import MCPService, LLMService, Tool 

# Use the new logger
from app_logger import engine_log_debug, engine_log_info, engine_log_warning, engine_log_error, engine_log_critical

# logger = logging.getLogger(__name__) # REMOVE

class WorkflowEngine:
    def __init__(self, workflow_name: str, app_config: AppConfig):
        self.workflow_name = workflow_name
        self.app_config = app_config
        self.workflow_config: Dict[str, Any] = self.app_config.get_workflow_config(workflow_name)
        engine_log_info(f"WorkflowEngine initialized for workflow: '{workflow_name}'")
        
        self.llm_service = LLMService(
            model_name=self.workflow_config["llm_model"],
            api_key=self.app_config.google_api_key
        )
        self.mcp_services: Dict[str, MCPService] = {} 
        self.all_mcp_tools: List[Tool] = [] 
        self.exit_stack = AsyncExitStack()

    async def setup_services(self):
        engine_log_info(f"Setting up services for workflow: {self.workflow_name}")
        for server_name in self.workflow_config["mcp_servers_used"]:
            server_cfg = self.app_config.get_mcp_server_config(server_name)
            service = MCPService(server_name, server_cfg, self.exit_stack)
            try:
                await service.connect() 
                self.mcp_services[server_name] = service
                # It's good practice to log what tools are actually available after connection
                current_server_tools = await service.get_tools()
                engine_log_info(f"MCP Server '{server_name}' connected with tools: {[t.name for t in current_server_tools]}")
                self.all_mcp_tools.extend(current_server_tools)
            except Exception as e:
                engine_log_error(f"Failed to connect or setup MCP service '{server_name}' for workflow '{self.workflow_name}': {e}", exc_info=True)
                # Decide if this is fatal for the workflow or if it can proceed without this server
                # For now, we'll let it raise, or you could collect errors and report.
                raise
        engine_log_info(f"Workflow services setup complete. Total MCP tools available for '{self.workflow_name}': {len(self.all_mcp_tools)} ({[t.name for t in self.all_mcp_tools]})")


    async def process_user_query(self, user_query: str) -> str:
        engine_log_info(f"Processing query for workflow '{self.workflow_name}': '{user_query[:50]}...'")
        if not self.mcp_services and self.workflow_config["mcp_servers_used"]:
             engine_log_error("MCP services not set up but workflow requires them. Call setup_services() first.")
             return "Error: Workflow services are not initialized."

        initial_prompt = self.workflow_config["initial_prompt_template"].format(query=user_query)
        engine_log_debug(f"Initial prompt for LLM: {initial_prompt}")
        conversation_history: List[genai_types.Content] = [
            genai_types.Content(parts=[genai_types.Part(text=initial_prompt)], role="user")
        ]
        
        final_response_parts = []
        max_turns = self.workflow_config.get("max_conversation_turns", 5)
        
        llm_tool_config = self.llm_service.prepare_tools_for_llm(self.all_mcp_tools)

        for turn in range(max_turns):
            engine_log_info(f"Workflow '{self.workflow_name}', Turn {turn + 1}/{max_turns}")
            engine_log_debug(f"Conversation history length before LLM call: {len(conversation_history)}")
            
            try:
                llm_response = await self.llm_service.generate_response(conversation_history, llm_tool_config)
            except Exception as e:
                err_msg = f"Error communicating with LLM in workflow '{self.workflow_name}': {e}"
                engine_log_error(err_msg, exc_info=True)
                final_response_parts.append(f"\n[{err_msg}]")
                break

            if not llm_response.candidates:
                engine_log_warning(f"LLM returned no candidates for workflow '{self.workflow_name}'.")
                final_response_parts.append("\n[AI model returned no response candidates.]")
                break
            
            model_content = llm_response.candidates[0].content
            engine_log_debug(f"LLM response model_content (turn {turn+1}): {model_content}")
            conversation_history.append(model_content)

            has_function_call = False
            for part_idx, part in enumerate(model_content.parts):
                engine_log_debug(f"Processing part {part_idx+1} of LLM response: {part}")
                if part.text:
                    engine_log_info(f"LLM text response (turn {turn+1}): '{part.text[:100]}...'")
                    final_response_parts.append(part.text)

                if part.function_call:
                    has_function_call = True
                    fc = part.function_call
                    tool_name = fc.name
                    tool_args = dict(fc.args) if fc.args else {}
                    engine_log_info(f"LLM requests tool call: '{tool_name}' with args: {tool_args}")
                    
                    tool_executed = False
                    tool_result_for_llm: Dict[str, Any] = {}

                    # Find which MCP service provides this tool
                    # This assumes tool names are unique across all connected MCP services for this workflow.
                    # If not, a more sophisticated dispatch (e.g., tool_name could be 'service_name/tool_name')
                    # or prioritization might be needed.
                    found_service_for_tool: Optional[MCPService] = None
                    for service_name, mcp_service in self.mcp_services.items():
                        service_tools = await mcp_service.get_tools() 
                        if any(t.name == tool_name for t in service_tools):
                            found_service_for_tool = mcp_service
                            engine_log_debug(f"Tool '{tool_name}' found in MCP service '{service_name}'.")
                            break
                    
                    if found_service_for_tool:
                        try:
                            mcp_result = await found_service_for_tool.call_tool(tool_name, tool_args)
                            engine_log_info(f"Tool '{tool_name}' executed by '{found_service_for_tool.server_name}'. Result snippet: {str(mcp_result)[:100]}...")
                            engine_log_debug(f"Full result from tool '{tool_name}': {mcp_result}")
                            
                            if isinstance(mcp_result, dict):
                                tool_result_for_llm = mcp_result
                            else: 
                                tool_result_for_llm = {"output": mcp_result}
                            tool_executed = True
                        except Exception as e:
                            error_msg = f"Error executing MCP tool '{tool_name}' via '{found_service_for_tool.server_name}': {e}"
                            engine_log_error(error_msg, exc_info=True)
                            tool_result_for_llm = {"error": error_msg, "details": traceback.format_exc(limit=3)}
                    else:
                        error_msg = f"Tool '{tool_name}' requested by LLM but not found in any active MCP service for workflow '{self.workflow_name}'."
                        engine_log_error(error_msg)
                        tool_result_for_llm = {"error": error_msg}
                    
                    tool_response_part = genai_types.Part.from_function_response(
                        name=tool_name, response=tool_result_for_llm
                    )
                    engine_log_debug(f"Adding tool response for '{tool_name}' to history: {tool_result_for_llm}")
                    conversation_history.append(genai_types.Content(parts=[tool_response_part], role="user"))
                    # Important: if a function call was processed, we break from processing *parts*
                    # and let the next *turn* happen so LLM can react to the tool output.
                    break 
            
            if not has_function_call:
                engine_log_info(f"No function call in LLM response (turn {turn+1}). Assuming final answer for workflow '{self.workflow_name}'.")
                if not any(p.strip() for p in final_response_parts) and hasattr(llm_response, 'text') and llm_response.text:
                    engine_log_debug(f"Using llm_response.text as fallback: {llm_response.text}")
                    final_response_parts.append(llm_response.text)
                if not any(p.strip() for p in final_response_parts): # Still nothing
                     engine_log_warning("LLM provided no text and no function call. Ending turn.")
                     final_response_parts.append("[AI model provided no further text or actions.]")
                break # Break from turns loop

        else: # Max turns reached
            engine_log_warning(f"Max turns ({max_turns}) reached for workflow '{self.workflow_name}'.")
            if not any(p.strip() for p in final_response_parts):
                final_response_parts.append("\n[Max interaction turns reached. No final text generated.]")
            else:
                final_response_parts.append("\n[Max interaction turns reached.]")

        final_text_output = "".join(final_response_parts).strip()
        engine_log_info(f"Final response for query: '{final_text_output[:100]}...'")
        return final_text_output

    async def close(self):
        engine_log_info(f"Closing services for workflow: {self.workflow_name}")
        await self.exit_stack.aclose()
        engine_log_info(f"Workflow services closed for '{self.workflow_name}'.")
