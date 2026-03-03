import os
import ssl

# SSL certificate paths to try (in order)
_CERT_PATHS = [
    "/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu
    "/etc/pki/tls/certs/ca-bundle.crt",  # RHEL/CentOS
    "/etc/ssl/ca-bundle.pem",  # OpenSUSE
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",  # Fedora
]


def _find_cert_file():
    """Find working SSL certificate file."""
    # Try certifi first (works in most PyInstaller bundles)
    try:
        import certifi

        cert_path = certifi.where()
        if os.path.exists(cert_path):
            # Test if it actually works
            ctx = ssl.create_default_context()
            ctx.load_verify_locations(cert_path)
            return cert_path
    except Exception:
        pass

    # Fallback to system certificates
    for path in _CERT_PATHS:
        if os.path.exists(path):
            return path

    return None


_cert_file = _find_cert_file()

if _cert_file:
    os.environ.setdefault("SSL_CERT_FILE", _cert_file)
    os.environ.setdefault("SSL_CERT_DIR", os.path.dirname(_cert_file))

    def _create_ssl_context():
        ctx = ssl.create_default_context()
        ctx.load_verify_locations(_cert_file)
        return ctx

    ssl._create_default_https_context = _create_ssl_context

from textual.app import App
from tui import ProjectBoardTree


class PlankaApp(App):
    # Inline CSS — PyInstaller breaks CSS_PATH resolution in onefile mode
    CSS = """
    Screen {
        background: $surface;
    }

    /* ── Dashboard ── */
    #dashboard_container {
        width: 100%;
        height: 100%;
        padding: 1 2;
        background: $surface;
    }

    .title {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: $text-muted;
        padding: 1 0 0 0;
    }

    #project_tree {
        margin: 1 2;
    }

    /* ── Board ── */
    #board_container {
        height: 1fr;
        width: auto;
        min-width: 100%;
        overflow-x: auto;
        background: $surface;
    }

    .list_column {
        width: 44;
        min-width: 44;
        max-width: 44;
        height: 100%;
        padding: 0 1;
        border-right: tall $warning 40%;
        background: $surface;
        scrollbar-size: 1 1;
    }

    .list_column:focus-within {
        border-right: tall $warning;
    }

    .list_title {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: $warning;
        background: $surface;
        height: 1;
        max-height: 1;
        overflow: hidden;
    }

    /* ── Cards ── */
    .card {
        height: 1;
        max-height: 1;
        padding: 0 1;
        background: $surface;
    }

    .card:focus {
        background: $warning 15%;
        color: $warning;
        text-style: bold;
    }

    .card_title {
        text-align: left;
        height: 1;
        max-height: 1;
        overflow: hidden;
        width: 100%;
    }

    /* ── Modals ── */
    ModalScreen {
        align: center middle;
        background: $surface 60%;
    }

    .modal_dialog {
        width: 60;
        max-width: 80%;
        height: auto;
        max-height: 80%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }

    .details_modal {
        width: 72;
    }

    .modal_header {
        text-style: bold;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
        color: $text;
    }

    .modal_body {
        width: 100%;
        height: auto;
        max-height: 20;
        overflow-y: auto;
        margin-bottom: 1;
        color: $text-muted;
    }

    .modal_buttons {
        width: 100%;
        height: auto;
        align: center middle;
        margin-top: 1;
    }

    .modal_buttons Button {
        margin: 0 1;
        min-width: 10;
    }

    Input {
        margin: 1 0;
    }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def on_mount(self) -> None:
        self.push_screen(ProjectBoardTree())


if __name__ == "__main__":
    app = PlankaApp()
    app.run()
