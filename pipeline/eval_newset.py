# v3 일반화 확인: 평가셋 밖 새 그림(화풍별 1장)에서 9B v3를 Claude 답지·Gemini 답지로 채점 (결정사항 6-1 Q7)
#   python eval_newset.py run      ← 9B v3 실행 (GPU)
#   python eval_newset.py gemini   ← Gemini 답지 만들기
#   python eval_newset.py score    ← 채점 (Claude 답지: paintings/newset/answers_claude.json, Gemini 답지) → bench/newset/index.html
import html, json, math, os, sys, time
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import PAINTINGS, BENCH
NEW = os.path.join(PAINTINGS, 'newset')
OUT = os.path.join(BENCH, 'newset'); os.makedirs(OUT, exist_ok=True)
meta = json.load(open(os.path.join(NEW, 'newset.json'), encoding='utf-8'))
KEYS = [m['file'][:-4] for m in meta]


VAR = sys.argv[2] if len(sys.argv) > 2 else ''   # '' = v3, 't' = v3 + 그림 정보(제목·화가)


def run():
    import torch
    from bench_run import MODELS, POINT_V3, load, ask, parse, painting_context
    model, proc = load(MODELS['qwen35_9b_nf4'], nf4=True)
    for k in KEYS:
        path = os.path.join(OUT, k + f'_9b{VAR}.json')
        if os.path.exists(path):
            continue
        m = next(x for x in meta if x['file'][:-4] == k)
        prompt = (painting_context(m['title'], m['artist']) if VAR == 't' else '') + POINT_V3
        img = Image.open(os.path.join(NEW, k + '.jpg')).convert('RGB'); img.thumbnail((1024, 1024))
        t = time.time(); raw, _ = ask(model, proc, img, prompt); parsed = parse(raw)
        if parsed is None:          # 파이프라인과 같은 조건: 한 번 더
            raw, _ = ask(model, proc, img, prompt); parsed = parse(raw)
        json.dump(dict(painting=k, seconds=round(time.time() - t, 1), parsed=parsed, raw=raw), open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'{k:16s} {time.time() - t:5.1f}s n={len((parsed or {}).get("sources") or [])}', flush=True)
        torch.cuda.empty_cache()


def gemini():
    import gemini_tools
    for k in KEYS:
        path = os.path.join(OUT, k + '_gemini_key.json')
        if os.path.exists(path):
            continue
        g = gemini_tools.answer_key(Image.open(os.path.join(NEW, k + '.jpg')).convert('RGB'))
        json.dump(g, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(k, len((g or {}).get('sources', [])), flush=True)


def score():
    import gemini_tools
    claude = json.load(open(os.path.join(NEW, 'answers_claude.json'), encoding='utf-8'))
    tot = {n: dict(req=0, found=0, pred=0, inv=0, loc_n=0, loc_ok=0) for n in ('claude', 'gemini')}
    rows = []
    for k in KEYS:
        img = Image.open(os.path.join(NEW, k + '.jpg')).convert('RGB')
        W, H = img.size; diag = math.hypot(W, H)
        p9 = (json.load(open(os.path.join(OUT, k + f'_9b{VAR}.json'), encoding='utf-8'))['parsed'] or {}).get('sources') or []
        pred = [dict(label_ko=str(s.get('label_ko', '')), sound_en=str(s.get('prompt_en', '')), ground_phrase_en=str(s.get('object_en', '')),
                     pt=(s.get('x'), s.get('y'))) for s in p9]
        keys = {'claude': claude[k]['sources'], 'gemini': (json.load(open(os.path.join(OUT, k + '_gemini_key.json'), encoding='utf-8')) or {}).get('sources', [])}
        cell = []
        for name, ans in keys.items():
            cache = os.path.join(OUT, f'{k}_judge{VAR}_{name}.json')
            j = json.load(open(cache, encoding='utf-8')) if os.path.exists(cache) else gemini_tools.judge(img, ans, pred)
            json.dump(j, open(cache, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            j = j or {}
            pairs = {}
            for pr in j.get('pairs', []):
                try:
                    pairs[int(pr['answer']) - 1] = int(pr['model']) - 1
                except (KeyError, TypeError, ValueError):
                    pass
            req = [i for i, a in enumerate(ans) if a.get('grade') == 'required']
            bad = [u for u in j.get('unpaired', []) if u.get('verdict') in ('silent', 'not_visible')]
            t = tot[name]; t['req'] += len(req); t['found'] += sum(1 for i in req if i in pairs); t['pred'] += len(pred); t['inv'] += len(bad)
            for a_i, m_i in pairs.items():
                a = ans[a_i]
                if a.get('source_type') == 'ambient' or not a.get('points') or not (0 <= m_i < len(pred)) or None in pred[m_i]['pt']:
                    continue
                x, y = pred[m_i]['pt']
                d = min(math.hypot((x - q[0]) / 1000 * W, (y - q[1]) / 1000 * H) for q in a['points']) / diag
                t['loc_n'] += 1; t['loc_ok'] += d <= 0.10
            missed = [ans[i]['label_ko'] for i in req if i not in pairs]
            invented = [f"{pred[int(u['model']) - 1]['label_ko']}({u['verdict']})" for u in bad if 0 < int(u['model']) <= len(pred)]
            cell.append(f"<td>필수 {sum(1 for i in req if i in pairs)}/{len(req)}<br>지어냄 {len(bad)}/{len(pred)}"
                        + (f"<br><span class=m>놓침: {html.escape(', '.join(missed))}</span>" if missed else '')
                        + (f"<br><span class=m>지어냄: {html.escape(', '.join(invented))}</span>" if invented else '') + '</td>')
        m = next(x for x in meta if x['file'][:-4] == k)
        rows.append(f"<tr><td><b>{html.escape(m['title'])}</b><br><span class=m>{m['artist']}, {m['style']}</span></td>"
                    f"<td>{html.escape(', '.join(p['label_ko'] for p in pred))}</td>{''.join(cell)}</tr>")
    summ = {n: dict(required=f"{t['found']}/{t['req']}", required_found=round(t['found'] / max(t['req'], 1), 3),
                    invented=f"{t['inv']}/{t['pred']}", invented_rate=round(t['inv'] / max(t['pred'], 1), 3),
                    loc=f"{t['loc_ok']}/{t['loc_n']}", loc_rate=round(t['loc_ok'] / max(t['loc_n'], 1), 3)) for n, t in tot.items()}
    json.dump(summ, open(os.path.join(OUT, f'summary{VAR}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    head = ''.join(f"<tr><td>{n} 답지</td><td>{s['required_found'] * 100:.0f}% ({s['required']})</td><td>{s['invented_rate'] * 100:.0f}% ({s['invented']})</td>"
                   f"<td>{s['loc_rate'] * 100:.0f}% ({s['loc']})</td></tr>" for n, s in summ.items())
    open(os.path.join(OUT, f'index{VAR}.html'), 'w', encoding='utf-8').write(
        "<!doctype html><meta charset=utf-8><title>v3 새 그림 확인</title><style>body{font-family:'Malgun Gothic';margin:24px;background:#f6f6f4}"
        "table{border-collapse:collapse;margin:10px 0}td,th{border:1px solid #ccc;padding:6px;vertical-align:top;font-size:13px}.m{color:#666;font-size:12px}</style>"
        "<h1>v3 일반화 확인 — 평가셋 밖 새 그림 (화풍별 1장)</h1><p class=m>9B v3를 Claude 답지와 Gemini 답지로 각각 채점(채점기 Gemini, ±5%p). 평가셋 30장 결과: 필수 75%, 지어냄 12.5%, 위치 90%</p>"
        f"<table><tr><th>기준</th><th>필수 찾음</th><th>지어냄</th><th>위치 10% 이내</th></tr>{head}</table>"
        f"<table><tr><th>그림</th><th>9B v3 소리원</th><th>Claude 답지 기준</th><th>Gemini 답지 기준</th></tr>{''.join(rows)}</table>")
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == '__main__':
    {'run': run, 'gemini': gemini, 'score': score}[sys.argv[1]]()
