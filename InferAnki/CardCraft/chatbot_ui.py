# ChatBot UI for InferAnki v0.6
# Qt-based chat interface for Norwegian language assistance

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel)  # type: ignore
from PyQt6.QtCore import Qt, QThread, pyqtSignal     # type: ignore
from PyQt6.QtGui import QFont, QKeySequence # type: ignore
import json
import os

try:
    from aqt.utils import showInfo, showCritical # type: ignore
    ANKI_AVAILABLE = True
except ImportError:
    ANKI_AVAILABLE = False
    def showInfo(text): print(f"INFO: {text}")
    def showCritical(text): print(f"CRITICAL: {text}")

# Import OpenAI client
try:
    from . import OpenAIClient
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAIClient = None


class ChatWorker(QThread):
    """Worker thread for ChatGPT API calls"""
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, message, config, prompts):
        super().__init__()
        self.message = message
        self.config = config
        self.prompts = prompts
        
    def run(self):
        """Execute ChatGPT API call in background thread"""
        try:
            if not OPENAI_AVAILABLE or not OpenAIClient:
                self.error_occurred.emit("OpenAI client not available")
                return
                
            # Create OpenAI client
            openai_client = OpenAIClient(self.config)
            
            # Get chatbot prompt from ai_prompts.json
            chatbot_prompt = self.prompts.get("chatbot", {})
            if not chatbot_prompt:
                self.error_occurred.emit("ChatBot prompt not found in ai_prompts.json")
                return
                
            # Get system message and API settings
            system_message = chatbot_prompt.get("system_message", "")
            api_settings = chatbot_prompt.get("api_settings", {})
            
            # Update client settings if provided
            if api_settings:
                openai_client.model = api_settings.get("model", "gpt-4")
                openai_client.temperature = api_settings.get("temperature", 0.7)
                openai_client.max_tokens = api_settings.get("max_tokens", 2000)
            
            # Make API request
            response = openai_client.simple_request(self.message, system_message)
            
            if response:
                self.response_ready.emit(response)
            else:
                self.error_occurred.emit("No response from ChatGPT")
                
        except Exception as e:
            self.error_occurred.emit(f"ChatGPT error: {str(e)}")


class ChatBotDialog(QDialog):
    """ChatGPT dialog window for Norwegian language assistance"""
    
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.config = config or {}
        self.chat_history = []
        self.max_history = self.config.get("chatbot_max_history", 10)
        self.prompts = self.load_prompts()
        self.worker_thread = None
        self.setWindowTitle("InferAnki ChatGPT Assistant")
        self.setMinimumSize(700, 600)
        self.resize(800, 700)
        
        # Make window non-modal and allow it to work in background
        self.setModal(False)
        
        self.setup_ui()
        self.add_welcome_message()
    
    def load_prompts(self):
        """Load AI prompts from ai_prompts.json"""
        try:
            # Get the directory where this file is located
            current_dir = os.path.dirname(__file__)
            prompts_path = os.path.join(current_dir, "ai_prompts.json")
            
            if os.path.exists(prompts_path):
                with open(prompts_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            if ANKI_AVAILABLE:
                showCritical(f"Error loading prompts: {e}")
        return {}
    
    def setup_ui(self):
        """Setup the chat interface"""
        layout = QVBoxLayout()
        
        # Chat history display (readonly)
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setPlaceholderText("Ask me anything about Norwegian language, grammar, vocabulary...")
          # Set larger font - Palatino Linotype 14
        chat_font = QFont("Palatino Linotype", 14)
        self.chat_display.setFont(chat_font)
        
        layout.addWidget(self.chat_display)
        
        # Input section
        input_layout = QHBoxLayout()
        
        # User input field - 3-line QTextEdit with word wrap
        self.input_field = QTextEdit()
        self.input_field.setPlaceholderText("Type your question here... (Enter to send, Shift+Enter for new line)")
        self.input_field.setMinimumHeight(80)  # Minimum 3 lines
        self.input_field.setMaximumHeight(200)  # Maximum height to prevent taking too much space
        self.input_field.setAcceptRichText(False)  # Plain text only
        self.input_field.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        
        # Set larger font for input field
        input_font = QFont("Palatino Linotype", 14)
        self.input_field.setFont(input_font)
        
        # Override keyPressEvent for Enter/Shift+Enter handling
        def handle_key_press(event):
            if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    # Shift+Enter: insert new line
                    self.input_field.insertPlainText('\n')
                else:
                    # Enter: send message
                    self.send_message()
            else:
                # Default handling for other keys
                QTextEdit.keyPressEvent(self.input_field, event)
        
        self.input_field.keyPressEvent = handle_key_press
        
        input_layout.addWidget(self.input_field)
        
        # Send button
        self.send_button = QPushButton("Send")
        self.send_button.setMaximumWidth(80)
        self.send_button.setFixedHeight(80)  # Initial height, will be adjusted by auto-resize
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button)
        
        # Auto-resize functionality (moved after send_button creation)
        def adjust_height():
            # Get document height
            doc_height = self.input_field.document().size().height()
            font_height = self.input_field.fontMetrics().height()
            
            # Calculate needed height (with some padding)
            needed_height = int(doc_height + 20)  # 20px padding
            
            # Clamp between min and max
            new_height = max(80, min(200, needed_height))
            self.input_field.setFixedHeight(new_height)
            
            # Update send button height to match
            self.send_button.setFixedHeight(new_height)
        
        # Connect text change to auto-resize
        self.input_field.textChanged.connect(adjust_height)
        
        # Initial adjustment
        adjust_height()
        
        layout.addLayout(input_layout)
          # Status label
        self.status_label = QLabel("Ready to help with Norwegian language!")
        self.status_label.setStyleSheet("color: green; font-style: italic;")        
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        
        # Focus on input field
        self.input_field.setFocus()
        
    def add_welcome_message(self):
        """Add welcome message to chat"""
        welcome = "<h3>I'm your Norwegian language assistant!</h3><br>How can I help you?"
        self.add_to_chat("☀️ ChatGPT", welcome)
        
    def test_connection(self):
        """Test ChatGPT connection"""
        if not OPENAI_AVAILABLE or not OpenAIClient:
            self.add_to_chat("☀️ ChatGPT", "❌ OpenAI client not available")
            return False
            
        api_key = self.config.get("openai_api_key", "")
        if not api_key or api_key == "YOUR_OPENAI_API_KEY_HERE":
            self.add_to_chat("☀️ ChatGPT", "❌ API key not configured")
            return False
            
        self.add_to_chat("☀️ ChatGPT", "✅ Connection test successful!")
        return True
        
    def send_message(self):
        """Handle sending user message"""
        user_message = self.input_field.toPlainText().strip()
        
        if not user_message:
            return
            
        # Check OpenAI availability
        if not OPENAI_AVAILABLE or not OpenAIClient:
            self.add_to_chat("☀️ ChatGPT", "❌ OpenAI client not available. Please check your configuration.")
            return
              # Check API key
        api_key = self.config.get("openai_api_key", "")
        if not api_key or api_key == "YOUR_OPENAI_API_KEY_HERE":
            self.add_to_chat("☀️ ChatGPT", "❌ OpenAI API key not configured. Please add your API key to config.json.")
            return
        
        # Clear input field and disable controls
        self.input_field.clear()
        self.input_field.setEnabled(False)
        self.send_button.setEnabled(False)
        
        # Add user message to chat
        self.add_to_chat("You", user_message)
        
        # Update status
        self.status_label.setText("Thinking...")
        self.status_label.setStyleSheet("color: orange; font-style: italic;")
        
        # Add to chat history (limit to max_history)
        self.chat_history.append({"role": "user", "content": user_message})
        if len(self.chat_history) > self.max_history:
            self.chat_history.pop(0)
        
        # Start worker thread for API call
        self.worker_thread = ChatWorker(user_message, self.config, self.prompts)
        self.worker_thread.response_ready.connect(self.on_response_ready)
        self.worker_thread.error_occurred.connect(self.on_error_occurred)
        self.worker_thread.finished.connect(self.on_worker_finished)
        self.worker_thread.start()
        
    def on_response_ready(self, response):
        """Handle successful ChatGPT response"""
        self.add_to_chat("☀️ ChatGPT", response)
        
        # Add to chat history
        self.chat_history.append({"role": "assistant", "content": response})
        if len(self.chat_history) > self.max_history:
            self.chat_history.pop(0)
            
        # Update status
        self.status_label.setText("Ready to help!")
        self.status_label.setStyleSheet("color: green; font-style: italic;")
        
    def on_error_occurred(self, error_message):
        """Handle ChatGPT API errors"""
        self.add_to_chat("☀️ ChatGPT", f"❌ {error_message}")
          # Update status
        self.status_label.setText("Error occurred. Please try again.")
        self.status_label.setStyleSheet("color: red; font-style: italic;")
        
    def on_worker_finished(self):
        """Re-enable controls when worker thread finishes"""
        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.input_field.setFocus()
        
        # Clean up worker thread
        if self.worker_thread:
            self.worker_thread.deleteLater()
            self.worker_thread = None
    
    def add_to_chat(self, sender, message):
        """Add message to chat display"""        # Convert Markdown to HTML for Anki compatibility
        html_message = self.convert_markdown_to_html(message)
        
        if sender == "You":
            chat_html = f'<div style="margin-bottom: 15px;"><b style="color: #6AB7FF;">👤 You:</b><br>{html_message}<br></div>'
        else:
            chat_html = f'<div style="margin-bottom: 15px;"><b style="color: #4CAF50;">{sender}:</b><br>{html_message}<br></div>'
            
        self.chat_display.append(chat_html)
          # Scroll to bottom
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def convert_markdown_to_html(self, text):
        """Convert Markdown formatting to HTML for Anki"""
        import re
        
        # Convert #### Header to <b>Header</b> (bold instead of h4)
        text = re.sub(r'^#### (.*?)$', r'<b>\1</b>', text, flags=re.MULTILINE)
        
        # Convert ### Header to <h3>Header</h3>
        text = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
        
        # Convert ## Header to <h2>Header</h2>
        text = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
        
        # Convert # Header to <h1>Header</h1>
        text = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
        
        # Convert **bold** to <b>bold</b>
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        
        # Convert *italic* to <i>italic</i>
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
        
        # Convert bullet points - to •
        text = re.sub(r'^- (.*?)$', r'• \1', text, flags=re.MULTILINE)
        
        # Convert Markdown tables to HTML tables
        text = self._convert_markdown_tables(text)
        
        # Convert newlines to <br>
        text = text.replace('\n', '<br>')
        
        # Convert --- to horizontal line
        text = re.sub(r'^---$', '<hr>', text, flags=re.MULTILINE)
        
        return text
        
    def _convert_markdown_tables(self, text):
        """Convert Markdown tables to HTML tables"""
        import re
        
        # Split text into lines
        lines = text.split('\n')
        result_lines = []
        in_table = False
        table_rows = []
        
        for line in lines:
            # Check if line looks like a table row (contains |)
            if '|' in line.strip() and line.strip().startswith('|') and line.strip().endswith('|'):
                if not in_table:
                    in_table = True
                    table_rows = []
                
                # Clean up the row and split by |
                row = line.strip()[1:-1]  # Remove first and last |
                cells = [cell.strip() for cell in row.split('|')]
                table_rows.append(cells)
                
            elif '|' in line.strip() and not line.strip().startswith('|'):
                # Handle tables without starting/ending |
                if not in_table:
                    in_table = True
                    table_rows = []
                
                cells = [cell.strip() for cell in line.split('|')]
                table_rows.append(cells)
                
            elif in_table and line.strip() == '':
                # Empty line ends table
                if table_rows:
                    html_table = self._build_html_table(table_rows)
                    result_lines.append(html_table)
                    table_rows = []
                in_table = False
                result_lines.append(line)
                
            elif in_table and not ('|' in line or line.strip().startswith('|')):
                # Non-table line ends table
                if table_rows:
                    html_table = self._build_html_table(table_rows)
                    result_lines.append(html_table)
                    table_rows = []
                in_table = False
                result_lines.append(line)
                
            else:
                # Regular line
                if in_table and table_rows:
                    # End of input while in table
                    html_table = self._build_html_table(table_rows)
                    result_lines.append(html_table)
                    table_rows = []
                    in_table = False
                result_lines.append(line)
        
        # Handle table at end of text
        if in_table and table_rows:
            html_table = self._build_html_table(table_rows)
            result_lines.append(html_table)
        
        return '\n'.join(result_lines)
     
    def _build_html_table(self, rows):
        """Build HTML table from rows"""
        if not rows:
            return ""
        
        # Check if second row is separator (indicates first row is header)
        has_header = (len(rows) > 1 and 
                     all(cell.strip() in ['---', '-', ''] or cell.strip().startswith('-') 
                         for cell in rows[1]))
        
        html = '<table border="1" style="border-collapse: collapse; margin: 10px 0; width: 100%;">'
        html += '<tbody>'
        
        for i, row in enumerate(rows):
            # Skip separator rows (like |---|---|)
            if all(cell.strip() in ['---', '-', ''] or cell.strip().startswith('-') for cell in row):
                continue
                
            html += '<tr>'
            for cell in row:
                # Make first row bold if it's a header
                if i == 0 and has_header:
                    html += f'<td style="padding: 8px;"><b>{cell}</b></td>'
                else:
                    html += f'<td style="padding: 8px;">{cell}</td>'
            html += '</tr>'
        
        html += '</tbody>'
        html += '</table>'
        return html
        
    def closeEvent(self, event):
        """Handle dialog close"""
        # Stop worker thread if running
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.terminate()
            self.worker_thread.wait()
        event.accept()


def show_chatbot_dialog(parent=None, config=None):
    """Show the ChatBot dialog"""
    dialog = ChatBotDialog(parent, config)
    dialog.show()
    return dialog
