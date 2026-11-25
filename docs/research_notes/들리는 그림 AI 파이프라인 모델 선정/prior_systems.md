# 선행 시스템 조사: 이미지/그림 → 공간(3D) 오디오 (2026년 11월 기준)

> 범위: 연구 파이프라인(이미지→공간 오디오), 그림 소니피케이션 연구, 미술관/상업 제품. "들리는 그림"(Unity AR Foundation + ARCore, Galaxy S23; Florence-2 → Depth Anything V2 → 사람이 쓰는 사운드 디자인(향후 로컬 VLM) → Stable Audio Open)과의 비교가 목적.
> 표기: [구] = 2024년 이전 자료.

## 1. 연구 파이프라인: 검출/분할, 깊이, 사운드 디자인(LLM/VLM), 생성, 평가는 어떻게 짜여 있나?

### Takeaway
주류는 "학습 없는(training-free) 조합형 파이프라인"이다: (분할/그라운딩) → (단안 깊이) → (소스별 모노 오디오 생성) → (거리 감쇠·방향 기반 공간 렌더링). 2024년 SEE-2-SOUND에는 VLM이 없었고, 2026년 SonoWorld(CVPR 2026)는 VLM이 "어떤 소리가 나는가 + 소스 유형(점/군집/앰비언트) + 텍스트 프롬프트 + 음량"을 정하는 단계를 추가했다. 이 구조는 "들리는 그림"의 계획(로컬 VLM으로 사운드 디자인 자동화)과 거의 같다.

### Cited Findings
**SEE-2-SOUND (Univ. of Toronto, arXiv 2406.06612, 2024년 6월 v1 → 2025년 7월 개정, SIGGRAPH Posters 2025)**
- 학습 없는 조합형 파이프라인 4단계: ① 관심 영역 식별 ② 3D 위치 추정 ③ 소스별 모노 오디오 생성 ④ 공간 오디오로 통합. 이미지, GIF, 비디오를 입력으로 받는다 — [arXiv abs](https://arxiv.org/abs/2406.06612v2), [HF papers](https://huggingface.co/papers/2406.06612)
- 분할은 SAM(ViT-H)이며, 마스크를 바운딩 박스로 근사하는 쪽이 공간 오디오에서 "대체로 더 낫다"고 한다. 깊이는 Depth Anything(ViT-L/14)이고, (x, y, 깊이)로 3D 좌표를 잡는다(명시적 수식은 없음) — [arXiv html v2](https://arxiv.org/html/2406.06612v2)
- 오디오는 CoDi가 이미지 패치마다 생성한다(텍스트 프롬프트는 선택, 500 diffusion steps). LLM/VLM/캡션 단계는 없고, 사용자 연구도 텍스트 프롬프트 없이 진행했다 — [arXiv html v2](https://arxiv.org/html/2406.06612v2)
- 렌더링은 pyroomacoustics ShoeBox로 하되 직접음만 쓴다(반사·RIR 없음). 거리/음속으로 지연, 거리 감쇠를 적용하고 5.1채널(ITU-R BS.775), 16 kHz로 출력한다 — [arXiv html v2](https://arxiv.org/html/2406.06612v2)
- 평가
  - AViTAR(Visual Acoustic Matching) 보정 출력과의 유사도: MFCC-DTW, ZCR, chroma, spectral contrast
  - COCO 1,000장 CLIP score: 0.0259, 비교 대상 Wav2CLIP 0.0247, Im2Wav 0.0108
  - 헤드폰 사용자 연구 43명: 사실감·몰입·정확도, 방향/거리 식별, 진짜/가짜 구분, 이미지-오디오 매칭(카이제곱 검정)
  - [arXiv html v2](https://arxiv.org/html/2406.06612v2)
- 저자가 밝힌 한계는 세부 묘사 누락, 정지 이미지라서 움직임 단서가 없음, A100에서도 실시간이 아님 — [arXiv html v2](https://arxiv.org/html/2406.06612v2)

**SonoWorld (Univ. of Maryland, arXiv 2603.28757, 2026년 3월, CVPR 2026) — 단일 이미지 → 3D 시청각 장면**
- 과제 "Image2AVScene"을 정의했다: 단일 RGB 이미지에서 탐색 가능한 3D 장면과 공간 음장을 만든다. 학습 없는 프레임워크이다 — [arXiv html](https://arxiv.org/html/2603.28757), [프로젝트](https://humathe.github.io/sonoworld/)
- 단계
  1. GeoCalib으로 카메라를 보정하고, 360° 파노라마로 아웃페인팅한 뒤 3D Gaussian Splatting으로 만든다(Marble 또는 HunyuanWorld-1.0).
  2. **VLM(GPT-5 또는 LLaVA-Next-34B)이 소리 나는 범주, 소스 유형(point/clustered/ambient), 오디오 텍스트 프롬프트, 음량 파라미터를 제안**한다.
  3. X-Decoder(open-vocab) 결과와 SAM2 마스크를 투표로 병합하고, 파노라마 깊이로 3D에 역투영한다.
  4. 소스별 오디오와 전역 앰비언트를 MMAudio로 생성하고, VLM이 추정한 에너지로 스케일한다.
  5. 앰비소닉스로 인코딩한다(점 소스는 인스턴스 중심, 군집 소스는 확산 음장, 앰비언트는 전방위). 거리 감쇠와 공기 흡수를 넣는다.
  6. HRTF로 바이노럴 디코딩해 자유 시점으로 렌더링한다.
  - [arXiv html](https://arxiv.org/html/2603.28757)
- 평가
  - 360° 카메라 + FOA 마이크로 녹음한 SonoScene360(6개 장면, 68클립)을 썼다.
  - 지표: 방위각/고도 오차, 측지 각도 오차, 구면 에너지맵 CC/AUC, 방향별 CLAP(D-CLAP), 방향 R-Precision. 50명 쌍대 비교 사용자 연구도 했다.
  - 보고된 수치: 베이스라인(SEE-2-SOUND, ViSAGe, OmniAudio, MMAudio) 대비 DoA 오차 약 47% 감소.
  - [arXiv html](https://arxiv.org/html/2603.28757)
- 한계는 정지 이미지라서 움직이는 소스(사이렌 차량)에 실패한다는 점이다. 최고 성능은 독점 모델(GPT-5, Marble)에 의존하고, 오픈소스 구성은 점수가 더 낮다 — [arXiv html](https://arxiv.org/html/2603.28757)

**기타 관련 파이프라인**
- "Soundscape Generation for Panorama"(Jiayu Lin, 프로젝트 페이지, ©2026)
  - 구성: VLM(InternVL2.5-MPO)이 소리 소스 후보를 낸다 → Grounding DINO로 박스를 잡는다 → DepthFM으로 박스 내 깊이를 읽어 거리를 구한다 → TangoFlux(text-to-audio)로 생성한다 → 역제곱 법칙으로 음량을 정해 상위 m개를 믹스한다.
  - 평가는 없다 — [프로젝트 페이지](https://barasakar.github.io/projects/project5)
- Liu, Gurelli, Wang, Reiss(arXiv 2502.07538, 2025년 2월): YOLOv8 얼굴 검출 + 단안 깊이 + 공간 오디오 기법으로 모노 음성을 바이노럴로 변환한다. 바이노럴 학습 데이터가 필요 없고, 영화·게임 사운드 디자이너의 수작업을 줄이는 것이 목적이다 — [arXiv abs](https://arxiv.org/abs/2502.07538v1)
- 종단간(end-to-end) 학습형 계열
  - SpatialSonic / BEWO-1M(ICLR 2025): 언어·이미지 조건 1단계 확산 모델로, "생성 모델 + 시뮬레이터 캐스케이드"를 대체한다 — [arXiv](https://arxiv.org/pdf/2410.10676)
  - OmniAudio(ICML 2025): 360° 비디오 → FOA, Sphere360 데이터셋 사용 — [arXiv](https://arxiv.org/html/2504.14906v3), [프로젝트](https://omniaudio-360v2sa.github.io)
  - SpatialV2A(2026년 1월): 비디오 → 바이노럴 — [arXiv](https://arxiv.org/html/2601.15017v1)
- Physics-Aware NVAS(arXiv 2601.19712, 2026년 1월): VLM(Chat-UniVi)이 물체·재질을 서술하고, Depth Anything V2로 방 크기를 추정해 바이노럴 음향을 합성한다. 사운드스케이프보다는 실내 음향 쪽 연구이다 — [arXiv](https://arxiv.org/html/2601.19712)

### Inferences
- "들리는 그림"의 오프라인 파이프라인(Florence-2 → Depth Anything V2 → 사운드 디자인 → Stable Audio Open)은 SEE-2-SOUND/SonoWorld형 조합 구조와 같은 계열이다. 학술적으로 타당한 설계라고 주장할 근거가 된다.
- 구조 아이디어
  - (a) SonoWorld처럼 VLM 출력 스키마를 `{label, source_type: point|area|ambient, prompt, loudness}`로 정의한다. 앰비언트(바람·군중 등)는 위치 없이 전방위로 깔고, 점 소스만 깊이에 배치한다.
  - (b) SEE-2-SOUND의 "마스크보다 박스가 낫다"는 관찰은 Florence-2 박스 + 박스 내 깊이 중앙값 방식을 정당화해 준다.
  - (c) 파노라마 프로젝트처럼 VLM이 후보를 내고 그라운딩 모델(Florence-2의 phrase grounding)이 위치를 잡는 "VLM 먼저 → 그라운딩" 순서도 고려할 수 있다.
  - (d) 음량을 VLM이 추정하는 방식(SonoWorld)과 거리 감쇠만 쓰는 방식(SEE-2-SOUND)을 비교해 볼 수 있다.
- 평가 아이디어(수업 규모에 맞게): CLAP 점수(이미지 캡션/VLM 프롬프트 ↔ 생성 오디오), 방향/거리 식별 과제(소수 참가자), 사실감·몰입 Likert. 이는 SEE-2-SOUND와 SonoWorld의 평가를 축소한 형태이다.
- 기존 연구는 모두 "사진/실사 장면"이 대상이고 결과물이 오디오 파일이나 VR 렌더링이다. 그림(회화)을 대상으로 한 것도, 폰 AR에서 실물 위에 소스를 시각화한 것도 확인하지 못했다.

### Gaps
- "Listening2Painting"이라는 이름의 논문/프로젝트는 찾지 못했다(이름이 다르거나 존재하지 않을 수 있음).
- Visual Acoustic Matching(AViTAR) 원 논문은 직접 확인하지 않았다(SEE-2-SOUND의 평가 기준으로만 인용).
- Nokia Bell Labs 페이지는 403으로 원문 확인이 불가했다(아래 3절에 검색 요약만 기록).
- SonoWorld 본문의 후반부(약 6만 자)는 읽지 않았다.

## 2. 그림 소니피케이션 연구와 미술관/상업 제품: 자동(AI)이면서 공간적인 것이 있나?

### Takeaway
그림 소니피케이션 연구는 대부분 **비공간(스테레오/모노) 음악 생성**이고, 접근성(시각장애) 목적이 많다. 미술관/상업 사례는 **사람이 작곡·녹음한 콘텐츠**가 주류이다(Dolby Atmos 앨범, Crossroads AR의 AR 공간 음악, Thyssen 음악 투어). "AI 자동 생성 + 그림 속 깊이 기반 공간 배치 + 폰 AR"을 모두 갖춘 제품은 찾지 못했다.

### Cited Findings
**연구**
- Krol et al.(Monash, arXiv 2405.14188, 2024): 시각장애인을 위한 그림 → 음악 사운드스케이프 연구이다.
  - 구성: InceptionV3로 감정(valence/arousal)을 추정하고 Magenta Music Transformer로 MIDI를 생성한다. YOLOv3(80클래스)로 물체를 검출해 51개 물체 효과음 DB와 매칭한다.
  - **공간 오디오는 구현하지 않았다.** 다만 설계 권고로 "스테레오·리버브로 해석을 돕기"를 제시했다.
  - 연구 1: 파일럿 33명.
  - 연구 2: 맹/저시력 10명 인터뷰. 전원이 미술관에서 제공되면 사용하겠다고 답했다.
  - 우려 사항: 오해석, 효과음 믹싱, 역사적 정확성.
  - [arXiv](https://arxiv.org/html/2405.14188v1)
- 같은 그룹의 ICCC 2024 논문: 오디오 가이드의 "서술적 성격"이 한계라고 보고, 그림의 지각된 감정을 음악으로 전달하려 했다 — [ICCC24 PDF](https://computationalcreativity.net/iccc24/papers/ICCC24_paper_103.pdf)
- Fink & Akdag Salah(2023) "Extending the Visual Arts Experience: Sonifying Paintings with AI"(검색 요약 기준): 색·엣지·saliency·물체/장면 검출 → 생성 음악 모델을 쓴다. 전문가들은 감정·의미 정보 추가를 원했다 — [AMiner](https://www.aminer.org/pub/64663092d68f896efaaa3a86/extending-the-visual-arts-experience-sonifying-paintings-with-ai)
- Virginia Tech(Dam et al., IJHCS 2024, 검색 요약 기준): 그림 8점에 오디오 AR을 적용했다. 주요 색 기반 알고리즘 오디오보다 음악가가 보강한 오디오에서 참여도가 유의하게 높았고, 오디오가 시선을 유도했다 — [VTechWorks](https://vtechworks.lib.vt.edu/items/0047af18-e96c-4485-80b8-26b649eaef11)
- IASDR 2025 포스터(검색 요약 기준): AI로 작품을 분석해 상호작용할수록 복잡해지는 짧은 음악을 생성한다 — [IASDR](https://dl.designresearchsociety.org/iasdr/iasdr2025/posterpapers/70)
- Springer 학회 논문(검색 요약 기준): 가상 전시에서 그림 안에 공간화된 가상 음원을 배치하는 프로토타입이다 — [Springer PDF](https://link.springer.com/content/pdf/10.1007/978-3-031-20302-2_28.pdf)
- [구] Nokia Bell Labs(2019): 웨어러블 visual-inertial odometry로 위치·방향을 추적하고, 갤러리 데모에서 그림 속 장면에 연결된 공간화 사운드를 재생했다. 사운드 저작 방식은 확인하지 못했다(페이지 403, 검색 요약만 확인) — [Nokia Bell Labs](https://www.nokia.com/bell-labs/publications-and-media/publications/audio-augmented-museum-experiences-using-wearable-visual-inertial-odometry)

**제품/캠페인**
- Dolby "Sound of a Masterpiece"(2025년 4월): Dolby와 RNIB가 협업했다. 시각장애 작곡가 Bobby Goulder 등이 모나리자, 모네, 뭉크, 칼로 등 7점을 **Dolby Atmos 앨범**으로 만들었다. **사람이 작곡**했고 AI 언급은 없다. Apple Music/Amazon/Tidal에서 감상하는 음반이며 AR이 아니다 — [Eye News](https://eyenews.uk.com/news/post/dolby-s-sound-of-a-masterpiece-hear-what-da-vincis-mona-lisa-and-monets-water-lily-pond-sound-like)
- Crossroads AR(Earful.be, iOS, 2023년 3월 출시, v2.3.2 2025년 7월): AR 카메라가 특정 화가(Teresa Parod)의 그림을 인식해 "situated spatial music" 앙상블을 재생한다. **사람이 녹음한 바이올린 프레이즈 500여 개**로 만들었고 AI는 언급되지 않는다. 그 화가의 작품에만 동작한다 — [App Store](https://apps.apple.com/us/app/-/id1668210261)
  - **가장 유사한 기존 제품**이다(그림 인식 + 폰 AR + 공간 음악). 차이점은 수작업 작곡이고, 특정 작품 전용이며, 깊이 기반 배치나 소스 시각화가 확인되지 않는다는 점이다.
- Thyssen-Bornemisza
  - "Cuadros Sónicos"(Second Canvas Thyssen 앱): 5점을 대상으로 한 음악 내레이션 투어이다(작곡가 Sonia Megías) — [Time Out](https://www.timeout.es/madrid/es/noticias/lo-nuevo-para-visitar-el-museo-thyssen-es-una-ruta-tematica-musical-y-con-sonido-052720)
  - "Ficción Sonora": 그림 9점에 대한 라디오극 팟캐스트로, QR로 접근한다 — [Fundación Iberdrola](https://www.fundacioniberdrolaespana.org/en/press-room/the-thyssen-bornemisza-museum-and-fundacion-iberdrola-espana-launch-ficcion-sonora)
  - 둘 다 사람이 제작했다.
- National Gallery(런던) "Soundscapes"[구, 2015]: 뮤지션 6명이 그림 6점에 응답하는 음악·사운드 설치를 만들었다(사람이 제작) — [Trend Hunter](https://www.trendhunter.com/trends/museum-exhibition)
- Google Arts & Culture × Centre Pompidou "Play a Kandinsky"[구, 2021, 2022년 개정]: Magenta Transformer와 사운드 아티스트(Antoine Bertin, NSDOS)의 협업이다. 웹에서 그림 영역을 클릭해 소리를 듣는다. **ML을 쓰지만 공간 오디오나 AR은 아니고** Kandinsky 한 점 전용이다 — [Google Arts & Culture](https://artsandculture.google.com/experiment/sgF5ivv105ukhA), [Centre Pompidou](https://www.centrepompidou.fr/en/play-a-kandinsky)
- Qosmo "Imaginary Soundscape"[구, 2017년 NIPS 워크숍 → 2021/2022 업데이트]: CNN/대조학습으로 이미지에 맞는 소리를 **6만여 개 라이브러리에서 검색**한다(생성이 아님). Street View 모드가 있다 — [Qosmo](https://qosmo.jp/en/news/imaginary-soundscape-v2), [NIPS 2017 PDF](https://nips2017creativity.github.io/doc/Imaginary_Soundscape.pdf)
- 미술관 앱 플랫폼
  - Bloomberg Connects: 1,500개 이상 기관이 쓰는 오디오 가이드·길찾기·접근성 플랫폼이다. AR이나 공간 오디오는 확인되지 않았다 — [MCN](https://mcn.edu/community-partner/bloomberg-connects/)
  - Artivive: 작가가 미리 등록한 디지털 레이어(영상/소리)를 AR로 재생하며, 등록된 작품에서만 동작한다 — [App Store](https://apps.apple.com/mt/app/artivive/id1188737494)
  - Smartify: SAAM에서 3개 언어 "AI 보조" 오디오 가이드와 AR 게임을 제공했다. AI는 해설용이며 사운드스케이프 생성은 아니다 — [Smartify 사례](https://smartify.org/partners/case-studies/ar-game-smithsonian-american-art-museum)

### Inferences
- 제품 쪽은 "사람이 만든 콘텐츠를 AR/앱으로 재생"하는 구조이고(Artivive, Crossroads AR, Thyssen), AI는 해설(Smartify)이나 음악 작곡 보조(Play a Kandinsky)에 쓰일 뿐이다.
- 접근성 연구(Krol et al.)가 공간 오디오(스테레오·리버브)를 권고하면서도 구현하지 않았다. 이는 "깊이 기반 3D 배치"를 차별점이자 연구 공백으로 제시할 근거가 된다(정확하지 않을 수 있음: 검색 범위 밖의 사례가 있을 수 있다).

### Gaps
- Second Canvas, Smartify, Artivive의 2026년 최신 기능(AI 사운드 생성 여부)은 공식 발표를 전수 확인하지 못했다.
- Prado의 소리 관련 프로젝트 중 그림 사운드 캠페인은 찾지 못했다. 찾은 것은 ACCIONA/Parreno의 고야 "검은 그림" 시청각 체험 정도이다 — [ACCIONA](https://cultura.acciona.com/projects/la-quinta-del-sordo-museo-del-prado)
- Dolby/Bell Labs 원문 일부는 403으로 2차 출처만 확인했다.

## 3. "들리는 그림"이 채우는 공백은 무엇인가? (사실 기반 차별점)

### Takeaway
조사 범위 안에서 다음 다섯 가지를 **동시에** 갖춘 시스템은 찾지 못했다.
1. 회화가 대상이다.
2. AI가 소리를 자동 생성한다.
3. 그림 속 물체의 깊이에 맞춰 3D로 배치한다.
4. 폰 AR로 실물 그림 위에 음원 위치를 시각화한다(링, 시차 창).
5. 여러 그림 간 상호작용이 있다(드래그, 병합).

다만 개별 요소는 각각 선행 사례가 있으므로, "최초"보다는 "조합과 적용 대상(회화 + 모바일 AR)"을 차별점으로 내세우는 것이 정확하다.

### Cited Findings
- 이미지 → 깊이 기반 공간 오디오 자동 생성은 이미 있다: SEE-2-SOUND(2024~25), SonoWorld(2026). 다만 출력은 5.1/앰비소닉스 오디오나 3DGS 렌더링이고, 실시간이 아니거나(A100에서도 비실시간) 서버급 모델(GPT-5 등)에 의존한다 — [SEE-2-SOUND](https://arxiv.org/html/2406.06612v2), [SonoWorld](https://arxiv.org/html/2603.28757)
- 그림 인식 + 폰 AR + 공간 음악도 이미 있다: Crossroads AR. 단, 사람이 작곡했고 특정 작가 작품 전용이다 — [App Store](https://apps.apple.com/us/app/-/id1668210261)
- 그림 → AI 자동 사운드스케이프도 있다: Krol et al. 2024. 단, 공간 오디오는 미구현이고 권고 사항으로만 남아 있다 — [arXiv](https://arxiv.org/html/2405.14188v1)
- 그림 속 장면에 연결된 공간화 사운드 재생도 있다: Nokia Bell Labs 2019 웨어러블 프로토타입(사운드 저작 방식 미확인) — [Nokia Bell Labs](https://www.nokia.com/bell-labs/publications-and-media/publications/audio-augmented-museum-experiences-using-wearable-visual-inertial-odometry)
- 오디오 AR은 그림 감상 중 시선을 유도하고, 음악가가 보강한 오디오가 알고리즘 오디오보다 참여도가 높다 — [VTechWorks](https://vtechworks.lib.vt.edu/items/0047af18-e96c-4485-80b8-26b649eaef11)

### Inferences
- 발표용 차별점(사실 기반 표현 제안)
  1. **회화 대상 + 깊이 기반 3D 배치**: 사진/실사 대상 연구(SEE-2-SOUND, SonoWorld)의 조합형 파이프라인을 회화에 적용한다.
  2. **AR에서 소리 위치의 시각화(사운드 링)와 시차 3D 창**: 기존 연구의 출력은 오디오 파일이나 VR 렌더링이었다.
  3. **다중 그림 동시 인식과 그림 간 음원 드래그·충돌 병합**: 조사 범위에서 유사 상호작용 사례를 찾지 못했다.
  4. **폰만으로 동작**: 무거운 생성은 오프라인으로 돌리고, 기기에서는 재생과 공간화만 한다. SEE-2-SOUND의 비실시간 한계를 아키텍처로 우회하는 셈이다.
  5. 그림별 수작업 작곡 없이 새 그림을 추가할 수 있는 확장성이 있다(Crossroads AR, Dolby 앨범과 대비). 단, 현재는 사운드 디자인이 사람 손이라 **VLM 자동화가 완료되어야 이 주장이 성립**한다.
- 반드시 인정할 점: "AI 생성 공간 오디오" 자체는 새롭지 않다(SEE-2-SOUND, SonoWorld). 그림 + AR + 공간 음악도 Crossroads AR이 있다. "최초"라는 표현은 피하는 것이 좋다.
- 선행 연구가 지적한 위험(오해석, 역사적 부정확성, 효과음 과밀)은 발표에서 한계와 향후 과제로 언급하면 좋다. 예: VLM 프롬프트에 시대·장소를 넣고, 소스 수에 상한을 둔다 — [Krol et al.](https://arxiv.org/html/2405.14188v1)

### Gaps
- 검색은 영문 위주였다. 한국·중국·일본의 유사 앱이나 학생 프로젝트는 확인하지 못했다.
- 2026년 하반기(7~11월) 신규 논문은 별도로 전수 검색하지 않았다. SonoWorld 이후 후속작이 있을 수 있다.
