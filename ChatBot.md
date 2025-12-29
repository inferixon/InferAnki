# InferAnki ChatBot Configuration Guide

## Overview

The InferAnki ChatBot is an AI-powered Norwegian language assistant integrated directly into Anki's card editor. It provides contextual help, explanations, and examples for Norwegian language learning.

## Configuration

### Basic ChatBot Settings

Edit `prompts.json` → `chatbot` section:

```json
"chatbot": {
  "system_message": "You are an expert Norwegian language teacher...",
  "api_settings": {
    "model": "gpt-5.2-chat-latest",
    "max_completion_tokens": 800
  }
}
```

### Quick Prompt System

The ChatBot features a dynamic quick prompt system that automatically generates buttons based on configuration in `prompts.json`. Each quick prompt:

1. Takes the current text from the input field as `{expression}`
2. Uses your configured user language as `{user_lang}`
3. Formats a pre-defined prompt template
4. Sends the formatted request to ChatGPT

### Adding New Quick Prompts

To add a new quick prompt button:

1. Open `prompts.json`
2. Find `"chatbot" → "quick_prompts"`
3. Add your new prompt:

```json
"prompt_your_new_function": {
  "description": "What this prompt does",
  "button_text": "BUTTON_TEXT",
  "prompt_template": "Your prompt here with {expression} and replies in {user_lang}",
  "max_completion_tokens": 1000
}
```


4. Restart Anki - the button will appear automatically!


## Template Variables

Available variables in `prompt_template`:

- `{expression}` - Text from user input field
- `{user_lang}` - User's language from config.json

## API Settings Per Prompt

Each quick prompt can override default API settings:

```json
"prompt_example": {
  "button_text": "EXAMPLE",
  "prompt_template": "...",
  "max_completion_tokens": 1500,  // Override default token limit
  "copy_to_clipboard": false       // Control `response to clipboard`
}
```

Temperature overrides only apply to models that expose the parameter (e.g., GPT-4.x). GPT-5.2 chat models ignore this value even if it is present.

## Tips for Creating Effective Quick Prompts

1. **Be Specific**: Clear instructions produce better results
2. **Use Context**: Include the purpose and expected format
3. **Set Appropriate Tokens**: Short answers = 400-800, detailed = 1000-1500
4. **Clipboard**: Set `"copy_to_clipboard": true` if you want the response copied after each prompt.
5. **Include Examples**: Show the AI what format you want

## Troubleshooting

### Button Not Appearing
- Check JSON syntax in `prompts.json`
- Restart Anki completely
- Verify the prompt is inside `"quick_prompts"` object

### Wrong Language Responses
- Check `"user_lang"` in `config.json`
- Ensure `{user_lang}` is used in prompt template
- Verify system_message language instructions

### API Errors
- Check OpenAI API key in `config.json`
- Verify internet connection

## Performance Notes

- Quick prompts clear the input field after execution
- **Conversation memory**: ChatBot remembers the last 10 message pairs (20 messages total) within each dialog session
- Each new dialog window starts with a clean slate (no cross-session memory)
- Context history is sent with each API request for coherent multi-turn conversations
- Responses are optimized for brevity to save tokens
- Set appropriate `max_completion_tokens` to control costs

---

> **Remember**: Always restart Anki after modifying `prompts.json` configuration!
