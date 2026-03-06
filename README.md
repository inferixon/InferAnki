# InferAnki v0.6.7

**AI-powered Anki add-on to help you learn Norwegian**

## What is Anki?

**Anki** is a **free** flashcard app that uses **spaced repetition**. This is one of the most effective, research-backed ways to memorize information, proven by cognitive psychology studies.

**Official website:** https://apps.ankiweb.net/

Anki is available on both computers and smartphones—so you can study anywhere, with your progress synced via the cloud.

### Scientific Background

**Ebbinghaus’ Forgetting Curve** (1885) shows how quickly we lose new information.

Without review, we forget:
- **50%** of information in 20 minutes
- **70%** in a day
- **90%** in a week

**Spaced repetition** changes this: by reviewing material at optimal intervals, you move information from short-term to long-term memory with minimal effort.

### How does Anki work?

Anki calculates **optimal review intervals** for each card. After seeing a card, you rate how hard it was to recall, and Anki automatically schedules the next review:
- “Easy” cards are shown less often.
- “Hard” cards are reviewed more frequently.

The system adapts to your learning pace.

**Result:** Instead of rote memorization, you remember material efficiently and for the long term, spending just 15–20 minutes a day.

### Why Anki + InferAnki?

InferAnki brings **AI power** to Anki. It adds four buttons to the card editor toolbar:

- ✨ **CardCraft**: Generate a complete card from a single word. GPT-5.2 finds related words, definitions, usage examples, and adds a translation in your chosen language.
- 📝 **Examples**: Create extra examples from the text in field 2.
- 👩🏼 **TTS**: Generate high-quality AI Norwegian audio for your text.
- ☀️ **ChatGPT Assistant**: Chat with GPT-5.2 for detailed help, with quick prompts and copy-to-clipboard (e.g., for translations).

The add-on uses custom prompts to control AI quality. You can flexibly adjust these prompts to your needs.

## System Requirements

⚠️ **Important:** This add-on works **only on the Windows Desktop version of Anki**

 **Why:** The add-on integrates directly into the Anki Desktop card editor using system hooks, Windows-specific file paths, and the built-in Python environment in Anki Desktop. This means you can only run the add-on on Windows, but you can use the generated cards (with audio) on other platforms.

### You need:
- ✅ **Windows 10 or newer**
- ✅ **Latest Anki Desktop for Windows**
- ✅ **Built-in Python and Qt** (included with Anki)

### NOT supported:
- ❌ AnkiWeb (browser version)
- ❌ AnkiMobile (iOS app)
- ❌ AnkiDroid (Android app)
- ❌ macOS/Linux (for now)

## Installation

### Prepare your API keys

**OpenAI API key**
- Go to: https://platform.openai.com/
- Sign up/log in
- Create an API key in the API Keys section and save it securely!

**ElevenLabs API key**
- Go to: https://try.elevenlabs.io/l8ypk48ku2uk
- Sign up/log in
- Create an API key in Account Settings and save it securely!
- Choose your preferred voice and save its id

### Add-on Setup

1. Make sure you have the latest Anki for Windows: https://apps.ankiweb.net/
2. Copy the entire `inferanki` folder to: `%APPDATA%\Anki2\addons21\`
3. Open `config.json` in any code editor.
4. Add your API keys to `config.json`:
   - Add your OpenAI API key to `openai_api_key`
   - Add your ElevenLabs API key to `elevenlabs_api_key`
   - Add your voice id to `elevenlabs_voice_id`
5. Start Anki
6. Set up fields 1 and 2 as shown in Card setup images 1–3

## Usage

1. Open the Anki card editor (Add/Edit card)
2. Enter a Norwegian word in field 2
3. Use the toolbar buttons:
   - ✨ **CardCraft** – add full content to field 2 and translation to field 1
   - 📝 **Examples** – add relevant usage examples to field 2 (field 2 must have at least one Norwegian word)
   - 👩🏼 **TTS-Emma** – add audio for field 2
   - ☀️ **ChatGPT Assistant** – open the AI chat window

## Other Settings

Edit `config.json` to adjust:
- TTS voice parameters
- AI model settings
- Translation language
- Debug mode

### Translation language – field 1

By default, AI generates translations in field 1 in English. Any language is possible—even Klingon 👽. To change the translation language (e.g., to Klingon), open `config.json` and set:

```json
{
    "field_1_response_lang": "Klingon"
}
```

**Note:** The add-on uses field indexes in code—field names in Anki do not affect the add-on!

**Context settings**

To personalize AI-generated examples for your field/interests:

1. Open: `prompts.json`
2. Find: `"user_context": []`
3. Replace with your context, e.g.:
   - Medicine: `["medisin", "helse", "sykehus"]`
   - Business: `["økonomi", "business", "ledelse"]`
   - IT: `["programmering", "teknologi", "data"]`
   - Education: `["utdanning", "skole", "læring"]`
   - Law: `["jus", "lov", "rettsvesen"]`

This makes AI examples more relevant to your field when learning Norwegian vocabulary.

### Chatbot settings

**Full documentation:** See `ChatBot-uk.md` for quick prompts, translation buttons, and clipboard copy setup.

**Conversation memory**: The chatbot remembers the last 10 message pairs within each dialog session for coherent multi-turn conversations. Each new window starts fresh.

## Support

- Check `debug.log` for issues
- Enable `debug_mode` in `config.json` for detailed logging

### IMPORTANT! RESTART ANKI AFTER ANY SETTINGS CHANGE!!!