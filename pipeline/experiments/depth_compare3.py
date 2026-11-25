# 깊이 모델 비교 (Q4): 원본 | DA2-S(현재) | DA2-L [NC] | DA3 Mono-Large(ONNX, Apache-2.0)
#   python depth_compare3.py [--gpu]
# 결과: bench/depth3/<그림>.jpg, bench/depth3/index.html
# 모두 "밝을수록 가까움", 같은 정규화(1~99 백분위)와 같은 색 지도로 그림.
import os, sys, time, gc
import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
IN = os.path.join(HERE, 'bench', 'inputs')
OUT = os.path.join(HERE, 'bench', 'depth3'); os.makedirs(OUT, exist_ok=True)
DEVICE = 0 if '--gpu' in sys.argv else -1
DA3_SIZE = 728          # ONNX 빌드는 1036/728/518/364/252 정사각형만 받음
names = sorted(n[:-4] for n in os.listdir(IN) if n.endswith('.jpg'))


def norm(d):
    lo, hi = np.percentile(d, 1), np.percentile(d, 99)
    return np.clip((d - lo) / (hi - lo + 1e-6), 0, 1)


def run_da2(mid):
    from transformers import pipeline
    pipe = pipeline('depth-estimation', model=mid, device=DEVICE)
    res, secs = {}, []
    for n in names:
        img = Image.open(os.path.join(IN, n + '.jpg')).convert('RGB')
        t = time.time()
        res[n] = norm(np.asarray(pipe(img)['depth'].resize(img.size), dtype=np.float32))
        secs.append(time.time() - t)
    del pipe; gc.collect()
    return res, float(np.mean(secs))


def run_da3():
    import onnxruntime as ort
    from huggingface_hub import hf_hub_download
    path = hf_hub_download('Jens-Duttke/Depth-Anything-3-MONO-ONNX', 'da-v3-mono-large_fp16_opset21_optimized.onnx')
    sess = ort.InferenceSession(path, providers=['CPUExecutionProvider'])
    iname, oname = sess.get_inputs()[0].name, sess.get_outputs()[0].name
    mean, std = np.array([0.485, 0.456, 0.406], np.float32), np.array([0.229, 0.224, 0.225], np.float32)
    res, secs = {}, []
    for n in names:
        img = Image.open(os.path.join(IN, n + '.jpg')).convert('RGB')
        x = np.asarray(img.resize((DA3_SIZE, DA3_SIZE), Image.BICUBIC), np.float32) / 255.0
        x = ((x - mean) / std).transpose(2, 0, 1)[None].astype(np.float16)
        t = time.time()
        d = sess.run([oname], {iname: x})[0].squeeze().astype(np.float32)   # disparity: 클수록 가까움, 하늘 = 0
        secs.append(time.time() - t)
        d = np.nan_to_num(d, nan=0.0)
        d = np.asarray(Image.fromarray(d).resize(img.size, Image.BICUBIC), np.float32)
        res[n] = norm(d)
    return res, float(np.mean(secs))


def main():
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    maps, timing = {}, {}
    for label, fn in [('DA2-S (현재)', lambda: run_da2('depth-anything/Depth-Anything-V2-Small-hf')),
                      ('DA2-L [NC]', lambda: run_da2('depth-anything/Depth-Anything-V2-Large-hf')),
                      ('DA3 Mono-L', run_da3)]:
        maps[label], timing[label] = fn()
        print(f'{label}: 평균 {timing[label]:.1f}s/장 ({"GPU" if DEVICE == 0 and "DA2" in label else "CPU"})', flush=True)
    plt.rcParams['font.family'] = 'Malgun Gothic'
    for n in names:
        img = Image.open(os.path.join(IN, n + '.jpg')).convert('RGB')
        fig, ax = plt.subplots(1, 1 + len(maps), figsize=(5 * (1 + len(maps)), 5 * img.height / img.width + 0.6))
        ax[0].imshow(img); ax[0].set_title('원본')
        for i, label in enumerate(maps):
            ax[i + 1].imshow(maps[label][n], cmap='inferno'); ax[i + 1].set_title(label)
        for a in ax: a.axis('off')
        plt.tight_layout(); plt.savefig(os.path.join(OUT, n + '.jpg'), dpi=80); plt.close()
    rows = ''.join(f'<h2>{n}</h2><img src="{n}.jpg">' for n in names)
    tm = ', '.join(f'{k} {v:.1f}초' for k, v in timing.items())
    open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(
        "<!doctype html><meta charset=utf-8><title>깊이 모델 비교</title><style>body{font-family:'Malgun Gothic';margin:24px;background:#f6f6f4}img{width:100%;max-width:1600px}</style>"
        f"<h1>깊이 모델 비교 (밝을수록 가까움)</h1><p>보는 법: 앞 사람·물체는 밝고, 건물·산은 중간, 하늘은 가장 어두워야 함. 물체 윤곽이 또렷하고, 같은 물체 안에서 얼룩이 없을수록 좋음.</p>"
        f"<p>라이선스: DA2-S, DA3 Mono-L은 Apache-2.0(상업 가능), DA2-L은 비상업(NC). 평균 시간(CPU 기준): {tm}</p>{rows}")
    print('보고서:', os.path.join(OUT, 'index.html'))


if __name__ == '__main__':
    main()
