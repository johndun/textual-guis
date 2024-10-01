from typing import Annotated
import random
import json
import inspect

import typer
from typer import Option

from textual_guis.llmchat import LlmChat, LlmPrompt
from textual_guis.chatgui import ChatGUI, DEFAULT_SAVE_FILE



SYSTEM_PROMPT = """\
You are an AI prompt engineer working to create an LLM workflow consisting of both LLM prompts and python functions that operate on a set of named inputs.

The user will provide input data within xml tags. They will provide descriptions of tasks to be performed on these inputs. Examples of tasks: summarize content, filter or refine a set of items. Do not perform these tasks directly. Instead, generate LLM instruction prompts or python functions to perform the user's tasks.

Python functions can be used for simple tasks. Define these functions within XML tags matching the name of the function (e.g., <dummy_func>def dummy_func...</dummy_func>). Function inputs must match XML tags found in the user inputs or tool responses. Functions must output dictionaries.

Instruction prompts should be used for tasks that are not well-suited for python functions. Prompts should contain variables denoted with xml tags and double curly braces: `<variable>{{variable}}</variable>`. Similarly, your prompts should include instructions to enclose outputs within xml tags.

Here is a minimal example showing the creation of a document summarization prompt:

<example>
user: Summarize this document:

<document>
...
</document>

assistant: <thinking>...</thinking>

<doc_summary_prompt>
Summarize the document.

Generate a summary in <summary> tags.

<document>
{{document}}
</document>
</doc_summary_prompt>
</example>

And here is an example showing the creation of a python function for counting the characters in a document:

<example>
user: Count the characters in this document:

<document>
...
</document>

assistant: <thinking>...</thinking>

<count_chars>
def count_chars(document: str) -> int:
    return len(document)
</count_chars>
</example>

Enclose each prompt or function in xml tags. After generating a prompt or function, ask the user if they would like to execute it. If yes, use the `execute_prompt` or `execute_function` tool. This will execute the prompt or function using the most recent data provided by the user.

Prompt writing guidelines:

- Prompts should include variables needed to perform the task. Prompt variables can reference user provided inputs, or the outputs of other prompts.
- Variables should be marked with xml tags **and** double curly braces.

Guidelines for assisting the user:

- Engage in a highly interactive session. Always prompt the user for inputs or confirmation before executing a prompt or function.
- After executing a prompt or function, you do not need repeat the results to the user. They will see the results in their UI. Instead, ask how they would like to continue.
"""


def execute_prompt(prompt_id: str):
    """Executes a prompt marked by XML tags in this dialog on XML-tagged inputs from the dialog

    PARAMETERS
    ----------
    prompt_id : str
        The xml tag of the prompt to be submitted
    """
    pass


def execute_function(function_id: str):
    """Executes a function marked by XML tags in this dialog on XML-tagged inputs from the dialog

    PARAMETERS
    ----------
    function_id : str
        The xml tag of the function to be executed
    """
    pass


def launch_gui(
    model: Annotated[str, Option(help="A litellm model identifier")] = "gpt-4o-mini",
    max_tokens: Annotated[int, Option(help="The maximum number of tokens to generate")] = 4096,
    top_p: Annotated[float, Option(help="The cumulative probability for top-p sampling")] = 1.0,
    temperature: Annotated[float, Option(help="The sampling temperature to use for generation")] = 0.0,
    stream: Annotated[bool, Option(help="If true, use streaming API mode")] = False,
    save_file: Annotated[str, Option(help="Path where json object containing the chat log will be saved")] = DEFAULT_SAVE_FILE
):
    """Launches a chat gui with a model backend."""
    def _execute_prompt(prompt_id: str, **kwargs):
        return LlmPrompt(prompt=kwargs[prompt_id], model=model, stream=stream)(**kwargs)

    def _execute_function(function_id: str, **kwargs):
        """
        Need to figure out how to pass the right inputs into each function.
        """
        exec(kwargs[function_id])
        # TODO: This isn't going to work. I need a reference to the function
        function_params = list(inspect.signature(function_id).parameters.keys())

    chat = LlmChat(
        system_prompt=SYSTEM_PROMPT, 
        model=model, 
        max_tokens=max_tokens, 
        top_p=top_p, 
        temperature=temperature, 
        stream=stream, 
        stream_functions=False, 
        tools=[execute_prompt, execute_function], 
        provide_xml_blocks_to_tools=True
    )
    chat.tools_map = {"execute_prompt": _execute_prompt, "execute_function": _execute_function}
    app = ChatGUI(title="Prompt Chain Assistant V2", chat=chat, save_file=save_file)
    app.run()


if __name__ == "__main__":
    typer.run(launch_gui)
