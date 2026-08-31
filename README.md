# InferAnki 0.6

AI-assisted Norwegian vocabulary tooling for the Anki Desktop card editor.

Current development build: `0.6.9`.

## Features

- **CardCraft** – builds a Norwegian word-family card from one word, adds a definition, usage examples, contextual sentences, and a translation in the configured target language.
- **Examples** – generates two reviewed Norwegian examples from the source phrase, normalizes field 2 spacing, and fills an empty field 1 with a target-language translation. Append `* your instruction` to request a specific context.
- **TTS** – generates Norwegian audio through ElevenLabs and attaches it to the note.
- **ChatGPT Assistant** – provides free-form chat, eight configurable quick prompts, clipboard actions, and session-local conversation history. Open it from the editor, the Anki toolbar, the Tools menu, or with `Ctrl+G`.

CardCraft and Examples can use frequency and collocation evidence from the National Library of Norway DH-LAB corpus. Compact draft stages use Luna, while independent review and repair stages use Terra before content is written to the note. Long-running operations use Anki's native progress dialog, and generated card fields are applied together only after the pipeline succeeds.

## Requirements

- Anki Desktop `25.02.5` or newer
- An internet connection for AI, corpus, and TTS requests
- An OpenAI API key for CardCraft, Examples, and ChatGPT Assistant
- An ElevenLabs API key only if TTS is used

The add-on is developed and tested on Windows 10/11. AnkiWeb and Anki mobile clients cannot run desktop add-ons, but they can display synced cards and audio created by InferAnki. Other desktop operating systems are not currently tested.

## Installation

1. Download or clone this repository.
2. Copy the `InferAnki` folder to `%APPDATA%\Anki2\addons21\`.
3. Open the copied `InferAnki/config.json`.
4. Replace `YOUR_OPENAI_API_KEY_HERE` with your OpenAI API key.
5. If using TTS, replace `YOUR_ELEVENLABS_API_KEY_HERE` with your ElevenLabs API key. The bundled configuration uses the Emma voice by default.
   [Try ElevenLabs](https://try.elevenlabs.io/l8ypk48ku2uk)
6. Restart Anki.

InferAnki expects at least two note fields:

- **Field 1** – translation in `field_1_response_lang`
- **Field 2** – Norwegian source and generated learning content

Field names do not matter; the add-on uses field positions.

## Usage

Open the Add or Edit window and use the editor buttons:

- `✨` – run CardCraft for the Norwegian word in field 2
- `📝` – generate or replace examples from the source phrase in field 2
- `👩🏼` – generate ElevenLabs audio from field 2
- `☀️` – open ChatGPT Assistant

Examples supports a one-off instruction after an asterisk. For example:

```text
et sjakkbrett * use only chess-related situations
```

## Configuration

`config.json` is the single source of truth for shared runtime settings.

| Setting | Purpose |
| --- | --- |
| `openai_default_model` | Shared OpenAI model; default is `gpt-5.6-terra` |
| `openai_draft_model` | Fast model for compact drafts; default is `gpt-5.6-luna` |
| `openai_reasoning_effort` | Shared reasoning level |
| `openai_text_verbosity` | Shared response verbosity |
| `openai_timeout_seconds` | Optional OpenAI request timeout; defaults to 120 seconds and accepts 30–600 |
| `field_1_response_lang` | Translation language written to field 1 |
| `user_lang` | User-language value available to ChatGPT prompt templates |
| `chatbot_max_history` | Number of completed message pairs retained per dialog |
| `tts_enabled` | Enables or disables ElevenLabs TTS |
| `tts_progress_threshold_chars` | Shows native TTS progress above this cleaned-text length |
| `openai_usage_log_enabled` | Writes secret-free token usage telemetry |
| `corpus_enabled` | Enables Norwegian corpus evidence |
| `corpus_eval_enabled` | Enables corpus-backed review and repair loops |
| `debug_mode` | Enables additional diagnostics |

Prompt-specific token limits and exceptional model overrides live in `prompts.json`. Normally, change the shared model only in `config.json`.

### Personal context

The public preset contains empty `user_context` arrays. To bias generated examples toward your interests, replace the relevant arrays in `prompts.json`, for example:

```json
"user_context": ["medisin", "helse", "sykehus"]
```

Keep the values short and concrete. Quick prompts are configured separately under `chatbot.quick_prompts`.

### Corpus evaluation

The default corpus settings query Norwegian newspaper material from 2000–2025 through the DH-LAB API. Frequency evidence helps reject implausible or obsolete forms; collocation evidence helps prefer attested modern usage. The corpus client itself fails open when the service is unavailable, while required evaluation stages may stop a generated result rather than write weak content to the note.

Corpus behavior can be adjusted with the `corpus_*` settings in `config.json`.

## Logs and troubleshooting

- Restart Anki after changing `config.json` or `prompts.json`.
- CardCraft logs: `InferAnki/logs/convert-*.log`
- Linguistic QA receipts: `InferAnki/logs/linguistic-qa-*.json`
- Exact OpenAI usage: `InferAnki/logs/openai-usage.jsonl`
- Add or increase `openai_timeout_seconds` in `config.json` if long requests time out.
- Set `debug_mode` to `true` for more visible error dialogs.
- API calls use your own OpenAI and ElevenLabs accounts and may incur provider charges.

For ChatGPT Assistant customization, see [ChatBot.md](ChatBot.md). Ukrainian documentation is available in [README-uk.md](README-uk.md) and [ChatBot-uk.md](ChatBot-uk.md).

## Screenshots

![CardCraft](images/CardCraft-01.jpg)

![Examples](images/Examples-01.jpg)

![ChatGPT Assistant](images/Chatbot.jpg)

## Contributing

Bug reports and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).
