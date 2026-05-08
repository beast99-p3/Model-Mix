"""
Model Mix — multi-model debate, single output.

Usage:
  pip install -r requirements.txt
  copy .env.example .env   # add OPENAI_API_KEY (and optionally ANTHROPIC_API_KEY)
  python main.py "Your question here"

Optional:
  python main.py "Your question" --show-debate

Web UI:
  python -m uvicorn server:app --reload --host 127.0.0.1 --port 8000
  Open http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import sys

from src.debate import run_debate


def main() -> None:
    parser = argparse.ArgumentParser(description="Debate across models → one answer")
    parser.add_argument("question", nargs="?", help="Question to answer")
    parser.add_argument(
        "--show-debate",
        action="store_true",
        help="Print internal rounds before the final answer",
    )
    args = parser.parse_args()

    q = args.question
    if not q and not sys.stdin.isatty():
        q = sys.stdin.read().strip()
    if not q:
        parser.print_help()
        sys.exit(1)

    result = run_debate(q)

    if args.show_debate:
        for t in result.transcript:
            print(f"\n--- {t.round_name} / {t.debater_id} ---\n")
            print(t.text)
        print("\n" + "=" * 48 + "\n")
        print("FINAL ANSWER\n")

    print(result.final_answer)


if __name__ == "__main__":
    main()
