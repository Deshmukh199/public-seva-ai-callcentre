# Public Seva AI Call Centre (demo)

Two AI bots, both driven by the live script you publish in the dashboard:

- **Call Center bot**: voter help (booth, documents, general questions)
- **Scheme bot**: scheme-wise calling (health, education, farmer) with a human expert per scheme

Voice: Sarvam AI | Brain: Groq or Google Gemini | Phone: Twilio

## Folder structure

```
public_seva_ai_callcentre/
  app.py              Flask backend: bots, scripts, Twilio webhooks, CRM API
  templates/
    index.html        dashboard page
  static/
    style.css         dashboard design
    app.js            dashboard logic (Overview, Call Center, Scheme Calling, Scripts, Knowledge Base, Live Demo, Integrations)
  data/
    db.json           created on first run (scripts, schemes, calls, contacts)
  numbers.csv         contact list: name,phone,scheme,booth,language
  .env                your API keys and settings
  requirements.txt
  docs/               quotation and architecture PDFs
```

## Run (Windows PowerShell, in the VS Code terminal)

```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000 in Chrome.
If PowerShell blocks the activate script, run: `Set-ExecutionPolicy -Scope Process Bypass`

## Keys (.env)

Minimum for the demo: ONE of Groq or Gemini (the bot's brain). Sarvam gives the Indian voice.
Without a Sarvam key the browser demo uses the browser's own voice.

## Real phone calls (optional)

1. Run `ngrok http 5000` and paste the https URL into `BASE_URL` in `.env`, restart `python app.py`
2. Twilio trial: verify your own number, enable India in Geo Permissions, fill the three Twilio values
3. Dashboard > Live Demo > enter your number > Call
4. Inbound: set your Twilio number's voice webhook to `BASE_URL/twilio/voice` (HTTP POST)

## Notes

- Hindi, Marathi and English supported. Add contacts in `numbers.csv` or upload a CSV in Scheme Calling.
- The bot never asks for or reads a full Aadhaar number, and says it is an AI and that the call may be recorded.
- Demo storage is a JSON file. Production should use PostgreSQL, login and roles, and Twilio signature checks.
- Election-related calls need the required approvals (client's responsibility).
