# -*- coding: utf-8 -*-
"""Data contracts and receipts for InferAnki linguistic QA."""

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


FINAL_STATES = {"VERIFIED", "NEEDS_HUMAN_REVIEW", "BLOCKED"}
REVIEW_VERDICTS = {"PASS", "REPAIR", "ESCALATE"}
REVIEWER_KINDS = {"human", "independent-agent", "self-review"}
EVIDENCE_TIERS = {1, 2, 3, 4}
REQUIRED_CONTRACT = {"locale", "audience", "purpose", "risk_class", "invariants"}
REQUIRED_EVIDENCE = {
    "span_id",
    "text",
    "question",
    "source_tier",
    "source",
    "query",
    "observation",
    "interpretation",
}
TARGET_LANGUAGE_PROFILES = {
    "english": {
        "profile_id": "en-GB-word-stack-v1",
        "locale": "en-GB",
        "language_variety": "contemporary British English",
        "register": "concise neutral learner-dictionary English",
    },
    "ukrainian": {
        "profile_id": "uk-UA-word-stack-v1",
        "locale": "uk-UA",
        "language_variety": "contemporary standard Ukrainian",
        "register": "concise neutral learner-dictionary Ukrainian",
    },
}


class LinguisticQABlockedError(RuntimeError):
    """Stop release when the mandatory linguistic gate cannot verify output."""


def sha256_text(text: str) -> str:
    """Return a stable SHA-256 hash for an exact candidate string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_inferanki_contract(
    purpose: str,
    source_content: Any,
    additional_context: Any = None,
    artifact_kind: str = "plain_text",
) -> Dict[str, Any]:
    """Build the routine nb-NO contract shared by InferAnki generators."""
    invariants = [
        "preserve source meaning and target lemmas",
        "preserve semantic variables and custom instructions",
        "do not introduce Nynorsk, dialect, or unrelated synonyms",
    ]
    if artifact_kind == "word_stack_json":
        invariants.extend([
            "return one valid JSON object with exactly the required word-stack keys",
            "preserve null values and array/string field types",
            "do not add Markdown, HTML, labels, prose, or code fences",
        ])
        technical_constraints = [
            "output must parse as the existing CardCraft word-stack JSON schema",
            "word-stack values must remain unformatted lexical forms",
        ]
    elif artifact_kind == "examples_text":
        invariants.extend([
            "return plain text lines, never JSON or a mapping",
            "preserve line structure and Markdown markers",
            "bold the complete inflected surface form",
        ])
        technical_constraints = [
            "output must remain line-oriented text compatible with Anki rendering",
            "do not add headings, bullets, explanations, JSON, or code fences",
        ]
    elif artifact_kind == "description_text":
        invariants.extend([
            "return plain text, never JSON",
            "preserve one learner-facing concept per line",
        ])
        technical_constraints = [
            "each non-empty line must start with the concept marker when requested",
            "do not add headings, JSON, or code fences",
        ]
    elif artifact_kind == "anki_html":
        invariants.extend([
            "preserve the complete learner-facing wording and section order",
            "preserve only the allowed br, b, and i markup",
            "do not add headings, scripts, styles, links, images, or code fences",
        ])
        technical_constraints = [
            "output must remain an exact Anki HTML field artifact",
            "allowed tags are br, b, and i without attributes",
        ]
    else:
        invariants.append("preserve the complete artifact format")
        technical_constraints = ["return only the requested complete artifact"]
    return {
        "locale": "nb-NO",
        "language_variety": "modern Norwegian Bokmål",
        "audience": "adult learner of Norwegian",
        "purpose": purpose,
        "channel": "Anki desktop card editor",
        "register": "natural contemporary Bokmål",
        "domain": "language learning",
        "risk_class": "routine",
        "glossary": source_content,
        "additional_context": additional_context,
        "artifact_kind": artifact_kind,
        "invariants": invariants,
        "technical_constraints": technical_constraints,
    }


def resolve_target_language_profile(target_language: str) -> Dict[str, str]:
    """Resolve a configured target-language label to an explicit locale profile."""
    normalized = str(target_language or "").strip().casefold()
    aliases = {
        "en": "english",
        "en-gb": "english",
        "англійська": "english",
        "uk": "ukrainian",
        "uk-ua": "ukrainian",
        "українська": "ukrainian",
    }
    normalized = aliases.get(normalized, normalized)
    profile = TARGET_LANGUAGE_PROFILES.get(normalized)
    if not profile:
        raise LinguisticQABlockedError(
            f"No qualified target-language QA profile for {target_language!r}"
        )
    return dict(profile)


def build_target_language_contract(
    target_language: str,
    source_content: Any,
) -> Dict[str, Any]:
    """Build a word-stack translation contract for a qualified target locale."""
    profile = resolve_target_language_profile(target_language)
    return {
        "profile_id": profile["profile_id"],
        "locale": profile["locale"],
        "language_variety": profile["language_variety"],
        "audience": "adult learner of Norwegian",
        "purpose": "Target-language equivalents for a verified Norwegian word stack",
        "channel": "Anki desktop card editor",
        "register": profile["register"],
        "domain": "language learning",
        "risk_class": "routine",
        "glossary": source_content,
        "artifact_kind": "word_stack_json",
        "invariants": [
            "preserve the meaning and part of speech of every Norwegian source form",
            "return exactly the existing five word-stack keys",
            "preserve null values and array/string field types",
            "use concise idiomatic target-language lexical equivalents",
            "do not add explanations, labels, Markdown, HTML, or code fences",
        ],
        "technical_constraints": [
            "output must parse as the existing CardCraft word-stack JSON schema",
            "word-stack values must remain unformatted lexical forms",
            "preserve Unicode and JSON escaping",
        ],
    }


def build_evidence_entries(corpus: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert DH-LAB output into the portable linguistic evidence contract."""
    words = corpus.get("queried_words", [])
    matches = corpus.get("matches", [])
    missing = corpus.get("missing", [])
    observation = {
        "matches": matches,
        "missing": missing,
    }
    return [{
        "span_id": "nb-corpus-words",
        "text": ", ".join(str(word) for word in words),
        "question": "Which candidate forms are attested and comparatively common?",
        "source_tier": 2,
        "source": corpus.get("source", "Nasjonalbiblioteket DH-LAB"),
        "query": {
            "endpoint": "reference_words",
            "corpus": corpus.get("corpus"),
            "period": corpus.get("period"),
            "words": words,
        },
        "observation": observation,
        "interpretation": (
            "Use counts comparatively for modern usage. Missing forms remain unknown; "
            "frequency alone does not prove semantic or contextual fitness."
        ),
    }]


def build_collocation_evidence_entries(corpus: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert DH-LAB concordances into collocation and valency evidence."""
    terms = corpus.get("query_terms", [])
    return [{
        "span_id": "nb-corpus-collocations",
        "text": ", ".join(str(term) for term in terms),
        "question": "Which collocations and valency patterns occur in modern usage?",
        "source_tier": 2,
        "source": corpus.get("source", "Nasjonalbiblioteket DH-LAB concordances"),
        "query": {
            "endpoint": "conc",
            "corpus": corpus.get("corpus"),
            "period": corpus.get("period"),
            "terms": terms,
            "window": corpus.get("window"),
            "sample_size": corpus.get("sample_size"),
            "sample_document_ids": corpus.get("sample_document_ids", []),
        },
        "observation": {
            "matches": corpus.get("matches", []),
            "missing": corpus.get("missing", []),
            "limitations": corpus.get("limitations", []),
        },
        "interpretation": (
            "Use concordances to assess phrase shape and valency comparatively. "
            "The sample is descriptive; empty results do not prove invalidity."
        ),
    }]


def build_translation_evidence_entries(
    source_content: Any,
    target_contract: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Bind translation review to the verified Norwegian source artifact."""
    source_text = (
        source_content if isinstance(source_content, str)
        else json.dumps(source_content, ensure_ascii=False, sort_keys=True)
    )
    return [{
        "span_id": "translation-source-alignment",
        "text": source_text,
        "question": "Does each target form preserve source meaning and part of speech?",
        "source_tier": 1,
        "source": "InferAnki verified Norwegian word-stack artifact",
        "query": {
            "operation": "source-to-target lexical alignment",
            "source_locale": "nb-NO",
            "target_locale": target_contract.get("locale"),
            "profile_id": target_contract.get("profile_id"),
        },
        "observation": {
            "verified_source": source_content,
            "required_keys": [
                "substantiv", "adjektiv", "adverb", "verb", "partisipp"
            ],
        },
        "interpretation": (
            "The verified source controls semantic fidelity and schema parity. "
            "The independent target-language reviewer controls idiomaticity and locale fit."
        ),
    }]


def build_receipt(
    *,
    status: str,
    generator_id: str,
    reviewer_id: str,
    verdict: str,
    contract: Dict[str, Any],
    evidence: List[Dict[str, Any]],
    findings: List[Dict[str, Any]],
    cycles: int,
    final_text: str,
) -> Dict[str, Any]:
    """Build a receipt tied to the exact final candidate hash."""
    final_hash = sha256_text(final_text) if final_text else ""
    return {
        "schema_version": 1,
        "artifact_type": "inferanki-linguistic-qa-receipt",
        "status": status,
        "generator_id": generator_id,
        "contract": contract,
        "evidence": evidence,
        "reviewer": {
            "kind": "independent-agent",
            "reviewer_id": reviewer_id,
            "verdict": verdict,
            "reviewed_text_sha256": final_hash,
        },
        "findings": findings,
        "cycles": cycles,
        "final_text": final_text,
        "final_text_sha256": final_hash,
    }


def _missing_fields(value: Dict[str, Any], required: set) -> List[str]:
    return sorted(
        field for field in required
        if field not in value or value[field] in (None, "")
    )


def validate_receipt(data: Any) -> List[str]:
    """Validate procedural integrity of an InferAnki linguistic QA receipt."""
    errors: List[str] = []
    if not isinstance(data, dict):
        return ["receipt must be an object"]

    status = data.get("status")
    if status not in FINAL_STATES:
        errors.append("invalid final status")

    contract = data.get("contract")
    if not isinstance(contract, dict):
        errors.append("contract must be an object")
        contract = {}
    missing = _missing_fields(contract, REQUIRED_CONTRACT)
    if missing:
        errors.append(f"contract is missing: {', '.join(missing)}")
    if contract.get("risk_class") not in {"routine", "sensitive", "critical"}:
        errors.append("invalid risk class")
    if not isinstance(contract.get("invariants"), list) or not contract.get("invariants"):
        errors.append("contract.invariants must be a non-empty array")

    evidence = data.get("evidence")
    if not isinstance(evidence, list):
        errors.append("evidence must be an array")
        evidence = []
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            errors.append(f"evidence[{index}] must be an object")
            continue
        missing = _missing_fields(item, REQUIRED_EVIDENCE)
        if missing:
            errors.append(f"evidence[{index}] is missing: {', '.join(missing)}")
        if item.get("source_tier") not in EVIDENCE_TIERS:
            errors.append(f"evidence[{index}] has invalid source tier")

    reviewer = data.get("reviewer")
    if not isinstance(reviewer, dict):
        errors.append("reviewer must be an object")
        reviewer = {}
    if reviewer.get("kind") not in REVIEWER_KINDS:
        errors.append("invalid reviewer kind")
    if not reviewer.get("reviewer_id"):
        errors.append("reviewer_id is required")
    if reviewer.get("reviewer_id") == data.get("generator_id"):
        errors.append("reviewer_id must differ from generator_id")
    if reviewer.get("verdict") not in REVIEW_VERDICTS:
        errors.append("invalid reviewer verdict")

    cycles = data.get("cycles")
    if not isinstance(cycles, int) or not 1 <= cycles <= 3:
        errors.append("cycles must be an integer from 1 to 3")

    findings = data.get("findings")
    if not isinstance(findings, list):
        errors.append("findings must be an array")
        findings = []
    open_severities = {
        item.get("severity")
        for item in findings
        if isinstance(item, dict) and item.get("status") != "closed"
    }

    if status == "VERIFIED":
        final_text = data.get("final_text")
        final_hash = data.get("final_text_sha256")
        if not final_text:
            errors.append("VERIFIED requires final_text")
        if not evidence:
            errors.append("VERIFIED requires evidence")
        if reviewer.get("kind") not in {"human", "independent-agent"}:
            errors.append("VERIFIED requires an independent reviewer")
        if reviewer.get("verdict") != "PASS":
            errors.append("VERIFIED requires PASS")
        if final_text and final_hash != sha256_text(final_text):
            errors.append("final_text_sha256 mismatch")
        if reviewer.get("reviewed_text_sha256") != final_hash:
            errors.append("reviewed hash does not match final hash")
        if open_severities & {"blocker", "major"}:
            errors.append("VERIFIED has open blocker or major findings")
        if contract.get("risk_class") == "critical" and reviewer.get("kind") != "human":
            errors.append("critical content requires a human reviewer")
    return errors


def write_receipt(log_dir: str, step_name: str, receipt: Dict[str, Any]) -> str:
    """Validate and atomically write one local linguistic QA receipt."""
    errors = validate_receipt(receipt)
    if errors:
        raise ValueError("; ".join(errors))
    safe_step = re.sub(r"[^A-Za-z0-9_-]+", "-", step_name).strip("-").lower()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    destination = Path(log_dir) / f"linguistic-qa-{timestamp}-{safe_step}.json"
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(str(temporary), str(destination))
    return str(destination)
