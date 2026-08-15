"""Background-safe CardCraft orchestration."""

import html
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional


class CardCraftPipelineError(RuntimeError):
    """Stop CardCraft before any Anki field is mutated."""


def normalize_generated_lines(text: str) -> str:
    """Remove blank lines while preserving line-oriented output."""
    if not text:
        return ""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(
        line.strip() for line in normalized.split("\n") if line.strip()
    )


def render_examples_html(text: str) -> str:
    """Render reviewed example Markdown into Anki-compatible HTML."""
    normalized = normalize_generated_lines(text)
    rendered = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", normalized)
    return rendered.replace("\n", "<br>")


def escape_word_stack_html(text: str) -> str:
    """Escape lexical text while preserving CardCraft line-break tags."""
    return "<br>".join(
        html.escape(part, quote=False) for part in text.split("<br>")
    )


def validate_compact_cardcraft_html(rendered_html: str) -> bool:
    """Enforce the compact four-section CardCraft output contract."""
    sections = re.split(r"<br\s*/?>\s*<br\s*/?>", rendered_html.strip())
    if len(sections) != 4:
        return False
    definition_words = re.sub(r"<[^>]+>", "", sections[1]).split()
    usage_lines = [
        line for line in re.split(r"<br\s*/?>", sections[2]) if line.strip()
    ]
    sentence_lines = [
        line for line in re.split(r"<br\s*/?>", sections[3]) if line.strip()
    ]
    if len(definition_words) > 23 or not 1 <= len(usage_lines) <= 2:
        return False
    if len(sentence_lines) != 2:
        return False
    return all(
        len(re.sub(r"<[^>]+>", "", sentence).split()) <= 18
        for sentence in sentence_lines
    )


def build_cardcraft_payload(
    analyzer: Any,
    config: Dict[str, Any],
    word: str,
    formatter: Callable[[Dict[str, Any]], str],
    logger: Callable[[str, str, Dict[str, Any]], None],
    progress: Optional[Callable[[str], None]] = None,
) -> Dict[str, str]:
    """Build a complete CardCraft result without mutating an Anki note."""
    def report(label: str) -> None:
        if progress:
            progress(label)

    report("Creating Word Family")
    raw_result = analyzer.analyze_word(word)
    logger("STEP1_NORWEGIAN_ANALYSIS", word, {"input": word, "result": raw_result})
    if not raw_result:
        raise CardCraftPipelineError(f"Could not analyze '{word}'")

    result = raw_result
    if config.get("cardcraft_expert_review_enabled", False):
        report("Refining Word Family")
        reviewed = analyzer.expert_review_word_stack(word, raw_result)
        logger("STEP1B_EXPERT_REVIEW", word, {"input": raw_result, "result": reviewed})
        if reviewed:
            result = reviewed

    report("Reviewing Word Family")
    result = analyzer.verify_word_stack_with_linguistic_qa(word, result)
    logger(
        "STEP1C_INDEPENDENT_LINGUISTIC_QA",
        word,
        {"input": raw_result, "result": result},
    )
    formatted_norwegian = formatter(result)
    if not formatted_norwegian:
        raise CardCraftPipelineError("Norwegian word stack is empty")

    report("Creating Card Content")

    def build_translation() -> Dict[str, Any]:
        translation_draft = analyzer.translate_to_language(result)
        if not translation_draft:
            raise CardCraftPipelineError("Target-language translation failed")
        return analyzer.verify_target_word_stack_translation(
            result,
            translation_draft,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        translation_future = executor.submit(build_translation)
        content_future = executor.submit(analyzer.get_cardcraft_content, result)
        translation = translation_future.result()
        content = content_future.result()

    logger("STEP2_ENGLISH_TRANSLATION", word, {"input": result, "result": translation})
    if not translation:
        raise CardCraftPipelineError("Target-language translation failed")
    logger(
        "STEP2B_TARGET_LANGUAGE_LINGUISTIC_QA",
        word,
        {"input": result, "result": translation},
    )
    formatted_translation = formatter(translation)
    if not formatted_translation:
        raise CardCraftPipelineError("Target-language word stack is empty")

    logger("STEP3_CARDCRAFT_CONTENT", word, {"input": result, "result": content})
    if not content:
        raise CardCraftPipelineError("Card content failed")
    definition = content.get("definition")
    usage_examples = content.get("usage_examples")
    context_sentences = content.get("context_sentences")
    if not definition or not usage_examples or not context_sentences:
        raise CardCraftPipelineError("Card content is incomplete")

    rendered_word_stack = escape_word_stack_html(formatted_norwegian)
    rendered_translation = escape_word_stack_html(formatted_translation)
    norwegian_parts = [
        rendered_word_stack,
        html.escape(str(definition), quote=False),
        render_examples_html("\n".join(usage_examples)),
        render_examples_html("\n".join(context_sentences)),
    ]
    rendered_norwegian = "<br><br>".join(norwegian_parts)
    report("Reviewing Card")
    rendered_norwegian = analyzer.verify_rendered_anki_field(
        {
            "artifact_role": "CardCraft word-family field",
            "input_word": word,
            "word_stack": result,
            "layout": [
                "unbolded related word-family forms",
                "one concise learner-facing definition",
                "at most two short collocation lines",
                "exactly two short contextual sentences",
            ],
            "output_limits": {
                "definition_max_words": 22,
                "usage_lines_max": 2,
                "context_sentences": 2,
                "context_sentence_max_words": 18,
            },
        },
        rendered_norwegian,
        "STEP6_RENDERED_FIELD_LINGUISTIC_QA",
    )
    if not validate_compact_cardcraft_html(rendered_norwegian):
        raise CardCraftPipelineError("Verified card violated the compact output contract")
    logger(
        "STEP6_RENDERED_FIELD_LINGUISTIC_QA",
        word,
        {"result": rendered_norwegian},
    )
    return {
        "field_1": rendered_translation,
        "field_2": rendered_norwegian,
    }
