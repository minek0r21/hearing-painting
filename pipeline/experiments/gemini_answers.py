# 평가셋 30장에 대해 Gemini로 독립 정답지 만들기 (G23·G28·G33)
# 사용: python gemini_answers.py [모델 이름, 기본 gemini-4-neon]
# 결과: 03_제작/paintings/evalset/answers_gemini/<번호_이름>.json
import base64, json, os, sys, time
import httpx

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.join(HERE, '..', 'paintings', 'evalset')
OUT = os.path.join(EVAL, 'answers_gemini_v2')   # v2: G44~G47 규칙 (v1은 answers_gemini)
os.makedirs(OUT, exist_ok=True)
MODEL = sys.argv[1] if len(sys.argv) > 1 else 'gemini-4-neon'
KEY = [l.split('=', 1)[1].strip() for l in open(os.path.join(HERE, '.env'), encoding='utf-8-sig') if l.startswith('GEMINI_API_KEY=')][0]

PROMPT = """You are building a ground-truth answer key for evaluating AI "sound designers" for paintings.
Look carefully at the painting. List the sound sources a careful viewer would expect to HEAR in this scene.

Rules:
- Only sounds that come from things actually visible in the painting (or the visible weather/environment). Never include silent objects (a lamp post, a building, a still cup) as sound sources.
- EXCLUDE tiny sounds a listener standing a few steps in front of the scene would not hear: breathing, clothes rustling, pages turning, fans fluttering, a stick tapping, snow landing on an umbrella.
- ONE source per object or per group of the same kind. Do not split one object into several sounds (a carriage = one source including wheels and hooves; a group of boys = one source including shouts and footsteps; a locomotive = one source including its whistle). Several instances of the same kind (dogs, crows, boats) = one "clustered" source with several points.
- grade "required" = the scene would not feel like this painting without it (the main subject/event, or a large prominent sound source). grade "allowed" = visibly supported but minor or secondary.
- At most 5 required and at most 3 allowed. Choose in this priority order: (1) the painting's main subject/event, (2) large sources in the foreground, (3) sounds that are loud in reality, (4) variety of kinds (not only people). If more than 5 qualify as required, move the extra ones to allowed (still max 3 allowed); drop the least important beyond that.
- Name each source as a SOUND, not an object (e.g. "horse hooves on cobblestones", not "horse").
- source_type: "point" = comes from one place; "clustered" = several places of the same kind (a flock, a crowd spread out, several boats); "ambient" = the whole scene (wind, rain, sea, distant city).
- points: coordinates of where the sound comes from, as [x, y] integers from 0 to 1000 (x: left→right, y: top→bottom). point: exactly 1 point at the center of the object. clustered: 2-6 points on the instances. ambient: empty list.
- label_ko: short natural Korean sound name (e.g. "말발굽 소리"). ground_phrase_en: a short English noun phrase for locating the object in the image (e.g. "horse-drawn carriage").
- If the painting has almost no sound sources (still life, quiet portrait), return only those that truly exist, even zero or one.

Return JSON: {"title_guess": "...", "sources": [{"label_ko": "...", "sound_en": "...", "ground_phrase_en": "...", "source_type": "point|clustered|ambient", "grade": "required|allowed", "points": [[x, y]]}]}"""

files = sorted(f for f in os.listdir(EVAL) if f[:2].isdigit() and f.endswith('.jpg'))
with httpx.Client(timeout=300) as c:
    for f in files:
        out = os.path.join(OUT, f[:-4] + '.json')
        if os.path.exists(out):
            print('skip', f); continue
        data = base64.b64encode(open(os.path.join(EVAL, f), 'rb').read()).decode()
        body = {'contents': [{'parts': [{'inline_data': {'mime_type': 'image/jpeg', 'data': data}}, {'text': PROMPT}]}],
                'generationConfig': {'responseMimeType': 'application/json', 'temperature': 0}}
        for attempt in range(4):
            t = time.time()
            r = c.post(f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent',
                       headers={'x-goog-api-key': KEY}, json=body)
            if r.status_code == 200:
                break
            print(f, 'HTTP', r.status_code, r.text[:200]); time.sleep(20 * (attempt + 1))
        try:
            text = r.json()['candidates'][0]['content']['parts'][-1]['text']
            parsed = json.loads(text)
        except Exception as e:
            parsed, text = None, r.text[:2000]
        json.dump(dict(model=MODEL, file=f, seconds=round(time.time() - t, 1), parsed=parsed, raw=text,
                       usage=r.json().get('usageMetadata') if r.status_code == 200 else None),
                  open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        n = len(parsed['sources']) if parsed else 'FAIL'
        print(f'{f:28s} {n} sources  {time.time() - t:.0f}s', flush=True)
        time.sleep(2)
print('done')
