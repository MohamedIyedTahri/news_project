#!/usr/bin/env python3
"""Interactive CLI for calling newsbot.llm_qwen.summarize_text.

Runs a REPL where you can paste article text and get back a summary.
Use --fake to force a lightweight fake summarizer (no model downloads).
"""
import argparse
import sys
import os


def main(argv=None):
    parser = argparse.ArgumentParser(description="Interactive LLM summarizer for newsbot")
    parser.add_argument("--fake", action="store_true", help="Use a fake summarizer (fast, local)")
    parser.add_argument("--max-tokens", type=int, default=200, help="Max tokens for generation")
    args = parser.parse_args(argv)

    # Ensure repo root is importable
    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    if args.fake:
        # lightweight fake summarize_text implemented inline to avoid heavy deps
        def summarize_text(text, max_tokens=200, temperature=0.7):
            if not text or not text.strip():
                raise ValueError("text must be a non-empty string")
            # Very small deterministic fake summary
            head = text.strip().split("\n")[0][:200]
            return f"[FAKE SUMMARY] {head[:min(120, len(head))]}..."
    else:
        try:
            from newsbot.llm_qwen import summarize_text
        except Exception as exc:
            print("Failed to import real summarizer:", exc)
            print("Run with --fake to use the local fake summarizer instead.")
            return 2

    print("Interactive LLM summarizer. Paste article text, then a blank line to summarize. Ctrl-C or Ctrl-D to quit.")
    buffer_lines = []
    try:
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip() == "":
                text = "\n".join(buffer_lines).strip()
                buffer_lines = []
                if not text:
                    continue
                try:
                    summary = summarize_text(text, max_tokens=args.max_tokens)
                except Exception as exc:
                    print("Error during summarization:", exc)
                    continue
                print("\n=== Summary ===\n")
                print(summary)
                print("\n--- End Summary ---\n")
            else:
                buffer_lines.append(line)
    except KeyboardInterrupt:
        print("\nExiting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
