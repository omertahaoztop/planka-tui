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
    CSS_PATH = "tui.css"
    BINDINGS = [("q", "quit", "Quit")]

    def on_mount(self) -> None:
        self.push_screen(ProjectBoardTree())


if __name__ == "__main__":
    app = PlankaApp()
    app.run()
