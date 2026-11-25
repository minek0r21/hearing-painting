# 밤새 실행: ① 깊이 모델 비교(DA2-Small vs DA2-Large) ② 다음 단계 모델 미리 받기
# 결과: bench/depth/<그림>.jpg (원본 | DA2-S | DA2-L), bench/overnight_log.txt
import os, sys, time, json, gc, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['HF_HUB_DISABLE_XET'] = '1'
for line in open(os.path.join(HERE, '.env'), encoding='utf-8-sig'):
    if '=' in line and not line.startswith('#'):
        k, v = line.strip().split('=', 1)
        if v.strip():
            os.environ[k.strip()] = v.strip()
LOG = os.path.join(HERE, 'bench', 'overnight_log.txt')


def log(msg):
    line = time.strftime('%H:%M:%S ') + msg
    print(line, flush=True)
    open(LOG, 'a', encoding='utf-8').write(line + '\n')


def depth_compare():
    import numpy as np, torch
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    from transformers import pipeline
    out = os.path.join(HERE, 'bench', 'depth'); os.makedirs(out, exist_ok=True)
    names = [n[:-4] for n in os.listdir(os.path.join(HERE, 'bench', 'inputs')) if n.endswith('.jpg')]
    models = {'DA2-S': 'depth-anything/Depth-Anything-V2-Small-hf', 'DA2-L [NC]': 'depth-anything/Depth-Anything-V2-Large-hf'}
    maps = {n: {} for n in names}
    for label, mid in models.items():
        pipe = pipeline('depth-estimation', model=mid, device=0)
        for n in names:
            img = Image.open(os.path.join(HERE, 'bench', 'inputs', n + '.jpg')).convert('RGB')
            torch.cuda.reset_peak_memory_stats(); t = time.time()
            d = np.asarray(pipe(img)['depth'].resize(img.size), dtype=np.float32)
            lo, hi = np.percentile(d, 1), np.percentile(d, 99)
            maps[n][label] = np.clip((d - lo) / (hi - lo + 1e-6), 0, 1)
            log(f'depth {label:10s} {n:10s} {time.time() - t:5.1f}s VRAM {torch.cuda.max_memory_allocated() / 1e9:.2f}GB')
        del pipe; gc.collect(); torch.cuda.empty_cache()
    for n in names:
        img = Image.open(os.path.join(HERE, 'bench', 'inputs', n + '.jpg')).convert('RGB')
        fig, ax = plt.subplots(1, 1 + len(models), figsize=(6 * (1 + len(models)), 6 * img.height / img.width))
        ax[0].imshow(img); ax[0].set_title('original')
        for i, label in enumerate(models):
            ax[i + 1].imshow(maps[n][label], cmap='inferno'); ax[i + 1].set_title(label + ' (bright = near)')
        for a in ax: a.axis('off')
        plt.tight_layout(); plt.savefig(os.path.join(out, n + '.jpg'), dpi=80); plt.close()
    log('depth compare done -> bench/depth/')


def prefetch():
    from huggingface_hub import snapshot_download
    pats = ['*.json', '*.safetensors', '*.py', '*.txt', '*.model', '*.jinja', 'tokenizer*', '*.ckpt', '*.pt']
    for rid in ['google/owlv2-large-patch14-ensemble', 'facebook/sam3',
                'stabilityai/stable-audio-3-small-sfx', 'stabilityai/stable-audio-3-medium']:
        t = time.time()
        try:
            snapshot_download(rid, allow_patterns=pats)
            log(f'prefetch OK   {rid} {time.time() - t:.0f}s')
        except Exception as e:
            log(f'prefetch FAIL {rid} {type(e).__name__}: {str(e)[:150]}  (gated이면 HF 페이지에서 약관 동의 필요)')


if __name__ == '__main__':
    for step in (depth_compare, prefetch):
        try:
            step()
        except Exception:
            log('ERROR in ' + step.__name__ + '\n' + traceback.format_exc()[-1500:])
    log('overnight finished')
