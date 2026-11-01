# Aria / Notify — free ML

## What is trained in-repo (no Colab required)

| Model | Type | Hold-out accuracy (synthetic) | Runtime |
|-------|------|-------------------------------|--------|
| Intent classifier | Torch mean-pool MLP → pure Python | **100%** on synthetic phrases | Free on Render |
| Rules extractor | Regex | N/A | Free |

**Honest limit:** high scores on *synthetic* English templates. Real messy chat will score lower until we log and retrain on *your* messages.

### Retrain on Google Colab (free GPU)

1. Open [Google Colab](https://colab.research.google.com/) with your Google account.
2. New notebook → paste the training script from `scripts/train_intent_colab.py` in this repo (or ask the assistant to regenerate it).
3. Runtime → Run all.
4. Download `intent_model.json` + `intent_emb.json`.
5. Commit them under `backend/alerts/`.

## ChatGPT-like understanding (still free tier)

Local models will not match GPT quality. Use a **free API key**:

### Option A — Groq (recommended free speed)

1. Create account: https://console.groq.com/
2. Create API key.
3. Render → Environment:
   - `GROQ_API_KEY=gsk_...`
   - optional `GROQ_MODEL=llama-3.1-8b-instant`
4. Redeploy. Chat will prefer LLM when the key is set; rules+NN remain fallback.

### Option B — Google Gemini free tier

1. https://aistudio.google.com/apikey
2. Render env: `GEMINI_API_KEY=...`

### Option C — Hugging Face Inference (free tier limits)

1. https://huggingface.co/settings/tokens
2. `HF_TOKEN=...`

## What you do not need to pay for

- Intent NN training (CPU in Colab free or this agent)
- Rule-based reminders / weather / news
- Hosting the small classifier on Render free

## What still is not free

- Always-on wake-word JARVIS on locked phones
- Unlimited GPT-4 class traffic
