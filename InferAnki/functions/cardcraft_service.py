"""Background-safe CardCraft orchestration."""

import html
import re
from typing import Any, Callable, Dict


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


def build_cardcraft_payload(
    analyzer: Any,
    config: Dict[str, Any],
    word: str,
    formatter: Callable[[Dict[str, Any]], str],
    logger: Callable[[str, str, Dict[str, Any]], None],
) -> Dict[str, str]:
    """Build a complete CardCraft result without mutating an Anki note."""
    raw_result = analyzer.analyze_word(word)
    logger("STEP1_NORWEGIAN_ANALYSIS", word, {"input": word, "result": raw_result})
    if not raw_result:
        raise CardCraftPipelineError(f"Could not analyze '{word}'")

    result = raw_result
    if config.get("cardcraft_expert_review_enabled", True):
        reviewed = analyzer.expert_review_word_stack(word, raw_result)
        logger("STEP1B_EXPERT_REVIEW", word, {"input": raw_result, "result": reviewed})
        if reviewed:
            result = reviewed

    result = analyzer.verify_word_stack_with_linguistic_qa(word, result)
    logger(
        "STEP1C_INDEPENDENT_LINGUISTIC_QA",
        word,
        {"input": raw_result, "result": result},
    )
    formatted_norwegian = formatter(result)
    if not formatted_norwegian:
        raise CardCraftPipelineError("Norwegian word stack is empty")

    translation = analyzer.translate_to_language(result)
    logger("STEP2_ENGLISH_TRANSLATION", word, {"input": result, "result": translation})
    if not translation:
        raise CardCraftPipelineError("Target-language translation failed")
    translation = analyzer.verify_target_word_stack_translation(result, translation)
    logger(
        "STEP2B_TARGET_LANGUAGE_LINGUISTIC_QA",
        word,
        {"input": result, "result": translation},
    )
    formatted_translation = formatter(translation)
    if not formatted_translation:
        raise CardCraftPipelineError("Target-language word stack is empty")

    descriptions = analyzer.get_description(formatted_norwegian)
    logger(
        "STEP3_NORWEGIAN_DESCRIPTION",
        word,
        {"input": formatted_norwegian, "result": descriptions},
    )
    if not descriptions:
        raise CardCraftPipelineError("Norwegian description failed")

    examples = analyzer.get_examples_simple(result)
    logger("STEP4_AI_EXAMPLES", word, {"input": result, "result": examples})
    if not examples:
        raise CardCraftPipelineError("Usage examples failed")

    sentences = analyzer.get_examples_sentences(result)
    logger("STEP5_NORWEGIAN_SENTENCES", word, {"input": result, "result": sentences})
    if not sentences:
        raise CardCraftPipelineError("Context sentences failed")

    rendered_word_stack = escape_word_stack_html(formatted_norwegian)
    rendered_translation = escape_word_stack_html(formatted_translation)
    norwegian_parts = [
        rendered_word_stack,
        "<br>".join(descriptions),
        render_examples_html(examples),
        render_examples_html(sentences),
    ]
    rendered_norwegian = "<br><br>".join(norwegian_parts)
    rendered_norwegian = analyzer.verify_rendered_anki_field(
        {
            "artifact_role": "CardCraft word-family field",
            "input_word": word,
            "word_stack": result,
            "layout": [
                "unbolded related word-family forms",
                "learner-facing definition",
                "bolded target forms inside usage examples",
                "bolded target forms inside contextual sentences",
            ],
        },
        rendered_norwegian,
        "STEP6_RENDERED_FIELD_LINGUISTIC_QA",
    )
    logger(
        "STEP6_RENDERED_FIELD_LINGUISTIC_QA",
        word,
        {"result": rendered_norwegian},
    )
    return {
        "field_1": rendered_translation,
        "field_2": rendered_norwegian,
    }
