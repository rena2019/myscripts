#!/usr/bin/env python3

# uvx --with pillow --with requests --with timm --with torch --with transformers python image2text.py <image> --language de

import argparse
import io
import os
import sys
import warnings
from pathlib import Path
from urllib.parse import urlparse
_DEBUG = True

# Disable progress bars before the transformers import
# (can be re-enabled via env: HF_HUB_DISABLE_PROGRESS_BARS=0).
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1" if _DEBUG else "0")

import requests
import torch
from PIL import Image
from transformers import (
    AutoModelForCausalLM,
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
)

try:
    from transformers.utils import logging as hf_logging
    hf_logging.set_verbosity_error()
    try:
        hf_logging.disable_progress_bar()
    except Exception:
        pass
except Exception:
    pass

if not(_DEBUG):
    # Specifically suppress the unauthenticated-request warning from the HF Hub –
    # for higher rate limits, set HF_TOKEN (see note in main).
    warnings.filterwarnings(
        "ignore",
        message=".*unauthenticated requests.*",
    )


FASTVLM_ID = "apple/FastVLM-0.5B"
TRANSLATION_MODEL_ID = "facebook/nllb-200-distilled-600M"
IMAGE_TOKEN_INDEX = -200

# NLLB language codes for possible target languages
LANGUAGES = {
    "en": ("English", None),
    "de": ("German", "deu_Latn"),
    "fr": ("French", "fra_Latn"),
    "es": ("Spanish", "spa_Latn"),
    "it": ("Italian", "ita_Latn"),
    "pt": ("Portuguese", "por_Latn"),
    "nl": ("Dutch", "nld_Latn"),
    "ja": ("Japanese", "jpn_Jpan"),
    "zh": ("Chinese", "zho_Hans"),
    "ko": ("Korean", "kor_Hang"),
    "ru": ("Russian", "rus_Cyrl"),
}


def load_image(source: str) -> Image.Image:
    """Loads an image from a local path or an HTTP(S) URL."""
    if urlparse(source).scheme in ("http", "https"):
        response = requests.get(source, timeout=30)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content)).convert("RGB")

    path = Path(source).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Image file not found: {path}")
    return Image.open(path).convert("RGB")


def translate_caption(text: str, language: str) -> str:
    """Translates the English image caption into the selected language."""
    language_name, target_code = LANGUAGES[language]

    if target_code is None:
        return text

    print(f"Translating to {language_name} …", file=__import__("sys").stderr)

    tokenizer = AutoTokenizer.from_pretrained(
        TRANSLATION_MODEL_ID,
        src_lang="eng_Latn",
    )
    model = AutoModelForSeq2SeqLM.from_pretrained(TRANSLATION_MODEL_ID)
    model.eval()

    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=512,
    )

    with torch.inference_mode():
        translated_ids = model.generate(
            **inputs,
            forced_bos_token_id=tokenizer.convert_tokens_to_ids(target_code),
            max_new_tokens=48, # 200 is too long? -> only short answer
        )
    return tokenizer.decode(translated_ids[0], skip_special_tokens=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Image Captioning with Apple FastVLM-0.5B and facebook/nllb-200-distilled-600M"
    )
    parser.add_argument(
        "image",
        help="Path to an image file or HTTP(S) URL",
    )
    parser.add_argument(
        "--language",
        choices=LANGUAGES.keys(),
        default="en",
        help="Output language (default: en)",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=128,
        help="Maximum length of the English image description",
    )
    args = parser.parse_args()

    image = load_image(args.image)

    use_cuda = torch.cuda.is_available()
    dtype = torch.float16 if use_cuda else torch.float32

    tokenizer = AutoTokenizer.from_pretrained(
        FASTVLM_ID,
        trust_remote_code=True,
    )
    try:
        model = AutoModelForCausalLM.from_pretrained(
            FASTVLM_ID,
            dtype=dtype,
            device_map="auto" if use_cuda else None,
            trust_remote_code=True,
        )
    except TypeError:
        # Fallback for older transformers versions (< ~4.46)
        model = AutoModelForCausalLM.from_pretrained(
            FASTVLM_ID,
            torch_dtype=dtype,
            device_map="auto" if use_cuda else None,
            trust_remote_code=True,
        )
    if not use_cuda:
        model = model.to("cpu")
    model.eval()

    # Always prompt FastVLM in English.
    messages = [{
        "role": "user",
        "content": (
            "<image>\n"
            "Describe the image clearly and concisely in English in a maximum of 2–3 sentences."
        ),
    }]
    rendered = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=False,
    )

    before, after = rendered.split("<image>", 1)
    before_ids = tokenizer(
        before,
        return_tensors="pt",
        add_special_tokens=False,
    ).input_ids
    after_ids = tokenizer(
        after,
        return_tensors="pt",
        add_special_tokens=False,
    ).input_ids

    image_token = torch.tensor(
        [[IMAGE_TOKEN_INDEX]],
        dtype=before_ids.dtype,
    )
    input_ids = torch.cat([before_ids, image_token, after_ids], dim=1)
    input_ids = input_ids.to(model.device)
    attention_mask = torch.ones_like(input_ids)

    image_processor = model.get_vision_tower().image_processor
    pixel_values = image_processor(
        images=image,
        return_tensors="pt",
    )["pixel_values"].to(device=model.device, dtype=model.dtype)

    with torch.inference_mode():
        output_ids = model.generate(
            inputs=input_ids,
            attention_mask=attention_mask,
            images=pixel_values,
            max_new_tokens=args.max_new_tokens,
        )

    # Decode only the newly generated response tokens.
    new_tokens = output_ids[0, input_ids.shape[1]:]
    english_caption = tokenizer.decode(
        new_tokens,
        skip_special_tokens=True,
    ).strip()

    if not english_caption:
        raise RuntimeError(
            "FastVLM did not produce any text. "
            "Check model version and Transformers compatibility."
        )
    print("en\n", english_caption)
    if (args.language != "en"):
        result = translate_caption(english_caption, args.language)
        print(result)

if __name__ == "__main__":
    main()
