# 평가셋 후보 30장 받기 (Wikimedia Commons, 퍼블릭 도메인만) → 03_제작/paintings/evalset/
# 이미 있는 5장(hunters, rainy_day, wave, beach, boulevard)은 복사, 나머지 25장은 검색해서 받음
import io, json, os, shutil, sys, time
import httpx
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
OUT = os.path.join(ROOT, '03_제작', 'paintings', 'evalset')
os.makedirs(OUT, exist_ok=True)
FONT = os.path.join(ROOT, 'AR_Midterm', 'Assets', 'HearingPainting', 'Fonts', 'NotoSansKR-Bold.ttf')
UA = {'User-Agent': 'HearingPaintingStudentProject/1.0 (educational use)'}

# (번호, 파일 이름, 한국어 제목, 작가, 유명도, 지역, 장면, 검색어 또는 기존 파일)
LIST = [
    (1, 'hunters', '눈 속의 사냥꾼', '브뤼헐', '유명', '서양', '시골·눈·동물', 'local:03_제작/paintings/hunters.jpg'),
    (2, 'rainy_day', '파리의 거리, 비 오는 날', '카유보트', '유명', '서양', '도시·비', 'local:AR_Midterm/Assets/HearingPainting/ReferenceImages/rainy_day.jpg'),
    (3, 'wave', '가나가와 앞바다의 거대한 파도', '호쿠사이', '유명', '일본', '바다', 'local:03_제작/paintings/wave.jpg'),
    (4, 'beach', '트루빌 해변', '부댕', '덜', '서양', '바다·군중', 'local:03_제작/paintings/beach.jpg'),
    (5, 'boulevard', '몽마르트르 대로', '베로', '덜', '서양', '도시·군중', 'local:03_제작/paintings/boulevard.jpg'),
    (6, 'ssireum', '씨름', '김홍도', '유명', '한국', '군중·놀이', 'Danwon Ssireum'),
    (7, 'seodang', '서당', '김홍도', '유명', '한국', '실내·아이들', 'Danwon Seodang'),
    (8, 'mudong', '무동', '김홍도', '덜', '한국', '음악·춤', 'Kim Hong-do Mudong dancing boy'),
    (9, 'danopungjeong', '단오풍정', '신윤복', '유명', '한국', '물·여인들', 'Shin Yun-bok Dano'),
    (10, 'inwang', '인왕제색도', '정선', '유명', '한국', '산수·비 갠 뒤', 'Inwang Jesaekdo Jeong Seon'),
    (11, 'shower', '오하시 아타케의 소나기', '히로시게', '유명', '일본', '비·다리', 'Hiroshige Sudden Shower over Shin-Ohashi bridge Atake'),
    (12, 'kambara', '가바라 밤의 눈', '히로시게', '덜', '일본', '눈·밤', 'Hiroshige Kambara night snow'),
    (13, 'qingming', '청명상하도 (부분)', '장택단', '유명', '중국', '도시·강·군중', 'Qingming Festival Zhang Zeduan detail rainbow bridge'),
    (14, 'tage', '답가도', '마원', '덜', '중국', '시골·노래', 'Ma Yuan Dancing and Singing peasants'),
    (15, 'galette', '물랭 드 라 갈레트의 무도회', '르누아르', '유명', '서양', '음악·군중', 'Renoir Bal du moulin de la Galette 1876'),
    (16, 'horsefair', '말 시장', '로자 보뇌르', '유명', '서양', '동물 다수', 'Rosa Bonheur The Horse Fair Metropolitan'),
    (17, 'rainsteam', '비, 증기, 속도', '터너', '유명', '서양', '기차·비', 'Turner Rain Steam and Speed Great Western Railway'),
    (18, 'milkmaid', '우유 따르는 여인', '페르메이르', '유명', '서양', '조용한 실내(함정)', 'Vermeer The Milkmaid Rijksmuseum'),
    (19, 'peasantwedding', '농민의 결혼식', '브뤼헐', '유명', '서양', '잔치·음악', 'Pieter Bruegel the Elder Peasant Wedding Kunsthistorisches'),
    (20, 'pearl', '진주 귀고리를 한 소녀', '페르메이르', '유명', '서양', '초상(함정)', 'Vermeer Girl with a Pearl Earring Mauritshuis'),
    (21, 'snapwhip', '채찍 놀이', '윈슬로 호머', '덜', '서양', '아이들 놀이', 'Winslow Homer Snap the Whip 1872'),
    (22, 'liverpool', '달빛 속 리버풀 부두', '그림쇼', '덜', '서양', '밤·항구·비', 'Atkinson Grimshaw Liverpool Quay by Moonlight'),
    (23, 'tuileries', '튈르리 공원의 음악회', '마네', '덜', '서양', '음악·군중', 'Manet Music in the Tuileries'),
    (24, 'avercamp', '스케이트 타는 사람들이 있는 겨울 풍경', '아베르캄프', '덜', '서양', '얼음·군중', 'Hendrick Avercamp Winter Landscape with Ice Skaters Rijksmuseum'),
    (25, 'bargehaulers', '볼가강의 배 끄는 인부들', '레핀', '덜', '서양', '강·노동', 'Repin Barge Haulers on the Volga'),
    (26, 'ironmill', '철 압연 공장', '멘첼', '덜', '서양', '공장·기계', 'Adolph Menzel Iron Rolling Mill Eisenwalzwerk'),
    (27, 'merryfamily', '즐거운 가족', '얀 스테인', '덜', '서양', '실내·음악', 'Jan Steen The Merry Family Rijksmuseum'),
    (28, 'railwaystation', '기차역', '프리스', '덜', '서양', '역·군중', 'William Powell Frith The Railway Station'),
    (29, 'ninthwave', '아홉 번째 파도', '아이바조프스키', '덜', '서양', '폭풍 바다', 'Aivazovsky The Ninth Wave 1850'),
    (30, 'stilllife', '금박 잔이 있는 정물', '헤다', '덜', '서양', '정물(함정)', 'Willem Claesz Heda Still Life with a Gilt Cup'),
]


import subprocess


class CurlClient:
    # Wikimedia가 파이썬 httpx 요청을 403으로 막아서 curl로 요청한다
    class R:
        def __init__(self, content):
            self.content = content

        def json(self):
            return json.loads(self.content)

    def get(self, url, params=None):
        cmd = ['curl', '-s', '-L', '-A', UA['User-Agent'], '--max-time', '120']
        if params:
            cmd += ['-G'] + sum([['--data-urlencode', f'{k}={v}'] for k, v in params.items()], [])
        return self.R(subprocess.run(cmd + [url], capture_output=True, check=True).stdout)


def commons_search(c, q):
    r = c.get('https://commons.wikimedia.org/w/api.php', params={
        'action': 'query', 'generator': 'search', 'gsrsearch': q + ' filetype:bitmap', 'gsrnamespace': 6, 'gsrlimit': 8,
        'prop': 'imageinfo', 'iiprop': 'url|size|extmetadata', 'iiurlwidth': 1600,
        'iiextmetadatafilter': 'LicenseShortName', 'format': 'json'})
    pages = sorted(r.json().get('query', {}).get('pages', {}).values(), key=lambda p: p.get('index', 99))
    for p in pages:
        ii = p['imageinfo'][0]
        lic = ii.get('extmetadata', {}).get('LicenseShortName', {}).get('value', '')
        if 'public domain' in lic.lower() and ii['width'] >= 800 and ii['height'] >= 500:
            return p['title'], ii.get('thumburl') or ii['url'], lic, (ii['width'], ii['height'])
    return None


meta = []
c = CurlClient()
if True:
    for n, slug, title, artist, fame, region, scene, src in LIST:
        path = os.path.join(OUT, f'{n:02d}_{slug}.jpg')
        try:
            if src.startswith('local:'):
                im = Image.open(os.path.join(ROOT, src[6:])).convert('RGB'); found = ('(기존 파일)', '', 'Public domain', im.size)
            elif os.path.exists(path):
                im = Image.open(path).convert('RGB'); found = ('(이미 받음)', '', 'Public domain', im.size)
            else:
                found = None
                for attempt in range(4):          # 속도 제한에 걸리면 기다렸다 다시
                    try:
                        time.sleep(4)
                        found = commons_search(c, src); break
                    except json.JSONDecodeError:
                        time.sleep(30 * (attempt + 1))
                if not found:
                    print(f'{n:02d} {slug}: 찾지 못함'); meta.append(dict(n=n, slug=slug, title=title, artist=artist, fame=fame, region=region, scene=scene, file=None)); continue
                time.sleep(3); im = Image.open(io.BytesIO(c.get(found[1]).content)).convert('RGB')
            im.thumbnail((1600, 1600)); im.save(path, quality=92)
            meta.append(dict(n=n, slug=slug, title=title, artist=artist, fame=fame, region=region, scene=scene, file=os.path.basename(path), commons=found[0], license=found[2]))
            print(f'{n:02d} {slug:15s} {found[0][:90]}')
        except Exception as e:
            print(f'{n:02d} {slug}: 오류 {type(e).__name__} {e}')
            meta.append(dict(n=n, slug=slug, title=title, artist=artist, fame=fame, region=region, scene=scene, file=None))
json.dump(meta, open(os.path.join(OUT, 'evalset.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# 번호·제목을 붙인 썸네일 한 장
cols, cw, ch = 6, 300, 250
sheet = Image.new('RGB', (cols * cw, 5 * (ch + 50)), (245, 242, 236))
d = ImageDraw.Draw(sheet); f = ImageFont.truetype(FONT, 15)
for i, m in enumerate(meta):
    x, y = (i % cols) * cw, (i // cols) * (ch + 50)
    if m.get('file'):
        im = Image.open(os.path.join(OUT, m['file'])); im.thumbnail((cw - 10, ch - 10)); sheet.paste(im, (x + 5, y + 5))
    d.text((x + 5, y + ch), f"{m['n']}. {m['title']}", fill=(20, 20, 20), font=f)
    d.text((x + 5, y + ch + 20), f"{m['artist']} · {m['fame']} · {m['scene']}", fill=(90, 90, 90), font=f)
sheet.save(os.path.join(OUT, '_contact_sheet.jpg'), quality=85)
print('done', sum(1 for m in meta if m.get('file')), '/ 30')
