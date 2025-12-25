import os
import json
from typing import List, Dict

import requests

from services.prompt import BASE_PROMPT, JSON_SCHEMA_INSTRUCTION


def analyze_reviews_with_llm(reviews: List[Dict], custom_prompt: str = "") -> Dict:
    provider = os.environ.get("LLM_PROVIDER", "openai").lower()

    prompt = BASE_PROMPT
    if custom_prompt.strip():
        prompt = custom_prompt.strip()

    joined_reviews = "\n".join([f"- {r.get('review_text','')}" for r in reviews if r.get("review_text")])

    if provider == "openai":
        return _analyze_openai(prompt=prompt, reviews_text=joined_reviews)

    if provider == "gemini":
        return _analyze_gemini(prompt=prompt, reviews_text=joined_reviews)

    raise ValueError("LLM_PROVIDER must be 'openai' or 'gemini'")


def _analyze_openai(prompt: str, reviews_text: str) -> Dict:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    if not api_key:
        raise ValueError("Missing OPENAI_API_KEY")

    url = f"{base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 8192,
        "messages": [
            {"role": "system", "content": prompt + "\n\n" + JSON_SCHEMA_INSTRUCTION},
            {"role": "user", "content": f"ОТЗЫВЫ:\n{reviews_text}"},
        ],
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=180)
    resp.raise_for_status()

    content = resp.json()["choices"][0]["message"]["content"]
    return _safe_json(content)


def _analyze_gemini(prompt: str, reviews_text: str) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    model = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
        f"?key={api_key}"
    )

    # Build the full prompt - emphasize Russian output
    full_prompt = f"""{prompt}

{JSON_SCHEMA_INSTRUCTION}

---
ОТЗЫВЫ ДЛЯ АНАЛИЗА:
{reviews_text}
---

Проанализируй отзывы выше и верни JSON на РУССКОМ языке. Не обрезай ответ!
"""

    # Build generation config based on model
    gen_config = {
        "temperature": 0.2,
        "maxOutputTokens": 16384,
    }

    # Try to use JSON mode for supported models
    if "1.5" in model or "2.0" in model:
        gen_config["responseMimeType"] = "application/json"

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": full_prompt}],
            }
        ],
        "generationConfig": gen_config,
    }

    resp = requests.post(url, json=payload, timeout=300)

    # If JSON mode fails, retry without it
    if resp.status_code == 400 and "responseMimeType" in gen_config:
        del gen_config["responseMimeType"]
        payload["generationConfig"] = gen_config
        resp = requests.post(url, json=payload, timeout=300)

    resp.raise_for_status()

    data = resp.json()

    # Check for finish reason
    finish_reason = None
    try:
        finish_reason = data.get("candidates", [{}])[0].get("finishReason", "")
    except (KeyError, IndexError):
        pass

    # Extract text
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        return {
            "raw_output": str(data),
            "error": "Could not extract text from Gemini response",
            "finish_reason": finish_reason
        }

    result = _safe_json(text)

    # Add warning if truncated
    if finish_reason and finish_reason not in ["STOP", "END_TURN", "FINISH"]:
        result["_warning"] = f"Response may be incomplete (finishReason: {finish_reason})"

    return result


def _safe_json(text: str) -> Dict:
    text = text.strip()

    # Remove markdown code block wrapper if present
    if text.startswith("```"):
        lines = text.split("\n")
        json_lines = []
        in_json = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```") and not in_json:
                in_json = True
                continue
            elif stripped == "```":
                break
            elif in_json:
                json_lines.append(line)
        text = "\n".join(json_lines)

    # Try to parse JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # Try to fix truncated JSON
        fixed_text = _try_fix_json(text)
        if fixed_text:
            try:
                return json.loads(fixed_text)
            except json.JSONDecodeError:
                pass

        # Return raw with error info
        return {
            "raw_output": text,
            "parse_error": str(e),
            "error_position": e.pos if hasattr(e, 'pos') else None
        }


def _try_fix_json(text: str) -> str:
    """Attempt to fix truncated or malformed JSON."""
    if not text:
        return None

    text = text.strip()

    # Count braces/brackets
    open_braces = text.count('{')
    close_braces = text.count('}')
    open_brackets = text.count('[')
    close_brackets = text.count(']')

    # If unbalanced, try to close
    if open_braces > close_braces or open_brackets > close_brackets:
        # Check if we're in middle of a string
        in_string = False
        escape_next = False
        last_good_pos = 0

        for i, char in enumerate(text):
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
            if not in_string and char in ',]}':
                last_good_pos = i + 1

        # Truncate at last good position if needed
        if in_string and last_good_pos > 0:
            text = text[:last_good_pos]

        # Re-count after potential truncation
        open_braces = text.count('{')
        close_braces = text.count('}')
        open_brackets = text.count('[')
        close_brackets = text.count(']')

        # Add missing closures
        missing_brackets = ']' * (open_brackets - close_brackets)
        missing_braces = '}' * (open_braces - close_braces)

        return text.rstrip(',') + missing_brackets + missing_braces

    return None
