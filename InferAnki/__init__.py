from aqt import mw, gui_hooks # type: ignore
from aqt.editor import Editor # type: ignore
from aqt.utils import showInfo, showCritical # type: ignore
import json
import os
import re
from datetime import datetime

# Import addon modules
from .CardCraft.tts_handler import ElevenLabsTTSProcessor 

# Create alias for backward compatibility
TTSProcessor = ElevenLabsTTSProcessor

# Addon configuration
ADDON_NAME = "InferAnki"

def get_addon_version():
    """Get addon version from meta.json"""
    try:
        addon_dir = os.path.dirname(__file__)
        meta_path = os.path.join(addon_dir, "meta.json")
        
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
                return meta.get("dev_version", meta.get("human_version", "0.5.1"))
    except Exception as e:
        if CONFIG.get("debug_mode", False):
            showCritical(f"Error loading version from meta.json: {str(e)}")
    
    return "0.5.1"  # Fallback version

ADDON_VERSION = get_addon_version()

# Load addon configuration
def load_config():
    """Load configuration from config.json"""
    try:
        addon_dir = os.path.dirname(__file__)
        config_path = os.path.join(addon_dir, "config.json")
        
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        showCritical(f"Error loading config: {str(e)}")
    
    # Default configuration
    return {
        "tts_language": "no",
        "tts_enabled": True,
        "ai_enabled": True,
        "debug_mode": True
    }

# Global config
CONFIG = load_config()

# Try to import OpenAI client safely
try:
    from .CardCraft import OpenAIClient, NorwegianWordAnalyzer
    OPENAI_AVAILABLE = True
    # Removed success message to reduce noise
except ImportError as e:
    OPENAI_AVAILABLE = False
    OpenAIClient = None
    NorwegianWordAnalyzer = None
    if CONFIG.get("debug_mode", False):
        showCritical(f"❌ OpenAI not available: {e}")
except Exception as e:
    OPENAI_AVAILABLE = False
    OpenAIClient = None
    NorwegianWordAnalyzer = None
    if CONFIG.get("debug_mode", False):
        showCritical(f"❌ CardCraft loading error: {e}")

# Initialize processors
TTS_PROCESSOR = TTSProcessor(CONFIG)

# Initialize CardCraft components if available
if OPENAI_AVAILABLE and OpenAIClient and NorwegianWordAnalyzer:
    try:
        CARD_CRAFT = OpenAIClient(CONFIG)
        WORD_ANALYZER = NorwegianWordAnalyzer(CONFIG)
    except Exception as e:
        if CONFIG.get("debug_mode", False):
            showCritical(f"❌ Error initializing CardCraft components: {e}")
        CARD_CRAFT = None
        WORD_ANALYZER = None
else:
    CARD_CRAFT = None
    WORD_ANALYZER = None

def log_cardcraft_step(step_name, word, data):
    """Log CardCraft step to convert-{timestamp}.log - all 4 steps in one file"""
    try:
        # Create logs directory in addon folder
        addon_dir = os.path.dirname(__file__)
        logs_dir = os.path.join(addon_dir, "logs")
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir, exist_ok=True)
        
        # Create single log file for the complete word analysis session
        # Use only session timestamp (no word in filename for privacy)
        session_time = getattr(log_cardcraft_step, 'session_time', None)
        session_word = getattr(log_cardcraft_step, 'session_word', None)
        
        # Start new session if word changed or first call
        if session_word != word or session_time is None:
            log_cardcraft_step.session_time = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_cardcraft_step.session_word = word
            session_time = log_cardcraft_step.session_time
        
        # Use only timestamp in filename - no word for privacy
        log_file = os.path.join(logs_dir, f"convert-{session_time}.log")
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"TIMESTAMP: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"STEP: {step_name}\n")
            f.write(f"WORD: {word}\n")
            f.write(f"{'='*60}\n")
            f.write("DATA:\n")
            f.write(json.dumps(data, indent=2, ensure_ascii=False))
            f.write(f"\n{'='*60}\n\n")
    except Exception as e:
        # Also log to Anki console
        showInfo(f"Logging error: {e}")

def init_addon():
    try:
        gui_hooks.editor_did_init_buttons.append(add_editor_buttons)
        gui_hooks.webview_did_receive_js_message.append(on_js_message)
            
    except Exception as e:
        showCritical(f"Error initializing {ADDON_NAME}: {str(e)}")

def on_js_message(handled, message, context):
    """Handle JavaScript messages from editor"""
    if message.startswith("inferanki_"):
        handle_bridge_command(message, context)
        return True, None
    return handled

def add_editor_buttons(buttons, editor):
    try:
        # CardCraft AI Word Analysis button (left)
        cardcraft_button = editor._addButton(
            icon=None,
            cmd="inferanki_cardcraft",
            tip="CardCraft", 
            label="✨",  # AI magic icon
            id="inferanki_cardcraft",
            toggleable=False,
            disables=False
        )
        buttons.append(cardcraft_button)
        
        # Examples button (new)
        examples_button = editor._addButton(
            icon=None,
            cmd="inferanki_examples", 
            tip="Add Examples",
            label="📝",  # Examples icon
            id="inferanki_examples",
            toggleable=False,
            disables=False
        )
        buttons.append(examples_button)
        
        # TTS button with icon (right)
        tts_button = editor._addButton(
            icon=None,
            cmd="inferanki_tts", 
            tip="TTS",
            label="👩🏼",  # icon - Norwegian voice from Bergen
            id="inferanki_tts",
            toggleable=False,
            disables=False
        )
        buttons.append(tts_button)
        
        # ChatGPT button (v0.6)
        chatgpt_button = editor._addButton(
            icon=None,
            cmd="inferanki_chatgpt",
            tip="ChatGPT Assistant", 
            label="☀️",  # Robot emoji for better UI
            id="inferanki_chatgpt",
            toggleable=False,
            disables=False
        )
        buttons.append(chatgpt_button)
        
        # Store global reference to current editor
        globals()['current_editor'] = editor
        
    except Exception as e:
        showCritical(f"Error adding buttons: {str(e)}")

def handle_bridge_command(cmd, context=None):
    """Handle bridge commands from editor buttons"""
    try:
        # Try multiple ways to get editor instance
        editor = None
        
        # Method 1: From context
        if context and hasattr(context, 'editor'):
            editor = context.editor
        # Method 2: From global reference
        elif 'current_editor' in globals():
            editor = globals()['current_editor']
        # Method 3: From mw.editor (legacy fallback)
        elif hasattr(mw, 'editor') and mw.editor:
            editor = mw.editor
        
        if not editor:
            showCritical("No active editor found. Please ensure you're in the card editor.")
            return
            
        if cmd == "inferanki_tts":
            handle_tts_command(editor)
        elif cmd == "inferanki_cardcraft":
            handle_cardcraft_analysis(editor)
        elif cmd == "inferanki_examples":
            handle_examples_command(editor)
        elif cmd == "inferanki_chatgpt":
            handle_chatgpt_command(editor)
        elif cmd == "inferanki_ai": 
            # AI functionality disabled until v0.4.x
            showInfo("AI functionality will be available in v0.4.x")
            # handle_ai_command(editor)
    except Exception as e:
        showCritical(f"Error handling command {cmd}: {str(e)}")

def is_norsk_field_available(editor):
    """Check if Norsk field (field 2) has content"""
    try:
        if not hasattr(editor, 'note') or not editor.note:
            return False
        
        # Find Norsk field
        norsk_field_index = None
        
        # Try to find field by name first
        model = editor.note.model()
        if model and 'flds' in model:
            for i, field in enumerate(model['flds']):
                field_name = field['name']
                if field_name.lower() == CONFIG.get("field_2_name", "Norsk").lower():
                    norsk_field_index = i
                    break
        
        # If not found by name, use index 1 (second field)
        if norsk_field_index is None:
            norsk_field_index = 1
        
        # Check if field exists and has content
        if len(editor.note.fields) > norsk_field_index:
            field_content = editor.note.fields[norsk_field_index].strip()
            # Remove HTML tags for checking
            clean_content = re.sub(r'<[^>]+>', '', field_content).strip()
            return bool(clean_content)
        
        return False
    except Exception:
        return False

def handle_tts_command(editor):
    try:
        # ✨ DISABLE TTS BUTTON AT THE START ✨
        disable_tts_button(editor)
        
        # Check if Norsk field has content before processing
        if not is_norsk_field_available(editor):
            showInfo("⚠️ Norsk field is empty!")
            enable_tts_button(editor)
            return
            
        # Process TTS with real functionality - silent operation
        result = TTS_PROCESSOR.process_text(editor)
        # Success is indicated by audio appearing in the audio field
            
    except Exception as e:
        showCritical(f"TTS Error: {str(e)}")
    finally:
        # ✨ ALWAYS RE-ENABLE TTS BUTTON AT THE END ✨
        enable_tts_button(editor)

def disable_cardcraft_button(editor):
    """Disable CardCraft button during processing to prevent crashes"""
    try:
        if hasattr(editor, 'web') and hasattr(editor.web, 'eval'):
            # Enhanced JavaScript to find button by multiple methods
            js_code = """
            (function() {
                console.log('🔍 Searching for CardCraft button...');
                
                // Method 1: Try by ID
                var button = document.getElementById('inferanki_cardcraft');
                
                // Method 2: If not found by ID, try by command attribute
                if (!button) {
                    console.log('🔍 ID search failed, trying by cmd attribute...');
                    button = document.querySelector('button[cmd="inferanki_cardcraft"]');
                }
                
                // Method 3: If still not found, try by content
                if (!button) {
                    console.log('🔍 CMD search failed, trying by content...');
                    var allButtons = document.querySelectorAll('button');
                    for (var i = 0; i < allButtons.length; i++) {
                        if (allButtons[i].innerHTML.includes('✨')) {
                            button = allButtons[i];
                            console.log('🎯 Found CardCraft button by content');
                            break;
                        }
                    }
                }
                
                if (button) {
                    console.log('🔍 CardCraft button found, disabling...');
                    console.log('Button details:', {
                        id: button.id,
                        cmd: button.getAttribute('cmd'),
                        innerHTML: button.innerHTML
                    });
                    
                    // Apply disable functionality only
                    button.disabled = true;
                    
                    console.log('✅ CardCraft button disabled successfully');
                    return 'SUCCESS';
                } else {
                    console.log('❌ CardCraft button NOT FOUND by any method');
                    return 'BUTTON_NOT_FOUND';
                }
            })();
            """
            result = editor.web.eval(js_code)
            
            # If immediate disable failed, try delayed approach
            if result == 'BUTTON_NOT_FOUND':
                if CONFIG.get("debug_mode", False):
                    showInfo("⚠️ Immediate disable failed, trying delayed approach...")
                disable_cardcraft_button_delayed(editor)
            
            if CONFIG.get("debug_mode", False) and result == 'BUTTON_NOT_FOUND':
                showInfo("⚠️ CardCraft button not found - button may not be loaded yet")
            
    except Exception as e:
        if CONFIG.get("debug_mode", False):
            showInfo(f"Button disable error: {e}")

def enable_cardcraft_button(editor):
    """Re-enable CardCraft button after processing"""
    try:
        if hasattr(editor, 'web') and hasattr(editor.web, 'eval'):
            # Enhanced JavaScript to find and enable CardCraft button
            js_code = """
            (function() {
                console.log('🔍 Searching for CardCraft button to enable...');
                
                // Method 1: Try by ID
                var button = document.getElementById('inferanki_cardcraft');
                
                // Method 2: If not found by ID, try by command attribute
                if (!button) {
                    console.log('🔍 ID search failed, trying by cmd attribute...');
                    button = document.querySelector('button[cmd="inferanki_cardcraft"]');
                }
                
                // Method 3: If still not found, try by content
                if (!button) {
                    console.log('🔍 CMD search failed, trying by content...');
                    var allButtons = document.querySelectorAll('button');
                    for (var i = 0; i < allButtons.length; i++) {
                        if (allButtons[i].innerHTML.includes('✨')) {
                            button = allButtons[i];
                            console.log('🎯 Found CardCraft button by content for enabling');
                            break;
                        }
                    }
                }
                
                if (button) {
                    console.log('🔍 CardCraft button found, enabling...');
                    
                    // Apply enable functionality only
                    button.disabled = false;
                    
                    console.log('✅ CardCraft button enabled successfully');
                    return 'SUCCESS';
                } else {
                    console.log('❌ CardCraft button NOT FOUND for enabling');
                    return 'BUTTON_NOT_FOUND';
                }
            })();
            """
            result = editor.web.eval(js_code)
            
            if CONFIG.get("debug_mode", False) and result == 'BUTTON_NOT_FOUND':
                showInfo("⚠️ CardCraft button not found for enabling")
                
    except Exception as e:
        if CONFIG.get("debug_mode", False):
            showInfo(f"Button enable error: {e}")

def disable_tts_button(editor):
    """Disable TTS button during processing to prevent crashes"""
    try:
        if hasattr(editor, 'web') and hasattr(editor.web, 'eval'):
            # Enhanced JavaScript to find TTS button by multiple methods
            js_code = """
            (function() {
                console.log('🔍 Searching for TTS button...');
                
                // Method 1: Try by ID
                var button = document.getElementById('inferanki_tts');
                
                // Method 2: If not found by ID, try by command attribute
                if (!button) {
                    console.log('🔍 ID search failed, trying by cmd attribute...');
                    button = document.querySelector('button[cmd="inferanki_tts"]');
                }
                
                // Method 3: If still not found, try by content
                if (!button) {
                    console.log('🔍 CMD search failed, trying by content...');
                    var allButtons = document.querySelectorAll('button');
                    for (var i = 0; i < allButtons.length; i++) {
                        if (allButtons[i].innerHTML.includes('👩🏼')) {
                            button = allButtons[i];
                            console.log('🎯 Found TTS button by content');
                            break;
                        }
                    }
                }
                
                if (button) {
                    console.log('🔍 TTS button found, disabling...');
                    console.log('Button details:', {
                        id: button.id,
                        cmd: button.getAttribute('cmd'),
                        innerHTML: button.innerHTML
                    });
                    
                    // Apply disable functionality only
                    button.disabled = true;
                    
                    console.log('✅ TTS button disabled successfully');
                    return 'SUCCESS';
                } else {
                    console.log('❌ TTS button NOT FOUND by any method');
                    return 'BUTTON_NOT_FOUND';
                }
            })();
            """
            result = editor.web.eval(js_code)
            
            # If immediate disable failed, try delayed approach
            if result == 'BUTTON_NOT_FOUND':
                if CONFIG.get("debug_mode", False):
                    showInfo("⚠️ Immediate TTS disable failed, trying delayed approach...")
                disable_tts_button_delayed(editor)
            
            if CONFIG.get("debug_mode", False) and result == 'BUTTON_NOT_FOUND':
                showInfo("⚠️ TTS button not found - button may not be loaded yet")
            
    except Exception as e:
        if CONFIG.get("debug_mode", False):
            showInfo(f"TTS button disable error: {e}")

def enable_tts_button(editor):
    """Re-enable TTS button after processing"""
    try:
        if hasattr(editor, 'web') and hasattr(editor.web, 'eval'):
            # Enhanced JavaScript to find and enable TTS button
            js_code = """
            (function() {
                console.log('🔍 Searching for TTS button to enable...');
                
                // Method 1: Try by ID
                var button = document.getElementById('inferanki_tts');
                
                // Method 2: If not found by ID, try by command attribute
                if (!button) {
                    console.log('🔍 ID search failed, trying by cmd attribute...');
                    button = document.querySelector('button[cmd="inferanki_tts"]');
                }
                
                // Method 3: If still not found, try by content
                if (!button) {
                    console.log('🔍 CMD search failed, trying by content...');
                    var allButtons = document.querySelectorAll('button');
                    for (var i = 0; i < allButtons.length; i++) {
                        if (allButtons[i].innerHTML.includes('👩🏼')) {
                            button = allButtons[i];
                            console.log('🎯 Found TTS button by content for enabling');
                            break;
                        }
                    }
                }
                
                if (button) {
                    console.log('🔍 TTS button found, enabling...');
                    
                    // Apply enable functionality only
                    button.disabled = false;
                    
                    console.log('✅ TTS button enabled successfully');
                    return 'SUCCESS';
                } else {
                    console.log('❌ TTS button NOT FOUND for enabling');
                    return 'BUTTON_NOT_FOUND';
                }
            })();
            """
            result = editor.web.eval(js_code)
            
            if CONFIG.get("debug_mode", False) and result == 'BUTTON_NOT_FOUND':
                showInfo("⚠️ TTS button not found for enabling")
                
    except Exception as e:
        if CONFIG.get("debug_mode", False):
            showInfo(f"TTS button enable error: {e}")

def handle_cardcraft_analysis(editor):
    """Handle CardCraft AI word analysis"""
    try:
        # ✨ DISABLE CARDCRAFT BUTTON AT THE START ✨
        disable_cardcraft_button(editor)
        
        if not WORD_ANALYZER:
            showCritical("❌ CardCraft AI not available. Check OpenAI configuration.")
            enable_cardcraft_button(editor)
            return
        
        # Check if Norsk field has content before processing
        if not is_norsk_field_available(editor):
            showInfo("⚠️ Norsk field is empty!")
            enable_cardcraft_button(editor)
            return
         # Get selected text from editor
        selected_text = get_selected_text_from_editor(editor)
        
        if not selected_text:
            showInfo(f"⚠️ No word found for analysis in '{CONFIG.get('field_2_name', 'Norsk')}' field.\nAdd a word and try again.")
            enable_cardcraft_button(editor)
            return
        
        # Clean the selected text (remove extra whitespace, punctuation)
        import re
        text = selected_text.strip()
        
        if not text:
            showInfo("⚠️ Found word contains only punctuation marks.\nAdd a proper Norwegian word.")
            enable_cardcraft_button(editor)
            return

        # Use the FULL text before 🔸 for analysis, not just the last word
        word = text

        # Analyze the word (can be a single word or full text)
        result = WORD_ANALYZER.analyze_word(word)
        
        # Log Step 1
        log_cardcraft_step("STEP1_NORWEGIAN_ANALYSIS", word, {"input": word, "result": result})
        
        if result:
            # Step 1: Format Norwegian analysis and insert into field 2 (Norsk)
            formatted_norwegian = format_analysis_result(result)
            insert_analysis_into_editor(editor, formatted_norwegian, CONFIG.get("field_2_name", "Norsk"))
            
            # Step 2: Translate to English and insert into field 1 (English)
            english_result = WORD_ANALYZER.translate_to_english(result)
            
            # Log Step 2
            log_cardcraft_step("STEP2_ENGLISH_TRANSLATION", word, {"input": result, "result": english_result})
            
            if english_result:
                formatted_english = format_analysis_result(english_result)
                insert_analysis_into_editor(editor, formatted_english, CONFIG.get("field_1_name", "English"))
                
                # Step 3: Get Norwegian word description and add to Norsk field
                description_list = WORD_ANALYZER.get_description(formatted_norwegian)
                
                # Log Step 3
                log_cardcraft_step("STEP3_NORWEGIAN_DESCRIPTION", word, {"input": formatted_norwegian, "result": description_list})
                
                if description_list:
                    # Add description lines to Norwegian field with proper HTML formatting
                    description_text = "<br>".join(description_list)
                    current_norsk = get_field_content(editor, "Norsk")
                    enhanced_norsk = f"{current_norsk}<br><br>{description_text}"
                    insert_analysis_into_editor(editor, enhanced_norsk, "Norsk")
                
                # Step 4: Get usage examples and add to Norsk field
                examples_text = WORD_ANALYZER.get_examples_simple(result)
                
                # Log Step 4
                log_cardcraft_step("STEP4_AI_EXAMPLES", word, {"input": result, "result": examples_text})
                
                if examples_text:
                    # Convert Markdown bold (**text**) to HTML (<b>text</b>)
                    import re
                    examples_html = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', examples_text)
                    
                    # Replace newlines with <br> tags
                    examples_html = examples_html.replace("\n", "<br>")
                    
                    # Add examples to Norwegian field
                    current_norsk = get_field_content(editor, "Norsk")
                    enhanced_norsk = f"{current_norsk}<br><br>{examples_html}"
                    insert_analysis_into_editor(editor, enhanced_norsk, "Norsk")
                
                # Step 5: Get example sentences with user context and add to Norsk field
                # Get user_context from ai_prompts.json instead of hardcoding
                sentences_text = WORD_ANALYZER.get_examples_sentences(result)
                
                # Log Step 5
                log_cardcraft_step("STEP5_NORWEGIAN_SENTENCES", word, {"input": result, "result": sentences_text})
                
                if sentences_text:
                    # Convert Markdown bold (**text**) to HTML (<b>text</b>)
                    sentences_html = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', sentences_text)
                    
                    # Replace newlines with <br> tags
                    sentences_html = sentences_html.replace("\n", "<br>")
                    
                    # Add sentences to Norwegian field with separator
                    current_norsk = get_field_content(editor, "Norsk")
                    enhanced_norsk = f"{current_norsk}<br><br>{sentences_html}"
                    insert_analysis_into_editor(editor, enhanced_norsk, "Norsk")
            else:
                showCritical(f"⚠️ Norwegian analysis complete, but English translation failed for '{word}'")
        else:
            showCritical(f"❌ Could not analyze the word '{word}'. Please try again.")
            
    except Exception as e:
        showCritical(f"CardCraft Analysis Error: {str(e)}")
    finally:
        # ✨ ALWAYS RE-ENABLE CARDCRAFT BUTTON AT THE END ✨
        enable_cardcraft_button(editor)

def get_selected_text_from_editor(editor):
    """Get text from Norsk field, processing everything before 🔸 symbol"""
    try:
        # Find Norsk field by name first
        norsk_field_index = None
        
        if hasattr(editor, 'note') and editor.note:
            # Try to find field by name
            model = editor.note.model()
            if model and 'flds' in model:
                for i, field in enumerate(model['flds']):
                    field_name = field['name']
                    if field_name.lower() == CONFIG.get("field_2_name", "Norsk").lower():
                        norsk_field_index = i
                        break
            
            # If not found by name, try index 1 (second field)
            if norsk_field_index is None:
                norsk_field_index = 1
            
            if len(editor.note.fields) > norsk_field_index:
                field_text = editor.note.fields[norsk_field_index].strip()
                
                if field_text:
                    # Step 1: Remove everything after 🔸 symbol (including it)
                    if '🔸' in field_text:
                        field_text = field_text.split('🔸')[0]
                    
                    # Step 2: Convert HTML entities FIRST (before tag removal)
                    import re
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
                        '&ldquo;': '"',
                        '&lt;': '<',
                        '&gt;': '>'
                    }
                    
                    for entity, replacement in html_entities.items():
                        field_text = field_text.replace(entity, replacement)
                    
                    # Step 3: Convert HTML <br> tags to \n
                    field_text = re.sub(r'<br\s*/?>', '\n', field_text, flags=re.IGNORECASE)
                    
                    # Step 4: Remove other HTML tags but add spaces to prevent word concatenation
                    field_text = re.sub(r'<[^>]+>', ' ', field_text)
                    
                    # Step 5: Clean up multiple spaces but preserve line breaks
                    field_text = re.sub(r'[ \t]+', ' ', field_text)  # Multiple spaces/tabs to single space
                    field_text = re.sub(r' *\n *', '\n', field_text)  # Clean around line breaks
                    final_text = field_text.strip()
                    
                    return final_text
        
        return ""
    except Exception:
        return ""

def format_analysis_result(analysis):
    """Format word analysis for Anki display"""
    # New format: substantiv (array), adjektiv, adverb, verb, partisipp
    substantiv = analysis.get("substantiv", None)
    adjektiv = analysis.get("adjektiv", None)
    adverb = analysis.get("adverb", None)
    verb = analysis.get("verb", None)
    partisipp = analysis.get("partisipp", None)
    
    # Build clean formatted output without class labels
    lines = []
    
    # Helper function to clean null patterns
    def clean_null_patterns(text):
        """Clean ugly null patterns from AI responses"""
        if not text or text == "null":
            return ""
        
        import re
        
        # Remove everything from the first "< null" onwards
        cleaned = re.sub(r'\s*<\s*null.*$', '', text, flags=re.IGNORECASE)
        
        # Also handle cases where null appears before the word
        cleaned = re.sub(r'^.*null\s*<\s*', '', cleaned, flags=re.IGNORECASE)
        
        # Clean any remaining standalone null words
        cleaned = re.sub(r'\bnull\b', '', cleaned, flags=re.IGNORECASE)
        
        # Clean up extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        return cleaned.strip()
    
    # Handle substantiv as array or string
    if substantiv and substantiv != "null":
        if isinstance(substantiv, list):
            # Join multiple substantivs with line breaks, cleaning each one
            valid_substantivs = []
            for s in substantiv:
                if s and s != "null" and s.strip():
                    cleaned_s = clean_null_patterns(s)
                    if cleaned_s:  # Only add if something remains after cleaning
                        valid_substantivs.append(cleaned_s)
            if valid_substantivs:
                lines.extend(valid_substantivs)  # Add each substantiv as separate line
        elif isinstance(substantiv, str) and substantiv.strip():
            cleaned_substantiv = clean_null_patterns(substantiv)
            if cleaned_substantiv:  # Only add if something remains after cleaning
                lines.append(cleaned_substantiv)
    
    # Handle other fields as before, but with cleaning
    if adjektiv and adjektiv != "null" and adjektiv.strip():
        cleaned_adjektiv = clean_null_patterns(adjektiv)
        if cleaned_adjektiv:
            lines.append(cleaned_adjektiv)
    if adverb and adverb != "null" and adverb.strip():
        cleaned_adverb = clean_null_patterns(adverb)
        if cleaned_adverb:
            lines.append(cleaned_adverb)
    if verb and verb != "null" and verb.strip():
        cleaned_verb = clean_null_patterns(verb)
        if cleaned_verb:
            lines.append(cleaned_verb)
    if partisipp and partisipp != "null" and partisipp.strip():
        cleaned_partisipp = clean_null_patterns(partisipp)
        if cleaned_partisipp:
            lines.append(cleaned_partisipp)
    
    return "<br>".join(lines)

def insert_analysis_into_editor(editor, formatted_text, field_name="Norsk"):
    """Insert analysis result into specified field, clearing it first"""
    try:
        # Determine field index based on field name
        field_index = 1  # Default to field 2
        
        if field_name.lower() == CONFIG.get("field_1_name", "English").lower():
            field_index = 0  # Field 1 (configurable)
        elif field_name.lower() == CONFIG.get("field_2_name", "Norsk").lower():
            field_index = 1  # Field 2 (configurable)
        
        # Use Anki's standard way to set field content
        if hasattr(editor, 'note') and editor.note and len(editor.note.fields) > field_index:
            # Clear and set the field content directly
            editor.note.fields[field_index] = formatted_text
            
            # Update the editor display
            editor.loadNote()
            
            # Force save
            editor.saveNow(lambda: None)
        else:
            showCritical(f"❌ Failed to find field {field_name}")
            
    except Exception as e:
        showCritical(f"❌ Insert error: {str(e)}")

def handle_cardcraft_test():
    """Test CardCraft OpenAI connection"""
    try:
        if not CARD_CRAFT:
            showCritical("❌ CardCraft not available. OpenAI client not loaded.")
            return
        
        result = CARD_CRAFT.test_connection()
        
        if not result["success"]:
            showCritical(f"❌ CardCraft connection failed:\n{result['error']}")
            
    except Exception as e:
        showCritical(f"CardCraft Test Error: {str(e)}")

def get_field_content(editor, field_name):
    """Get content from specific field"""
    try:
        if not hasattr(editor, 'note') or not editor.note:
            return ""
        
        # Determine field index based on field name
        field_index = 1  # Default to field 2
        
        if field_name.lower() == CONFIG.get("field_1_name", "English").lower():
            field_index = 0  # Field 1 (configurable)
        elif field_name.lower() == CONFIG.get("field_2_name", "Norsk").lower():
            field_index = 1  # Field 2 (configurable)
        
        # Get field content
        if len(editor.note.fields) > field_index:
            return editor.note.fields[field_index]
        
        return ""
    except Exception:
        return ""

# Initialize addon when Anki starts
init_addon()

def disable_cardcraft_button_delayed(editor):
    """Disable CardCraft button with delay to ensure DOM is ready"""
    try:
        if hasattr(editor, 'web') and hasattr(editor.web, 'eval'):
            js_code = """
            setTimeout(function() {
                console.log('⏰ Delayed CardCraft button disable attempt...');
                
                // Multi-method search approach
                var button = document.getElementById('inferanki_cardcraft') ||
                           document.querySelector('button[cmd="inferanki_cardcraft"]') ||
                           Array.from(document.querySelectorAll('button')).find(btn => btn.innerHTML.includes('✨'));
                
                if (button) {
                    console.log('✅ CardCraft button found with delay, disabling...');
                    button.disabled = true;
                    console.log('✅ CardCraft button disabled with delay');
                } else {
                    console.log('❌ CardCraft button still not found after delay');
                }
            }, 100); // 100ms delay
            """
            editor.web.eval(js_code)
    except Exception as e:
        if CONFIG.get("debug_mode", False):
            showInfo(f"Delayed button disable error: {e}")

def disable_tts_button_delayed(editor):
    """Disable TTS button with delay to ensure DOM is ready"""
    try:
        if hasattr(editor, 'web') and hasattr(editor.web, 'eval'):
            js_code = """
            setTimeout(function() {
                console.log('⏰ Delayed TTS button disable attempt...');
                
                // Multi-method search approach
                var button = document.getElementById('inferanki_tts') ||
                           document.querySelector('button[cmd="inferanki_tts"]') ||
                           Array.from(document.querySelectorAll('button')).find(btn => btn.innerHTML.includes('👩🏼'));
                
                if (button) {
                    console.log('✅ TTS button found with delay, disabling...');
                    button.disabled = true;
                    console.log('✅ TTS button disabled with delay');
                } else {
                    console.log('❌ TTS button still not found after delay');
                }
            }, 100); // 100ms delay
            """
            editor.web.eval(js_code)
    except Exception as e:
        if CONFIG.get("debug_mode", False):
            showInfo(f"Delayed TTS button disable error: {e}")

def handle_examples_command(editor):
    """Handle the examples generation command."""
    try:
        # Get the current note and field content
        note = editor.note
        if not note:
            showInfo("No note selected.")
            return
        
        # Get content from Norsk field using get_field_content helper
        norsk_content = get_field_content(editor, "Norsk").strip()
        if not norsk_content:
            showInfo("Norsk field is empty.")
            return
        
        # Disable the examples button while processing
        disable_examples_button(editor)
        
        try:
            # Generate examples directly from Norsk field content
            examples = generate_examples_from_content(norsk_content)
            if not examples:
                showInfo("Could not generate examples.")
                return
            
            # Append examples to Norsk field
            updated_content = norsk_content + "<br><br>" + examples
            
            # Find Norsk field index and update it
            norsk_field_index = 1  # Default to field 2 (Norsk)
            model = note.model()
            if model and 'flds' in model:
                for i, field in enumerate(model['flds']):
                    field_name = field['name']
                    if field_name.lower() == CONFIG.get("field_2_name", "Norsk").lower():
                        norsk_field_index = i
                        break
            
            # Update the field
            if len(note.fields) > norsk_field_index:
                note.fields[norsk_field_index] = updated_content
                
                # Check if note is new (id = 0) and save appropriately
                if note.id == 0:
                    # For new notes, use editor's save method
                    editor.saveNow(lambda: None)
                else:
                    # For existing notes, use note.flush()
                    note.flush()
                
                editor.loadNote()
            
        except Exception as e:
            showInfo(f"Error generating examples: {str(e)}")
        finally:
            # Re-enable the examples button
            enable_examples_button(editor)
            
    except Exception as e:
        showInfo(f"Error in examples command: {str(e)}")


def generate_examples_from_content(content):
    """Generate example sentences from existing Norsk field content."""
    try:
        # Check if WORD_ANALYZER is available
        if not WORD_ANALYZER:
            raise Exception("CardCraft AI not available")
        
        # Get API key from CONFIG
        api_key = CONFIG.get("openai_api_key", "")
        if not api_key or api_key == "YOUR_OPENAI_API_KEY_HERE":
            raise Exception("OpenAI API key not configured")
        
        # Get prompt from ai_prompts.json
        examples_prompt = WORD_ANALYZER.prompts.get("norwegian_examples_from_content", {})
        if not examples_prompt:
            raise Exception("Examples prompt not found in ai_prompts.json")
        
        # Get user_context from prompt
        user_context = examples_prompt.get("user_context", [])
        
        # Build user message from template
        user_template = examples_prompt.get("user_template", "")
        user_message = user_template.format(content=content, user_context=user_context)
        
        # Get system message
        system_message = examples_prompt.get("system_message", "")
        
        # Update OpenAI client settings
        api_settings = examples_prompt.get("api_settings", {})
        if api_settings:
            WORD_ANALYZER.openai_client.model = api_settings.get("model", "gpt-4")
            WORD_ANALYZER.openai_client.temperature = api_settings.get("temperature", 0.3)
            WORD_ANALYZER.openai_client.max_tokens = api_settings.get("max_tokens", 400)

        # Use WORD_ANALYZER's OpenAI client for the request
        response = WORD_ANALYZER.openai_client.simple_request(
            user_message, 
            system_message
        )
        
        if not response:
            raise Exception("No response from OpenAI")
        
        # Convert Markdown bold (**text**) to HTML (<b>text</b>)
        import re
        examples_html = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', response)
        
        # Replace newlines with <br> tags
        examples_html = examples_html.replace("\n", "<br>")
        
        return examples_html
        
    except Exception as e:
        raise Exception(f"Failed to generate examples: {str(e)}")

def disable_examples_button(editor):
    """Disable Examples button during processing to prevent crashes"""
    try:
        if hasattr(editor, 'web') and hasattr(editor.web, 'eval'):
            js_code = """
            (function() {
                console.log('🔍 Searching for Examples button...');
                
                // Method 1: Try by ID
                var button = document.getElementById('inferanki_examples');
                
                // Method 2: If not found by ID, try by command attribute
                if (!button) {
                    console.log('🔍 ID search failed, trying by cmd attribute...');
                    button = document.querySelector('button[cmd="inferanki_examples"]');
                }
                
                // Method 3: If still not found, try by content
                if (!button) {
                    console.log('🔍 CMD search failed, trying by content...');
                    var allButtons = document.querySelectorAll('button');
                    for (var i = 0; i < allButtons.length; i++) {
                        if (allButtons[i].innerHTML.includes('📝')) {
                            button = allButtons[i];
                            console.log('🎯 Found Examples button by content');
                            break;
                        }
                    }
                }
                
                if (button) {
                    console.log('🔍 Examples button found, disabling...');
                    button.disabled = true;
                    console.log('✅ Examples button disabled successfully');
                    return 'SUCCESS';
                } else {
                    console.log('❌ Examples button NOT FOUND by any method');
                    return 'BUTTON_NOT_FOUND';
                }
            })();
            """
            result = editor.web.eval(js_code)
            
            if CONFIG.get("debug_mode", False) and result == 'BUTTON_NOT_FOUND':
                showInfo("⚠️ Examples button not found - button may not be loaded yet")
            
    except Exception as e:
        if CONFIG.get("debug_mode", False):
            showInfo(f"Examples button disable error: {e}")

def enable_examples_button(editor):
    """Re-enable Examples button after processing"""
    try:
        if hasattr(editor, 'web') and hasattr(editor.web, 'eval'):
            js_code = """
            (function() {
                console.log('🔍 Searching for Examples button to enable...');
                
                // Method 1: Try by ID
                var button = document.getElementById('inferanki_examples');
                
                // Method 2: If not found by ID, try by command attribute
                if (!button) {
                    console.log('🔍 ID search failed, trying by cmd attribute...');
                    button = document.querySelector('button[cmd="inferanki_examples"]');
                }
                
                // Method 3: If still not found, try by content
                if (!button) {
                    console.log('🔍 CMD search failed, trying by content...');
                    var allButtons = document.querySelectorAll('button');
                    for (var i = 0; i < allButtons.length; i++) {
                        if (allButtons[i].innerHTML.includes('📝')) {
                            button = allButtons[i];
                            console.log('🎯 Found Examples button by content for enabling');
                            break;
                        }
                    }
                }
                
                if (button) {
                    console.log('🔍 Examples button found, enabling...');
                    button.disabled = false;
                    console.log('✅ Examples button enabled successfully');
                    return 'SUCCESS';
                } else {
                    console.log('❌ Examples button NOT FOUND for enabling');
                    return 'BUTTON_NOT_FOUND';
                }
            })();
            """
            result = editor.web.eval(js_code)
            
            if CONFIG.get("debug_mode", False) and result == 'BUTTON_NOT_FOUND':
                showInfo("⚠️ Examples button not found for enabling")
                
    except Exception as e:
        if CONFIG.get("debug_mode", False):
            showInfo(f"Examples button enable error: {e}")

def handle_chatgpt_command(editor):
    """Handle ChatGPT command - open chatbot window"""
    try:
        # Disable button to prevent multiple opens
        disable_chatgpt_button(editor)
        
        if not CONFIG.get("chatbot_enabled", True):
            showInfo("ChatGPT is disabled in configuration")
            enable_chatgpt_button(editor)
            return
            
        # Import chatbot UI
        from .CardCraft.chatbot_ui import show_chatbot_dialog
        
        # Show chatbot dialog
        show_chatbot_dialog(parent=editor.parentWidget if hasattr(editor, 'parentWidget') else None, config=CONFIG)
        
    except Exception as e:
        showCritical(f"ChatGPT Error: {str(e)}")
    finally:
        # Re-enable button when dialog closes
        enable_chatgpt_button(editor)

def disable_chatgpt_button(editor):
    """Disable ChatGPT button during processing to prevent multiple requests"""
    try:
        if hasattr(editor, 'web') and hasattr(editor.web, 'eval'):
            js_code = """
            (function() {
                console.log('🔍 Searching for ChatGPT button...');
                
                // Method 1: Try by ID
                var button = document.getElementById('inferanki_chatgpt');
                
                // Method 2: If not found by ID, try by command attribute
                if (!button) {
                    button = document.querySelector('button[cmd="inferanki_chatgpt"]');
                }
                
                // Method 3: If still not found, try by content
                if (!button) {
                    var allButtons = document.querySelectorAll('button');
                    for (var i = 0; i < allButtons.length; i++) {
                        if (allButtons[i].innerHTML.includes('☀️')) {
                            button = allButtons[i];
                            break;
                        }
                    }
                }
                
                if (button) {
                    button.disabled = true;
                    console.log('✅ ChatGPT button disabled');
                    return 'SUCCESS';
                } else {
                    console.log('❌ ChatGPT button NOT FOUND');
                    return 'BUTTON_NOT_FOUND';
                }
            })();
            """
            editor.web.eval(js_code)
    except Exception as e:
        if CONFIG.get("debug_mode", False):
            showInfo(f"ChatGPT button disable error: {e}")

def enable_chatgpt_button(editor):
    """Re-enable ChatGPT button after processing"""
    try:
        if hasattr(editor, 'web') and hasattr(editor.web, 'eval'):
            js_code = """
            (function() {
                // Multi-method search for ChatGPT button
                var button = document.getElementById('inferanki_chatgpt') ||
                           document.querySelector('button[cmd="inferanki_chatgpt"]') ||
                           Array.from(document.querySelectorAll('button')).find(btn => btn.innerHTML.includes('☀️'));
                
                if (button) {
                    button.disabled = false;
                    console.log('✅ ChatGPT button enabled');
                } else {
                    console.log('❌ ChatGPT button NOT FOUND for enabling');
                }
            })();
            """
            editor.web.eval(js_code)
    except Exception as e:
        if CONFIG.get("debug_mode", False):
            showInfo(f"ChatGPT button enable error: {e}")
