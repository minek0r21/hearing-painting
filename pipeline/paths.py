# 폴더 위치를 한곳에서 정한다. 작업 폴더 구조와 GitHub 저장소 구조를 모두 지원:
#   저장소:     hearing-painting/pipeline (여기) · ../unity · ../paintings · ../eval
#   작업 폴더:  Unity_System/03_제작/local_ai (여기) · ../../AR_Midterm · ../paintings · ./bench
# 환경 변수 HP_UNITY로 Unity 프로젝트 폴더를 직접 지정할 수 있다.
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _first_dir(*cands):
    for c in cands:
        if c and os.path.isdir(c):
            return os.path.normpath(c)
    return os.path.normpath(cands[-1])


UNITY = _first_dir(os.environ.get('HP_UNITY', ''), os.path.join(HERE, '..', 'unity'), os.path.join(HERE, '..', '..', 'AR_Midterm'))
UNITY_RES = os.path.join(UNITY, 'Assets', 'Resources', 'HearingPainting')
REF_DIR = os.path.join(UNITY, 'Assets', 'HearingPainting', 'ReferenceImages')
FONT = os.path.join(UNITY, 'Assets', 'HearingPainting', 'Fonts', 'NotoSansKR-Bold.ttf')
PAINTINGS = os.path.normpath(os.path.join(HERE, '..', 'paintings'))
BENCH = _first_dir(os.path.join(HERE, '..', 'eval'), os.path.join(HERE, 'bench'))   # 평가 결과


def load_env():
    # .env(HF_TOKEN, GEMINI_API_KEY)를 환경 변수로. 파일이 없어도 됨 (Gemini 답지 없이 진행)
    path = os.path.join(HERE, '.env')
    if not os.path.exists(path):
        return
    for line in open(path, encoding='utf-8-sig'):
        if '=' in line and not line.lstrip().startswith('#'):
            k, v = line.strip().split('=', 1)
            if v.strip() and not os.environ.get(k.strip()):
                os.environ[k.strip()] = v.strip().strip('"').strip("'")
