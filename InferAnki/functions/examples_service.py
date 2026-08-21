"""Background-safe standalone Examples orchestration."""

import html
import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional


class ExamplesPipelineError(RuntimeError):
    """Stop Examples generation before an Anki note is mutated."""


_BR_TAG = r"<br\s*/?>"


def normalize_blank_lines_html(field_html: str) -> str:
    """Collapse every HTML blank-line run to exactly two break tags."""
    normalized = re.sub(
        rf"{_BR_TAG}(?P<closing>(?:\s*</(?:b|i)>)+)",
        rf"\g<closing><br>",
        field_html,
        flags=re.IGNORECASE,
    )
    return re.sub(
        rf"(?:{_BR_TAG}(?:\s|&nbsp;|&#160;)*){{2,}}",
        "<br><br>",
        normalized,
        flags=re.IGNORECASE,
    )


def extract_source_phrase_html(field_html: str) -> str:
    """Return only the source phrase before generated examples."""
    normalized = normalize_blank_lines_html(field_html)
    source = re.split(
        rf"{_BR_TAG}\s*{_BR_TAG}",
        normalized,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return re.sub(
        rf"(?:{_BR_TAG}\s*)+$",
        "",
        source,
        flags=re.IGNORECASE,
    ).strip()


def is_html_field_empty(field_html: str) -> bool:
    """Return whether an Anki HTML field has no visible text."""
    visible = re.sub(r"<[^>]+>", "", html.unescape(field_html or ""))
    return not visible.replace("\xa0", " ").strip()


def join_source_and_examples(source_html: str, examples_html: str) -> str:
    """Join source and examples with exactly one blank line."""
    combined = f"{source_html}<br><br>{examples_html}"
    return normalize_blank_lines_html(combined)


def normalize_examples_response(text: str) -> str:
    """Remove blank lines while preserving one sentence per line."""
    if not text:
        return ""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(
        line.strip() for line in normalized.split("\n") if line.strip()
    )


def translate_source_phrase(
    analyzer: Any,
    config: Dict[str, Any],
    source_html: str,
) -> str:
    """Translate one Norwegian source phrase for the first Anki field."""
    prompt = analyzer.prompts.get("examples_source_translation", {})
    if not prompt:
        raise ExamplesPipelineError("Examples source translation prompt not found")

    target_language = config.get("field_1_response_lang", "English")
    source_phrase = extract_source_phrase_html(source_html)
    messages = [
        {
            "role": "system",
            "content": prompt.get("system_message", "").format(
                target_language=target_language,
            ),
        },
        {
            "role": "user",
            "content": prompt.get("user_template", "").format(
                source_phrase=source_phrase,
                target_language=target_language,
            ),
        },
    ]
    api_settings = prompt.get("api_settings", {})
    response, _usage = analyzer.openai_client.request_with_messages(
        messages,
        custom_model=api_settings.get(
            "model",
            config.get("openai_default_model", analyzer.openai_client.model),
        ),
        custom_temperature=api_settings.get("temperature"),
        custom_max_tokens=(
            api_settings.get("max_completion_tokens")
            or api_settings.get("max_tokens", analyzer.openai_client.max_tokens)
        ),
        response_format=api_settings.get("response_format"),
        custom_reasoning_effort=api_settings.get("reasoning_effort"),
        custom_verbosity=api_settings.get("verbosity"),
    )
    analyzer._log_api_call(
        {
            "system_message": messages[0]["content"],
            "user_message": messages[1]["content"],
            "api_settings": api_settings,
        },
        response,
        "EXAMPLES_SOURCE_TRANSLATION",
    )
    try:
        translation = json.loads(response).get("translation", "").strip()
    except (AttributeError, json.JSONDecodeError, TypeError) as error:
        raise ExamplesPipelineError("Invalid source translation response") from error
    if not translation or "\n" in translation or re.search(_BR_TAG, translation, re.I):
        raise ExamplesPipelineError("Source translation must be one non-empty line")
    unsupported_tags = re.sub(r"</?i>", "", translation, flags=re.IGNORECASE)
    if re.search(r"<[^>]+>", unsupported_tags):
        raise ExamplesPipelineError("Source translation contains unsupported HTML")
    return translation


def build_examples_card_payload(
    analyzer: Any,
    config: Dict[str, Any],
    content: str,
    custom_instructions: Optional[str] = None,
    progress: Optional[Callable[[str], None]] = None,
    include_translation: bool = False,
) -> Dict[str, Optional[str]]:
    """Build Examples output and an optional source translation in parallel."""
    if not include_translation:
        return {
            "examples": build_examples_payload(
                analyzer,
                config,
                content,
                custom_instructions,
                progress,
            ),
            "translation": None,
        }
    with ThreadPoolExecutor(max_workers=2) as executor:
        examples_future = executor.submit(
            build_examples_payload,
            analyzer,
            config,
            content,
            custom_instructions,
            progress,
        )
        translation_future = executor.submit(
            translate_source_phrase,
            analyzer,
            config,
            content,
        )
        return {
            "examples": examples_future.result(),
            "translation": translation_future.result(),
        }


def build_examples_payload(
    analyzer: Any,
    config: Dict[str, Any],
    content: str,
    custom_instructions: Optional[str] = None,
    progress: Optional[Callable[[str], None]] = None,
) -> str:
    """Generate, review, render, and verify standalone examples."""
    def report(label: str) -> None:
        if progress:
            progress(label)

    if analyzer is None:
        raise ExamplesPipelineError("CardCraft AI not available")
    api_key = config.get("openai_api_key", "")
    if not api_key or api_key == "YOUR_OPENAI_API_KEY_HERE":
        raise ExamplesPipelineError("OpenAI API key not configured")

    prompt = analyzer.prompts.get("norwegian_examples_from_content", {})
    if not prompt:
        raise ExamplesPipelineError("Examples prompt not found in prompts.json")

    user_context = prompt.get("user_context", [])
    user_message = prompt.get("user_template", "").format(
        content=content,
        user_context=user_context,
    )
    if custom_instructions:
        user_message += f"\n\nADDITIONAL INSTRUCTIONS: {custom_instructions}"

    system_message = prompt.get("system_message", "")
    api_settings = prompt.get("api_settings", {})
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message},
    ]
    report("Creating Examples")
    response, _usage = analyzer.openai_client.request_with_messages(
        messages,
        custom_model=api_settings.get(
            "model",
            config.get("openai_draft_model", analyzer.openai_client.model),
        ),
        custom_temperature=api_settings.get("temperature"),
        custom_max_tokens=(
            api_settings.get("max_completion_tokens")
            or api_settings.get("max_tokens", analyzer.openai_client.max_tokens)
        ),
        response_format=api_settings.get("response_format"),
        custom_reasoning_effort=api_settings.get("reasoning_effort"),
        custom_verbosity=api_settings.get("verbosity"),
    )
    analyzer._log_api_call(
        {
            "system_message": system_message,
            "user_message": user_message,
            "api_settings": api_settings,
        },
        response,
        "EXAMPLES_FROM_CONTENT",
    )
    if not response:
        raise ExamplesPipelineError("No response from OpenAI")

    normalized = normalize_examples_response(response)
    report("Reviewing Examples")
    reviewed = analyzer.review_examples_with_corpus(
        {
            "content": content,
            "custom_instructions": custom_instructions,
            "output_limits": {
                "sentences": 2,
                "max_words_per_sentence": 18,
            },
        },
        normalized,
        "EXAMPLES_FROM_CONTENT_QA",
        custom_instructions,
    )
    reviewed = normalize_examples_response(reviewed)
    if len(reviewed.splitlines()) != 2:
        raise ExamplesPipelineError("Verified examples violated the two-sentence limit")
    rendered = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", reviewed)
    return rendered.replace("\n", "<br>")
