# rule based (non-LLM) logic
# used when ollama is not running, so the app still does something useful
# these are simple keyword checks, NOT ai. output is marked source="rule_based"

SIGNAL_KEYWORDS = {
    "hiring": ["we're hiring", "we are hiring", "careers", "join our team", "open positions", "job opening"],
    "growth": ["new location", "expanding", "opening soon", "series a", "series b", "raised", "funding"],
    "manual_process": ["call us to book", "call to book", "email us to schedule", "fill the form", "phone only", "excel", "spreadsheet"],
    "no_online_booking": ["call us to book", "call to book", "walk-ins", "phone only"],
    "tech_change": ["migrating", "new website", "switching to", "looking for a new"],
    "pain_complaint": ["slow", "missed calls", "long wait", "too many", "struggling", "difficult"],
}

REPLY_KEYWORDS = {
    "unsubscribe": ["unsubscribe", "remove me", "stop emailing", "do not contact", "opt out"],
    "out_of_office": ["out of office", "on leave", "on vacation", "away until", "auto-reply", "automatic reply"],
    "interested": ["interested", "let's talk", "lets talk", "book a call", "send more info", "sounds good", "schedule", "demo"],
    "not_interested": ["not interested", "no thanks", "not a fit", "we already use", "no need"],
    "objection": ["too expensive", "price", "budget", "maybe later", "next quarter", "not right now"],
    "referral": ["talk to", "contact my colleague", "reach out to", "the right person is"],
}


def find_signals(text):
    text = (text or "").lower()
    found = []
    for sig, words in SIGNAL_KEYWORDS.items():
        for w in words:
            if w in text:
                found.append({"signal": sig, "evidence": w, "strength": "medium"})
                break
    return found


def classify_reply_rules(text):
    t = (text or "").lower()
    # order matters - unsubscribe should win over everything
    for label in ["unsubscribe", "out_of_office", "referral", "objection", "not_interested", "interested"]:
        for w in REPLY_KEYWORDS[label]:
            if w in t:
                return {"label": label, "confidence": 0.5, "reason": "matched keyword '" + w + "'"}
    return {"label": "unclear", "confidence": 0.2, "reason": "no keyword matched"}


def score_rules(prospect, icp, signals):
    """simple points system. max 100"""
    score = 0
    reasons = []

    industries = [i.lower() for i in (icp or {}).get("industries", [])]
    ind = (prospect.get("industry") or "").lower()
    if ind and any(ind in i or i in ind for i in industries):
        score += 30
        reasons.append("industry matches ICP")

    emp = prospect.get("employees") or 0
    size = (icp or {}).get("company_size", {})
    try:
        mn = int(size.get("min", 0))
        mx = int(size.get("max", 100000))
    except Exception:
        mn, mx = 0, 100000
    if mn <= emp <= mx:
        score += 20
        reasons.append("company size in range")

    roles = [r.lower() for r in (icp or {}).get("decision_makers", [])]
    role = (prospect.get("contact_role") or "").lower()
    if role and any(r in role or role in r for r in roles):
        score += 15
        reasons.append("contact is a decision maker")

    s = min(len(signals) * 10, 35)
    if s:
        score += s
        reasons.append(f"{len(signals)} buying signals")

    return {"score": min(score, 100), "reason": ", ".join(reasons) or "weak match"}
