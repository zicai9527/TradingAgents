from __future__ import annotations

import argparse
import html
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"
OUTPUT_HTML = ROOT / "webui" / "report_viewer.html"


def find_latest_report() -> Path:
    candidates = list(REPORTS_DIR.glob("*/complete_report.md"))
    if not candidates:
        raise FileNotFoundError("No report file found under reports/*/complete_report.md")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def read_markdown(path: Path) -> str:
    # Try UTF-8 first (expected), fallback to CP932 for Windows edge cases.
    for enc in ("utf-8", "utf-8-sig", "cp932"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="replace")


def markdown_to_html(md: str) -> tuple[str, list[tuple[str, str]]]:
    lines = md.splitlines()
    out: list[str] = []
    toc: list[tuple[str, str]] = []
    in_list = False
    in_table = False
    table_rows: list[list[str]] = []

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    def close_table() -> None:
        nonlocal in_table, table_rows
        if not in_table:
            return
        if len(table_rows) >= 2:
            header = table_rows[0]
            body = [r for r in table_rows[2:]]
            head_html = "".join(f"<th>{html.escape(c.strip())}</th>" for c in header)
            body_html = ""
            for row in body:
                cells = "".join(f"<td>{html.escape(c.strip())}</td>" for c in row)
                body_html += f"<tr>{cells}</tr>"
            out.append(
                "<div class='table-wrap'><table><thead><tr>"
                + head_html
                + "</tr></thead><tbody>"
                + body_html
                + "</tbody></table></div>"
            )
        in_table = False
        table_rows = []

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            close_list()
            close_table()
            out.append("<div class='spacer'></div>")
            continue

        if line.startswith("|") and line.endswith("|"):
            close_list()
            if not in_table:
                in_table = True
                table_rows = []
            cols = [c for c in line.strip("|").split("|")]
            table_rows.append(cols)
            continue
        close_table()

        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            close_list()
            level = len(m.group(1))
            text = m.group(2).strip()
            slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+", "-", text).strip("-").lower()
            if level <= 3:
                toc.append((text, slug))
            out.append(f"<h{level} id='{slug}'>{html.escape(text)}</h{level}>")
            continue

        if re.match(r"^\s*[-*]\s+", line):
            close_table()
            if not in_list:
                out.append("<ul>")
                in_list = True
            text = re.sub(r"^\s*[-*]\s+", "", line)
            out.append(f"<li>{html.escape(text)}</li>")
            continue

        close_list()
        text = html.escape(line)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
        out.append(f"<p>{text}</p>")

    close_list()
    close_table()
    return "\n".join(out), toc


def extract_title(md: str, default: str) -> str:
    for line in md.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return default


def build_html(title: str, source: Path, report_html: str, toc: list[tuple[str, str]]) -> str:
    toc_html = "\n".join(
        f"<a class='toc-link' href='#{slug}'>{html.escape(text)}</a>" for text, slug in toc
    )
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)} - Report Viewer</title>
  <style>
    :root {{
      --bg: #f5f7fb;
      --panel: #ffffff;
      --ink: #1b2430;
      --sub: #5c6675;
      --line: #dfe5ee;
      --accent: #0f766e;
      --accent-2: #0369a1;
      --shadow: 0 8px 28px rgba(15, 23, 42, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Noto Sans SC", "PingFang SC", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(1100px 500px at 110% -20%, rgba(14, 116, 144, 0.10), transparent 55%),
        radial-gradient(900px 480px at -10% 0%, rgba(15, 118, 110, 0.10), transparent 52%),
        var(--bg);
    }}
    .layout {{
      max-width: 1240px;
      margin: 0 auto;
      padding: 24px;
      display: grid;
      gap: 16px;
      grid-template-columns: 280px minmax(0, 1fr);
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .sidebar {{
      position: sticky;
      top: 16px;
      padding: 16px;
      height: fit-content;
    }}
    .eyebrow {{
      font-size: 12px;
      font-weight: 600;
      color: var(--accent-2);
      text-transform: uppercase;
    }}
    .h1 {{
      margin: 8px 0 4px;
      font-size: 20px;
      font-weight: 700;
      line-height: 1.3;
    }}
    .meta {{
      font-size: 12px;
      color: var(--sub);
      margin-bottom: 10px;
      word-break: break-all;
    }}
    .toc-title {{
      margin: 14px 0 8px;
      font-size: 12px;
      color: var(--sub);
      text-transform: uppercase;
      letter-spacing: .04em;
    }}
    .toc-link {{
      display: block;
      text-decoration: none;
      color: var(--ink);
      font-size: 13px;
      border-left: 2px solid transparent;
      padding: 6px 8px;
      border-radius: 4px;
    }}
    .toc-link:hover {{
      background: #eef6f6;
      border-left-color: var(--accent);
    }}
    .content {{
      padding: 20px 24px;
      overflow: hidden;
    }}
    h1,h2,h3,h4,h5,h6 {{
      margin: 18px 0 8px;
      line-height: 1.35;
    }}
    h1 {{ font-size: 28px; }}
    h2 {{
      font-size: 22px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 8px;
    }}
    h3 {{ font-size: 18px; color: #0b5560; }}
    p {{
      margin: 8px 0;
      color: #2b3440;
      line-height: 1.72;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    ul {{
      margin: 8px 0 8px 18px;
      padding: 0;
    }}
    li {{
      margin: 5px 0;
      line-height: 1.65;
    }}
    code {{
      background: #edf2f7;
      padding: 2px 6px;
      border-radius: 4px;
      font-family: Consolas, "SFMono-Regular", monospace;
      font-size: 0.92em;
    }}
    .table-wrap {{ overflow-x: auto; margin: 12px 0; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 700px;
    }}
    th, td {{
      border: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }}
    th {{ background: #f2f7fb; font-weight: 700; }}
    .spacer {{ height: 4px; }}
    @media (max-width: 980px) {{
      .layout {{ grid-template-columns: 1fr; padding: 12px; }}
      .sidebar {{ position: static; }}
      .content {{ padding: 16px; }}
    }}
  </style>
</head>
<body>
  <div class="layout">
    <aside class="panel sidebar">
      <div class="eyebrow">TradingAgents Report</div>
      <div class="h1">{html.escape(title)}</div>
      <div class="meta">Source: {html.escape(str(source))}</div>
      <div class="meta">Generated UI: {generated}</div>
      <div class="toc-title">Contents</div>
      {toc_html}
    </aside>
    <main class="panel content">
      {report_html}
    </main>
  </div>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    source = resolve_source(args.input, args.pick_file)
    md = read_markdown(source)
    report_html, toc = markdown_to_html(md)
    title = extract_title(md, source.parent.name)
    page = build_html(title, source, report_html, toc)
    output_path = resolve_output_path(args, source)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page, encoding="utf-8")
    if not args.no_latest:
        OUTPUT_HTML.write_text(page, encoding="utf-8")
        print(f"Updated latest viewer: {OUTPUT_HTML}")
    print(f"Generated: {output_path}")
    print(f"Report source: {source}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build styled HTML viewer from TradingAgents markdown report.")
    p.add_argument("--input", default="", help="Path to markdown report file. If empty, use latest or picker.")
    p.add_argument("--output-dir", default="", help="Directory for generated HTML output.")
    p.add_argument("--output-file", default="", help="Exact output HTML file path.")
    p.add_argument("--name", default="", help="Output file name without extension (used with --output-dir).")
    p.add_argument("--pick-file", action="store_true", help="Open file picker to choose report markdown.")
    p.add_argument("--no-latest", action="store_true", help="Do not overwrite webui/report_viewer.html.")
    return p.parse_args()


def pick_file_dialog() -> Optional[Path]:
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        chosen = filedialog.askopenfilename(
            title="Select report markdown",
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
            initialdir=str(REPORTS_DIR if REPORTS_DIR.exists() else ROOT),
        )
        root.destroy()
        if chosen:
            return Path(chosen)
    except Exception:
        return None
    return None


def resolve_source(input_arg: str, pick_file: bool = False) -> Path:
    if pick_file:
        picked = pick_file_dialog()
        if picked is not None:
            return picked
    if input_arg.strip():
        p = Path(input_arg.strip()).expanduser()
        if not p.is_absolute():
            p = (ROOT / p).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Input report not found: {p}")
        return p
    # fallback: latest report
    return find_latest_report()


def resolve_output_path(args: argparse.Namespace, source: Path) -> Path:
    if args.output_file.strip():
        p = Path(args.output_file.strip()).expanduser()
        if not p.is_absolute():
            p = (ROOT / p).resolve()
        return p

    out_dir = Path(args.output_dir.strip()).expanduser() if args.output_dir.strip() else (ROOT / "reports" / "webui_views")
    if not out_dir.is_absolute():
        out_dir = (ROOT / out_dir).resolve()

    if args.name.strip():
        filename = f"{args.name.strip()}.html"
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{source.stem}_{stamp}.html"
    return out_dir / filename


if __name__ == "__main__":
    main()
