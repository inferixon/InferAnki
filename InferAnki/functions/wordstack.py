# -*- coding: utf-8 -*-
"""
CardCraft Word Family Analyzer
Norwegian Bokmål word analysis using OpenAI GPT-4.1
"""

import json
import os
import re
from typing import Dict, Optional, Any
from datetime import datetime

try:
    from aqt.utils import showInfo, showCritical # type: ignore
    ANKI_AVAILABLE = True
except ImportError:
    ANKI_AVAILABLE = False

    def showInfo(text): print(f"INFO: {text}")
    def showCritical(text): print(f"CRITICAL: {text}")

from .openai_client import OpenAIClient


class NorwegianWordAnalyzer:
    """Analyze Norwegian Bokmål words using AI"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.openai_client = OpenAIClient(config)
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
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
    def _validate_analysis(self, analysis: Dict[str, Any]) -> bool:        
        """Validate the structure of word analysis"""
        # Check for new format fields including partisipp
        required_fields = ["substantiv", "adjektiv", "adverb", "verb", "partisipp"]
        
        return True
    
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
    def get_description(self, word_stack: str) -> Optional[list]:
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
            
        except Exception as e:
            showCritical(f"Description error: {str(e)}")
            return None
    def get_examples_simple(self, norwegian_json: Dict[str, Any]) -> Optional[str]:
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
            if response:
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
            
        except Exception as e:
            showCritical(f"Examples error: {str(e)}")
            return None

    def get_examples_sentences(self, norwegian_json: Dict[str, Any], user_context: Optional[list] = None) -> Optional[str]:
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
                "api_settings": api_settings
            }
            self._log_api_call(request_data, response, "STEP5_NORWEGIAN_SENTENCES")
            if response:
                # Clean null patterns and return response text
                cleaned_response = self._clean_null_patterns(response.strip())
                return cleaned_response
            else:
                showCritical("No response from sentences API")
                return None
            
        except Exception as e:
            showCritical(f"Sentences error: {str(e)}")
            return None
