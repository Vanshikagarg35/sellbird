from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import json

import database as db
import workflows
import llm
import hardware
import import_data

app = FastAPI(title="Local Sales Agent")
db.init_db()

app.mount("/static", StaticFiles(directory="static"), name="static")


class ProductIn(BaseModel):
    company_name: str
    product_name: str
    description: str
    price: str = ""
    company_info_file: str = "data/company_info/tasknest.txt"


class ReplyIn(BaseModel):
    reply_text: str
    prospect_id: int = None


class ModelIn(BaseModel):
    model: str


@app.get("/")
def home():
    return FileResponse("static/index.html")


# ---------- status ----------

@app.get("/api/status")
def status():
    hw = hardware.get_hardware()
    rec = hardware.recommend_model(hw)
    oll = llm.check_ollama()
    model = llm.get_model()
    msg = "ok"
    if not oll["running"]:
        msg = "Ollama is not running. AI features are paused, tasks will be queued. Start it with: ollama serve"
    elif model not in oll["models"] and (model + ":latest") not in oll["models"]:
        msg = f"Model {model} is not downloaded. Run: ollama pull {model}"
    pending = db.query("SELECT COUNT(*) as c FROM task_queue WHERE status='pending'", one=True)["c"]
    return {"hardware": hw, "recommended": rec, "ollama": oll, "model": model,
            "message": msg, "pending_tasks": pending}


@app.post("/api/model")
def change_model(m: ModelIn):
    llm.set_model(m.model)
    return {"model": m.model}


@app.get("/api/logs")
def logs():
    return {"lines": llm.read_logs(100)}


# ---------- products ----------

@app.post("/api/products")
def add_product(p: ProductIn):
    pid = db.add_product(p.company_name, p.product_name, p.description, p.price, p.company_info_file)
    return {"id": pid}


@app.get("/api/products")
def list_products():
    return db.query("SELECT * FROM products ORDER BY id")


@app.get("/api/products/{pid}")
def get_product(pid: int):
    return {"product": db.get_product(pid), "profile": db.latest_profile(pid), "icp": db.latest_icp(pid)}


@app.post("/api/products/{pid}/profile")
def make_profile(pid: int):
    return workflows.business_profile(pid)


@app.post("/api/products/{pid}/icp")
def make_icp(pid: int):
    return workflows.generate_icp(pid)


@app.post("/api/products/{pid}/import_prospects")
def import_prospects(pid: int):
    n = import_data.import_prospects_for_product(pid)
    return {"imported": n}


@app.post("/api/products/{pid}/run_all")
def run_all(pid: int):
    return workflows.run_full_pipeline(pid)


# ---------- prospects ----------

@app.get("/api/products/{pid}/prospects")
def list_prospects(pid: int):
    rows = db.query("SELECT id, company, contact_name, contact_role, industry, employees, location, score, status, signals_json, problem_statement, score_reason FROM prospects WHERE product_id=? ORDER BY score DESC", (pid,))
    for r in rows:
        r["signals"] = json.loads(r.pop("signals_json") or "{}").get("signals", [])
    return rows


@app.get("/api/prospects/{prid}")
def get_prospect(prid: int):
    pr = db.query("SELECT * FROM prospects WHERE id=?", (prid,), one=True)
    pr["emails"] = db.query("SELECT * FROM emails WHERE prospect_id=? ORDER BY id DESC", (prid,))
    return pr


@app.post("/api/prospects/{prid}/research")
def research(prid: int):
    return workflows.research_prospect(prid)


@app.post("/api/prospects/{prid}/signals")
def signals(prid: int):
    return workflows.classify_signals(prid)


@app.post("/api/prospects/{prid}/problem")
def problem(prid: int):
    return workflows.problem_statement(prid)


@app.post("/api/prospects/{prid}/score")
def score(prid: int):
    return workflows.score_prospect(prid)


@app.post("/api/prospects/{prid}/email")
def email(prid: int):
    return workflows.write_email(prid)


# ---------- replies ----------

@app.get("/api/sample_replies")
def sample_replies():
    with open("data/sample_replies.json", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/replies/classify")
def classify(r: ReplyIn):
    return workflows.classify_reply(r.reply_text, r.prospect_id)


@app.get("/api/replies")
def list_replies():
    return db.query("SELECT * FROM replies ORDER BY id DESC")


# ---------- queue ----------

@app.get("/api/queue")
def queue():
    return db.query("SELECT * FROM task_queue ORDER BY id DESC LIMIT 50")


@app.post("/api/queue/process")
def process_queue():
    return workflows.process_queue()
