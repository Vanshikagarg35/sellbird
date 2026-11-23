"""
Main sales agent workflows. Every function first tries the local LLM (ollama).
If ollama is down -> task goes to queue + we return rule based result (if possible)
so user can still see something. source field tells what was used.
"""
import json
import os

import database as db
import llm
import rules
import embed
from llm import OllamaDown

SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer"},
        "reason": {"type": "string"},
        "priority": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["score", "reason", "priority"],
}

PROBLEM_SCHEMA = {
    "type": "object",
    "properties": {"problem_statement": {"type": "string"}},
    "required": ["problem_statement"],
}

EMAIL_SCHEMA = {
    "type": "object",
    "properties": {"subject": {"type": "string"}, "body": {"type": "string"}},
    "required": ["subject", "body"],
}

SYSTEM = "You are a B2B sales assistant. Be specific and short. Only use the facts given to you, do not invent numbers or names."


def pick(res, keys):
    # model does not always use the exact key we asked for (problemStatement, email_body etc)
    for k in keys:
        if res.get(k):
            return res[k]
    for v in res.values():
        if isinstance(v, str) and len(v) > 20:
            return v
    return ""


def read_company_file(path):
    if not path:
        return ""
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(__file__), path)
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print("cant read company file", path, e)
        return ""


# 1. business profile
def business_profile(product_id):
    p = db.get_product(product_id)
    if not p:
        return {"error": "product not found"}
    info = read_company_file(p["company_info_file"])

    prompt = f"""Read the company information and make a business profile.

Company: {p['company_name']}
Product: {p['product_name']}
Product description: {p['description']}
Price: {p['price']}

Company information document:
{info[:4000]}

Return JSON with keys:
"summary" (2-3 sentences), "value_proposition", "key_features" (list),
"target_market", "differentiators" (list), "tone_of_voice"
"""
    try:
        profile = llm.ask(prompt, system=SYSTEM, want_json=True, task="business_profile")
        source = "local_llm:" + llm.get_model()
    except OllamaDown as e:
        db.add_to_queue("business_profile", {"product_id": product_id}, str(e))
        return {"error": str(e), "queued": True}

    db.save_profile(product_id, profile, source)
    return {"profile": profile, "source": source}


# 2. ICP for one product
def generate_icp(product_id):
    p = db.get_product(product_id)
    profile = db.latest_profile(product_id)
    if not profile:
        return {"error": "generate business profile first"}

    prompt = f"""Create an Ideal Customer Profile (ICP) for this specific product.

Product: {p['product_name']} by {p['company_name']}
Business profile: {json.dumps(profile)}

Return JSON with keys:
"industries" (list of 3-5 industries),
"company_size" (object with "min" and "max" number of employees),
"locations" (list),
"decision_makers" (list of job titles),
"pain_points" (list),
"buying_signals" (list of things we can see on a company website that show they need this product),
"disqualifiers" (list)
"""
    try:
        icp = llm.ask(prompt, system=SYSTEM, want_json=True, task="icp")
        source = "local_llm:" + llm.get_model()
    except OllamaDown as e:
        db.add_to_queue("icp", {"product_id": product_id}, str(e))
        return {"error": str(e), "queued": True}

    db.save_icp(product_id, icp, source)
    return {"icp": icp, "source": source}


# 3. research one prospect from data we already downloaded
def research_prospect(prospect_id):
    pr = db.query("SELECT * FROM prospects WHERE id=?", (prospect_id,), one=True)
    if not pr:
        return {"error": "prospect not found"}
    icp = db.latest_icp(pr["product_id"]) or {}
    text = pr["page_text"] or ""
    if not text:
        return {"error": "no page text saved for this prospect. run the scraper or import data first"}

    # pick the most useful parts of the website using embeddings
    q = "company services customers problems hiring growth " + " ".join(icp.get("pain_points", []))
    chunks = embed.top_chunks(q, text)
    sim, method = embed.similarity(" ".join(icp.get("pain_points", [])) or "business", text[:2000])

    prompt = f"""Research notes for a sales prospect. Use ONLY the website text below.

Company: {pr['company']} ({pr['industry']}, ~{pr['employees']} employees, {pr['location']})
Contact: {pr['contact_name']} - {pr['contact_role']}

Website text (most relevant parts):
{chr(10).join(chunks)}

Return JSON with keys: "what_they_do", "customers", "current_tools_or_process",
"recent_events" (list), "possible_needs" (list), "facts_for_personalization" (list of short facts from the text)
"""
    try:
        research = llm.ask(prompt, system=SYSTEM, want_json=True, task="research")
        source = "local_llm:" + llm.get_model()
    except OllamaDown as e:
        db.add_to_queue("research", {"prospect_id": prospect_id}, str(e))
        return {"error": str(e), "queued": True}

    research["icp_similarity"] = sim
    research["similarity_method"] = method
    db.execute("UPDATE prospects SET research_json=?, status='researched' WHERE id=?",
               (json.dumps(research), prospect_id))
    return {"research": research, "source": source}


# 4. buying signals
def classify_signals(prospect_id):
    pr = db.query("SELECT * FROM prospects WHERE id=?", (prospect_id,), one=True)
    icp = db.latest_icp(pr["product_id"]) or {}
    text = (pr["page_text"] or "")[:3500]

    prompt = f"""Find buying signals in this company's website text.

Buying signals we care about for this product: {icp.get('buying_signals', [])}

Website text:
{text}

Return JSON: {{"signals": [{{"signal": "short name", "evidence": "exact phrase from text", "strength": "high|medium|low"}}], "intent_level": "high|medium|low|none"}}
If you are not sure, do not add the signal. evidence MUST be copied from the text.
"""
    try:
        res = llm.ask(prompt, system=SYSTEM, want_json=True, task="buying_signals", temperature=0.1)
        signals = res.get("signals", [])
        # remove signals where the evidence is not really in the text (model made it up)
        checked = []
        for s in signals:
            ev = str(s.get("evidence", "")).lower()[:40]
            if ev and ev in text.lower():
                checked.append(s)
            else:
                print("dropping signal, evidence not found in text:", s)
        res["signals"] = checked
        source = "local_llm:" + llm.get_model()
    except OllamaDown as e:
        db.add_to_queue("buying_signals", {"prospect_id": prospect_id}, str(e))
        sigs = rules.find_signals(text)
        res = {"signals": sigs, "intent_level": "unknown"}
        source = "rule_based (ollama down, queued for AI)"

    db.execute("UPDATE prospects SET signals_json=? WHERE id=?", (json.dumps(res), prospect_id))
    return {"result": res, "source": source}


# 5. problem statement
def problem_statement(prospect_id):
    pr = db.query("SELECT * FROM prospects WHERE id=?", (prospect_id,), one=True)
    p = db.get_product(pr["product_id"])
    research = json.loads(pr["research_json"] or "{}")
    signals = json.loads(pr["signals_json"] or "{}")

    prompt = f"""Write a problem statement for this prospect: what problem do they likely have that
{p['product_name']} solves. 2-3 sentences, based only on the research and signals. Do not exaggerate.

Prospect: {pr['company']} ({pr['industry']})
Research: {json.dumps(research)}
Signals: {json.dumps(signals)}
Our product: {p['description']}

Return JSON: {{"problem_statement": "the 2-3 sentences"}}"""
    try:
        # plain text mode made qwen3 write its whole thinking ("Okay, let me tackle this..."),
        # with a json schema it only gives the answer
        res = llm.ask(prompt, system=SYSTEM, task="problem_statement", schema=PROBLEM_SCHEMA)
        ps = str(res.get("problem_statement", "")).strip()
    except OllamaDown as e:
        db.add_to_queue("problem_statement", {"prospect_id": prospect_id}, str(e))
        return {"error": str(e), "queued": True}

    if not ps:
        return {"error": "model returned empty problem statement, please click Problem again"}

    db.execute("UPDATE prospects SET problem_statement=? WHERE id=?", (ps, prospect_id))
    return {"problem_statement": ps, "source": "local_llm:" + llm.get_model()}


# 6. scoring - llm score + rule score mixed
def score_prospect(prospect_id):
    pr = db.query("SELECT * FROM prospects WHERE id=?", (prospect_id,), one=True)
    icp = db.latest_icp(pr["product_id"]) or {}
    signals = json.loads(pr["signals_json"] or "{}").get("signals", [])
    rule = rules.score_rules(pr, icp, signals)

    # small model was copying the whole icp json back instead of scoring, so give it short text
    size = icp.get("company_size", {})
    prompt = f"""Score how good this prospect is for our product from 0 to 100.

What our ideal customer looks like:
- industries: {", ".join(icp.get("industries", []))}
- size: {size.get("min", "?")} to {size.get("max", "?")} employees
- locations: {", ".join(icp.get("locations", []))}
- decision makers: {", ".join(icp.get("decision_makers", []))}
- pain points: {", ".join(icp.get("pain_points", []))}

Prospect: company={pr['company']}, industry={pr['industry']}, employees={pr['employees']},
location={pr['location']}, contact role={pr['contact_role']}
Buying signals: {json.dumps(signals)}
Problem statement: {pr['problem_statement']}

Return JSON: {{"score": number, "reason": "one sentence", "priority": "high|medium|low"}}"""
    try:
        res = llm.ask(prompt, system=SYSTEM, task="scoring", temperature=0.1, schema=SCORE_SCHEMA)
        ai_score = None
        try:
            ai_score = int(res["score"])
        except:
            # sometimes model uses other key name like prospect_score, take first number
            for v in res.values():
                if isinstance(v, (int, float)) and 0 <= v <= 100:
                    ai_score = int(v)
                    break
        if ai_score is None:
            # dont count it as 0
            llm.write_log("WARN scoring no score in model output: " + json.dumps(res)[:300])
        if ai_score is None:
            final = rule["score"]
            reason = "AI did not return a score, rules only: " + rule["reason"]
        else:
            # 60% ai, 40% rules. rules keep it a bit stable because small model scores jump around
            final = round(ai_score * 0.6 + rule["score"] * 0.4)
            reason = f"AI: {res.get('reason', '')} | Rules: {rule['reason']}"
        source = "local_llm+rules"
    except OllamaDown as e:
        db.add_to_queue("scoring", {"prospect_id": prospect_id}, str(e))
        final = rule["score"]
        reason = "Rules only (ollama down): " + rule["reason"]
        source = "rule_based"

    status = "qualified" if final >= 60 else "low_fit"
    db.execute("UPDATE prospects SET score=?, score_reason=?, status=? WHERE id=?",
               (final, reason, status, prospect_id))
    return {"score": final, "reason": reason, "source": source}


# 7. email
def write_email(prospect_id):
    pr = db.query("SELECT * FROM prospects WHERE id=?", (prospect_id,), one=True)
    p = db.get_product(pr["product_id"])
    profile = db.latest_profile(pr["product_id"]) or {}
    research = json.loads(pr["research_json"] or "{}")

    # skip titles, otherwise "Dr. Anjali Kulkarni" became "Hi Dr.,"
    parts = [w for w in (pr["contact_name"] or "there").split(" ") if w.lower().strip(".") not in ("dr", "mr", "mrs", "ms")]
    first_name = parts[0] if parts else "there"

    prompt = f"""Write a short cold email (under 120 words) from {p['company_name']} to {pr['contact_name']},
{pr['contact_role']} at {pr['company']}.

Use 1 or 2 of these real facts about them to personalise: {research.get('facts_for_personalization', [])}
Their problem: {pr['problem_statement']}
Our product: {p['product_name']} - {profile.get('value_proposition', p['description'])}
Tone: {profile.get('tone_of_voice', 'friendly, simple')}

Rules: no fake statistics, no "I hope this email finds you well", one clear question at the end.
Start with "Hi {first_name},".
Return JSON with "subject" and "body"."""
    try:
        res = llm.ask(prompt, system=SYSTEM, task="email", temperature=0.7, schema=EMAIL_SCHEMA)
    except OllamaDown as e:
        db.add_to_queue("email", {"prospect_id": prospect_id}, str(e))
        return {"error": str(e), "queued": True}

    subject = res.get("subject", "")
    body = pick(res, ["body", "email_body", "email", "content", "raw_output"])
    if not body:
        llm.write_log("WARN email empty, model output was: " + json.dumps(res)[:300])
        return {"error": "model returned empty email, please click Email again"}
    source = "local_llm:" + llm.get_model()
    db.execute("INSERT INTO emails (prospect_id, subject, body, source, created_at) VALUES (?,?,?,?,?)",
               (prospect_id, subject, body, source, db.now()))
    db.execute("UPDATE prospects SET status='email_drafted' WHERE id=?", (prospect_id,))
    return {"subject": subject, "body": body, "source": source}


# 8. reply classification
LABELS = ["interested", "not_interested", "objection", "out_of_office", "referral", "unsubscribe", "unclear"]


def classify_reply(reply_text, prospect_id=None):
    prompt = f"""Classify this reply to a sales email.

Reply:
\"\"\"{reply_text}\"\"\"

Labels: {LABELS}
Return JSON: {{"label": one of the labels, "confidence": 0-1, "reason": "short", "suggested_action": "what the sales person should do next"}}"""
    try:
        res = llm.ask(prompt, system=SYSTEM, want_json=True, task="reply_classification", temperature=0.1)
        if res.get("label") not in LABELS:
            res["label"] = "unclear"
        source = "local_llm:" + llm.get_model()
    except OllamaDown as e:
        db.add_to_queue("reply_classification", {"reply_text": reply_text, "prospect_id": prospect_id}, str(e))
        res = rules.classify_reply_rules(reply_text)
        res["suggested_action"] = "check manually"
        source = "rule_based (ollama down, queued for AI)"

    db.execute("INSERT INTO replies (prospect_id, reply_text, label, confidence, suggested_action, source, created_at) VALUES (?,?,?,?,?,?,?)",
               (prospect_id, reply_text, res.get("label"), res.get("confidence"), res.get("suggested_action"), source, db.now()))
    res["source"] = source
    return res


def run_full_pipeline(product_id):
    """runs everything for one product, used by the 'Run all' button and offline test"""
    out = {"steps": []}
    r = business_profile(product_id)
    out["steps"].append(("business_profile", "error" not in r))
    if "error" in r:
        out["error"] = r["error"]
        return out
    r = generate_icp(product_id)
    out["steps"].append(("icp", "error" not in r))

    prospects = db.query("SELECT id FROM prospects WHERE product_id=?", (product_id,))
    for pr in prospects:
        pid = pr["id"]
        research_prospect(pid)
        classify_signals(pid)
        problem_statement(pid)
        score_prospect(pid)
    # emails only for good ones
    good = db.query("SELECT id FROM prospects WHERE product_id=? AND score>=60 ORDER BY score DESC", (product_id,))
    for pr in good:
        write_email(pr["id"])
    out["steps"].append(("prospects_processed", len(prospects)))
    out["steps"].append(("emails_written", len(good)))
    return out


TASK_FUNCS = {
    "business_profile": lambda p: business_profile(p["product_id"]),
    "icp": lambda p: generate_icp(p["product_id"]),
    "research": lambda p: research_prospect(p["prospect_id"]),
    "buying_signals": lambda p: classify_signals(p["prospect_id"]),
    "problem_statement": lambda p: problem_statement(p["prospect_id"]),
    "scoring": lambda p: score_prospect(p["prospect_id"]),
    "email": lambda p: write_email(p["prospect_id"]),
    "reply_classification": lambda p: classify_reply(p["reply_text"], p.get("prospect_id")),
}


def process_queue():
    status = llm.check_ollama()
    if not status["running"]:
        return {"error": "ollama still not running", "processed": 0}
    tasks = db.query("SELECT * FROM task_queue WHERE status='pending' ORDER BY id")
    done = 0
    for t in tasks:
        func = TASK_FUNCS.get(t["task_type"])
        if not func:
            continue
        # mark done first, otherwise if it fails again it adds a new row and we get duplicates
        db.execute("UPDATE task_queue SET status='done', done_at=? WHERE id=?", (db.now(), t["id"]))
        try:
            func(json.loads(t["payload"]))
            done += 1
        except Exception as e:
            print("queue task failed", t["id"], e)
            db.execute("UPDATE task_queue SET status='failed', error=? WHERE id=?", (str(e), t["id"]))
    return {"processed": done, "total": len(tasks)}
