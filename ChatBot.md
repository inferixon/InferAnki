# InferAnki ChatBot Configuration Guide

## Overview

The InferAnki ChatBot is an AI-powered Norwegian language assistant integrated directly into Anki's card editor. It provides contextual help, explanations, and examples for Norwegian language learning.

## Configuration

### Basic ChatBot Settings

Edit `CardCraft/ai_prompts.json` → `chatbot` section:

```json
"chatbot": {
  "system_message": "You are an expert Norwegian language teacher...",
  "api_settings": {
    "model": "gpt-5-chat-latest",
    "temperature": 0.7,
    "max_completion_tokens": 800
  }
}
```

### Quick Prompt System

The ChatBot features a dynamic quick prompt system that automatically generates buttons based on configuration in `ai_prompts.json`. Each quick prompt:

1. Takes the current text from the input field as `{expression}`
2. Uses your configured user language as `{user_lang}`
3. Formats a pre-defined prompt template
4. Sends the formatted request to ChatGPT

### Adding New Quick Prompts

To add a new quick prompt button:

1. Open `CardCraft/ai_prompts.json`
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
  "temperature": 0.3,              // Override default temperature
  "copy_to_clipboard": false       // Control `response to clipboard`
}
```

## Tips for Creating Effective Quick Prompts

1. **Be Specific**: Clear instructions produce better results
2. **Use Context**: Include the purpose and expected format
3. **Set Appropriate Tokens**: Short answers = 400-800, detailed = 1000-1500
4. **Test Temperature**: 0.0-0.3 for factual, 0.5-0.8 for creative responses
5. **Clipboard**: Set `"copy_to_clipboard": true` if you want the response copied after each prompt.
6. **Include Examples**: Show the AI what format you want

## Troubleshooting

### Button Not Appearing
- Check JSON syntax in `ai_prompts.json`
- Restart Anki completely
- Verify the prompt is inside `"quick_prompts"` object

### Wrong Language Responses
- Check `"user_lang"` in `config.json`
- Ensure `{user_lang}` is used in prompt template
- Verify system_message language instructions

### API Errors
- Check OpenAI API key in `config.json`
- Verify internet connection
- Check token limits (max 4000 for GPT-4)

## Performance Notes

- Quick prompts clear the input field after execution
- Each prompt uses separate API calls (no conversation memory)
- Responses are optimized for brevity to save tokens
- Set appropriate `max_completion_tokens` to control costs

---

> **Remember**: Always restart Anki after modifying `ai_prompts.json` configuration!
