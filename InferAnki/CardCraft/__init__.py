# CardCraft - AI Integration Module for InferAnki
# Version: 0.5.1

"""
CardCraft: AI-powered card crafting for InferAnki
Transforms Norwegian language learning with GPT-powered analysis
"""

__version__ = "0.5.1"
__author__ = "Inferix"

from .openai_client import OpenAIClient
from .wordstack import NorwegianWordAnalyzer
from .chatbot_ui import show_chatbot_dialog

__all__ = ["OpenAIClient", "NorwegianWordAnalyzer", "show_chatbot_dialog"]
