# 12/03 목표 기준선 측정: 소리 설계 VLM을 평가셋 30장에 돌려 정답지 v2로 채점
#   python eval_baseline.py [모델키=qwen35_9b_nf4] [--prompt v1|v2|v3|v3t] [--score-only] [--no-judge]   (발표 수치: --prompt v3t)
# 결과: eval/eval30(저장소) 또는 bench/eval30(작업 폴더)/<모델키>[_p2|_p3|_p3t]/<그림>.json, index.html, summary.json, judge/<그림>.json(의미 판정 캐시)
# 지표 (결정사항 G63~): 필수 소리원 찾은 비율(목표 70%↑), 지어낸 소리 비율(15%↓), 위치 오차 대각선 10% 이내, JSON 성공, 시간
# 짝짓기
#   의미 판정(기본): Gemini가 그림을 보며 모델 소리원과 정답지 소리원을 뜻으로 짝지음. 정답지에 없는 모델 소리는
#                    plausible(실제로 들릴 만한데 정답지에 없음) / silent(소리 안 나는 물체) / not_visible(그림에 없음)로 분류.
#                    "지어낸 소리" = silent + not_visible.
#   단어 겹침(비교용): answers_compare.py와 같은 규칙(이름 단어 겹침 + 0~1000 좌표 거리 150 이내).
import base64, hashlib, html, io, json, math, os, re, sys, time
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import PAINTINGS, BENCH, FONT
EVAL = os.path.join(PAINTINGS, 'evalset')
args = [a for a in sys.argv[1:] if not a.startswith('--')]
KEY = args[0] if args else 'qwen35_9b_nf4'
PROMPT_VER = sys.argv[sys.argv.index('--prompt') + 1] if '--prompt' in sys.argv else 'v1'
assert PROMPT_VER in ('v1', 'v2', 'v3', 'v3t'), PROMPT_VER   # v3t = v3 + 그림 정보(제목·화가)
SCORE_ONLY = '--score-only' in sys.argv
JUDGE = '--no-judge' not in sys.argv
JUDGE_MODEL = 'gemini-4-neon'
OUT = os.path.join(BENCH, 'eval30', KEY + {'v1': '', 'v2': '_p2', 'v3': '_p3', 'v3t': '_p3t'}[PROMPT_VER])
os.makedirs(os.path.join(OUT, 'judge'), exist_ok=True)

answers = json.load(open(os.path.join(EVAL, 'answers_claude', 'answers_claude_v2.json'), encoding='utf-8'))
DIST = 150
AMBIENT_KEYS = {'rain': ['rain', 'shower', 'drizzle'], 'wind': ['wind', 'breeze', 'gust'], 'sea': ['sea', 'ocean', 'wave', 'surf', 'shore'],
                'crowd': ['crowd', 'murmur', 'chatter', 'city', 'market'], 'music': ['music', 'band', 'concert'], 'quiet': ['quiet', 'room tone', 'silence', 'still'],
                'water': ['river', 'stream', 'water', 'drip'], 'snow': ['snow', 'night']}


# ---------- 단어 겹침 짝짓기 (이전 방식, 비교용) ----------
def tags(s):
    text = (s.get('sound_en', '') + ' ' + s.get('ground_phrase_en', '')).lower()
    return {k for k, ws in AMBIENT_KEYS.items() if any(w in text for w in ws)}


def words(s):
    text = (s.get('sound_en', '') + ' ' + s.get('ground_phrase_en', '')).lower()
    return set(re.findall(r'[a-z]{4,}', text)) - {'with', 'from', 'over', 'distant', 'sound', 'people', 'person', 'field', 'recording'}


def similar(a, b):
    if a['source_type'] == 'ambient' or b['source_type'] == 'ambient' or not a.get('points') or not b.get('points'):
        return bool(tags(a) & tags(b)) or len(words(a) & words(b)) >= 2
    d = min(math.dist(p, q) for p in a['points'] for q in b['points'])
    return d <= DIST and (len(words(a) & words(b)) >= 1 or bool(tags(a) & tags(b)) or d <= DIST / 2)


def word_match(ans, pred):
    def score(a, p):
        if not similar(a, p):
            return None
        d = min(math.dist(x, y) for x in a['points'] for y in p['points']) if a.get('points') and p.get('points') else 0
        return d - 100 * len(words(a) & words(p)) - 100 * len(tags(a) & tags(p))
    cand = sorted((sc, i, j) for i, a in enumerate(ans) for j, p in enumerate(pred) if (sc := score(a, p)) is not None)
    ui, uj, pairs = set(), set(), []
    for sc, i, j in cand:
        if i not in ui and j not in uj:
            ui.add(i); uj.add(j); pairs.append((i, j))
    return sorted(pairs)


# ---------- 의미 판정 (Gemini) ----------
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


def gemini_key():
    from gemini_tools import api_key
    return api_key()


def semantic_match(key, ans, pred):
    al = '\n'.join(f"A{i + 1}. {a['label_ko']} / {a['sound_en']} (object: {a.get('ground_phrase_en', '')}, {a['source_type']})" for i, a in enumerate(ans))
    ml = '\n'.join(f"M{j + 1}. {p['label_ko']} / {p['sound_en']} (object: {p['ground_phrase_en']})" for j, p in enumerate(pred))
    prompt = JUDGE_PROMPT.replace('{answer_list}', al).replace('{model_list}', ml)
    h = hashlib.sha1(prompt.encode('utf-8')).hexdigest()[:12]
    cache = os.path.join(OUT, 'judge', key + '.json')
    if os.path.exists(cache):
        c = json.load(open(cache, encoding='utf-8'))
        if c.get('hash') == h and c.get('parsed'):
            return c['parsed']
    import httpx
    img = Image.open(os.path.join(EVAL, key + '.jpg')).convert('RGB'); img.thumbnail((1024, 1024))
    buf = io.BytesIO(); img.save(buf, 'JPEG', quality=88)
    body = {'contents': [{'parts': [{'inline_data': {'mime_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}}, {'text': prompt}]}],
            'generationConfig': {'responseMimeType': 'application/json', 'temperature': 0}}
    parsed, text = None, ''
    with httpx.Client(timeout=300) as cl:
        for attempt in range(4):
            r = cl.post(f'https://generativelanguage.googleapis.com/v1beta/models/{JUDGE_MODEL}:generateContent',
                        headers={'x-goog-api-key': gemini_key()}, json=body)
            if r.status_code == 200:
                try:
                    text = r.json()['candidates'][0]['content']['parts'][-1]['text']
                    parsed = json.loads(text)
                    break
                except Exception:
                    pass
            print(f'  judge {key} HTTP {r.status_code} 재시도', flush=True); time.sleep(15 * (attempt + 1))
    json.dump(dict(hash=h, model=JUDGE_MODEL, parsed=parsed, raw=text), open(cache, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    time.sleep(1)
    return parsed


def to_answer_form(s):
    # 모델 출력(point 방식) → 정답지와 같은 모양
    ok = isinstance(s.get('x'), (int, float)) and isinstance(s.get('y'), (int, float))
    return dict(label_ko=str(s.get('label_ko', '')), sound_en=str(s.get('prompt_en', '')), ground_phrase_en=str(s.get('object_en', '')),
                source_type='point', points=[[float(s['x']), float(s['y'])]] if ok else [], type=s.get('type'))


# ---------- 모델 실행 ----------
def run_model():
    import torch
    sys.path.insert(0, HERE)
    from bench_run import MODELS, POINT, POINT_V2, POINT_V3, load, ask, parse, check, painting_context
    prompt = {'v1': POINT, 'v2': POINT_V2, 'v3': POINT_V3, 'v3t': POINT_V3}[PROMPT_VER]
    meta = {m['file'][:-4]: m for m in json.load(open(os.path.join(EVAL, 'evalset.json'), encoding='utf-8')) if m.get('file')}
    t0 = time.time()
    model, proc = load(MODELS[KEY], nf4=KEY.endswith('_nf4'))
    print(f'[{KEY} {PROMPT_VER}] 로드 {time.time() - t0:.0f}s', flush=True)
    for key in answers:
        path = os.path.join(OUT, key + '.json')
        if os.path.exists(path):
            continue
        img = Image.open(os.path.join(EVAL, key + '.jpg')).convert('RGB')
        img.thumbnail((1024, 1024))
        torch.cuda.reset_peak_memory_stats()
        t = time.time()
        try:
            ctx = painting_context(meta[key]['title'], meta[key].get('artist', '')) if PROMPT_VER == 'v3t' else ''
            raw, _ = ask(model, proc, img, ctx + prompt); err = None
        except Exception as e:
            raw, err = '', f'{type(e).__name__}: {e}'
        sec = time.time() - t
        parsed = parse(raw)
        r = dict(model=MODELS[KEY], prompt=PROMPT_VER, painting=key, seconds=round(sec, 1), peak_vram_gb=round(torch.cuda.max_memory_allocated() / 1e9, 2),
                 error=err, checks=check(parsed, 'point', 0), parsed=parsed, raw=raw)
        json.dump(r, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'[{KEY} {PROMPT_VER}] {key:20s} {sec:5.1f}s json={r["checks"].get("json_ok")} n={r["checks"].get("n_sources")}', flush=True)
        torch.cuda.empty_cache()


# ---------- 채점 ----------
def score_all():
    z = lambda: dict(req=0, req_found=0, allowed_found=0, pred=0, unpaired=0, plausible=0, silent=0, not_visible=0, loc_n=0, loc_ok=0)
    tot = dict(paintings=0, json_ok=0, sec=0.0, vram=0.0)
    sem, wrd = z(), z()
    rows = []
    font = ImageFont.truetype(FONT, 14)
    for key, ak in answers.items():
        path = os.path.join(OUT, key + '.json')
        if not os.path.exists(path):
            continue
        r = json.load(open(path, encoding='utf-8'))
        tot['paintings'] += 1; tot['sec'] += r['seconds']; tot['vram'] = max(tot['vram'], r['peak_vram_gb'])
        ok = bool(r['checks'].get('json_ok')) and isinstance((r['parsed'] or {}).get('sources'), list)
        tot['json_ok'] += ok
        ans = ak['sources']
        pred = [to_answer_form(s) for s in (r['parsed'] or {}).get('sources', [])] if ok else []
        img = Image.open(os.path.join(EVAL, key + '.jpg')).convert('RGB')
        W0, H0 = img.size
        diag = math.hypot(W0, H0)

        def tally(acc, pairs, verdicts):
            found = {i for i, _ in pairs}
            acc['req'] += sum(1 for a in ans if a['grade'] == 'required')
            acc['req_found'] += sum(1 for i in found if ans[i]['grade'] == 'required')
            acc['allowed_found'] += sum(1 for i in found if ans[i]['grade'] == 'allowed')
            acc['pred'] += len(pred); acc['unpaired'] += len(pred) - len(pairs)
            for v in verdicts.values():
                acc[v] = acc.get(v, 0) + 1
            locs = []
            for i, j in pairs:
                a, p = ans[i], pred[j]
                if a['source_type'] == 'ambient' or not a.get('points') or not p.get('points'):
                    continue
                px = p['points'][0]
                d = min(math.hypot((px[0] - q[0]) / 1000 * W0, (px[1] - q[1]) / 1000 * H0) for q in a['points']) / diag
                acc['loc_n'] += 1; acc['loc_ok'] += d <= 0.10
                locs.append((a['label_ko'], p['label_ko'], d))
            return found, locs

        wpairs = word_match(ans, pred)
        tally(wrd, wpairs, {})
        spairs, verdicts = wpairs, {}
        if JUDGE and pred:
            j = semantic_match(key, ans, pred) or {}
            seen_a, seen_m, spairs = set(), set(), []
            for pr in j.get('pairs', []):
                try:
                    m, a = int(pr['model']) - 1, int(pr['answer']) - 1
                except (KeyError, TypeError, ValueError):
                    continue
                if 0 <= m < len(pred) and 0 <= a < len(ans) and m not in seen_m and a not in seen_a:
                    seen_m.add(m); seen_a.add(a); spairs.append((a, m))
            for u in j.get('unpaired', []):
                try:
                    m = int(u['model']) - 1
                except (KeyError, TypeError, ValueError):
                    continue
                if 0 <= m < len(pred) and m not in seen_m:
                    verdicts[m] = u.get('verdict') if u.get('verdict') in ('plausible', 'silent', 'not_visible') else 'plausible'
            for m in range(len(pred)):           # 판정이 빠진 것은 '그럴듯함'으로 (보수적으로 지어냄에 넣지 않음)
                if m not in seen_m and m not in verdicts:
                    verdicts[m] = 'plausible'
        found, locs = tally(sem, spairs, verdicts) if JUDGE else (set(i for i, _ in wpairs), [])

        # 그림: 정답(파랑, 필수는 큰 원) vs 모델(주황 네모)
        im = img.copy(); im.thumbnail((640, 640)); W, H = im.size; dr = ImageDraw.Draw(im)
        for n, a in enumerate(ans, 1):
            for q in a.get('points', []):
                x, y = q[0] / 1000 * W, q[1] / 1000 * H; rr = 7 if a['grade'] == 'required' else 5
                dr.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(40, 120, 255), outline=(0, 0, 0), width=2)
            if a.get('points'):
                q = a['points'][0]; dr.text((q[0] / 1000 * W + 8, q[1] / 1000 * H - 8), f'C{n}', fill=(40, 120, 255), font=font, stroke_width=2, stroke_fill=(0, 0, 0))
        for n, p in enumerate(pred, 1):
            for q in p['points']:
                x, y = q[0] / 1000 * W, q[1] / 1000 * H
                dr.rectangle([x - 6, y - 6, x + 6, y + 6], fill=(255, 130, 0), outline=(0, 0, 0), width=2)
                dr.text((x + 8, y + 2), f'Q{n}', fill=(255, 130, 0), font=font, stroke_width=2, stroke_fill=(0, 0, 0))
        im.save(os.path.join(OUT, key + '.jpg'), quality=85)
        pm = {m: a for a, m in spairs}
        vname = {'plausible': '정답지에 없지만 들릴 만함', 'silent': '지어냄: 소리 안 나는 물체', 'not_visible': '지어냄: 그림에 없음'}
        li_a = ''.join(f"<li class={'ok' if i in found else 'miss'}>C{i + 1} [{'필수' if a['grade'] == 'required' else '허용'}/{a['source_type']}] {html.escape(a['label_ko'])}</li>" for i, a in enumerate(ans))
        li_p = ''.join(f"<li class={'ok' if j in pm else ('inv' if verdicts.get(j) in ('silent', 'not_visible') else 'pl')}>Q{j + 1} {html.escape(p['label_ko'])} <span class=m>{html.escape(p['ground_phrase_en'])}</span>"
                       + (f" → C{pm[j] + 1}" if j in pm else f" → {vname.get(verdicts.get(j), '정답지에 없음')}") + '</li>' for j, p in enumerate(pred))
        li_l = ''.join(f"<li class={'ok' if d <= 0.1 else 'miss'}>{html.escape(a)} ↔ {html.escape(b)}: 대각선의 {d * 100:.1f}%</li>" for a, b, d in locs)
        rows.append(f"<h2>{html.escape(key)} — {html.escape(ak['title'])} <span class=m>{r['seconds']}초" + ('' if ok else ' · <b class=miss>JSON 실패</b>') + "</span></h2>"
                    f"<div class=row><img src='{key}.jpg'><div><h4>정답지 (초록 = 찾음, 빨강 = 놓침)</h4><ul>{li_a}</ul>"
                    f"<h4>모델 출력 (초록 = 짝 있음, 파랑 = 정답지에 없지만 들릴 만함, 빨강 = 지어냄)</h4><ul>{li_p}</ul><h4>위치 오차</h4><ul>{li_l or '<li>-</li>'}</ul></div></div>")
    n = max(tot['paintings'], 1)
    S = sem if JUDGE else wrd
    inv = S['silent'] + S['not_visible'] if JUDGE else S['unpaired']
    summ = dict(model=KEY, prompt=PROMPT_VER, judge=JUDGE_MODEL if JUDGE else 'word', paintings=tot['paintings'], json_ok=f"{tot['json_ok']}/{tot['paintings']}",
                required_found=round(S['req_found'] / max(S['req'], 1), 3), required=f"{S['req_found']}/{S['req']}", allowed_found=S['allowed_found'],
                invented=round(inv / max(S['pred'], 1), 3), invented_n=f"{inv}/{S['pred']}",
                plausible_extra=S.get('plausible', 0), silent=S.get('silent', 0), not_visible=S.get('not_visible', 0),
                loc_within_10pct=round(S['loc_ok'] / max(S['loc_n'], 1), 3), loc_n=f"{S['loc_ok']}/{S['loc_n']}",
                word_required_found=round(wrd['req_found'] / max(wrd['req'], 1), 3), word_unpaired=round(wrd['unpaired'] / max(wrd['pred'], 1), 3),
                avg_sec=round(tot['sec'] / n, 1), peak_vram_gb=tot['vram'])
    json.dump(summ, open(os.path.join(OUT, 'summary.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    def row(name, val, goal, good):
        return f"<tr><td>{name}</td><td><b>{val}</b></td><td>{goal}</td><td class={'ok' if good else 'miss'}>{'달성' if good else '미달'}</td></tr>"
    table = ('<table><tr><th>지표</th><th>현재</th><th>12/03 목표</th><th></th></tr>'
             + row('필수 소리원 찾은 비율', f"{summ['required_found'] * 100:.0f}% ({summ['required']})", '70% 이상', summ['required_found'] >= 0.7)
             + row('지어낸 소리 비율 (소리 안 나는 물체 + 그림에 없음)', f"{summ['invented'] * 100:.0f}% ({summ['invented_n']})", '15% 이하', summ['invented'] <= 0.15)
             + row('위치 오차 대각선 10% 이내', f"{summ['loc_within_10pct'] * 100:.0f}% ({summ['loc_n']})", '(전부)', summ['loc_within_10pct'] >= 0.9)
             + row('JSON 성공', summ['json_ok'], '100%', tot['json_ok'] == tot['paintings'])
             + row('그림 1장 평균 시간 (VLM 단계만)', f"{summ['avg_sec']}초", '전 과정 10분 이내', summ['avg_sec'] < 600) + '</table>')
    extra = (f"<p class=m>정답지 밖 소리: 들릴 만함 {summ['plausible_extra']}, 소리 안 나는 물체 {summ['silent']}, 그림에 없음 {summ['not_visible']}. "
             f"비교: 이전 단어 겹침 채점이면 필수 {summ['word_required_found'] * 100:.0f}%, 짝 없음 {summ['word_unpaired'] * 100:.0f}%.</p>") if JUDGE else ''
    page = ("<!doctype html><meta charset=utf-8><title>VLM 기준선 30장</title><style>body{font-family:'Malgun Gothic',sans-serif;margin:24px;background:#f6f6f4}"
            "table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:4px 10px}.row{display:flex;gap:16px;align-items:flex-start}.row img{width:560px;border-radius:6px}"
            "h2{margin-top:32px;border-bottom:2px solid #333;font-size:18px}.m{color:#666;font-size:12px;font-weight:normal}.ok{color:#176}.miss{color:#c00}.inv{color:#c00}.pl{color:#2a5db0}li{margin:2px 0;font-size:13px}</style>"
            f"<h1>소리 설계 VLM 기준선 — {KEY}, 프롬프트 {PROMPT_VER}, 평가셋 {tot['paintings']}장, 정답지 v2</h1>{table}{extra}"
            f"<p class=m>짝짓기: {'Gemini(' + JUDGE_MODEL + ')가 그림을 보며 뜻으로 판정' if JUDGE else '이름 단어 겹침 + 거리 150 이내'}. "
            "그림: 파랑 원 = 정답지(C번호, 큰 원 = 필수), 주황 네모 = 모델(Q번호).</p>" + ''.join(rows))
    open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(page)
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == '__main__':
    if not SCORE_ONLY:
        run_model()
    score_all()
