"""
Offline acceptance test.
1. turn off wifi / internet
2. make sure ollama is running (ollama serve)
3. python offline_test.py

To be extra sure nothing goes outside, this script blocks every network
connection that is not localhost. If any code tries to call internet it will
crash with "BLOCKED".
"""
import os
import socket
import sys

# otherwise sentence-transformers tries to check huggingface for updates
os.environ["HF_HUB_OFFLINE"] = "1"

real_connect = socket.socket.connect


def only_local(self, address):
    host = address[0] if isinstance(address, tuple) else address
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError("BLOCKED non-local connection to " + str(address))
    return real_connect(self, address)


socket.socket.connect = only_local

import database as db
import workflows
import llm
import import_data

print("=== OFFLINE ACCEPTANCE TEST ===")
status = llm.check_ollama()
if not status["running"]:
    print("Ollama is not running, start it first")
    sys.exit(1)
print("ollama ok, model:", llm.get_model())

db.init_db()
product = db.query("SELECT * FROM products WHERE product_name='BookEasy'", one=True)
if not product:
    print("run seed.py first")
    sys.exit(1)
pid = product["id"]
prospect = db.query("SELECT * FROM prospects WHERE product_id=? LIMIT 1", (pid,), one=True)
if not prospect:
    # prospects were not loaded from the dashboard yet, load them from the local json
    import_data.import_prospects_for_product(pid)
    prospect = db.query("SELECT * FROM prospects WHERE product_id=? LIMIT 1", (pid,), one=True)
prid = prospect["id"]

results = []


def check(name, func):
    try:
        r = func()
        ok = isinstance(r, dict) and "error" not in r and "rule_based" not in str(r.get("source", ""))
        results.append((name, ok))
        print(("PASS" if ok else "FAIL"), name)
        if not ok:
            print("   ", r)
    except Exception as e:
        results.append((name, False))
        print("FAIL", name, e)


check("1. business profile", lambda: workflows.business_profile(pid))
check("2. product ICP", lambda: workflows.generate_icp(pid))
check("3. prospect research (local data)", lambda: workflows.research_prospect(prid))
check("4. buying signal classification", lambda: workflows.classify_signals(prid))
check("5. problem statement", lambda: workflows.problem_statement(prid))
check("6. prospect scoring", lambda: workflows.score_prospect(prid))
check("7. personalised email", lambda: workflows.write_email(prid))
check("8. reply classification", lambda: workflows.classify_reply("Sounds interesting, can we do a demo next week?", prid))

print()
passed = len([r for r in results if r[1]])
print(f"{passed}/{len(results)} passed")
print("see logs/llm_calls.log for the local inference log")
