import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import load_env
load_env()   # HF_TOKEN (Stable Audio 3처럼 사용 동의가 필요한 모델에 필요)
from huggingface_hub import snapshot_download
for rid in sys.argv[1:]:
    t = time.time()
    try:
        snapshot_download(rid, allow_patterns=['*.json', '*.safetensors', '*.py', '*.txt', '*.model', '*.jinja', 'tokenizer*'])
        print(f'OK   {rid}  {time.time() - t:.0f}s', flush=True)
    except Exception as e:
        print(f'FAIL {rid}  {type(e).__name__}: {e}', flush=True)
