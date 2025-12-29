import os
import dataclasses
from typing import Optional
from dotenv import load_dotenv
from plankapy import (
    Planka, PasswordAuth, 
    Project, Board, List, Card, Label, Task, User, Notification, 
    Action, Archive, Attachment, CardLabel, CardMembership, 
    CardSubscription, IdentityUserProvider, ProjectManager
)

# List of models to patch
MODELS_TO_PATCH = [
    Project, Board, List, Card, Label, Task, User, Notification, 
    Action, Archive, Attachment, CardLabel, CardMembership, 
    CardSubscription, IdentityUserProvider, ProjectManager
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
        if hasattr(self, '__dataclass_fields__'):
            valid_fields = self.__dataclass_fields__.keys()
            filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_fields}
        else:
            # If not a dataclass (unlikely provided we act on plankapy models), pass through
            filtered_kwargs = kwargs
            
        original_init(self, *args, **filtered_kwargs)
    
    return safe_init

# Apply the patch to all models
for model_cls in MODELS_TO_PATCH:
    if hasattr(model_cls, '__init__'):
        model_cls.__init__ = make_safe_init(model_cls)

class PlankaClient:
    _instance: Optional[Planka] = None

    @classmethod
    def get_instance(cls) -> Planka:
        if cls._instance is None:
            load_dotenv()
            url = os.getenv("PLANKA_API_URL")
            username = os.getenv("PLANKA_USERNAME")
            password = os.getenv("PLANKA_PASSWORD")

            if not all([url, username, password]):
                raise ValueError("Missing Planka credentials in .env file.")

            auth = PasswordAuth(username, password)
            cls._instance = Planka(url, auth)
        
        return cls._instance

if __name__ == "__main__":
    try:
        updated_client = PlankaClient.get_instance()
        print(f"Successfully connected to Planka at {updated_client._url}")
    except Exception as e:
        print(f"Connection failed: {e}")
