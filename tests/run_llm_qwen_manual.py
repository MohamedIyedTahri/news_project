"""Manual test runner for llm_qwen.summarize_text without pytest dependency.

Runs a few lightweight checks by monkeypatching the heavy model loader.
"""
import sys
import os
import sys
import torch

# Ensure the repository root is on sys.path so the manual runner can import the package
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from newsbot import llm_qwen


class FakeTokenizer:
    def __init__(self):
        self.eos_token_id = 2
        self.pad_token_id = 0
        self.eos_token = "<eos>"
        self.pad_token = "<pad>"

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        return "\n".join(m["content"] for m in messages)

    def __call__(self, prompt, return_tensors=None):
        ids = [ord(c) % 100 for c in prompt][:64]
        input_ids = torch.tensor([ids], dtype=torch.long)
        attention_mask = torch.ones_like(input_ids)
        return {"input_ids": input_ids, "attention_mask": attention_mask}

    def decode(self, token_ids, skip_special_tokens=True):
        return "decoded:" + "".join(chr((int(t) % 26) + 97) for t in token_ids)


class FakeModel:
    def __init__(self, device=torch.device("cpu")):
        self._device = device

    def parameters(self):
        p = torch.nn.Parameter(torch.tensor([1.0], device=self._device))
        yield p

    def generate(self, **kwargs):
        input_ids = kwargs.get("input_ids")
        new = torch.tensor([[1, 2, 3, 4, 5, 6, 7, 8]], dtype=torch.long)
        return torch.cat([input_ids, new], dim=1)

    def eval(self):
        return self


def fake_load_components():
    return FakeModel(), FakeTokenizer()


def run_tests():
    llm_qwen._load_components = fake_load_components

    failures = 0

    # Happy path
    try:
        summary = llm_qwen.summarize_text("This is a test article.", max_tokens=16, temperature=0.0)
        assert isinstance(summary, str) and summary.startswith("decoded:"), "Unexpected summary"
        print("PASS: happy path")
    except Exception as e:
        print("FAIL: happy path ->", e)
        failures += 1

    # Empty text validation
    for bad in ["", "   \n\t "]:
        try:
            llm_qwen.summarize_text(bad)
            print("FAIL: empty text did not raise")
            failures += 1
        except ValueError:
            print("PASS: empty text validation")
        except Exception as e:
            print("FAIL: empty text unexpected ->", e)
            failures += 1

    # Invalid max_tokens
    try:
        llm_qwen.summarize_text("valid", max_tokens=0)
        print("FAIL: invalid max_tokens did not raise")
        failures += 1
    except ValueError:
        print("PASS: max_tokens validation")
    except Exception as e:
        print("FAIL: max_tokens unexpected ->", e)
        failures += 1

    if failures:
        print(f"{failures} test(s) failed")
        sys.exit(2)
    print("All manual tests passed")


if __name__ == "__main__":
    run_tests()
