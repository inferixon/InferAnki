# InferAnki v0.6.3

**Norwegian Language Learning Add-on for Anki with AI-powered features**


## Required API Keys

### OpenAI API Key
- Go to: https://platform.openai.com/
- Register/log into your account
- Create an API key in the API Keys section

### ElevenLabs API Key
- Go to: https://try.elevenlabs.io/l8ypk48ku2uk
- Register/log into your account
- Create an API key in Account Settings
- Select your desired voice and save its ID


## Installation Steps

1. Copy the entire inferanki folder to: `%APPDATA%\Anki2\addons21\`
2. Open `config.json` and add your API keys:
   - Copy the OpenAI API key to the `openai_api_key` field
   - Copy the ElevenLabs API key to the `elevenlabs_api_key` field
   - Copy the voice ID to the `elevenlabs_voice_id` field
3. Restart Anki
4. Configure fields 1 and 2 as shown in the images


## Usage

1. Open the Anki card editor (Add/Edit card)
2. Use the toolbar buttons:
   - ✨ WordCraft: Word analysis and generation of word stack, definitions, and usage examples
   - 📝 Examples: Generate additional examples from existing content in field 2
   - 👩🏼 TTS: Text-to-speech for Norwegian text
   - ☀️ChatGPT Assistant: Chat with GPT-5 configured to help with language learning

## Configuration

Edit `config.json` to configure:
- TTS voice settings
- AI model settings
- Translation language
- Debug mode

### Translation Language Configuration - Field 1

By default, AI generates translations in field 1 in English. **Available languages:** Any language, even Klingon. To change field 1 language to another (e.g., Ukrainian), open `config.json` and replace:

```json
{
    "field_1_response_lang": "Ukrainian"
}
```

**Note:** The add-on automatically uses field indexes in the code – so the field names in Anki do not affect anything!

**Context Configuration**

To personalize AI-generated examples for your field/interests:

1. Open: `prompts.json`
2. Find: `"user_context": []`
3. Replace with your context, for example:
   - Medicine: `["medisin", "helse", "sykehus"]`
   - Business: `["økonomi", "business", "ledelse"]`
   - IT: `["programmering", "teknologi", "data"]`
   - Education: `["utdanning", "skole", "læring"]`
   - Law: `["jus", "lov", "rettsvesen"]`

This makes AI examples more relevant to your field when learning Norwegian vocabulary.

### Chatbot Configuration

**Detailed Documentation:** See `ChatBot.md` for configuring quick prompts, translation buttons, and clipboard copy functionality.

**WARNING!** In this version, the Chatbot doesn't remember conversation context to save tokens. It only works in question ⇒ answer mode.


## Support

- Check debug.log for issues
- Enable debug_mode in config.json for detailed logging


### IMPORTANT! RESTART ANKI AFTER ANY CONFIGURATION CHANGES!!!