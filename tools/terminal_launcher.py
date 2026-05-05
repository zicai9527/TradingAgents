from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox


ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / "venv" / "Scripts" / "python.exe"
RUNNER = ROOT / "scripts" / "run_analysis_noninteractive.py"

PROVIDERS = ["google", "openai", "anthropic", "xai", "deepseek", "qwen", "glm", "openrouter", "ollama"]
LANGUAGES = ["Chinese", "English", "Japanese"]
ANALYST_KEYS = ["market", "social", "news", "fundamentals"]

MODEL_MAP = {
    "google": ["gemini-3.1-pro-preview", "gemini-3-flash-preview", "gemini-3.1-flash-lite-preview"],
    "openai": ["gpt-5.5", "gpt-5.4", "gpt-5.2"],
    "anthropic": ["claude-sonnet-4-6"],
    "xai": ["grok-4"],
    "deepseek": ["deepseek-reasoner", "deepseek-chat"],
    "qwen": ["qwen-max", "qwen-plus"],
    "glm": ["glm-4.5", "glm-4-plus"],
    "openrouter": ["openai/gpt-5.4", "google/gemini-2.5-pro", "anthropic/claude-sonnet-4-6"],
    "ollama": ["deepseek-r1:8b", "llama3.1:70b", "qwen2.5:72b"],
}


def build_command(values: dict) -> list[str]:
    cmd = [
        str(VENV_PYTHON),
        str(RUNNER),
        "--ticker",
        values["ticker"],
        "--trade-date",
        values["trade_date"],
        "--provider",
        values["provider"],
        "--output-language",
        values["output_language"],
        "--research-depth",
        str(values["depth"]),
        "--analysts",
        ",".join(values["analysts"]),
    ]
    if values["deep_model"]:
        cmd += ["--deep-model", values["deep_model"]]
    if values["quick_model"]:
        cmd += ["--quick-model", values["quick_model"]]
    if values["checkpoint"]:
        cmd += ["--checkpoint"]
    if values["clear_checkpoints"]:
        cmd += ["--clear-checkpoints"]
    if values["backend_url"]:
        cmd += ["--backend-url", values["backend_url"]]
    if values["google_thinking_level"]:
        cmd += ["--google-thinking-level", values["google_thinking_level"]]
    if values["openai_reasoning_effort"]:
        cmd += ["--openai-reasoning-effort", values["openai_reasoning_effort"]]
    if values["anthropic_effort"]:
        cmd += ["--anthropic-effort", values["anthropic_effort"]]
    return cmd


def launch_terminal(cmd: list[str]) -> None:
    cmdline = subprocess.list2cmdline(cmd)
    ps_cmd = (
        "Start-Process powershell "
        f"-ArgumentList '-NoExit','-Command','cd \"{ROOT}\"; {cmdline}'"
    )
    subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
        cwd=str(ROOT),
    )


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("TradingAgents 终端启动器")
        self.root.geometry("760x620")

        self.ticker = tk.StringVar(value="NVDA")
        self.trade_date = tk.StringVar(value="2026-05-05")
        self.provider = tk.StringVar(value="google")
        self.output_language = tk.StringVar(value="Chinese")
        self.deep_model = tk.StringVar(value="")
        self.quick_model = tk.StringVar(value="")
        self.depth = tk.IntVar(value=1)
        self.backend_url = tk.StringVar(value="")
        self.google_thinking_level = tk.StringVar(value="")
        self.openai_reasoning_effort = tk.StringVar(value="")
        self.anthropic_effort = tk.StringVar(value="")
        self.checkpoint = tk.BooleanVar(value=False)
        self.clear_checkpoints = tk.BooleanVar(value=False)
        self.analyst_vars = {k: tk.BooleanVar(value=True) for k in ANALYST_KEYS}

        self._build_ui()
        self._refresh_model_options()

    def _build_ui(self) -> None:
        frm = ttk.Frame(self.root, padding=14)
        frm.pack(fill="both", expand=True)

        row = 0
        for label, var in [
            ("股票代码", self.ticker),
            ("分析日期 (YYYY-MM-DD)", self.trade_date),
        ]:
            ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Entry(frm, textvariable=var, width=32).grid(row=row, column=1, sticky="w", pady=4)
            if label == "股票代码":
                ttk.Label(
                    frm,
                    text="示例：美股 NVDA / A股 600519.SS 或 000001.SZ / 日股 7974.T",
                    foreground="#666",
                ).grid(row=row, column=2, sticky="w", padx=8, pady=4)
            row += 1

        ttk.Label(frm, text="模型提供方").grid(row=row, column=0, sticky="w", pady=4)
        provider_box = ttk.Combobox(frm, textvariable=self.provider, values=PROVIDERS, width=30, state="readonly")
        provider_box.grid(row=row, column=1, sticky="w", pady=4)
        provider_box.bind("<<ComboboxSelected>>", lambda _e: self._refresh_model_options())
        row += 1

        ttk.Label(frm, text="深度模型 (可留空自动)").grid(row=row, column=0, sticky="w", pady=4)
        self.deep_box = ttk.Combobox(frm, textvariable=self.deep_model, width=30)
        self.deep_box.grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Label(frm, text="快速模型 (可留空自动)").grid(row=row, column=0, sticky="w", pady=4)
        self.quick_box = ttk.Combobox(frm, textvariable=self.quick_model, width=30)
        self.quick_box.grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Label(frm, text="输出语言").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Combobox(frm, textvariable=self.output_language, values=LANGUAGES, width=30, state="readonly").grid(
            row=row, column=1, sticky="w", pady=4
        )
        row += 1

        ttk.Label(frm, text="研究深度 (1-5)").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Spinbox(frm, from_=1, to=5, textvariable=self.depth, width=8).grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Label(frm, text="分析团队").grid(row=row, column=0, sticky="nw", pady=6)
        afrm = ttk.Frame(frm)
        afrm.grid(row=row, column=1, sticky="w", pady=6)
        for i, k in enumerate(ANALYST_KEYS):
            ttk.Checkbutton(afrm, text=k, variable=self.analyst_vars[k]).grid(row=i // 2, column=i % 2, sticky="w", padx=8)
        row += 1

        ttk.Label(frm, text="backend_url (可选)").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=self.backend_url, width=42).grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Label(frm, text="Google thinking (可选)").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=self.google_thinking_level, width=20).grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Label(frm, text="OpenAI effort (可选)").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=self.openai_reasoning_effort, width=20).grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Label(frm, text="Anthropic effort (可选)").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=self.anthropic_effort, width=20).grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Checkbutton(frm, text="启用 checkpoint", variable=self.checkpoint).grid(row=row, column=1, sticky="w", pady=4)
        row += 1
        ttk.Checkbutton(frm, text="运行前清理 checkpoint", variable=self.clear_checkpoints).grid(
            row=row, column=1, sticky="w", pady=4
        )
        row += 1

        btn = ttk.Button(frm, text="开始分析（打开终端执行）", command=self.run)
        btn.grid(row=row, column=1, sticky="w", pady=14)

        tip = (
            f"运行器: {RUNNER}\n"
            f"Python: {VENV_PYTHON}\n"
            "点按钮后会打开新的 PowerShell 窗口执行，不会占用当前窗口。"
        )
        ttk.Label(frm, text=tip, foreground="#555").grid(row=row + 1, column=0, columnspan=2, sticky="w")

    def _refresh_model_options(self) -> None:
        p = self.provider.get().strip().lower() or "google"
        models = MODEL_MAP.get(p, [])
        self.deep_box["values"] = models
        self.quick_box["values"] = models
        if p == "google":
            if not self.deep_model.get():
                self.deep_model.set("gemini-3.1-pro-preview" if "gemini-3.1-pro-preview" in models else (models[0] if models else ""))
            if not self.quick_model.get():
                if "gemini-3-flash-preview" in models:
                    self.quick_model.set("gemini-3-flash-preview")
                elif "gemini-3.1-flash-lite-preview" in models:
                    self.quick_model.set("gemini-3.1-flash-lite-preview")
                elif models:
                    self.quick_model.set(models[min(1, len(models) - 1)])
        else:
            if not self.deep_model.get() and models:
                self.deep_model.set(models[0])
            if not self.quick_model.get() and models:
                self.quick_model.set(models[min(1, len(models) - 1)])

    def run(self) -> None:
        if not VENV_PYTHON.exists():
            messagebox.showerror("错误", f"未找到 Python: {VENV_PYTHON}")
            return
        if not RUNNER.exists():
            messagebox.showerror("错误", f"未找到运行脚本: {RUNNER}")
            return

        analysts = [k for k, v in self.analyst_vars.items() if v.get()]
        if not analysts:
            messagebox.showerror("错误", "至少选择一个分析团队。")
            return
        if not self.ticker.get().strip() or not self.trade_date.get().strip():
            messagebox.showerror("错误", "股票代码和分析日期不能为空。")
            return

        values = {
            "ticker": self.ticker.get().strip().upper(),
            "trade_date": self.trade_date.get().strip(),
            "provider": self.provider.get().strip().lower(),
            "deep_model": self.deep_model.get().strip(),
            "quick_model": self.quick_model.get().strip(),
            "output_language": self.output_language.get().strip(),
            "depth": self.depth.get(),
            "analysts": analysts,
            "checkpoint": self.checkpoint.get(),
            "clear_checkpoints": self.clear_checkpoints.get(),
            "backend_url": self.backend_url.get().strip(),
            "google_thinking_level": self.google_thinking_level.get().strip(),
            "openai_reasoning_effort": self.openai_reasoning_effort.get().strip(),
            "anthropic_effort": self.anthropic_effort.get().strip(),
        }
        cmd = build_command(values)
        launch_terminal(cmd)
        messagebox.showinfo("已启动", "已打开终端并开始执行分析。")


def main() -> None:
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
