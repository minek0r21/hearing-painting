# VLM 비교 실행: python bench_run.py <모델키> [그림 이름 ...]
# 그림마다 두 방식으로 묻는다
#   pick : Florence 탐지 목록을 주고 "몇 번 상자가 무슨 소리"인지 고르게 함 (위치는 탐지 상자)
#   point: 탐지 목록 없이 모델이 소리원 위치(0~1000 좌표)를 직접 찍게 함
# 결과: bench/results/<모델키>/<그림>_<방식>.json (원문, 파싱 결과, 자동 검사, 시간, VRAM)
import json, os, re, sys, time
import torch
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
IN = os.path.join(HERE, 'bench', 'inputs')
MODELS = {
    'qwen35_4b': 'Qwen/Qwen3.5-4B',
    'gemma4_e2b': 'google/gemma-4-E2B-it',
    'internvl35_4b': 'OpenGVLab/InternVL3_5-4B-HF',
    'minicpm47_1b': 'openbmb/MiniCPM-V-4.7-1B',
    'qwen35_9b_nf4': 'Qwen/Qwen3.5-9B',      # 키가 _nf4로 끝나면 4비트(NF4)로 불러옴
}
PAINTINGS = ['hunters', 'rainy_day', 'wave', 'beach', 'boulevard']
TYPES = ['nature', 'people', 'animal', 'vehicle', 'music']

COMMON = """You are a sound designer for an AR app that makes paintings audible.
Look at the painting and choose 4 to 6 sound sources that a viewer would expect to HEAR in this scene.
Rules:
- Only use things that are actually visible in the painting. Do not invent objects.
- Include at most one or two scene-wide ambient sounds (wind, rain, sea, crowd murmur).
- label_ko: short Korean name (2-8 characters). description_ko: one natural Korean sentence.
- prompt_en: a concrete English prompt for a sound generator, describing the sound itself, ending with "field recording".
- type: one of nature, people, animal, vehicle, music. volume: 0.5 to 1.0.
Return ONLY a JSON object, no explanation, no markdown."""

PICK = COMMON + """
Below are objects detected in the painting by another model.
Each line: index: label (u, v) size depth   — u: 0 left..1 right, v: 0 top..1 bottom, depth: 0 near..1 far.
{detections}
Scene caption from another model: {caption}

For a sound coming from a detected object, set "detection" to its index (use only indices in the list, and make sure that box really is the object you describe).
For a scene-wide ambient sound, set "detection" to null and give "u" and "v" (0..1) where it should be placed.
JSON format:
{{"title_guess": "painting title if you know it, else empty", "sources": [{{"id": "snake_case", "detection": 3, "u": null, "v": null, "label_ko": "...", "type": "...", "description_ko": "...", "prompt_en": "...", "volume": 0.8}}]}}"""

POINT = COMMON + """
For each sound source, give the point in the painting where the sound comes from, as integer coordinates x and y from 0 to 1000 (x: 0 left..1000 right, y: 0 top..1000 bottom). Point at the center of the object that makes the sound.
Also give "object_en": the English name of the visible object at that point.
JSON format:
{"title_guess": "painting title if you know it, else empty", "sources": [{"id": "snake_case", "object_en": "...", "x": 500, "y": 600, "label_ko": "...", "type": "...", "description_ko": "...", "prompt_en": "...", "volume": 0.8}]}"""


# v2 (11/25 밤): 30장 기준선에서 조용한 그림(초상화·정물)에 소리 안 나는 물체를 고르고, 같은 종류를 둘로 나누는 문제 수정.
# 출력 JSON 형식은 POINT와 같다.
POINT_V2 = """You are a sound designer for an AR app that makes paintings audible.
Look at the painting and choose the sound sources a viewer standing in front of this scene would actually HEAR.
What counts as a sound source:
- Something that is making sound in the scene right now: people or animals doing something, moving water or sea, weather (wind, rain, storm), fire, machines and vehicles, musical instruments being played, tools or objects being used.
- NOT a sound source: still objects (jewelry, clothes, hats, furniture, food, cups, bottles, baskets, buildings, lamps, signs, the background). Do not give sounds to them unless someone is visibly using them.
- Do not invent things that are not visible.
How many:
- Busy scenes: 4 to 6 sources. Quiet scenes (portrait, still life, empty room): only 1 to 3 (for example the one real action plus a quiet room tone).
- One source per kind: several dogs, boats, skaters or talking people doing the same thing = ONE source placed on the most important one.
- Choose in this order: the painting's main subject or event, large sources in the foreground, sounds that are loud in reality, variety of kinds.
- At most one or two scene-wide ambient sounds (wind, rain, sea, crowd murmur, room tone).
Fields:
- label_ko: short Korean name of the SOUND (2-8 characters). description_ko: one natural Korean sentence.
- prompt_en: a concrete English prompt for a sound generator, describing the sound itself, ending with "field recording".
- type: one of nature, people, animal, vehicle, music. volume: 0.5 to 1.0.
- x, y: integer point from 0 to 1000 (x: 0 left..1000 right, y: 0 top..1000 bottom) at the center of the object that makes the sound.
- object_en: the English name of the visible object at that point.
Return ONLY a JSON object, no explanation, no markdown:
{"title_guess": "painting title if you know it, else empty", "sources": [{"id": "snake_case", "object_en": "...", "x": 500, "y": 600, "label_ko": "...", "type": "...", "description_ko": "...", "prompt_en": "...", "volume": 0.8}]}"""


# v3 (11/25 밤, 마지막 버전): v2 결과 반영 (결정사항 6-1, v3 그릴링 Q1~Q7)
#   Q1 room tone 제안 삭제 / Q2 그림에 그려진 동작만(상상한 동작 금지) / Q4 위치 규칙 / Q5 악기는 모양으로, 동아시아 그림일 때만 한국 악기 이름
#   Q6 보이는 날씨·물은 장면 소리 필수 + 주인공(사람·동물)의 소리 우선
POINT_V3 = """You are a sound designer for an AR app that makes paintings audible.
Look at the painting and choose the sound sources a viewer standing in front of this scene would actually HEAR.

What counts as a sound source:
- Something that is clearly making sound in the painting right now: people or animals doing a visible action, moving water or sea, weather, fire, machines and vehicles, musical instruments being played.
- Only actions that are actually painted. Do not imagine what might happen next or what someone could do with an object. If a person is just standing or sitting, do not invent an activity for them.
- NOT a sound source: still objects (jewelry, clothes, hats, furniture, food, cups, bottles, baskets, buildings, lamps, signs, the background, silence or "room tone").
- Do not invent things that are not visible.

What to include first:
1. The main subject or event of the painting: the people or animals the painting is about and what they are doing (their footsteps, voices, work, play).
2. Visible weather or water: if rain, snow storm, strong wind, sea waves, a river or a waterfall is visible, include it as one scene-wide ambient source.
3. Other large sources in the foreground, then loud sounds, then variety.
- Busy scenes: 4 to 6 sources. Quiet scenes (portrait, still life, empty room): only the 1 or 2 sounds that really exist; it is fine to return just one.
- One source per kind: several dogs, boats, skaters or talking people doing the same thing = ONE source.

Musical instruments:
- Name an instrument only if you are sure. Otherwise describe what you see (for example "bowed string instrument", "transverse flute", "barrel drum").
- Only if the painting is clearly East Asian or Korean (ink painting, hanbok, Joseon genre painting), typical Korean instruments are: janggu (hourglass drum), buk (barrel drum), daegeum (large transverse flute), piri (small double-reed pipe), haegeum (two-string fiddle played with a bow), gayageum (zither). Never use these names for Western paintings.

Where to put each source (x, y):
- Point at the exact spot where the sound is produced: the mouth of a singer, the hands on an instrument, the spout of a pouring jug, the feet or hooves on the ground, the fire itself.
- For a group (crowd, flock, several dogs) point at the largest and nearest member of the group, never at an empty space between members.
- Never use a default center such as (500, 500) or (500, 200). Every point must be on the object itself.
- For a scene-wide ambient sound, point where it is most visible (the rain over the street, the crest of the wave, the top of the trees bent by wind).

Fields:
- label_ko: short Korean name of the SOUND (2-8 characters). description_ko: one natural Korean sentence.
- prompt_en: a concrete English prompt for a sound generator, describing the sound itself, ending with "field recording".
- type: one of nature, people, animal, vehicle, music. volume: 0.5 to 1.0.
- x, y: integers from 0 to 1000 (x: 0 left..1000 right, y: 0 top..1000 bottom).
- object_en: the English name of the visible object at that point.
Return ONLY a JSON object, no explanation, no markdown:
{"title_guess": "painting title if you know it, else empty", "sources": [{"id": "snake_case", "object_en": "...", "x": 500, "y": 600, "label_ko": "...", "type": "...", "description_ko": "...", "prompt_en": "...", "volume": 0.8}]}"""


# 그림 정보 단락 (11/25 밤 시험: v3 앞에 붙임. v3 본문은 그대로). 사용자가 입력한 제목·화가·연도를 끼워 넣기만 함
def painting_context(title='', artist='', year=''):
    title, artist, year = (title or '').strip(), (artist or '').strip(), str(year or '').strip()
    if not title:
        return ''
    line = f'About this painting: "{title}"' + (f' by {artist}' if artist else '') + (f' ({year})' if year else '') + '.'
    return (line + '\nUse this only to understand what is depicted. Still include only sounds whose source you can actually see in the image.'
            '\nDo not add a sound just because the title or the artist suggests it.\n\n')


def load(model_id, nf4=False):
    from transformers import AutoModelForImageTextToText, AutoProcessor
    proc = AutoProcessor.from_pretrained(model_id)
    kwargs = dict(dtype=torch.bfloat16, device_map='cuda')
    if nf4:
        from transformers import BitsAndBytesConfig
        kwargs['quantization_config'] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                                                           bnb_4bit_compute_dtype=torch.bfloat16)
    model = AutoModelForImageTextToText.from_pretrained(model_id, **kwargs)
    model.eval()
    return model, proc


def ask(model, proc, img, text, max_new_tokens=1500):
    messages = [{'role': 'user', 'content': [{'type': 'image', 'image': img}, {'type': 'text', 'text': text}]}]
    kwargs = dict(add_generation_prompt=True, tokenize=True, return_dict=True, return_tensors='pt')
    try:
        inputs = proc.apply_chat_template(messages, enable_thinking=False, **kwargs)   # Qwen3.5 등: 생각 모드 끔
    except TypeError:
        inputs = proc.apply_chat_template(messages, **kwargs)
    inputs = inputs.to(model.device)
    for k, v in inputs.items():
        if torch.is_floating_point(v):
            inputs[k] = v.to(torch.bfloat16)
    n_in = inputs['input_ids'].shape[1]
    with torch.inference_mode():
        out = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    return proc.batch_decode(out[:, n_in:], skip_special_tokens=True)[0], n_in


def parse(raw):
    s = re.sub(r'<think>.*?</think>', '', raw, flags=re.S)
    s = re.sub(r'```(?:json)?', '', s)
    start, end = s.find('{'), s.rfind('}')
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(s[start:end + 1])
    except json.JSONDecodeError:
        return None


def check(parsed, mode, n_det):
    c = dict(json_ok=parsed is not None)
    if not parsed or not isinstance(parsed.get('sources'), list):
        c['sources_ok'] = False
        return c
    src = parsed['sources']
    c['n_sources'] = len(src)
    c['count_ok'] = 4 <= len(src) <= 6
    hangul = re.compile('[가-힣]')
    c['korean_label'] = sum(1 for s in src if hangul.search(str(s.get('label_ko', ''))))
    c['korean_desc'] = sum(1 for s in src if hangul.search(str(s.get('description_ko', ''))))
    c['type_ok'] = sum(1 for s in src if s.get('type') in TYPES)
    c['prompt_ok'] = sum(1 for s in src if isinstance(s.get('prompt_en'), str) and len(s['prompt_en']) > 20 and not hangul.search(s['prompt_en']))
    if mode == 'pick':
        bad = 0
        for s in src:
            d = s.get('detection')
            if d is None:
                if not (isinstance(s.get('u'), (int, float)) and isinstance(s.get('v'), (int, float))):
                    bad += 1
            elif not (isinstance(d, int) and 0 <= d < n_det):
                bad += 1
        c['bad_position'] = bad
    else:
        c['bad_position'] = sum(1 for s in src if not (isinstance(s.get('x'), (int, float)) and isinstance(s.get('y'), (int, float))
                                                        and 0 <= s['x'] <= 1000 and 0 <= s['y'] <= 1000))
    return c


def main():
    key = sys.argv[1]
    names = sys.argv[2:] or PAINTINGS
    out_dir = os.path.join(HERE, 'bench', 'results', key)
    os.makedirs(out_dir, exist_ok=True)

    t0 = time.time()
    model, proc = load(MODELS[key], nf4=key.endswith('_nf4'))
    load_sec = time.time() - t0
    print(f'[{key}] 로드 {load_sec:.0f}s, VRAM {torch.cuda.memory_allocated() / 1e9:.1f}GB', flush=True)

    for name in names:
        data = json.load(open(os.path.join(IN, name + '.json'), encoding='utf-8'))
        img = Image.open(os.path.join(IN, name + '.jpg')).convert('RGB')
        img.thumbnail((1024, 1024))     # 모든 모델에 같은 크기로
        det_lines = '\n'.join(f"{d['index']}: {d['label']} (u={d['u']:.2f}, v={d['v']:.2f}) size={d['size']:.3f} depth={d['depth']:.2f}"
                              for d in data['detections'])
        prompts = {'pick': PICK.format(detections=det_lines, caption=data['caption']), 'point': POINT}
        for mode, text in prompts.items():
            torch.cuda.reset_peak_memory_stats()
            t = time.time()
            try:
                raw, n_in = ask(model, proc, img, text)
                err = None
            except Exception as e:
                raw, n_in, err = '', 0, f'{type(e).__name__}: {e}'
            sec = time.time() - t
            parsed = parse(raw)
            result = dict(model=MODELS[key], painting=name, mode=mode, seconds=round(sec, 1), input_tokens=n_in,
                          peak_vram_gb=round(torch.cuda.max_memory_allocated() / 1e9, 2), error=err,
                          checks=check(parsed, mode, len(data['detections'])), parsed=parsed, raw=raw)
            json.dump(result, open(os.path.join(out_dir, f'{name}_{mode}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            print(f'[{key}] {name:10s} {mode:5s} {sec:5.1f}s  {result["checks"]}' + (f'  ERR {err}' if err else ''), flush=True)
            torch.cuda.empty_cache()


if __name__ == '__main__':
    main()
