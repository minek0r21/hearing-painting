# VLM 비교 결과 페이지 만들기: python bench_report.py
# bench/results/*/*.json → bench/report/index.html (+ 그림마다 소리원을 찍은 이미지)
import html, json, os, glob
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
IN = os.path.join(HERE, 'bench', 'inputs')
RES = os.path.join(HERE, 'bench', 'results')
OUT = os.path.join(HERE, 'bench', 'report')
os.makedirs(OUT, exist_ok=True)
FONT_PATH = os.path.join(HERE, '..', '..', 'AR_Midterm', 'Assets', 'HearingPainting', 'Fonts', 'NotoSansKR-Bold.ttf')
COLORS = {'nature': (80, 160, 255), 'people': (60, 200, 100), 'animal': (255, 200, 40),
          'vehicle': (255, 140, 40), 'music': (190, 120, 255)}
PAINTINGS = ['hunters', 'rainy_day', 'wave', 'beach', 'boulevard']
NAMES = {'hunters': '브뤼헐, 눈 속의 사냥꾼 (유명)', 'rainy_day': '카유보트, 파리의 거리 비 오는 날 (유명)',
         'wave': '호쿠사이, 가나가와 파도 (유명)', 'beach': '부댕, 트루빌 해변 (덜 알려짐)',
         'boulevard': '베로, 몽마르트르 대로 (덜 알려짐)'}
MODES = {'pick': 'A. 탐지 목록에서 고르기', 'point': 'B. 직접 위치 찍기'}


CRITERIA = [('fit', '① 소리 선택이 장면에 맞음'), ('loc', '② 위치·물체가 맞음'), ('nohal', '③ 지어낸 것 없음'),
            ('ko', '④ 한국어 자연스러움'), ('prompt', '⑤ 프롬프트 구체성')]


def grade_html(key):
    # 결과 카드 하나의 채점 칸: 기준 5개 × 1~5점 + 메모
    rows = []
    for cid, name in CRITERIA:
        btns = ''.join(f'<input type=radio name="{key}|{cid}" id="{key}|{cid}|{v}" value={v}>'
                       f'<label for="{key}|{cid}|{v}">{v}</label>' for v in range(1, 6))
        rows.append(f'<div class=q><span class=l>{name}</span>{btns}</div>')
    return f'<div class=grade>{"".join(rows)}<textarea data-memo="{key}" placeholder="메모 (선택)"></textarea></div>'


# 채점 저장(브라우저 localStorage), 진행률, 모델별 평균, 모델 이름 가리기, JSON 내보내기
GRADE_JS = """<script>
const KEY = 'hp_vlm_scores_v1', MODELS = __MODELS__, CRIT = ['fit', 'loc', 'nohal', 'ko', 'prompt'];
const CNAME = ['소리 선택', '위치', '지어내지 않음', '한국어', '프롬프트'];
let S = JSON.parse(localStorage.getItem(KEY) || '{}');
const alias = m => '모델 ' + 'ABCDEFGH'[MODELS.indexOf(m)];
function save() { localStorage.setItem(KEY, JSON.stringify(S)); refresh(); }
document.querySelectorAll('.grade input[type=radio]').forEach(r => {
  const a = r.name.split('|'), k = a.slice(0, 3).join('|'), c = a[3];
  if (S[k] && S[k][c] == r.value) r.checked = true;
  r.addEventListener('change', () => { (S[k] = S[k] || {})[c] = +r.value; save(); });
});
document.querySelectorAll('.grade textarea').forEach(t => {
  const k = t.dataset.memo; t.value = (S[k] && S[k].memo) || '';
  t.addEventListener('input', () => { (S[k] = S[k] || {}).memo = t.value; save(); });
});
function refresh() {
  const cells = document.querySelectorAll('.cell[data-key]'); let done = 0;
  cells.forEach(c => { const s = S[c.dataset.key] || {}; const ok = CRIT.every(x => s[x]); c.classList.toggle('done', ok); done += ok; });
  document.getElementById('prog').textContent = '완료 ' + done + ' / ' + cells.length;
  const blind = document.getElementById('blind').checked;
  let h = '<tr><th>모델</th><th>채점한 결과</th>' + CNAME.map(n => '<th>' + n + '</th>').join('') + '<th>평균</th></tr>';
  MODELS.forEach(m => {
    const sum = {}, cnt = {}; let n = 0;
    Object.entries(S).forEach(([k, v]) => {
      if (k.split('|')[2] !== m) return; n++;
      CRIT.forEach(c => { if (v[c]) { sum[c] = (sum[c] || 0) + v[c]; cnt[c] = (cnt[c] || 0) + 1; } });
    });
    const avg = CRIT.map(c => cnt[c] ? sum[c] / cnt[c] : null), have = avg.filter(x => x !== null);
    h += '<tr><td><b>' + (blind ? alias(m) : m) + '</b></td><td>' + n + '</td>'
       + avg.map(a => '<td>' + (a === null ? '-' : a.toFixed(2)) + '</td>').join('')
       + '<td><b>' + (have.length ? (have.reduce((a, b) => a + b, 0) / have.length).toFixed(2) : '-') + '</b></td></tr>';
  });
  document.getElementById('avg').innerHTML = h;
  document.querySelectorAll('.mname').forEach(e => { e.textContent = blind ? alias(e.dataset.m) : e.dataset.m; });
  document.querySelectorAll('.cell .run').forEach(e => { e.style.visibility = blind ? 'hidden' : ''; });
}
document.getElementById('blind').addEventListener('change', refresh);
function exportScores() {
  const blob = new Blob([JSON.stringify({ saved: new Date().toISOString(), scores: S }, null, 2)], { type: 'application/json' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'vlm_scores.json'; a.click();
}
function resetScores() { if (confirm('채점을 모두 지울까요?')) { localStorage.removeItem(KEY); location.reload(); } }
refresh();
</script>"""


def font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except OSError:
        return ImageFont.load_default()


def positions(result, det):
    # 소리원마다 (번호, 화면 위치 u,v, 상자) — 위치를 못 구하면 None
    out = []
    for i, s in enumerate((result.get('parsed') or {}).get('sources') or []):
        uv, box = None, None
        if result['mode'] == 'pick':
            d = s.get('detection')
            if isinstance(d, int) and 0 <= d < len(det['detections']):
                dd = det['detections'][d]
                uv, box = (dd['u'], dd['v']), dd['box']
            elif isinstance(s.get('u'), (int, float)) and isinstance(s.get('v'), (int, float)):
                uv = (float(s['u']), float(s['v']))
        else:
            if isinstance(s.get('x'), (int, float)) and isinstance(s.get('y'), (int, float)):
                uv = (s['x'] / 1000, s['y'] / 1000)
        out.append((i + 1, s, uv, box))
    return out


def draw(result, det, path):
    img = Image.open(os.path.join(IN, result['painting'] + '.jpg')).convert('RGB')
    img.thumbnail((900, 900))
    W, H = img.size
    sx, sy = W / det['width'], H / det['height']
    d = ImageDraw.Draw(img)
    f = font(max(14, W // 45))
    for n, s, uv, box in positions(result, det):
        c = COLORS.get(s.get('type'), (255, 255, 255))
        if box:
            d.rectangle([box[0] * sx, box[1] * sy, box[2] * sx, box[3] * sy], outline=c, width=3)
        if uv:
            x, y = uv[0] * W, uv[1] * H
            r = max(9, W // 70)
            d.ellipse([x - r, y - r, x + r, y + r], fill=c, outline=(0, 0, 0), width=2)
            d.text((x, y), str(n), fill=(0, 0, 0), font=font(r + 2), anchor='mm')
            d.text((x + r + 3, y), str(s.get('label_ko', '')), fill=c, font=f, anchor='lm', stroke_width=3, stroke_fill=(0, 0, 0))
    img.save(path, quality=88)


def main():
    models = sorted(os.listdir(RES)) if os.path.isdir(RES) else []
    models = [m for m in models if glob.glob(os.path.join(RES, m, '*.json'))]  # 결과가 없는 모델(실행 실패)은 빼기
    rows, summary = [], {}
    for m in models:
        s = summary.setdefault(m, dict(n=0, json_ok=0, count_ok=0, bad=0, sec=0.0, vram=0.0, model=''))
        for f in glob.glob(os.path.join(RES, m, '*.json')):
            r = json.load(open(f, encoding='utf-8'))
            c = r['checks']
            s['model'] = r['model']
            s['n'] += 1
            s['json_ok'] += int(c.get('json_ok', False))
            s['count_ok'] += int(c.get('count_ok', False))
            s['bad'] += c.get('bad_position', 0) or 0
            s['sec'] += r['seconds']
            s['vram'] = max(s['vram'], r['peak_vram_gb'])

    parts = ['<!doctype html><meta charset="utf-8"><title>들리는 그림 — VLM 비교</title><style>',
             'body{font-family:"Malgun Gothic",sans-serif;margin:24px;background:#f6f6f4;color:#222}',
             'h1{font-size:22px}h2{margin-top:40px;border-bottom:2px solid #333;padding-bottom:4px}h3{margin:24px 0 8px}',
             '.row{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:14px}',
             '.cell{background:#fff;border:1px solid #ddd;border-radius:8px;padding:10px}',
             '.cell img{width:100%;border-radius:4px}.cell h4{margin:4px 0 6px;font-size:15px}',
             'table{border-collapse:collapse;font-size:13px;width:100%}td,th{border:1px solid #ddd;padding:3px 6px;vertical-align:top;text-align:left}',
             'th{background:#eee}.meta{font-size:12px;color:#555;margin:4px 0}.bad{color:#c00;font-weight:bold}',
             '.score{margin-top:6px;font-size:13px;background:#fffbe6;padding:6px;border-radius:4px}',
             'details{font-size:12px}pre{white-space:pre-wrap;font-size:11px}',
             '.grade{margin-top:8px;background:#fffbe6;border:1px solid #eedc8a;border-radius:6px;padding:8px;font-size:13px}',
             '.grade .q{display:flex;align-items:center;gap:6px;margin:3px 0}.grade .q span.l{width:150px}',
             '.grade label{border:1px solid #bbb;border-radius:4px;padding:1px 8px;cursor:pointer;background:#fff}',
             '.grade input[type=radio]{display:none}.grade input[type=radio]:checked+label{background:#222;color:#fff;border-color:#222}',
             '.grade textarea{width:100%;height:38px;margin-top:4px;font-size:12px}.cell.done{outline:3px solid #2a8}',
             '#bar{position:sticky;top:0;z-index:9;background:#222;color:#fff;padding:8px 12px;border-radius:6px;display:flex;gap:14px;align-items:center;font-size:13px}',
             '#bar button{font-size:13px;padding:3px 10px;cursor:pointer}#avg td,#avg th{text-align:center}</style>',
             '<h1>들리는 그림 — 소리 설계 VLM 비교</h1>',
             '<p>같은 그림·같은 질문·같은 탐지 목록. 생성은 무작위성 없음(greedy). 점 번호 = 소리원 번호, 색 = 종류(파랑 자연, 초록 사람, 노랑 동물, 주황 탈것, 보라 음악). '
             'A는 위치를 Florence 탐지 상자에서 가져옴(상자 테두리 표시), B는 모델이 직접 찍은 점.</p>',
             '<div id=bar><b>채점</b><span id=prog></span><label><input type=checkbox id=blind> 모델 이름 가리기</label>'
             '<button onclick="exportScores()">채점 결과 저장(JSON)</button><button onclick="resetScores()">초기화</button></div>',
             '<p class=meta>각 결과 카드 아래에서 기준마다 1~5점을 고르세요(5가 가장 좋음). 고르는 즉시 이 브라우저에 저장되고, '
             '다 끝나면 "채점 결과 저장"을 눌러 파일(vlm_scores.json)로 내보내세요. VS Code 미리보기가 아니라 브라우저(Chrome, Edge)에서 여세요.</p>',
             '<h2>채점 평균 (직접 평가, 실시간)</h2><table id=avg></table>',
             '<h2>요약 (자동 검사)</h2><table><tr><th>모델</th><th>실행 수</th><th>JSON 성공</th><th>소리원 4~6개</th><th>잘못된 위치 수</th><th>평균 시간(초)</th><th>최대 VRAM(GB)</th></tr>']
    for m, s in summary.items():
        if s['n']:
            parts.append(f"<tr><td><b>{m}</b><br><span class=meta>{s['model']}</span></td><td>{s['n']}</td><td>{s['json_ok']}/{s['n']}</td>"
                         f"<td>{s['count_ok']}/{s['n']}</td><td>{s['bad']}</td><td>{s['sec'] / s['n']:.1f}</td><td>{s['vram']:.1f}</td></tr>")
    parts.append('</table>')

    for p in PAINTINGS:
        det_path = os.path.join(IN, p + '.json')
        if not os.path.exists(det_path):
            continue
        det = json.load(open(det_path, encoding='utf-8'))
        parts.append(f'<h2>{html.escape(NAMES[p])}</h2>')
        for mode, mode_name in MODES.items():
            parts.append(f'<h3>{mode_name}</h3><div class=row>')
            for m in models:
                f = os.path.join(RES, m, f'{p}_{mode}.json')
                if not os.path.exists(f):
                    continue
                r = json.load(open(f, encoding='utf-8'))
                img_name = f'{p}_{mode}_{m}.jpg'
                draw(r, det, os.path.join(OUT, img_name))
                c = r['checks']
                title = (r.get('parsed') or {}).get('title_guess', '')
                parts.append(f'<div class=cell data-key="{p}|{mode}|{m}"><h4 class=mname data-m="{m}">{m}</h4><img src="{img_name}">')
                parts.append(f"<div class='meta run'>{r['seconds']}초 · VRAM {r['peak_vram_gb']}GB · 제목 추정: {html.escape(str(title)) or '-'}"
                             + (f" · <span class=bad>JSON 실패</span>" if not c.get('json_ok') else '')
                             + (f" · <span class=bad>잘못된 위치 {c.get('bad_position')}</span>" if c.get('bad_position') else '')
                             + (f" · <span class=bad>오류 {html.escape(r['error'])}</span>" if r.get('error') else '') + '</div>')
                parts.append('<table><tr><th>#</th><th>이름</th><th>위치</th><th>설명 / 프롬프트</th></tr>')
                for n, s, uv, box in positions(r, det):
                    if mode == 'pick':
                        d = s.get('detection')
                        where = f"#{d} {html.escape(det['detections'][d]['label'])}" if box else ('장면 전체' if uv else '<span class=bad>없음</span>')
                    else:
                        where = html.escape(str(s.get('object_en', ''))) if uv else '<span class=bad>없음</span>'
                    parts.append(f"<tr><td>{n}</td><td>{html.escape(str(s.get('label_ko', '')))}<br><span class=meta>{html.escape(str(s.get('type', '')))}</span></td>"
                                 f"<td>{where}</td><td>{html.escape(str(s.get('description_ko', '')))}<br><span class=meta>{html.escape(str(s.get('prompt_en', '')))}</span></td></tr>")
                parts.append('</table>')
                parts.append(f"<details><summary>모델 원문</summary><pre>{html.escape(r['raw'])}</pre></details>")
                parts.append(grade_html(f'{p}|{mode}|{m}') + '</div>')
            parts.append('</div>')
        dl = '<br>'.join(f"#{d['index']} {html.escape(d['label'])} (u={d['u']}, v={d['v']}, 깊이 {d['depth']})" for d in det['detections'])
        parts.append(f'<details><summary>이 그림의 Florence 탐지 목록 ({len(det["detections"])}개)과 설명문</summary><p class=meta>{html.escape(det["caption"])}</p><p class=meta>{dl}</p></details>')

    parts.append(GRADE_JS.replace('__MODELS__', json.dumps(models)))
    open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write('\n'.join(parts))
    print('보고서:', os.path.join(OUT, 'index.html'))


if __name__ == '__main__':
    main()
