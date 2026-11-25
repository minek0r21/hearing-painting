# v3 일반화 확인용 새 그림(평가셋 밖, 화풍별 1장) 받기 — 위키미디어 공용, 퍼블릭 도메인만 (결정사항 6-1, Q7)
#   python newset_fetch.py → 03_제작/paintings/newset/<번호_이름>.jpg, newset.json, _contact_sheet.jpg
import io, json, os, subprocess, sys, time
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
OUT = os.path.join(ROOT, '03_제작', 'paintings', 'newset')
os.makedirs(OUT, exist_ok=True)
FONT = os.path.join(ROOT, 'AR_Midterm', 'Assets', 'HearingPainting', 'Fonts', 'NotoSansKR-Bold.ttf')
UA = 'HearingPaintingStudentProject/1.0 (educational use)'

LIST = [  # 번호, 이름, 제목, 작가, 화풍, 검색어
    (1, 'nightwatch', '야경', '렘브란트', '바로크', 'Rembrandt The Night Watch Rijksmuseum'),
    (2, 'liberty', '민중을 이끄는 자유의 여신', '들라크루아', '낭만주의', 'Delacroix Liberty Leading the People Louvre'),
    (3, 'gleaners', '이삭 줍는 여인들', '밀레', '사실주의', 'Jean-François Millet Gleaners Google Art Project'),
    (4, 'saintlazare', '생라자르 역', '모네', '인상주의', 'Monet La Gare Saint-Lazare 1877 Orsay'),
    (5, 'swing', '그네', '프라고나르', '로코코', 'Fragonard The Swing Wallace Collection'),
    (6, 'cafeterrace', '밤의 카페 테라스', '반 고흐', '후기인상주의', 'Van Gogh Cafe Terrace at Night Kroller-Muller'),
    (7, 'scream', '절규', '뭉크', '표현주의', 'Edvard Munch The Scream 1893 National Gallery Oslo'),
    (8, 'pajeokdo', '파적도', '김득신', '조선 풍속화', 'Kim Deuk-sin Pajeokdo'),
    (9, 'ejiri', '스루가의 에지리', '호쿠사이', '우키요에', 'Hokusai Ejiri in Suruga Province Thirty-six Views'),
]


def get(url, params=None):
    cmd = ['curl', '-s', '-L', '-A', UA, '--max-time', '120']
    if params:
        cmd += ['-G'] + sum([['--data-urlencode', f'{k}={v}'] for k, v in params.items()], [])
    return subprocess.run(cmd + [url], capture_output=True, check=True).stdout


def commons_search(q):
    r = json.loads(get('https://commons.wikimedia.org/w/api.php', params={
        'action': 'query', 'generator': 'search', 'gsrsearch': q + ' filetype:bitmap', 'gsrnamespace': 6, 'gsrlimit': 8,
        'prop': 'imageinfo', 'iiprop': 'url|size|extmetadata', 'iiurlwidth': 1600,
        'iiextmetadatafilter': 'LicenseShortName', 'format': 'json'}))
    pages = sorted(r.get('query', {}).get('pages', {}).values(), key=lambda p: p.get('index', 99))
    for p in pages:
        ii = p['imageinfo'][0]
        lic = ii.get('extmetadata', {}).get('LicenseShortName', {}).get('value', '')
        if 'public domain' in lic.lower() and ii['width'] >= 800 and ii['height'] >= 500:
            return p['title'], ii.get('thumburl') or ii['url'], lic
    return None


meta = []
for n, slug, title, artist, style, q in LIST:
    path = os.path.join(OUT, f'{n:02d}_{slug}.jpg')
    try:
        if os.path.exists(path):
            print(f'{n:02d} {slug}: 이미 받음'); meta.append(dict(n=n, slug=slug, title=title, artist=artist, style=style, file=os.path.basename(path))); continue
        found = None
        for attempt in range(4):
            try:
                time.sleep(4); found = commons_search(q); break
            except json.JSONDecodeError:
                time.sleep(30 * (attempt + 1))
        if not found:
            print(f'{n:02d} {slug}: 찾지 못함'); continue
        time.sleep(3)
        im = Image.open(io.BytesIO(get(found[1]))).convert('RGB'); im.thumbnail((1600, 1600)); im.save(path, quality=92)
        meta.append(dict(n=n, slug=slug, title=title, artist=artist, style=style, file=os.path.basename(path), commons=found[0], license=found[2]))
        print(f'{n:02d} {slug:12s} {found[0][:90]}')
    except Exception as e:
        print(f'{n:02d} {slug}: 오류 {type(e).__name__} {e}')
json.dump(meta, open(os.path.join(OUT, 'newset.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

cw, ch = 320, 260
sheet = Image.new('RGB', (3 * cw, 3 * (ch + 30)), (245, 242, 236)); d = ImageDraw.Draw(sheet); f = ImageFont.truetype(FONT, 15)
for i, m in enumerate(meta):
    x, y = (i % 3) * cw, (i // 3) * (ch + 30)
    im = Image.open(os.path.join(OUT, m['file'])); im.thumbnail((cw - 10, ch - 10)); sheet.paste(im, (x + 5, y + 5))
    d.text((x + 5, y + ch + 4), f"{m['n']}. {m['title']} ({m['style']})", fill=(20, 20, 20), font=f)
sheet.save(os.path.join(OUT, '_contact_sheet.jpg'), quality=85)
print('done', len(meta), '/', len(LIST))
