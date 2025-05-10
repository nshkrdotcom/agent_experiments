import asyncio
from typing import Optional
from contextlib import AsyncExitStack
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.chat = None  # Will be initialized in process_query

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.protocol = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.protocol))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str) -> str:
        """Process a query using Gemini and available tools"""
        # Initialize chat session if not already done
        if self.chat is None:
            self.chat = self.client.chats.create(model="gemini-2.0-flash")

        # Get available tools from MCP session
        response = await self.session.list_tools()
        available_tools = [
            types.Tool(
                function_declarations=[
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": {
                            k: v
                            for k, v in tool.inputSchema.items()
                            if k not in ["additionalProperties", "$schema"]
                        },
                    }
                ]
            )
            for tool in response.tools
        ]

        # Configure generation with tools
        config = types.GenerateContentConfig(
            tools=available_tools,
            temperature=0.1,
            max_output_tokens=1000
        )

        # Send initial query
        messages = [types.Content(role="user", parts=[types.Part(text=query)])]
        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=messages,
            config=config
        )

        # Process response and handle tool calls
        final_text = []

        while True:
            # Check if response contains a function call
            if response.candidates[0].content.parts and hasattr(response.candidates[0].content.parts[0], 'function_call') and response.candidates[0].content.parts[0].function_call:
                function_call = response.candidates[0].content.parts[0].function_call
                tool_name = function_call.name
                tool_args = function_call.args

                # Execute tool call via MCP session
                result = await self.session.call_tool(tool_name, tool_args)
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                # Append function call and result to conversation history
                messages.append(types.Content(
                    role="model",
                    parts=[types.Part(function_call=function_call)]
                ))
                function_response_part = types.Part.from_function_response(
                    name=tool_name,
                    response={"result": result.content}
                )
                messages.append(types.Content(
                    role="user",
                    parts=[function_response_part]
                ))

                # Send updated conversation to Gemini
                response = self.client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=messages,
                    config=config
                )
            else:
                # No function call, append text response
                if response.candidates[0].content.parts:
                    final_text.append(response.candidates[0].content.parts[0].text)
                break

        return "\n".join(final_text)

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == 'quit':
                    break

                response = await self.process_query(query)
                print("\n" + response)

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()
