# Free LLM chain for Aria

Order used by the backend:

1. **Groq** — `GROQ_API_KEY`, optional `GROQ_MODEL`
2. **Gemini** — `GEMINI_API_KEY`, optional `GEMINI_MODEL=gemini-3.8-flash`
3. **OpenRouter** — `OPENROUTER_API_KEY`, optional `OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct:free`
4. **Hugging Face** — `HF_TOKEN` (or `HUGGINGFACE_TOKEN`), optional `HF_MODEL`
5. **Rules + local NN** — always on, no key

All free tiers have rate limits. Keys stay only on Render Environment — never in the repo.

## Get keys

| Provider | URL |
|----------|-----|
| Groq | https://console.groq.com/keys |
| Gemini | https://aistudio.google.com/apikey |
| OpenRouter | https://openrouter.ai/keys |
| Hugging Face | https://huggingface.co/settings/tokens |

Not free for app use: xAI Grok API, OpenAI, Claude (paid).
