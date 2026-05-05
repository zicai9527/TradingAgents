from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run TradingAgents analysis without interactive prompts.")
    p.add_argument("--ticker", required=True, help="Ticker, e.g. NVDA or 7974.T")
    p.add_argument("--trade-date", required=True, help="Trade date in YYYY-MM-DD")
    p.add_argument("--provider", default="google", help="LLM provider")
    p.add_argument("--deep-model", default="", help="Deep model name")
    p.add_argument("--quick-model", default="", help="Quick model name")
    p.add_argument("--output-language", default="Chinese", help="Output language")
    p.add_argument("--research-depth", type=int, default=1, help="Debate depth (1-5)")
    p.add_argument(
        "--analysts",
        default="market,social,news,fundamentals",
        help="Comma-separated analyst keys",
    )
    p.add_argument("--checkpoint", action="store_true", help="Enable checkpoint resume")
    p.add_argument("--clear-checkpoints", action="store_true", help="Clear all checkpoints before run")
    p.add_argument("--google-thinking-level", default="", help="Google thinking level")
    p.add_argument("--openai-reasoning-effort", default="", help="OpenAI reasoning effort")
    p.add_argument("--anthropic-effort", default="", help="Anthropic effort")
    p.add_argument("--backend-url", default="", help="Optional provider backend URL")
    return p.parse_args()


def choose_default_models(provider: str) -> tuple[str, str]:
    provider = provider.lower()
    if provider == "google":
        return "gemini-3.1-pro-preview", "gemini-3-flash-preview"
    if provider == "openai":
        return "gpt-5.4", "gpt-5.4-mini"
    if provider == "anthropic":
        return "claude-sonnet-4-6", "claude-haiku-4-5"
    return "gpt-5.4", "gpt-5.4-mini"


def main() -> None:
    load_dotenv()
    load_dotenv(".env.enterprise", override=False)
    args = parse_args()

    provider = args.provider.strip().lower()
    deep_default, quick_default = choose_default_models(provider)
    deep_model = args.deep_model.strip() or deep_default
    quick_model = args.quick_model.strip() or quick_default
    depth = max(1, min(5, int(args.research_depth)))
    analysts = [x.strip().lower() for x in args.analysts.split(",") if x.strip()]
    if not analysts:
        analysts = ["market", "social", "news", "fundamentals"]

    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = provider
    config["deep_think_llm"] = deep_model
    config["quick_think_llm"] = quick_model
    config["output_language"] = args.output_language.strip() or "Chinese"
    config["checkpoint_enabled"] = bool(args.checkpoint)
    config["max_debate_rounds"] = depth
    config["max_risk_discuss_rounds"] = depth

    if args.backend_url.strip():
        config["backend_url"] = args.backend_url.strip()
    if args.google_thinking_level.strip():
        config["google_thinking_level"] = args.google_thinking_level.strip()
    if args.openai_reasoning_effort.strip():
        config["openai_reasoning_effort"] = args.openai_reasoning_effort.strip()
    if args.anthropic_effort.strip():
        config["anthropic_effort"] = args.anthropic_effort.strip()

    if args.clear_checkpoints:
        from tradingagents.graph.checkpointer import clear_all_checkpoints

        n = clear_all_checkpoints(config["data_cache_dir"])
        print(f"[checkpoint] Cleared {n} checkpoint(s).")

    print("=== TradingAgents Non-Interactive Run ===")
    print(f"ticker={args.ticker} date={args.trade_date}")
    print(f"provider={provider} deep={deep_model} quick={quick_model}")
    print(f"analysts={','.join(analysts)} depth={depth} checkpoint={config['checkpoint_enabled']}")

    ta = TradingAgentsGraph(selected_analysts=analysts, debug=False, config=config)
    final_state, decision = ta.propagate(args.ticker.strip().upper(), args.trade_date.strip())

    print("\n=== Final Decision ===")
    print(decision)
    print("\n=== Final Trade Decision (raw) ===")
    print(final_state.get("final_trade_decision", ""))
    print("\nState log written under:")
    safe_ticker = args.ticker.strip().upper()
    print(Path(config["results_dir"]) / safe_ticker / "TradingAgentsStrategy_logs")


if __name__ == "__main__":
    main()
