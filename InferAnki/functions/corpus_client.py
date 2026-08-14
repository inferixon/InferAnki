# -*- coding: utf-8 -*-
"""Norwegian corpus evidence from the National Library DH-LAB API."""

import json
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class CorpusEvidenceClient:
    """Fetch fail-open frequency and concordance evidence for Norwegian text."""

    SOURCE_NAME = "Nasjonalbiblioteket DH-LAB reference_words"
    IGNORED_WORDS = {
        "de", "den", "det", "ei", "en", "et", "har", "med", "mer", "mest",
        "og", "som", "til", "å",
    }

    def __init__(self, config: Dict[str, Any]):
        self.enabled = bool(config.get("corpus_enabled", True))
        self.base_url = str(
            config.get("corpus_base_url", "https://api.nb.no/dhlab")
        ).rstrip("/")
        self.timeout = float(config.get("corpus_timeout_seconds", 8))
        self.doctype = str(config.get("corpus_doctype", "digavis"))
        self.from_year = int(config.get("corpus_from_year", 2000))
        self.to_year = int(config.get("corpus_to_year", 2025))
        self.max_words = int(config.get("corpus_max_words", 40))
        self.collocations_enabled = bool(
            config.get("corpus_collocations_enabled", True)
        )
        self.collocation_sample_size = int(
            config.get("corpus_collocation_sample_size", 80)
        )
        self.collocation_max_terms = int(
            config.get("corpus_collocation_max_terms", 3)
        )
        self.collocation_window = int(
            config.get("corpus_collocation_window", 5)
        )
        self.collocation_limit = int(
            config.get("corpus_collocation_limit_per_document", 2)
        )
        self._cache: Dict[Tuple[str, ...], Dict[str, Any]] = {}
        self._collocation_cache: Dict[Tuple[str, ...], Dict[str, Any]] = {}
        self._collocation_corpus_ids: Optional[List[int]] = None

    def _post_json(self, endpoint: str, payload: Dict[str, Any]) -> Any:
        """POST JSON to one DH-LAB endpoint and decode its response."""
        request = Request(
            f"{self.base_url}/{endpoint.lstrip('/')}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def extract_words(value: Any) -> List[str]:
        """Extract unique Norwegian-looking word tokens from nested content."""
        fragments: List[str] = []

        def collect(item: Any) -> None:
            if isinstance(item, str):
                fragments.append(item)
            elif isinstance(item, dict):
                for nested in item.values():
                    collect(nested)
            elif isinstance(item, (list, tuple, set)):
                for nested in item:
                    collect(nested)

        collect(value)
        text = " ".join(fragments)
        text = re.sub(r"<[^>]+>|\*+", " ", text)
        tokens = re.findall(r"[A-Za-zÆØÅæøåÉé]+(?:-[A-Za-zÆØÅæøåÉé]+)*", text)

        unique: List[str] = []
        seen = set()
        for token in tokens:
            normalized = token.casefold()
            if (
                len(normalized) < 2
                or normalized in seen
                or normalized == "null"
                or normalized in CorpusEvidenceClient.IGNORED_WORDS
            ):
                continue
            seen.add(normalized)
            unique.append(normalized)
        return unique

    def lookup(self, values: Iterable[Any]) -> Dict[str, Any]:
        """Look up extracted words and return evidence without raising errors."""
        words = sorted(self.extract_words(list(values))[: self.max_words])
        base_result: Dict[str, Any] = {
            "source": self.SOURCE_NAME,
            "corpus": self.doctype,
            "period": [self.from_year, self.to_year],
            "queried_words": words,
        }
        if not self.enabled:
            return {**base_result, "status": "disabled", "matches": [], "missing": words}
        if not words:
            return {**base_result, "status": "empty", "matches": [], "missing": []}

        cache_key = tuple(words)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            rows = self._post_json(
                "reference_words",
                {
                    "doctype": self.doctype,
                    "from_year": self.from_year,
                    "to_year": self.to_year,
                    "words": words,
                },
            )
            matches = [
                {
                    "word": str(row[0]),
                    "absolute_frequency": int(row[1]),
                    "relative_frequency": float(row[2]),
                }
                for row in rows
                if isinstance(row, list) and len(row) >= 3
            ]
            matched_words = {item["word"].casefold() for item in matches}
            result = {
                **base_result,
                "status": "ok",
                "matches": matches,
                "missing": [word for word in words if word not in matched_words],
            }
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as error:
            result = {
                **base_result,
                "status": "unavailable",
                "matches": [],
                "missing": [],
                "error": type(error).__name__,
            }

        self._cache[cache_key] = result
        return result

    def _get_collocation_corpus_ids(self) -> List[int]:
        """Build and cache the exact DH-LAB sample used for concordances."""
        if self._collocation_corpus_ids is not None:
            return self._collocation_corpus_ids
        corpus = self._post_json(
            "build_corpus",
            {
                "doctype": self.doctype,
                "from_year": self.from_year,
                "to_year": self.to_year,
                "limit": self.collocation_sample_size,
                "order_by": "random",
            },
        )
        raw_ids = corpus.get("dhlabid", {}) if isinstance(corpus, dict) else {}
        if isinstance(raw_ids, dict):
            values = raw_ids.values()
        elif isinstance(raw_ids, list):
            values = raw_ids
        else:
            values = []
        self._collocation_corpus_ids = [int(value) for value in values]
        return self._collocation_corpus_ids

    def lookup_collocations(self, values: Iterable[Any]) -> Dict[str, Any]:
        """Return concordances and common context words for target forms."""
        terms = [
            word for word in self.extract_words(list(values))
            if len(word) >= 3
        ][: self.collocation_max_terms]
        base_result: Dict[str, Any] = {
            "source": "Nasjonalbiblioteket DH-LAB concordances",
            "locale": "nb-NO",
            "corpus": self.doctype,
            "period": [self.from_year, self.to_year],
            "query_terms": terms,
            "window": self.collocation_window,
            "sample_size": self.collocation_sample_size,
            "matches": [],
            "missing": [],
            "limitations": [
                "Random corpus sample; concordances are usage evidence, not a normative verdict."
            ],
        }
        if not self.enabled or not self.collocations_enabled:
            return {**base_result, "status": "disabled", "missing": terms}
        if not terms:
            return {**base_result, "status": "empty"}

        cache_key = tuple(terms)
        cached = self._collocation_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            corpus_ids = self._get_collocation_corpus_ids()
            if not corpus_ids:
                raise ValueError("DH-LAB corpus sample is empty")
            matches = []
            missing = []
            for term in terms:
                rows = self._post_json(
                    "conc",
                    {
                        "dhlabids": corpus_ids,
                        "query": term,
                        "window": self.collocation_window,
                        "limit": self.collocation_limit,
                        "html_formatting": False,
                    },
                )
                raw_concordances = rows.get("conc", {}) if isinstance(rows, dict) else {}
                if isinstance(raw_concordances, dict):
                    concordances = [str(value) for value in raw_concordances.values()]
                elif isinstance(raw_concordances, list):
                    concordances = [str(value) for value in raw_concordances]
                else:
                    concordances = []
                if not concordances:
                    missing.append(term)
                    continue
                context_counts = Counter()
                for concordance in concordances:
                    for token in self.extract_words(concordance):
                        if token != term:
                            context_counts[token] += 1
                matches.append({
                    "term": term,
                    "concordance_count": len(concordances),
                    "top_context": [
                        {"word": word, "count": count}
                        for word, count in sorted(
                            context_counts.items(),
                            key=lambda item: (-item[1], item[0]),
                        )[:12]
                    ],
                    "concordances": concordances[:12],
                })
            result = {
                **base_result,
                "status": "ok",
                "sample_document_ids": corpus_ids,
                "matches": matches,
                "missing": missing,
            }
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as error:
            result = {
                **base_result,
                "status": "unavailable",
                "error": type(error).__name__,
            }
        self._collocation_cache[cache_key] = result
        return result

    @staticmethod
    def format_for_prompt(evidence: Optional[Dict[str, Any]]) -> str:
        """Format corpus evidence with explicit epistemic limits."""
        if not evidence:
            return ""
        status = evidence.get("status")
        if status not in {"ok", "empty"}:
            return (
                "\n\nCORPUS EVIDENCE: unavailable. Continue from linguistic knowledge; "
                "do not invent corpus findings."
            )

        compact = {
            "source": evidence.get("source"),
            "corpus": evidence.get("corpus"),
            "period": evidence.get("period"),
            "matches": evidence.get("matches", []),
            "missing": evidence.get("missing", []),
        }
        return (
            "\n\nCORPUS EVIDENCE (usage signal, not dictionary proof):\n"
            + json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
            + "\nUse frequencies comparatively. A missing word is unknown, not proof that "
            "the word is invalid. Do not claim checks against sources absent here."
        )

    @staticmethod
    def format_collocations_for_prompt(evidence: Optional[Dict[str, Any]]) -> str:
        """Format concordance evidence without overstating its authority."""
        if not evidence:
            return ""
        if evidence.get("status") not in {"ok", "empty"}:
            return (
                "\n\nCOLLOCATION EVIDENCE: unavailable. Do not invent concordances "
                "or valency findings."
            )
        compact = {
            "source": evidence.get("source"),
            "corpus": evidence.get("corpus"),
            "period": evidence.get("period"),
            "window": evidence.get("window"),
            "sample_size": evidence.get("sample_size"),
            "matches": evidence.get("matches", []),
            "missing": evidence.get("missing", []),
            "limitations": evidence.get("limitations", []),
        }
        return (
            "\n\nCOLLOCATION EVIDENCE (concordance signal, not dictionary proof):\n"
            + json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
            + "\nUse concordances to compare natural phrase and valency patterns. "
            "Do not infer invalidity from an empty sample."
        )
