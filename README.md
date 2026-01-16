# Gemini Chat Saver

This tool allows you to save Google Gemini chat conversations to local Markdown files. It uses Playwright to navigate the chat page, handle dynamic content loading, and extract messages.

## Features

- **Save to Markdown**: Converts chat content to formatted Markdown.
- **Filter Thinking Process**: Option to exclude the "thinking" blocks from the output.
- **Auto-Scroll**: Automatically scrolls to load the entire conversation history.
- **Login State Reuse**: Attempts to reuse your Chrome login state to avoid manual login (if available).

## Prerequisites

- Python 3.7+
- Chrome browser (for login state reuse)

## Installation

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Install Playwright browsers:
   ```bash
   playwright install chromium
   ```

## Usage

Run the script with the Gemini chat URL and the desired output file path.

```bash
python main.py <URL> -o <OUTPUT_FILE> [OPTIONS]
```

### Options

- `url`: The URL of the Gemini chat (e.g., `https://gemini.google.com/app/xxxx`).
- `-o, --output`: Output Markdown file path (required).
- `--include-thinking`: Include the AI's thinking process in the output (default is to filter it out).
- `-h, --help`: Show help message.

### Examples

**Basic usage:**
```bash
python main.py https://gemini.google.com/app/12345678 -o my_chat.md
```

**Include thinking process:**
```bash
python main.py https://gemini.google.com/app/12345678 -o my_chat_with_thoughts.md --include-thinking
```

## How it works

1. Launches a Chromium browser (headless or headed depending on configuration).
2. Navigates to the provided Gemini URL.
3. Checks for login; if needed, prompts you to log in.
4. Scrolls up to load all historical messages in the thread.
5. Extracts user queries and model responses.
6. Converts HTML content to Markdown and saves it.

## Troubleshooting

- **Login Issues**: If the tool cannot detect your login state, it will open a browser window for you to log in manually. Once logged in, press Enter in the terminal to continue.
- **Timeout**: If the chat is very long, it might take some time to scroll and load everything.
