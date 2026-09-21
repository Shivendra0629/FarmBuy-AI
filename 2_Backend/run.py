import uvicorn
import os
import sys

# Ensure utf-8 encoding for standard output on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

if __name__ == "__main__":
    print("[FarmBuy AI] Starting platform backend on http://127.0.0.1:8000 ...")
    print("[FarmBuy AI] Interactive API Docs: http://127.0.0.1:8000/docs")
    print("[FarmBuy AI] Web Dashboard: http://127.0.0.1:8000/")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
