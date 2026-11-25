# 들리는 그림 — AI 생성 (로컬 PC 버전, Colab 노트북 v2와 같은 과정)
# 사용:
#   python generate.py vision hunters ..\paintings\hunters.jpg   ← ① VLM + ② 깊이 → 소리원 배치, 확인 그림
#   python generate.py audio  hunters                            ← ③ 소리 생성 (HF 로그인 필요)
#   python generate.py pack   hunters [id=후보번호 ...]           ← 후보 고르기 + scene.json + Unity로 복사
import json, os, sys, shutil, gc
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
NOTEBOOK = os.path.join(HERE, '..', 'colab', 'HearingPainting_AI_v2.ipynb')
UNITY_RES = os.path.join(HERE, '..', '..', 'AR_Midterm', 'Assets', 'Resources', 'HearingPainting')

# 같은 폴더의 .env에서 HF_TOKEN을 읽어 환경 변수로 넘긴다 (huggingface_hub가 자동으로 사용)
def load_env():
    path = os.path.join(HERE, '.env')
    if not os.path.exists(path):
        return
    for line in open(path, encoding='utf-8-sig'):
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            v = v.strip().strip('"').strip("'")
            if v:
                os.environ[k.strip()] = v


load_env()

COLORS = {'nature': (80, 160, 255), 'people': (90, 220, 120), 'vehicle': (255, 150, 50),
          'music': (190, 120, 255), 'animal': (255, 215, 75)}


def load_preset(key):
    # 노트북 3번 셀의 PRESETS를 그대로 읽는다 (설정을 한 곳에서만 관리)
    nb = json.load(open(NOTEBOOK, encoding='utf-8'))
    cell = next(''.join(c['source']) for c in nb['cells'] if 'PRESETS = {' in ''.join(c['source']))
    g = {}
    exec(cell.split('from google.colab')[0], g)
    return g['PRESETS'][key]


def out_dir(key):
    d = os.path.join(HERE, 'out_' + key)
    for sub in ['sounds', 'figures', 'candidates']:
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    return d


def vision(key, image_path):
    import torch
    from transformers import AutoProcessor, Florence2ForConditionalGeneration, pipeline
    P = load_preset(key)
    out = out_dir(key)

    img = Image.open(image_path).convert('RGB')
    img.thumbnail((1600, 1600))
    W, H = img.size
    img.save(os.path.join(out, 'figures', '0_original.jpg'), quality=92)

    # ① VLM: Florence-2
    fl_id = 'florence-community/Florence-2-large'
    model = Florence2ForConditionalGeneration.from_pretrained(fl_id, dtype=torch.float16).to('cuda')
    proc = AutoProcessor.from_pretrained(fl_id)

    def florence(task, text=''):
        inputs = proc(text=task + text, images=img, return_tensors='pt').to('cuda', torch.float16)
        ids = model.generate(**inputs, max_new_tokens=1024, num_beams=3)
        raw = proc.batch_decode(ids, skip_special_tokens=False)[0]
        return proc.post_process_generation(raw, task=task, image_size=img.size)[task]

    def boxes_of(result):
        labels = result.get('labels') or result.get('bboxes_labels') or []
        return list(zip(labels, result.get('bboxes', [])))

    caption = florence('<MORE_DETAILED_CAPTION>')
    print('[그림 설명]', caption)
    detections = boxes_of(florence('<OD>'))
    for phrase in P['phrases']:
        detections += boxes_of(florence('<OPEN_VOCABULARY_DETECTION>', phrase))
    for label, box in detections:
        print(f'  {label:25s}', [round(b) for b in box])
    del model
    gc.collect()
    torch.cuda.empty_cache()

    # ② 깊이: Depth Anything V2 Small
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    depth_pipe = pipeline('depth-estimation', model='depth-anything/Depth-Anything-V2-Small-hf', device=0)
    depth_img = depth_pipe(img)['depth']
    if depth_img.size != img.size:
        depth_img = depth_img.resize(img.size)
    near = np.asarray(depth_img, dtype=np.float32) / 255.0
    plt.imsave(os.path.join(out, 'figures', '2_depth.png'), near, cmap='inferno')

    cols = 160
    rows = max(2, round(cols * H / W))
    far_img = Image.fromarray(((1 - near) * 255).astype(np.uint8))
    far_img = far_img.filter(ImageFilter.GaussianBlur(W / cols * 1.5)).resize((cols, rows), Image.BILINEAR)
    with open(os.path.join(out, 'depth.bytes'), 'wb') as f:
        f.write(np.array([cols, rows], dtype='<u2').tobytes())
        f.write(np.asarray(far_img, dtype=np.uint8).tobytes())

    def box_far(box):
        x0, y0, x1, y1 = [int(round(b)) for b in box]
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
        patch = near[y0:y1, x0:x1]
        return 1.0 - float(np.median(patch)) if patch.size else 0.5

    def far_at(u, v):
        x, y = min(int(u * W), W - 1), min(int(v * H), H - 1)
        return 1.0 - float(near[y, x])

    # 소리원 고르기 (노트북 6번 셀과 같은 규칙)
    sound_map = [o[:6] for o in P['objects']]
    people_keys = ['umbrella', 'person', 'man', 'woman', 'people', 'hunter']

    def make(c, sid, name, typ, desc, prompt, volume=1.0):
        x0, y0, x1, y1 = c['box']
        return dict(id=sid, label=name, type=typ, u=(x0 + x1) / 2 / W, v=(y0 + y1) / 2 / H,
                    far=c['far'], volume=volume, description=desc, prompt=prompt, box=c['box'], by='AI')

    cands = []
    for label, box in detections:
        area = (box[2] - box[0]) * (box[3] - box[1]) / (W * H)
        if area < 0.002 or area > 0.5:
            continue
        low = label.lower()
        sid = next((e[1] for e in sound_map if any(k in low for k in e[0])), None)
        if sid is None and any(k in low for k in people_keys):
            sid = 'people'
        if sid:
            cands.append(dict(sid=sid, label=label, box=box, area=area, far=box_far(box)))

    sources = []
    for keys, sid, name, typ, desc, prompt in sound_map:
        group = [c for c in cands if c['sid'] == sid]
        if group:
            sources.append(make(max(group, key=lambda c: c['area']), sid, name, typ, desc, prompt))
    people = [c for c in cands if c['sid'] == 'people']
    if people and P['people_near']:
        nearest = min(people, key=lambda c: c['far'])
        farthest = max(people, key=lambda c: c['far'])
        sources.append(make(nearest, *P['people_near'][:5]))
        if P['people_far'] and farthest['far'] - nearest['far'] > 0.15:
            sources.append(make(farthest, *P['people_far'][:5], volume=0.7))

    # AI가 못 찾은 소리원은 대략값으로 채움 (노트북의 ADD_MISSING = True와 같음)
    have = {s['id'] for s in sources}
    manual = list(P['objects']) + [p for p in (P['people_near'], P['people_far']) if p]
    for o in manual:
        sid, name, typ, desc, prompt, u, v, _ = o[-8:]
        if sid not in have:
            sources.append(dict(id=sid, label=name, type=typ, u=u, v=v, far=far_at(u, v), volume=1.0,
                                description=desc, prompt=prompt, by='대략값'))

    fs = [s['far'] for s in sources]
    lo, hi = min(fs), max(fs)
    for s in sources:
        s['depth'] = 0.1 + 0.8 * (s['far'] - lo) / (hi - lo) if hi > lo else 0.5
    for a in P['ambient']:
        sources.append(dict(a, by='고정'))

    # 확인 그림
    vis = img.copy()
    draw = ImageDraw.Draw(vis)
    for label, box in detections:
        draw.rectangle(box, outline=(160, 160, 160), width=2)
    for s in sources:
        c = COLORS.get(s['type'], (255, 255, 255))
        if 'box' in s:
            draw.rectangle(s['box'], outline=c, width=6)
        cx, cy = s['u'] * W, s['v'] * H
        draw.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=c, outline=(0, 0, 0), width=3)
        draw.text((cx + 18, cy - 8), f"{s['id']} d={s['depth']:.2f} ({s['by']})", fill=c)
    vis.save(os.path.join(out, 'figures', '1_detect.jpg'), quality=92)

    for s in sources:
        print(f"{s['id']:12s} u={s['u']:.2f} v={s['v']:.2f} depth={s['depth']:.2f}  {s['label']} ({s['by']})")
    draft = dict(title=P['title'], artist=P['artist'], year=P['year'], caption=caption,
                 sources=[{k: v for k, v in s.items() if k not in ('box', 'far')} for s in sources])
    json.dump(draft, open(os.path.join(out, 'sources_draft.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('저장:', out)


def make_loop(x, sr, fade_sec=1.0):
    n = int(sr * fade_sec)
    t = np.linspace(0, 1, n)
    y = x[n:].copy()
    y[-n:] = x[-n:] * np.sqrt(1 - t) + x[:n] * np.sqrt(t)
    return y / (np.max(np.abs(y)) + 1e-9) * 0.9


def audio(key, only=None):
    import torch
    import soundfile as sf
    from diffusers import StableAudioPipeline
    out = out_dir(key)
    draft = json.load(open(os.path.join(out, 'sources_draft.json'), encoding='utf-8'))
    sa = StableAudioPipeline.from_pretrained('stabilityai/stable-audio-open-1.0', torch_dtype=torch.float16).to('cuda')
    sr = sa.vae.sampling_rate
    for s in draft['sources']:
        if only and s['id'] not in only:
            continue
        g = torch.Generator('cuda').manual_seed(0)
        audios = sa(s['prompt'], negative_prompt='low quality, distorted, music, speech',
                    num_inference_steps=100, audio_end_in_s=12.0,
                    num_waveforms_per_prompt=2, generator=g).audios
        for k in range(audios.shape[0]):
            mono = audios[k].T.float().cpu().numpy().mean(axis=1)
            sf.write(os.path.join(out, 'candidates', f"{s['id']}_{k}.wav"), make_loop(mono, sr), sr)
        print(s['id'], '후보 2개 완료', flush=True)


def pack(key, choices):
    import soundfile as sf
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out = out_dir(key)
    draft = json.load(open(os.path.join(out, 'sources_draft.json'), encoding='utf-8'))
    srcs = draft['sources']
    target_db = -28.0   # 중간 과제 그림 소리들의 크기(-28~-34dB)에 맞춤
    for s in srcs:
        s['file'] = s['id']
        k = choices.get(s['id'], 0)
        y, sr = sf.read(os.path.join(out, 'candidates', f"{s['id']}_{k}.wav"))
        # 소리마다 크기가 크게 달라서(-14~-39dB) 평균 크기를 맞춘다. 커진 순간 최고점은 tanh로 부드럽게 누름
        rms = np.sqrt(np.mean(y ** 2)) + 1e-9
        y = y * (10 ** (target_db / 20) / rms)
        y = 0.95 * np.tanh(y / 0.95)
        sf.write(os.path.join(out, 'sounds', s['file'] + '.wav'), y.astype(np.float32), sr)
        print(f"{s['id']:10s} 후보 {k}  {20 * np.log10(rms):6.1f}dB → {20 * np.log10(np.sqrt(np.mean(y ** 2)) + 1e-9):6.1f}dB")

    fig, axes = plt.subplots(len(srcs), 1, figsize=(10, 1.6 * len(srcs)), sharex=True)
    for ax, s in zip(np.atleast_1d(axes), srcs):
        y, sr = sf.read(os.path.join(out, 'sounds', s['file'] + '.wav'))
        ax.plot(np.arange(len(y)) / sr, y, linewidth=0.4, color=np.array(COLORS.get(s['type'], (128, 128, 128))) / 255)
        ax.set_ylabel(s['id'], rotation=0, ha='right')
        ax.set_yticks([])
    np.atleast_1d(axes)[-1].set_xlabel('seconds')
    plt.tight_layout()
    plt.savefig(os.path.join(out, 'figures', '3_waveforms.png'), dpi=150)

    keys = ['id', 'label', 'type', 'u', 'v', 'depth', 'file', 'volume', 'description', 'prompt']
    scene = dict(title=draft['title'], artist=draft['artist'], year=draft['year'], caption=draft['caption'],
                 sources=[{k: (round(s[k], 3) if isinstance(s[k], float) else s[k]) for k in keys} for s in srcs])
    json.dump(scene, open(os.path.join(out, 'scene.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    # Unity Resources로 복사
    dst = os.path.join(UNITY_RES, key)
    os.makedirs(os.path.join(dst, 'sounds'), exist_ok=True)
    shutil.copy(os.path.join(out, 'scene.json'), os.path.join(dst, 'scene.json'))
    shutil.copy(os.path.join(out, 'depth.bytes'), os.path.join(dst, 'depth.bytes'))
    for s in srcs:
        shutil.copy(os.path.join(out, 'sounds', s['file'] + '.wav'), os.path.join(dst, 'sounds', s['file'] + '.wav'))
    print('Unity로 복사:', os.path.abspath(dst))


if __name__ == '__main__':
    if sys.argv[1] == 'check':
        # 토큰 값은 출력하지 않고, Stable Audio Open에 접근 가능한지만 확인
        from huggingface_hub import auth_check
        if not os.environ.get('HF_TOKEN'):
            print('HF_TOKEN 없음: .env에 HF_TOKEN=토큰 을 적고 저장했는지 확인')
            sys.exit(1)
        auth_check('stabilityai/stable-audio-open-1.0')
        print('토큰 확인 완료: stable-audio-open-1.0 접근 가능')
        sys.exit(0)
    stage, key = sys.argv[1], sys.argv[2]
    if stage == 'vision':
        vision(key, sys.argv[3])
    elif stage == 'audio':
        audio(key, set(sys.argv[3:]) or None)
    elif stage == 'pack':
        pack(key, {a.split('=')[0]: int(a.split('=')[1]) for a in sys.argv[3:]})
