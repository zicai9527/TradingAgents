from __future__ import annotations

import subprocess
import sys
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


ROOT = Path(__file__).resolve().parents[1]
PYTHON_EXE = ROOT / "venv" / "Scripts" / "python.exe"
BUILDER = ROOT / "webui" / "build_report_ui.py"
DEFAULT_OUT_DIR = ROOT / "reports" / "webui_views"


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("报告网页生成器")
        self.root.geometry("780x430")

        self.input_file = tk.StringVar(value="")
        self.output_dir = tk.StringVar(value=str(DEFAULT_OUT_DIR))
        self.output_name = tk.StringVar(value="")
        self.update_latest = tk.BooleanVar(value=True)
        self.open_after = tk.BooleanVar(value=True)
        self.generated_file = tk.StringVar(value="")

        self._build_ui()

    def _build_ui(self) -> None:
        frm = ttk.Frame(self.root, padding=14)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="输入报告文件 (Markdown)").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Entry(frm, textvariable=self.input_file, width=72).grid(row=1, column=0, sticky="we", pady=4)
        ttk.Button(frm, text="选择文件", command=self.pick_input_file).grid(row=1, column=1, sticky="w", padx=8)

        ttk.Label(frm, text="输出目录").grid(row=2, column=0, sticky="w", pady=10)
        ttk.Entry(frm, textvariable=self.output_dir, width=72).grid(row=3, column=0, sticky="we", pady=4)
        ttk.Button(frm, text="选择目录", command=self.pick_output_dir).grid(row=3, column=1, sticky="w", padx=8)

        ttk.Label(frm, text="输出文件名 (可选，不填则自动时间戳)").grid(row=4, column=0, sticky="w", pady=10)
        ttk.Entry(frm, textvariable=self.output_name, width=40).grid(row=5, column=0, sticky="w", pady=4)

        options = ttk.Frame(frm)
        options.grid(row=6, column=0, sticky="w", pady=10)
        ttk.Checkbutton(options, text="同时更新 webui/report_viewer.html", variable=self.update_latest).grid(
            row=0, column=0, sticky="w", padx=(0, 16)
        )
        ttk.Checkbutton(options, text="生成后自动打开网页", variable=self.open_after).grid(row=0, column=1, sticky="w")

        action = ttk.Frame(frm)
        action.grid(row=7, column=0, sticky="w", pady=12)
        ttk.Button(action, text="生成网页", command=self.generate).grid(row=0, column=0, sticky="w")
        ttk.Button(action, text="打开输出目录", command=self.open_output_dir).grid(row=0, column=1, sticky="w", padx=8)
        ttk.Button(action, text="打开最新网页", command=self.open_latest).grid(row=0, column=2, sticky="w", padx=8)

        ttk.Label(frm, text="生成结果").grid(row=8, column=0, sticky="w", pady=(12, 2))
        ttk.Entry(frm, textvariable=self.generated_file, width=90, state="readonly").grid(row=9, column=0, columnspan=2, sticky="we")

        hint = (
            "说明：\n"
            "1) 输入文件不填时，脚本会自动使用最新报告。\n"
            "2) 输出文件名不填会自动生成带时间戳的版本，避免覆盖。\n"
            "3) 可视化工具本身只负责生成网页，不改动原报告。"
        )
        ttk.Label(frm, text=hint, foreground="#666").grid(row=10, column=0, columnspan=2, sticky="w", pady=(10, 0))

        frm.columnconfigure(0, weight=1)

    def pick_input_file(self) -> None:
        chosen = filedialog.askopenfilename(
            title="选择 Markdown 报告",
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
            initialdir=str(ROOT / "reports"),
        )
        if chosen:
            self.input_file.set(chosen)

    def pick_output_dir(self) -> None:
        chosen = filedialog.askdirectory(
            title="选择输出目录",
            initialdir=self.output_dir.get() or str(DEFAULT_OUT_DIR),
        )
        if chosen:
            self.output_dir.set(chosen)

    def _build_cmd(self) -> list[str]:
        cmd = [str(PYTHON_EXE), str(BUILDER)]
        if self.input_file.get().strip():
            cmd += ["--input", self.input_file.get().strip()]
        if self.output_dir.get().strip():
            cmd += ["--output-dir", self.output_dir.get().strip()]
        if self.output_name.get().strip():
            cmd += ["--name", self.output_name.get().strip()]
        if not self.update_latest.get():
            cmd += ["--no-latest"]
        return cmd

    def generate(self) -> None:
        if not PYTHON_EXE.exists():
            messagebox.showerror("错误", f"未找到 Python：{PYTHON_EXE}")
            return
        if not BUILDER.exists():
            messagebox.showerror("错误", f"未找到脚本：{BUILDER}")
            return
        try:
            cmd = self._build_cmd()
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), check=False)
            if proc.returncode != 0:
                messagebox.showerror("生成失败", proc.stderr or proc.stdout or "未知错误")
                return

            output_path = self._parse_generated_path(proc.stdout)
            self.generated_file.set(str(output_path) if output_path else "(未识别输出路径)")
            messagebox.showinfo("成功", "网页报告已生成。")
            if output_path and self.open_after.get():
                webbrowser.open(output_path.as_uri())
        except Exception as exc:
            messagebox.showerror("异常", str(exc))

    @staticmethod
    def _parse_generated_path(stdout: str) -> Path | None:
        for line in stdout.splitlines():
            if line.startswith("Generated: "):
                p = line.replace("Generated: ", "", 1).strip()
                path = Path(p)
                if path.exists():
                    return path
        return None

    def open_output_dir(self) -> None:
        out = Path(self.output_dir.get().strip() or DEFAULT_OUT_DIR)
        out.mkdir(parents=True, exist_ok=True)
        webbrowser.open(out.as_uri())

    def open_latest(self) -> None:
        latest = ROOT / "webui" / "report_viewer.html"
        if latest.exists():
            webbrowser.open(latest.as_uri())
        else:
            messagebox.showwarning("提示", "未找到 report_viewer.html，请先生成一次。")


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

