from typing import Annotated
import random
import json

import typer
from typer import Option

from textual_guis.llmchat import LlmChat, LlmPrompt
from textual_guis.chatgui import ChatGUI



SYSTEM_PROMPT = """\
You are an AI prompt engineer. Help the user create LLM prompts that operate on a provided set of inputs.

The user will provide input data within <xml> tags. They will provide descriptions of tasks to be performed on these inputs. Examples of tasks: summarize content, filter or refine a set of items. Do not perform these tasks directly. Instead, generate an LLM instruction prompt that performs the task. Your instruction prompts will contain variables indicated using xml tags and double curly braces: `<variable>{{variable}}</variable>`.

Here is a minimal example showing the proper creation of a document summarization prompt:

<example>
user: Summarize this document:

<document>
...
</document>

assistant: ...
<doc_summary_prompt>
Summarize the document.

Generate a summary in <summary> tags.

<document>
{{document}}
</document>
</doc_summary_prompt>
</example>

Enclose each prompt in xml tags using an informative <prompt_id>. After generating a prompt, ask the user if they would like to execute it. If yes, use the `execute_prompt` tool. This will execute the prompt using the most recent data provided by the user.
Prompt writing guidelines:

- Each prompt should include variables needed to perform the task. Prompt variables can reference user provided inputs, or the outputs of other prompts. This enables the creation of chains of prompts for more complex tasks.
- Variables should be marked with xml tags and double curly braces. Both are needed.
- Write general purpose prompts that can be applied to other inputs like the ones provided by the user.

Guidelines for assisting the user:

- After executing a prompt, do not repeat the results to the user. They will see the results in their UI. Instead, ask how they would like to continue.
"""


def execute_prompt(prompt_id: str):
    """Submit a prompt indicated by the prompt tag using the most recent data provided by the user.

    PARAMETERS
    ----------
    prompt_id : str
        The xml tag of the prompt to be submitted.
    """
    pass


def launch_gui(
    model: Annotated[str, Option(help="A litellm model identifier")] = "gpt-4o-mini", 
    max_tokens: Annotated[int, Option(help="The maximum number of tokens to generate")] = 4096,
    top_p: Annotated[float, Option(help="The cumulative probability for top-p sampling")] = 1.0,
    temperature: Annotated[float, Option(help="The sampling temperature to use for generation")] = 0.0,
    stream: Annotated[bool, Option(help="If true, use streaming API mode")] = False
):
    """Launches a chat gui with a model backend."""
    def _execute_prompt(prompt_id: str, **kwargs):
        return LlmPrompt(prompt=kwargs[prompt_id], model=model)(**kwargs)

    chat = LlmChat(
        system_prompt=SYSTEM_PROMPT, 
        model=model, 
        max_tokens=max_tokens, 
        top_p=top_p, 
        temperature=temperature, 
        stream=stream, 
        tools=[execute_prompt]
    )
    chat.tools_map = {"execute_prompt": _execute_prompt}
    app = ChatGUI(title=model, chat=chat)
    app.run()


if __name__ == "__main__":
    typer.run(launch_gui)
