import json
import os
# import logging # No longer needed directly
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Use the new logger
from app_logger import config_log_debug, config_log_info, config_log_warning, config_log_error

# logger = logging.getLogger(__name__) # REMOVE

class AppConfig:
    def __init__(
        self,
        mcp_config_path: Optional[str] = None,
        workflows_config_path: Optional[str] = None,
    ):
        load_dotenv()
        self.google_api_key: Optional[str] = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not self.google_api_key:
            # For critical startup errors, we might still print or raise immediately
            # Or use a specific critical log if app_logger is already minimally set up.
            # For simplicity, ValueError is fine here as it's a hard stop.
            config_log_error("GOOGLE_API_KEY or GEMINI_API_KEY not found in environment.")
            raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY not found in environment.")

        self.mcp_servers: Dict[str, Any] = self._load_json_config(
            mcp_config_path, self._find_config_file("mcp_servers.json"), "mcpServers"
        )
        self.workflows: Dict[str, Any] = self._load_json_config(
            workflows_config_path, self._find_config_file("workflows.json"), "workflows"
        )
        self._validate_mcp_servers()
        self._validate_workflows()
        config_log_info("Application configuration loaded successfully.")

    def _find_config_file(self, filename: str) -> str:
        possible_paths = [
            Path.cwd() / filename,
            Path.home() / ".config" / "mcp_client" / filename,
            Path.home() / ".mcp_client" / filename,
        ]
        for path in possible_paths:
            if path.exists():
                config_log_debug(f"Found configuration file at {path}")
                return str(path)
        # This will be caught by _load_json_config if no explicit path is given
        # and default search fails.
        config_log_error(f"Could not find {filename} in standard locations or explicit path.")
        raise FileNotFoundError(f"Could not find {filename} in standard locations.")


    def _load_json_config(self, explicit_path: Optional[str], default_path_str: str, expected_key: str) -> Dict[str, Any]:
        path_to_load = Path(explicit_path) if explicit_path else Path(default_path_str)
        
        if not path_to_load.exists():
            config_log_error(f"Configuration file not found: {path_to_load}")
            raise FileNotFoundError(f"Configuration file not found: {path_to_load}")
        try:
            with open(path_to_load, 'r') as f:
                config_data = json.load(f)
            if expected_key not in config_data:
                config_log_error(f"Missing '{expected_key}' key in {path_to_load}")
                raise ValueError(f"Missing '{expected_key}' key in {path_to_load}")
            config_log_info(f"Loaded {expected_key} from {path_to_load}")
            return config_data[expected_key]
        except json.JSONDecodeError as e:
            config_log_error(f"Invalid JSON in {path_to_load}: {e}")
            raise
        except Exception as e:
            config_log_error(f"Error loading {path_to_load}: {e}")
            raise

    def _validate_mcp_servers(self):
        for name, config in self.mcp_servers.items():
            if not isinstance(config, dict):
                raise ValueError(f"Server config for '{name}' must be a dictionary.")
            if "command" not in config or "args" not in config or not isinstance(config["args"], list):
                raise ValueError(f"Server '{name}' has invalid 'command' or 'args'.")
            config.setdefault("transportType", "stdio")
            if config["transportType"] != "stdio":
                raise ValueError(f"Unsupported transportType for '{name}'.")
        config_log_debug("MCP server configurations validated.")


    def _validate_workflows(self):
        for name, wf_config in self.workflows.items():
            if not isinstance(wf_config, dict):
                raise ValueError(f"Workflow config for '{name}' must be a dictionary.")
            required_keys = ["llm_model", "mcp_servers_used", "initial_prompt_template", "max_conversation_turns"]
            for key in required_keys:
                if key not in wf_config:
                    raise ValueError(f"Workflow '{name}' missing required key: '{key}'.")
            if not isinstance(wf_config["mcp_servers_used"], list):
                raise ValueError(f"Workflow '{name}' 'mcp_servers_used' must be a list.")
            for server_name in wf_config["mcp_servers_used"]:
                if server_name not in self.mcp_servers:
                    raise ValueError(f"Workflow '{name}' uses undefined MCP server: '{server_name}'.")
        config_log_debug("Workflow configurations validated.")


    def get_mcp_server_config(self, server_name: str) -> Dict[str, Any]:
        if server_name not in self.mcp_servers:
            config_log_warning(f"Attempt to get undefined MCP Server: '{server_name}'")
            raise ValueError(f"MCP Server '{server_name}' not defined.")
        return self.mcp_servers[server_name]

    def get_workflow_config(self, workflow_name: str) -> Dict[str, Any]:
        if workflow_name not in self.workflows:
            config_log_warning(f"Attempt to get undefined Workflow: '{workflow_name}'")
            raise ValueError(f"Workflow '{workflow_name}' not defined.")
        return self.workflows[workflow_name]

    def list_workflows(self) -> List[str]:
        return list(self.workflows.keys())
