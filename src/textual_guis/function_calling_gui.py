from typing import Annotated
import random
import json

import typer
from typer import Option

from .llmchat import LlmChat
from .chatgui import ChatGUI


def get_weather(location: str):
    """Returns the weather for a location

    Parameters
    ----------
    location : str
        A location to fetch the weather for
    """
    import random
    options = [
        {'temperature': 26, 'temperature_units': 'C', 'summary': 'sunny, chance of rain 30%'}, 
        {'temperature': 18, 'temperature_units': 'F', 'summary': 'windy, chance of snow 80%'}
    ]
    return json.dumps(random.choice(options), indent=2)


def launch_gui(
    model: Annotated[str, Option(help="A litellm model identifier")] = "gpt-4o-mini", 
    max_tokens: Annotated[int, Option(help="The maximum number of tokens to generate")] = 4096,
    top_p: Annotated[float, Option(help="The cumulative probability for top-p sampling")] = 1.0,
    temperature: Annotated[float, Option(help="The sampling temperature to use for generation")] = 0.0,
    stream: Annotated[bool, Option(help="If true, use streaming API mode")] = False
):
    """Launches a chat gui with a model backend."""
    chat = LlmChat(
        model=model, 
        max_tokens=max_tokens, 
        top_p=top_p, 
        temperature=temperature, 
        stream=stream, 
        tools=[get_weather]
    )
    app = ChatGUI(title=model, chat=chat)
    app.run()


if __name__ == "__main__":
    typer.run(launch_gui)
