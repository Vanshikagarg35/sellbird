"""
All the AI calls go through this file. It only talks to ollama on localhost.
There is NO cloud fallback, if ollama is down we raise OllamaDown and the
caller decides (rule based output or put in queue).
"""
import json
import re
import time
import datetime
import requests

import config
from hardware import recommend_model

log_file = config.LOG_DIR + "/llm_calls.log"

current_model = config.MODEL_NAME


class OllamaDown(Exception):
    pass


def get_model():
    global current_model
    if not current_model:
        current_model = recommend_model()["model"]
    return current_model


def set_model(name):
    global current_model
    current_model = name


def write_log(line):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {line}\n")


def check_ollama():
    """returns dict with status + list of models that are pulled"""
    try:
        r = requests.get(config.OLLAMA_URL + "/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
        return {"running": True, "models": models, "url": config.OLLAMA_URL}
    except Exception as e:
        return {"running": False, "models": [], "url": config.OLLAMA_URL, "error": str(e)}


def clean_output(text):
    # qwen3 sometimes still puts <think>...</think> even with think false
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return text.strip()


def ask(prompt, system=None, want_json=False, task="general", temperature=0.4, is_retry=False, schema=None):
    model = get_model()

    # safety check so nobody can point this to some cloud url by mistake
    if not ("localhost" in config.OLLAMA_URL or "127.0.0.1" in config.OLLAMA_URL
            or config.OLLAMA_URL.startswith("http://192.168.")):
        print("WARNING: OLLAMA_URL is not local -", config.OLLAMA_URL)

    # qwen3 was still writing its thinking ("Okay, the user wants...") even with think false
    # and taking 2-3 min. /no_think in prompt stops it
    if "qwen3" in model:
        prompt = prompt + "\n/no_think"

    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {"temperature": temperature, "num_predict": 1000, "repeat_penalty": 1.1},
    }
    if system:
        body["system"] = system
    if schema:
        # ollama structured output - model has to follow these exact keys
        body["format"] = schema
        want_json = True
    elif want_json:
        body["format"] = "json"

    start = time.time()
    try:
        r = requests.post(config.OLLAMA_URL + "/api/generate", json=body, timeout=config.OLLAMA_TIMEOUT)
    except requests.exceptions.ConnectionError:
        write_log(f"FAILED task={task} model={model} reason=ollama not reachable at {config.OLLAMA_URL}")
        raise OllamaDown("Ollama is not running at " + config.OLLAMA_URL + ". Start it with `ollama serve`")
    except requests.exceptions.Timeout:
        write_log(f"FAILED task={task} model={model} reason=timeout")
        raise OllamaDown("Ollama took too long to respond (timeout " + str(config.OLLAMA_TIMEOUT) + "s)")

    # sometimes model gets stuck writing same thing again and ollama stops it, try once more
    if r.status_code != 200 and "repeat limit" in r.text and not is_retry:
        write_log(f"RETRY task={task} model={model} reason=token repeat limit")
        return ask(prompt.replace("\n/no_think", ""), system, want_json, task, temperature=0.2, is_retry=True, schema=schema)

    if r.status_code != 200:
        write_log(f"FAILED task={task} model={model} status={r.status_code} body={r.text[:200]}")
        if "not found" in r.text:
            raise OllamaDown(f"Model {model} not found. Run: ollama pull {model}")
        raise OllamaDown("Ollama error: " + r.text[:200])

    data = r.json()
    took = round(time.time() - start, 2)
    out = clean_output(data.get("response", ""))

    # for debugging - last request and raw answer (file is overwritten every call)
    with open(config.LOG_DIR + "/last_call.txt", "w", encoding="utf-8") as f:
        f.write("TASK: " + task + "\nFORMAT: " + json.dumps(body.get("format")) + "\n\nSYSTEM:\n" + str(system)
                + "\n\nPROMPT:\n" + prompt + "\n\nRAW RESPONSE:\n" + data.get("response", "")
                + "\n\nTHINKING:\n" + str(data.get("thinking", "")))

    # eval_count = output tokens. this is just for logs, nothing is billed
    write_log(
        f"OK task={task} model={model} url={config.OLLAMA_URL} time={took}s "
        f"prompt_tokens={data.get('prompt_eval_count')} output_tokens={data.get('eval_count')} cost=$0"
    )

    if want_json:
        return parse_json(out)
    return out


def lower_keys(d):
    # model sometimes gives "Subject" or "Score" instead of "subject"/"score"
    if isinstance(d, dict):
        return {str(k).lower(): v for k, v in d.items()}
    return {"raw_output": str(d), "parse_error": True}


def parse_json(text):
    try:
        return lower_keys(json.loads(text))
    except Exception:
        # small models sometimes add text before/after the json
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return lower_keys(json.loads(m.group(0)))
            except:
                pass
    print("could not parse json from model:", text[:300])
    return {"raw_output": text, "parse_error": True}


def read_logs(n=50):
    try:
        with open(log_file, encoding="utf-8") as f:
            lines = f.readlines()
        return lines[-n:]
    except FileNotFoundError:
        return []
