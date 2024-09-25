import asyncio
import subprocess
import json
import re

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll, Container, HorizontalScroll, ScrollableContainer
from textual.widgets import (
    Static, Header, Footer, Markdown, 
    TabbedContent, TabPane, Select, TextArea, Input
)
from textual.binding import Binding
from textual import work, on

from litellm import completion
import typer

from typer import Option
from typing_extensions import Annotated

from textual_guis.llmchat import LlmChat
from textual_guis.chatcontainer import ChatContainer, Message


TEMPERATURES = [0.0, 0.1, 0.3, 0.7, 1.0]
TOP_P = [0.5, 0.9, 0.99, 1.0]
MODELS = [
    "gpt-4o", 
    "gpt-4o-mini", 
    "claude-3-5-sonnet-20240620"
]
SAVE_DATA_PATH = "chatlog.json"


def escape_text(markdown_text):
    # Function to escape XML tags
    def escape(match):
        return '\\' + match.group(0)

    # Split the text into code and non-code parts
    parts = re.split(r'(```[\s\S]*?```)', markdown_text)

    # Process each part
    for i in range(len(parts)):
        if i % 2 == 0:  # Non-code part
            # Escape XML tags
            parts[i] = re.sub(r'<[^>]*>', escape, parts[i])

    # Join all parts back together
    return ''.join(parts)


def extract_number(prefix, s):
    pattern = f'^{re.escape(prefix)}-(\\d+)$'
    match = re.match(pattern, s)
    
    if match:
        return int(match.group(1))
    else:
        return None


class ChatGUI(App):
    """Simple LLM chat GUI"""

    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+r", "", "Submit"),
        Binding("ctrl+s", "save", "Save")
    ]

    def __init__(
            self, 
            chat: LlmChat, 
            title: str = "LLM Chat", 
            save_file: str = SAVE_DATA_PATH
    ):
        super().__init__()
        self.chat = chat
        self.title = title
        self.save_file = save_file
        self.n_user_messages = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Config"):
                with VerticalScroll():
                    with Container(classes="inputs-container"):
                        with Container():
                            yield Static("Model")
                            yield Select.from_values(MODELS, id="model-selector")
                        with Container():
                            yield Static("Temp")
                            yield Select.from_values(TEMPERATURES, id="temp-selector")
                        with Container():
                            yield Static("Top-P")
                            yield Select.from_values(TOP_P, id="top_p-selector")
                    with Container(classes="config-text-inputs-container"):
                        yield Static("Save file path:")
                        yield Input(SAVE_DATA_PATH, id="save-file-input")
                    with Container(classes="config-text-inputs-container"):
                        yield Static("System Prompt:")
                        yield TextArea.code_editor(
                            self.chat.system_prompt,
                            id="system-prompt-input",
                            language="markdown",
                            soft_wrap=True
                        )
            with TabPane("Chat"):
                yield ChatContainer()
        yield Footer(show_command_palette=False)

    @on(Select.Changed, "#model-selector,#temp-selector,#top_p-selector,#save-file-selector")
    def select_changed(self, event: Select.Changed) -> None:
        assert event.select.id is not None
        if event.select.id == "model-selector":
            self.chat.model = event.value
            self.title = event.value
        elif event.select.id == "temp-selector":
            self.chat.temperature = event.value
        elif event.select.id == "top_p-selector":
            self.chat.top_p = event.value

    @on(Input.Changed, "#save-file-input")
    def input_changed(self, event: Input.Changed) -> None:
        self.save_file = event.value

    @on(TextArea.Changed, "#system-prompt-input")
    def text_area_changed(self, event: TextArea.Changed) -> None:
        assert event.text_area.id is not None
        if event.text_area.id == "system-prompt-input":
            self.chat.system_prompt = event.text_area.text

    def action_copy(self) -> None:
        copy_button = self.query_one(".message-container.hovered > .message-buttons > .copy")
        copy_button.update("copied")
        copy_button.add_class("copied")
        hovered = self.query_one(".message-container.hovered")
        msg = hovered.markdown
        msg = msg.lstrip("**User**: ").replace("\\<", "<")
        process = subprocess.Popen(
            'pbcopy',
            env={'LANG': 'en_US.UTF-8'},
            stdin=subprocess.PIPE
        )
        process.communicate(msg.encode('utf-8'))
        asyncio.create_task(self.reset_text())

    def action_goto(self) -> None:
        msgs = self.query_one("#chat-log-container")
        start_dropping = False
        for msg in msgs.children:
            if msg.has_class("hovered"):
                nums = [extract_number("user-message", x) for x in msg.classes]
                nums = [x for x in nums if x is not None]
                new_hist_size = nums[0] if nums else None
                start_dropping = True
                text = msg.markdown.lstrip("**User**: ")
                text_input = self.query_one("#text-input")
                text_input.text = text
                text_input.focus()
                text_input.move_cursor(text_input.document.end)

                new_hist = []
                n_user_messages = 0
                for chat_msg in self.chat.history:
                    if n_user_messages <= new_hist_size:
                        new_hist.append(chat_msg)
                    if chat_msg["role"] == "user":
                        n_user_messages += 1
                self.chat.history = new_hist[:-1]
            if start_dropping:
                msg.remove()

    async def reset_text(self)   -> None:
        await asyncio.sleep(1)
        copy_button = self.query_one(".copied")
        copy_button.update("[@click='app.copy()']copy[/]")
        copy_button.remove_class("copied")

    def action_quit(self) -> None:
        self.exit()

    def action_save(self) -> None:
        with open(self.save_file, "w") as f:
            f.write(json.dumps(self.chat.history) + "\n")

    def action_clear(self) -> None:
        chat_log = self.query_one("#chat-log-container")
        chat_log.remove_children()
        self.chat.clear_history()
        input_widget = self.query_one("#text-input")
        input_widget.text = ""
        input_widget.focus()

    def action_update_display(self) -> None:
        """Called when Ctrl+R is pressed."""
        input_widget = self.query_one("#text-input")
        input_text = escape_text(input_widget.text)
        if input_text:
            input_widget.text = ""
            self.query_one("#loading").display = True
            self.run_worker(self.update_display(input_text))
        input_widget.focus()

    async def update_display(self, text: str) -> None:
        """Update the display with the given text after a delay."""
        chat_log = self.query_one("#chat-log-container")

        # Render the user message
        message = Message(
            "**User**: " + text, 
            classes=f"user-message user-message-{self.n_user_messages}"
        )
        self.n_user_messages += 1
        chat_log.mount(message)
        message.anchor()

        # Add the next message block to the chat log
        message = Message("", classes="assistant-message")
        await chat_log.mount(message)
        message.anchor()

        # Chat response
        self.send_prompt(text, message)

        self.action_save()

    @work(thread=True)
    def send_prompt(
            self, 
            prompt: str, 
            message
    ):
        chat_log = message.app.query_one("#chat-log-container")
        message_container = message.query_one(".message")
        token_count_container = message.query_one(".token-counts")

        if self.chat.stream:
            for idx, chunk in enumerate(self.chat(prompt=prompt)):
                chunk = escape_text(chunk)
                if idx % 10 == 0:
                    self.call_from_thread(message_container.update, chunk)
                    self.call_from_thread(chat_log.scroll_end)
            self.call_from_thread(message_container.update, chunk)
            self.call_from_thread(chat_log.scroll_end)
            response_text = chunk
        else:
            response_text = escape_text(self.chat(prompt=prompt))
            self.call_from_thread(message_container.update, response_text)
        self.query_one("#loading").display = False
        self.call_from_thread(message.set_markdown, response_text)
        self.call_from_thread(token_count_container.update, self.chat.tokens.last)


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
        stream=stream
    )
    app = ChatGUI(title=model, chat=chat)
    app.run()


if __name__ == "__main__":
    typer.run(launch_gui)
