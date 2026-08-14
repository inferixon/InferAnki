# CardCraft - AI Integration Module for InferAnki


"""
CardCraft: AI-powered card crafting for InferAnki
Transforms Norwegian language learning with GPT-powered analysis
"""

__version__ = "0.6.8"
__author__ = "Inferix"

from .openai_client import OpenAIClient
from .corpus_client import CorpusEvidenceClient
from .wordstack import NorwegianWordAnalyzer
from .chatbot_ui import show_chatbot_dialog

__all__ = ["OpenAIClient", "CorpusEvidenceClient", "NorwegianWordAnalyzer", "show_chatbot_dialog"]
