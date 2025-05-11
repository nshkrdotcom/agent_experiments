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
        possible_paths = [
            Path.cwd() / ".mcp.json",
            Path.home() / ".mcp" / "mcp.json",
        ]
        for path in possible_paths:
            if path.exists():
                logger.debug(f"Found configuration file at {path}")
                return str(path)
        logger.warning("No mcp.json found. Using default configuration.")
        return ""

    def load_config(self):
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
        return self.config.get("mcpServers", {}).get(server_name)

    def list_servers(self) -> List[str]:
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

    # ... (Rest of the MCPClient methods unchanged: _convert_mcp_tool_to_genai_function_declaration, process_query, chat_loop, cleanup)

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
        print("Usage: python client-g4.py --server <server_name> | --script <path_to_server_script> [--config <config_path>]")
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
