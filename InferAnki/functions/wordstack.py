# -*- coding: utf-8 -*-
"""
CardCraft Word Family Analyzer
Norwegian Bokmål word analysis using OpenAI
"""

import json
import os
import re
import threading
from typing import Dict, Optional, Any
from datetime import datetime

try:
    from aqt.utils import showInfo as _anki_show_info # type: ignore
    from aqt.utils import showCritical as _anki_show_critical # type: ignore
    ANKI_AVAILABLE = True

    def showInfo(text):
        """Show UI information only from the Anki main thread."""
        if threading.current_thread() is threading.main_thread():
            _anki_show_info(text)
        else:
            print(f"INFO: {text}")

    def showCritical(text):
        """Show UI errors only from the Anki main thread."""
        if threading.current_thread() is threading.main_thread():
            _anki_show_critical(text)
        else:
            print(f"CRITICAL: {text}")
except ImportError:
    ANKI_AVAILABLE = False

    def showInfo(text): print(f"INFO: {text}")
    def showCritical(text): print(f"CRITICAL: {text}")

from .openai_client import OpenAIClient
from .corpus_client import CorpusEvidenceClient
from .linguistic_qa import (
    LinguisticQABlockedError,
    build_collocation_evidence_entries,
    build_evidence_entries,
    build_inferanki_contract,
    build_receipt,
    build_target_language_contract,
    build_translation_evidence_entries,
    sha256_text,
    write_receipt,
)
from .logging_utils import prune_log_files


class NorwegianWordAnalyzer:
    """Analyze Norwegian Bokmål words using AI"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.openai_client = OpenAIClient(config)
        self.corpus_client = CorpusEvidenceClient(config)
        self.prompts = self._load_prompts()
        
        # Setup logging relative to addon root for portability
        addon_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.log_dir = os.path.join(addon_root, "logs")
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir, exist_ok=True)
    
    def _build_api_override_kwargs(self, api_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Map prompt api_settings to OpenAIClient override kwargs"""
        overrides: Dict[str, Any] = {}
        if not api_settings:
            return overrides

        model = api_settings.get("model")
        if model:
            overrides["custom_model"] = model

        if "temperature" in api_settings:
            overrides["custom_temperature"] = api_settings.get("temperature")

        max_tokens = api_settings.get("max_completion_tokens")
        if max_tokens is None:
            max_tokens = api_settings.get("max_tokens")
        if max_tokens is not None:
            overrides["custom_max_tokens"] = max_tokens

        response_format = api_settings.get("response_format")
        if response_format:
            overrides["response_format"] = response_format

        reasoning_effort = api_settings.get("reasoning_effort")
        if reasoning_effort:
            overrides["custom_reasoning_effort"] = reasoning_effort

        verbosity = api_settings.get("verbosity")
        if verbosity:
            overrides["custom_verbosity"] = verbosity

        return overrides

    def _log_api_call(self, request_data, response_data, step_name=""):
        """Log API request and response to convert-datetime.log"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            log_file = os.path.join(self.log_dir, f"convert-{timestamp}.log")
            
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"TIMESTAMP: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"STEP: {step_name}\n")
                f.write(f"{'='*60}\n")
                f.write("API-REQUEST:\n")
                f.write(json.dumps(request_data, indent=2, ensure_ascii=False))
                f.write(f"\n{'-'*60}\n")
                f.write("API-RESPONSE:\n")
                f.write(str(response_data))
                f.write(f"\n{'='*60}\n\n")
            prune_log_files(
                self.log_dir,
                "convert-*.log",
                self.config.get("runtime_log_max_files", 180),
            )
        except Exception as e:
            print(f"Logging error: {e}")
    
    def _load_prompts(self) -> Dict[str, Any]:
        """Load AI prompts from prompts.json"""
        try:
            prompts_file = os.path.join(os.path.dirname(__file__), "..", "prompts.json")
            
            if os.path.exists(prompts_file):
                with open(prompts_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                showCritical("prompts.json not found")
                return {}
                
        except Exception as e:
            showCritical(f"Error loading prompts: {e}")
            return {}
    
    def analyze_word(self, word: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a Norwegian word and return grammatical forms
        
        Args:
            word: Norwegian word to analyze
            
        Returns:
            Dictionary with word analysis or None if failed
        """
        if not word or not word.strip():
            return None
        
        word = word.strip().lower()
        
        # Get prompt template
        analyzer_prompt = self.prompts.get("norwegian_word_stack", {})
        
        if not analyzer_prompt:
            showCritical("Norwegian word stack prompt not found")
            return None
          # Build user message with Norwegian template
        user_template = analyzer_prompt.get("user_template", "")
        user_message = user_template.format(input_word=word)
        
        # Get system message
        system_message = analyzer_prompt.get("system_message", "")
        system_message += (
            "\nVIKTIG KILDEGRENSE: Du har ikke direkte tilgang til NAOB, "
            "Bokmålsordboka eller SNL i dette steget. Ikke påstå at du har søkt i dem. "
            "Foreslå former fra språkkompetansen din; neste steg får faktisk korpusevidens."
        )
        
        # Build few-shot examples from examples field
        examples_list = []
        examples_data = analyzer_prompt.get("examples", {})
        if examples_data:
            for example_word, expected_result in examples_data.items():
                example_user = user_template.format(input_word=example_word)
                example_assistant = json.dumps(expected_result, ensure_ascii=False)
                examples_list.append({
                    "user": example_user,
                    "assistant": example_assistant
                })
        
        # Update OpenAI client settings
        api_settings = analyzer_prompt.get("api_settings", {})
        override_kwargs = self._build_api_override_kwargs(api_settings)
        try:
            # Make API request with examples
            response = self.openai_client.simple_request(
                user_message,
                system_message,
                examples_list,
                **override_kwargs
            )
            
            # Log the API call
            request_data = {
                "system_message": system_message,
                "examples": examples_list,
                "user_message": user_message,
                "api_settings": api_settings
            }
            self._log_api_call(request_data, response, f"STEP1_NORWEGIAN_ANALYSIS_{word}")
            
            if response:
                # Parse JSON response
                try:
                    analysis = json.loads(response)
                    
                    # Validate response structure
                    if self._validate_analysis(analysis):
                        return analysis
                    else:
                        showCritical("Invalid analysis structure received")
                        return None
                        
                except json.JSONDecodeError as e:
                    showCritical(f"Failed to parse AI response as JSON: {e}")
                    return None
            else:
                showCritical("No response from AI")
                return None
                
        except Exception as e:
                        showCritical(f"Error analyzing word '{word}': {e}")
        return None

    def expert_review_word_stack(self, input_word: str, analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Refine STEP1 output to keep only common modern Bokmål forms.

        This is a second-pass review to reduce rare/archaic/dialectal forms.
        Returns the refined JSON on success, or the original analysis on failure.
        """
        try:
            if not analysis:
                return None
            if not self.openai_client.enabled:
                return analysis

            review_prompt = self.prompts.get("norwegian_word_stack_expert_review", {})
            if not review_prompt:
                return analysis

            user_template = review_prompt.get("user_template", "")
            system_message = review_prompt.get("system_message", "")
            api_settings = review_prompt.get("api_settings", {})

            norwegian_json_str = json.dumps(analysis, ensure_ascii=False, indent=2)
            corpus_evidence = self.get_corpus_evidence(input_word, analysis)
            collocation_evidence = self.get_collocation_evidence(input_word, analysis)
            user_message = user_template.format(input_word=input_word, norwegian_json=norwegian_json_str)
            user_message += self.corpus_client.format_for_prompt(corpus_evidence)
            user_message += self.corpus_client.format_collocations_for_prompt(
                collocation_evidence
            )

            # Few-shot examples (optional)
            examples_list = []
            examples_data = review_prompt.get("examples", {})
            if isinstance(examples_data, dict):
                for example_word, example_obj in examples_data.items():
                    if not isinstance(example_obj, dict):
                        continue
                    example_input = example_obj.get("input")
                    example_output = example_obj.get("output")
                    if not example_input or not example_output:
                        continue
                    example_user = user_template.format(
                        input_word=example_word,
                        norwegian_json=json.dumps(example_input, ensure_ascii=False, indent=2)
                    )
                    example_assistant = json.dumps(example_output, ensure_ascii=False)
                    examples_list.append({"user": example_user, "assistant": example_assistant})

            override_kwargs = self._build_api_override_kwargs(api_settings)

            response = self.openai_client.simple_request(
                user_message,
                system_message,
                examples_list,
                **override_kwargs
            )

            request_data = {
                "system_message": system_message,
                "examples": examples_list,
                "user_message": user_message,
                "corpus_evidence": corpus_evidence,
                "collocation_evidence": collocation_evidence,
                "api_settings": api_settings
            }
            self._log_api_call(request_data, response, f"STEP1B_EXPERT_REVIEW_{input_word}")

            if not response:
                return analysis

            try:
                reviewed = json.loads(response)
            except json.JSONDecodeError:
                return analysis

            if not isinstance(reviewed, dict):
                return analysis

            # Minimal structural validation
            required_keys = {"substantiv", "adjektiv", "adverb", "verb", "partisipp"}
            if not required_keys.issubset(set(reviewed.keys())):
                return analysis

            # Ensure substantiv is always a list (or null)
            substantiv_val = reviewed.get("substantiv")
            if substantiv_val is not None and not isinstance(substantiv_val, list):
                reviewed["substantiv"] = [str(substantiv_val)]

            return reviewed

        except Exception as e:
            showCritical(f"Expert review error: {str(e)}")
            return analysis

    def get_corpus_evidence(self, *values: Any) -> Dict[str, Any]:
        """Return fail-open Norwegian corpus evidence for prompt grounding."""
        return self.corpus_client.lookup(values)

    def get_collocation_evidence(self, *values: Any) -> Dict[str, Any]:
        """Return fail-open Norwegian concordance evidence for phrase review."""
        return self.corpus_client.lookup_collocations(values)

    @staticmethod
    def _serialize_qa_value(value: Any) -> str:
        """Serialize structured QA context without generator rationale."""
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, indent=2)

    def _run_clean_linguistic_review(
        self,
        contract: Dict[str, Any],
        source_content: Any,
        candidate: str,
        evidence: list,
        step_name: str,
    ) -> Dict[str, Any]:
        """Run a stateless reviewer request that cannot rewrite the candidate."""
        prompt_key = (
            "norwegian_linguistic_independent_review"
            if contract.get("locale") == "nb-NO"
            else "target_language_linguistic_independent_review"
        )
        prompt = self.prompts.get(prompt_key, {})
        if not prompt:
            raise LinguisticQABlockedError("Independent reviewer prompt is missing")
        user_message = prompt.get("user_template", "").format(
            contract=json.dumps(contract, ensure_ascii=False, indent=2),
            source_content=self._serialize_qa_value(source_content),
            candidate=candidate,
            evidence=json.dumps(evidence, ensure_ascii=False, indent=2),
            candidate_sha256=sha256_text(candidate),
        )
        system_message = prompt.get("system_message", "")
        api_settings = prompt.get("api_settings", {})
        response = self.openai_client.simple_request(
            user_message,
            system_message,
            **self._build_api_override_kwargs(api_settings),
        )
        self._log_api_call(
            {
                "system_message": system_message,
                "user_message": user_message,
                "api_settings": api_settings,
            },
            response,
            step_name,
        )
        if not response:
            raise LinguisticQABlockedError("Independent reviewer returned no response")
        review = json.loads(response)
        if not isinstance(review, dict):
            raise LinguisticQABlockedError("Independent review must be a JSON object")
        if review.get("candidate_sha256") != sha256_text(candidate):
            raise LinguisticQABlockedError("Independent reviewer hash mismatch")
        verdict = review.get("verdict")
        findings = review.get("findings")
        if verdict not in {"PASS", "REPAIR", "ESCALATE"}:
            raise LinguisticQABlockedError("Independent review verdict is invalid")
        if not isinstance(findings, list):
            raise LinguisticQABlockedError("Independent review findings must be an array")
        normalized_findings = []
        for index, finding in enumerate(findings):
            if not isinstance(finding, dict):
                raise LinguisticQABlockedError("Independent review finding is invalid")
            normalized = dict(finding)
            normalized.setdefault("span_id", f"finding-{index + 1}")
            normalized.setdefault("category", "linguistic-conventions")
            normalized.setdefault("severity", "major")
            normalized.setdefault("status", "open")
            normalized_findings.append(normalized)
        return {"verdict": verdict, "findings": normalized_findings}

    def _run_linguistic_repair(
        self,
        contract: Dict[str, Any],
        source_content: Any,
        candidate: str,
        findings: list,
        step_name: str,
    ) -> str:
        """Repair a candidate in a separate request after independent findings."""
        prompt_key = (
            "norwegian_linguistic_repair"
            if contract.get("locale") == "nb-NO"
            else "target_language_linguistic_repair"
        )
        prompt = self.prompts.get(prompt_key, {})
        if not prompt:
            raise LinguisticQABlockedError("Linguistic repair prompt is missing")
        user_message = prompt.get("user_template", "").format(
            contract=json.dumps(contract, ensure_ascii=False, indent=2),
            source_content=self._serialize_qa_value(source_content),
            candidate=candidate,
            findings=json.dumps(findings, ensure_ascii=False, indent=2),
        )
        system_message = prompt.get("system_message", "")
        api_settings = prompt.get("api_settings", {})
        response = self.openai_client.simple_request(
            user_message,
            system_message,
            **self._build_api_override_kwargs(api_settings),
        )
        self._log_api_call(
            {
                "system_message": system_message,
                "user_message": user_message,
                "api_settings": api_settings,
            },
            response,
            step_name,
        )
        if not response:
            raise LinguisticQABlockedError("Repair returned no response")
        repaired = json.loads(response)
        output = repaired.get("output") if isinstance(repaired, dict) else None
        if not isinstance(output, str) or not output.strip():
            raise LinguisticQABlockedError("Repair output is invalid")
        return output.strip()

    def _write_qa_receipt(
        self,
        *,
        status: str,
        contract: Dict[str, Any],
        evidence: list,
        findings: list,
        cycles: int,
        verdict: str,
        final_text: str,
        step_name: str,
    ) -> str:
        """Write a validated receipt for the exact reviewed candidate."""
        model = self.openai_client.model
        receipt = build_receipt(
            status=status,
            generator_id=f"InferAnki:{model}:generator",
            reviewer_id=f"InferAnki:{model}:clean-reviewer",
            verdict=verdict,
            contract=contract,
            evidence=evidence,
            findings=findings,
            cycles=cycles,
            final_text=final_text,
        )
        path = write_receipt(self.log_dir, step_name, receipt)
        prune_log_files(
            self.log_dir,
            "linguistic-qa-*.json",
            self.config.get("qa_receipt_max_files", 100),
        )
        return path

    def run_linguistic_qa_gate(
        self,
        source_content: Any,
        generated_text: str,
        step_name: str,
        additional_context: Optional[Any] = None,
        purpose: str = "Norwegian learner-facing content",
        artifact_kind: str = "plain_text",
        contract_override: Optional[Dict[str, Any]] = None,
        evidence_override: Optional[list] = None,
    ) -> str:
        """Run corpus evidence, clean review, repair, and mandatory re-review."""
        if not generated_text or not self.config.get("corpus_eval_enabled", True):
            return generated_text
        contract = contract_override or build_inferanki_contract(
            purpose, source_content, additional_context, artifact_kind
        )
        current = generated_text.strip()
        max_cycles = max(1, min(3, int(self.config.get("corpus_eval_max_cycles", 3))))
        all_findings = []
        evidence = []
        cycle = 1
        receipt_written = False
        evidence_source = self._select_qa_evidence_source(source_content)
        try:
            for cycle in range(1, max_cycles + 1):
                if not self._validate_qa_candidate(current, artifact_kind):
                    raise LinguisticQABlockedError(
                        f"Candidate violates {artifact_kind} output contract"
                    )
                if evidence_override is not None:
                    evidence = list(evidence_override)
                else:
                    candidate_terms = self._extract_candidate_evidence_terms(current)
                    corpus = self.get_corpus_evidence(
                        evidence_source,
                        candidate_terms,
                    )
                    if corpus.get("status") != "ok":
                        raise LinguisticQABlockedError(
                            f"Corpus evidence is {corpus.get('status', 'unavailable')}"
                        )
                    evidence = build_evidence_entries(corpus)
                    if self.config.get("corpus_collocations_enabled", True):
                        collocations = self.get_collocation_evidence(
                            evidence_source,
                            candidate_terms,
                        )
                        if (
                            self.config.get("corpus_collocations_required", True)
                            and collocations.get("status") not in {"ok", "empty"}
                        ):
                            raise LinguisticQABlockedError(
                                "Collocation evidence is "
                                f"{collocations.get('status', 'unavailable')}"
                            )
                        if collocations.get("status") in {"ok", "empty"}:
                            evidence.extend(
                                build_collocation_evidence_entries(collocations)
                            )
                review = self._run_clean_linguistic_review(
                    contract,
                    source_content,
                    current,
                    evidence,
                    f"{step_name}_REVIEW_{cycle}",
                )
                verdict = review["verdict"]
                findings = review["findings"]
                if verdict == "PASS":
                    if not self._validate_qa_candidate(current, artifact_kind):
                        raise LinguisticQABlockedError(
                            f"Reviewed candidate violates {artifact_kind} contract"
                        )
                    for finding in all_findings:
                        finding["status"] = "closed"
                    all_findings.extend(findings)
                    self._write_qa_receipt(
                        status="VERIFIED",
                        contract=contract,
                        evidence=evidence,
                        findings=all_findings,
                        cycles=cycle,
                        verdict="PASS",
                        final_text=current,
                        step_name=step_name,
                    )
                    receipt_written = True
                    return current
                all_findings.extend(findings)
                if verdict == "ESCALATE" or cycle == max_cycles:
                    self._write_qa_receipt(
                        status="NEEDS_HUMAN_REVIEW",
                        contract=contract,
                        evidence=evidence,
                        findings=all_findings,
                        cycles=cycle,
                        verdict=verdict,
                        final_text=current,
                        step_name=step_name,
                    )
                    receipt_written = True
                    diagnosis = next(
                        (
                            str(finding.get("diagnosis", "")).strip()
                            for finding in findings
                            if isinstance(finding, dict)
                            and finding.get("diagnosis")
                        ),
                        "",
                    )
                    detail = f": {diagnosis[:240]}" if diagnosis else ""
                    raise LinguisticQABlockedError(
                        f"Linguistic QA requires human review{detail}"
                    )
                current = self._run_linguistic_repair(
                    contract,
                    source_content,
                    current,
                    findings,
                    f"{step_name}_REPAIR_{cycle}",
                )
        except LinguisticQABlockedError:
            if not receipt_written:
                try:
                    self._write_qa_receipt(
                        status="BLOCKED",
                        contract=contract,
                        evidence=evidence,
                        findings=all_findings + [{
                            "span_id": "qa-gate",
                            "category": "consistency",
                            "severity": "blocker",
                            "diagnosis": "Mandatory linguistic gate did not complete",
                            "status": "open",
                        }],
                        cycles=cycle,
                        verdict="ESCALATE",
                        final_text=current,
                        step_name=step_name,
                    )
                except Exception:
                    pass
            raise
        except Exception as error:
            blocker = {
                "span_id": "qa-runtime",
                "category": "consistency",
                "severity": "blocker",
                "diagnosis": type(error).__name__,
                "status": "open",
            }
            try:
                self._write_qa_receipt(
                    status="BLOCKED",
                    contract=contract,
                    evidence=evidence,
                    findings=all_findings + [blocker],
                    cycles=cycle,
                    verdict="ESCALATE",
                    final_text=current,
                    step_name=step_name,
                )
            except Exception:
                pass
            raise LinguisticQABlockedError(
                f"Linguistic QA failed: {type(error).__name__}"
            ) from error

    @staticmethod
    def _select_qa_evidence_source(source_content: Any) -> Any:
        """Exclude contract metadata from lexical corpus queries."""
        if isinstance(source_content, dict):
            word_stack = source_content.get("word_stack")
            if isinstance(word_stack, dict):
                return word_stack
        return source_content

    @staticmethod
    def _extract_candidate_evidence_terms(candidate: str) -> list:
        """Extract only marked target forms from learner-facing candidates."""
        if not isinstance(candidate, str):
            return []
        markdown = re.findall(r"\*\*([^*]+)\*\*", candidate)
        html_terms = re.findall(
            r"<b>(.*?)</b>",
            candidate,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return [
            re.sub(r"<[^>]+>", "", term).strip()
            for term in markdown + html_terms
            if re.sub(r"<[^>]+>", "", term).strip()
        ]

    def review_examples_with_corpus(
        self,
        source_content: Any,
        generated_text: str,
        step_name: str,
        additional_context: Optional[Any] = None,
    ) -> str:
        """Verify generated examples before they enter an Anki field."""
        return self.run_linguistic_qa_gate(
            source_content,
            generated_text,
            step_name,
            additional_context,
            "Norwegian usage examples for an adult learner",
            "examples_text",
        )

    def verify_word_stack_with_linguistic_qa(
        self,
        input_word: str,
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Independently verify the complete CardCraft word-stack JSON."""
        candidate = json.dumps(analysis, ensure_ascii=False, indent=2)
        source = {
            "input_word": input_word,
            "required_schema": list(analysis.keys()),
        }
        contract = build_inferanki_contract(
            "CardCraft morphology and modern Bokmål word-family selection",
            source,
            None,
            "word_stack_json",
        )
        contract["invariants"].extend([
            "validate the article and grammatical gender of every Norwegian noun",
            "treat corpus surface frequency as usage evidence, not proof of part of speech",
            "exclude marginal, ambiguous, or merely possible derivations unless they are useful modern lexical entries",
            "prefer a compact semantically coherent word family over exhaustive derivation",
            "partisipp may contain only a useful present participle and must not duplicate a verb paradigm form",
        ])
        verified_text = self.run_linguistic_qa_gate(
            source,
            candidate,
            "STEP1C_WORD_STACK_LINGUISTIC_QA",
            None,
            "CardCraft morphology and modern Bokmål word-family selection",
            "word_stack_json",
            contract_override=contract,
        )
        verified = json.loads(verified_text)
        if not self._validate_analysis(verified):
            raise LinguisticQABlockedError("Verified word stack has invalid structure")
        return verified

    def verify_target_word_stack_translation(
        self,
        source_word_stack: Dict[str, Any],
        translated_word_stack: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Verify target-language lexical fidelity with an explicit locale profile."""
        target_language = self.config.get("field_1_response_lang", "English")
        contract = build_target_language_contract(
            target_language,
            source_word_stack,
        )
        evidence = build_translation_evidence_entries(source_word_stack, contract)
        candidate = json.dumps(
            translated_word_stack,
            ensure_ascii=False,
            indent=2,
        )
        verified_text = self.run_linguistic_qa_gate(
            source_word_stack,
            candidate,
            "STEP2B_TARGET_LANGUAGE_LINGUISTIC_QA",
            None,
            contract["purpose"],
            "word_stack_json",
            contract,
            evidence,
        )
        verified = json.loads(verified_text)
        if not self._validate_analysis(verified):
            raise LinguisticQABlockedError(
                "Verified target-language word stack has invalid structure"
            )
        return verified

    def verify_rendered_anki_field(
        self,
        source_content: Any,
        rendered_html: str,
        step_name: str,
    ) -> str:
        """Verify and hash the exact HTML artifact released into Anki."""
        return self.run_linguistic_qa_gate(
            source_content,
            rendered_html,
            step_name,
            None,
            "Complete rendered Norwegian learner field",
            "anki_html",
        )

    def _validate_qa_candidate(self, candidate: str, artifact_kind: str) -> bool:
        """Enforce artifact syntax independently from linguistic judgment."""
        if not isinstance(candidate, str) or not candidate.strip():
            return False
        stripped = candidate.strip()
        if artifact_kind == "word_stack_json":
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return False
            if "**" in stripped or "<b>" in stripped.lower():
                return False
            return self._validate_analysis(parsed)
        if artifact_kind in {"examples_text", "description_text"}:
            if stripped.startswith(("{", "[", "```")):
                return False
            return True
        if artifact_kind == "anki_html":
            if stripped.startswith(("{", "[", "```")):
                return False
            without_allowed_tags = re.sub(
                r"<br\s*/?>|</?(?:b|i)>",
                "",
                stripped,
                flags=re.IGNORECASE,
            )
            return re.search(r"<[A-Za-z][^>]*>", without_allowed_tags) is None
        return True

    def _validate_analysis(self, analysis: Dict[str, Any]) -> bool:        
        """Validate the structure of word analysis"""
        required_fields = {"substantiv", "adjektiv", "adverb", "verb", "partisipp"}
        if not isinstance(analysis, dict) or not required_fields.issubset(analysis):
            return False
        substantiv = analysis.get("substantiv")
        if substantiv is not None and not isinstance(substantiv, list):
            return False
        return all(
            analysis.get(field) is None or isinstance(analysis.get(field), str)
            for field in ("adjektiv", "adverb", "verb", "partisipp")
        )
    
    def _clean_null_patterns(self, text: str) -> str:
        """Clean ugly null patterns from AI responses but keep the valid word part"""
        if not text or text == "null":
            return ""
        
        import re
        
        # More aggressive cleaning: remove any pattern containing "null" with < symbols
        # This will handle "hovedsakelig < null < null" -> "hovedsakelig"
        
        # First, remove everything from the first "< null" onwards
        cleaned = re.sub(r'\s*<\s*null.*$', '', text, flags=re.IGNORECASE)
        
        # Also handle cases where null appears before the word
        cleaned = re.sub(r'^.*null\s*<\s*', '', cleaned, flags=re.IGNORECASE)
        
        # Clean any remaining standalone null words
        cleaned = re.sub(r'\bnull\b', '', cleaned, flags=re.IGNORECASE)
          # Clean up extra whitespace but preserve newlines
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)  # Only spaces and tabs, not newlines
        
        return cleaned.strip()
    
    def format_for_anki(self, analysis: Dict[str, Any]) -> Dict[str, str]:
        """
        Format word analysis for Anki card fields
        
        Args:
            analysis: Word analysis from analyze_word()
            
        Returns:
            Dictionary with formatted fields for Anki
        """
        if not analysis:
            return {}
        
        # Handle the new 5-field format - clean output without labels
        forms = []

        def _flatten_substantiv_entries(entry):
            """Yield plain strings from nested substantiv lists"""
            if isinstance(entry, list):
                for item in entry:
                    yield from _flatten_substantiv_entries(item)
            elif isinstance(entry, str):
                yield entry
            elif entry is None:
                return
            else:
                # Fallback: convert unexpected types to string to avoid crashes
                yield str(entry)

        # Handle substantiv field (can be array or string)
        substantiv = analysis.get("substantiv")
        if substantiv and substantiv != "null":
            if isinstance(substantiv, list):
                # Add multiple substantivs as separate lines, cleaning each one
                valid_substantivs = []
                for s in _flatten_substantiv_entries(substantiv):
                    if isinstance(s, str) and s and s != "null" and s.strip():
                        cleaned_s = self._clean_null_patterns(s)
                        if cleaned_s:  # Only add if something remains after cleaning
                            valid_substantivs.append(cleaned_s)
                if valid_substantivs:
                    forms.extend(valid_substantivs)  # Add each substantiv as separate line
            elif isinstance(substantiv, str) and substantiv.strip():
                cleaned_substantiv = self._clean_null_patterns(substantiv)
                if cleaned_substantiv:  # Only add if something remains after cleaning
                    forms.append(cleaned_substantiv)
        
        # Handle other fields as before
        other_fields = {
            "adjektiv": analysis.get("adjektiv"), 
            "adverb": analysis.get("adverb"),
            "verb": analysis.get("verb"),
            "partisipp": analysis.get("partisipp")
        }
        for field_value in other_fields.values():
            if field_value and field_value != "null" and field_value.strip():
                # Clean up the ugly "< null < null" patterns
                cleaned_value = self._clean_null_patterns(field_value)
                if cleaned_value:  # Only add if something remains after cleaning
                    forms.append(cleaned_value)
        
        forms_text = "<br>".join(forms) if forms else ""
        
        return {
            "Norwegian": analysis.get("input_word", ""),
            "Word_Forms": forms_text
        }
    
    def test_analysis(self, test_word: str = "god") -> bool:
        """Test word analysis functionality"""
        try:
            result = self.analyze_word(test_word)
            
            if result:
                formatted = self.format_for_anki(result)
                
                if self.config.get("debug_mode", False):
                    showInfo(f"✅ Test successful for '{test_word}':\n{json.dumps(result, indent=2, ensure_ascii=False)}")
                
                return True
            else:
                showCritical(f"❌ Test failed for '{test_word}'")
                return False
        except Exception as e:
            showCritical(f"❌ Test error: {e}")
            return False
            
    def translate_to_language(self, norwegian_json: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Translate Norwegian word forms JSON to target language from config"""
        try:
            if not self.openai_client.enabled:
                showCritical("OpenAI client not enabled")
                return None
            
            # Get target language from config
            target_language = self.config.get("field_1_response_lang", "English")
            
            # Get translator prompt
            translator_prompt = self.prompts.get("english_word_stack", {})
            
            if not translator_prompt:
                showCritical("Target language word stack prompt not found")
                return None
            
            # Convert Norwegian JSON to clean string for template
            norwegian_json_str = json.dumps(norwegian_json, ensure_ascii=False, indent=2)
            
            # Build user message with target language substitution
            user_template = translator_prompt.get("user_template", "")
            user_message = user_template.format(
                norwegian_json=norwegian_json_str,
                target_language=target_language
            )
            
            # Get system message with target language substitution
            system_message = translator_prompt.get("system_message", "")
            system_message = system_message.format(target_language=target_language)
              # Build few-shot examples from examples field
            examples_list = []
            examples_data = translator_prompt.get("examples", {})
            if examples_data:
                # Check if examples have the new structure with norwegian_input/english_output
                if "norwegian_input" in examples_data and "english_output" in examples_data:
                    norwegian_example = examples_data["norwegian_input"]
                    english_example = examples_data["english_output"]
                    
                    example_user = user_template.format(
                        norwegian_json=json.dumps(norwegian_example, ensure_ascii=False, indent=2),
                        target_language=target_language
                    )
                    example_assistant = json.dumps(english_example, ensure_ascii=False)
                    examples_list.append({
                        "user": example_user,
                        "assistant": example_assistant
                    })
                else:
                    # Old format - iterate through examples
                    for example_input, expected_result in examples_data.items():
                        example_user = user_template.format(
                            norwegian_json=json.dumps(example_input, ensure_ascii=False, indent=2),
                            target_language=target_language
                        )
                        example_assistant = json.dumps(expected_result, ensure_ascii=False)
                        examples_list.append({
                            "user": example_user,
                            "assistant": example_assistant
                        })
            
            # Update OpenAI client settings
            api_settings = translator_prompt.get("api_settings", {})
            override_kwargs = self._build_api_override_kwargs(api_settings)
            
            # Make the API call using simple_request with examples
            response = self.openai_client.simple_request(
                user_message,
                system_message,
                examples_list,
                **override_kwargs
            )
            
            # Log the API call
            request_data = {
                "system_message": system_message,
                "examples": examples_list,
                "user_message": user_message,
                "api_settings": api_settings            }
            self._log_api_call(request_data, response, "STEP2_ENGLISH_TRANSLATION")
            
            if response:
                try:
                    # Check if response is null or contains null
                    response_stripped = response.strip()
                    if response_stripped.lower() == 'null' or not response_stripped:
                        showCritical("API returned null response for English translation")
                        return None
                    
                    # Clean up common JSON formatting issues from GPT
                    # Remove "json" prefix if present
                    if response_stripped.lower().startswith('json'):
                        response_stripped = response_stripped[4:].strip()
                    
                    # Remove markdown code blocks if present
                    if response_stripped.startswith('```'):
                        lines = response_stripped.split('\n')
                        if len(lines) > 2:
                            response_stripped = '\n'.join(lines[1:-1])
                    
                    # Fix trailing commas before closing braces/brackets
                    import re
                    response_stripped = re.sub(r',(\s*[}\]])', r'\1', response_stripped)
                    
                    english_result = json.loads(response_stripped)
                    
                    # Check if the parsed result is None/null
                    if english_result is None:
                        showCritical("English translation result is null")
                        return None
                    
                    # Clean null patterns from English translation result
                    if english_result:
                        for field_name, field_value in english_result.items():
                            if isinstance(field_value, str) and field_value:
                                english_result[field_name] = self._clean_null_patterns(field_value)
                            elif isinstance(field_value, list):
                                english_result[field_name] = [
                                    self._clean_null_patterns(item) if isinstance(item, str) else item
                                    for item in field_value
                                ]
                    
                    return english_result
                except json.JSONDecodeError as e:
                    showCritical(f"Failed to parse English translation JSON: {e}\nResponse was: {response[:200]}...")
                    return None
            else:
                showCritical("No response from translation API")
                return None
            
        except Exception as e:
            showCritical(f"Translation error: {str(e)}")
            return None
    def get_description(
        self,
        word_stack: str,
        run_qa: bool = True,
    ) -> Optional[list]:
        """
        Get Norwegian description of the core concept(s) represented by the word stack
        
        Args:
            word_stack: Formatted Norwegian word stack text
            
        Returns:
            List of description strings starting with 🔸 or None if failed
        """
        try:
            if not self.openai_client.enabled:
                showCritical("OpenAI client not enabled")
                return None
              # Get description prompt
            description_prompt = self.prompts.get("norwegian_description", {})
            
            if not description_prompt:
                showCritical("Norwegian description prompt not found")
                return None
              # Build user message
            user_template = description_prompt.get("user_template", "")
            user_message = user_template.format(word_stack=word_stack)
            
            # Get system message
            system_message = description_prompt.get("system_message", "")
            
            # Build few-shot examples from examples field
            examples_list = []
            examples_data = description_prompt.get("examples", {})
            if examples_data:
                for example_input, expected_result in examples_data.items():
                    example_user = user_template.format(word_stack=example_input)
                    if isinstance(expected_result, list):
                        example_assistant = "\n".join(expected_result)
                    else:
                        example_assistant = str(expected_result)
                    examples_list.append({
                        "user": example_user,
                        "assistant": example_assistant
                    })
            
            # Update OpenAI client settings
            api_settings = description_prompt.get("api_settings", {})
            override_kwargs = self._build_api_override_kwargs(api_settings)
            
            # Make the API call with examples
            response = self.openai_client.simple_request(
                user_message,
                system_message,
                examples_list,
                **override_kwargs
            )
            
            # Log the API call
            request_data = {
                "system_message": system_message,
                "examples": examples_list,
                "user_message": user_message,
                "api_settings": api_settings
            }
            self._log_api_call(request_data, response, "STEP3_NORWEGIAN_DESCRIPTION")
            if response:
                if run_qa:
                    response = self.run_linguistic_qa_gate(
                        word_stack,
                        response,
                        "STEP3B_DESCRIPTION_LINGUISTIC_QA",
                        None,
                        "Concise Norwegian learner-facing semantic explanation",
                        "description_text",
                    )
                # Try to parse response as JSON first (in case GPT returned array)
                try:
                    import json
                    parsed_response = json.loads(response.strip())
                    if isinstance(parsed_response, list) and len(parsed_response) > 0:
                        # If it's a list with one string, extract the string
                        if len(parsed_response) == 1 and isinstance(parsed_response[0], str):
                            response = parsed_response[0]
                        else:
                            # Multiple items in list, join them
                            response = '\n'.join(str(item) for item in parsed_response)
                except (json.JSONDecodeError, ValueError):
                    # Not JSON, treat as regular text
                    pass
                
                # Parse response as text and split by lines starting with 🔸
                description_lines = []
                for line in response.strip().split('\n'):
                    line = line.strip()
                    if line.startswith('🔸'):
                        # Clean null patterns from each description line
                        cleaned_line = self._clean_null_patterns(line)
                        if cleaned_line:  # Only add if something remains after cleaning
                            description_lines.append(cleaned_line)
                
                # If no 🔸 lines found, but we have response text, add it with 🔸
                if not description_lines and response.strip():
                    response_text = self._clean_null_patterns(response.strip())
                    if response_text and not response_text.startswith('🔸'):
                        response_text = f"🔸 {response_text}"
                    if response_text:
                        description_lines.append(response_text)
                    if response_text and not response_text.startswith('🔸'):
                        response_text = f"🔸 {response_text}"
                    if response_text:
                        description_lines.append(response_text)
                
                return description_lines if description_lines else None
            else:
                showCritical("No response from description API")
                return None
            
        except LinguisticQABlockedError:
            raise
        except Exception as e:
            showCritical(f"Description error: {str(e)}")
            return None

    def get_cardcraft_content(
        self,
        norwegian_word_stack: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Generate one compact definition-and-examples pack for CardCraft."""
        try:
            if not self.openai_client.enabled:
                return None
            prompt = self.prompts.get("cardcraft_content", {})
            if not prompt:
                return None

            word_stack_json = json.dumps(
                norwegian_word_stack,
                ensure_ascii=False,
                indent=2,
            )
            user_context = prompt.get("user_context", [])
            user_message = prompt.get("user_template", "").format(
                word_stack_json=word_stack_json,
                user_context=user_context,
            )

            system_message = prompt.get("system_message", "")
            api_settings = dict(prompt.get("api_settings", {}))
            draft_model = self.config.get("openai_draft_model")
            if draft_model and "model" not in api_settings:
                api_settings["model"] = draft_model
            response = self.openai_client.simple_request(
                user_message,
                system_message,
                **self._build_api_override_kwargs(api_settings),
            )
            self._log_api_call(
                {
                    "system_message": system_message,
                    "user_message": user_message,
                    "api_settings": api_settings,
                },
                response,
                "STEP3_CARDCRAFT_CONTENT",
            )
            if not response:
                return None
            parsed = json.loads(response)
            if not isinstance(parsed, dict):
                return None
            definition = parsed.get("definition")
            usage_examples = parsed.get("usage_examples")
            context_sentences = parsed.get("context_sentences")
            if not isinstance(definition, str) or not definition.strip():
                return None
            if not isinstance(usage_examples, list) or not usage_examples:
                return None
            if not isinstance(context_sentences, list) or not context_sentences:
                return None
            usage_examples = [
                str(item).strip() for item in usage_examples if str(item).strip()
            ][:2]
            context_sentences = [
                str(item).strip() for item in context_sentences if str(item).strip()
            ][:2]
            if not usage_examples or not context_sentences:
                return None
            definition = definition.strip()
            if not definition.startswith("🔸"):
                definition = f"🔸 {definition}"
            return {
                "definition": definition,
                "usage_examples": usage_examples,
                "context_sentences": context_sentences,
            }
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
    def get_examples_simple(
        self,
        norwegian_json: Dict[str, Any],
        run_qa: bool = True,
    ) -> Optional[str]:
        """
        Generate simple usage examples for each word form in the Norwegian word stack
        
        Args:
            norwegian_json: JSON result from norwegian_word_stack
            
        Returns:
            String with usage examples or None if failed
        """
        try:
            if not self.openai_client.enabled:
                showCritical("OpenAI client not enabled")
                return None
            
            # Get examples prompt
            examples_prompt = self.prompts.get("norwegian_examples_simple", {})
            
            if not examples_prompt:
                showCritical("Norwegian examples simple prompt not found")
                return None
            
            # Convert Norwegian JSON to clean string for template
            norwegian_json_str = json.dumps(norwegian_json, ensure_ascii=False, indent=2)
              # Build user message
            user_template = examples_prompt.get("user_template", "")
            user_message = user_template.format(word_stack_json=norwegian_json_str)
            corpus_evidence = self.get_corpus_evidence(norwegian_json)
            collocation_evidence = self.get_collocation_evidence(norwegian_json)
            user_message += self.corpus_client.format_for_prompt(corpus_evidence)
            user_message += self.corpus_client.format_collocations_for_prompt(
                collocation_evidence
            )
            
            # Get system message
            system_message = examples_prompt.get("system_message", "")            # Build few-shot examples from examples field
            examples_list = []
            examples_data = examples_prompt.get("examples", [])
            if examples_data:
                # Handle both old dict format and new array format
                if isinstance(examples_data, list):
                    # New format: [{"input": "word", "output": "result"}]
                    for example in examples_data:
                        if isinstance(example, dict) and "input" in example and "output" in example:
                            example_word = example["input"]
                            expected_result = example["output"]
                            
                            # Look up the word in norwegian_word_stack examples
                            norwegian_examples = self.prompts.get("norwegian_word_stack", {}).get("examples", {})
                            if example_word in norwegian_examples:
                                example_input_json = norwegian_examples[example_word]
                                example_input_str = json.dumps(example_input_json, ensure_ascii=False, indent=2)
                                example_user = user_template.format(word_stack_json=example_input_str)
                                example_assistant = str(expected_result)
                                examples_list.append({
                                    "user": example_user,
                                    "assistant": example_assistant
                                })
                else:
                    # Old format: {"word": "result"}
                    for example_word, expected_result in examples_data.items():
                        # Look up the word in norwegian_word_stack examples
                        norwegian_examples = self.prompts.get("norwegian_word_stack", {}).get("examples", {})
                        if example_word in norwegian_examples:
                            example_input_json = norwegian_examples[example_word]
                            example_input_str = json.dumps(example_input_json, ensure_ascii=False, indent=2)
                            example_user = user_template.format(word_stack_json=example_input_str)
                            example_assistant = str(expected_result)
                            examples_list.append({
                                "user": example_user,
                                "assistant": example_assistant
                            })
            
            # Update OpenAI client settings
            api_settings = examples_prompt.get("api_settings", {})
            override_kwargs = self._build_api_override_kwargs(api_settings)

            # Make the API call with examples
            response = self.openai_client.simple_request(
                user_message,
                system_message,
                examples_list,
                **override_kwargs
            )
            request_data = {
                "system_message": system_message,
                "examples": examples_list,
                "user_message": user_message,
                "corpus_evidence": corpus_evidence,
                "collocation_evidence": collocation_evidence,
                "api_settings": api_settings,
            }
            self._log_api_call(request_data, response, "STEP4_NORWEGIAN_EXAMPLES_SIMPLE")
            if response:
                if run_qa:
                    response = self.review_examples_with_corpus(
                        norwegian_json,
                        response,
                        "STEP4B_CORPUS_REVIEW_SIMPLE_EXAMPLES",
                    )
                # Apply hardcoded processing: make noen, ens, noe italic
                processed_response = response.strip()
                
                # Clean null patterns first
                processed_response = self._clean_null_patterns(processed_response)
                
                # Replace specific words with italic formatting (case-insensitive)
                import re
                processed_response = re.sub(r'\bnoen\b', r'<i>noen</i>', processed_response, flags=re.IGNORECASE)
                processed_response = re.sub(r'\bens\b', r'<i>ens</i>', processed_response, flags=re.IGNORECASE)
                processed_response = re.sub(r'\bnoe\b', r'<i>noe</i>', processed_response, flags=re.IGNORECASE)
                
                return processed_response
            else:
                showCritical("No response from examples API")
                return None
            
        except LinguisticQABlockedError:
            raise
        except Exception as e:
            showCritical(f"Examples error: {str(e)}")
            return None

    def get_examples_sentences(
        self,
        norwegian_json: Dict[str, Any],
        user_context: Optional[list] = None,
        run_qa: bool = True,
    ) -> Optional[str]:
        """
        Generate complete Norwegian sentences for each word form in the Norwegian word stack
        
        Args:
            norwegian_json: JSON result from norwegian_word_stack
            user_context: List of context words/topics to influence sentence generation
            
        Returns:
            String with example sentences or None if failed
        """
        try:
            if not self.openai_client.enabled:
                showCritical("OpenAI client not enabled")
                return None
            
            # Get examples sentences prompt
            sentences_prompt = self.prompts.get("norwegian_examples_sentences", {})
            
            if not sentences_prompt:
                showCritical("Norwegian examples sentences prompt not found")
                return None
            
            # Convert Norwegian JSON to clean string for template
            norwegian_json_str = json.dumps(norwegian_json, ensure_ascii=False, indent=2)
            
            # Use provided user_context or default from prompt
            if user_context is None:
                user_context = sentences_prompt.get("user_context", [])
            
            # Build user message
            user_template = sentences_prompt.get("user_template", "")
            user_message = user_template.format(
                word_stack_json=norwegian_json_str,
                user_context=user_context
            )
            corpus_evidence = self.get_corpus_evidence(norwegian_json)
            collocation_evidence = self.get_collocation_evidence(norwegian_json)
            user_message += self.corpus_client.format_for_prompt(corpus_evidence)
            user_message += self.corpus_client.format_collocations_for_prompt(
                collocation_evidence
            )
            
            # Get system message
            system_message = sentences_prompt.get("system_message", "")
            
            # Build examples list
            examples_list = []
            examples_data = sentences_prompt.get("examples", [])
            if examples_data:
                for example in examples_data:
                    example_input = example.get("input", "")
                    example_context = example.get("user_context", [])
                    expected_output = example.get("output", "")
                    
                    example_user = user_template.format(
                        word_stack_json=json.dumps({"example": example_input}, ensure_ascii=False),
                        user_context=example_context
                    )
                    
                    examples_list.append({
                        "user": example_user,
                        "assistant": expected_output
                    })
            
            # Update OpenAI client settings
            api_settings = sentences_prompt.get("api_settings", {})
            override_kwargs = self._build_api_override_kwargs(api_settings)
            
            # Make the API call with examples
            response = self.openai_client.simple_request(
                user_message,
                system_message,
                examples_list,
                **override_kwargs
            )
            
            # Log the API call
            request_data = {
                "system_message": system_message,
                "examples": examples_list,
                "user_message": user_message,
                "user_context": user_context,
                "corpus_evidence": corpus_evidence,
                "collocation_evidence": collocation_evidence,
                "api_settings": api_settings
            }
            self._log_api_call(request_data, response, "STEP5_NORWEGIAN_SENTENCES")
            if response:
                if run_qa:
                    response = self.review_examples_with_corpus(
                        norwegian_json,
                        response,
                        "STEP5B_CORPUS_REVIEW_SENTENCES",
                        user_context,
                    )
                # Clean null patterns and return response text
                cleaned_response = self._clean_null_patterns(response.strip())
                cleaned_response = "\n".join(
                    line.strip()
                    for line in cleaned_response.splitlines()
                    if line.strip()
                )
                return cleaned_response
            else:
                showCritical("No response from sentences API")
                return None
            
        except LinguisticQABlockedError:
            raise
        except Exception as e:
            showCritical(f"Sentences error: {str(e)}")
            return None
