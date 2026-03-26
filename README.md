# Gemini Chat Saver

This tool allows you to save Google Gemini chat conversations to local Markdown files. It uses Playwright to navigate the chat page, handle dynamic content loading, and extract messages.

## Features

- **Save to Markdown**: Converts chat content to formatted Markdown.
- **Extract Generated Images**: Automatically downloads Gemini-generated images and embeds them in the output.
- **Filter Thinking Process**: Option to exclude the "thinking" blocks from the output.
- **Auto-Scroll**: Automatically scrolls to load the entire conversation history.
- **One-Click PDF**: Convert conversations directly to PDF with `gemini2pdf.py`.
- **Login State Reuse**: Attempts to reuse your Chrome login state to avoid manual login (if available).

## Prerequisites

- Python 3.7+
- Chrome browser (for login state reuse)

The script now seamlessly manages an isolated Python virtual environment (`.venv`).

1. Make the wrapper script executable (only needed once):
   ```bash
   chmod +x gemini2pdf.sh
   ```

2. That's it! The script will automatically create a virtual environment, install dependencies, and download the Chromium browser on its first run.

It is recommended to use the `gemini2pdf.sh` shell script, which automatically handles standard environment isolation for you.

```bash
./gemini2pdf.sh "URL" [OPTIONS]
```

### Options

- `url`: The URL of the Gemini chat (e.g., `https://gemini.google.com/app/xxxx`).
- `-o, --output`: Output Markdown file path (required).
- `--include-thinking`: Include the AI's thinking process in the output (default is to filter it out).
- `-h, --help`: Show help message.

**Basic usage:**
```bash
./gemini2pdf.sh "https://gemini.google.com/app/12345678"
```

**Include thinking process:**
```bash
./gemini2pdf.sh "https://gemini.google.com/app/12345678" --include-thinking
```

---

## 一键转换 PDF (gemini2pdf.py)

新增的 `gemini2pdf.py` 命令可以直接将 Gemini 对话一键保存为 PDF，无需手动指定输出文件名。

### 使用方法

```bash
./gemini2pdf.sh "URL" [OPTIONS]
```

### 选项

- `-d, --dir DIR`: 输出目录（默认为当前目录）
- `--keep-md`: 保留中间的 Markdown 文件
- `--include-thinking`: 包含思考过程

**基本用法（自动生成文件名）：**
```bash
./gemini2pdf.sh "https://gemini.google.com/app/12345678"
```

**指定输出目录：**
```bash
./gemini2pdf.sh "https://gemini.google.com/app/12345678" -d ~/Documents
```

**同时保留 Markdown 和 PDF：**
```bash
./gemini2pdf.sh "https://gemini.google.com/app/12345678" --keep-md
```

---

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
