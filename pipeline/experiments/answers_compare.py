# Claude 정답지 vs Gemini 정답지 비교 (G28): 일치는 자동 확정, 불일치만 사용자 판정 페이지로
# 결과: 03_제작/paintings/evalset/compare/index.html, merged_auto.json
import html, json, math, os, re, sys
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.join(HERE, '..', 'paintings', 'evalset')
VER = sys.argv[1] if len(sys.argv) > 1 else ''          # '' = 1차, 'v2' = 2차
SUF = '_' + VER if VER else ''
OUT = os.path.join(EVAL, 'compare' + SUF); os.makedirs(OUT, exist_ok=True)
FONT = os.path.join(HERE, '..', '..', 'AR_Midterm', 'Assets', 'HearingPainting', 'Fonts', 'NotoSansKR-Bold.ttf')
DIST = 150          # 0~1000 좌표에서 이 거리 안이면 같은 위치로 봄
AMBIENT_KEYS = {'rain': ['rain', 'shower', 'drizzle'], 'wind': ['wind', 'breeze', 'gust'], 'sea': ['sea', 'ocean', 'wave', 'surf', 'shore'],
                'crowd': ['crowd', 'murmur', 'chatter', 'city', 'market'], 'music': ['music', 'band', 'concert'], 'quiet': ['quiet', 'room tone', 'silence', 'still'],
                'water': ['river', 'stream', 'water', 'drip'], 'snow': ['snow', 'night']}

claude = json.load(open(os.path.join(EVAL, 'answers_claude', 'answers_claude' + SUF + '.json'), encoding='utf-8'))


def tags(s):
    text = (s.get('sound_en', '') + ' ' + s.get('ground_phrase_en', '')).lower()
    return {k for k, ws in AMBIENT_KEYS.items() if any(w in text for w in ws)}


def words(s):
    text = (s.get('sound_en', '') + ' ' + s.get('ground_phrase_en', '')).lower()
    return set(re.findall(r'[a-z]{4,}', text)) - {'with', 'from', 'over', 'distant', 'sound', 'people', 'person'}


def similar(a, b):
    if a['source_type'] == 'ambient' or b['source_type'] == 'ambient' or not a.get('points') or not b.get('points'):
        return bool(tags(a) & tags(b)) or len(words(a) & words(b)) >= 2
    d = min(math.dist(p, q) for p in a['points'] for q in b['points'])
    return d <= DIST and (len(words(a) & words(b)) >= 1 or bool(tags(a) & tags(b)) or d <= DIST / 2)


def draw(img_path, groups, out_path):
    im = Image.open(img_path).convert('RGB'); im.thumbnail((700, 700)); W, H = im.size
    d = ImageDraw.Draw(im); f = ImageFont.truetype(FONT, 14)
    colors = {'claude': (40, 120, 255), 'gemini': (255, 120, 0)}
    for who, idx, s in groups:
        for p in s.get('points', []):
            x, y = p[0] / 1000 * W, p[1] / 1000 * H
            d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=colors[who], outline=(0, 0, 0), width=2)
            d.text((x + 9, y - 8), f"{'C' if who == 'claude' else 'G'}{idx}", fill=colors[who], font=f, stroke_width=2, stroke_fill=(0, 0, 0))
    im.save(out_path, quality=85)


rows, merged, stats = [], {}, dict(auto=0, only_c=0, only_g=0, grade_diff=0)
for key, ck in claude.items():
    gpath = os.path.join(EVAL, 'answers_gemini' + SUF, key + '.json')
    g = json.load(open(gpath, encoding='utf-8')).get('parsed') if os.path.exists(gpath) else None
    gs = (g or {}).get('sources', [])
    cs = ck['sources']
    # 가장 잘 맞는 짝부터 정한다 (앞에서부터 차례로 짝지으면 엉뚱한 짝에 먼저 묶이는 문제)
    def score(c, x):
        if not similar(c, x):
            return None
        if c.get('points') and x.get('points'):
            d = min(math.dist(p, q) for p in c['points'] for q in x['points'])
        else:
            d = 0
        return d - 100 * len(words(c) & words(x)) - 100 * len(tags(c) & tags(x))
    cand = sorted((sc, i, j) for i, c in enumerate(cs) for j, x in enumerate(gs) if (sc := score(c, x)) is not None)
    ui, uj, pairs = set(), set(), []
    for sc, i, j in cand:
        if i not in ui and j not in uj:
            ui.add(i); uj.add(j); pairs.append((i, j))
    pairs.sort()
    only_c = [i for i in range(len(cs)) if i not in ui]
    only_g = [j for j in range(len(gs)) if j not in uj]
    auto = [(i, j) for i, j in pairs if cs[i]['grade'] == gs[j].get('grade')]
    gdiff = [(i, j) for i, j in pairs if cs[i]['grade'] != gs[j].get('grade')]
    stats['auto'] += len(auto); stats['only_c'] += len(only_c); stats['only_g'] += len(only_g); stats['grade_diff'] += len(gdiff)
    merged[key] = dict(title=ck['title'], confirmed=[dict(cs[i], matched_gemini=gs[j]) for i, j in auto],
                       pending=dict(only_claude=[cs[i] for i in only_c], only_gemini=[gs[j] for j in only_g],
                                    grade_diff=[dict(claude=cs[i], gemini=gs[j]) for i, j in gdiff]))
    img = os.path.join(EVAL, key + '.jpg')
    draw(img, [('claude', i + 1, s) for i, s in enumerate(cs)] + [('gemini', j + 1, s) for j, s in enumerate(gs)], os.path.join(OUT, key + '.jpg'))

    def li(s, who, n):
        return f"<li><b>{who}{n}</b> {html.escape(s.get('label_ko', ''))} <span class=m>[{s.get('source_type')}/{s.get('grade')}] {html.escape(s.get('sound_en', ''))}</span></li>"
    rows.append(f"<h2>{html.escape(key)} — {html.escape(ck['title'])}</h2><div class=row><img src='{key}.jpg'><div>"
                f"<p class=ok>자동 확정 {len(auto)}개: " + ', '.join(html.escape(cs[i]['label_ko']) for i, _ in auto) + "</p>"
                + (f"<h4>등급만 다름 → 판정 (필수/허용)</h4><ul>" + ''.join(li(cs[i], 'C', i + 1) + li(gs[j], 'G', j + 1) for i, j in gdiff) + "</ul>" if gdiff else '')
                + (f"<h4>Claude에만 있음 → 판정 (넣기/빼기)</h4><ul>" + ''.join(li(cs[i], 'C', i + 1) for i in only_c) + "</ul>" if only_c else '')
                + (f"<h4>Gemini에만 있음 → 판정 (넣기/빼기)</h4><ul>" + ''.join(li(gs[j], 'G', j + 1) for j in only_g) + "</ul>" if only_g else '')
                + (f"<p class=bad>Gemini 결과 없음</p>" if g is None else '') + "</div></div>")

page = ("<!doctype html><meta charset=utf-8><title>정답지 비교</title><style>body{font-family:'Malgun Gothic',sans-serif;margin:24px;background:#f6f6f4}"
        ".row{display:flex;gap:16px;align-items:flex-start}.row img{width:560px;border-radius:6px}h2{margin-top:36px;border-bottom:2px solid #333}"
        ".m{color:#666;font-size:12px}.ok{color:#176}.bad{color:#c00}li{margin:3px 0}</style>"
        f"<h1>정답지 비교 — Claude(파랑 C) vs Gemini(주황 G)</h1><p>자동 확정 {stats['auto']} · 등급 다름 {stats['grade_diff']} · Claude에만 {stats['only_c']} · Gemini에만 {stats['only_g']}</p>"
        "<p>판정할 것: 등급 다름(필수/허용), 한쪽에만 있는 소리원(넣기/빼기). 같은 위치인데 다른 이름으로 나뉜 경우도 여기서 합쳐 주세요.</p>" + ''.join(rows))
open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(page)
json.dump(merged, open(os.path.join(OUT, 'merged_auto.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(stats)
