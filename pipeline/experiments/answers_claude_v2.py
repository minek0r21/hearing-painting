# Claude 정답지 1차 → 2차 (G44~G47 규칙 적용: 미세음 제외, 같은 물체 1개, 필수≤5·허용≤3)
# 규칙에 따른 삭제·병합만 한다 (Gemini 1차 결과에서 본 항목은 추가하지 않음)
import json, os, sys
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, '..', 'paintings', 'evalset', 'answers_claude')
a = json.load(open(os.path.join(D, 'answers_claude.json'), encoding='utf-8'))

REMOVE = {  # (그림, 라벨): 이유
    ('02_rainy_day', '두 사람의 대화'): '같은 사람들(발소리 무리)과 중복',
    ('03_wave', '뱃사람들의 외침'): '배와 같은 물체 → 배 소리원에 병합',
    ('05_boulevard', '신문 넘기는 소리'): '미세음',
    ('06_ssireum', '부채 부치는 소리'): '미세음',
    ('07_seodang', '책장 넘기는 소리'): '미세음',
    ('12_kambara', '지팡이 짚는 소리'): '미세음',
    ('12_kambara', '우산에 쌓이는 눈'): '미세음',
    ('14_tage', '농부들의 웃음'): '같은 무리 → 병합',
    ('17_rainsteam', '기차 기적'): '기관차와 같은 물체 → 병합',
    ('18_milkmaid', '고요한 부엌'): '무음(소리원 아님)',
    ('19_peasantwedding', '아이가 먹는 소리'): '미세음',
    ('20_pearl', '고요한 실내'): '무음(소리원 아님)',
    ('22_liverpool', '가게 앞 사람들 소리'): '같은 종류(보행자 무리)와 중복',
    ('23_tuileries', '부채와 철제 의자 소리'): '미세음',
    ('26_ironmill', '쇳물 지글거림과 불꽃'): '달군 쇠와 같은 물체 → 병합',
    ('26_ironmill', '구석에서 식사하는 소리'): '미세음',
    ('28_railwaystation', '작별 인사와 아이 소리'): '같은 무리(역 군중)와 중복',
    ('30_stilllife', '고요한 실내'): '무음(소리원 아님)',
}
MERGE = [  # (그림, 남길 라벨, 합칠 라벨, 새 라벨, 새 영어)
    ('05_boulevard', '거리 사람들의 대화', '보도 발소리', '거리 사람들의 대화와 발소리', 'crowd chatter and footsteps on a busy boulevard'),
    ('16_horsefair', '말발굽 소리', '말 울음과 콧김', '말발굽과 말 울음', 'many horses pounding hooves, neighing and snorting'),
    ('21_snapwhip', '아이들의 함성과 웃음', '풀밭을 달리는 맨발 소리', '아이들 함성과 달리는 발소리', 'boys shouting and laughing, bare feet running on grass'),
    ('25_bargehaulers', '인부들의 힘겨운 숨과 신음', '모래 밟는 무거운 발소리', '인부들의 신음과 무거운 발소리', 'barge haulers groaning, heavy feet dragging on sand'),
]
RENAME = {
    ('03_wave', '배 삐걱임과 노 젓는 소리'): ('배 삐걱임과 뱃사람 외침', 'wooden boats creaking, oars splashing, rowers shouting'),
    ('14_tage', '농부들의 노래와 발 구르기'): ('농부들의 노래·웃음과 발 구르기', 'peasants singing, laughing and stamping feet'),
    ('17_rainsteam', '증기기관차 소리'): ('증기기관차 소리와 기적', 'steam locomotive chugging and whistle'),
    ('26_ironmill', '달군 쇠를 끄는 금속 소리'): ('달군 쇠를 끄는 금속 소리와 지글거림', 'glowing iron dragged with tongs, clanging and hissing'),
}

log = []
for (k, lab), why in REMOVE.items():
    before = len(a[k]['sources'])
    a[k]['sources'] = [s for s in a[k]['sources'] if s['label_ko'] != lab]
    assert len(a[k]['sources']) == before - 1, (k, lab)
    log.append(f'삭제 {k} "{lab}" — {why}')
for k, keep, other, newlab, newen in MERGE:
    src = a[k]['sources']
    ks = next(s for s in src if s['label_ko'] == keep); os_ = next(s for s in src if s['label_ko'] == other)
    ks['points'] = ks['points'] + [p for p in os_['points'] if p not in ks['points']]
    ks['label_ko'], ks['sound_en'] = newlab, newen
    src.remove(os_)
    log.append(f'병합 {k} "{keep}" + "{other}" → "{newlab}"')
for (k, lab), (newlab, newen) in RENAME.items():
    s = next(s for s in a[k]['sources'] if s['label_ko'] == lab)
    s['label_ko'], s['sound_en'] = newlab, newen
    log.append(f'이름 {k} "{lab}" → "{newlab}"')

# 규칙 검사: 필수≤5, 허용≤3
for k, v in a.items():
    r = sum(s['grade'] == 'required' for s in v['sources']); al = sum(s['grade'] == 'allowed' for s in v['sources'])
    assert r <= 5 and al <= 3, (k, r, al)
    for s in v['sources']:
        s['by'] = 'claude-v2'

json.dump(a, open(os.path.join(D, 'answers_claude_v2.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
open(os.path.join(D, 'v2_changes.txt'), 'w', encoding='utf-8').write('\n'.join(log))
req = sum(s['grade'] == 'required' for v in a.values() for s in v['sources']); alw = sum(s['grade'] == 'allowed' for v in a.values() for s in v['sources'])
print('\n'.join(log)); print(f'v2: 필수 {req}, 허용 {alw}, 평균 {round((req + alw) / 30, 1)}개/그림')
