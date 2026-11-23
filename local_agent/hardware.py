import platform
import subprocess
import psutil


def get_gpu_info():
    # try nvidia first, if nvidia-smi is not there we assume no nvidia gpu
    gpu = {"has_gpu": False, "name": None, "vram_gb": 0}
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL, timeout=5
        ).decode().strip()
        if out:
            first = out.split("\n")[0]
            name, mem = first.split(",")
            gpu["has_gpu"] = True
            gpu["name"] = name.strip()
            gpu["vram_gb"] = round(int(mem.strip()) / 1024, 1)
    except Exception:
        pass

    # apple silicon - gpu shares the ram so we just mark it
    if not gpu["has_gpu"] and platform.system() == "Darwin" and platform.machine() == "arm64":
        gpu["has_gpu"] = True
        gpu["name"] = "Apple Silicon (unified memory)"
        gpu["vram_gb"] = 0  # uses system ram

    return gpu


def get_hardware():
    ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
    free_ram = round(psutil.virtual_memory().available / (1024 ** 3), 1)
    info = {
        "os": platform.system() + " " + platform.release(),
        "cpu": platform.processor() or platform.machine(),
        "cpu_cores": psutil.cpu_count(logical=False),
        "cpu_threads": psutil.cpu_count(logical=True),
        "ram_gb": ram_gb,
        "free_ram_gb": free_ram,
    }
    info.update(get_gpu_info())
    return info


def recommend_model(hw=None):
    """
    Very rough rules. on a normal 16gb laptop without gpu 4b should be ok,
    8b on cpu only is very slow.
    Sizes are from ollama library page (q4 quantized).
    """
    if hw is None:
        hw = get_hardware()

    ram = hw["ram_gb"]
    vram = hw["vram_gb"]

    if hw["has_gpu"] and vram >= 10:
        model = "qwen3:14b"
        profile = "high-performance"
        reason = "GPU with %sGB VRAM found, 14b model fits in vram" % vram
    elif (hw["has_gpu"] and vram >= 6) or ram >= 32:
        model = "qwen3:8b"
        profile = "high-performance"
        reason = "Enough GPU memory / RAM for 8b model"
    elif ram >= 12:
        model = "qwen3:4b"
        profile = "standard"
        reason = "Normal laptop, 4b runs on cpu at ok speed"
    else:
        model = "qwen3:1.7b"
        profile = "low-memory"
        reason = "Less than 12GB RAM, using smallest model. output quality will be lower"

    return {"model": model, "profile": profile, "reason": reason}


if __name__ == "__main__":
    h = get_hardware()
    print(h)
    print(recommend_model(h))
