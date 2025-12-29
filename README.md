# Planka TUI

A Textual-based Terminal User Interface (TUI) for [Planka](https://github.com/plankanban/planka), a real-time kanban board.

## Features

-   **Dashboard**: View and select from your available projects and boards.
-   **Kanban View**: Interact with your board columns and cards.
-   **Card Management**:
    -   Create new cards.
    -   View card details.
    -   Move cards between lists (Drag & Drop not supported, use move actions).
    -   Mark cards as done (moves to a list named "Done", "Completed", "Tamamlandı", etc.).
    -   Delete cards.
-   **Keyboard Navigation**: Full keyboard support for navigating boards, lists, and cards.

## Installation

### Release binary (Linux)

1.  Download the latest `planka-tui-linux-amd64` from Releases:
    https://github.com/omertahaoztop/planka-tui/releases

2.  Make it executable:
    ```bash
    chmod +x planka-tui-linux-amd64
    ```

3.  Run:
    ```bash
    ./planka-tui-linux-amd64
    ```

Example (system-wide install with `wget`):

```bash
# Download the binary and make it executable
sudo wget https://github.com/omertahaoztop/planka-tui/releases/latest/download/planka-tui-linux-amd64 -O /usr/local/bin/planka-tui
sudo chmod +x /usr/local/bin/planka-tui
# Run
planka-tui
```

### From source

1.  Clone the repository:
    ```bash
    git clone <repository_url>
    cd planka-tui
    ```

2.  Create and activate a virtual environment:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

3.  Install dependencies:
    ```bash
    pip install textual plankapy python-dotenv
    ```

## Configuration

Configuration is loaded from the first file found (in order):
1. `/etc/default/planka-tui` (system-wide, recommended for binary installs)
2. `~/.config/planka-tui/config` (user-specific)
3. `.env` in current directory (for development)

### Binary install (recommended)

```bash
sudo tee /etc/default/planka-tui << 'EOF'
PLANKA_API_URL=https://your-planka-instance.com/api
PLANKA_USERNAME=your_username
PLANKA_PASSWORD=your_password
EOF
sudo chmod 600 /etc/default/planka-tui
```

### From source

```bash
cp .env.example .env
# Edit .env with your credentials
```

### Required variables

```
PLANKA_API_URL=https://your-planka-instance.com/api
PLANKA_USERNAME=your_username
PLANKA_PASSWORD=your_password
```

## Usage

Run the application:

### Binary

```bash
planka-tui
```

### From source

```bash
python main.py
```

### Key Bindings

| Key | Action |
| :--- | :--- |
| `Tab` / `Right` | Next List |
| `Shift+Tab` / `Left` | Previous List |
| `Down` | Next Card |
| `Up` | Previous Card |
| `a` | Add Card |
| `d` | Delete Card |
| `c` | Mark Card as Done |
| `Enter` | View Card Details |
| `Esc` | Back / Cancel |

## Disclaimer

This project is created for **personal and educational purposes only**. It is not affiliated with, endorsed by, or directly supported by the official Planka project. Use at your own risk.
