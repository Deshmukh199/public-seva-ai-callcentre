"""
Public Seva AI Call Centre - demo backend (Flask)
MORYA IT Solution & AI Solution

Two bots, both driven by the live script:  Call Center bot  and  Scheme bot.
Voice: Sarvam AI (STT + TTS) | Brain: Groq or Google Gemini | Phone: Twilio
Run:  python app.py   ->  http://localhost:5000
"""
import os, re, csv, json, uuid, time, base64, threading
from datetime import date, timedelta
import requests
from flask import Flask, request, jsonify, Response
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"), override=True)
E = os.environ
PORT = int(E.get("PORT", "5000"))
BASE = (E.get("BASE_URL") or E.get("RENDER_EXTERNAL_URL") or f"http://localhost:{PORT}").rstrip("/")
DB_FILE = os.path.join(HERE, "data", "db.json")
FILLER_FILE = os.path.join(HERE, "data", "filler_words.json")
NUMBERS_CSV = os.path.join(HERE, "numbers.csv")

LANG = {"mr-IN": "Marathi (मराठी)", "hi-IN": "Hindi (हिंदी)", "en-IN": "English"}
DISC = {
    "mr-IN": "",
    "hi-IN": "",
    "en-IN": "",
}
app = Flask(__name__, static_folder=os.path.join(HERE, "static"), static_url_path="/static")
LOCK = threading.Lock()
AUDIO = {}  # id -> wav bytes (served to Twilio <Play>)

# ---------------------------------------------------------------- filler words dictionary & language detection
def load_fillers():
    try:
        with open(FILLER_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"mr-IN": {}, "hi-IN": {}, "en-IN": {}}


def save_fillers(fillers):
    with LOCK:
        try:
            with open(FILLER_FILE, "w", encoding="utf-8") as f:
                json.dump(fillers, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("Error saving fillers:", e)


def detect_and_learn_fillers(text, current_lang, llm_suggested_fillers=None):
    fillers = load_fillers()
    detected = []
    text_lower = text.lower()

    # Search through filler dictionary
    langs_to_check = [current_lang] + [l for l in ["mr-IN", "hi-IN", "en-IN"] if l != current_lang]
    for lang in langs_to_check:
        lang_dict = fillers.setdefault(lang, {})
        for word, meta in list(lang_dict.items()):
            pattern = rf"(?<!\w){re.escape(word.lower())}(?!\w)" if word.isascii() else re.escape(word)
            if re.search(pattern, text_lower if word.isascii() else text):
                if word not in detected:
                    detected.append(word)
                meta["count"] = meta.get("count", 0) + 1
                meta["last_seen"] = int(time.time() * 1000)

    # Auto-learn newly discovered fillers from LLM
    if llm_suggested_fillers:
        target_dict = fillers.setdefault(current_lang, {})
        for w in llm_suggested_fillers:
            clean_w = str(w).strip().strip(".,!?\"'")
            if clean_w and len(clean_w) < 30 and clean_w not in target_dict:
                target_dict[clean_w] = {
                    "count": 1,
                    "meaning": "colloquial filler / hesitation",
                    "category": "learned",
                    "last_seen": int(time.time() * 1000)
                }
                if clean_w not in detected:
                    detected.append(clean_w)

    save_fillers(fillers)
    return detected


MARATHI_MARKERS = {
    "आहे", "नाही", "नाहीत", "का", "कसे", "मला", "माझं", "माझे", "तुमचे", "आपले",
    "काय", "होय", "कधी", "कुठे", "करा", "बघा", "पाहिजे", "द्या", "सांगा", "म्हणजे",
    "अडकलो", "ऐका", "हो", "नको", "चालणार", "गेलो", "आलो", "केले", "फार", "खूप",
    "नमस्कार", "धन्यवाद", "असेल", "झाले", "करू", "शकतो", "शकते", "नाव", "मिळेल",
    "कोणते", "कागदपत्रे", "केंद्रात", "सांगतो", "समजले", "बरोबर", "कशा", "कशी",
    "बरं", "बघू", "थोडं", "माहिती", "योजना", "लाडकी", "बहीण", "शेतकरी"
}

HINDI_MARKERS = {
    "है", "नहीं", "क्या", "कैसे", "मुझे", "मेरा", "मेरी", "आपका", "आपकी", "कहाँ",
    "कब", "करना", "चाहिए", "दीजिए", "बताइए", "मतलब", "सुनाई", "हाँ", "होगा",
    "सकता", "सकती", "हुआ", "गया", "आया", "पास", "कुछ", "भी", "दस्तावेज़", "चाहता", "हूँ"
}


def detect_language(text, fallback_lang="mr-IN"):
    t = text.strip()
    if not t:
        return fallback_lang
    ascii_chars = sum(1 for c in t if c.isascii() and c.isalpha())
    total_letters = sum(1 for c in t if c.isalpha())
    if total_letters > 0 and (ascii_chars / total_letters) > 0.65:
        return "en-IN"
    words = set(re.findall(r"[\u0900-\u097F]+", t))
    mr_score = sum(1 for w in words if w in MARATHI_MARKERS)
    hi_score = sum(1 for w in words if w in HINDI_MARKERS)
    if mr_score > hi_score:
        return "mr-IN"
    elif hi_score > mr_score:
        return "hi-IN"
    return fallback_lang



# ---------------------------------------------------------------- data store
def load_numbers():
    """Contacts from numbers.csv: name,phone,scheme,booth,language"""
    out = []
    try:
        with open(NUMBERS_CSV, encoding="utf-8-sig") as f:
            for i, r in enumerate(csv.DictReader(f), 1):
                if (r.get("name") or "").strip():
                    out.append({"id": f"c{i}", "name": r["name"].strip(), "phone": (r.get("phone") or "").strip(),
                                "scheme": (r.get("scheme") or "health").strip(), "booth": (r.get("booth") or "").strip(),
                                "lang": (r.get("language") or "hi-IN").strip()})
    except FileNotFoundError:
        pass
    return out


def seed():
    today, later = date.today().isoformat(), (date.today() + timedelta(days=15)).isoformat()
    d = {
        "schemes": [
            {"id": "health", "name": "Health Support", "expert": {"name": "Dr. S. Kulkarni", "phone": E.get("EXPERT_PHONE", "")},
             "info": "Cashless treatment at empanelled hospitals. Carry Aadhaar and ration card. Apply at the nearest seva kendra."},
            {"id": "education", "name": "Education Scholarship", "expert": {"name": "R. Patil", "phone": ""},
             "info": "Scholarship form closes 30 November. Needs marksheet and income certificate."},
            {"id": "farmer", "name": "Farmer Support", "expert": {"name": "M. Shinde", "phone": ""},
             "info": "Crop support and insurance forms at the taluka seva kendra. Carry 7/12 extract and bank passbook."},
        ],
        "scripts": [
            {"id": "s_mr_cc", "bot": "callcenter", "scheme": "", "title": "मतदार सहाय्यता व केंद्र मार्गदर्शन (लोकप्रतिनिधी कक्ष - मराठी)", "lang": "mr-IN", "from": today, "to": later, "status": "live",
             "body": "सस्नेह नमस्कार {name} जी, मी आपल्या स्थानिक लोकप्रतिनिधींच्या जनसंपर्क व मतदार सहाय्यता कक्षातून बोलत आहे. आगामी मतदानासाठी आपले नाव मतदार यादीत समाविष्ट असून आपले मतदान केंद्र {booth} हे आहे. मतदानाच्या दिवशी आपले मतदार ओळखपत्र किंवा आधार अथवा पॅन कार्ड सोबत ठेवावे. मतदान केंद्राची माहिती किंवा ओळखपत्राबाबत आपल्याला काही अडचण किंवा प्रश्न आहे का?"},
            {"id": "s_mr_cc_warroom", "bot": "callcenter", "scheme": "", "title": "आमदार / खासदार थेट मतदार संपर्क (मतदार पावती व समस्या निवारण)", "lang": "mr-IN", "from": today, "to": later, "status": "live",
             "body": "सस्नेह जय महाराष्ट्र {name} जी, मी आपल्या मतदार संघातील मध्यवर्ती जनसंपर्क कार्यालयातून बोलत आहे. साहेबांच्या वतीने आपल्या भागातील मतदार बंधू-भगिनींशी थेट संवाद साधून मार्गदर्शन करण्यासाठी मी फोन केला आहे. आपले मतदान केंद्र {booth} हे निश्चित झाले आहे. मतदानासाठी कोणती कागदपत्रे लागतील किंवा परिसरातील नागरी समस्यांविषयी काही सांगायचे असल्यास नक्की सांगा, मी आपल्या मदतीसाठी उपस्थित आहे."},
            {"id": "s_mr_scheme", "bot": "scheme", "scheme": "health", "title": "महात्मा फुले जन आरोग्य योजना (५ लाख मोफत उपचार जनजागृती)", "lang": "mr-IN", "from": today, "to": later, "status": "live",
             "body": "सस्नेह नमस्कार {name} जी, मी आपल्या लोकप्रतिनिधी जन सेवा कार्यालयातून बोलत आहे. आपल्या कुटुंबासाठी {scheme} अंतर्गत ५ लाख रुपयांपर्यंत मोफत कॅशलेस उपचारांची सुविधा उपलब्ध आहे. यासाठी फक्त पिवळे अथवा केशरी रेशन कार्ड आणि आधार कार्ड आवश्यक असते. या योजनेचा लाभ मिळण्यात किंवा जवळच्या नोंदणीकृत रुग्णालयांची माहिती हवी असल्यास आपण सांगू शकता, मी पूर्ण मदत करते."},
            {"id": "s_mr_scheme_ladki", "bot": "scheme", "scheme": "ladki_bahin", "title": "मुख्यमंत्री माझी लाडकी बहीण योजना (दरमहा ₹१,५०० थेट लाभ)", "lang": "mr-IN", "from": today, "to": later, "status": "live",
             "body": "सस्नेह नमस्कार {name} जी, मी आपल्या लोकप्रतिनिधी जन सेवा कार्यालयातून बोलत आहे. आपल्या कुटुंबातील महिलांसाठी मुख्यमंत्री माझी लाडकी बहीण योजनेची माहिती देण्यासाठी मी फोन केला आहे. पात्र महिलांना दरमहा ₹१,५०० चा लाभ थेट बँक खात्यात मिळतो. या योजनेचा अर्ज भरण्यात किंवा आधार लिंकिंग संदर्भात आपल्याला काही मदत हवी असल्यास नक्की सांगा, मी पूर्ण सहकार्य करते."},
            {"id": "s_mr_scheme_farmer", "bot": "scheme", "scheme": "farmer", "title": "नमो शेतकरी महासन्मान निधी व पीक विमा (शेतकरी मदत कक्ष)", "lang": "mr-IN", "from": today, "to": later, "status": "live",
             "body": "सस्नेह नमस्कार {name} जी, मी आपल्या शेतकरी जन सेवा संपर्क कक्षातून बोलत आहे. {scheme} अंतर्गत शेतकरी बांधवांना वर्षाला ₹१२,००० चा सन्मान निधी थेट बँक खात्यात दिला जात आहे. ७/१२ उतारा, ई-केवायसी किंवा अनुदानाबाबत आपल्याला काही अडचण असल्यास आपण विचारू शकता."},
            {"id": "s_hi_cc", "bot": "callcenter", "scheme": "", "title": "मतदाता सहायता एवं केंद्र मार्गदर्शन (जनप्रतिनिधि कार्यालय - हिंदी)", "lang": "hi-IN", "from": today, "to": later, "status": "live",
             "body": "सादर नमस्ते {name} जी, मैं आपके स्थानीय जनप्रतिनिधि जनसंपर्क एवं मतदाता सहायता केंद्र से बोल रही हूँ। आपका मतदान केंद्र {booth} है। मतदान के दिन अपना वोटर आईडी, आधार या पैन कार्ड साथ रखें। क्या मतदान केंद्र या मतदाता सूची से संबंधित आपकी कोई समस्या या सवाल है? मैं आपकी सहायता के लिए उपस्थित हूँ।"},
            {"id": "s_en_cc", "bot": "callcenter", "scheme": "", "title": "Voter Outreach & Polling Station Help (Public Representative Office - English)", "lang": "en-IN", "from": today, "to": later, "status": "live",
             "body": "Namaskar {name} ji, I am calling from the Public Representative Citizen Outreach and Voter Assistance Center. Your polling booth is {booth}. Please carry your Voter ID or Aadhaar card on voting day. Do you need any assistance regarding your booth or voting documents? I am here to assist you."}
        ],
        "knowledge": [{"id": "k1", "title": "Booth and documents FAQ",
                       "text": "For voting carry Voter ID. If not available, Aadhaar or PAN card is accepted as photo proof. Polling booth details are given per voter. Helpline works 9 am to 7 pm."}],
        "contacts": load_numbers() or [
            {"id": "c1", "name": "Ramesh Pawar", "phone": "", "scheme": "health", "booth": "Zilla Parishad School, Ward 14", "lang": "hi-IN"},
            {"id": "c2", "name": "Sunita Jadhav", "phone": "", "scheme": "education", "booth": "Community Hall, Ward 9", "lang": "en-IN"},
            {"id": "c3", "name": "Mahesh Kale", "phone": "", "scheme": "farmer", "booth": "Gram Panchayat Office", "lang": "mr-IN"}],
        "calls": [],
    }
    names = ["Ramesh Pawar", "Sunita Jadhav", "Mahesh Kale", "Anita More", "Vijay Patil", "Kavita Shinde", "Sanjay Deshmukh", "Pooja Joshi"]
    outs = ["Resolved", "Resolved", "Resolved", "Resolved", "Sent to expert", "No answer"]
    now = int(time.time() * 1000)
    for i in range(56):
        bot = "callcenter" if i % 3 else "scheme"
        sc = d["schemes"][i % 3]["id"] if bot == "scheme" else ""
        o = outs[(i * 7) % 6]
        d["calls"].append({
            "id": f"d{i}", "bot": bot, "scheme": sc, "name": names[i % 8], "phone": f"98xxxxxx{10 + i}", "channel": "phone",
            "start": int(now - (i % 7) * 864e5 - (i * 3.1e6) % 7e7), "dur": 0 if o == "No answer" else 60 + (i * 17) % 140,
            "outcome": o, "status": "done",
            "transcript": [] if o == "No answer" else [
                {"r": "bot", "t": "Namaste, this is the Public Seva AI assistant. Your booth is Ward 14 school."},
                {"r": "user", "t": "Am I eligible for this scheme?" if bot == "scheme" else "Which documents should I carry?"},
                {"r": "bot", "t": "I am connecting you to our expert now." if o == "Sent to expert" else "Carry Voter ID, or Aadhaar or PAN card."}]})
    return d


def save():
    with LOCK:
        os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False)


try:
    with open(DB_FILE, encoding="utf-8") as f:
        db = json.load(f)
except Exception:
    db = seed()
    save()


# ---------------------------------------------------------------- AI brain + Sarvam voice
def fill(t, c, scheme_name=""):
    return (t.replace("{name}", c.get("name") or "Friend").replace("{booth}", c.get("booth") or "your polling booth")
            .replace("{scheme}", scheme_name or ""))


def active_script(bot, scheme="", preferred_lang="mr-IN"):
    t = date.today().isoformat()
    # 1. Match bot, status, scheme, date, and preferred_lang
    for s in db["scripts"]:
        if s["bot"] == bot and s["status"] == "live" and (not scheme or s["scheme"] == scheme) and s["from"] <= t <= s["to"] and s.get("lang") == preferred_lang:
            return s
    # 2. Match without preferred_lang
    for s in db["scripts"]:
        if s["bot"] == bot and s["status"] == "live" and (not scheme or s["scheme"] == scheme) and s["from"] <= t <= s["to"]:
            return s
    return next((s for s in db["scripts"] if s["bot"] == bot and s["status"] == "live"), None)


def sys_prompt(call):
    sc = next((s for s in db["scripts"] if s["id"] == call.get("scriptId")), None)
    sch = next((s for s in db["schemes"] if s["id"] == call.get("scheme")), None)
    ct = call.get("contact") or {}
    kind = "scheme calling" if call["bot"] == "scheme" else "general call centre"
    curr_lang = call.get("lang") or "mr-IN"
    lang_name = LANG.get(curr_lang, "Marathi (मराठी)")

    return f"""You are the professional, polite, and culturally respectful female civic outreach executive for "स्थानिक लोकप्रतिनिधी जनसंपर्क व मतदार सहाय्यता कक्ष" (Public Representative Citizen Outreach & Voter Assistance War Room / Seva Office) ({kind}).
You speak with a warm, natural, respectful female tone (native Maharashtrian voice: Priya).
CURRENT CONVERSATION LANGUAGE: {lang_name} ({curr_lang}).

CORE INSTRUCTIONS:
1. DYNAMIC LANGUAGE ADAPTATION (SELF-LEARNER):
   - You MUST detect what language the caller speaks in their message.
   - If the caller speaks Marathi (e.g. आहे, नाही, सांगा, काय, नमस्कार, मला, कसे or Roman Marathi), reply in MARATHI and set "lang": "mr-IN".
   - If the caller speaks Hindi (e.g. है, नहीं, बताइए, क्या, नमस्ते, मुझे), reply in HINDI and set "lang": "hi-IN".
   - If the caller speaks English, reply in ENGLISH and set "lang": "en-IN".
   - Seamlessly follow the caller's language switch anytime during the call!

2. PROFESSIONAL FEMALE CIVIC CALL CENTER TONE & GRAMMAR:
   - Always maintain a highly courteous, reassuring, and respectful female speaker manner:
   - For Marathi (mr-IN): Use proper female first-person verbal forms:
     "सस्नेह नमस्कार!", "काही काळजी करू नका, मी नक्की मदत करते.", "मी आपल्याला माहिती सांगते.", "हो नक्कीच!", "धन्यवाद!", "आपल्या सेवेत सदैव तत्पर आहे."
     (CRITICAL: Use female forms "मदत करते", "सांगते", NEVER male "करतो", "सांगतो"!).
   - For Hindi (hi-IN): Use proper female verbal forms:
     "नमस्ते!", "बिल्कुल चिंता न करें, मैं आपकी पूरी सहायता करूँगी।", "मैं जानकारी दे रही हूँ।", "जी अवश्य!", "धन्यवाद!", "आपका दिन शुभ हो!"
     (CRITICAL: Use female forms "करूँगी", "बोल रही हूँ", NEVER male "करूँगा", "बोल रहा हूँ"!).
   - For English (en-IN):
     "Hello! Please don't worry, I am glad to assist you.", "Certainly!", "Thank you so much!", "Have a wonderful day!"

3. EXTENSIVE CIVIC KNOWLEDGE & ANSWER ALL QUESTIONS (DO NOT TRANSFER PREMATURELY):
   - You possess complete knowledge of government schemes, voter assistance, civic documents, and helplines.
   - Directly answer the citizen's questions! Guide them step-by-step on what to do, which alternative documents to use, which website/app to visit, and which office to go to.
   - Example 1: If caller says they have no Voter ID:
     Reassure them! Explain that if their name is in the voter list, they can vote using Aadhaar Card, PAN Card, Driving Licence, Passport, or 12 other valid photo ID cards. Tell them to check name on voters.eci.gov.in or call 1950, or apply via Form 6.
   - Example 2: If caller asks for polling booth location:
     State their booth ({ct.get('booth') or 'the assigned polling station'}), and advise checking voters.eci.gov.in or calling 1950.
   - Example 3: If caller asks about schemes:
     Explain Ayushman Bharat / MJPJAY (up to ₹5 lakh free cashless hospital treatment), Mukhyamantri Majhi Ladki Bahin Yojana (₹1500/month for women 21-65), Namo Shetkari / PM Kisan (₹12,000/year for farmers), or MahaDBT Scholarships, and the required documents.
   - ONLY set "handoff": true IF:
     (a) The caller explicitly demands to speak to an officer or human expert, OR
     (b) The request involves an individual confidential grievance that only an authorized officer can resolve.

4. FILLER WORD AWARENESS:
   - Identify any conversational filler words / hesitation phrases used by the caller:
     (Marathi fillers: म्हणजे, अं, बघा, हो ना, बरं, काय ते, तर, ना, ऐका ना; Hindi fillers: मतलब, अरे, तो, यार, अच्छा; English: um, uh, like, you know).
   - Return any filler words detected in "detected_fillers": ["word1", ...].

5. CONCISE SPOKEN FORMAT:
   - Keep replies within 1-2 SHORT, crisp spoken sentences that sound natural over a phone call.
   - Do NOT write long paragraphs. Be BRIEF and direct.
   - Maximum 40-50 words per reply. Shorter is better.

SCRIPT: {fill(sc['body'], ct, sch['name'] if sch else '') if sc else ''}
SCHEME INFO: {(sch['name'] + ': ' + sch['info']) if sch else 'n/a'}
KNOWLEDGE BASE: {' '.join(k['text'] for k in db['knowledge'])}

Reply ONLY valid JSON format:
{{"reply": "your warm spoken response", "lang": "mr-IN"|"hi-IN"|"en-IN", "handoff": false, "end": false, "detected_fillers": []}}"""


def llm(system, hist, user):
    load_dotenv(os.path.join(HERE, ".env"), override=True)
    use_gemini = (E.get("LLM") == "gemini" and E.get("GOOGLE_API_KEY")) or (not E.get("GROQ_API_KEY") and E.get("GOOGLE_API_KEY"))
    txt = ""
    try:
        if E.get("GROQ_API_KEY") and not use_gemini:
            model = E.get("GROQ_MODEL", "openai/gpt-oss-120b")
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", timeout=20,
                              headers={"Authorization": "Bearer " + E["GROQ_API_KEY"]},
                              json={"model": model, "temperature": 0.2,
                                    "max_tokens": 1024,
                                    "response_format": {"type": "json_object"},
                                    "messages": [{"role": "system", "content": system}, *hist, {"role": "user", "content": user}]})
            j = r.json()
            txt = ((j.get("choices") or [{}])[0].get("message") or {}).get("content", "")
            if not txt:
                print("Groq primary error, trying fallback model:", str(j)[:250])
                # Secondary attempt with qwen on Groq or without json_object constraint
                for alt in ["qwen/qwen3.8-27b", model]:
                    try:
                        r2 = requests.post("https://api.groq.com/openai/v1/chat/completions", timeout=15,
                                           headers={"Authorization": "Bearer " + E["GROQ_API_KEY"]},
                                           json={"model": alt, "temperature": 0.2, "max_tokens": 800,
                                                 "messages": [{"role": "system", "content": system}, *hist, {"role": "user", "content": user}]})
                        if r2.ok:
                            txt = ((r2.json().get("choices") or [{}])[0].get("message") or {}).get("content", "")
                            if txt:
                                break
                    except Exception as alt_err:
                        print("Fallback attempt error:", alt_err)
        elif use_gemini:
            model = E.get("GEMINI_MODEL", "gemini-2.0-flash")
            contents = [{"role": "user" if h["role"] == "user" else "model", "parts": [{"text": h["content"]}]} for h in hist]
            contents.append({"role": "user", "parts": [{"text": user}]})
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={E['GOOGLE_API_KEY']}",
                              timeout=15, json={"systemInstruction": {"parts": [{"text": system}]}, "contents": contents,
                                                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2, "maxOutputTokens": 800}})
            j = r.json()
            try:
                txt = j["candidates"][0]["content"]["parts"][0]["text"]
            except Exception:
                print("Gemini error:", str(j)[:300])
        else:
            return {"reply": "Demo mode: add GROQ_API_KEY or GOOGLE_API_KEY in the .env file to enable the AI brain.", "lang": "mr-IN", "handoff": False, "end": False, "detected_fillers": []}
    except Exception as e:
        print("LLM call exception:", e)

    # Parse JSON output robustly
    if txt:
        try:
            cleaned = re.sub(r"```json|```", "", txt).strip()
            match = re.search(r"\{[\s\S]*\}", cleaned)
            payload = match.group(0) if match else cleaned
            out = json.loads(payload)
            out.setdefault("reply", "")
            out.setdefault("lang", "mr-IN")
            out.setdefault("handoff", False)
            out.setdefault("end", False)
            out.setdefault("detected_fillers", [])
            if out.get("reply"):
                return out
        except Exception as pe:
            print("JSON parse fallback on raw text:", pe, "txt was:", txt[:200])

    # Smart contextual fallback when LLM encounters an unexpected network issue
    u = user.lower()
    if any(w in u for w in ["वोटर", "voter", "id", "ओळखपत्र", "कार्ड", "नाही", "नाहीये"]):
        fb = "काही काळजी करू नका, आपले नाव मतदार यादीत असल्यास आपण आधार कार्ड, पॅन कार्ड, ड्रायव्हिंग लायसन्स किंवा पासपोर्ट दाखवून मतदान करू शकता. नवीन ओळखपत्रासाठी Form 6 भरा किंवा 1950 वर संपर्क करा."
    elif any(w in u for w in ["केंद्र", "booth", "कुठे", "पत्ता", "शाळा"]):
        fb = "आपले मतदान केंद्र संबंधित जिल्हा परिषद शाळा किंवा वॉर्ड कार्यालयात असते. अचूक माहितीसाठी voters.eci.gov.in तपासा किंवा 1950 वर कॉल करा."
    elif any(w in u for w in ["योजना", "scheme", "पैसे", "लाडकी बहीण", "शेतकरी"]):
        fb = "शासनाच्या योजना जसे की मुख्यमंत्री माझी लाडकी बहीण, आयुष्मान भारत किंवा शेतकरी सन्मान निधी याबद्दल सविस्तर माहितीसाठी आपण जवळच्या सेतू केंद्रात संपर्क करू शकता."
    else:
        fb = "हो नक्कीच, मी आपल्या सेवेसाठी तत्पर आहे. कृपया आपला प्रश्न किंवा शंका सांगा, मी संपूर्ण मदत करते."

    return {"reply": fb, "lang": "mr-IN", "handoff": False, "end": False, "detected_fillers": []}


def sarvam_key():
    return (E.get("SARVAM_API_KEY") or E.get("SARVAM_KEY") or "").strip()


def tts(text, lang, speaker=None):
    """Sarvam text-to-speech -> WAV bytes (None if no key / error)."""
    load_dotenv(os.path.join(HERE, ".env"), override=True)
    key = sarvam_key()
    if not key:
        return None
    try:
        spk = (speaker or E.get("SARVAM_SPEAKER") or "").strip()
        # Strictly reject legacy male speakers (shubh, etc.) and ensure authentic Maharashtrian female voice
        MALE_SPEAKERS = {"shubh", "aditya", "ashutosh", "rahul", "rohan", "amit", "dev", "ratan", "varun", "manan", "sumit", "kabir", "aayan", "advait", "anand", "tarun", "sunny", "mani", "gokul", "vijay", "mohit", "rehan", "soham"}
        if not spk or spk.lower() in MALE_SPEAKERS:
            spk = "rupali"

        pace = float(E.get("SARVAM_TTS_PACE", "1.25"))
        r = requests.post("https://api.sarvam.ai/text-to-speech", timeout=12,
                          headers={"api-subscription-key": key},
                          json={"text": text, "target_language_code": lang, "model": E.get("SARVAM_TTS_MODEL", "bulbul:v3"),
                                "speaker": spk, "pace": pace, "speech_sample_rate": 22050})
        if not r.ok:
            print("Sarvam TTS", r.status_code, r.text[:200]); return None
        return base64.b64decode(r.json()["audios"][0])
    except Exception as e:
        print("Sarvam TTS error:", e); return None


def stt(buf):
    """Sarvam speech-to-text -> transcript string."""
    load_dotenv(os.path.join(HERE, ".env"), override=True)
    key = sarvam_key()
    if not key:
        return ""
    try:
        r = requests.post("https://api.sarvam.ai/speech-to-text", timeout=30,
                          headers={"api-subscription-key": key},
                          files={"file": ("a.wav", buf, "audio/wav")},
                          data={"model": E.get("SARVAM_STT_MODEL", "saarika:v2.5"), "language_code": "unknown"})
        if not r.ok:
            print("Sarvam STT", r.status_code); return ""
        return r.json().get("transcript", "")
    except Exception as e:
        print("Sarvam STT error:", e); return ""


def find_call(cid):
    if not cid:
        return None
    # 1. Search in-memory
    c = next((x for x in db.get("calls", []) if x["id"] == cid), None)
    if c:
        return c
    # 2. Reload from disk in case written by another worker/process
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, encoding="utf-8") as f:
                disk_db = json.load(f)
                c = next((x for x in disk_db.get("calls", []) if x["id"] == cid), None)
                if c:
                    db["calls"] = disk_db.get("calls", [])
                    return c
    except Exception as e:
        print("Error reloading db in find_call:", e)
    return None


def new_call(bot, script_id=None, contact_id=None, scheme=None, channel="browser", phone=""):
    ct = next((c for c in db["contacts"] if c["id"] == contact_id), None) or {"name": "नागरिक", "booth": "आपले मतदान केंद्र"}
    given = next((s for s in db["scripts"] if s["id"] == script_id), None)
    sch = (scheme or (given and given["scheme"]) or ct.get("scheme") or "health") if bot == "scheme" else ""
    pref_lang = (given and given["lang"]) or ct.get("lang") or "mr-IN"
    sc = given or active_script(bot, sch, pref_lang)
    call_lang = (sc and sc["lang"]) or pref_lang or "mr-IN"
    c = {"id": uuid.uuid4().hex[:8], "bot": bot, "scheme": sch, "scriptId": sc and sc["id"], "contact": ct, "name": ct["name"],
         "phone": phone or ct.get("phone", ""), "lang": call_lang, "channel": channel,
         "start": int(time.time() * 1000), "dur": 0, "status": "live", "outcome": "In progress", "transcript": [], "empties": 0}
    sn = next((s["name"] for s in db["schemes"] if s["id"] == sch), "")
    
    # Natural politician / representative opening (NO robotic "I am AI assistant" message)
    if sc and sc.get("body"):
        c["opening"] = fill(sc["body"], ct, sn)
    else:
        if call_lang == "mr-IN":
            c["opening"] = f"सस्नेह नमस्कार {ct.get('name', 'नागरिक')} जी, मी आपल्या स्थानिक लोकप्रतिनिधींच्या जनसंपर्क व मतदार सहाय्यता कक्षातून बोलत आहे. आगामी मतदानासाठी आपले नाव मतदार यादीत समाविष्ट असून आपले मतदान केंद्र {ct.get('booth', 'आपले मतदान केंद्र')} हे आहे. मतदानाच्या दिवशी आपले मतदार ओळखपत्र किंवा आधार/पॅन कार्ड सोबत ठेवावे. मतदान केंद्राची माहिती किंवा ओळखपत्राबाबत आपल्याला काही अडचण किंवा प्रश्न आहे का? मी आपल्या मदतीसाठी सदैव उपस्थित आहे."
        elif call_lang == "hi-IN":
            c["opening"] = f"सादर नमस्ते {ct.get('name', 'नागरिक')} जी, मैं आपके स्थानीय जनप्रतिनिधि जनसंपर्क एवं मतदाता सहायता केंद्र से बोल रही हूँ। आपका मतदान केंद्र {ct.get('booth', 'आपका मतदान केंद्र')} है। मतदान के दिन अपना वोटर आईडी, आधार या पैन कार्ड साथ रखें। क्या मतदान केंद्र या मतदाता सूची से संबंधित आपकी कोई समस्या या सवाल है? मैं आपकी सहायता के लिए उपस्थित हूँ।"
        else:
            c["opening"] = f"Namaskar {ct.get('name', 'Citizen')} ji, I am calling from the Public Representative Citizen Outreach and Voter Assistance Center. Your polling booth is {ct.get('booth', 'your polling booth')}. Please carry your Voter ID or Aadhaar card on voting day. Do you need any assistance regarding your booth or voting documents? I am here to assist you."
            
    c["transcript"].append({"r": "bot", "t": c["opening"], "lang": c["lang"]})
    db["calls"].insert(0, c); save()
    return c


def run_turn(call, text):
    call["transcript"].append({"r": "user", "t": text})

    # 1. Heuristic pre-detection
    heuristic_lang = detect_language(text, call.get("lang") or "mr-IN")
    if heuristic_lang != call.get("lang"):
        call["lang"] = heuristic_lang

    hist = [{"role": "user" if x["r"] == "user" else "assistant", "content": x["t"]} for x in call["transcript"][-11:-1]]
    out = llm(sys_prompt(call), hist, text)

    # 2. Dynamic LLM language adaptation
    detected_lang = out.get("lang")
    if detected_lang in ["mr-IN", "hi-IN", "en-IN"]:
        call["lang"] = detected_lang

    # 3. Filler words detection & self-learning
    llm_fillers = out.get("detected_fillers", [])
    detected_fillers = detect_and_learn_fillers(text, call["lang"], llm_fillers)
    out["detected_fillers"] = detected_fillers
    out["lang"] = call["lang"]

    call["transcript"].append({"r": "bot", "t": out["reply"], "lang": call["lang"], "fillers": detected_fillers})
    if out["handoff"]:
        call["outcome"] = "Sent to expert"
    if out["end"] or out["handoff"]:
        call["status"] = "done"
        if not out["handoff"]:
            call["outcome"] = "Resolved"
    call["dur"] = round(time.time() - call["start"] / 1000)
    save()
    return out


# ---------------------------------------------------------------- Twilio helpers
def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def xml(s):
    return Response('<?xml version="1.0" encoding="UTF-8"?><Response>' + s + "</Response>", mimetype="text/xml")


def tw_auth():
    return (E.get("TWILIO_ACCOUNT_SID", ""), E.get("TWILIO_AUTH_TOKEN", ""))


def say(text, lang):
    buf = tts(text, lang)
    if buf:
        aid = uuid.uuid4().hex
        AUDIO[aid] = buf
        threading.Timer(600, lambda: AUDIO.pop(aid, None)).start()
        return f"<Play>{BASE}/audio/{aid}.wav</Play>"
    return f'<Say language="{lang}" voice="Google.{lang}-Standard-A">{esc(text)}</Say>'


def listen(c):
    if sarvam_key():
        return f'<Record action="{BASE}/twilio/turn?cid={c["id"]}" maxLength="12" timeout="3" trim="trim-silence" playBeep="false"/>'
    return (f'<Gather input="speech" language="{c["lang"]}" speechTimeout="auto" action="{BASE}/twilio/turn?cid={c["id"]}"/>'
            f'<Redirect>{BASE}/twilio/turn?cid={c["id"]}</Redirect>')


def place_call(to, call):
    r = requests.post(f"https://api.twilio.com/2010-04-01/Accounts/{E.get('TWILIO_ACCOUNT_SID')}/Calls.json", auth=tw_auth(), timeout=30,
                      data={"To": to, "From": E.get("TWILIO_FROM"), "Url": f"{BASE}/twilio/voice?cid={call['id']}",
                            "StatusCallback": f"{BASE}/twilio/status?cid={call['id']}", "StatusCallbackEvent": "completed",
                            "Record": "true", "RecordingStatusCallback": f"{BASE}/twilio/rec?cid={call['id']}"})
    j = r.json()
    if not r.ok:
        raise RuntimeError(j.get("message", "Twilio error"))
    return j


def need_twilio():
    if not E.get("TWILIO_ACCOUNT_SID") or not E.get("TWILIO_AUTH_TOKEN"):
        raise RuntimeError("Add your Twilio keys in the .env file")


# ---------------------------------------------------------------- routes: dashboard + API
@app.errorhandler(Exception)
def on_error(e):
    if isinstance(e, HTTPException):
        return e
    print("ERROR:", e)
    return jsonify({"error": str(e)}), 500


@app.route("/")
def index():
    with open(os.path.join(HERE, "templates", "index.html"), encoding="utf-8") as f:
        return Response(f.read(), mimetype="text/html")


@app.route("/audio/<aid>.wav")
def audio(aid):
    a = AUDIO.get(aid)
    return Response(a, mimetype="audio/wav") if a else Response(status=404)


@app.route("/api/state")
def api_state():
    calls = [{k: v for k, v in c.items() if k != "contact"} for c in db["calls"][:120]]
    fillers = load_fillers()
    filler_count = sum(len(v) for v in fillers.values())
    filler_occurrences = sum(sum(w.get("count", 0) for w in v.values()) for v in fillers.values())
    return jsonify({**db, "calls": calls, "fillers_summary": {"total_words": filler_count, "total_occurrences": filler_occurrences}, "status": {
        "twilio": bool(E.get("TWILIO_ACCOUNT_SID") and E.get("TWILIO_AUTH_TOKEN") and E.get("TWILIO_FROM")),
        "sarvam": bool(sarvam_key()), "groq": bool(E.get("GROQ_API_KEY")), "google": bool(E.get("GOOGLE_API_KEY")),
        "whatsapp": bool(E.get("TWILIO_WHATSAPP_FROM") and E.get("TWILIO_ACCOUNT_SID")),
        "base": BASE}})


@app.route("/api/fillers", methods=["GET"])
def api_get_fillers():
    fillers = load_fillers()
    stats = {
        "total_words": sum(len(v) for v in fillers.values()),
        "total_occurrences": sum(sum(w.get("count", 0) for w in v.values()) for v in fillers.values()),
        "by_lang": {l: len(v) for l, v in fillers.items()}
    }
    return jsonify({"fillers": fillers, "stats": stats})


@app.route("/api/fillers", methods=["POST"])
def api_save_filler():
    b = request.get_json(force=True)
    lang = b.get("lang") or "mr-IN"
    word = (b.get("word") or "").strip()
    if not word:
        return jsonify({"error": "Word is required"}), 400
    fillers = load_fillers()
    d = fillers.setdefault(lang, {})
    d[word] = {
        "count": int(b.get("count") or (d.get(word, {}).get("count", 1))),
        "meaning": b.get("meaning") or d.get(word, {}).get("meaning", "colloquial filler"),
        "category": b.get("category") or d.get(word, {}).get("category", "general"),
        "last_seen": int(time.time() * 1000)
    }
    save_fillers(fillers)
    return jsonify({"ok": True, "word": word})


@app.route("/api/fillers", methods=["DELETE"])
def api_delete_filler():
    b = request.get_json(force=True)
    lang = b.get("lang") or "mr-IN"
    word = (b.get("word") or "").strip()
    fillers = load_fillers()
    if lang in fillers and word in fillers[lang]:
        del fillers[lang][word]
        save_fillers(fillers)
    return jsonify({"ok": True})


@app.route("/api/script", methods=["POST"])
def api_script():
    b = request.get_json(force=True)
    s = next((x for x in db["scripts"] if x["id"] == b.get("id")), None)
    if not s:
        s = {"id": "s" + str(int(time.time() * 1000))}
        db["scripts"].append(s)
    s.update({"bot": b["bot"], "scheme": b.get("scheme") or "", "title": b["title"], "lang": b["lang"], "from": b["from"], "to": b["to"],
              "body": b["body"], "status": b["status"]})
    if s["status"] == "live":
        for x in db["scripts"]:
            if x is not s and x["bot"] == s["bot"] and x["scheme"] == s["scheme"] and x["status"] == "live":
                x["status"] = "archived"
    save()
    return jsonify(s)


@app.route("/api/knowledge", methods=["POST"])
def api_knowledge():
    b = request.get_json(force=True)
    db["knowledge"].append({"id": "k" + str(int(time.time() * 1000)), "title": b.get("title", "Untitled"), "text": b.get("text", "")})
    save()
    return jsonify({})


@app.route("/api/scheme", methods=["POST"])
def api_scheme():
    b = request.get_json(force=True)
    s = next((x for x in db["schemes"] if x["id"] == b["id"]), None)
    if s:
        s["expert"], s["info"] = b["expert"], b["info"]
        save()
    return jsonify({})


@app.route("/api/contacts", methods=["POST"])
def api_contacts():
    b = request.get_json(force=True)
    for row in csv.reader((b.get("csv") or "").splitlines()):
        r = [x.strip() for x in row]
        if r and r[0] and r[0].lower() != "name":
            db["contacts"].append({"id": "c" + uuid.uuid4().hex[:6], "name": r[0], "phone": r[1] if len(r) > 1 else "",
                                   "scheme": r[2] if len(r) > 2 and r[2] else "health", "booth": r[3] if len(r) > 3 else "",
                                   "lang": r[4] if len(r) > 4 and r[4] else "mr-IN"})
    save()
    return jsonify({})


@app.route("/api/preview", methods=["POST"])
def api_preview():
    b = request.get_json(force=True)
    a = tts(b["text"], b["lang"], b.get("speaker"))
    return jsonify({"audio": base64.b64encode(a).decode() if a else None})


@app.route("/api/sim/start", methods=["POST"])
def sim_start():
    b = request.get_json(force=True)
    c = new_call(b["bot"], b.get("scriptId"), b.get("contactId"), b.get("scheme"), "browser")
    spk = b.get("speaker") or "rupali"
    c["speaker"] = spk
    a = tts(c["opening"], c["lang"], spk)
    return jsonify({"callId": c["id"], "opening": c["opening"], "lang": c["lang"], "speaker": spk, "audio": base64.b64encode(a).decode() if a else None})


@app.route("/api/sim/say", methods=["POST"])
def sim_say():
    b = request.get_json(force=True)
    cid = b.get("callId")
    c = find_call(cid)
    if not c:
        # Reconstruct call session seamlessly so turn never fails
        c = new_call("callcenter", None, None, None, "browser")
        if cid:
            c["id"] = cid
    spk = b.get("speaker") or (c and c.get("speaker")) or "rupali"
    o = run_turn(c, b.get("text", ""))
    a = tts(o["reply"], c["lang"], spk)
    return jsonify({**o, "lang": c["lang"], "speaker": spk, "audio": base64.b64encode(a).decode() if a else None})


@app.route("/api/call", methods=["POST"])
def api_call():
    need_twilio()
    b = request.get_json(force=True)
    c = new_call(b["bot"], b.get("scriptId"), b.get("contactId"), b.get("scheme"), "phone", b["to"])
    c["sid"] = place_call(b["to"], c)["sid"]
    save()
    return jsonify({"ok": True, "callId": c["id"]})


# ---------------------------------------------------------------- Outbound Campaign Engine
CAMPAIGN = {
    "id": "cmp_1",
    "name": "जन सेवा मतदार संपर्क मोहीम",
    "status": "idle",  # "idle", "running", "paused", "completed"
    "bot": "callcenter",
    "scriptId": "s_mr_cc",
    "mode": "auto",  # "auto" (interactive demo) or "phone" (Twilio)
    "queue": [],
    "current_index": 0,
    "current_call": None,
    "completed": 0,
    "total": 0,
    "active": False,
    "started_at": 0
}
CAMPAIGN_LOCK = threading.Lock()
CAMPAIGN_THREAD = None


def init_campaign_queue():
    if not CAMPAIGN.get("queue") and db.get("contacts"):
        CAMPAIGN["queue"] = [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "phone": c.get("phone") or f"98200{i:05d}",
                "booth": c.get("booth") or "Ward 14 School",
                "scheme": c.get("scheme") or "",
                "lang": c.get("lang") or "mr-IN",
                "status": "pending",
                "outcome": ""
            }
            for i, c in enumerate(db["contacts"], 1)
        ]
        CAMPAIGN["total"] = len(CAMPAIGN["queue"])


init_campaign_queue()


def campaign_worker():
    global CAMPAIGN
    with CAMPAIGN_LOCK:
        bot = CAMPAIGN.get("bot") or "callcenter"
        script_id = CAMPAIGN.get("scriptId") or ""
        mode = CAMPAIGN.get("mode") or "auto"
        queue = CAMPAIGN.get("queue") or []
        CAMPAIGN["started_at"] = int(time.time() * 1000)

    for idx in range(CAMPAIGN.get("current_index", 0), len(queue)):
        if not CAMPAIGN.get("active") or CAMPAIGN.get("status") in ["idle", "stopped"]:
            break

        # Check pause
        while CAMPAIGN.get("status") == "paused":
            time.sleep(1)
            if not CAMPAIGN.get("active"):
                break

        if not CAMPAIGN.get("active"):
            break

        contact = queue[idx]
        CAMPAIGN["current_index"] = idx
        contact["status"] = "calling"

        phone = contact.get("phone", "")
        call = new_call(bot=bot, script_id=script_id, contact_id=contact.get("id"),
                        channel="phone" if mode == "phone" else "campaign", phone=phone)
        call["campaign_id"] = CAMPAIGN.get("id")

        if mode == "phone" and E.get("TWILIO_ACCOUNT_SID") and phone:
            try:
                tw_res = place_call(phone, call)
                call["sid"] = tw_res.get("sid")
                contact["status"] = "connected"
                contact["outcome"] = "Dialed"
            except Exception as ex:
                print("Twilio call failed:", ex)
                contact["status"] = "failed"
                contact["outcome"] = str(ex)[:60]
                call["status"] = "done"
                call["outcome"] = "Failed"
        else:
            # Simulated campaign call with authentic Sarvam voice
            contact["status"] = "completed"
            contact["outcome"] = "Resolved"
            call["dur"] = 45 + (idx * 11) % 45
            call["status"] = "done"
            call["outcome"] = "Resolved"
            tts(call["opening"], call["lang"])

        CAMPAIGN["completed"] = idx + 1
        CAMPAIGN["current_call"] = {
            "contact": contact,
            "callId": call["id"],
            "opening": call["opening"],
            "lang": call["lang"],
            "status": contact["status"],
            "outcome": contact.get("outcome", "Resolved")
        }
        save()

        # Pause between calls (5 seconds so user can see it dial one by one)
        for _ in range(5):
            if not CAMPAIGN.get("active") or CAMPAIGN.get("status") == "paused":
                break
            time.sleep(1)

    with CAMPAIGN_LOCK:
        if CAMPAIGN.get("active") and CAMPAIGN["current_index"] >= len(queue) - 1:
            CAMPAIGN["status"] = "completed"
            CAMPAIGN["active"] = False


@app.route("/api/campaign/state")
def api_campaign_state():
    init_campaign_queue()
    return jsonify({
        **CAMPAIGN,
        "twilio_configured": bool(E.get("TWILIO_ACCOUNT_SID") and E.get("TWILIO_AUTH_TOKEN") and E.get("TWILIO_FROM"))
    })


@app.route("/api/campaign/upload", methods=["POST"])
def api_campaign_upload():
    global CAMPAIGN
    b = request.get_json(force=True)
    raw_csv = b.get("csv") or ""
    new_contacts = []
    for row in csv.reader(raw_csv.splitlines()):
        r = [x.strip() for x in row]
        if r and r[0] and r[0].lower() not in ["name", "voter name"]:
            cid = "cmp_" + uuid.uuid4().hex[:6]
            contact = {
                "id": cid,
                "name": r[0],
                "phone": r[1] if len(r) > 1 else "",
                "booth": r[2] if len(r) > 2 else "Polling Station",
                "scheme": r[3] if len(r) > 3 and r[3] in ["health", "education", "farmer"] else "",
                "lang": r[4] if len(r) > 4 and r[4] in ["mr-IN", "hi-IN", "en-IN"] else "mr-IN",
                "status": "pending",
                "outcome": ""
            }
            new_contacts.append(contact)
            db["contacts"].append(contact)

    if new_contacts:
        if b.get("replace"):
            CAMPAIGN["queue"] = new_contacts
            CAMPAIGN["current_index"] = 0
            CAMPAIGN["completed"] = 0
        else:
            CAMPAIGN["queue"].extend(new_contacts)
        CAMPAIGN["total"] = len(CAMPAIGN["queue"])
        save()

    return jsonify({"ok": True, "added": len(new_contacts), "total": CAMPAIGN["total"], "queue": CAMPAIGN["queue"]})


@app.route("/api/campaign/start", methods=["POST"])
def api_campaign_start():
    global CAMPAIGN, CAMPAIGN_THREAD
    b = request.get_json(force=True) or {}
    init_campaign_queue()

    with CAMPAIGN_LOCK:
        CAMPAIGN["bot"] = b.get("bot") or CAMPAIGN.get("bot", "callcenter")
        CAMPAIGN["scriptId"] = b.get("scriptId") or CAMPAIGN.get("scriptId", "s_mr_cc")
        CAMPAIGN["mode"] = b.get("mode") or CAMPAIGN.get("mode", "auto")

        # Restart from 0 if completed or idle
        if CAMPAIGN.get("status") in ["completed", "idle"] or b.get("restart"):
            CAMPAIGN["current_index"] = 0
            CAMPAIGN["completed"] = 0
            for c in CAMPAIGN["queue"]:
                c["status"] = "pending"
                c["outcome"] = ""

        CAMPAIGN["active"] = True
        CAMPAIGN["status"] = "running"

    if CAMPAIGN_THREAD is None or not CAMPAIGN_THREAD.is_alive():
        CAMPAIGN_THREAD = threading.Thread(target=campaign_worker, daemon=True)
        CAMPAIGN_THREAD.start()

    return jsonify({"ok": True, "status": CAMPAIGN["status"], "queue_size": len(CAMPAIGN["queue"])})


@app.route("/api/campaign/pause", methods=["POST"])
def api_campaign_pause():
    with CAMPAIGN_LOCK:
        if CAMPAIGN.get("status") == "running":
            CAMPAIGN["status"] = "paused"
        elif CAMPAIGN.get("status") == "paused":
            CAMPAIGN["status"] = "running"
    return jsonify({"ok": True, "status": CAMPAIGN["status"]})


@app.route("/api/campaign/stop", methods=["POST"])
def api_campaign_stop():
    with CAMPAIGN_LOCK:
        CAMPAIGN["active"] = False
        CAMPAIGN["status"] = "idle"
        CAMPAIGN["current_index"] = 0
        for c in CAMPAIGN["queue"]:
            c["status"] = "pending"
            c["outcome"] = ""
    return jsonify({"ok": True, "status": CAMPAIGN["status"]})


@app.route("/api/campaign", methods=["POST"])
def api_campaign():
    # Backwards-compatible route
    return api_campaign_start()


@app.route("/api/rec")
def api_rec():
    c = find_call(request.args.get("id", ""))
    if not c or not c.get("rec"):
        return Response(status=404)
    r = requests.get(c["rec"] + ".mp3", auth=tw_auth(), timeout=30)
    return Response(r.content, mimetype="audio/mpeg")


# ---------------------------------------------------------------- routes: Twilio webhooks
@app.route("/twilio/voice", methods=["GET", "POST"])
def tw_voice():
    c = find_call(request.args.get("cid", ""))
    if not c:  # inbound call to the Twilio number -> Call Center bot
        c = new_call("callcenter", channel="phone-inbound", phone=request.form.get("From", ""))
    c["sid"] = request.form.get("CallSid") or c.get("sid")
    return xml(say(c["opening"], c["lang"]) + listen(c))


@app.route("/twilio/turn", methods=["GET", "POST"])
def tw_turn():
    c = find_call(request.args.get("cid", ""))
    if not c:
        return xml("<Hangup/>")
    text = request.form.get("SpeechResult", "")
    rec = request.form.get("RecordingUrl")
    if not text and rec and sarvam_key():
        buf = None
        for _ in range(3):
            r = requests.get(rec + ".wav", auth=tw_auth(), timeout=30)
            if r.ok:
                buf = r.content; break
            time.sleep(0.7)
        if buf:
            text = stt(buf)
    if not text:
        c["empties"] += 1
        if c["empties"] > 2:
            c["status"], c["outcome"] = "done", "No response"; save()
            return xml("<Hangup/>")
        again = {"en-IN": "Sorry, I could not hear you. Please say it again.", "mr-IN": "माफ करा, ऐकू आले नाही. कृपया पुन्हा सांगा."}.get(
            c["lang"], "माफ़ कीजिए, सुनाई नहीं दिया। कृपया फिर से बोलिए।")
        return xml(say(again, c["lang"]) + listen(c))
    c["empties"] = 0
    o = run_turn(c, text)
    v = say(o["reply"], c["lang"])
    ex = next((s["expert"] for s in db["schemes"] if s["id"] == c["scheme"]), db["schemes"][0]["expert"])
    if o["handoff"] and ex.get("phone"):
        return xml(v + f"<Dial>{esc(ex['phone'])}</Dial>")
    return xml(v + ("<Hangup/>" if o["end"] or o["handoff"] else listen(c)))


@app.route("/twilio/status", methods=["POST"])
def tw_status():
    c = find_call(request.args.get("cid", ""))
    if c:
        c["status"] = "done"
        c["dur"] = int(request.form.get("CallDuration") or c["dur"] or 0)
        if c["outcome"] == "In progress":
            c["outcome"] = "Resolved" if len(c["transcript"]) > 1 else "No answer"
        save()
    return jsonify({})


@app.route("/twilio/rec", methods=["POST"])
def tw_rec():
    c = find_call(request.args.get("cid", ""))
    if c:
        c["rec"] = request.form.get("RecordingUrl"); save()
    return jsonify({})


# ---------------------------------------------------------------- WhatsApp Integration (Twilio)
WHATSAPP_SESSIONS = {}  # phone -> {callId, lang, last_active}
WHATSAPP_LOCK = threading.Lock()


def wa_get_or_create_session(sender):
    """Get existing WhatsApp session or create new one for this sender."""
    with WHATSAPP_LOCK:
        sess = WHATSAPP_SESSIONS.get(sender)
        # Expire sessions after 30 minutes of inactivity
        if sess and (time.time() - sess.get("last_active", 0)) > 1800:
            sess = None
        if not sess:
            # Find contact by phone number
            phone_clean = sender.replace("whatsapp:", "").strip()
            ct = next((c for c in db["contacts"] if c.get("phone", "").replace("+", "").replace(" ", "") == phone_clean.replace("+", "").replace(" ", "")), None)
            contact_id = ct["id"] if ct else None
            call = new_call("callcenter", contact_id=contact_id, channel="whatsapp", phone=phone_clean)
            sess = {"callId": call["id"], "lang": call.get("lang", "mr-IN"), "last_active": time.time()}
            WHATSAPP_SESSIONS[sender] = sess
        else:
            sess["last_active"] = time.time()
        return sess


@app.route("/whatsapp", methods=["POST"])
def whatsapp_incoming():
    """Handle incoming WhatsApp messages via Twilio."""
    sender = request.form.get("From", "")
    incoming_msg = request.form.get("Body", "").strip()
    num_media = int(request.form.get("NumMedia", "0"))

    if not incoming_msg and num_media == 0:
        return Response('<?xml version="1.0" encoding="UTF-8"?><Response></Response>', mimetype="text/xml")

    # Handle voice notes (media)
    if num_media > 0 and not incoming_msg:
        media_url = request.form.get("MediaUrl0", "")
        media_type = request.form.get("MediaContentType0", "")
        if "audio" in media_type and media_url and sarvam_key():
            try:
                r = requests.get(media_url, auth=tw_auth(), timeout=15)
                if r.ok:
                    incoming_msg = stt(r.content) or ""
            except Exception as e:
                print("WhatsApp voice note STT error:", e)
        if not incoming_msg:
            twiml = '<?xml version="1.0" encoding="UTF-8"?><Response><Message>'
            twiml += 'माफ करा, कृपया लिखित संदेश पाठवा किंवा स्पष्ट आवाजात बोला. धन्यवाद! 🙏'
            twiml += '</Message></Response>'
            return Response(twiml, mimetype="text/xml")

    # Get or create session
    sess = wa_get_or_create_session(sender)
    call = find_call(sess["callId"])

    if not call:
        # Recreate session if call was lost
        with WHATSAPP_LOCK:
            WHATSAPP_SESSIONS.pop(sender, None)
        sess = wa_get_or_create_session(sender)
        call = find_call(sess["callId"])

    # Handle special commands
    lower_msg = incoming_msg.lower().strip()
    if lower_msg in ["reset", "नवीन", "new", "restart"]:
        with WHATSAPP_LOCK:
            WHATSAPP_SESSIONS.pop(sender, None)
        twiml = '<?xml version="1.0" encoding="UTF-8"?><Response><Message>'
        twiml += '🔄 संभाषण रीसेट झाले. नवीन संदेश पाठवा! / Conversation reset. Send a new message!'
        twiml += '</Message></Response>'
        return Response(twiml, mimetype="text/xml")

    # First message - send opening + process their message
    if call and len(call.get("transcript", [])) <= 1:
        # Send opening greeting first, then process
        opening = call.get("opening", "")
        out = run_turn(call, incoming_msg)
        reply_text = out.get("reply", "नमस्कार, कृपया पुन्हा सांगा.")
        # Update session language
        sess["lang"] = call.get("lang", "mr-IN")
    else:
        out = run_turn(call, incoming_msg)
        reply_text = out.get("reply", "नमस्कार, कृपया पुन्हा सांगा.")
        sess["lang"] = call.get("lang", "mr-IN")

    # Build TwiML response
    twiml = '<?xml version="1.0" encoding="UTF-8"?><Response><Message>'
    twiml += esc(reply_text)

    # Add filler detection info if any
    fillers = out.get("detected_fillers", [])
    if fillers:
        twiml += f'\n\n🏷️ Fillers detected: {", ".join(fillers)}'

    # Add handoff notice
    if out.get("handoff"):
        ex = next((s["expert"] for s in db["schemes"] if s["id"] == call.get("scheme")), db["schemes"][0]["expert"])
        twiml += f'\n\n📞 तज्ञांशी जोडत आहे: {ex.get("name", "Expert")}'
        if ex.get("phone"):
            twiml += f' ({ex["phone"]})'

    twiml += '</Message></Response>'
    return Response(twiml, mimetype="text/xml")


@app.route("/whatsapp/status", methods=["POST"])
def whatsapp_status():
    """WhatsApp message status callback."""
    return jsonify({"ok": True})


@app.route("/api/whatsapp/send", methods=["POST"])
def api_whatsapp_send():
    """Send a WhatsApp message to a phone number (outbound)."""
    need_twilio()
    b = request.get_json(force=True)
    to = b.get("to", "").strip()
    message = b.get("message", "").strip()
    if not to or not message:
        return jsonify({"error": "'to' and 'message' are required"}), 400

    wa_from = E.get("TWILIO_WHATSAPP_FROM", "")
    if not wa_from:
        return jsonify({"error": "Add TWILIO_WHATSAPP_FROM in .env (e.g. whatsapp:+14155238886)"}), 400

    try:
        r = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{E['TWILIO_ACCOUNT_SID']}/Messages.json",
            auth=tw_auth(), timeout=15,
            data={"To": f"whatsapp:{to}" if not to.startswith("whatsapp:") else to,
                  "From": wa_from,
                  "Body": message})
        j = r.json()
        if not r.ok:
            return jsonify({"error": j.get("message", "Twilio error")}), 400
        return jsonify({"ok": True, "sid": j.get("sid")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print(f"\n  Public Seva AI Call Centre -> http://localhost:{PORT}")
    print(f"  Twilio inbound webhook:      {BASE}/twilio/voice")
    print(f"  WhatsApp webhook:            {BASE}/whatsapp\n")
    app.run(host="0.0.0.0", port=PORT, debug=False)
