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
python -m textual_guis.chatgui
```

## Notes

My goal for this project is to develop a console LLM chat GUI that works with both Anthropic and OpenAI APIs. Requirements:

- Copy-paste LLM responses. Turns out the textual markdown widget doesn't support text highlighting and copying. Need to add a copy button to each message, and maybe each code and XML block
- Clear button to delete the chat history
- Concurrency: I want to be able to type the next message while waiting on the LLM
- Token counts: I want to be able to see the token counts for each message
- See XML tags: Show the XML tags in the chat history
- I want to keep a log all of the messages in a local sqlite db

## TODOs

- Clear the text input box on submission
- Retain chat history
