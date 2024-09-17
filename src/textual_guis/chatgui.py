import os
import asyncio
import subprocess

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll, Container, HorizontalScroll, ScrollableContainer
from textual.geometry import Region
from textual.widgets import (
    TextArea, Static, LoadingIndicator, Header, Footer, Markdown
)
from textual.binding import Binding

from litellm import completion
import typer

from typer import Option
from typing_extensions import Annotated

from textual_guis.llmchat import LlmChat


class TextInput(TextArea):
    """A text input widget"""
    def __init__(
            self, 
            show_line_numbers: bool = False,
            language: str = "markdown", 
            id: str = "text-input", 
            **kwargs
    ):
        super().__init__(
            id=id, 
            show_line_numbers=show_line_numbers,
            language=language,
            **kwargs
        )

    def on_mount(self) -> None:
        self.focus()

    def _on_key(self, event) -> None:
        if event.key in("ctrl+r", "registered_sign") and self.text:
            event.prevent_default()
            self.app.action_update_display()


class ButtonContainer(HorizontalScroll):
    def __init__(self, **kwargs):
        super().__init__(id="buttons", **kwargs)

    def compose(self) -> ComposeResult:
        yield Static("[@click='app.update_display()']Submit[/]", classes="submit")
        yield Static("[@click='app.clear()']Clear[/]", classes="clear")


class ChatContainer(Container):
    """A container that allows 2 vertically stacked items to be resized"""
    def __init__(self, id: str = "chat-container", **kwargs):
        super().__init__(id=id, **kwargs)
        self.separator = None

    def compose(self) -> ComposeResult:
        with Container():
            yield ScrollableContainer(id="chat-log-container")
            yield LoadingIndicator(id="loading")
        yield Separator()
        yield TextInput()
        yield ButtonContainer()

    def action_clear(self) -> None:
        raise Exception

    def on_mount(self) -> None:
        self.separator = self.query_one("#separator")
        self.query_one("#loading").display = False

    def on_mouse_down(self, event) -> None:
        """Initialize panel resizing"""
        if self.separator.has_class("hovered"):
            self.separator.add_class("moving")
            self.capture_mouse()

    def on_mouse_up(self, event) -> None:
        """End panel resizing"""
        self.separator.remove_class("moving")
        self.release_mouse()

    def on_mouse_move(self, event) -> None:
        """Resize panels"""
        if self.separator.has_class("moving"):
            try:
                top_height = max(1, min(event.y, self.size.height - 6))
                bottom_height = self.size.height - top_height - 1
                self.styles.grid_rows = f"{top_height + 2}fr 1 {bottom_height}fr 2"
                self.refresh()
            except NoMatches:
                pass


class Separator(Static):
    """A widget for separating and resizing panels in a container"""
    def __init__(
            self,
            id: str = "separator",
            **kwargs
        ):
        super().__init__(id=id, **kwargs)

    def on_enter(self) -> None:
        self.add_class("hovered")

    def on_leave(self) -> None:
        self.remove_class("hovered")


class QuietMarkdown(Markdown):
    def on_leave(self, event) -> None:
        event.stop()


class Message(Container):
    """A message"""
    def __init__(self, markdown: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.markdown = markdown
        self.add_class("message-container")

    def compose(self) -> ComposeResult:
        yield QuietMarkdown(self.markdown, classes="message")
        copy_button = Static("[@click='app.copy()']copy[/]", classes="copy")
        yield copy_button

    def on_enter(self, event) -> None:
        for x in self.app.query(".message-container"):
            x.remove_class("hovered")
        self.add_class("hovered")

    def on_mouse_move(self, event) -> None:
        self.add_class("hovered")

    def on_leave(self, event) -> None:
        self.remove_class("hovered")


class ChatGUI(App):
    """Simple LLM chat GUI"""

    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+r", "", "Submit")
    ]

    def __init__(self, chat: LlmChat, title: str = "LLM Chat"):
        super().__init__()
        self.chat = chat
        self.title = title

    def compose(self) -> ComposeResult:
        yield Header()
        yield ChatContainer()
        yield Footer(show_command_palette=False)

    def action_copy(self) -> None:
        copy_button = self.query_one(".message-container.hovered > .copy")
        copy_button.update("copied")
        copy_button.add_class("copied")
        hovered = self.query_one(".message-container.hovered")
        msg = hovered.markdown
        msg = msg.lstrip("**User**: ")
        process = subprocess.Popen(
            'pbcopy',
            env={'LANG': 'en_US.UTF-8'},
            stdin=subprocess.PIPE
        )
        process.communicate(msg.encode('utf-8'))
        asyncio.create_task(self.reset_text())

    async def reset_text(self) -> None:
        await asyncio.sleep(1)
        copy_button = self.query_one(".copied")
        copy_button.update("[@click='app.copy()']copy[/]")
        copy_button.remove_class("copied")

    def action_quit(self) -> None:
        self.exit()

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
        input_text = input_widget.text
        if input_text:
            input_widget.text = ""
            self.query_one("#loading").display = True
            self.run_worker(self.update_display(input_text))
        input_widget.focus()

    async def update_display(self, text: str) -> None:
        """Update the display with the given text after a delay."""
        chat_log = self.query_one("#chat-log-container")

        message = Message("**User**: " + text, classes="user-message")
        chat_log.mount(message)
        message.scroll_visible()

        chat = self.chat
        response = await asyncio.to_thread(chat, prompt=text)
        message = Message(response.choices[0].message.content, classes="assistant-message")
        chat_log.mount(message)
        self.query_one("#loading").display = False
        message.scroll_visible()


def launch_gui(
    model: Annotated[str, Option(help="A litellm model identifier")] = "gpt-4o", 
    max_tokens: Annotated[int, Option(help="The maximum number of tokens to generate")] = 4096,
    top_p: Annotated[float, Option(help="The cumulative probability for top-p sampling")] = 1.0,
    temperature: Annotated[float, Option(help="The sampling temperature to use for generation")] = 0.0
):
    """Launches a chat gui with a model backend."""
    chat = LlmChat(model=model, max_tokens=max_tokens, top_p=top_p, temperature=temperature)
    app = ChatGUI(title=model, chat=chat)
    app.run()


if __name__ == "__main__":
    typer.run(launch_gui)
