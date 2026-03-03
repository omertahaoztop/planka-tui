from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll, Vertical
from textual.widgets import Header, Footer, Button, Label, Tree, Input, LoadingIndicator, Static
from textual.screen import ModalScreen, Screen
from textual import work
from textual.widget import Widget
from rich.text import Text

from client import PlankaClient


def _one_line(text: str, maxlen: int = 0) -> str:
    """Collapse multiline text to a single line (no hard truncation; Rich handles overflow)."""
    if not text:
        return "Untitled"
    line = text.replace("\r", "").split("\n")[0].strip()
    if not line:
        return "Untitled"
    # Only hard-truncate when an explicit maxlen is requested (e.g. notify messages)
    if maxlen and len(line) > maxlen:
        line = line[: maxlen - 1] + "…"
    return line


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────


class ProjectBoardTree(Screen):
    """Dashboard — pick a board."""

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="dashboard_container"):
            yield Static("planka · tui", classes="dashboard_logo")
            yield Tree("Boards", id="project_tree")
        yield Footer()

    def on_mount(self) -> None:
        self._load()

    @work(thread=True)
    def _load(self) -> None:
        try:
            planka = PlankaClient.get_instance()
            projects = planka.projects
            self.app.call_from_thread(self._populate, projects)
        except Exception as e:
            self.app.call_from_thread(
                self.notify, f"Connection error: {e}", severity="error"
            )

    def _populate(self, projects) -> None:
        tree = self.query_one("#project_tree", Tree)
        tree.root.expand()
        for project in projects:
            pnode = tree.root.add(project.name, expand=True)
            for board in project.boards:
                pnode.add_leaf(board.name, data=board)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        if not event.node.allow_expand and event.node.data:
            self.app.push_screen(BoardScreen(event.node.data))


# ─────────────────────────────────────────────────────────────────────────────
# Card widget — a focusable Label row
# ─────────────────────────────────────────────────────────────────────────────


class CardWidget(Widget):
    """Single-line focusable card row."""

    can_focus = True
    DEFAULT_CSS = "CardWidget { height: 1; min-height: 1; max-height: 1; }"

    def __init__(self, card, **kwargs):
        super().__init__(**kwargs)
        self.card = card

    def on_focus(self) -> None:
        self.refresh()

    def on_blur(self) -> None:
        self.refresh()

    def render(self) -> Text:
        name = _one_line(self.card.name)
        bullet = "▶ " if self.has_focus else "· "
        avail = max(4, (self.size.width or 38) - 4)
        t = Text(bullet + name, no_wrap=True, overflow="ellipsis")
        t.truncate(avail, overflow="ellipsis")
        return t

# ─────────────────────────────────────────────────────────────────────────────
# List column
# ─────────────────────────────────────────────────────────────────────────────


class ListColumn(VerticalScroll):
    """Vertical column for one Planka list."""

    can_focus = True

    BINDINGS = [
        ("down", "next_card", "↓"),
        ("up", "prev_card", "↑"),
    ]

    def __init__(self, planka_list, **kwargs):
        super().__init__(**kwargs)
        self.planka_list = planka_list

    def _cards(self) -> list[CardWidget]:
        return list(self.query(CardWidget))

    def action_next_card(self) -> None:
        self._move(1)

    def action_prev_card(self) -> None:
        self._move(-1)

    def _move(self, d: int) -> None:
        cards = self._cards()
        if not cards:
            return
        focused = self.screen.focused
        if focused == self:
            cards[0].focus()
            return
        if focused in cards:
            i = cards.index(focused) + d
            if 0 <= i < len(cards):
                cards[i].focus()

    def on_focus(self) -> None:
        cards = self._cards()
        if cards:
            cards[0].focus()

    def compose(self) -> ComposeResult:
        cards = list(self.planka_list.cards)
        name = self.planka_list.name or "—"
        yield Label(f"{name}  [{len(cards)}]", classes="list_header")
        for card in cards:
            yield CardWidget(card, classes="card")

    def refresh_header(self) -> None:
        count = len(self._cards())
        self.query_one(".list_header", Label).update(
            f"{self.planka_list.name}  [{count}]"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Modals
# ─────────────────────────────────────────────────────────────────────────────


class InputModal(ModalScreen[str | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, prompt: str):
        super().__init__()
        self.prompt_text = prompt

    def compose(self) -> ComposeResult:
        with Container(classes="modal_box"):
            yield Label(self.prompt_text, classes="modal_title")
            yield Input(id="modal_input", classes="modal_input")
            with Horizontal(classes="modal_row"):
                yield Button("OK", variant="primary", id="ok")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, e: Button.Pressed) -> None:
        if e.button.id == "ok":
            self.dismiss(self.query_one(Input).value or None)
        else:
            self.dismiss(None)

    def on_input_submitted(self, e: Input.Submitted) -> None:
        self.dismiss(e.value or None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmModal(ModalScreen[bool]):
    BINDINGS = [("escape", "no", "No"), ("y", "yes", "Yes")]

    def __init__(self, prompt: str):
        super().__init__()
        self.prompt_text = prompt

    def compose(self) -> ComposeResult:
        with Container(classes="modal_box"):
            yield Label(self.prompt_text, classes="modal_title")
            with Horizontal(classes="modal_row"):
                yield Button("Yes  [y]", variant="error", id="yes")
                yield Button("No [esc]", id="no")

    def on_button_pressed(self, e: Button.Pressed) -> None:
        self.dismiss(e.button.id == "yes")

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)


class DetailModal(ModalScreen):
    BINDINGS = [("escape", "close", "Close"), ("q", "close", "Close")]

    def __init__(self, title: str, body: str):
        super().__init__()
        self._title = title
        self._body = body

    def compose(self) -> ComposeResult:
        with Container(classes="modal_box detail_box"):
            yield Label(self._title, classes="modal_title")
            yield Label(self._body or "No description.", classes="modal_body")
            yield Button("Close  [esc]", variant="primary", id="close")

    def on_button_pressed(self, _: Button.Pressed) -> None:
        self.dismiss()

    def action_close(self) -> None:
        self.dismiss()


# ─────────────────────────────────────────────────────────────────────────────
# Board screen
# ─────────────────────────────────────────────────────────────────────────────


class BoardScreen(Screen):
    """Kanban board."""

    BINDINGS = [
        ("escape", "app.pop_screen", "← Back"),
        ("a", "add_card", "+ Card"),
        ("d", "delete_card", "Delete"),
        ("D", "clear_list", "Clear List"),
        ("c", "mark_done", "✓ Done"),
        ("enter", "view_details", "Details"),
        ("r", "reload", "Reload"),
    ]

    def __init__(self, board, **kwargs):
        super().__init__(**kwargs)
        self._stub = board
        self._board = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield LoadingIndicator(id="loading")
        yield Horizontal(id="board")
        yield Footer()

    def on_mount(self) -> None:
        self._fetch()

    @work(thread=True)
    def _fetch(self) -> None:
        try:
            board = PlankaClient.get_instance().load_board(self._stub)
            self.app.call_from_thread(self._show_board, board)
        except Exception as e:
            self.app.call_from_thread(
                self.notify, f"Failed to load board: {e}", severity="error"
            )

    def _show_board(self, board) -> None:
        self._board = board
        self.query_one("#loading").display = False
        container = self.query_one("#board", Horizontal)
        container.remove_children()
        for lst in board.lists:
            if lst.name:
                container.mount(ListColumn(lst, classes="list_col"))
        self.sub_title = board.name

    def action_reload(self) -> None:
        self.query_one("#loading").display = True
        self.query_one("#board", Horizontal).remove_children()
        self._fetch()

    # ── navigation ──────────────────────────────────────────────────────────

    def _shift_col(self, d: int) -> None:
        cols = list(self.query(ListColumn))
        if not cols:
            return
        cur = self._focused_col()
        idx = (cols.index(cur) + d) % len(cols) if cur in cols else 0
        cols[idx].focus()

    def on_key(self, e) -> None:
        if e.key == "tab":
            self._shift_col(1)
            e.stop()
        elif e.key == "shift+tab":
            self._shift_col(-1)
            e.stop()
        elif e.key == "right":
            self._shift_col(1)
            e.stop()
        elif e.key == "left":
            self._shift_col(-1)
            e.stop()

    def _focused_card(self) -> CardWidget | None:
        f = self.app.focused
        return f if isinstance(f, CardWidget) else None

    def _focused_col(self) -> ListColumn | None:
        f = self.app.focused
        if isinstance(f, CardWidget) and isinstance(f.parent, ListColumn):
            return f.parent
        if isinstance(f, ListColumn):
            return f
        return None

    # ── actions ─────────────────────────────────────────────────────────────

    def action_add_card(self) -> None:
        col = self._focused_col()
        if col is None:
            try:
                col = self.query_one(ListColumn)
            except Exception:
                self.notify("No list found.", severity="warning")
                return

        def _done(name: str | None) -> None:
            if not name:
                return
            try:
                card = col.planka_list.create_card(name=name)
                col.mount(CardWidget(card, classes="card"))
                col.refresh_header()
                self.notify(f"Added: {_one_line(name, 30)}")
            except Exception as ex:
                self.notify(f"Error: {ex}", severity="error")

        self.app.push_screen(InputModal("New card name:"), _done)

    def action_delete_card(self) -> None:
        cw = self._focused_card()
        if cw is None:
            self.notify("No card selected.", severity="warning")
            return

        def _done(ok: bool) -> None:
            if not ok:
                return
            try:
                col = cw.parent
                cw.card.delete()
                cw.remove()
                if isinstance(col, ListColumn):
                    col.refresh_header()
                self.notify("Deleted.")
            except Exception as ex:
                self.notify(f"Error: {ex}", severity="error")

        self.app.push_screen(
            ConfirmModal(f"Delete '{_one_line(cw.card.name, 40)}'?"), _done
        )

    def action_mark_done(self) -> None:
        cw = self._focused_card()
        if cw is None:
            self.notify("No card selected.", severity="warning")
            return

        target_col: ListColumn | None = None
        for col in self.query(ListColumn):
            if col.planka_list._data.get("type") == "closed":
                target_col = col
                break

        if target_col is None:
            self.notify("'Done' list not found.", severity="warning")
            return

        if target_col.planka_list._data["id"] == cw.card.listId:
            self.notify("Card is already in Done.")
            return

        try:
            src = cw.parent
            cw.card.move(target_col.planka_list)
            cw.remove()
            if isinstance(src, ListColumn):
                src.refresh_header()
            target_col.mount(CardWidget(cw.card, classes="card"))
            target_col.refresh_header()
            self.notify("Marked as done.")
        except Exception as ex:
            self.notify(f"Error: {ex}", severity="error")

    def action_view_details(self) -> None:
        cw = self._focused_card()
        if cw:
            self.app.push_screen(DetailModal(cw.card.name, cw.card.description))

    def action_clear_list(self) -> None:
        col = self._focused_col()
        if col is None:
            self.notify("No list selected.", severity="warning")
            return
        cards = col._cards()
        if not cards:
            self.notify("List is already empty.", severity="warning")
            return

        def _done(ok: bool) -> None:
            if not ok:
                return
            deleted, failed = 0, 0
            for cw in cards:
                try:
                    cw.card.delete()
                    cw.remove()
                    deleted += 1
                except Exception:
                    failed += 1
            col.refresh_header()
            sev = "warning" if failed else "information"
            self.notify(
                f"{deleted} card(s) deleted."
                + (f" {failed} failed." if failed else ""),
                severity=sev,
            )

        name = col.planka_list.name or "this list"
        self.app.push_screen(
            ConfirmModal(f"Delete all {len(cards)} cards in '{name}'?"), _done
        )
