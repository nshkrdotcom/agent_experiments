import asyncio
# import logging # No longer needed directly
import sys
import argparse
import traceback
from typing import Optional # Added for type hinting

# Use the new logger and its setup functions
from app_logger import setup_logging, cli_log_info, cli_log_warning, cli_log_error, cli_log_critical, cli_log_debug
from app_logger import LOG_LEVEL_NORMAL, LOG_LEVEL_VERBOSE, LOG_LEVEL_QUIET # Import levels

from config import AppConfig
from engine import WorkflowEngine

# logger = logging.getLogger(__name__) # REMOVE

async def run_chat_loop(engine: WorkflowEngine):
    # This info is already logged by engine init and setup
    # cli_log_info(f"Starting chat with workflow: '{engine.workflow_name}'")
    # cli_log_info(f"Description: {engine.workflow_config.get('description', 'N/A')}")
    # cli_log_info(f"Using LLM model: {engine.workflow_config['llm_model']}")
    # cli_log_info(f"Connected to MCP servers: {engine.workflow_config['mcp_servers_used']}")
    print(f"\nChatting with workflow: '{engine.workflow_name}' (LLM: {engine.workflow_config['llm_model']})")
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

            print("Processing...") # User feedback
            cli_log_info(f"User query received: '{query[:50]}...'")
            response_text = await engine.process_user_query(query)
            print("\n" + response_text if response_text else "\n[No response from AI model]")

        except KeyboardInterrupt:
            cli_log_info("Chat loop interrupted by user (Ctrl+C).")
            print("\nQuery input interrupted. Type 'quit' to exit.")
        except Exception as e:
            cli_log_error(f"Error in chat loop: {e}", exc_info=True)
            print(f"\nAn error occurred in the chat loop: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Composable MCP Client with Workflows.")
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
        "--list-workflows",
        action="store_true",
        help="List available workflows and exit."
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose (debug) logging output to console and file."
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Disable all console logging (file logging might still occur at normal/verbose if configured)."
    )
    parser.add_argument(
        "--no-log-file",
        action="store_true",
        help="Disable logging to file (app_client.log)."
    )

    args = parser.parse_args()

    # --- Initialize Logging ---
    log_level = LOG_LEVEL_NORMAL
    if args.verbose:
        log_level = LOG_LEVEL_VERBOSE
    # Quiet overrides verbose for console, but file might still be verbose
    # The setup_logging function will handle console vs file level differences
    
    log_file_name = 'app_client.log' if not args.no_log_file else None

    # If --quiet is passed, we want minimal console output from the logger itself.
    # The `print` statements for user interaction will still occur.
    # `setup_logging` itself will log one "Logging initialized" message unless globally disabled.
    # If true quiet for logger is needed, then pass enable_global=False based on args.quiet
    global_logging_on = not args.quiet # If --quiet, then global logging is OFF for console
                                       # setup_logging will use LOG_LEVEL_QUIET if global_logging_on is False

    # Simplified: --quiet disables console logging from the logger.
    # --verbose enables debug level.
    # Default is INFO.
    if args.quiet:
        # Turn off console logging from the logger, file logging still possible based on log_file_name
        # This specific setup call aims to make console handler for logger very quiet
        # while potentially keeping file log active.
        # A more advanced setup_logging could take separate console/file levels.
        # For now, this effectively means only print() statements in CLI will show if --quiet
        _root_logger_instance = logging.getLogger() # Get root
        _root_logger_instance.handlers = [logging.NullHandler()] # Remove all handlers
        if log_file_name: # If file logging is still desired despite --quiet for console
            setup_logging(level=LOG_LEVEL_VERBOSE if args.verbose else LOG_LEVEL_NORMAL, log_file=log_file_name, enable_global=True)
            # Then mute console specifically
            for handler in logging.getLogger().handlers:
                if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
                    handler.setLevel(LOG_LEVEL_QUIET) # Make console handler very quiet
        else: # no file log, quiet console for logger
            setup_logging(level=LOG_LEVEL_QUIET, log_file=None, enable_global=False)


    else: # Not quiet, setup normally
        setup_logging(level=log_level, log_file=log_file_name, enable_global=True)

    cli_log_info(f"CLI started with arguments: {args}")
    if args.verbose:
        cli_log_debug("Verbose logging enabled.")
    if args.quiet:
        # Note: this log message might not appear on console if truly quiet.
        # It will go to file if file logging is enabled.
        cli_log_info("Quiet mode enabled for console logger output.")


    engine: Optional[WorkflowEngine] = None
    try:
        app_config = AppConfig(
            mcp_config_path=args.mcp_config,
            workflows_config_path=args.workflows_config
        )

        if args.list_workflows:
            print("Available workflows:")
            if not app_config.workflows:
                print("  No workflows defined in workflows.json.")
            for wf_name, wf_data in app_config.workflows.items():
                print(f"  - {wf_name}: {wf_data.get('description', 'No description')}")
            sys.exit(0)

        if not args.workflow_name:
            # Log this error before exiting
            cli_log_error("Workflow name not provided and --list-workflows not used.")
            parser.error("The 'workflow_name' argument is required unless --list-workflows is used.")
            
        cli_log_info(f"Selected workflow: '{args.workflow_name}'")
        engine = WorkflowEngine(args.workflow_name, app_config)
        await engine.setup_services()

        if args.query:
            cli_log_info(f"Processing single query for workflow '{args.workflow_name}': '{args.query[:50]}...'")
            response = await engine.process_user_query(args.query)
            print(response) # Direct output for single query
        else:
            await run_chat_loop(engine)

    except FileNotFoundError as e:
        cli_log_error(f"Configuration file error: {e}", exc_info=args.verbose) # Only full exc_info if verbose
        print(f"ERROR: Configuration file not found - {e}")
        print("Please ensure mcp_servers.json and workflows.json exist in CWD, ~/.config/mcp_client/, or ~/.mcp_client/")
    except ValueError as e: 
        cli_log_error(f"Configuration or setup error: {e}", exc_info=args.verbose)
        print(f"ERROR: {e}")
    except Exception as e:
        cli_log_critical(f"An unexpected critical error occurred in main: {e}", exc_info=True) # Always exc_info for critical
        print(f"CRITICAL ERROR: {e}\nCheck log file for details (default: app_client.log).")
        if args.verbose: # If verbose, also print traceback to console
            traceback.print_exc()
    finally:
        if engine:
            await engine.close()
        cli_log_info("CLI main function finished.")
        # logging.shutdown() # Handled by app_logger or implicitly by Python exit

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # This might be logged by main()'s finally block if it reaches there,
        # or we can log it here too.
        # If setup_logging hasn't run (e.g. error in argparse), this log might go nowhere.
        cli_log_info("Program interrupted by user (Ctrl+C at top level).")
        print("\nProgram interrupted. Exiting.")
    except Exception as e:
        # Catch-all for truly unexpected errors before logging is even set up
        # or if asyncio.run itself fails spectacularly.
        # If app_logger is initialized, use it. Otherwise, plain print.
        try:
            cli_log_critical(f"Fatal error during program execution: {str(e)}", exc_info=True)
        except Exception: # Logging system itself might be broken
            print(f"A FATAL, UNLOGGED ERROR OCCURRED: {e}")
            traceback.print_exc()
        print(f"A fatal error occurred: {e}")
    finally:
        # Ensure logs are flushed. Standard logging does this at shutdown.
        # If using custom handlers that need explicit flush, do it here.
        pass
