# InferAnki v0.6.3

**Norwegian Language Learning Add-on for Anki with AI-powered features**

## Installation Steps

1. Copy the entire inferanki folder to: `%APPDATA%\Anki2\addons21\`
2. Edit config.json and add your API keys
3. Restart Anki

## Required API Keys

### 1. OpenAI API Key
- Go to: https://platform.openai.com/
- Register/log into your account
- Create an API key in the API Keys section
- Copy it to the `openai_api_key` field in `config.json`

### 2. ElevenLabs API Key
- Go to: https://try.elevenlabs.io/l8ypk48ku2uk
- Register/log into your account
- Get your API key in Account Settings
- Copy it to the `elevenlabs_api_key` field in `config.json`
- Select your desired voice
- Copy the voice ID to the `elevenlabs_voice_id` field in `config.json`

## Usage

1. Open the Anki card editor (Add/Edit card)
2. Use the toolbar buttons:
   - ✨ CardCraft: Word analysis and generation of word stack, definitions, and usage examples
   - 📝 Examples: Generate additional examples from existing content in field 2
   - 👩🏼 TTS: Text-to-speech for Norwegian text
   - ☀️ChatGPT Assistant: Chat with an AI assistant configured to help with language learning

## Configuration

Edit config.json to configure:
- TTS voice settings
- AI model settings
- Translation language
- Debug mode

### Field 1 Language Configuration

By default, AI generates translations in field 1 in English.
To change field 1 language to another language (e.g., Ukrainian), simply edit config.json. Open config.json and replace this field:

```json
{
    "field_1_response_lang": "Ukrainian"
}
```

**Available languages:** Any language, even Klingon. The add-on automatically uses field indexes – custom field names in Anki do not matter!

### AI Context Configuration

To personalize AI-generated examples for your field/interests:

1. Open: CardCraft/ai_prompts.json
2. Find: `"user_context": ["vitenskap", "kodekraft", "3d tegning bransje"]`
3. Replace with your context, for example:
   - Medicine: `["medisin", "helse", "sykehus"]`
   - Business: `["økonomi", "business", "ledelse"]`
   - IT: `["programmering", "teknologi", "data"]`
   - Education: `["utdanning", "skole", "læring"]`
   - Law: `["jus", "lov", "rettsvesen"]`

This makes AI examples more relevant to your field when learning Norwegian vocabulary.

### Chatbot Configuration

To personalize the Norwegian language ChatBot assistant:

1. Open: CardCraft/ai_prompts.json
2. Find the "chatbot" section
3. Configure system_message for desired behavior:

**Configuration Ideas:**
- Use specific instructions in system_message
- Specify the desired response language
- Indicate your Norwegian level for complexity adaptation
- For advanced users: "Du er en norsk språkekspert. Svar på norsk med detaljerte forklaringer. Fokuser på nyanser, dialekter og kulturelle aspekter."
- For specialized fields: "You are a Norwegian teacher specializing in business/medical/technical Norwegian. Focus on professional vocabulary and formal language patterns."
- Add quick commands and descriptions. Example: "Handle these quick commands: *u [text] = translate [text] to Ukrainian, ..."
- Experiment with "temperature" (0.0-1.0, higher = more creative responses)
- Maximum response length "max_tokens" for token usage control

> **WARNING!** In this version, the Chatbot doesn't remember conversation context to save tokens. It only works in question ⇒ answer mode.

## Support

- Check debug.log for issues
- Enable debug_mode in config.json for detailed logging

> **IMPORTANT!** RESTART ANKI AFTER ANY CONFIGURATION CHANGES!!!
