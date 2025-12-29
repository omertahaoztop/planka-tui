from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll, Grid
from textual.widgets import Header, Footer, Button, Label, Tree, Static, ListItem, ListView, Input
from textual.screen import ModalScreen, Screen
from textual.message import Message
from textual.reactive import reactive
from textual.worker import Worker, get_current_worker
from textual.binding import Binding
from textual import work
from client import PlankaClient

class ProjectBoardTree(Screen):
    """Screen to select a board from projects."""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Label("Select a Board", classes="title"),
            Tree("Projects", id="project_tree"),
            id="dashboard_container"
        )
        yield Footer()

    def on_mount(self) -> None:
        """Load projects and boards into the tree."""
        tree = self.query_one("#project_tree", Tree)
        tree.root.expand()
        
        try:
            planka = PlankaClient.get_instance()
            me = planka.me
            projects = me.projects
            
            for project in projects:
                project_node = tree.root.add(project.name, expand=True)
                for board in project.boards:
                    project_node.add_leaf(board.name, data=board)
                    
        except Exception as e:
            self.notify(f"Error loading boards: {e}", severity="error")

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle board selection."""
        if not event.node.allow_expand and event.node.data:
            board = event.node.data
            self.app.push_screen(BoardScreen(board))

class CardWidget(Static):
    """A widget representing a card in the Kanban board."""
    can_focus = True

    def __init__(self, card, **kwargs):
        super().__init__(**kwargs)
        self.card = card

    def compose(self) -> ComposeResult:
        # Handle case where card.name might be None
        name = self.card.name if self.card.name else "Untitled Card"
        yield Label(name, classes="card_title")

class ListColumn(VerticalScroll):
    """A column representing a list in the Kanban board."""
    can_focus = True # Allow focusing the list itself (useful for empty lists)
    
    BINDINGS = [
        ("down", "next_card", "Next Card"),
        ("up", "prev_card", "Prev Card"),
    ]

    def action_next_card(self):
        self._navigate_card(1)

    def action_prev_card(self):
        self._navigate_card(-1)

    def _navigate_card(self, direction: int):
        # We need to find what is focused. 
        # Since this method is on the ListColumn, we expect one of our children (Cards) to be focused, 
        # OR self explicitly if empty.
        
        cards = list(self.query(CardWidget))
        if not cards:
            return

        focused = self.screen.focused
        
        if focused == self:
             # If list is focused and we press down/up, go to first card?
             if cards:
                 cards[0].focus()
             return

        if focused in cards:
            current_index = cards.index(focused)
            next_index = current_index + direction
            
            if 0 <= next_index < len(cards):
                cards[next_index].focus()
            # Else stop at boundaries

    def __init__(self, planka_list, **kwargs):
        super().__init__(**kwargs)
        self.planka_list = planka_list

    def on_focus(self) -> None:
        """When list is focused, try to focus its first card if available."""
        # If we just tabbed to the list, we might want to focus the first card immediately
        # But if the list is empty, we stay focused on the list column.
        cards = list(self.query(CardWidget))
        if cards:
            cards[0].focus()

    def compose(self) -> ComposeResult:
        # Handle case where planka_list.name might be None
        name = self.planka_list.name if self.planka_list.name else "Untitled List"
        yield Label(name, classes="list_title")
        for card in self.planka_list.cards:
            yield CardWidget(card, classes="card")

class InputModal(ModalScreen[str]):
    """Modal to get text input from user."""
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, prompt: str):
        super().__init__()
        self.prompt = prompt

    def compose(self) -> ComposeResult:
        with Container(classes="modal_dialog"):
            yield Label(self.prompt)
            yield Input(id="input_field")
            with Horizontal(classes="modal_buttons"):
                yield Button("OK", variant="primary", id="ok_btn")
                yield Button("Cancel", variant="error", id="cancel_btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok_btn":
            input_widget = self.query_one(Input)
            self.dismiss(input_widget.value)
        elif event.button.id == "cancel_btn":
            self.dismiss(None)
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_cancel(self):
        self.dismiss(None)

class ConfirmationModal(ModalScreen[bool]):
    """Modal to confirm an action."""
    def __init__(self, prompt: str):
        super().__init__()
        self.prompt = prompt

    def compose(self) -> ComposeResult:
        with Container(classes="modal_dialog"):
            yield Label(self.prompt)
            with Horizontal(classes="modal_buttons"):
                yield Button("Yes", variant="primary", id="yes_btn")
                yield Button("No", variant="error", id="no_btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "yes_btn":
            self.dismiss(True)
        else:
            self.dismiss(False)

class DetailsModal(ModalScreen):
    """Modal to show card details."""
    def __init__(self, title: str, description: str):
        super().__init__()
        self.card_title = title
        self.description = description

    def compose(self) -> ComposeResult:
        with Container(classes="modal_dialog details_modal"):
            yield Label(f"Details for {self.card_title}", classes="modal_header")
            yield Label(self.description, classes="modal_body")
            yield Button("Close", variant="primary", id="close_btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()

class BoardScreen(Screen):
    """Screen to view a specific board."""
    
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("a", "add_card", "Add Card"),
        ("d", "delete_card", "Delete Card"),
        ("c", "mark_done", "Mark Done"),
        ("enter", "view_details", "Details"),
        ("tab", "next_column", "Next List"),
        ("shift+tab", "prev_column", "Prev List"),
        ("right", "next_column", "Next List"),
        ("left", "prev_column", "Prev List"),
    ]

    def __init__(self, board, **kwargs):
        super().__init__(**kwargs)
        self.board = board

    def compose(self) -> ComposeResult:
        yield Header()
        
        # Horizontal container for lists
        with Horizontal(id="board_container"):
            try:
                for lst in self.board.lists:
                    # Filter out lists with None name or empty name if desired
                    if lst.name:
                         # Ensure we can find this specific column later. 
                         # We rely on query(ListColumn) order.
                         yield ListColumn(lst, classes="list_column")
            except Exception as e:
                 yield Label(f"Error loading lists: {e}")

        yield Footer()

    def action_next_column(self):
        self._navigate_column(1)

    def action_prev_column(self):
        self._navigate_column(-1)

    def _navigate_column(self, direction: int):
        """Move focus to the next/prev column, preserving index if possible."""
        current_list = self._get_focused_list()
        all_lists = list(self.query(ListColumn))
        
        if not all_lists:
            return

        next_index = 0
        if current_list in all_lists:
            current_index = all_lists.index(current_list)
            next_index = (current_index + direction) % len(all_lists)
        else:
            # If nothing strictly focused, default to 0 or stay
            pass
            
        target_list = all_lists[next_index]
        target_list.focus()
        
    def on_key(self, event) -> None:
        """Override default tab behavior if needed."""
        if event.key == "tab":
            self.action_next_column()
            event.stop() # Prevent default focus movement
        elif event.key == "shift+tab":
            self.action_prev_column()
            event.stop()




    def _get_focused_card(self):
        focused = self.app.focused
        if isinstance(focused, CardWidget):
            return focused
        return None

    def _get_focused_list(self):
        """Find the list containing the focused card or the list itself if focused."""
        focused = self.app.focused
        # If a card is focused, its parent is the ListColumn (VerticalScroll)
        # Note: CardWidget items are children of ListColumn
        if isinstance(focused, CardWidget):
            # In Textual, widget.parent is the container.
            # CardWidget -> ListColumn
            if isinstance(focused.parent, ListColumn):
                return focused.parent
        elif isinstance(focused, ListColumn):
            return focused
        return None

    def action_add_card(self):
        """Add a card to the current list."""
        target_list_column = self._get_focused_list()
        
        # If no list is focused (e.g. at start), maybe default to first list?
        if not target_list_column:
             # Try to get the first list column
             try:
                 target_list_column = self.query_one(ListColumn)
             except:
                 self.notify("No list available to add card.", severity="warning")
                 return

        def handle_input(name: str):
            if name:
                try:
                    # Create card via API
                    # Using target_list_column.planka_list.create_card(name) if plankapy supports it
                    # Checking plankapy interfaces: List has 'create_card' or we use 'routes'
                    # Assuming typical model method:
                    new_card = target_list_column.planka_list.create_card(name)
                    
                    # Update UI
                    target_list_column.mount(CardWidget(new_card, classes="card"))
                    self.notify(f"Added card: {name}")
                except Exception as e:
                    self.notify(f"Error creating card: {e}", severity="error")

        self.app.push_screen(InputModal("Enter card name:"), handle_input)

    def action_delete_card(self):
        """Delete the focused card."""
        card_widget = self._get_focused_card()
        if card_widget:
            def handle_confirm(confirm: bool):
                if confirm:
                    try:
                        # Delete via API
                        card_widget.card.delete()
                        # Update UI
                        card_widget.remove()
                        self.notify("Card deleted.")
                    except Exception as e:
                        self.notify(f"Error deleting card: {e}", severity="error")
            
            self.app.push_screen(ConfirmationModal(f"Delete '{card_widget.card.name}'?"), handle_confirm)
        else:
            self.notify("No card selected.", severity="warning")

    def action_mark_done(self):
        """Move card to 'Done'/'Tamamlandı' list."""
        card_widget = self._get_focused_card()
        if not card_widget:
            self.notify("No card selected.", severity="warning")
            return

        # Find the "Done" list
        done_list = None
        target_keywords = ["done", "completed", "tamamlandı", "tamamlanan", "finished"]
        
        # We need to iterate over all lists in the board
        # The board object is self.board
        # But we also need the UI component to move the widget visually without full reload if possible
        
        target_planka_list = None
        target_list_ui = None
        
        for ui_list in self.query(ListColumn):
            if ui_list.planka_list.name and ui_list.planka_list.name.lower() in target_keywords:
                target_planka_list = ui_list.planka_list
                target_list_ui = ui_list
                break
        
        if not target_planka_list:
             # Fallback: check all lists on the board object just in case UI didn't render it?
             # Or just notify user
             self.notify("Could not find a 'Done' list.", severity="warning")
             return

        if target_planka_list.id == card_widget.card.listId:
            self.notify("Card is already in Done list.")
            return

        try:
             # Move via API
             # Card update: listId = new_id
             with card_widget.card.editor():
                 card_widget.card.listId = target_planka_list.id
             
             # UI Update: Remove from current, add to new
             card_widget.remove()
             # Ideally we re-create the widget to bind to the updated card, 
             # but card object is mutated in place by editor() usually?
             # Let's just mount the existing widget instance if Textual allows re-mounting
             # Or create new one. Safer to create new one to ensure clean state.
             target_list_ui.mount(CardWidget(card_widget.card, classes="card"))
             
             self.notify("Moved to Done.")

        except Exception as e:
            self.notify(f"Error moving card: {e}", severity="error")

    def action_view_details(self):
        card_widget = self._get_focused_card()
        if card_widget:
             # Fast enough to be sync
             try:
                 desc = card_widget.card.description
                 if not desc:
                     desc = "No description entered."
                 
                 self.app.push_screen(DetailsModal(card_widget.card.name, desc))
             except Exception as e:
                 self.notify(f"Error viewing details: {e}", severity="error")
