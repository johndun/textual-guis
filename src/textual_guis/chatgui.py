import os
import asyncio

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll, Container
from textual.widgets import (
    TextArea, Static, LoadingIndicator, Header, Footer, Markdown
)
from textual.binding import Binding

from litellm import completion


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


class ChatContainer(Container):
    """A container that allows 2 vertically stacked items to be resized"""
    def __init__(self, id: str = "chat-container", **kwargs):
        super().__init__(id=id, **kwargs)
        self.separator = None

    def compose(self) -> ComposeResult:
        with Container():
            yield VerticalScroll(id="chat-log-container")
            yield LoadingIndicator(id="loading")
        yield Separator()
        yield TextInput()

    def on_mount(self) -> None:
        self.separator = self.query_one("#separator")

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
                top_height = max(1, min(event.y, self.size.height - 4))
                bottom_height = self.size.height - top_height - 1
                self.styles.grid_rows = f"{top_height + 2}fr 1 {bottom_height}fr"
                self.refresh()
            except NoMatches:
                pass


class ChatGUI(App):
    """Simple LLM chat GUI"""

    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+r", "", "Submit")
    ]

    def __init__(self, title: str = "LLM Chat"):
        super().__init__()
        self.title = title

    def compose(self) -> ComposeResult:
        yield Header()
        yield ChatContainer()
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self.query_one("#loading").display = False

    def action_quit(self) -> None:
        self.exit()

    def action_update_display(self) -> None:
        """Called when Ctrl+R is pressed."""
        input_text = self.query_one("#text-input").text
        self.query_one("#loading").display = True
        self.run_worker(self.update_display(input_text))

    async def update_display(self, text: str) -> None:
        """Update the display with the given text after a delay."""
        chat_log = self.query_one("#chat-log-container")

        message = Markdown("**User**: " + text)
        message.add_class("message")
        message.add_class("user-message")
        chat_log.mount(message)
        message.scroll_visible()

        response = await asyncio.to_thread(completion,
            model="gpt-4o",
            messages=[{"content": text, "role": "user"}]
        )

        self.query_one("#loading").display = False

        message = Markdown(response.choices[0].message.content)
        message.add_class("message")
        chat_log.mount(message)
        message.scroll_visible()


if __name__ == "__main__":
    app = ChatGUI()
    app.run()