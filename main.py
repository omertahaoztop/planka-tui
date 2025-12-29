import os
import ssl
import certifi

# Fix SSL certificate verification for PyInstaller bundles
_cert_file = certifi.where()
os.environ.setdefault("SSL_CERT_FILE", _cert_file)
os.environ.setdefault("SSL_CERT_DIR", os.path.dirname(_cert_file))


# Override default SSL context for urllib (used by plankapy)
def _create_ssl_context():
    ctx = ssl.create_default_context()
    ctx.load_verify_locations(_cert_file)
    return ctx


ssl._create_default_https_context = _create_ssl_context

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
