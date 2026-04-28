"""
Custom Agent framework supporting OpenAI Function Calling for Alpha Research.
🧠 2025 Revision:
- Compatible with openai>=1.0 SDK
- Automatically detects tool function parameters (based on inspect.signature)
- Automatically passes context
"""

import os
import json
import inspect
import sys
from pathlib import Path
from openai import OpenAI

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from agent_pools.poe_config import get_openai_client_kwargs, setup_poe_env, resolve_poe_model

setup_poe_env()


# ==============================
# Tool function decorator
# ==============================
def function_tool(func, name=None, description=None):
    """Wrap a Python function as a callable tool"""
    func.is_tool = True
    func.name = name or func.__name__
    func.description = description or func.__doc__ or "No description available"
    return func


# ==============================
# Agent class definition
# ==============================
class Agent:
    """
    General-purpose agent class supporting OpenAI Function Calling with automatic tool execution.
    """

    def __init__(self, name="Agent", instructions="", model="GPT-5.4", tools=None):
        self.name = name
        self.instructions = instructions
        self.model = model if model else resolve_poe_model("GPT-5.4")
        self.tools = tools or []
        from openai import OpenAI
        self.client = OpenAI(**get_openai_client_kwargs())

    def _find_tool(self, name):
        """Find a tool by name in the registered tool list"""
        for t in self.tools:
            t_name = getattr(t, "name", getattr(t, "__name__", ""))
            if t_name == name:
                return t
        return None

    def _build_tool_schema(self, func):
        """Automatically generate JSON schema for function parameters"""
        # If it's wrapped, it might have a __wrapped__ or similar, but inspect handles it mostly.
        # Fallback if func is not directly a function
        try:
            sig = inspect.signature(func)
        except ValueError:
            sig = inspect.signature(func.__call__)

        params = {}
        required = []

        for name, param in sig.parameters.items():
            if name in ("ctx", "self"):
                continue

            # Infer parameter type
            ptype = "string"
            if param.annotation == int:
                ptype = "integer"
            elif param.annotation == float:
                ptype = "number"
            elif param.annotation == bool:
                ptype = "boolean"

            params[name] = {
                "type": ptype,
                "description": f"Argument {name}"
            }
            if param.default == inspect._empty:
                required.append(name)

        return {
            "type": "object",
            "properties": params,
            "required": required,
            "additionalProperties": True
        }

    def as_tool(self, name=None, description=None, tool_name=None, tool_description=None, **kwargs):
        """Returns the agent as a callable function tool so it can be handled by other agents."""
        def tool_func(request: str, context: dict = None) -> str:
            return self.run(request, context=context)
            
        tool_func.__name__ = tool_name or name or self.name.replace(" ", "_")
        tool_func.__doc__ = tool_description or description or self.instructions or f"A sub-agent named {self.name}"
        
        # Mark it so our _build_tool_schema knows
        tool_func.is_tool = True
        return tool_func

    def run(self, user_request, context=None, max_turns=10):
        """Core execution logic: GPT planning → automatic tool execution → result aggregation"""
        print(f"\n[Agent] Starting: {self.name}")
        print(f"[Agent] Model: {self.model}")
        print(f"[Agent] User request: {user_request[:200]}...")
        print(f"[Agent] Number of available tools: {len(self.tools)}")

        # Initial conversation context
        messages = [
            {"role": "system", "content": self.instructions},
            {"role": "user", "content": user_request},
        ]

        for turn in range(max_turns):
            try:
                # Automatically build tool schemas
                tool_schemas = [
                    {
                        "type": "function",
                        "function": {
                            "name": getattr(t, "name", getattr(t, "__name__", "unknown_tool")),
                            "description": getattr(t, "description", getattr(t, "__doc__", "No description provided")),
                            "parameters": self._build_tool_schema(t)
                        }
                    }
                    for t in self.tools
                ]

                # Send request
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tool_schemas,
                    tool_choice="auto",
                )
            except Exception as e:
                print(f"OpenAI API call failed: {e}")
                return f"OpenAI API call failed: {e}"

            msg = response.choices[0].message

            # Check if a tool was called
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for call in msg.tool_calls:
                    name = call.function.name
                    args_str = call.function.arguments or "{}"

                    try:
                        args = json.loads(args_str)
                    except Exception:
                        args = {}

                    print(f"\n[Tool] Invoked: {name} | Args: {args}")

                    tool = self._find_tool(name)
                    if not tool:
                        print(f"[Warning] Tool {name} not registered.")
                        continue

                    try:
                        result = tool(context, **args) if context else tool(**args)
                        print(f"[Success] Tool executed: {name}")

                        # Feed the result back to the model
                        messages.append({
                            "role": "assistant",
                            "content": f"Tool {name} result: {str(result)[:1000]}"
                        })
                    except Exception as e:
                        print(f"[Error] Tool execution failed: {name} - {e}")
                        messages.append({
                            "role": "assistant",
                            "content": f"Error running {name}: {e}"
                        })

            else:
                # Model produced the final output
                final_output = msg.content or ""
                print("\n[Output] Final model response:\n", final_output[:800])
                return final_output

        return "Execution complete (maximum turns reached)"
