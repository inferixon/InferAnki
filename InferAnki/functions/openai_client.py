# CardCraft HTTP Client
# Simple HTTP-based OpenAI client without dependencies

import json
import urllib.request
import urllib.parse
import ssl

try:
    from aqt.utils import showInfo, showCritical # type: ignore
    ANKI_AVAILABLE = True
except ImportError:
    ANKI_AVAILABLE = False
    # Fallback functions for testing without Anki
    def showInfo(text):
        print(f"INFO: {text}")
    def showCritical(text):
        print(f"CRITICAL: {text}")


class OpenAIClient:
    """Simple HTTP-based OpenAI client for Chat Completions API"""
    
    def __init__(self, config):
        self.config = config
        self.api_key = config.get("openai_api_key", "")
        self.model = config.get("openai_default_model", "gpt-4.1")  # Use default_model as fallback
        self.temperature = config.get("ai_temperature", 0.3)
        self.max_tokens = config.get("ai_max_tokens", 1500)
        self.base_url = "https://api.openai.com/v1"
        
        # Check availability
        self.enabled = self._check_availability()
    
    def _prepare_request_data(
        self,
        messages,
        custom_model=None,
        custom_temperature=None,
        custom_max_tokens=None,
        response_format=None
    ):
        """Prepare request payload with optional per-call overrides"""
        model = custom_model or self.model
        temperature = custom_temperature if custom_temperature is not None else self.temperature
        max_tokens = custom_max_tokens if custom_max_tokens is not None else self.max_tokens
        
        data = {
            "model": model,
            "messages": messages
        }
        if response_format:
            data["response_format"] = response_format
        
        # Handle different parameter formats for different model families
        normalized_model = model.lower()
        if "gpt-5" in normalized_model:
            # GPT-5 uses max_completion_tokens and may have temperature restrictions
            data["max_completion_tokens"] = max_tokens
            # Current GPT-5 chat endpoints only expose default temperature=1.0
            if abs(temperature - 1.0) > 1e-6 and self.config.get("debug_mode", False):
                print("InferAnki: GPT-5 chat models ignore custom temperature; falling back to default 1.0")
        else:
            # GPT-4 and older models use standard parameters
            data["max_tokens"] = max_tokens
            data["temperature"] = temperature
        
        return data
    
    def _check_availability(self):
        """Check if OpenAI is configured"""
        if not self.api_key or self.api_key == "your-api-key-here":
            return False
        return True
    
    def _make_request(self, endpoint, data):
        """Make HTTP request to OpenAI API"""
        try:
            url = f"{self.base_url}/{endpoint}"
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}',
                'User-Agent': 'InferAnki-CardCraft/1.0'
            }
            
            # Prepare request
            json_data = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(url, data=json_data, headers=headers)
            
            # Create SSL context (for HTTPS)
            ssl_context = ssl.create_default_context()
            
            # Make request
            with urllib.request.urlopen(req, context=ssl_context, timeout=30) as response:
                response_data = json.loads(response.read().decode('utf-8'))
                return {"success": True, "data": response_data}
                
        except urllib.error.HTTPError as e: # type: ignore
            error_body = e.read().decode('utf-8')
            try:
                error_data = json.loads(error_body)
                error_msg = error_data.get('error', {}).get('message', f'HTTP {e.code}')
            except:
                error_msg = f'HTTP {e.code}: {error_body}'
            return {"success": False, "error": error_msg}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def test_connection(self):
        """Test basic connection to OpenAI"""
        if not self.enabled:
            return {"success": False, "error": "OpenAI not configured (check API key)"}
        
        # Prepare messages
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello in one word."}
        ]
        
        # Use _prepare_request_data with custom max_tokens for quick test
        data = self._prepare_request_data(messages, custom_max_tokens=10)
        
        result = self._make_request("chat/completions", data)
        
        if result["success"]:
            try:
                message = result["data"]["choices"][0]["message"]["content"]
                return {
                    "success": True, 
                    "response": message.strip(), 
                    "model": self.model
                }
            except (KeyError, IndexError) as e:
                return {"success": False, "error": f"Invalid response format: {e}"}
        else:
            return {"success": False, "error": result["error"]}
    def simple_request(
        self,
        prompt,
        system_message="You are a helpful assistant.",
        examples=None,
        custom_model=None,
        custom_temperature=None,
        custom_max_tokens=None,
        response_format=None
    ):
        """Make a simple request to OpenAI with optional few-shot examples"""
        if not self.enabled:
            return None
        
        # Build messages list
        messages = [{"role": "system", "content": system_message}]
        
        # Add few-shot examples if provided
        if examples:
            for example in examples:
                if isinstance(example, dict) and "user" in example and "assistant" in example:
                    messages.append({"role": "user", "content": example["user"]})
                    messages.append({"role": "assistant", "content": example["assistant"]})
        
        # Add the actual user prompt
        messages.append({"role": "user", "content": prompt})
        
        # Use _prepare_request_data to handle model-specific parameters
        data = self._prepare_request_data(
            messages,
            custom_model=custom_model,
            custom_temperature=custom_temperature,
            custom_max_tokens=custom_max_tokens,
            response_format=response_format
        )
        
        result = self._make_request("chat/completions", data)
        
        if result["success"]:
            try:
                message = result["data"]["choices"][0]["message"]["content"]
                return message.strip() if message else None
            except (KeyError, IndexError):
                return None
        else:
            if self.config.get("debug_mode", False):
                showCritical(f"OpenAI request failed: {result['error']}")
            return None
    
    def simple_request_with_usage(
        self,
        prompt,
        system_message="You are a helpful assistant.",
        examples=None,
        custom_model=None,
        custom_temperature=None,
        custom_max_tokens=None,
        response_format=None
    ):
        """Make a simple request to OpenAI with optional few-shot examples, return response and usage info"""
        if not self.enabled:
            return None, None
        
        # Build messages list
        messages = [{"role": "system", "content": system_message}]
        
        # Add few-shot examples if provided
        if examples:
            for example in examples:
                if isinstance(example, dict) and "user" in example and "assistant" in example:
                    messages.append({"role": "user", "content": example["user"]})
                    messages.append({"role": "assistant", "content": example["assistant"]})
        
        # Add the actual user prompt
        messages.append({"role": "user", "content": prompt})
        
        # Use _prepare_request_data to handle model-specific parameters
        data = self._prepare_request_data(
            messages,
            custom_model=custom_model,
            custom_temperature=custom_temperature,
            custom_max_tokens=custom_max_tokens,
            response_format=response_format
        )
        
        result = self._make_request("chat/completions", data)
        
        if result["success"]:
            try:
                response_data = result["data"]
                message = response_data["choices"][0]["message"]["content"]
                usage_info = response_data.get("usage", {})
                
                return message.strip() if message else None, usage_info
            except (KeyError, IndexError):
                return None, None
        else:
            if self.config.get("debug_mode", False):
                showCritical(f"OpenAI request failed: {result['error']}")
            return None, None
