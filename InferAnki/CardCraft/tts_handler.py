import os
import re
import tempfile
import json
from datetime import datetime
from pathlib import Path

# Anki imports - make optional for testing
try:
    from aqt.utils import showInfo, showCritical # type: ignore
    from aqt import mw # type: ignore
    from anki.utils import stripHTML # type: ignore
    ANKI_AVAILABLE = True
except ImportError:
    # Mock functions for testing outside Anki
    def showInfo(msg): print(f"INFO: {msg}")
    def showCritical(msg): print(f"CRITICAL: {msg}")
    def stripHTML(text): return re.sub(r'<[^>]+>', '', text)
    mw = None
    ANKI_AVAILABLE = False

# ElevenLabs API imports
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

class ElevenLabsTTSProcessor:
    """Handle ElevenLabs TTS processing for Anki cards with Norwegian optimization"""
    
    def __init__(self, config):
        self.config = config
        self.language = config.get("tts_language", "nor")  # Norwegian ISO 639-3 code
        self.enabled = config.get("tts_enabled", True)
        self.max_chars = config.get("tts_max_chars", 40000)  # Flash v2.5 supports 40,000 chars
        self.field_name = config.get("tts_field_name", "Norsk")
        
        # ElevenLabs TTS configuration
        self.api_key = config.get("elevenlabs_api_key", "")
        self.voice_id = config.get("elevenlabs_voice_id", "")  # Will be set based on voice name
        self.voice_name = config.get("tts_voice", "Emma")  # Default to Emma (Norwegian native)
        self.model = config.get("elevenlabs_model", "eleven_flash_v2_5")  # Flash v2.5 with Norwegian support
        self.language_code = config.get("elevenlabs_language_code", "no")  # ISO 639-1 code (no=Norwegian, en=English)
        self.stability = config.get("elevenlabs_stability", 0.75)  # Stable for consistent quality
        self.similarity_boost = config.get("elevenlabs_similarity_boost", 0.75)
        self.style = config.get("elevenlabs_style", 0.0)
        self.use_speaker_boost = config.get("elevenlabs_speaker_boost", True)
        self.speech_rate = config.get("elevenlabs_speech_rate", 0.8)  # Speech rate: 0.5-2.0 (0.8 = 20% slower)
        
        # Output format optimization for smaller files
        self.output_format = config.get("elevenlabs_output_format", "mp3_22050_64")  # Smaller, good quality
        
        # Privacy and performance settings
        self.enable_logging = config.get("elevenlabs_enable_logging", False)  # Disable for privacy
        self.seed = config.get("elevenlabs_seed", None)  # Deterministic generation
        
        # Norwegian voice recommendations (including native speakers)
        self.norwegian_voices = {
            "Emma": "b3jcIbyC3BSnaRu8avEk",       # 🇳🇴 Native from Bergen! (recommended)
            "Rachel": "21m00Tcm4TlvDq8ikWAM",     # Female, clear, versatile
            "Domi": "AZnzlk1XvdvUeBnXmlld",       # Female, young, energetic  
            "Bella": "EXAVITQu4vr4xnSDxMaL",      # Female, calm, mature
            "Antoni": "ErXwobaYiN019PkySvjV",     # Male, deep, professional
            "Josh": "TxGEqnHWrfWFTfGW9XjX",       # Male, young, friendly
            "Arnold": "VR6AewLTigWG4xSOukaG",     # Male, mature, authoritative
            "Adam": "pNInz6obpgDQGcFmaJgB",       # Male, deep, narrator
            "Sam": "yoZ06aMxZJJ28mfd3POQ"         # Male, casual, conversational
        }
        
        # Set voice ID based on voice name
        if self.voice_name in self.norwegian_voices:
            self.voice_id = self.norwegian_voices[self.voice_name]
        elif not self.voice_id:
            self.voice_id = self.norwegian_voices["Emma"]  # Default to Emma from Bergen
          # Check API availability
        if not REQUESTS_AVAILABLE:
            showCritical("ElevenLabs TTS requires 'requests' library")
            self.enabled = False
        elif not self.api_key or self.api_key == "your-api-key-here":
            if config.get("debug_mode", False):
                showInfo("ElevenLabs API key not configured in config.json")
                
    def process_text_for_tts(self, text):
        """Process text with comprehensive HTML cleaning for Norwegian TTS"""
        if not text or not isinstance(text, str):
            return ""
        input_text = text.strip()
        
        # DEBUG: Add version marker to logs to confirm new code is running
        debug_marker = " [v0.3.22-FIXED]"
        
        # FIRST: Remove 🔸 bullet content (improved logic)
        # Pattern 1: 🔸 content with <br><br> ending
        input_text = re.sub(r'(?:<[^>]*>)?🔸.*?<br\s*/?>\s*<br\s*/?>', '', input_text, flags=re.IGNORECASE | re.DOTALL)
        # Pattern 2: 🔸 content at end of text
        input_text = re.sub(r'(?:<[^>]*>)?🔸.*$', '', input_text, flags=re.IGNORECASE | re.DOTALL)
        
        # SECOND: Convert HTML entities BEFORE tag removal (but keep &lt; and &gt; for now)
        html_entities = {
            '&nbsp;': ' ',
            '&amp;': '&',
            '&quot;': '"',
            '&apos;': "'",
            '&#39;': "'",
            '&mdash;': '—',
            '&ndash;': '–',
            '&hellip;': '...',
            '&rsquo;': "'",
            '&lsquo;': "'",
            '&rdquo;': '"',
            '&ldquo;': '"'
        }
        
        for entity, replacement in html_entities.items():
            input_text = input_text.replace(entity, replacement)
        
        # THIRD: Handle HTML tags with content preservation
        # Replace <br><br> (double) with longer pause for clear separation
        input_text = re.sub(r'<br\s*/?>\s*<br\s*/?>', ' ... ', input_text, flags=re.IGNORECASE)
        # Replace single <br> with medium pause for word separation
        input_text = re.sub(r'<br\s*/?>', ' .. ', input_text, flags=re.IGNORECASE)
        
        # Handle list items - add pause between list items
        input_text = re.sub(r'</li>\s*<li[^>]*>', ' .. ', input_text, flags=re.IGNORECASE)
        input_text = re.sub(r'</?li[^>]*>', ' ', input_text, flags=re.IGNORECASE)
        input_text = re.sub(r'</?ul[^>]*>', ' ', input_text, flags=re.IGNORECASE)
        input_text = re.sub(r'</?ol[^>]*>', ' ', input_text, flags=re.IGNORECASE)
        
        # Handle div tags - add spacing between divs
        input_text = re.sub(r'</div>\s*<div[^>]*>', ' .. ', input_text, flags=re.IGNORECASE)
        input_text = re.sub(r'</?div[^>]*>', ' ', input_text, flags=re.IGNORECASE)
        
        # FOURTH: Strip remaining HTML tags (comprehensive approach)
        # Remove all HTML tags but preserve content
        input_text = re.sub(r'<[^>]+>', '', input_text)
        
        # FIFTH: Now convert remaining HTML entities that could interfere with text
        input_text = input_text.replace('&lt;', '<')
        input_text = input_text.replace('&gt;', '>')
          # SIXTH: Norwegian text processing
        # Handle pipe-separated words (Norwegian learning) - convert all | to commas
        input_text = re.sub(r'\s*\|\s*', ', ', input_text)
        
        # Handle dashes - convert to commas ONLY when surrounded by spaces (preserve within words like "PC-en")
        input_text = re.sub(r'\s+-\s+', ', ', input_text)
        
        # Handle angle brackets (< >) - convert to commas as well  
        input_text = re.sub(r'\s*<\s*', ', ', input_text)
        input_text = re.sub(r'\s*>\s*', ', ', input_text)
        
        # Force pause after every real linebreak
        input_text = re.sub(r'\r?\n+', ' ... ', input_text)
        
        # Convert multiple dots to pauses (use placeholders to prevent interference)
        input_text = re.sub(r'\.{4,}', '⟨LONG_PAUSE⟩', input_text)
        input_text = re.sub(r'\.{3}', '⟨LONG_PAUSE⟩', input_text)
        input_text = re.sub(r'\.{2}', '⟨MED_PAUSE⟩', input_text)
        
        # Convert placeholders to final pause format
        input_text = re.sub(r'⟨LONG_PAUSE⟩', ' ... ', input_text)
        input_text = re.sub(r'⟨MED_PAUSE⟩', ' .. ', input_text)
        
        # SEVENTH: Clean up spacing and whitespace
        input_text = re.sub(r'\s+', ' ', input_text)  # Multiple spaces to single
        input_text = input_text.strip()
          # LOG: Record processed text with version marker
        if self.config.get("debug_mode", False):
            try:
                logs_dir = r"a:\KODEKRAFT\PROJECTS\InferAnki\logs"
                os.makedirs(logs_dir, exist_ok=True)
                log_file = os.path.join(logs_dir, "convert.log")
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"[{timestamp}] ORIGINAL: {repr(text)}\n")
                    f.write(f"[{timestamp}] PROCESSED{debug_marker}: {input_text}\n")
            except:
                pass

        # Apply speech rate control using SSML (if not default rate)
        if hasattr(self, 'speech_rate') and self.speech_rate != 1.0:
            input_text = f'<prosody rate="{self.speech_rate}">{input_text}</prosody>'
        
        # Final check - if result is empty, return empty
        if not input_text:
            return ""
      
        return input_text
    
    def create_audio_file(self, text):
        """Create MP3 audio file using ElevenLabs TTS"""
        if not self.enabled or not REQUESTS_AVAILABLE:
            return None
            
        try:
            # Process text with SSML markup
            processed_text = self.process_text_for_tts(text)
            if not processed_text or not processed_text.strip():
                return None
            
            # ElevenLabs API endpoint with privacy setting
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream?enable_logging=false"
            headers = {
                "xi-api-key": self.api_key,
                "Content-Type": "application/json"
            }
            data = {
                "text": processed_text,
                "model_id": self.model,
                "language_code": self.language_code,  # Language code from config (no=Norwegian, en=English)
                "voice_settings": {
                    "stability": self.stability,  # type: ignore
                    "similarity_boost": self.similarity_boost,
                    "style": self.style,
                    "use_speaker_boost": self.use_speaker_boost
                },
                "apply_text_normalization": "auto"  # Auto text normalization
            }
            
            # Make API request with timeout
            response = requests.post(url, headers=headers, json=data, timeout=30, stream=True)
            
            if response.status_code != 200:
                error_msg = f"ElevenLabs TTS API error: {response.status_code}"
                try:
                    error_details = response.json()
                    error_msg += f" - {error_details.get('detail', 'Unknown error')}"
                except:
                    pass
                showCritical(error_msg)
                return None
            
            # Create temporary file
            now = datetime.now().strftime('%y%m%d-%H%M%S')
            filename = f"inferanki-elevenlabs-tts-{now}.mp3"
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, filename)
            
            # Save audio file
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return temp_path
            
        except requests.exceptions.Timeout:
            showCritical("ElevenLabs TTS request timed out (30 seconds). Try with shorter text.")
            return None
        except requests.exceptions.RequestException as e:
            showCritical(f"Network error with ElevenLabs TTS: {str(e)}")
            return None
        except Exception as e:
            showCritical(f"Error creating ElevenLabs TTS audio: {str(e)}")
            return None
    
    def get_field_content(self, editor, field_name):
        """Get raw HTML content from specific field"""
        try:
            if hasattr(editor, 'note') and editor.note:
                if field_name in editor.note:
                    return editor.note[field_name]
            return ""
        except Exception as e:
            if self.config.get("debug_mode", False):
                showCritical(f"Error getting field content: {str(e)}")
            return ""
    
    def clear_audio_field(self, editor):
        """Clear audio field without questions"""
        try:
            if hasattr(editor, 'note') and editor.note:
                audio_fields = ['Audio', 'audio', 'Sound', 'sound']
                for field in audio_fields:
                    if field in editor.note:
                        editor.note[field] = ""
                        break
        except Exception as e:
            pass
    
    def add_audio_to_note(self, editor, audio_path):
        """Add audio file to note"""
        try:
            if not os.path.exists(audio_path):
                showCritical("Audio file not found")
                return False
                
            filename = os.path.basename(audio_path)
            
            # Add file to Anki media collection (only if in Anki environment)
            if mw and hasattr(mw, 'col') and mw.col:
                media_name = mw.col.media.addFile(audio_path)
            else:
                media_name = filename
                showInfo(f"TEST MODE: Would add audio file {filename}")
            
            # Add audio reference to note
            if hasattr(editor, 'note') and editor.note:
                audio_fields = ['Audio', 'audio', 'Sound', 'sound']
                audio_field = None
                
                for field in audio_fields:
                    if field in editor.note:
                        audio_field = field
                        break
                
                if audio_field:
                    audio_tag = f"[sound:{media_name}]"
                    editor.note[audio_field] = audio_tag
                    return True
                else:
                    showCritical("No audio field found (looking for: Audio, audio, Sound, sound)")
                    return False
            
            return False
            
        except Exception as e:
            showCritical(f"Error adding audio to note: {str(e)}")
            return False
    
    def process_text(self, editor):
        """Main TTS processing function"""
        if not self.enabled:
            showInfo("ElevenLabs TTS is disabled in configuration")
            return False
            
        if not REQUESTS_AVAILABLE:
            showCritical("ElevenLabs TTS requires 'requests' library")
            return False
        
        if not self.api_key or self.api_key == "your-api-key-here":
            showCritical("ElevenLabs API key not configured. Please add 'elevenlabs_api_key' to config.json")
            return False
            
        try:
            # Get text from specified field
            text = self.get_field_content(editor, self.field_name)
            
            if not text or not text.strip():
                showInfo(f"Field '{self.field_name}' is empty. Please add text to generate TTS audio.")
                return False
                
            # Check character limit
            if len(text) > self.max_chars:
                showCritical(f"Text too long ({len(text)} chars). Max allowed: {self.max_chars}")
                return False
            
            # Clear existing audio (silent processing)
            self.clear_audio_field(editor)
            
            # Create audio file
            audio_path = self.create_audio_file(text)
            if not audio_path:
                showCritical("Failed to create audio file")
                return False
                
            # Add audio to note
            success = self.add_audio_to_note(editor, audio_path)
            if success:
                # Update editor display (only if in Anki environment)
                if ANKI_AVAILABLE and hasattr(editor, 'loadNote'):
                    editor.loadNote()
                
                # Clean up temporary file
                try:
                    os.remove(audio_path)
                except:
                    pass
                    
                return True
            else:
                showCritical("Failed to add audio to note")
                return False
                
        except Exception as e:
            showCritical(f"ElevenLabs TTS processing error: {str(e)}")
            return False

# Maintain backward compatibility
TTSHandler = ElevenLabsTTSProcessor
TTSProcessor = ElevenLabsTTSProcessor
