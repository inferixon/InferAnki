# InferAnki v0.6.3

**An application for learning Norwegian in Anki with AI-powered features**

## System Requirements

⚠️ **Important**: This add-on works **only on the Windows Desktop version of Anki**

**Reason for limitations**: The add-on integrates directly into the Anki Desktop card editor using system hooks. It relies on Windows-specific file system paths and the built-in Python environment of Anki Desktop.

### Supported Platforms:
- ✅ **Windows 10+** - fully supported
- ✅ **Anki Desktop 25.02.5+** - required
- ✅ **Python 3.9+** - bundled with Anki

### NOT supported:
- ❌ AnkiWeb (browser version)
- ❌ AnkiMobile (iOS app)
- ❌ AnkiDroid (Android app)
- ❌ macOS/Linux (for now)

## Installation

### Prepare the required API keys

**OpenAI API key**
- Go to: https://platform.openai.com/
- Register/log in to your account
- Create an API key in the API Keys section and save it in a secure place!

**ElevenLabs API key**
- Go to: https://try.elevenlabs.io/l8ypk48ku2uk
- Register/log in to your account
- Create an API key in Account Settings and save it in a secure place!
- Choose your preferred voice and save its id

### Add-on Setup

1. Make sure you have the latest version of Anki for Windows: https://apps.ankiweb.net/
2. Copy the entire `inferanki` folder to: `%APPDATA%\Anki2\addons21\`
3. Open `config.json` in any code editor.
4. Add your API keys to `config.json`:
   - Paste your OpenAI API key into `openai_api_key`
   - Paste your ElevenLabs API key into `elevenlabs_api_key`
   - Paste the voice id into `elevenlabs_voice_id`
5. Start Anki
6. Set up fields 1 and 2 as shown in the Card setup images 1-3

## Usage

1. Open the Anki card editor (Add/Edit card)
2. Use the toolbar buttons:
   - ✨ CardCraft: Analyze words and generate word stack, definitions, and usage examples
   - 📝 Examples: Generate additional examples from the content in field 2
   - 👩🏼 TTS: Speak Norwegian text with a selected voice
   - ☀️ChatGPT Assistant: Chat with GPT-5 tuned for language learning assistance

## Other Settings

Edit `config.json` to configure:
- TTS voice parameters
- AI model settings
- Translation language
- Debug mode

### Translation language setup - field 1

By default, the AI generates translations in field 1 in English. Any language is supported, even Klingon 👽. To change the translation language for field 1 (e.g., to Klingon), open `config.json` and set:

```json
{
    "field_1_response_lang": "Klingon"
}
```

**Note:** The add-on uses field indexes in the code – so field names in Anki do not affect the add-on!

**Context customization**

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

### Chatbot setup

**Detailed documentation:** See `ChatBot-uk.md` for configuring quick prompts, translation buttons, and clipboard copy features.

**NOTE!** In this version, the chatbot does not remember conversation context to save tokens. It works only in question ⇒ answer mode.

## Support

- Check debug.log for issues
- Enable debug_mode in config.json for detailed logging

### IMPORTANT! RESTART ANKI AFTER ANY SETTINGS CHANGE!!!