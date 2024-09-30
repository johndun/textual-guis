# textual-guis

LLM chat gui using textual

## Setup

Download from github:

```bash
git clone https://github.com/johndun/textual-guis.git
cd textual-guis
```

Create python environment:

```bash
mkdir venv
python3 -m venv venv
source venv/bin/activate
```

Install using `pip`:

```bash
pip install -e .
```

Launch the chat gui:

```bash
export OPENAI_API_KEY=...
python -m textual_guis.chatgui --help

 Usage: python -m textual_guis.chatgui [OPTIONS]

 Launches a chat gui with a model backend.

╭─ Options ───────────────────────────────────────────────────────────────────────────────────────╮
│ --model              TEXT     A litellm model identifier [default: gpt-4o]                      │
│ --max-tokens         INTEGER  The maximum number of tokens to generate [default: 4096]          │
│ --top-p              FLOAT    The cumulative probability for top-p sampling [default: 1.0]      │
│ --temperature        FLOAT    The sampling temperature to use for generation [default: 0.0]     │
│ --help                        Show this message and exit.                                       │
╰─────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## Notes

[x] Mock LLM chat class
[x] Remove hard coded CSS classes in chatcontainer widgets.
[x] When a chat message is added, parse for XML tags.
    [x] Initialize an `objects` parameter in the app class.
    [x] When the user enters a chat message, parse the text and add any XML blocked content to self.objects
    [x] When the bot enters a chat message, parse the text and add any XML blocked content to self.objects


Completed: 

- Streaming interface: https://gist.github.com/willmcgugan/648a537c9d47dafa59cb8ece281d8c2c
- Clear button to delete the chat history
- Token counts: I want to be able to see the token counts for each message
- See XML tags: Show the XML tags in the chat history
- Copy-paste LLM responses. Turns out the textual markdown widget doesn't support text highlighting and copying. Need to add a copy button to each message, and maybe each code and XML block
- Concurrency: I want to be able to type the next message while waiting on the LLM
- Clear the text input box on submission
- Retain chat history
