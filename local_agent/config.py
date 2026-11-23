import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
DB_PATH = os.path.join(DATA_DIR, "sales_agent.db")

# ollama runs locally on this port by default
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
# if MODEL_NAME is empty we pick one based on hardware (see hardware.py)
MODEL_NAME = os.getenv("MODEL_NAME", "")
EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")

OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
