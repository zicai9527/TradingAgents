from __future__ import annotations

import html
import json
import os
import threading
import traceback
import uuid
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.request import urlopen
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.enterprise", override=False)

HOST = "127.0.0.1"
PORT = 8765
EXPORT_DIR = ROOT / "reports" / "webui_exports"

ANALYSTS = ["market", "social", "news", "fundamentals"]
OUTPUT_LANGUAGES = ["Chinese", "English", "Japanese"]
PROVIDERS = ["openai", "google", "anthropic", "xai", "deepseek", "qwen", "glm", "openrouter", "ollama"]

MODEL_SUGGESTIONS = {
    "openai": ("gpt-5.5", "gpt-5.4"),
    "google": ("gemini-3.1-pro-preview", "gemini-2.5-pro"),
    "anthropic": ("claude-sonnet-4-6", "claude-sonnet-4-6"),
}

MODEL_OPTIONS = {
    "openai": ["gpt-5.5", "gpt-5.4", "gpt-5.2"],
    "google": ["gemini-3.1-pro-preview", "gemini-3-pro-preview", "gemini-2.5-pro", "gemini-pro-latest"],
    "anthropic": ["claude-sonnet-4-6"],
    "xai": ["grok-4"],
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
    "qwen": ["qwen-max", "qwen-plus"],
    "glm": ["glm-4.5", "glm-4-plus"],
    "openrouter": ["openai/gpt-5.4", "google/gemini-2.5-pro", "anthropic/claude-sonnet-4-6"],
    "ollama": ["deepseek-r1:8b", "llama3.1:70b", "qwen2.5:72b"],
}

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()

def fetch_google_models_live() -> list[str]:
    env_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not env_key:
        return []

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={env_key}"
    try:
        with urlopen(url, timeout=12) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except (URLError, HTTPError, TimeoutError, json.JSONDecodeError):
        return []

    models = []
    for item in payload.get("models", []):
        name = str(item.get("name", ""))
        # API returns names like "models/gemini-2.5-pro"
        if name.startswith("models/"):
            name = name.split("/", 1)[1]
        methods = item.get("supportedGenerationMethods", []) or []
        if "generateContent" not in methods:
            continue
        if not name.startswith("gemini"):
            continue
        lower = name.lower()
        blocked = ("flash-lite", "lite", "robotics", "image", "tts", "aqa", "embedding")
        if any(k in lower for k in blocked):
            continue
        if ("pro" not in lower) and ("reasoner" not in lower) and ("latest" not in lower):
            continue
        models.append(name)

    # Deduplicate while preserving natural sorted order
    return sorted(set(models), reverse=True)


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(str(x) for x in value)
    return str(value)


def build_complete_report_md(ticker: str, trade_date: str, final_state: dict) -> str:
    parts = [
        f"# Trading Analysis Report: {ticker}",
        f"Generated: {trade_date}",
        "",
        "## I. Analyst Team Reports",
        "",
        "### Market Analyst",
        to_text(final_state.get("market_report", "")),
        "",
        "### Social Analyst",
        to_text(final_state.get("sentiment_report", "")),
        "",
        "### News Analyst",
        to_text(final_state.get("news_report", "")),
        "",
        "### Fundamentals Analyst",
        to_text(final_state.get("fundamentals_report", "")),
        "",
        "## II. Research Team Reports",
    ]
    inv = final_state.get("investment_debate_state", {}) or {}
    parts.extend(
        [
            "",
            "### Bull Researcher",
            to_text(inv.get("bull_history", "")),
            "",
            "### Bear Researcher",
            to_text(inv.get("bear_history", "")),
            "",
            "### Research Manager",
            to_text(final_state.get("investment_plan", "")),
            "",
            "## III. Trading Team Reports",
            "",
            "### Trader",
            to_text(final_state.get("trader_investment_plan", "")),
            "",
            "## IV. Risk Management Team Reports",
        ]
    )
    risk = final_state.get("risk_debate_state", {}) or {}
    parts.extend(
        [
            "",
            "### Aggressive Analyst",
            to_text(risk.get("aggressive_history", "")),
            "",
            "### Neutral Analyst",
            to_text(risk.get("neutral_history", "")),
            "",
            "### Conservative Analyst",
            to_text(risk.get("conservative_history", "")),
            "",
            "## V. Portfolio Management Team Reports",
            "",
            "### Portfolio Manager",
            to_text(final_state.get("final_trade_decision", "")),
            "",
        ]
    )
    return "\n".join(parts).strip() + "\n"


def export_structured_bundle(base_dir: Path, ticker: str, trade_date: str, final_state: dict) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "1_analysts").mkdir(parents=True, exist_ok=True)
    (base_dir / "2_research").mkdir(parents=True, exist_ok=True)
    (base_dir / "3_trading").mkdir(parents=True, exist_ok=True)
    (base_dir / "4_risk").mkdir(parents=True, exist_ok=True)
    (base_dir / "5_portfolio").mkdir(parents=True, exist_ok=True)

    (base_dir / "1_analysts" / "market.md").write_text(to_text(final_state.get("market_report", "")), encoding="utf-8")
    (base_dir / "1_analysts" / "sentiment.md").write_text(to_text(final_state.get("sentiment_report", "")), encoding="utf-8")
    (base_dir / "1_analysts" / "news.md").write_text(to_text(final_state.get("news_report", "")), encoding="utf-8")
    (base_dir / "1_analysts" / "fundamentals.md").write_text(to_text(final_state.get("fundamentals_report", "")), encoding="utf-8")

    inv = final_state.get("investment_debate_state", {}) or {}
    (base_dir / "2_research" / "bull.md").write_text(to_text(inv.get("bull_history", "")), encoding="utf-8")
    (base_dir / "2_research" / "bear.md").write_text(to_text(inv.get("bear_history", "")), encoding="utf-8")
    (base_dir / "2_research" / "manager.md").write_text(to_text(final_state.get("investment_plan", "")), encoding="utf-8")

    (base_dir / "3_trading" / "trader.md").write_text(to_text(final_state.get("trader_investment_plan", "")), encoding="utf-8")

    risk = final_state.get("risk_debate_state", {}) or {}
    (base_dir / "4_risk" / "aggressive.md").write_text(to_text(risk.get("aggressive_history", "")), encoding="utf-8")
    (base_dir / "4_risk" / "neutral.md").write_text(to_text(risk.get("neutral_history", "")), encoding="utf-8")
    (base_dir / "4_risk" / "conservative.md").write_text(to_text(risk.get("conservative_history", "")), encoding="utf-8")

    (base_dir / "5_portfolio" / "decision.md").write_text(to_text(final_state.get("final_trade_decision", "")), encoding="utf-8")

    complete = build_complete_report_md(ticker, trade_date, final_state)
    (base_dir / "complete_report.md").write_text(complete, encoding="utf-8")
    return base_dir


def render_form(message: str = "", error: bool = False, defaults: dict | None = None) -> str:
    defaults = defaults or {}
    ticker = defaults.get("ticker", "NVDA")
    trade_date = defaults.get("trade_date", date.today().isoformat())
    provider = defaults.get("provider", "google")
    deep_model = defaults.get("deep_model", "")
    quick_model = defaults.get("quick_model", "")
    output_language = defaults.get("output_language", "Chinese")
    checkpoint = defaults.get("checkpoint", False)
    selected = defaults.get("analysts", ANALYSTS)
    max_debate_rounds = defaults.get("max_debate_rounds", "1")

    options_provider = "".join(
        f"<option value='{p}' {'selected' if p == provider else ''}>{p}</option>" for p in PROVIDERS
    )
    options_lang = "".join(
        f"<option value='{lang}' {'selected' if lang == output_language else ''}>{lang}</option>"
        for lang in OUTPUT_LANGUAGES
    )

    checkbox_html = "".join(
        (
            "<label class='check'>"
            f"<input type='checkbox' name='analysts' value='{name}' {'checked' if name in selected else ''}/>"
            f"<span>{name}</span></label>"
        )
        for name in ANALYSTS
    )

    status_class = "status err" if error else "status ok"
    status = f"<div class='{status_class}'>{esc(message)}</div>" if message else ""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>TradingAgents 网页版</title>
  <style>
    :root {{
      --bg:#f4f7fb; --panel:#fff; --line:#dce4ef; --ink:#1f2937; --sub:#596579;
      --brand:#0f766e; --brand2:#0b5ea8;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0; font-family: "Segoe UI","Noto Sans",sans-serif; color:var(--ink);
      background:
        radial-gradient(900px 380px at -10% -10%, rgba(15,118,110,.12), transparent 55%),
        radial-gradient(1000px 420px at 110% -20%, rgba(11,94,168,.10), transparent 55%),
        var(--bg);
    }}
    .wrap {{ max-width:980px; margin:24px auto; padding:0 16px; }}
    .panel {{
      background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:18px;
      box-shadow:0 10px 24px rgba(15,23,42,.06);
    }}
    h1 {{ margin:0 0 8px; font-size:24px; }}
    .sub {{ margin:0 0 16px; color:var(--sub); font-size:14px; }}
    .grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }}
    .field label {{ font-size:13px; color:var(--sub); display:block; margin-bottom:4px; }}
    input, select {{
      width:100%; height:38px; border:1px solid var(--line); border-radius:6px; padding:0 10px;
      background:#fff; color:var(--ink);
    }}
    .checks {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; margin-top:6px; }}
    .check {{ display:flex; align-items:center; gap:8px; border:1px solid var(--line); border-radius:6px; padding:8px; font-size:13px; }}
    .actions {{ display:flex; gap:8px; margin-top:14px; }}
    button {{
      border:none; background:var(--brand); color:#fff; height:38px; padding:0 14px; border-radius:6px;
      cursor:pointer; font-weight:600;
    }}
    .ghost {{ background:#e8eef8; color:#123; text-decoration:none; display:inline-flex; align-items:center; padding:0 14px; border-radius:6px; height:38px; }}
    .status {{ margin:0 0 12px; padding:10px 12px; border-radius:6px; font-size:13px; }}
    .ok {{ background:#ecfdf5; border:1px solid #bbf7d0; color:#166534; }}
    .err {{ background:#fef2f2; border:1px solid #fecaca; color:#991b1b; }}
    @media (max-width:760px) {{ .grid,.checks{{grid-template-columns:1fr;}} }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <h1>TradingAgents 网页版</h1>
      <p class="sub">不需要终端，直接在浏览器运行完整分析流程。</p>
      {status}
      <form method="post" action="/run">
        <div class="grid">
          <div class="field">
            <label>股票代码</label>
            <input name="ticker" value="{esc(str(ticker))}" required/>
          </div>
          <div class="field">
            <label>分析日期</label>
            <input type="date" name="trade_date" value="{esc(str(trade_date))}" required/>
          </div>
          <div class="field">
            <label>模型提供方</label>
            <select name="provider">{options_provider}</select>
          </div>
          <div class="field">
            <label>输出语言</label>
            <select name="output_language">{options_lang}</select>
          </div>
          <div class="field">
            <label>深度模型（可选）</label>
            <select id="deep_model" name="deep_model"></select>
          </div>
          <div class="field">
            <label>快速模型（可选）</label>
            <select id="quick_model" name="quick_model"></select>
          </div>
          <div class="field">
            <label>最大辩论轮数</label>
            <input type="number" min="1" max="5" name="max_debate_rounds" value="{esc(str(max_debate_rounds))}"/>
          </div>
          <div class="field">
            <label>断点续跑</label>
            <select name="checkpoint">
              <option value="false" {'selected' if not checkpoint else ''}>关闭</option>
              <option value="true" {'selected' if checkpoint else ''}>开启</option>
            </select>
          </div>
        </div>
        <div class="field" style="margin-top:12px;">
          <label>分析团队</label>
          <div class="checks">{checkbox_html}</div>
        </div>
        <div class="actions">
          <button type="submit">开始分析</button>
          <a class="ghost" href="/health">服务状态</a>
        </div>
      </form>
    </div>
  </div>
</body>
<script>
  const modelOptions = {json.dumps(MODEL_OPTIONS, ensure_ascii=False)};
  const fallbackByProvider = {json.dumps(MODEL_SUGGESTIONS, ensure_ascii=False)};
  const presetDeep = {json.dumps(deep_model, ensure_ascii=False)};
  const presetQuick = {json.dumps(quick_model, ensure_ascii=False)};
  const providerEl = document.querySelector("select[name='provider']");
  const deepEl = document.getElementById("deep_model");
  const quickEl = document.getElementById("quick_model");

  function fillModelSelect(el, options, selectedValue, fallbackValue) {{
    el.innerHTML = "";
    const autoOpt = document.createElement("option");
    autoOpt.value = "";
    autoOpt.textContent = "自动（推荐）";
    el.appendChild(autoOpt);

    (options || []).forEach(m => {{
      const opt = document.createElement("option");
      opt.value = m;
      opt.textContent = m;
      el.appendChild(opt);
    }});

    if (selectedValue && (options || []).includes(selectedValue)) {{
      el.value = selectedValue;
    }} else {{
      el.value = "";
    }}

    if (!selectedValue && fallbackValue && (options || []).includes(fallbackValue)) {{
      el.title = "Auto fallback: " + fallbackValue;
    }} else {{
      el.title = "";
    }}
  }}

  function refreshModelOptions() {{
    const provider = providerEl.value || "google";
    const options = modelOptions[provider] || [];
    const fb = fallbackByProvider[provider] || fallbackByProvider["google"];
    fillModelSelect(deepEl, options, presetDeep, fb[0]);
    fillModelSelect(quickEl, options, presetQuick, fb[1]);
  }}

  providerEl.addEventListener("change", () => {{
    // provider changed: clear manual preset and refresh
    fillModelSelect(deepEl, modelOptions[providerEl.value] || [], "", (fallbackByProvider[providerEl.value] || fallbackByProvider["google"])[0]);
    fillModelSelect(quickEl, modelOptions[providerEl.value] || [], "", (fallbackByProvider[providerEl.value] || fallbackByProvider["google"])[1]);
  }});

  async function tryLoadGoogleModels() {{
    if ((providerEl.value || "google") !== "google") return;
    try {{
      const r = await fetch("/api/google-models", {{ cache: "no-store" }});
      if (!r.ok) return;
      const data = await r.json();
      if (Array.isArray(data.models) && data.models.length > 0) {{
        modelOptions.google = data.models;
        refreshModelOptions();
      }}
    }} catch (_) {{
      // Keep static fallback list
    }}
  }}

  refreshModelOptions();
  tryLoadGoogleModels();
</script>
</html>"""


def render_result(form: dict, final_state: dict, decision: str) -> str:
    reports = [
        ("市场分析", final_state.get("market_report", "")),
        ("情绪分析", final_state.get("sentiment_report", "")),
        ("新闻分析", final_state.get("news_report", "")),
        ("基本面分析", final_state.get("fundamentals_report", "")),
        ("投研计划", final_state.get("investment_plan", "")),
        ("交易员计划", final_state.get("trader_investment_plan", "")),
        ("最终决策", final_state.get("final_trade_decision", "")),
    ]
    cards = "".join(
        f"<section class='card'><h3>{esc(name)}</h3><pre>{esc(str(text))}</pre></section>"
        for name, text in reports
        if str(text).strip()
    )
    inv = final_state.get("investment_debate_state", {}) or {}
    risk = final_state.get("risk_debate_state", {}) or {}
    think_blocks = [
        ("多方观点", inv.get("bull_history", "")),
        ("空方观点", inv.get("bear_history", "")),
        ("投研辩论记录", inv.get("history", "")),
        ("风控激进观点", risk.get("aggressive_history", "")),
        ("风控中性观点", risk.get("neutral_history", "")),
        ("风控保守观点", risk.get("conservative_history", "")),
        ("风控辩论记录", risk.get("history", "")),
    ]
    think_html = "".join(
        f"<details class='think'><summary>{esc(title)}</summary><pre>{esc(str(content))}</pre></details>"
        for title, content in think_blocks
        if str(content).strip()
    )
    if not think_html:
        think_html = "<div class='card'><h3>思考过程</h3><pre>当前任务未返回可视化思考轨迹。</pre></div>"
    return f"""<!doctype html>
<html lang="en"><head>
  <meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>分析结果</title>
  <style>
    body {{ margin:0; font-family:"Segoe UI","Noto Sans",sans-serif; background:#f4f7fb; color:#1f2937; }}
    .wrap {{ max-width:1180px; margin:20px auto; padding:0 14px; }}
    .top {{ background:#fff; border:1px solid #dce4ef; border-radius:8px; padding:14px; }}
    .title {{ font-size:22px; margin:0 0 6px; }}
    .meta {{ color:#5b6779; font-size:13px; }}
    .badge {{ display:inline-block; margin-top:8px; background:#ecfeff; color:#0f766e; border:1px solid #99f6e4; border-radius:999px; padding:6px 10px; font-size:12px; font-weight:700; }}
    .actions {{ margin-top:10px; display:flex; gap:8px; }}
    .btn {{ text-decoration:none; background:#0f766e; color:#fff; border-radius:6px; padding:8px 12px; font-size:13px; }}
    .btn2 {{ text-decoration:none; background:#0b5ea8; color:#fff; border-radius:6px; padding:8px 12px; font-size:13px; }}
    .think-wrap {{ margin-top:12px; }}
    .think {{ background:#fff; border:1px solid #dce4ef; border-radius:8px; padding:10px 12px; margin-bottom:10px; }}
    .think summary {{ cursor:pointer; font-weight:600; }}
    .grid {{ margin-top:12px; display:grid; gap:12px; grid-template-columns:1fr 1fr; }}
    .card {{ background:#fff; border:1px solid #dce4ef; border-radius:8px; padding:12px; }}
    h3 {{ margin:0 0 8px; font-size:16px; }}
    pre {{ margin:0; white-space:pre-wrap; word-break:break-word; line-height:1.58; font-family:"Segoe UI","Noto Sans",sans-serif; }}
    @media (max-width:920px) {{ .grid {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <h1 class="title">分析完成</h1>
      <div class="meta">股票: {esc(form.get("ticker",""))} | 日期: {esc(form.get("trade_date",""))} | Provider: {esc(form.get("provider",""))}</div>
      <div class="badge">信号: {esc(str(decision))}</div>
      <div class="actions">
        <a class="btn" href="/">再跑一次</a>
        <a class="btn2" href="/export/{esc(form.get("_job_id",""))}?fmt=md">保存 Markdown</a>
        <a class="btn2" href="/export/{esc(form.get("_job_id",""))}?fmt=html">保存 HTML</a>
      </div>
    </div>
    <div class="think-wrap">{think_html}</div>
    <div class="grid">{cards}</div>
  </div>
</body></html>"""


def render_job_page(job_id: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head>
  <meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>分析进行中</title>
  <style>
    body {{ margin:0; font-family:"Segoe UI","Noto Sans",sans-serif; background:#f4f7fb; color:#1f2937; }}
    .wrap {{ max-width:780px; margin:40px auto; padding:0 16px; }}
    .card {{ background:#fff; border:1px solid #dce4ef; border-radius:8px; padding:18px; }}
    h1 {{ margin:0 0 10px; font-size:22px; }}
    .muted {{ color:#5b6779; font-size:14px; }}
    .status {{ margin-top:12px; padding:10px 12px; border-radius:6px; font-size:14px; }}
    .running {{ background:#eff6ff; border:1px solid #bfdbfe; color:#1d4ed8; }}
    .done {{ background:#ecfdf5; border:1px solid #bbf7d0; color:#166534; }}
    .err {{ background:#fef2f2; border:1px solid #fecaca; color:#991b1b; white-space:pre-wrap; }}
    .btn {{ margin-top:12px; display:inline-block; text-decoration:none; background:#0f766e; color:#fff; padding:8px 12px; border-radius:6px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>分析进行中</h1>
      <div class="muted">任务 ID: {esc(job_id)}</div>
      <div id="status" class="status running">任务已启动...</div>
      <a id="resultBtn" class="btn" href="#" style="display:none;">查看结果</a>
    </div>
  </div>
<script>
  const jobId = {json.dumps(job_id)};
  const statusEl = document.getElementById("status");
  const btn = document.getElementById("resultBtn");
  async function tick() {{
    try {{
      const r = await fetch("/api/job/" + encodeURIComponent(jobId), {{cache:"no-store"}});
      if (!r.ok) return;
      const d = await r.json();
      if (d.status === "running") {{
        statusEl.className = "status running";
        statusEl.textContent = "正在运行，请稍候（取决于模型和网络，可能需要几分钟）";
      }} else if (d.status === "done") {{
        statusEl.className = "status done";
        statusEl.textContent = "已完成。";
        btn.href = "/result/" + encodeURIComponent(jobId);
        btn.style.display = "inline-block";
        clearInterval(timer);
      }} else if (d.status === "error") {{
        statusEl.className = "status err";
        statusEl.textContent = "失败: " + (d.error || "未知错误");
        clearInterval(timer);
      }}
    }} catch (_) {{}}
  }}
  const timer = setInterval(tick, 2000);
  tick();
</script>
</body></html>"""


def start_job(form_defaults: dict, params: dict) -> str:
    job_id = uuid.uuid4().hex[:12]
    with JOBS_LOCK:
        JOBS[job_id] = {"status": "running", "form": form_defaults}

    def worker() -> None:
        try:
            config = DEFAULT_CONFIG.copy()
            config["llm_provider"] = params["provider"]
            config["deep_think_llm"] = params["deep_model"]
            config["quick_think_llm"] = params["quick_model"]
            config["output_language"] = params["output_language"]
            config["checkpoint_enabled"] = params["checkpoint"]
            config["max_debate_rounds"] = params["debate_rounds"]
            ta = TradingAgentsGraph(selected_analysts=params["analysts"], debug=False, config=config)
            final_state, decision = ta.propagate(params["ticker"], params["trade_date"])
            with JOBS_LOCK:
                JOBS[job_id]["status"] = "done"
                JOBS[job_id]["final_state"] = final_state
                JOBS[job_id]["decision"] = str(decision)
        except Exception as exc:
            with JOBS_LOCK:
                JOBS[job_id]["status"] = "error"
                JOBS[job_id]["error"] = f"{exc}\n{traceback.format_exc(limit=2)}"

    threading.Thread(target=worker, daemon=True).start()
    return job_id


class Handler(BaseHTTPRequestHandler):
    def _write_html(self, content: str, status: int = HTTPStatus.OK) -> None:
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_form(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(length).decode("utf-8", errors="ignore")
        parsed = parse_qs(payload, keep_blank_values=True)
        return {k: v for k, v in parsed.items()}

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "service": "TradingAgents Web UI"}).encode("utf-8"))
            return
        if path == "/api/google-models":
            models = fetch_google_models_live()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(json.dumps({"models": models}, ensure_ascii=False).encode("utf-8"))
            return
        if path.startswith("/api/job/"):
            job_id = path.split("/api/job/", 1)[1].strip()
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if not job:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Job not found"}).encode("utf-8"))
                return
            body = {"status": job.get("status", "running")}
            if job.get("status") == "error":
                body["error"] = job.get("error", "Unknown error")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(json.dumps(body, ensure_ascii=False).encode("utf-8"))
            return
        if path.startswith("/job/"):
            job_id = path.split("/job/", 1)[1].strip()
            self._write_html(render_job_page(job_id))
            return
        if path.startswith("/result/"):
            job_id = path.split("/result/", 1)[1].strip()
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if not job:
                self._write_html(render_form("未找到结果。", error=True), status=404)
                return
            if job.get("status") != "done":
                self._write_html(render_job_page(job_id))
                return
            form_data = dict(job.get("form", {}))
            form_data["_job_id"] = job_id
            self._write_html(render_result(form_data, job["final_state"], job["decision"]))
            return
        if path.startswith("/export/"):
            job_id = path.split("/export/", 1)[1].strip()
            qs = parse_qs(urlparse(self.path).query)
            fmt = (qs.get("fmt", ["md"])[0] or "md").lower()
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if not job or job.get("status") != "done":
                self._write_html(render_form("任务尚未完成，暂时不能导出。", error=True), status=400)
                return

            ticker = str(job.get("form", {}).get("ticker", "UNKNOWN"))
            d = str(job.get("form", {}).get("trade_date", date.today().isoformat()))
            stamp = uuid.uuid4().hex[:8]
            base = f"{ticker}_{d}_{stamp}"
            final_state = job["final_state"]
            decision = job["decision"]

            EXPORT_DIR.mkdir(parents=True, exist_ok=True)
            run_dir = EXPORT_DIR / base
            export_structured_bundle(run_dir, ticker, d, final_state)

            if fmt == "html":
                html_page = render_result({**job.get("form", {}), "_job_id": job_id}, final_state, decision)
                html_path = run_dir / "complete_report.html"
                html_path.write_text(html_page, encoding="utf-8")
                self._write_html(render_form(f"已保存目录: {run_dir}", defaults=job.get("form", {})))
                return

            self._write_html(render_form(f"已保存目录: {run_dir}", defaults=job.get("form", {})))
            return
        self._write_html(render_form())

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/run":
            self._write_html(render_form("不支持的路由。", error=True), status=HTTPStatus.NOT_FOUND)
            return

        form = self._read_form()
        ticker = (form.get("ticker", [""])[0] or "").strip().upper()
        trade_date = (form.get("trade_date", [""])[0] or "").strip()
        provider = (form.get("provider", ["google"])[0] or "google").strip().lower()
        deep_model = (form.get("deep_model", [""])[0] or "").strip()
        quick_model = (form.get("quick_model", [""])[0] or "").strip()
        output_language = (form.get("output_language", ["Chinese"])[0] or "Chinese").strip()
        checkpoint = ((form.get("checkpoint", ["false"])[0] or "false").strip().lower() == "true")
        analysts = [x.strip().lower() for x in form.get("analysts", []) if x.strip()]
        debate_rounds_raw = (form.get("max_debate_rounds", ["1"])[0] or "1").strip()

        defaults = {
            "ticker": ticker,
            "trade_date": trade_date,
            "provider": provider,
            "deep_model": deep_model,
            "quick_model": quick_model,
            "output_language": output_language,
            "checkpoint": checkpoint,
            "analysts": analysts or ANALYSTS,
            "max_debate_rounds": debate_rounds_raw,
        }

        if not ticker or not trade_date:
            self._write_html(render_form("请填写必填项。", error=True, defaults=defaults), status=400)
            return
        try:
            debate_rounds = max(1, min(5, int(debate_rounds_raw)))
        except ValueError:
            debate_rounds = 1
        if not analysts:
            analysts = ANALYSTS
        if not deep_model or not quick_model:
            fallback = MODEL_SUGGESTIONS.get(provider, MODEL_SUGGESTIONS["google"])
            deep_model = deep_model or fallback[0]
            quick_model = quick_model or fallback[1]
            defaults["deep_model"] = deep_model
            defaults["quick_model"] = quick_model

        params = {
            "ticker": ticker,
            "trade_date": trade_date,
            "provider": provider,
            "deep_model": deep_model,
            "quick_model": quick_model,
            "output_language": output_language,
            "checkpoint": checkpoint,
            "debate_rounds": debate_rounds,
            "analysts": analysts,
        }
        job_id = start_job(defaults, params)
        self.send_response(303)
        self.send_header("Location", f"/job/{job_id}")
        self.end_headers()


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"TradingAgents Web UI: http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
