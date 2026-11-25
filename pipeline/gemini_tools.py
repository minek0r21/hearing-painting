# Gemini 도구 (결정사항 6-1, 6-3 N1~N4): 새 그림 답지 만들기 + 모델 출력 의미 판정
# 평가(eval_baseline.py)와 파이프라인(pipeline.py)이 같은 지시문을 쓰도록 한 곳에 둔다.
# 채점기 편향 확인(11/25): 6장에서 Claude 직접 판정과 비교 — Gemini 출력 판정은 완전히 일치(자기 선호 편향 없음),
# 9B 출력은 필수 1개 엄격·지어냄 2개 관대 → 흔들림 약 ±5%p
import base64, io, json, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = 'gemini-4-neon'

ANSWER_PROMPT = """You are building a ground-truth answer key for evaluating AI "sound designers" for paintings.
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

JUDGE_PROMPT = """You are grading an AI "sound designer" for a painting against an answer key.
Look at the painting. Below are two lists of sound sources.
ANSWER KEY (A1, A2, ...) and MODEL OUTPUT (M1, M2, ...).

Tasks:
1. Pair each model source with the answer-key source that means the SAME sound coming from the SAME kind of thing in the painting, even if the words differ
   (e.g. "crowd noise" = "spectators cheering"; "boat creaking" = "creaking ships and ropes"). Each answer item and each model item can be used at most once.
   Do not pair sounds that are only loosely related (e.g. "wind in trees" is not "waterfall").
2. For every model source that is NOT paired, give a verdict. Decide in this order:
   - "not_visible": ONLY when the object or creature that makes the sound is absent from the painting (e.g. a horse when there is no horse, a guitar when the instrument shown is a fiddle).
   - "silent": the object is in the painting but cannot make sound in this scene at all (jewelry, clothes, still objects, buildings, background, "room tone" or silence).
   - "plausible": the object is in the painting and it can make this kind of sound, even if the exact action is not clearly shown (e.g. walking dogs barking, a crowd murmuring), but the answer key does not list it.
Return ONLY JSON: {"pairs": [{"model": 1, "answer": 3}], "unpaired": [{"model": 2, "verdict": "plausible|silent|not_visible", "why": "short reason"}]}

ANSWER KEY:
{answer_list}

MODEL OUTPUT:
{model_list}"""


def api_key():
    from paths import load_env
    load_env()
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not key:
        raise RuntimeError('GEMINI_API_KEY 없음 (.env 또는 환경 변수)')
    return key


def call(img, text, tries=4):
    # 그림 + 지시문 → JSON (실패하면 None). 네트워크·한도 오류는 잠깐 쉬고 다시 시도
    import httpx
    im = img.copy(); im.thumbnail((1024, 1024))
    buf = io.BytesIO(); im.convert('RGB').save(buf, 'JPEG', quality=88)
    body = {'contents': [{'parts': [{'inline_data': {'mime_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}}, {'text': text}]}],
            'generationConfig': {'responseMimeType': 'application/json', 'temperature': 0}}
    with httpx.Client(timeout=300) as cl:
        for attempt in range(tries):
            try:
                r = cl.post(f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent',
                            headers={'x-goog-api-key': api_key()}, json=body)
                if r.status_code == 200:
                    return json.loads(r.json()['candidates'][0]['content']['parts'][-1]['text'])
                print(f'  Gemini HTTP {r.status_code}, 다시 시도', flush=True)
            except Exception as e:
                print(f'  Gemini 오류 {type(e).__name__}, 다시 시도', flush=True)
            time.sleep(10 * (attempt + 1))
    return None


def answer_key(img):
    # 새 그림의 답지 (평가셋 정답지 v2와 같은 규칙). 실패하면 None
    parsed = call(img, ANSWER_PROMPT)
    if not parsed or not isinstance(parsed.get('sources'), list):
        return None
    return parsed


def judge(img, ans, pred):
    # ans: 답지 소리원 목록 (label_ko, sound_en, ground_phrase_en, source_type)
    # pred: 모델 소리원 목록 (label_ko, sound_en, ground_phrase_en)
    al = '\n'.join(f"A{i + 1}. {a['label_ko']} / {a['sound_en']} (object: {a.get('ground_phrase_en', '')}, {a['source_type']})" for i, a in enumerate(ans))
    ml = '\n'.join(f"M{j + 1}. {p['label_ko']} / {p['sound_en']} (object: {p['ground_phrase_en']})" for j, p in enumerate(pred))
    return call(img, JUDGE_PROMPT.replace('{answer_list}', al).replace('{model_list}', ml))


def score(img, ans, pred):
    # 그림 한 장의 품질 점수: 필수 찾은 비율, 지어낸 소리 비율 (채점기 흔들림 약 ±5%p)
    j = judge(img, ans, pred)
    if j is None:
        return None
    paired = {int(p['answer']) - 1 for p in j.get('pairs', []) if str(p.get('answer', '')).isdigit()}
    req = [i for i, a in enumerate(ans) if a.get('grade') == 'required']
    bad = [u for u in j.get('unpaired', []) if u.get('verdict') in ('silent', 'not_visible')]
    return dict(required_found=round(sum(1 for i in req if i in paired) / max(len(req), 1), 3),
                required=f"{sum(1 for i in req if i in paired)}/{len(req)}",
                invented=round(len(bad) / max(len(pred), 1), 3), invented_n=f'{len(bad)}/{len(pred)}',
                missed=[ans[i]['label_ko'] for i in req if i not in paired],
                invented_items=[f"{pred[int(u['model']) - 1]['label_ko']} ({u.get('verdict')})" for u in bad if 0 < int(u['model']) <= len(pred)],
                judge=MODEL)
