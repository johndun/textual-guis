import json
from dataclasses import dataclass
from typing import Dict, List, Callable

from litellm import completion, ModelResponse, get_model_info
from litellm.utils import function_to_dict


@dataclass
class LlmChat:
    """A class for facilitating a multi-turn chat with an LLM

    ### Usage

    ```
    chat = LlmChat(system_prompt="Talk like a pirate")
    print(chat("Hello", prefill="This be").content[0].text)
    print(chat("How are you").content[0].text)
    print(chat.usage)
    ```
    """
    model: str  #: A litellm model identifier: https://docs.litellm.ai/docs/providers (default=bedrock/anthropic.claude-3-sonnet-20240229-v1:0)
    system_prompt: str = ""  #: A system prompt (default: )
    max_tokens: int = 4096  #: The maximum number of tokens to generate (default: 4,096)
    top_p: float = 1.0  #: The cumulative probability for top-p sampling (default: 1.)
    temperature: float = 0.0  #: The sampling temperature to use for generation (default: 0.)
    tools: List[Callable] = None  #: An optional list of tools as python functions (default: None)
    max_tool_calls: int = 5  #: The maximum number of sequential tool calls (default: 5)

    def __post_init__(self):
        self.history = []
        self.clear_history()
        self.input_tokens = 0
        self.output_tokens = 0
        self.tool_schemas = []
        model_info = get_model_info(model=self.model)
        self.supports_assistant_prefill = model_info["supports_assistant_prefill"]
        self.supports_function_calling = model_info["supports_function_calling"]
        assert not self.tools or self.supports_function_calling
        if self.tools:
            self.tool_schemas = [
                {
                    "type": "function",
                    "function": function_to_dict(function)
                }
                for function in self.tools
            ]
            self.tools_map = {
                schema["function"]["name"]: function
                for schema, function in zip(self.tool_schemas, self.tools)
            }

    def clear_history(self):
        """Clears and re initializes the history"""
        self.history = []
        if self.system_prompt:
            self.history.append({"role": "system", "content": self.system_prompt})


    def _call(self, prompt: str = "", prefill: str = "", tool_call_depth: int = 0) -> ModelResponse:
        assert not prefill or self.supports_assistant_prefill
        if prompt:
            self.history.append({"role": "user", "content": prompt})
        messages = (
            self.history
            if not prefill else
            self.history + [{"role": "assistant", "content": prefill}]
        )
        response = (
            completion(
                model=self.model,
                messages=messages,
                top_p=self.top_p,
                temperature=self.temperature,
                tools=self.tool_schemas,
                max_tokens=self.max_tokens
            )
            if self.tool_schemas else
            completion(
                model=self.model,
                messages=messages,
                top_p=self.top_p,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
        )
        response.choices[0].message.content = prefill + response.choices[0].message.content
        self.history.append(response.choices[0].message.model_dump())
        self.input_tokens += response.usage.prompt_tokens
        self.output_tokens += response.usage.completion_tokens

        tool_calls = response.choices[0].message.tool_calls
        if tool_calls:
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_to_call = self.tools_map[function_name]
                function_args = json.loads(tool_call.function.arguments)
                function_response = function_to_call(**function_args)
                self.history.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": function_response,
                })
            if tool_call_depth < self.max_tool_calls:
                response = tool_chat(tool_call_depth=tool_call_depth + 1)

        return response

    def __call__(self, prompt: str = "", prefill: str = "", tool_call_depth: int = 0) -> ModelResponse:
        return self._call(prompt=prompt, prefill=prefill)

    @property
    def usage(self) -> Dict:
        """Returns a dict with `input_tokens` and `output_tokens` used"""
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens}