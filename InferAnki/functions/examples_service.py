"""Background-safe standalone Examples orchestration."""

import re
from typing import Any, Callable, Dict, Optional


class ExamplesPipelineError(RuntimeError):
    """Stop Examples generation before an Anki note is mutated."""


def normalize_examples_response(text: str) -> str:
    """Remove blank lines while preserving one sentence per line."""
    if not text:
        return ""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(
        line.strip() for line in normalized.split("\n") if line.strip()
    )


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
    rendered = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", normalized)
    rendered = rendered.replace("\n", "<br>")
    report("Reviewing Examples")
    verified = analyzer.verify_rendered_anki_field(
        {
            "content": content,
            "custom_instructions": custom_instructions,
            "output_limits": {
                "sentences": 2,
                "max_words_per_sentence": 18,
            },
        },
        rendered,
        "EXAMPLES_FROM_CONTENT_RENDERED_QA",
    )
    if len([line for line in re.split(r"<br\s*/?>", verified) if line.strip()]) != 2:
        raise ExamplesPipelineError("Verified examples violated the two-sentence limit")
    return verified
