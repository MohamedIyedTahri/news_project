"""Utilities for running summaries with the Qwen2.5-7B-Instruct model.

This module provides a single ``summarize_text`` function that lazily loads the
Hugging Face model the first time it is used. The heavy model objects are kept in
module-level globals so repeated calls reuse the same resources. GPU hardware is
used automatically when available. If ``bitsandbytes`` is installed and a CUDA
GPU is present, the model is loaded in 4-bit precision to reduce VRAM usage.
"""
from __future__ import annotations

import logging
import os
from typing import Optional, Tuple

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

logger = logging.getLogger(__name__)

# Allow overriding the exact model repo or a local path via env var. If unset,
# we'll try a few common Qwen 2.5 repo name variants so users who have slightly
# different naming still get the intended model. If you want to force a local
# directory, set QWEN_LOCAL_PATH. To allow the lightweight fake model (useful
# for CI or offline tests) set QWEN_ALLOW_FAKE=1.
MODEL_NAME = os.environ.get("QWEN_MODEL_NAME")
QWEN_LOCAL_PATH = os.environ.get("QWEN_LOCAL_PATH")
QWEN_ALLOW_FAKE = os.environ.get("QWEN_ALLOW_FAKE", "0") in ("1", "true", "True")

# Candidate Hugging Face identifiers (try in order) when no explicit model name
# or local path is provided. These are all 2.5B variants; adjust if you have a
# different sanctioned repo name.
CANDIDATE_MODEL_IDS = [
    "Qwen/Qwen2.5B-Instruct",
    "Qwen/Qwen-2.5B-Instruct",
    "qwen/qwen-2.5b-instruct",
    "Qwen/qwen-2.5b",
]
DEFAULT_MAX_TOKENS = 200
SYSTEM_PROMPT = "You are an expert news editor. Summarize articles accurately and concisely."

_model = None
_tokenizer = None

try:  # bitsandbytes is optional but recommended on NVIDIA GPUs
    import bitsandbytes  # type: ignore  # noqa: F401

    BITSANDBYTES_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    BITSANDBYTES_AVAILABLE = False

try:  # accelerate enables device_map="auto" usage
    import accelerate  # type: ignore  # noqa: F401

    ACCELERATE_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    ACCELERATE_AVAILABLE = False


def _load_components() -> Tuple[AutoModelForCausalLM, AutoTokenizer]:
    """Lazily load the tokenizer and model, reusing cached instances."""
    global _model, _tokenizer
    if _model is not None and _tokenizer is not None:
        return _model, _tokenizer

    logger.info("Loading Qwen model %s", MODEL_NAME)
    is_cuda = torch.cuda.is_available()
    torch_dtype = torch.float16 if is_cuda else torch.float32

    model_kwargs = {
        "trust_remote_code": True,
        "torch_dtype": torch_dtype,
    }

    load_quantized = is_cuda and BITSANDBYTES_AVAILABLE and ACCELERATE_AVAILABLE

    if load_quantized:
        logger.info("Using 4-bit quantization via bitsandbytes for Qwen model")
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
        )
        model_kwargs["quantization_config"] = quantization_config
        model_kwargs["device_map"] = "auto"
    else:
        if not is_cuda:
            logger.warning(
                "CUDA GPU not detected. Loading Qwen model on CPU; this will be slow."
            )
        else:
            if not BITSANDBYTES_AVAILABLE:
                logger.info("bitsandbytes not available; using full-precision weights on GPU.")
            if not ACCELERATE_AVAILABLE:
                logger.info(
                    "accelerate not installed; falling back to manual GPU placement. "
                    "Install accelerate for best performance."
                )

    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")

    def _try_load_from(name: str):
        """Try loading tokenizer+model for a single name; return tuple or raise."""
        logger.info("Attempting to load Qwen model '%s'", name)
        tokenizer = AutoTokenizer.from_pretrained(name, trust_remote_code=True, use_auth_token=hf_token)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(name, use_auth_token=hf_token, **model_kwargs)
        if is_cuda and not load_quantized:
            model.to("cuda")
        model.eval()
        return model, tokenizer

    # Determine the list of targets to try
    targets = []
    if QWEN_LOCAL_PATH:
        targets.append(QWEN_LOCAL_PATH)
    if MODEL_NAME:
        targets.append(MODEL_NAME)
    # Only extend with candidates if user didn't explicitly set a model name
    if not MODEL_NAME and not QWEN_LOCAL_PATH:
        targets.extend(CANDIDATE_MODEL_IDS)

    last_exc: Optional[Exception] = None
    for candidate in targets:
        try:
            model, tokenizer = _try_load_from(candidate)
            _model = model
            _tokenizer = tokenizer
            return model, tokenizer
        except Exception as exc:  # pragma: no cover - gated/offline handling
            logger.warning("Loading candidate '%s' failed: %s", candidate, exc)
            last_exc = exc

    # If we reach here, no candidate loaded successfully.
    err_msg = (
        "Could not load any Qwen 2.5 model. Tried: %s. "
        "Set QWEN_LOCAL_PATH to a local model directory, set QWEN_MODEL_NAME to a valid "
        "Hugging Face repo id for Qwen 2.5, and/or set HF_TOKEN (or HUGGINGFACE_TOKEN) "
        "in your environment if the repo is gated. If you want to continue with a "
        "lightweight fake model for testing, set QWEN_ALLOW_FAKE=1."
    ) % (targets,)
    logger.error(err_msg)

    if not QWEN_ALLOW_FAKE:
        # Surface a helpful error rather than silently falling back to a fake model
        raise RuntimeError(err_msg) from last_exc

    logger.warning("QWEN_ALLOW_FAKE set; creating a lightweight fake model for local testing.")

    # Lightweight fake tokenizer and model for safe local operation
    class FakeTokenizer:
        def __init__(self):
            self.eos_token_id = 2
            self.pad_token_id = 0
            self.eos_token = "<eos>"
            self.pad_token = "<pad>"

        def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
            return "\n".join(m["content"] for m in messages)

        def __call__(self, prompt, return_tensors=None):
            import torch as _torch

            ids = [ord(c) % 100 for c in prompt][:64]
            input_ids = _torch.tensor([ids], dtype=_torch.long)
            attention_mask = _torch.ones_like(input_ids)
            return {"input_ids": input_ids, "attention_mask": attention_mask}

        def decode(self, token_ids, skip_special_tokens=True):
            return "[FAKE] " + "".join(chr((int(t) % 26) + 97) for t in token_ids)

    class FakeModel:
        def __init__(self):
            import torch as _torch

            self._param = _torch.nn.Parameter(_torch.tensor([1.0]))

        def parameters(self):
            # yield a parameter so `next()` works as in real models
            yield self._param

        def generate(self, **kwargs):
            # Return input_ids with a small deterministic appended sequence
            input_ids = kwargs.get("input_ids")
            import torch as _torch

            new = _torch.tensor([[1, 2, 3, 4, 5, 6, 7, 8]], dtype=_torch.long)
            return _torch.cat([input_ids, new], dim=1)

        def eval(self):
            return self

    _tokenizer = FakeTokenizer()
    _model = FakeModel()
    return _model, _tokenizer
    


def summarize_text(text: str, max_tokens: int = DEFAULT_MAX_TOKENS, *, temperature: float = 0.7) -> str:
    """Generate a concise summary for the provided article text.

    Args:
        text: Raw article text to summarize.
        max_tokens: Maximum number of new tokens to generate.
        temperature: Sampling temperature for generation.

    Returns:
        Summary string produced by Qwen.
    """
    if not text or not text.strip():
        raise ValueError("text must be a non-empty string")
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")

    model, tokenizer = _load_components()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Summarize the following news article in a few sentences, highlighting key facts "
                "and maintaining neutrality:\n\n" + text.strip()
            ),
        },
    ]

    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt")

    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=temperature,
            top_p=0.9,
            do_sample=True,
            eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.pad_token_id,
        )

    generated_tokens = output_ids[0][inputs["input_ids"].shape[-1]:]
    summary = tokenizer.decode(generated_tokens, skip_special_tokens=True)
    return summary.strip()


if __name__ == "__main__":  # pragma: no cover - convenience entry point
    example_text = "Your news article text goes here..."
    try:
        result = summarize_text(example_text)
        print(result)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Failed to summarize example text: %s", exc)
        raise
