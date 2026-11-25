# 깊이 자동 선택 기준(일치도 0.5) 확인: 평가셋 30장에서 DA3 vs DA2-L 일치도 분포와 고른 결과
#   python depth_agree30.py          (CPU에서 실행, 그림당 약 20초)
# 결과: bench/depth_agree30/index.html — 일치도 낮은 순으로, 원본 | DA2-L | DA3 와 자동 선택 결과
import json, os, sys
import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
EVAL = os.path.join(HERE, '..', 'paintings', 'evalset')
OUT = os.path.join(HERE, 'bench', 'depth_agree30'); os.makedirs(OUT, exist_ok=True)
import pipeline as P   # 같은 일치도 계산과 DA3 실행 코드를 그대로 씀


def main():
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from transformers import pipeline
    plt.rcParams['font.family'] = 'Malgun Gothic'
    da2l = pipeline('depth-estimation', model='depth-anything/Depth-Anything-V2-Large-hf', device=-1)
    keys = sorted(f[:-4] for f in os.listdir(EVAL) if f[:2].isdigit() and f.endswith('.jpg'))
    res = []
    for k in keys:
        img = Image.open(os.path.join(EVAL, k + '.jpg')).convert('RGB'); img.thumbnail((1024, 1024))
        a = P.da3(img)
        b = P.norm01(np.asarray(da2l(img)['depth'].resize(img.size), np.float32))
        agree = P.agreement(a, b)
        pick = 'DA3' if agree >= P.AUTO_MIN_AGREE else 'DA2-L'
        fig, ax = plt.subplots(1, 3, figsize=(15, 5 * img.height / img.width + 0.5))
        ax[0].imshow(img); ax[0].set_title(f'{k}  일치도 {agree:.2f} → {pick}')
        ax[1].imshow(b, cmap='inferno'); ax[1].set_title('DA2-L [NC]' + (' ✔' if pick == 'DA2-L' else ''))
        ax[2].imshow(a, cmap='inferno'); ax[2].set_title('DA3 Mono-L' + (' ✔' if pick == 'DA3' else ''))
        for x in ax: x.axis('off')
        plt.tight_layout(); plt.savefig(os.path.join(OUT, k + '.jpg'), dpi=70); plt.close()
        res.append((agree, k, pick))
        print(f'{k:22s} 일치도 {agree:5.2f} → {pick}', flush=True)
    res.sort()
    json.dump([dict(key=k, agreement=round(a, 3), pick=p) for a, k, p in res], open(os.path.join(OUT, 'agree.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    n3 = sum(p == 'DA3' for _, _, p in res)
    rows = ''.join(f'<h3>{k} — 일치도 {a:.2f} → {p}</h3><img src="{k}.jpg">' for a, k, p in res)
    open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(
        "<!doctype html><meta charset=utf-8><title>깊이 자동 선택 30장</title><style>body{font-family:'Malgun Gothic';margin:24px;background:#f6f6f4}img{width:100%;max-width:1400px}</style>"
        f"<h1>깊이 자동 선택 확인 — 기준 일치도 {P.AUTO_MIN_AGREE}</h1><p>DA3 {n3}장, DA2-L {len(res) - n3}장. 일치도 낮은 순. "
        "확인할 것: 기준 근처(0.3~0.7) 그림에서 ✔ 표시된 쪽이 실제로 더 나은지. 밝을수록 가까움.</p>" + rows)
    print('보고서:', os.path.join(OUT, 'index.html'))


if __name__ == '__main__':
    main()
