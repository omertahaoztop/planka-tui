"""Planka API client — direct HTTP, no plankapy dependency."""

import os
import json
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from dotenv import load_dotenv

CONFIG_SEARCH_PATHS = [
    Path("/etc/default/planka-tui"),
    Path.home() / ".config" / "planka-tui" / "config",
    Path.cwd() / ".env",
]

# ---------------------------------------------------------------------------
# Lightweight model objects (plain dicts wrapped in a class for attr access)
# ---------------------------------------------------------------------------


class _Obj:
    """Wrap a raw API dict so attributes are accessible as obj.field."""

    def __init__(self, data: dict, routes: "Routes"):
        self._data = data
        self._routes = routes

    def __getattr__(self, name):
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name)

    def __repr__(self):
        return f"{self.__class__.__name__}({self._data.get('name', self._data.get('id', '?'))})"


class Card(_Obj):
    @property
    def name(self) -> str:
        return self._data.get("name") or "Untitled"

    @property
    def description(self) -> str:
        return self._data.get("description") or ""

    @property
    def listId(self) -> str:
        return self._data["listId"]

    def delete(self):
        self._routes.delete(f"/cards/{self._data['id']}")

    def move(self, target_list: "List"):
        self._routes.patch(
            f"/cards/{self._data['id']}",
            {
                "listId": target_list._data["id"],
                "boardId": target_list._data["boardId"],
                "position": 65535,
            },
        )
        self._data["listId"] = target_list._data["id"]


class List(_Obj):
    def __init__(self, data: dict, cards: list, routes: "Routes"):
        super().__init__(data, routes)
        self._cards = cards

    @property
    def name(self) -> Optional[str]:
        return self._data.get("name")

    @property
    def cards(self) -> list:
        return self._cards

    def create_card(self, name: str) -> Card:
        result = self._routes.post(
            f"/lists/{self._data['id']}/cards",
            {
                "name": name,
                "position": 65535,
                "type": "project",
            },
        )
        return Card(result["item"], self._routes)


class Board(_Obj):
    def __init__(self, data: dict, lists: list, routes: "Routes"):
        super().__init__(data, routes)
        self._lists = lists

    @property
    def name(self) -> str:
        return self._data.get("name", "Untitled")

    @property
    def lists(self) -> list:
        return self._lists


class Project(_Obj):
    def __init__(self, data: dict, boards: list, routes: "Routes"):
        super().__init__(data, routes)
        self._boards = boards

    @property
    def name(self) -> str:
        return self._data.get("name", "Untitled")

    @property
    def boards(self) -> list:
        return self._boards


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------


class Routes:
    def __init__(self, base_url: str, token: str):
        self._base = base_url.rstrip("/") + "/api"
        self._token = token

    def _request(self, method: str, path: str, data: dict = None) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._token}",
        }
        body = json.dumps(data).encode() if data is not None else None
        req = Request(self._base + path, data=body, headers=headers, method=method)
        try:
            with urlopen(req) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except HTTPError as e:
            msg = e.read().decode(errors="replace")
            raise RuntimeError(f"Planka API {method} {path} → {e.code}: {msg}") from e

    def get(self, path: str) -> dict:
        return self._request("GET", path)

    def post(self, path: str, data: dict) -> dict:
        return self._request("POST", path, data)

    def patch(self, path: str, data: dict) -> dict:
        return self._request("PATCH", path, data)

    def delete(self, path: str) -> dict:
        return self._request("DELETE", path)


# ---------------------------------------------------------------------------
# High-level Planka client
# ---------------------------------------------------------------------------


class PlankaAPI:
    """Authenticated Planka client."""

    def __init__(self, base_url: str, username: str, password: str):
        clean_url = base_url.rstrip("/")
        if clean_url.endswith("/api"):
            clean_url = clean_url[:-4]

        # Login → get token
        login_url = clean_url + "/api/access-tokens"
        req = Request(
            login_url,
            data=json.dumps(
                {"emailOrUsername": username, "password": password}
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req) as r:
                resp = json.loads(r.read())
        except HTTPError as e:
            raise RuntimeError(f"Login failed ({e.code}): {e.read().decode()}") from e

        token = resp.get("item")
        if not token:
            raise RuntimeError(f"Login failed: no token in response. Got: {resp}")

        self._routes = Routes(clean_url, token)
        self._me_name: Optional[str] = None

    @property
    def me_name(self) -> str:
        if self._me_name is None:
            data = self._routes.get("/users/me")
            self._me_name = data["item"]["name"]
        return self._me_name

    @property
    def projects(self) -> list:
        """Return list of Project objects with board stubs (no eager board detail fetch)."""
        resp = self._routes.get("/projects")
        raw_boards_by_project: dict[str, list] = {}

        for b in resp.get("included", {}).get("boards", []):
            pid = b["projectId"]
            raw_boards_by_project.setdefault(pid, []).append(b)

        result = []
        for p in resp.get("items", []):
            raw_boards = raw_boards_by_project.get(p["id"], [])
            # Board stubs: name+id only, lists/cards loaded on demand
            board_stubs = [Board(b, None, self._routes) for b in raw_boards]
            result.append(Project(p, board_stubs, self._routes))
        return result

    def load_board(self, board: "Board") -> "Board":
        """Fetch full board detail (lists + cards) and return a new loaded Board."""
        return self._load_board(board._data)

    def _load_board(self, board_data: dict) -> Board:
        """Fetch full board (lists + cards) and build Board object."""
        resp = self._routes.get(f"/boards/{board_data['id']}")
        included = resp.get("included", {})
        raw_lists = included.get("lists", [])
        raw_cards = included.get("cards", [])

        # Group cards by listId
        cards_by_list: dict[str, list] = {}
        for c in raw_cards:
            if not c.get("isClosed"):
                cards_by_list.setdefault(c["listId"], []).append(c)

        lists = []
        for lst in raw_lists:
            if lst.get("type") not in ("archive", "trash") and lst.get("name"):
                raw_cards_for_list = cards_by_list.get(lst["id"], [])
                card_objs = [Card(c, self._routes) for c in raw_cards_for_list]
                lists.append(List(lst, card_objs, self._routes))

        return Board(board_data, lists, self._routes)


# ---------------------------------------------------------------------------
# Singleton accessor (same interface the old PlankaClient provided)
# ---------------------------------------------------------------------------


class PlankaClient:
    _instance: Optional[PlankaAPI] = None

    @classmethod
    def _load_config(cls) -> None:
        for config_path in CONFIG_SEARCH_PATHS:
            if config_path.exists():
                load_dotenv(config_path)
                return
        load_dotenv()

    @classmethod
    def get_instance(cls) -> PlankaAPI:
        if cls._instance is None:
            cls._load_config()
            url = os.getenv("PLANKA_API_URL")
            username = os.getenv("PLANKA_USERNAME")
            password = os.getenv("PLANKA_PASSWORD")

            if not all([url, username, password]):
                search_paths = "\n  - ".join(str(p) for p in CONFIG_SEARCH_PATHS)
                raise ValueError(
                    "Missing Planka credentials. "
                    f"Set PLANKA_API_URL, PLANKA_USERNAME, PLANKA_PASSWORD in:\n  - {search_paths}\n"
                    "Or export them as environment variables."
                )

            cls._instance = PlankaAPI(url, username, password)
        return cls._instance


if __name__ == "__main__":
    try:
        client = PlankaClient.get_instance()
        print(f"Connected as: {client.me_name}")
        for project in client.projects:
            print(f"  Project: {project.name}")
            for board in project.boards:
                print(f"    Board: {board.name} ({len(board.lists)} lists)")
    except Exception as e:
        print(f"Connection failed: {e}")
