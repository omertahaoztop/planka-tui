import os
import certifi

os.environ.setdefault("SSL_CERT_FILE", certifi.where())

from textual.app import App
from tui import ProjectBoardTree


class PlankaApp(App):
    CSS_PATH = "tui.css"
    BINDINGS = [("q", "quit", "Quit")]

    def on_mount(self) -> None:
        self.push_screen(ProjectBoardTree())


if __name__ == "__main__":
    app = PlankaApp()
    app.run()
