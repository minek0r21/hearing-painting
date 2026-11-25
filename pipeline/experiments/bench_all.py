# 모델이 다 받아지면 바로 측정 → 마지막에 보고서. 다운로드는 download_models.py가 따로 진행
import os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['HF_HUB_DISABLE_XET'] = '1'
from huggingface_hub import snapshot_download
ORDER = [('qwen35_4b', 'Qwen/Qwen3.5-4B'), ('minicpm47_1b', 'openbmb/MiniCPM-V-4.7-1B'),
         ('internvl35_4b', 'OpenGVLab/InternVL3_5-4B-HF'), ('gemma4_e2b', 'google/gemma-4-E2B-it')]
if len(sys.argv) > 1:   # 예: python bench_all.py gemma4_e2b qwen35_9b_nf4
    sys.path.insert(0, HERE)
    from bench_run import MODELS
    ORDER = [(k, MODELS[k]) for k in sys.argv[1:]]
PATTERNS =['*.json', '*.safetensors', '*.py', '*.txt', '*.model', '*.jinja', 'tokenizer*']
py = sys.executable
for key, rid in ORDER:
    while True:
        try:
            snapshot_download(rid, allow_patterns=PATTERNS, local_files_only=True)
            # 받는 중인 파일이 남아 있으면 아직
            break
        except Exception:
            time.sleep(20)
    print(f'== {key} 측정 시작', flush=True)
    r = subprocess.run([py, os.path.join(HERE, 'bench_run.py'), key], cwd=HERE)
    print(f'== {key} 종료 코드 {r.returncode}', flush=True)
    subprocess.run([py, os.path.join(HERE, 'bench_report.py')], cwd=HERE)
