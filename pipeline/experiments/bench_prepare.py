# VLM 비교용 공통 입력 만들기: 그림마다 Florence-2 탐지 + Depth Anything 깊이를 한 번만 계산해 저장
# 모든 모델이 같은 탐지 목록을 받도록 하고, 탐지 문구는 그림별 맞춤 없이 일반 문구만 쓴다
import json, os, gc
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
IMAGES = {
    'hunters': os.path.join(ROOT, '03_제작', 'paintings', 'hunters.jpg'),
    'rainy_day': os.path.join(ROOT, 'AR_Midterm', 'Assets', 'HearingPainting', 'ReferenceImages', 'rainy_day.jpg'),
    'wave': os.path.join(ROOT, '03_제작', 'paintings', 'wave.jpg'),
    'beach': os.path.join(ROOT, '03_제작', 'paintings', 'beach.jpg'),
    'boulevard': os.path.join(ROOT, '03_제작', 'paintings', 'boulevard.jpg'),
}
GENERIC_PHRASES = ['animal', 'vehicle', 'boat', 'bird', 'fire', 'water', 'tree']
OUT = os.path.join(HERE, 'bench', 'inputs')
os.makedirs(OUT, exist_ok=True)

import torch
from transformers import AutoProcessor, Florence2ForConditionalGeneration, pipeline

fl_id = 'florence-community/Florence-2-large'
model = Florence2ForConditionalGeneration.from_pretrained(fl_id, dtype=torch.float16).to('cuda')
proc = AutoProcessor.from_pretrained(fl_id)
depth_pipe = pipeline('depth-estimation', model='depth-anything/Depth-Anything-V2-Small-hf', device=0)

for name, path in IMAGES.items():
    img = Image.open(path).convert('RGB')
    img.thumbnail((1600, 1600))
    W, H = img.size

    def florence(task, text=''):
        inputs = proc(text=task + text, images=img, return_tensors='pt').to('cuda', torch.float16)
        ids = model.generate(**inputs, max_new_tokens=1024, num_beams=3)
        raw = proc.batch_decode(ids, skip_special_tokens=False)[0]
        return proc.post_process_generation(raw, task=task, image_size=img.size)[task]

    def boxes_of(result):
        labels = result.get('labels') or result.get('bboxes_labels') or []
        return list(zip(labels, result.get('bboxes', [])))

    caption = florence('<MORE_DETAILED_CAPTION>')
    dets = boxes_of(florence('<OD>'))
    for p in GENERIC_PHRASES:
        dets += boxes_of(florence('<OPEN_VOCABULARY_DETECTION>', p))

    depth_img = depth_pipe(img)['depth']
    if depth_img.size != img.size:
        depth_img = depth_img.resize(img.size)
    near = np.asarray(depth_img, dtype=np.float32) / 255.0

    items = []
    seen = set()
    for label, box in dets:
        x0, y0, x1, y1 = [float(b) for b in box]
        area = (x1 - x0) * (y1 - y0) / (W * H)
        if area < 0.001 or area > 0.6:
            continue
        key = (label, round(x0 / 20), round(y0 / 20), round(x1 / 20), round(y1 / 20))   # 같은 상자 중복 제거
        if key in seen:
            continue
        seen.add(key)
        patch = near[max(int(y0), 0):min(int(y1), H), max(int(x0), 0):min(int(x1), W)]
        far = 1.0 - float(np.median(patch)) if patch.size else 0.5
        items.append(dict(label=label, u=round((x0 + x1) / 2 / W, 3), v=round((y0 + y1) / 2 / H, 3),
                          size=round(area, 4), depth=round(far, 3), box=[round(x0), round(y0), round(x1), round(y1)]))
    # 너무 많으면 큰 것 위주로 30개까지
    items = sorted(items, key=lambda d: -d['size'])[:30]
    items = sorted(items, key=lambda d: (d['v'], d['u']))
    for i, it in enumerate(items):
        it['index'] = i

    img.save(os.path.join(OUT, name + '.jpg'), quality=92)
    json.dump(dict(name=name, width=W, height=H, caption=caption, detections=items),
              open(os.path.join(OUT, name + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{name:10s} {len(items):2d} detections | {caption[:90]}', flush=True)
