# 들리는 그림 — AI 파이프라인 (명령 1개, 결정 D1·D4·Q6)
#   python pipeline.py 그림.jpg --key slug --title "제목" --artist "작가" [--year 1565]
#                      [--depth auto|da3|da2s] [--audio sa3m|sa3s|sao1] [--to-unity]
#   소리 다시 만들기: python pipeline.py --key slug --regen <소리원 id>|all [--to-unity]
# 단계 (단계마다 모델을 하나씩 올렸다가 내려 RTX 3060 12GB 안에서 돈다)
#   1 소리 설계: Qwen3.5-9B 4bit(NF4)가 소리원 4~6개의 이름·유형·설명·생성 프롬프트·위치(0~1000)를 정함 (D1, D2=직접 찍기)
#   2 깊이: DA2-Small(기본) 또는 DA3 Mono-Large(ONNX) → depth.bytes, 소리원마다 깊이
#   3 소리 생성: Stable Audio Open 1.0(기본) 또는 Stable Audio 3 small-sfx → 모노, 이음매 없는 반복, LUFS 음량 맞춤
#   4 묶기: out_<key>/ scene.json, depth.bytes, sounds/*.wav, figures/, report.html  (+ --to-unity면 Unity Resources로 복사)
# 출력 형식은 기존 앱이 읽는 scene.json과 같다. 새 필드(source_type, object_en, by)는 추가만 하므로 앱 수정 불필요.
import argparse, gc, html, json, os, re, shutil, sys, time
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import UNITY, UNITY_RES, FONT, REF_DIR, load_env   # 작업 폴더·저장소 구조 모두 지원
os.environ['HF_HUB_DISABLE_XET'] = '1'
load_env()   # .env(HF_TOKEN, GEMINI_API_KEY)는 없어도 됨

VLM_KEY = 'qwen35_9b_nf4'
TYPES = ['nature', 'people', 'animal', 'vehicle', 'music']
COLORS = {'nature': (89, 166, 255), 'people': (102, 230, 128), 'vehicle': (255, 153, 51), 'music': (190, 128, 255), 'animal': (255, 217, 77)}
AMBIENT_WORDS = ['wind', 'breeze', 'rain', 'drizzle', 'storm', 'thunder', 'ambient', 'ambience', 'room tone']
SEC, TARGET_LUFS, SEED = 12.0, -28.0, 1234     # -28 LUFS = 지금 앱 소리들의 중앙값
GRID_COLS = 160                                 # depth.bytes 가로 칸 수 (기존과 같음)


def free():
    import torch
    gc.collect(); torch.cuda.empty_cache()


def log(t0, msg):
    print(f'[{time.time() - t0:6.1f}s] {msg}', flush=True)


# ---------- 1. 소리 설계 (VLM) ----------
HAN = re.compile('[㐀-䶿一-鿿豈-﫿぀-ヿ]')   # 한자·가나 (11/25: 9B가 의성어에서 중국어로 샘)
RETRY_JSON = '\n\nYour previous answer was not valid JSON. Return ONLY one valid JSON object in the format above.'
RETRY_KOREAN = ('\n\nIMPORTANT: write label_ko and description_ko in Korean Hangul only. Never use Chinese characters or Japanese kana, '
                'even for sound words (use Korean onomatopoeia such as 바스락, 휘잉, 쏴아, 덜컹).')


def han_items(parsed):
    return [str(s.get('label_ko', '')) for s in (parsed or {}).get('sources') or []
            if HAN.search(str(s.get('label_ko', '')) + str(s.get('description_ko', '')))]


def design(img, title='', artist='', year=''):
    from bench_run import MODELS, POINT_V3, load, ask, parse, painting_context   # 프롬프트 v3 확정 (결정사항 6-1, 30장: 필수 75%, 지어냄 12.5%, 위치 90%)
    model, proc = load(MODELS[VLM_KEY], nf4=True)
    small = img.copy(); small.thumbnail((1024, 1024))
    # 9B는 같은 입력에 항상 같은 답(무작위성 없음) → 다시 시도할 때만 짧은 지시를 덧붙인다. 첫 시도는 v3 그대로(측정과 같은 조건)
    # 그림 정보 단락 (결정사항 6-1 v3+제목, 11/25): 제목이 있으면 v3 앞에 붙임, 없으면 v3 그대로
    base = painting_context(title, artist, year) + POINT_V3
    raw, parsed, prompt = '', None, base
    for attempt in range(3):
        raw, _ = ask(model, proc, small, prompt)
        cand = parse(raw)
        if not (cand and isinstance(cand.get('sources'), list)):
            prompt = base + RETRY_JSON
            continue
        if parsed is None or len(han_items(cand)) < len(han_items(parsed)):
            parsed = cand
        if not han_items(parsed):
            break
        print(f'    이름에 한자 섞임: {", ".join(han_items(parsed))} → 한글로 다시 요청', flush=True)
        prompt = base + RETRY_KOREAN
    del model, proc; free()
    if not parsed:
        raise RuntimeError('VLM 출력에서 JSON을 읽지 못함:\n' + raw[:500])
    sources, used = [], set()
    for s in parsed['sources'][:10]:   # 6개 자르기는 중복 정리 뒤에
        if not (isinstance(s.get('x'), (int, float)) and isinstance(s.get('y'), (int, float))):
            continue
        sid = ''.join(ch if ch.isalnum() or ch == '_' else '_' for ch in str(s.get('id') or 'src').lower())[:24] or 'src'
        while sid in used:
            sid += '_2'
        used.add(sid)
        text = (str(s.get('prompt_en', '')) + ' ' + str(s.get('object_en', ''))).lower()
        ambient = any(w in text for w in AMBIENT_WORDS)
        # 다시 요청해도 한자가 남으면 지워서 앱 화면에 한자가 뜨지 않게 (경고는 name_warnings로 남음)
        s['label_ko'] = re.sub(r'\s+', ' ', HAN.sub('', str(s.get('label_ko', '')))).strip() or sid
        s['description_ko'] = re.sub(r'\s+', ' ', HAN.sub('', str(s.get('description_ko', '')))).strip()
        sources.append(dict(id=sid, label=str(s.get('label_ko', sid)), type=s.get('type') if s.get('type') in TYPES else 'nature',
                            u=min(max(s['x'] / 1000, 0), 1), v=min(max(s['y'] / 1000, 0), 1),
                            volume=float(min(max(s.get('volume', 0.8) or 0.8, 0.3), 1.0)),
                            description=str(s.get('description_ko', '')), prompt=str(s.get('prompt_en', '')),
                            object_en=str(s.get('object_en', '')), source_type='ambient' if ambient else 'point', by=VLM_KEY))
    return sources, parsed.get('title_guess', ''), raw, han_items(parsed)


# ---------- 2. 깊이 ----------
AUTO_MIN_AGREE = 0.5   # DA3와 DA2-L의 깊이 순서 일치도(순위 상관)가 이 값 미만이면 DA2-L (풍경화에서 DA3가 하늘을 앞으로 내는 문제)


def norm01(d):
    lo, hi = np.percentile(d, 1), np.percentile(d, 99)
    return np.clip((d - lo) / (hi - lo + 1e-6), 0, 1)


def da2(img, size):
    from transformers import pipeline
    mid = {'s': 'depth-anything/Depth-Anything-V2-Small-hf', 'l': 'depth-anything/Depth-Anything-V2-Large-hf'}[size]
    pipe = pipeline('depth-estimation', model=mid, device=0)
    near = norm01(np.asarray(pipe(img)['depth'].resize(img.size), np.float32))
    del pipe; free()
    return near


def agreement(a, b):
    small = lambda m: np.asarray(Image.fromarray(m).resize((256, 256)), np.float32).ravel()
    ra, rb = np.argsort(np.argsort(small(a))), np.argsort(np.argsort(small(b)))
    return float(np.corrcoef(ra, rb)[0, 1])


def depth_map(img, which):
    # 반환: (가까움 0..1 지도, 쓴 모델 이름, 일치도 또는 None)
    if which == 'da2s':
        return da2(img, 's'), 'DA2-S', None
    if which == 'auto':
        a, b = da3(img), da2(img, 'l')
        agree = agreement(a, b)
        return (a, 'DA3 Mono-L', agree) if agree >= AUTO_MIN_AGREE else (b, 'DA2-L [NC]', agree)
    return da3(img), 'DA3 Mono-L', None


def da3(img):
    import onnxruntime as ort
    from huggingface_hub import hf_hub_download
    path = hf_hub_download('Jens-Duttke/Depth-Anything-3-MONO-ONNX', 'da-v3-mono-large_fp16_opset21_optimized.onnx')
    sess = ort.InferenceSession(path, providers=['CPUExecutionProvider'])
    S = 728
    mean, std = np.array([0.485, 0.456, 0.406], np.float32), np.array([0.229, 0.224, 0.225], np.float32)
    x = ((np.asarray(img.resize((S, S), Image.BICUBIC), np.float32) / 255.0 - mean) / std).transpose(2, 0, 1)[None].astype(np.float16)
    d = np.nan_to_num(sess.run(None, {sess.get_inputs()[0].name: x})[0].squeeze().astype(np.float32))
    d = np.asarray(Image.fromarray(d).resize(img.size, Image.BICUBIC), np.float32)
    return norm01(d)


def write_depth_bytes(near, path):
    H, W = near.shape
    rows = max(2, round(GRID_COLS * H / W))
    far_img = Image.fromarray(((1 - near) * 255).astype(np.uint8))
    far_img = far_img.filter(ImageFilter.GaussianBlur(W / GRID_COLS * 1.5)).resize((GRID_COLS, rows), Image.BILINEAR)
    with open(path, 'wb') as f:
        f.write(np.array([GRID_COLS, rows], dtype='<u2').tobytes())
        f.write(np.asarray(far_img, dtype=np.uint8).tobytes())


def assign_depth(sources, near):
    H, W = near.shape
    r = max(2, int(W * 0.015))
    for s in sources:
        x, y = min(int(s['u'] * W), W - 1), min(int(s['v'] * H), H - 1)
        patch = near[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1]
        s['far'] = 1.0 - float(np.median(patch))
    pts = [s for s in sources if s['source_type'] == 'point']
    if pts:
        lo, hi = min(s['far'] for s in pts), max(s['far'] for s in pts)
        for s in pts:      # 기존과 같은 규칙: 소리원끼리 0.1(가장 가까움)~0.9(가장 멂)로 펼침
            s['depth'] = 0.1 + 0.8 * (s['far'] - lo) / (hi - lo) if hi > lo else 0.5
    for s in sources:
        if s['source_type'] == 'ambient':
            s['depth'] = 1.0   # 장면 전체 소리는 그림 맨 뒤 (기존 바람·비와 같음)


# ---------- 3. 소리 생성 ----------
def make_loop(x, sr, fade_sec=1.0):
    n = int(sr * fade_sec)
    t = np.linspace(0, 1, n)
    y = x[n:].copy()
    y[-n:] = x[-n:] * np.sqrt(1 - t) + x[:n] * np.sqrt(t)
    return y


MAX_GAIN_DB = 20.0        # 음량 맞춤으로 키우는 상한 (11/26: 거의 무음 생성물을 +33dB 키우던 문제)
REGEN_TRIES = 2           # 상한을 넘으면 새 시드로 다시 만드는 횟수
DEFAULT_AUDIO = 'sa3m'    # 11/26 사용자 청취: hunters 6개 소리에서 medium 3번, Open 1.0 2번, small-sfx 1번 선택


def to_lufs(y, sr, max_gain_db=MAX_GAIN_DB):
    # -28 LUFS로 맞추되 키우는 폭은 max_gain_db까지. (소리, 원래 LUFS, 맞춘 뒤 LUFS, 상한에 걸렸는지)
    import pyloudnorm as pyln
    meter = pyln.Meter(sr)
    L = meter.integrated_loudness(y)
    capped = False
    if np.isfinite(L):
        gain = TARGET_LUFS - L
        if gain > max_gain_db:
            gain, capped = max_gain_db, True
        y = y * 10 ** (gain / 20)
    y = 0.95 * np.tanh(y / 0.95)               # 순간 최고점만 부드럽게 누름
    return y.astype(np.float32), L, meter.integrated_loudness(y), capped


def name_rain(sources):
    # Unity 비 효과는 id가 'rain'인 소리원에만 붙는다 (PaintingWorld.rainSourceId) → 장면 전체 비 소리 하나를 'rain'으로
    if any(s['id'] == 'rain' for s in sources):
        return
    for s in sources:
        text = (s['prompt'] + ' ' + s['object_en'] + ' ' + s['label']).lower()
        if s['source_type'] == 'ambient' and any(w in text for w in ('rain', 'drizzle', 'shower', '비')):
            s['id'] = 'rain'
            return


def make_generator(which):
    import torch
    if which == 'sao1':
        from diffusers import StableAudioPipeline
        pipe = StableAudioPipeline.from_pretrained('stabilityai/stable-audio-open-1.0', torch_dtype=torch.float16).to('cuda')
        sr = pipe.vae.sampling_rate
        gen = lambda p, seed: pipe(p, negative_prompt='low quality, distorted, music, speech', num_inference_steps=100, audio_end_in_s=SEC,
                                   num_waveforms_per_prompt=1, generator=torch.Generator('cuda').manual_seed(seed)).audios[0].float().cpu().numpy()
    else:   # sa3s = Stable Audio 3 small-sfx, sa3m = Stable Audio 3 medium (Flash Attention 없이도 동작 확인, 최대 VRAM 9.4GB)
        from stable_audio_3 import StableAudioModel
        pipe = StableAudioModel.from_pretrained({'sa3s': 'small-sfx', 'sa3m': 'medium'}[which])
        sr = pipe.model.sample_rate
        gen = lambda p, seed: pipe.generate(prompt=p, duration=SEC, steps=8, cfg_scale=1, seed=seed, batch_size=1)[0].float().cpu().numpy()
    return pipe, sr, gen


def render_sound(s, gen, sr, out, seed):
    # 생성 → 모노 → 이음매 없는 반복 → 음량 맞춤. 키워야 하는 폭이 상한을 넘으면 새 시드로 다시 (가장 덜 키워도 되는 결과를 씀)
    import soundfile as sf
    best = None
    for k in range(REGEN_TRIES + 1):
        a = gen(s['prompt'], seed + 100 * k)
        mono = a.mean(axis=0) if a.ndim == 2 else a
        y, before, after, capped = to_lufs(make_loop(mono[:int(SEC * sr)], sr), sr)
        if best is None or (np.isfinite(before) and before > best[1]):
            best = (y, before, after, capped, seed + 100 * k)
        if not capped:
            break
        print(f"    {s['id']:16s} 원래 {before:6.1f} LUFS: +{TARGET_LUFS - before:.0f}dB 필요 (상한 +{MAX_GAIN_DB:.0f}dB) → 새 시드로 다시", flush=True)
    y, before, after, capped, used = best
    s['file'] = s['id']
    s['seed'] = used
    s['lufs'] = round(after, 1)
    s['quiet'] = bool(capped)        # 상한에 걸려 목표보다 작게 남음
    sf.write(os.path.join(out, 'sounds', s['file'] + '.wav'), y, sr)
    print(f"    {s['id']:16s} {before:6.1f} → {after:6.1f} LUFS (seed {used})" + (' — 상한에 걸려 목표보다 작음' if capped else ''), flush=True)


def sounds(sources, which, out):
    os.makedirs(os.path.join(out, 'sounds'), exist_ok=True)
    pipe, sr, gen = make_generator(which)
    for n, s in enumerate(sources, 1):
        print(f'@@SUB {n}/{len(sources)} {s["label"]}', flush=True)
        render_sound(s, gen, sr, out, SEED)
    del pipe; free()


# ---------- 4. 묶기 ----------
def figures(img, near, sources, out):
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig_dir = os.path.join(out, 'figures'); os.makedirs(fig_dir, exist_ok=True)
    img.save(os.path.join(fig_dir, '0_original.jpg'), quality=92)
    plt.imsave(os.path.join(fig_dir, '2_depth.png'), near, cmap='inferno')
    vis = img.copy(); W, H = vis.size
    d = ImageDraw.Draw(vis); f = ImageFont.truetype(FONT, max(16, W // 55))
    for n, s in enumerate(sources, 1):
        c = COLORS.get(s['type'], (255, 255, 255)); x, y = s['u'] * W, s['v'] * H; r = max(10, W // 80)
        d.ellipse([x - r, y - r, x + r, y + r], fill=c, outline=(0, 0, 0), width=3)
        d.text((x + r + 4, y), f"{n} {s['label']} (깊이 {s['depth']:.2f}{', 전체' if s['source_type'] == 'ambient' else ''})",
               fill=c, font=f, anchor='lm', stroke_width=3, stroke_fill=(0, 0, 0))
    vis.save(os.path.join(fig_dir, '1_sources.jpg'), quality=90)


SCENE_KEYS = ['id', 'label', 'type', 'u', 'v', 'depth', 'file', 'volume', 'description', 'prompt', 'source_type', 'object_en', 'by', 'seed', 'lufs', 'quiet']


def report(scene, out, timing):
    rows = ''.join(f"<tr><td>{n}</td><td><b>{html.escape(s['label'])}</b><br><span class=m>{s['id']} · {s['type']}, {s['source_type']}</span></td>"
                   f"<td>u {s['u']:.2f}, v {s['v']:.2f}<br>깊이 {s['depth']:.2f}</td><td>{html.escape(s['description'])}<br><span class=m>{html.escape(s['prompt'])}</span></td>"
                   f"<td><audio controls preload=none src='sounds/{s['file']}.wav?seed={s.get('seed', '')}'></audio><br><span class=m>{s.get('lufs', '')} LUFS, volume {s['volume']}, seed {s.get('seed', '')}{' · <b style=color:#c00>상한에 걸려 작음</b>' if s.get('quiet') else ''}</span></td></tr>"
                   for n, s in enumerate(scene['sources'], 1))
    tm = ', '.join(f'{k} {v:.0f}초' for k, v in timing.items())
    open(os.path.join(out, 'report.html'), 'w', encoding='utf-8').write(
        "<!doctype html><meta charset=utf-8><title>소리 묶음 확인</title><style>body{font-family:'Malgun Gothic';margin:24px;background:#f6f6f4}"
        "img{max-width:49%;border-radius:6px}table{border-collapse:collapse;margin-top:12px}td,th{border:1px solid #ccc;padding:6px;vertical-align:top}.m{color:#666;font-size:12px}</style>"
        f"<h1>{html.escape(scene['title'])} — {html.escape(scene['artist'])}</h1>"
        f"<p class=m>깊이 {scene['depth_model']}" + (f" (일치도 {scene['depth_agreement']})" if scene.get('depth_agreement') is not None else '')
        + f", 소리 {scene.get('audio_model', '')}, VLM {VLM_KEY}. 시간: {tm}</p>"
        + ''.join(f"<p><b>품질 ({k} 답지 기준, ±5%p)</b>: 필수 {r['required']}, 지어냄 {r['invented_n']}"
                  + (' <b style=color:#c00>확인 필요</b>' if r['required_found'] < 0.7 or r['invented'] > 0.15 else '')
                  + (f" · 놓침: {html.escape(', '.join(r['missed']))}" if r['missed'] else '')
                  + (f" · 지어냄: {html.escape(', '.join(r['invented_items']))}" if r['invented_items'] else '') + '</p>'
                  for k, r in (scene.get('quality') or {}).items())
        + (f"<p class=m>중복으로 뺀 소리원: {html.escape(', '.join(scene['dropped']))}</p>" if scene.get('dropped') else '')
        + (f"<p><b style=color:#c00>이름 확인 필요 (한자 섞임)</b>: {html.escape(', '.join(scene['name_warnings']))}</p>" if scene.get('name_warnings') else '')
        + (f"<p><b>ARCore 인식 점수</b>: {scene['arcore_score']} (권장 {ARCORE_MIN} 이상)"
           + (' <b style=color:#c00>낮음: 앱에서 인식이 불안정할 수 있음</b>' if 0 <= scene['arcore_score'] < ARCORE_MIN else '') + '</p>'
           if scene.get('arcore_score', -1) >= 0 else '')
        + "<img src='figures/1_sources.jpg'> <img src='figures/2_depth.png'>"
        f"<table><tr><th>#</th><th>소리원</th><th>위치</th><th>설명 / 프롬프트</th><th>소리</th></tr>{rows}</table>")


ARCORE_MIN = 75   # ARCore 권장 인식 점수


def arcoreimg_path():
    # Unity ARCore 패키지에 들어 있는 arcoreimg.exe (환경 변수 ARCOREIMG로 바꿀 수 있음)
    import glob
    cands = [os.environ.get('ARCOREIMG', '')]
    cands += glob.glob(os.path.join(UNITY, 'Library', 'PackageCache', 'com.unity.xr.arcore@*', 'Tools~', 'Windows', 'arcoreimg.exe'))
    cands += [os.path.join(os.path.expanduser('~'), 'Downloads', 'arcoreimg.exe')]
    return next((c for c in cands if c and os.path.exists(c)), None)


def arcore_score(path, tool):
    import subprocess
    try:
        r = subprocess.run([tool, 'eval-img', f'--input_image_path={os.path.abspath(path)}'], capture_output=True, text=True, timeout=60)
        last = (r.stdout.strip().splitlines() or [''])[-1].strip()
        return int(last) if last.isdigit() else None
    except Exception:
        return None


def make_reference(src_path, img, out):
    # ARCore 참조 이미지 고르기 (11/25 실험: 같은 그림도 저장 방식에 따라 점수가 60~85로 흔들림 →
    # 후보 몇 개를 재서 가장 높은 것을 씀. Unity는 빌드할 때 이 jpg 파일을 그대로 써서 ARCore 데이터베이스를 만든다)
    cdir = os.path.join(out, 'reference_candidates'); os.makedirs(cdir, exist_ok=True)
    cands = []
    try:
        src = Image.open(src_path)
        if src.format == 'JPEG' and not src.info.get('progressive') and not src.info.get('progression') and max(src.size) <= 2048:
            shutil.copy(src_path, os.path.join(cdir, 'original.jpg')); cands.append('original.jpg')
    except Exception:
        pass
    img.save(os.path.join(cdir, 'q95.jpg'), 'JPEG', quality=95, progressive=False); cands.append('q95.jpg')
    img.save(os.path.join(cdir, 'q100.jpg'), 'JPEG', quality=100, subsampling=0, progressive=False); cands.append('q100.jpg')
    tool = arcoreimg_path()
    scores = {c: (arcore_score(os.path.join(cdir, c), tool) if tool else None) for c in cands}
    best = max(cands, key=lambda c: (scores[c] if scores[c] is not None else -1, -cands.index(c)))
    shutil.copy(os.path.join(cdir, best), os.path.join(out, 'reference.jpg'))
    return dict(score=scores[best], picked=best, candidates=scores, tool=bool(tool))


def copy_layers(out, dst):
    # 그림 꺼내기 층 PNG + 층 지도 (없으면 앱은 예전 방식으로 층을 만듦)
    src = os.path.join(out, 'layers')
    if not os.path.exists(os.path.join(src, 'layers.bytes')):
        return
    os.makedirs(os.path.join(dst, 'layers'), exist_ok=True)
    for f in os.listdir(src):
        if f.startswith('layer') and (f.endswith('.png') or f.endswith('.bytes')):
            shutil.copy(os.path.join(src, f), os.path.join(dst, 'layers', f))


def to_unity(key, out, scene, only=None):
    dst = os.path.join(UNITY_RES, key)
    os.makedirs(os.path.join(dst, 'sounds'), exist_ok=True)
    for f in ('scene.json', 'depth.bytes'):
        shutil.copy(os.path.join(out, f), os.path.join(dst, f))
    for s in scene['sources']:
        if only is None or s['id'] == only:
            shutil.copy(os.path.join(out, 'sounds', s['file'] + '.wav'), os.path.join(dst, 'sounds', s['file'] + '.wav'))
    if only is None:
        copy_layers(out, dst)
    if only is None and os.path.exists(os.path.join(out, 'reference.jpg')):
        os.makedirs(REF_DIR, exist_ok=True)
        shutil.copy(os.path.join(out, 'reference.jpg'), os.path.join(REF_DIR, key + '.jpg'))
    return os.path.abspath(dst)


def regen(args):
    # 소리 다시 만들기
    #   --key p001 --regen <소리원 id>      : 그 소리 하나만, 새 시드
    #   --key p001 --regen all [--audio sa3s] : 그 그림의 소리 전부 (모델을 바꿀 때). 모델이 같으면 새 시드, 바뀌면 원래 시드
    #   --key all  --regen all --audio sa3s   : 만든 그림 전부 (ptest로 시작하는 시험 폴더는 뺌)
    if args.key == 'all':
        # 이 파이프라인이 만든 폴더만 (scene.json에 audio_model이 있음). 예전 generate.py 결과(out_hunters 등)와 시험 폴더(ptest)는 뺌
        keys = sorted(d[4:] for d in os.listdir(HERE) if d.startswith('out_') and not d.startswith('out_ptest')
                      and os.path.exists(os.path.join(HERE, d, 'scene.json'))
                      and 'audio_model' in json.load(open(os.path.join(HERE, d, 'scene.json'), encoding='utf-8')))
        if not keys:
            raise RuntimeError('다시 만들 그림이 없음 (파이프라인으로 만든 out_ 폴더가 없음)')
    else:
        keys = [args.key]
    jobs = []
    for key in keys:
        out = os.path.join(HERE, 'out_' + key)
        scene = json.load(open(os.path.join(out, 'scene.json'), encoding='utf-8'))
        if args.regen == 'all':
            targets = scene['sources']
        else:
            targets = [x for x in scene['sources'] if x['id'] == args.regen]
            if not targets:
                raise RuntimeError(f"[{key}] 소리원 '{args.regen}' 없음: " + ', '.join(x['id'] for x in scene['sources']))
        jobs.append((key, out, scene, targets))
    which = args.audio or jobs[0][2].get('audio_model', 'sao1')
    total = sum(len(t) for _, _, _, t in jobs)
    print(f'@@STEP 1/1 소리 다시 만들기: 그림 {len(jobs)}장, 소리 {total}개 ({which})', flush=True)
    pipe, sr, gen = make_generator(which)      # 모델은 한 번만 올림
    n = 0
    for key, out, scene, targets in jobs:
        same_model = scene.get('audio_model', 'sao1') == which
        for s in targets:
            n += 1
            print(f'@@SUB {n}/{total} {key} {s["label"]}', flush=True)
            seed = int(s.get('seed') or SEED) + (1 if same_model else 0)
            render_sound(s, gen, sr, out, seed)
        scene['audio_model'] = which
        json.dump(scene, open(os.path.join(out, 'scene.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        report(scene, out, {})
        if args.to_unity:
            to_unity(key, out, scene, only=None if args.regen == 'all' else targets[0]['id'])
    del pipe; free()
    print(f"@@DONE {os.path.join(jobs[-1][1], 'report.html')}", flush=True)


def load_keys(img, out):
    # 답지: Gemini(자동) + Claude(이 대화에서 직접 만든 경우 out_<key>/answers_claude.json). 실패하면 빈 목록 (N4)
    keys = {}
    try:
        import gemini_tools
        g = gemini_tools.answer_key(img)
        if g:
            json.dump(g, open(os.path.join(out, 'answers_gemini.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            keys['gemini'] = g['sources']
    except Exception as e:
        print(f'    Gemini 답지 실패: {type(e).__name__}: {e}', flush=True)
    cpath = os.path.join(out, 'answers_claude.json')
    if os.path.exists(cpath):
        c = json.load(open(cpath, encoding='utf-8'))
        keys['claude'] = c.get('sources', c) if isinstance(c, dict) else c
    return keys


def dedupe(sources, keys, limit=6):
    # 같은 이름의 소리원은 하나만: 답지가 있으면 답지 점에 가장 가까운 것, 없으면 가장 앞(가까운) 것 (N1, 결정 6-1). 그 뒤 최대 6개
    pts = [p for ks in keys.values() for a in ks for p in (a.get('points') or [])]

    def rank(s):
        if pts:
            return min(((s['u'] * 1000 - p[0]) ** 2 + (s['v'] * 1000 - p[1]) ** 2) ** 0.5 for p in pts)
        return s.get('far', 0.5)
    groups = {}
    for s in sources:
        groups.setdefault(''.join(s['label'].split()), []).append(s)
    keep = {id(min(g, key=rank)) for g in groups.values()}
    dropped = [s['label'] for s in sources if id(s) not in keep]
    kept = [s for s in sources if id(s) in keep][:limit]
    return kept, dropped


def quality(img, keys, sources):
    if not keys:
        return {}
    import gemini_tools
    pred = [dict(label_ko=s['label'], sound_en=s['prompt'], ground_phrase_en=s['object_en']) for s in sources]
    q = {}
    for name, ans in keys.items():
        try:
            r = gemini_tools.score(img, ans, pred)
            if r:
                q[name] = r
        except Exception as e:
            print(f'    품질 채점 실패({name}): {type(e).__name__}', flush=True)
    return q


def build(args):
    out = os.path.join(HERE, 'out_' + args.key); os.makedirs(out, exist_ok=True)
    t0 = time.time(); timing = {}
    img = Image.open(args.image).convert('RGB'); img.thumbnail((1600, 1600))
    arcore = make_reference(args.image, img, out)
    print(f"    ARCore 인식 점수 {arcore['score']} ({arcore['picked']}, 후보 {arcore['candidates']})"
          + ('' if arcore['score'] is None or arcore['score'] >= ARCORE_MIN else f' — 권장 {ARCORE_MIN}점 미만: 앱에서 인식이 불안정할 수 있음'), flush=True)

    t = time.time(); print('@@STEP 1/5 소리 설계 (Qwen3.5-9B 4bit)', flush=True)
    from bench_run import painting_context
    print('    그림 정보: ' + (painting_context(args.title, args.artist, args.year).splitlines() or ['없음 (v3 그대로)'])[0], flush=True)
    sources, title_guess, raw, name_warnings = design(img, args.title, args.artist, args.year)
    open(os.path.join(out, 'vlm_raw.txt'), 'w', encoding='utf-8').write(raw)
    if not sources:
        raise RuntimeError('소리원이 없는 조용한 그림 (VLM이 들릴 만한 소리를 찾지 못함) — 앱에 넣지 않음')
    timing['소리 설계'] = time.time() - t
    for s in sources:
        log(t0, f"    {s['id']:16s} {s['label']} ({s['type']}, {s['source_type']}) u={s['u']:.2f} v={s['v']:.2f}")

    t = time.time(); print('@@STEP 2/5 답지 확인 (Gemini)', flush=True)
    keys = load_keys(img, out)
    log(t0, '    답지: ' + (', '.join(f'{k} {len(v)}개' for k, v in keys.items()) or '없음 (오프라인 또는 실패 → 답지 없이 계속)'))
    timing['답지'] = time.time() - t

    t = time.time(); print(f'@@STEP 3/5 깊이 ({args.depth}) · 층 채우기 · 중복 정리', flush=True)
    near, depth_model, agree = depth_map(img, args.depth)
    log(t0, f'    → {depth_model}' + (f' (DA3·DA2-L 일치도 {agree:.2f}, 기준 {AUTO_MIN_AGREE})' if agree is not None else ''))
    write_depth_bytes(near, os.path.join(out, 'depth.bytes'))
    from layers import load_lama, build_layers, preview
    print('@@SUB 1/1 그림 꺼내기 층 채우기 (LaMa)', flush=True)
    lama = load_lama()
    layer_info = build_layers(lama, img, near, os.path.join(out, 'layers'), log=lambda m: log(t0, m))
    del lama; free()
    preview(os.path.join(out, 'layers'))
    assign_depth(sources, near)
    sources, dropped = dedupe(sources, keys)
    if dropped:
        log(t0, '    중복 정리: ' + ', '.join(dropped) + ' 뺌')
    assign_depth(sources, near)          # 남은 소리원끼리 깊이 0.1~0.9 다시 펼침
    name_rain(sources)
    timing['깊이'] = time.time() - t

    t = time.time(); print('@@STEP 4/5 품질 채점 (Gemini)', flush=True)
    q = quality(img, keys, sources)
    for name, r in q.items():
        log(t0, f"    {name} 답지 기준: 필수 {r['required']}, 지어냄 {r['invented_n']}" + (f" · 놓침 {', '.join(r['missed'])}" if r['missed'] else ''))
    timing['품질'] = time.time() - t

    t = time.time(); print(f'@@STEP 5/5 소리 생성 ({args.audio}) · 묶기', flush=True)
    sounds(sources, args.audio, out)
    timing['소리 생성'] = time.time() - t
    figures(img, near, sources, out)
    scene = dict(title=args.title, artist=args.artist, year=args.year, caption=f'VLM 제목 추정: {title_guess}',
                 depth_model=depth_model, depth_agreement=None if agree is None else round(agree, 3), audio_model=args.audio,
                 quality=q, dropped=dropped, name_warnings=[f"{HAN.sub('', n).strip() or n} (원래 '{n}')" for n in name_warnings], arcore_score=arcore['score'] if arcore['score'] is not None else -1, arcore=arcore, layers=layer_info,
                 sources=[{k: (round(s[k], 3) if isinstance(s[k], float) else s[k]) for k in SCENE_KEYS if k in s} for s in sources])
    json.dump(scene, open(os.path.join(out, 'scene.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    timing['전체'] = time.time() - t0
    report(scene, out, timing)
    if args.to_unity:
        log(t0, 'Unity로 복사: ' + to_unity(args.key, out, scene))
    log(t0, f"완료 ({', '.join(f'{k} {v:.0f}초' for k, v in timing.items())})")
    print(f"@@DONE {os.path.join(out, 'report.html')}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('image', nargs='?'); ap.add_argument('--key', required=True)
    ap.add_argument('--title', default=''); ap.add_argument('--artist', default=''); ap.add_argument('--year', default='')
    ap.add_argument('--depth', choices=['auto', 'da2s', 'da3'], default='auto')
    ap.add_argument('--audio', choices=['sao1', 'sa3s', 'sa3m'], default=None)
    ap.add_argument('--regen', metavar='SOURCE_ID', help='이 소리원 하나만 새 시드로 다시 만들기')
    ap.add_argument('--to-unity', action='store_true')
    args = ap.parse_args()
    try:
        if args.regen:
            regen(args)
        else:
            if not args.image or not args.title:
                ap.error('그림 경로와 --title이 필요함')
            args.audio = args.audio or DEFAULT_AUDIO
            build(args)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f'@@ERROR {type(e).__name__}: {e}', flush=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
