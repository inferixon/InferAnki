"""Background-safe standalone Examples orchestration."""

import re
from typing import Any, Dict, Optional


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
) -> str:
    """Generate, review, render, and verify standalone examples."""
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

    corpus_evidence = analyzer.get_corpus_evidence(content)
    collocation_evidence = analyzer.get_collocation_evidence(content)
    user_message += analyzer.corpus_client.format_for_prompt(corpus_evidence)
    user_message += analyzer.corpus_client.format_collocations_for_prompt(
        collocation_evidence
    )

    system_message = prompt.get("system_message", "")
    api_settings = prompt.get("api_settings", {})
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message},
    ]
    response, _usage = analyzer.openai_client.request_with_messages(
        messages,
        custom_model=api_settings.get("model", analyzer.openai_client.model),
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
            "corpus_evidence": corpus_evidence,
            "collocation_evidence": collocation_evidence,
            "api_settings": api_settings,
        },
        response,
        "EXAMPLES_FROM_CONTENT",
    )
    if not response:
        raise ExamplesPipelineError("No response from OpenAI")

    reviewed = analyzer.review_examples_with_corpus(
        content,
        response,
        "EXAMPLES_FROM_CONTENT_CORPUS_REVIEW",
        custom_instructions,
    )
    normalized = normalize_examples_response(reviewed)
    rendered = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", normalized)
    rendered = rendered.replace("\n", "<br>")
    return analyzer.verify_rendered_anki_field(
        {"content": content, "custom_instructions": custom_instructions},
        rendered,
        "EXAMPLES_FROM_CONTENT_RENDERED_QA",
    )
