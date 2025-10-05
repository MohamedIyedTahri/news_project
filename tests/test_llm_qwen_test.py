import os
import sys
import types
import pytest

# Ensure the repository root is on sys.path so tests can import the local package
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import torch

from newsbot import llm_qwen


class FakeTokenizer:
    def __init__(self):
        self.eos_token_id = 2
        self.pad_token_id = 0
        self.eos_token = "<eos>"
        self.pad_token = "<pad>"

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        # Simple concatenation used as the prompt
        return "\n".join(m["content"] for m in messages)

    def __call__(self, prompt, return_tensors=None):
        # Return simple tensor ids for input ids and attention mask
        # We'll encode each character as its ordinal mod 100 to keep small
        ids = [ord(c) % 100 for c in prompt][:64]
        input_ids = torch.tensor([ids], dtype=torch.long)
        attention_mask = torch.ones_like(input_ids)
        return {"input_ids": input_ids, "attention_mask": attention_mask}

    def decode(self, token_ids, skip_special_tokens=True):
        # token_ids is a list/iterable of ints; map back to letters for test
        return "decoded:" + "".join(chr((int(t) % 26) + 97) for t in token_ids)


class FakeModel:
    def __init__(self, device=torch.device("cpu")):
        self._device = device

    def parameters(self):
        # return a dummy param on CPU device as a generator so `next()` works
        p = torch.nn.Parameter(torch.tensor([1.0], device=self._device))
        yield p

    def generate(self, **kwargs):
        # emulate generation by returning a tensor of ids appended to input
        input_ids = kwargs.get("input_ids")
        batch = input_ids.shape[0]
        seq_len = input_ids.shape[1]
        # produce 8 new tokens with deterministic small integers
        new = torch.tensor([[1, 2, 3, 4, 5, 6, 7, 8]], dtype=torch.long)
        return torch.cat([input_ids, new], dim=1)

    def eval(self):
        return self


def fake_load_components():
    return FakeModel(), FakeTokenizer()


def test_summarize_text_happy_path(monkeypatch):
    # Replace heavy loader with the fake one
    monkeypatch.setattr(llm_qwen, "_load_components", fake_load_components)

    text = "This is a short test article about testing."
    summary = llm_qwen.summarize_text(text, max_tokens=16, temperature=0.0)
    assert isinstance(summary, str)
    assert summary.startswith("decoded:")


@pytest.mark.parametrize("bad_text", ["", "   \n\t "])
def test_summarize_text_validates_input(bad_text):
    with pytest.raises(ValueError):
        llm_qwen.summarize_text(bad_text)


def test_summarize_text_invalid_max_tokens():
    with pytest.raises(ValueError):
        llm_qwen.summarize_text("valid text", max_tokens=0)
