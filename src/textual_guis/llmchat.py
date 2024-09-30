import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Callable, Union, Generator

from datasets import Dataset

from litellm import completion, ModelResponse, get_model_info, stream_chunk_builder
from litellm.utils import function_to_dict

from textual_guis.utils import Template, parse_text_for_tags


@dataclass
class Tokens:
    """Counts tokens"""
    last_input_tokens: int = 0
    last_output_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, input_tokens, output_tokens):
        self.last_input_tokens = input_tokens
        self.input_tokens += input_tokens
        self.last_output_tokens = output_tokens
        self.output_tokens += output_tokens

    @property
    def last(self):
        """Returns formatted string containing last message token counts"""
        return f"in: {self.last_input_tokens:,.0f}, out: {self.last_output_tokens:,.0f}"

    @property
    def total(self):
        """Returns formatted string containing total token counts"""
        return f"in: {self.input_tokens:,.0f}, out: {self.output_tokens:,.0f}"


@dataclass
class LlmChat:
    """A class for facilitating a multi-turn chat with an LLM

    ### Usage

    ```
    chat = LlmChat(system_prompt="Talk like a pirate")
    print(chat("Hello"))
    print(chat("How are you"))
    print(chat.tokens.total)
    ```
    """
    model: str = "gpt-4o-mini"  #: A litellm model identifier: https://docs.litellm.ai/docs/providers
    system_prompt: str = ""  #: A system prompt (default: )
    max_tokens: int = 4096  #: The maximum number of tokens to generate (default: 4,096)
    top_p: float = 1.0  #: The cumulative probability for top-p sampling (default: 1.)
    temperature: float = 0.0  #: The sampling temperature to use for generation (default: 0.)
    tools: List[Callable] = None  #: An optional list of tools as python functions (default: None)
    max_tool_calls: int = 6  #: The maximum number of sequential tool calls (default: 6)
    stream: bool = False  #: If true, use streaming API mode
    stream_functions: bool = False  #: If this and `stream` are true, function responses are also streamed
    provide_xml_blocks_to_tools: bool = False  #: If true, XML blocks will as kwargs to function calls 

    def __post_init__(self):
        self.history = []
        self.clear_history()
        self.tokens = Tokens()
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

    def get_tool_responses(self, tool_calls):
        response_text = ""
        for tool_call in tool_calls:
            response_text += "\n\n#### Tool call:\n\n```tool_call\n" + json.dumps(dict(tool_call.function), indent=2) + "\n```"
            function_name = tool_call.function.name
            function_to_call = self.tools_map[function_name]
            function_args = json.loads(tool_call.function.arguments)
            if self.provide_xml_blocks_to_tools:
                for msg in self.history:
                    for xml_block in parse_text_for_tags(msg["content"]):
                        function_args[xml_block.tag] = xml_block.content
            function_response = function_to_call(**function_args) or ""
            response_text += "\n\n#### Tool response:\n\n" + function_response
            self.history.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": function_name,
                "content": function_response,
            })
        return response_text + "\n\n"

    def get_tool_responses_stream(self, tool_calls):
        response_text = ""
        for tool_call in tool_calls:
            response_text += "\n\n#### Tool call:\n\n```tool_call\n" + json.dumps(dict(tool_call.function), indent=2) + "\n```"
            function_name = tool_call.function.name
            function_to_call = self.tools_map[function_name]
            function_args = json.loads(tool_call.function.arguments)
            if self.provide_xml_blocks_to_tools:
                for msg in self.history:
                    for xml_block in parse_text_for_tags(msg["content"]):
                        function_args[xml_block.tag] = xml_block.content
            response_text += "\n\n#### Tool response:\n\n"
            function_response = ""
            for chunk in function_to_call(**function_args):
                function_response += chunk
                yield response_text + function_response
            response_text += function_response + "\n\n"
            yield response_text
            self.history.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": function_name,
                "content": function_response,
            })

    def get_messages_for_completion(self, prompt: str, prefill: str) -> List[Dict]:
        assert not prefill or self.supports_assistant_prefill
        if prompt:
            self.history.append({"role": "user", "content": prompt})
        messages = (
            self.history
            if not prefill else
            self.history + [{"role": "assistant", "content": prefill}]
        )
        if self.system_prompt:
            messages = [{"role": "system", "content": self.system_prompt}] + messages
        return messages

    def _call(self, prompt: str = "", prefill: str = "", tool_call_depth: int = 0) -> ModelResponse:
        messages = self.get_messages_for_completion(prompt, prefill)
        completion_args = {"tools": self.tool_schemas} if self.tool_schemas else {}
        response = completion(
            model=self.model,
            messages=messages,
            top_p=self.top_p,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            **completion_args
        )
        response_text = prefill + (response.choices[0].message.content or "")
        response.choices[0].message.content = response_text
        self.history.append(response.choices[0].message.model_dump())
        self.tokens.add(response.usage.prompt_tokens, response.usage.completion_tokens)

        tool_calls = response.choices[0].message.tool_calls
        if tool_calls:
            response_text += self.get_tool_responses(tool_calls)
            if tool_call_depth < self.max_tool_calls:
                response_text += self._call(tool_call_depth=tool_call_depth + 1)

        return response_text

    def _call_stream(self, prompt: str = "", prefill: str = "", tool_call_depth: int = 0) -> ModelResponse:
        messages = self.get_messages_for_completion(prompt, prefill)
        completion_args = {"tools": self.tool_schemas} if self.tool_schemas else {}
        response = completion(
            model=self.model,
            messages=messages,
            top_p=self.top_p,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
            stream_options={"include_usage": True},
            **completion_args
        )

        response_text = prefill
        for chunk in response:
            chunk_text = chunk.choices[0].delta.content
            if chunk_text:
                response_text += chunk_text
                yield response_text

        response = stream_chunk_builder(response.chunks, messages=messages)
        self.history.append(response.choices[0].message.model_dump())
        self.tokens.add(response.usage.prompt_tokens, response.usage.completion_tokens)

        tool_calls = response.choices[0].message.tool_calls
        if tool_calls:
            if not self.stream_functions:
                response_text += self.get_tool_responses(tool_calls)
                yield response_text
            else:
                for chunk in self.get_tool_responses_stream(tool_calls):
                    yield response_text + chunk
                response_text += chunk
            
            if tool_call_depth < self.max_tool_calls:
                for chunk in self._call_stream(tool_call_depth=tool_call_depth + 1):
                    yield response_text + chunk

    def __call__(self, prompt: str = "", prefill: str = "") -> Union[str, Generator]:
        if not self.stream:
            return self._call(prompt=prompt, prefill=prefill)
        else:
            return self._call_stream(prompt=prompt, prefill=prefill)


@dataclass
class LlmPrompt(LlmChat):
    """A class for prompting an LLM with a prompt template

    ### Usage

    ```
    chat = LlmPrompt(system_prompt="Talk like a pirate")
    print(chat(prompt="Hello"))
    print(chat(prompt="How are you"))
    print(chat.tokens.total)
    ```
    """
    prompt: str = "{{prompt}}"  #: A string template with keys marked by double curly braces.

    def __call__(self, prefill="", **kwargs) -> Union[str, Generator]:
        return self._call(prompt=Template(self.prompt).format(**kwargs), prefill=prefill)


@dataclass
class MockLlmChat(LlmChat):
    """A mock chat class for testing"""
    response: str = "Hello world"

    def __call__(self, prefill="", **kwargs) -> str:
        return self.response


def batch_inference(
        prompt: str,
        dataset: Dataset,
        num_proc: int = 1,
        prefill: str = "",
        **kwargs
) -> Dataset:
    """Batch inference given a dataset and a prompt.

    ### Usage

    ```
    topics = ["space", "cats", "gardening", "unicorns"]
    dataset = Dataset.from_list([{"topic": topic} for topic in topics])
    dataset = batch_inference(
        system_prompt="Talk like a pirate",
        prompt="Write a haiku, enclosed in <haiku> tags about {{topic}}",
        dataset=dataset,
        client="bedrock",
        model="sonnet",
        num_proc=4
    )
    print(dataset[0])
    ```

    ### Args

    `prompt: str`
    :   A string template with keys marked by double curly braces.

    `dataset: Dataset`
    :   A dataset with fields corresponding to keys in `prompt`.

    `num_proc: int`
    :   The number of processes to use (default: 1)

    `prefill: str`
    :   A prefill string for the LLM response (default: )

    ### Returns

    `dataset` with new fields: `response`, `input_tokens`, and `output_tokens`. If the LLM API call
    fails for any reason, `response` will be empty.
    """

    def call_api(sample):
        chat = LlmPrompt(prompt=prompt, **kwargs)
        try:
            sample["response"] = chat(**sample)
            sample["input_tokens"] = chat.tokens.input_tokens
            sample["output_tokens"] = chat.tokens.output_tokens
        except Exception as e:
            print(e)
            sample["response"] = ""
            sample["input_tokens"] = 0
            sample["output_tokens"] = 0
        return sample

    dataset = dataset.map(call_api, num_proc=num_proc, batched=False)
    return dataset
