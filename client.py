import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from plankapy import (
    Planka,
    PasswordAuth,
    Project,
    Board,
    List,
    Card,
    Label,
    Task,
    User,
    Notification,
    Action,
    Archive,
    Attachment,
    CardLabel,
    CardMembership,
    CardSubscription,
    IdentityUserProvider,
    ProjectManager,
)

CONFIG_SEARCH_PATHS = [
    Path("/etc/default/planka-tui"),
    Path.home() / ".config" / "planka-tui" / "config",
    Path.cwd() / ".env",
]

# List of models to patch
MODELS_TO_PATCH = [
    Project,
    Board,
    List,
    Card,
    Label,
    Task,
    User,
    Notification,
    Action,
    Archive,
    Attachment,
    CardLabel,
    CardMembership,
    CardSubscription,
    IdentityUserProvider,
    ProjectManager,
]


def make_safe_init(cls):
    """
    Creates a safe __init__ method for a dataclass-based model that ignores
    unexpected keyword arguments.
    """
    # Capture the original __init__ (which comes from the dataclass)
    original_init = cls.__init__

    def safe_init(self, *args, **kwargs):
        # Check if the instance has dataclass fields
        if hasattr(self, "__dataclass_fields__"):
            valid_fields = self.__dataclass_fields__.keys()
            filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_fields}
        else:
            # If not a dataclass (unlikely provided we act on plankapy models), pass through
            filtered_kwargs = kwargs

        original_init(self, *args, **filtered_kwargs)

    return safe_init


# Apply the patch to all models
for model_cls in MODELS_TO_PATCH:
    if hasattr(model_cls, "__init__"):
        model_cls.__init__ = make_safe_init(model_cls)


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
            loaded_from = cls._load_config()

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

            auth = PasswordAuth(username, password)
            cls._instance = Planka(url, auth)

        return cls._instance


if __name__ == "__main__":
    try:
        updated_client = PlankaClient.get_instance()
        print(f"Successfully connected to Planka at {updated_client._url}")
    except Exception as e:
        print(f"Connection failed: {e}")
