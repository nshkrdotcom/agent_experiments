import asyncio
import sys
import argparse
import traceback
import logging # Keep for accessing logging constants like INFO, DEBUG
from typing import Optional 
import json # For engine_log_user tool args formatting

# Use the new logger and its setup functions
from app_logger import (
    setup_logging, 
    cli_log_info, cli_log_warning, cli_log_error, cli_log_critical, cli_log_debug,
    LOG_LEVEL_NORMAL, LOG_LEVEL_VERBOSE, LOG_LEVEL_QUIET, LOG_LEVEL_USER_INTERACTION
)

from config import AppConfig
from engine import WorkflowEngine


async def run_chat_loop(engine: WorkflowEngine):
    print(f"\nChatting with workflow: '{engine.workflow_name}' (LLM: {engine.workflow_config['llm_model']})")
    tool_names_str = ', '.join([tool.name for tool in engine.all_mcp_tools]) if engine.all_mcp_tools else 'None'
    print(f"Available tools: {tool_names_str}")
    print("Type your queries or 'quit' to exit.")

    while True:
        try:
            query = await asyncio.to_thread(input, "\nQuery: ")
            query = query.strip()
            
            if query.lower() == 'quit':
                cli_log_info("User requested quit from chat loop.")
                break
            if not query:
                print("Please enter a query.")
                continue

            print("Processing...") 
            cli_log_info(f"User query received: '{query[:70]}...'") 
            response_text = await engine.process_user_query(query)
            print("\n" + response_text if response_text else "\n[No response from AI model]")

        except KeyboardInterrupt:
            cli_log_info("Chat loop interrupted by user (Ctrl+C).")
            print("\nQuery input interrupted. Type 'quit' to exit.")
        except Exception as e:
            cli_log_error(f"Error in chat loop: {e}", exc_info=True) # exc_info=True is fine here
            print(f"\nAn error occurred in the chat loop: {e}")


async def main():
    parser = argparse.ArgumentParser(
        description="Composable MCP Client with Workflows.",
        formatter_class=argparse.RawTextHelpFormatter # Allows newlines in help
    )
    parser.add_argument(
        "workflow_name", 
        nargs='?',
        help="Name of the workflow to run (defined in workflows.json)."
    )
    parser.add_argument(
        "--query", 
        help="A single query to process (non-interactive mode)."
    )
    parser.add_argument(
        "--mcp-config",
        help="Path to custom mcp_servers.json configuration file."
    )
    parser.add_argument(
        "--workflows-config",
        help="Path to custom workflows.json configuration file."
    )
    parser.add_argument(
        "--list-workflows", "-l",
        action="store_true",
        help="List available workflows and exit."
    )
    parser.add_argument(
        "--log-level",
        choices=['quiet', 'user', 'normal', 'verbose'],
        default='user', 
        help=(
            "Set console logging verbosity:\n"
            "  quiet   : Almost no log output from the app's logger to console.\n"
            "  user    : Key interactions like LLM turns, tool calls (default).\n"
            "  normal  : More operational info (INFO level).\n"
            "  verbose : Detailed debug output (DEBUG level)."
        )
    )
    parser.add_argument(
        "--no-log-file",
        action="store_true",
        help="Disable logging to file (default: app_client.log)."
    )

    args = parser.parse_args()

    console_log_level_map = {
        'quiet': LOG_LEVEL_QUIET,
        'user': LOG_LEVEL_USER_INTERACTION,
        'normal': LOG_LEVEL_NORMAL,
        'verbose': LOG_LEVEL_VERBOSE,
    }
    chosen_console_level = console_log_level_map.get(args.log_level, LOG_LEVEL_USER_INTERACTION)
    
    # Determine the master level for the application loggers.
    # This should be the most verbose level required by any handler.
    # File handler is always VERBOSE if active. Console handler is chosen_console_level.
    app_master_level = LOG_LEVEL_VERBOSE # Default to verbose if file logging is on
    if args.no_log_file: # If no file log, master level can match console
        app_master_level = chosen_console_level
    else: # File log is active, ensure it gets everything
        app_master_level = LOG_LEVEL_VERBOSE 
    
    # Ensure chosen_console_level is not more verbose than app_master_level if app_master_level is lower
    # (e.g., if somehow app_master_level was set to NORMAL and console to VERBOSE, this would cap console)
    # However, with current logic, app_master_level will be >= chosen_console_level.
    # No, this is not quite right. Root logger level should be min(all_handler_levels).
    # Let setup_logging handle it: pass the most verbose needed to 'level'
    # and specific console level to 'console_level_override'.

    effective_app_level_for_setup = LOG_LEVEL_VERBOSE # Assume file wants all details
    if args.no_log_file:
        effective_app_level_for_setup = chosen_console_level # No file, so app only needs to be as verbose as console

    log_file_name = 'app_client.log' if not args.no_log_file else None
    
    setup_logging(
        level=effective_app_level_for_setup, 
        console_level_override=chosen_console_level, 
        log_file=log_file_name,
        enable_global=True 
    )
    
    cli_log_info(f"CLI started with arguments: {args}")
    if chosen_console_level == LOG_LEVEL_VERBOSE:
        cli_log_debug("Verbose (DEBUG) console logging enabled.")
    
    engine: Optional[WorkflowEngine] = None
    try:
        app_config = AppConfig(
            mcp_config_path=args.mcp_config,
            workflows_config_path=args.workflows_config
        )

        if args.list_workflows:
            print("\nAvailable workflows:")
            if not app_config.workflows:
                print("  No workflows defined in workflows.json.")
            else:
                for wf_name, wf_data in app_config.workflows.items():
                    print(f"  - {wf_name}: {wf_data.get('description', 'No description')}")
            sys.exit(0)

        if not args.workflow_name:
            cli_log_error("Workflow name not provided and --list-workflows not used.")
            parser.print_help()
            print("\nError: The 'workflow_name' argument is required unless --list-workflows is used.")
            if app_config.list_workflows():
                 print(f"Available workflows: {', '.join(app_config.list_workflows())}")
            sys.exit(1)
            
        cli_log_info(f"Selected workflow: '{args.workflow_name}'")
        engine = WorkflowEngine(args.workflow_name, app_config)
        await engine.setup_services()

        if args.query:
            cli_log_info(f"Processing single query for workflow '{args.workflow_name}': '{args.query[:70]}...'")
            response = await engine.process_user_query(args.query)
            print(response) 
        else:
            await run_chat_loop(engine)

    except FileNotFoundError as e:
        cli_log_error(f"Configuration file error: {e}", exc_info=(chosen_console_level == LOG_LEVEL_VERBOSE))
        print(f"ERROR: Configuration file not found - {e}")
        print("Please ensure mcp_servers.json and workflows.json exist in CWD, ~/.config/mcp_client/, or ~/.mcp_client/")
    except ValueError as e: 
        cli_log_error(f"Configuration or setup error: {e}", exc_info=(chosen_console_level == LOG_LEVEL_VERBOSE))
        print(f"ERROR: {e}")
    except Exception as e:
        cli_log_critical(f"An unexpected critical error occurred in main: {e}", exc_info=True) 
        print(f"CRITICAL ERROR: {e}\nCheck log file for details (default: app_client.log).")
        if chosen_console_level == LOG_LEVEL_VERBOSE: 
            traceback.print_exc()
    finally:
        if engine:
            await engine.close()
        cli_log_info("CLI main function finished.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        cli_log_info("Program interrupted by user (Ctrl+C at top level).")
        print("\nProgram interrupted. Exiting.")
    except Exception as e:
        try:
            cli_log_critical(f"Fatal error during program execution: {str(e)}", exc_info=True)
        except Exception: 
            print(f"A FATAL, UNLOGGED ERROR OCCURRED: {e}")
            traceback.print_exc()
        print(f"A fatal error occurred: {e}")
    finally:
        logging.shutdown() # Ensure all handlers are flushed and closed