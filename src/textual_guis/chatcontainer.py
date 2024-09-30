from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll, HorizontalScroll
from textual.widgets import TextArea, Static, Markdown, LoadingIndicator
from textual.reactive import reactive


class ChatContainer(Container):
    """A container that allows 2 vertically stacked items to be resized"""
    def __init__(self, id: str = "chat-container", **kwargs):
        super().__init__(id=id, **kwargs)
        self.separator = None

    def compose(self) -> ComposeResult:
        with Container():
            yield VerticalScroll(id="chat-log-container")
            yield LoadingIndicator(id="loading")
        yield Separator(id="separator")
        yield TextInput(id="text-input", show_line_numbers=True, language="markdown")
        with HorizontalScroll(id="buttons"):
            yield Static("[@click='app.update_display()']Submit[/]", classes="submit")
            yield Static("[@click='app.clear()']Clear[/]", classes="clear")

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


class TextInput(TextArea):
    """A text input widget"""
    def on_mount(self) -> None:
        self.focus()

    def _on_key(self, event) -> None:
        if event.key in("ctrl+r", "registered_sign") and self.text:
            event.prevent_default()
            self.app.action_update_display()


class Separator(Static):
    """A widget for separating and resizing panels in a container"""
    def on_enter(self) -> None:
        self.add_class("hovered")

    def on_leave(self) -> None:
        self.remove_class("hovered")


class QuietMarkdown(Markdown):
    def on_leave(self, event) -> None:
        event.stop()


class Message(Container):
    token_counts: reactive[str | None] = reactive("")

    """A message"""
    def __init__(self, markdown: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.markdown = markdown
        self.add_class("message-container")

    def set_markdown(self, markdown):
        self.markdown = markdown

    def compose(self) -> ComposeResult:
        yield QuietMarkdown(self.markdown, classes="message")
        with HorizontalScroll(classes="message-buttons"):
            yield Static(self.token_counts, classes="token-counts")
            yield Static("[@click='app.goto()']goto[/]", classes="goto message-button")
            yield Static("[@click='app.copy()']copy[/]", classes="copy message-button")

    def on_enter(self, event) -> None:
        for x in self.app.query(".message-container"):
            x.remove_class("hovered")
        self.add_class("hovered")

    def on_mouse_move(self, event) -> None:
        self.add_class("hovered")

    def on_leave(self, event) -> None:
        self.remove_class("hovered")