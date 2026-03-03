import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from plankapy.v2 import Planka

CONFIG_SEARCH_PATHS = [
    Path("/etc/default/planka-tui"),
    Path.home() / ".config" / "planka-tui" / "config",
    Path.cwd() / ".env",
]


class PlankaClient:
    _instance: Optional[Planka] = None

    @classmethod
    def _load_config(cls) -> Path | None:
        for config_path in CONFIG_SEARCH_PATHS:
            if config_path.exists():
                load_dotenv(config_path)
                return config_path
        load_dotenv()
        return None

    @classmethod
    def get_instance(cls) -> Planka:
        if cls._instance is None:
            cls._load_config()

            url = os.getenv("PLANKA_API_URL")
            username = os.getenv("PLANKA_USERNAME")
            password = os.getenv("PLANKA_PASSWORD")

            if not all([url, username, password]):
                search_paths = "\n  - ".join(str(p) for p in CONFIG_SEARCH_PATHS)
                raise ValueError(
                    f"Missing Planka credentials. "
                    f"Set PLANKA_API_URL, PLANKA_USERNAME, PLANKA_PASSWORD in:\n  - {search_paths}\n"
                    f"Or export them as environment variables."
                )

            # v2 expects base URL without /api suffix
            base_url = url.rstrip("/")
            if base_url.endswith("/api"):
                base_url = base_url[:-4]

            planka = Planka(base_url)
            planka.login(username=username, password=password)
            cls._instance = planka

        return cls._instance


if __name__ == "__main__":
    try:
        client = PlankaClient.get_instance()
        print(f"Successfully connected to Planka as {client.me.name}")
    except Exception as e:
        print(f"Connection failed: {e}")
