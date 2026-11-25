# 오디오 생성 모델 선정 (Text/Image-to-Audio, 앰비언트·효과음 루프) — 2026년 11월 기준

> 조사일: 2026-11-25. 대상 환경: Windows PC, RTX 3060 12GB, PyTorch. 현재 파이프라인: `stabilityai/stable-audio-open-1.0` (diffusers StableAudioPipeline, 100 step, 후보 2개, 크로스페이드 루프, -28 dB RMS 정규화).
> 표기: [NC] = 비상업 라이선스, [SCL] = Stability AI Community License(연매출 $1M 미만 무료 상업 사용), [구버전] = 2025년 이전 정보, [미검증] = 이번 조사에서 1차 출처를 직접 확인하지 못함.

## 1. 후보 모델 목록: 크기, 라이선스, 출시일, VRAM, 속도, 12GB/Windows 실행 가능성, diffusers/transformers 지원

### Takeaway
2026년 상반기에 Stability AI가 **Stable Audio 3** 제품군(Small SFX 0.6B / Small / Medium 오픈 웨이트, [SCL])을 내놓았고, 효과음 벤치마크에서 Stable Audio Open 1.0 대비 FAD·CLAP 모두 크게 앞서며 8 step으로 빠르고 VRAM도 작다(small 약 1.9GB, medium 약 5.5GB). 현재 SAO 1.0을 쓰는 이 프로젝트에 가장 직접적인 업그레이드 후보다. 다만 diffusers 네이티브가 아니라 전용 라이브러리(`stable-audio-3` / `stable-audio-tools`)를 쓰고, 출력이 스테레오이며, Windows 동작은 확인되지 않았다.

### Cited Findings

**Stable Audio 3 (Stability AI, 2026-05)**
- 논문 arXiv:2605.17991, 2026-05-18 제출. small/medium/large 세 가지 변형. small과 medium 웨이트와 학습·추론 파이프라인을 공개 — [arXiv abs](https://arxiv.org/abs/2605.17991)
- DiT 파라미터: small 459M, medium 1.4B, large 2.7B. 오토인코더 SAME-S 108M, SAME-L 852M. 44.1 kHz **스테레오**. 최대 길이 small 2분, medium/large 6분 20초. post-trained 모델은 ping-pong 샘플링으로 **8 step**, 추론 시 CFG 불필요 — [arXiv HTML](https://arxiv.org/html/2605.17991v1)
- 효과음 벤치마크(BBC Sound Effects, 5초 클립), FAD↓ / CLAP↑ / H200 추론시간(s): medium 0.369 / 0.369 / 0.60; large 0.358 / 0.370 / 0.64; **small-sfx 0.395 / 0.351 / 0.41**; **Stable Audio Open 0.501 / 0.263 / 12.30**(100 step); SAO-small 0.500 / 0.277 / 0.24; Woosh Flow 0.580 / 0.277 / 1.92; Woosh DFlow 0.619 / 0.228 / 0.06; TangoFlux 0.760 / 0.179 / 1.90 — [arXiv HTML](https://arxiv.org/html/2605.17991v1) (Stability 자체 평가)
- 최대 VRAM(Table 13): small 1.89 GB(30초)·2.40 GB(120초); medium 5.49 GB(30초)·약 6.5 GB(120초 이상); large 8.01 GB(30초)·약 9.0 GB. 논문 본문은 small은 RTX 3050 같은 보급형, medium은 "RTX 3060, RTX 4060, RTX 4070" 같은 소비자 GPU에서 돌아간다고 서술 — [arXiv HTML(뒷부분)](https://arxiv.org/html/2605.17991v1)
- 제품군 구성: Small SFX(폰·노트북용 효과음), Small(음악), Medium(오픈 웨이트), Large(API 전용·엔터프라이즈) — [Stability AI 발표](https://stability.ai/news-updates/meet-stable-audio-3-the-model-family-built-for-artistic-experimentation-with-open-weight-models)
- HF `stabilityai/stable-audio-3-small-sfx`: "0.6B params"(HF 표기, 텍스트 인코더 등 포함 추정). 라이선스는 Stability AI Community License에 더해 T5Gemma 구성요소에 Gemma Terms of Use가 적용된다. 접근하려면 약관 동의(gated)가 필요하다. 실행은 `stable-audio-3` 라이브러리의 `StableAudioModel.from_pretrained("small-sfx")`와 `model.generate(prompt, duration)`, 또는 `stable-audio-tools`의 `generate_diffusion_cond_inpaint`(steps=8, cfg_scale=1.0, sampler "pingpong")로 한다. 모델 카드에 diffusers 사용법은 없고, 예시 코드 주석은 "Generate stereo audio"다 — [HF 모델 카드](https://huggingface.co/stabilityai/stable-audio-3-small-sfx)
- HF는 Medium을 2B, Small을 0.6B로 표기하지만, 일부 가이드는 Medium 1.6B, Small 459M으로 표기해 파라미터 수가 출처마다 다르다(HF 수치는 전체 파이프라인, 논문 수치는 DiT만 센 것으로 보임) — [HF medium](https://huggingface.co/stabilityai/stable-audio-3-medium); [검색 결과 요약 출처: aivideobootcamp](https://aivideobootcamp.com/blog/stable-audio-3-complete-guide-2026/)
- 학습 데이터: 라이선스를 확보한 AudioSparx 806,284개와 Freesound CC-0/CC-BY/CC-Sampling+ 녹음 — [arXiv HTML](https://arxiv.org/html/2605.17991v1)

**Stable Audio Open 1.0 [구버전, 2024-06] / Stable Audio Open Small [2025-05]**
- SAO 1.0은 1.1B 파라미터이고 최대 47초 생성, 웨이트는 HF 공개 — [Stability AI](https://stability.ai/news-updates/introducing-stable-audio-open); [arXiv 2407.14358](https://arxiv.org/abs/2407.14358v2)
- SAO Small: 341M, Arm과 공동으로 2025-05 공개, Arm CPU 온디바이스 대상, 영어 프롬프트만 지원. 라이선스는 Stability AI Community License — [Stability AI 발표](https://stability.ai/news/stability-ai-and-arm-release-stable-audio-open-small-enabling-real-world-deployment-for-on-device-audio-control); [TechCrunch](https://techcrunch.com/2025/05/14/stability-ai-releases-an-audio-generating-model-that-can-run-on-smartphones); [HF](https://huggingface.co/stabilityai/stable-audio-open-small)

**Woosh (Sony AI, 2026-04) [NC]**
- arXiv:2604.01929(2026-04-02 제출, v3 04-29). 구성: Woosh-AE(221M, 48 kHz, **모노 전용**), Woosh-CLAP, Woosh-Flow(T2A 337M, 약 70 DOPRI5 step), Woosh-DFlow(증류판, 4 step), Woosh-VFlow / DVFlow(V2A 413M). 학습은 5초 청크. 웨이트는 "non-commercial use". 코드는 https://github.com/SonyResearch/Woosh — [arXiv HTML v3](https://arxiv.org/html/2604.01929v3)
- 커뮤니티 HF 미러에 CC-BY-NC 4.0, 출력물 상업 사용 불가로 표기(비공식 미러) — [HF 미러](https://huggingface.co/AEmotionStudio/woosh-models/blob/main/README.md)
- 스튜디오급 라이선스 SFX로 학습한 상위 버전은 비공개(Sony에 문의 필요) — [arXiv v3](https://arxiv.org/html/2604.01929v3)
- VRAM과 Windows 지원: 논문에 명시 없음.

**MOSS-SoundEffect v2.0 (OpenMOSS, 2026-05-26)**
- DiT와 Flow Matching, 약 1.3B, 48 kHz, 중·영 이중언어 효과음, 최대 30초. MOSS-TTS Family 전체는 Apache 2.0으로 표기(이 모델의 개별 라이선스는 확인 필요). v1은 8B(MossTTSDelay) — [GitHub OpenMOSS/MOSS-TTS](https://github.com/OpenMOSS/MOSS-TTS); [HF](https://huggingface.co/OpenMOSS-Team/MOSS-SoundEffect-v2.0)
- VRAM, Windows 지원, AudioCaps 수치: 확인 못 함(Gaps 참조).

**AudioX (ICLR 2026) / AudioX-Turbo (2026-06)**
- AudioX: "Anything-to-Audio" 통합 모델(text/video/image/audio 조건). ICLR 2026 채택 — [arXiv 2503.10522](https://arxiv.org/pdf/2503.10522)
- AudioX-Turbo: arXiv:2606.12555(2026-06-10, v2 07-02). AudioX-Base(MM-DiT)를 distribution matching distillation으로 증류해 **4 step**, 다단계 대비 NFE 약 25배 감소. 조건은 text/video/audio. 코드·데이터는 "will be available"(논문 시점에는 미공개). 웨이트 라이선스 미표기 — [arXiv abs](https://arxiv.org/abs/2606.12555)

**TangoFlux (declare-lab, 2024-12) [NC] [구버전]**
- 최대 30초, 44.1 kHz, 기본 25 step(권장 50). 체크포인트는 "non-commercial research use only"이며 Stable Audio Open 라이선스, WavCaps 라이선스 등도 적용 — [HF 모델 카드](https://huggingface.co/declare-lab/TangoFlux)
- 515~516M — [MeanAudio 논문 표](https://arxiv.org/html/2508.06098v1)

**MeanAudio (2025-08)**
- 120M, Mean Flow 기반 1~25 step. RTX 3090에서 1-step RTF 0.013. 저자는 코드와 웨이트를 "will open-source"라고 서술(공개 여부·라이선스는 저장소 확인 필요) — [arXiv HTML](https://arxiv.org/html/2508.06098v1); 코드 https://github.com/xiquan-li/MeanAudio

**EzAudio / GenAU [구버전]**
- EzAudio-XL 875M, 200 NFE. GenAU-Large-Full 1250M, 200 NFE — [MeanAudio 논문 Table 1](https://arxiv.org/html/2508.06098v1)

**MMAudio (CVPR 2025) [NC 웨이트]**
- 코드 MIT, 체크포인트 **CC-BY-NC 4.0**. 16-bit 추론 시 약 **6GB** VRAM. 기본 8초 생성(학습 길이에서 많이 벗어나면 품질 저하 가능). "We have only tested this on Ubuntu." 단일 이미지 입력은 Gradio에서 **실험적**으로만 지원(이미지를 복제해 비디오로 만드는 방식, 이 용도로 학습되지 않음) — [GitHub MMAudio](https://github.com/hkchengrex/MMAudio)

**HunyuanVideo-Foley (Tencent, 2025-08-28; XL 2025-09-29)**
- XXL은 VRAM 20GB, offload 시 12GB. XL은 16GB, offload 시 8GB. 48 kHz. 입력은 **비디오와 텍스트**(이미지·텍스트 단독 입력은 언급 없음). 라이선스는 LICENSE 파일 참조(상업 조건은 페이지에 없음). 벤치마크 우위 주장은 자체 보고이며, 표에서도 일부 지표(Kling-Audio-Eval CLAP·IS)는 MMAudio가 더 높다 — [GitHub](https://github.com/Tencent-Hunyuan/HunyuanVideo-Foley)

**ThinkSound (2025-06~07) / PrismAudio (2025-11, ICLR 2026)**
- 입력은 video/text/audio이고 이미지 입력은 언급 없음. Windows용 `setup_windows.bat` 제공(2025-07-15). 라이선스 표기가 모순된다: "Apache 2.0"이라고 하면서 같은 섹션에 "research and educational purposes only… Commercial use is NOT permitted"라고 쓰고, 번들된 SAO VAE에는 SCL이 적용된다. 후속작 PrismAudio는 `prismaudio` 브랜치로 2026-03-24 공개(비디오→오디오 CoT-RL) — [GitHub ThinkSound](https://github.com/FunAudioLLM/ThinkSound)

### Inferences
- **12GB에서 돌아갈 것으로 보이는 모델**: Stable Audio 3 small-sfx·medium(논문 VRAM 수치 기준), SAO 1.0(현재 사용 중), SAO Small, Woosh(파라미터 규모상, 수치 미보고), TangoFlux, MeanAudio, MMAudio(약 6GB). HunyuanVideo-Foley는 XL+offload(8GB)여야 가능하고 XXL은 offload해도 12GB로 빠듯하다.
- **Windows 명시 지원**: ThinkSound만 공식 .bat를 확인했다. MMAudio는 Ubuntu에서만 테스트됐다고 명시돼 있다. 나머지는 미확인이지만 대부분 순수 PyTorch라 동작 가능성이 높다(추정이며 정확하지 않을 수 있음). flash-attn 같은 의존성이 있으면 Windows에서 막힐 수 있다.
- **diffusers/transformers 네이티브 지원**: diffusers에는 `StableAudioPipeline`(SAO 1.0), `AudioLDM2Pipeline`, `AudioLDMPipeline`이 있다[미검증: 이번 조사에서 docs를 직접 열지 않음, https://huggingface.co/docs/diffusers/api/pipelines/stable_audio]. Stable Audio 3는 모델 카드상 전용 라이브러리를 쓰므로 현재 diffusers 코드를 재사용하기 어렵고, 파이프라인 교체 작업이 필요하다.
- 과제 맥락(개인·학생 프로젝트, 연매출 $1M 미만)에서는 SCL 모델(SAO 1.0, SAO Small, SA3)을 상업 용도까지 포함해 자유롭게 쓸 수 있다. 반면 TangoFlux·MMAudio·Woosh·ThinkSound는 비상업 전용이다.

### Gaps
- Stable Audio 3의 Windows 동작 여부, diffusers 통합 계획, RTX 3060에서의 실측 생성 시간.
- MOSS-SoundEffect v2.0의 VRAM, 벤치마크, 개별 라이선스(모델 카드 미확인).
- AudioX(원본)의 웨이트 라이선스·VRAM, AudioX-Turbo의 웨이트 공개 여부(2026-11 시점).
- Make-An-Audio 2/3, Kling-Foley, AudioGen(AudioCraft), Tango 2, AudioLDM 2의 최신 라이선스·VRAM은 이번 조사 범위(툴 호출 한도)에서 1차 출처를 확인하지 못했다. 일반적으로 AudioCraft 웨이트는 CC-BY-NC로 알려져 있으나 [미검증]이다.
- SAO Small의 최대 길이(약 11초로 알려짐)는 [미검증]이다.
- 2026 하반기(7~11월) 신규 오픈 모델 전수 조사는 하지 못했다. 검색에서 TinyAudio(arXiv 2609.31525) 같은 이름이 보였으나 내용은 확인하지 않았다.

## 2. 품질 근거: AudioCaps 벤치마크, 인간 평가, 앰비언트·긴 루프 적합성

### Takeaway
여러 독립 표에서 **Stable Audio Open 1.0은 AudioCaps 지표(FAD·KL·CLAP)가 동시대 모델 중 하위권**이다. 이는 학습 데이터(Freesound)와 AudioCaps 분포의 차이 탓도 크다. 효과음 중심 평가(BBC SFX)에서는 Stable Audio 3 계열이 가장 좋고, SAO 1.0 대비 FAD 0.501→0.395(small-sfx), CLAP 0.263→0.351로 개선된다. "품질이 불확실하다"는 현재 관찰과 정합한다.

### Cited Findings
- **AudioCaps Table(MeanAudio 논문, RTX 3090 RTF)**, FAD / FD / KL / IS / CLAP / RTF: AudioLDM-L-Full 4.32 / 29.50 / 1.68 / 8.17 / 0.208 / 2.935; Tango-Full-FT 2.68 / 15.64 / 1.24 / 8.78 / 0.291 / 2.382; EzAudio-XL 3.64 / 14.98 / 1.29 / 11.38 / 0.314 / 1.718; **Stable Audio Open 4.19 / 39.14 / 2.36 / 10.07 / 0.209 / 2.867**; TangoFlux 2.41 / 20.65 / 1.27 / 12.81 / 0.318 / 0.449; GenAU-L 2.07 / 14.58 / 1.36 / 10.43 / 0.300 / 1.612; MeanAudio(25 step) 1.74 / 13.38 / 1.26 / 11.14 / 0.321 / 0.083; MeanAudio(1 step) 1.77 / 15.40 / 1.31 / 9.78 / 0.292 / 0.013 — [arXiv 2508.06098](https://arxiv.org/html/2508.06098v1)
- **Woosh 논문 Table 3**(FD(OpenL3) / KL / CLAP): AudioCaps-Test에서 SAO 150.1 / 4.068 / 0.146, TangoFlux 131.9 / 1.700 / 0.347, Woosh-Flow-Public 109.1 / 1.599 / 0.372, Woosh-DFlow-Public 132.1 / 1.836 / 0.323. 내부 SFX 테스트에서 SAO 341.0 / 2.690 / 0.254, TangoFlux 378.1 / 2.729 / 0.225, Woosh-Flow-Public 282.7 / 2.248 / 0.375 — [arXiv 2604.01929v3](https://arxiv.org/html/2604.01929v3)
  - 주목할 점: **SFX 도메인 테스트에서는 SAO가 TangoFlux보다 낫다**(FD 341 vs 378, CLAP 0.254 vs 0.225). AudioCaps 순위가 실제 효과음 품질 순위와 다를 수 있다.
- **Stable Audio 3 논문 BBC SFX 비교**(앞의 표): small-sfx FAD 0.395 / CLAP 0.351 vs SAO 0.501 / 0.263 vs TangoFlux 0.760 / 0.179 — [arXiv 2605.17991](https://arxiv.org/html/2605.17991v1). 논문에 listening test 결과도 있다고 하지만, 이번에 읽은 부분에서는 수치를 확인하지 못했다.
- 같은 모델(SAO)의 CLAP 점수가 논문마다 다르다(0.209 vs 0.146 vs 0.263). 평가 셋업(CLAP 모델, 길이, 데이터셋)이 달라서이므로 **논문 간 절대 수치는 직접 비교하면 안 된다** — [MeanAudio](https://arxiv.org/html/2508.06098v1); [Woosh](https://arxiv.org/html/2604.01929v3); [SA3](https://arxiv.org/html/2605.17991v1)
- 긴 생성과 관련해, SA3 논문은 "짧은 학습 샘플의 대부분이 루프"이며 20초에서 FAD·CLAP이 떨어진다고 서술한다 — [arXiv 2605.17991](https://arxiv.org/html/2605.17991v1)
- Woosh는 5초 청크로 학습했다. 따라서 10~12초 생성은 학습 길이 밖이다 — [arXiv 2604.01929v3](https://arxiv.org/html/2604.01929v3). MMAudio도 기본 8초이고 길이를 크게 벗어나면 품질 저하 가능성이 명시돼 있다 — [GitHub](https://github.com/hkchengrex/MMAudio)
- HunyuanVideo-Foley는 MovieGen-Audio-Bench MOS-Q 4.14±0.68 등을 자체 보고 — [GitHub](https://github.com/Tencent-Hunyuan/HunyuanVideo-Foley)

### Inferences
- 10~12초 앰비언트 루프라는 요구조건에서는 **학습 길이가 길거나 가변 길이를 지원하는 모델**(SAO 1.0: 47초, SA3: 수 분, TangoFlux: 30초, MOSS v2: 30초)이 유리하다. Woosh(5초)와 MMAudio(8초)는 길이 면에서 불리하다.
- 1순위 실험 후보: **Stable Audio 3 small-sfx**(효과음 특화, 8 step, VRAM 2GB 수준)와 **SA3 medium**(품질 상위, 약 5.5~6.5GB). 8 step이므로 후보 2개에서 4~8개로 늘려 CLAP 점수로 고르는 전략도 시간 내에 가능할 것으로 추정된다(RTX 3060 실측 필요).
- 비상업 허용 시 비교군: TangoFlux(AudioCaps 강함), Woosh-Flow(AudioCaps·SFX 모두 SAO보다 높음, 단 5초 학습).
- 자동 선별 방법: 후보마다 CLAP 텍스트-오디오 유사도를 계산해 최고점을 채택하는 방식이 논문들의 공통 평가 지표와 정합한다(Woosh-CLAP 등 사용 가능, 추론).

### Gaps
- 앰비언트·환경음(바람, 군중, 모닥불) 전용 벤치마크나 인간 평가는 찾지 못했다.
- SA3 listening test의 구체 수치는 이번에 읽은 범위에서 확인하지 못했다.
- AudioLDM 2, Make-An-Audio 2/3, AudioGen의 동일 조건 비교 수치는 확보하지 못했다(위 MeanAudio 표에는 없음).

## 3. Image-to-Audio: 그림(또는 크롭)에서 직접 소리 생성 vs VLM 프롬프트

### Takeaway
2026-11 시점에 **정지 이미지 전용으로 학습된 고품질 오픈 모델은 찾지 못했다**. MMAudio는 단일 프레임을 실험적으로만 지원하고, HunyuanVideo-Foley·ThinkSound·Woosh-VFlow는 비디오 입력 전용이다. 문헌에서는 "이미지 캡션 → T2A" 파이프라인이 Im2Wav 같은 직접 방식과 지표별로 엇갈리거나 더 낫다. 따라서 **VLM 프롬프트 + 강한 T2A 모델 구조를 유지하는 것이 합리적**이다. 회화(비사실적 이미지)는 비디오 학습 분포와도 거리가 멀다.

### Cited Findings
- MMAudio: 단일 이미지는 Gradio에서 실험적으로 지원하며, 이미지를 복제해 비디오로 만든다. "not trained for this" — [GitHub MMAudio](https://github.com/hkchengrex/MMAudio)
- AudioX(ICLR 2026) 이미지→오디오 표에서 Im2Wav와 "Caption2Audio"(이미지 캡션 후 T2A)를 비교한다. Caption2Audio는 IS·FAD가, Im2Wav는 FD·정렬 지표가 낫다. 테스트 이미지는 AnimeGANv2(Paprika 스타일)로 **회화풍 변환**된 키프레임이다 — [arXiv 2503.10522](https://arxiv.org/pdf/2503.10522)
- V2A-Mapper(AAAI 2024): BLIP 캡션을 T2A에 넣는 방식 대비 Im2Wav와 비교했을 때 자체 방법이 FD·FAD·관련성에서 낫고 Im2Wav보다 약 24배 빠르다 [구버전] — [arXiv 2308.09300](https://arxiv.org/pdf/2308.09300)
- "Sounding that Object"(2025): Make-an-Audio, Im2Wav, SpecVQGAN이 AVC 점수는 괜찮지만 FAD·KL에서 저조하다(음질 한계)고 지적. 객체 인식 기반 이미지→오디오(클릭/영역 선택)를 제안 — [arXiv 2506.04214](https://arxiv.org/html/2506.04214v1)
- HunyuanVideo-Foley 입력은 video + text — [GitHub](https://github.com/Tencent-Hunyuan/HunyuanVideo-Foley); ThinkSound는 video/text/audio이고 이미지 입력 언급 없음 — [GitHub](https://github.com/FunAudioLLM/ThinkSound); Woosh는 text/video만 지원 — [arXiv](https://arxiv.org/html/2604.01929v3)
- 비디오→오디오 FoleyBench에서는 Woosh-VFlow(413M)가 FD 24.14 / CLAP 0.325로 MMAudio-M(621M)의 30.48 / 0.292보다 낫다 — [arXiv 2604.01929v3](https://arxiv.org/html/2604.01929v3)

### Inferences
- 이 앱은 영상 동기화가 필요 없는 **정지 회화의 분위기음**이므로, V2A 모델의 강점(타이밍 동기화, DeSync)이 쓸모없다. 오히려 정지 프레임 복제 입력은 학습 분포 밖이라 위험하다.
- "Sounding that Object"처럼 크롭/영역 기반 접근이 개념적으로 앱과 가장 비슷하다. 다만 공개 웨이트·라이선스·VRAM은 확인하지 못했다(Gaps 참조). 실무적으로는 **크롭 이미지를 VLM에 넣어 음원별 상세 프롬프트를 만드는 방식**(현재 구조의 개선판)이 가장 안전하다.
- 실험해 볼 만한 하이브리드: MMAudio에 정지 프레임과 텍스트 프롬프트를 함께 넣어 텍스트 단독 결과와 비교한다(비상업, Ubuntu만 테스트됨, 8초). 과제 데모용 비교 실험으로는 흥미롭지만 주 파이프라인으로는 추천하지 않는다.

### Gaps
- 회화(유화) 입력에 대한 이미지→오디오 정량 평가는 AudioX의 AnimeGAN 변환 실험 외에 찾지 못했다.
- AudioX 원본의 이미지 조건 웨이트 라이선스와 12GB 실행 가능 여부는 미확인이다.
- SEE-2-SOUND, CLIPSonic의 2026 현황은 이번에 조사하지 못했다.

## 4. 끊김 없는 루프와 음량 일관성

### Takeaway
**루프 생성을 명시적으로 지원하는 오픈 T2A 모델은 찾지 못했다**. 다만 Stable Audio 3와 `stable-audio-tools`는 **inpainting**(여러 구간 마스킹 가능)을 지원하므로, "끝부분을 시작부분 문맥으로 inpaint"하는 루프 경계 생성이 기술적으로 가능하다. 음량은 RMS보다 **ITU-R BS.1770 기반 LUFS(pyloudnorm)** 정규화와 true-peak/peak 제한을 같이 쓰는 방식이 표준적이다.

### Cited Findings
- SA3: 단일·다중 구간 inpainting과 continuation 지원. 두 구간 마스킹도 한 구간과 비슷한 품질. small은 medium/large보다 inpainting FAD가 나쁘고 전환이 덜 매끄럽다. continuation은 inpainting보다 FAD가 나쁘다 — [arXiv 2605.17991](https://arxiv.org/html/2605.17991v1)
- SA3 small-sfx 모델 카드 예제가 `generate_diffusion_cond_inpaint`를 사용 — [HF](https://huggingface.co/stabilityai/stable-audio-3-small-sfx)
- SA3 논문에 "짧은 학습 샘플 대부분이 루프"라는 서술이 있다(학습 데이터에 루프 소재가 많다는 뜻) — [arXiv 2605.17991](https://arxiv.org/html/2605.17991v1)
- pyloudnorm: ITU-R BS.1770-4 구현, 기본 400ms 게이팅 블록. `pyln.Meter(rate).integrated_loudness(data)`로 측정하고 `pyln.normalize.loudness(data, loudness, target)`로 정규화한다. 피크 정규화는 `pyln.normalize.peak(data, -1.0)`, LRA 측정(EBU Tech 3342)도 지원. MIT 라이선스 — [GitHub pyloudnorm](https://github.com/csteinmetz1/pyloudnorm)

### Inferences
- **음량 편차 원인 추정**: RMS는 주파수 가중이 없어서, 저역이 많은 바람 소리와 고역 중심의 까마귀 소리가 같은 RMS여도 체감 음량이 크게 다르다. 또 무음 구간이 많은 산발적 소리(까마귀 울음)는 RMS가 낮게 나와 과도하게 증폭되고 노이즈가 부각된다. LUFS(K-weighting과 게이팅)는 이 두 문제를 모두 완화한다.
- 권장 절차(추론, 검증 필요): (1) 스테레오 출력이면 모노로 다운믹스 → (2) DC 제거와 하이패스(~30Hz) → (3) 루프화 → (4) **루프 완성본에 대해** pyloudnorm integrated LUFS로 통일된 목표값(예: 음원 레이어 기준 -23~-28 LUFS 범위에서 하나를 선택) 정규화 → (5) `peak` 또는 true-peak로 -1 dBFS 이하 제한. 게이팅 때문에 산발적 소리는 RMS 방식보다 덜 증폭된다. 음원 유형(배경 베드 vs 포인트 소리)별로 목표값 오프셋을 두는 것도 고려할 만하다.
- 루프 방법 대안: (a) 현재처럼 크로스페이드. 앰비언트 베드(바람, 모닥불)에는 충분하다. (b) SA3 inpainting으로 [끝 1~2초 | 시작 1~2초]를 이어 붙인 뒤 접합부만 재생성. (c) 앰비언트는 생성 길이를 늘려(예: 20초) 루프 지점을 RMS·스펙트럼 유사도로 탐색. 포인트성 소리(까마귀, 웃음)는 루프보다 **원샷 여러 개를 Unity에서 랜덤 간격으로 재생**하는 편이 반복감이 적다(설계상 제안).

### Gaps
- 루프 인지(loop-aware) 생성을 공식 지원하는 오픈 오디오 모델이나 논문은 이번 조사에서 확인하지 못했다.
- 게임/AR 앰비언트용 권장 LUFS 수치의 표준 문서(예: EBU R128 -23 LUFS, 게임 오디오 가이드)는 직접 확인하지 않았다.

## 5. 라이선스 정리 (상업 사용 여부)

### Takeaway
SCL 계열(SAO 1.0, SAO Small, SA3 small/medium)은 연매출 $1M 미만이면 상업 사용이 무료이고 출력물 소유권은 사용자에게 있다. TangoFlux, MMAudio(웨이트), Woosh, ThinkSound는 비상업 전용이다. MOSS-SoundEffect v2.0은 Apache 2.0(패밀리 표기) 가능성이 있으나 개별 확인이 필요하다.

### Cited Findings
- Stability AI Community License: 연매출 USD $1M 미만 개인·조직은 Core Model 사용·배포가 무료이고, 그 이상이면 Enterprise License가 필요하다. 출력물은 "as between you and Stability" 사용자 소유이며 법률과 AUP를 지키는 범위에서 자유롭게 사용 가능. 출력물로 경쟁 파운데이션 모델을 만드는 것은 금지. 위반 시 철회 가능 — [stability.ai/license](https://stability.ai/license)
- SAO Small 발표문은 "free for commercial and non-commercial use"라고 하지만, 실제로는 위 매출 기준이 붙는다 — [Stability 발표](https://stability.ai/news/stability-ai-and-arm-release-stable-audio-open-small-enabling-real-world-deployment-for-on-device-audio-control); [stability.ai/license](https://stability.ai/license)
- SA3 small-sfx: SCL + Gemma Terms of Use(T5Gemma, Section 3.2 사용 제한) — [HF](https://huggingface.co/stabilityai/stable-audio-3-small-sfx)
- TangoFlux: non-commercial research only [NC] — [HF](https://huggingface.co/declare-lab/TangoFlux)
- MMAudio: 코드 MIT, 웨이트 CC-BY-NC 4.0 [NC] — [GitHub](https://github.com/hkchengrex/MMAudio)
- Woosh: non-commercial weights [NC] — [arXiv](https://arxiv.org/html/2604.01929v3)
- ThinkSound: "Commercial use is NOT permitted"(Apache 2.0 표기와 모순), SAO VAE에 SCL 적용 [NC] — [GitHub](https://github.com/FunAudioLLM/ThinkSound)
- HunyuanVideo-Foley: 별도 LICENSE 파일(상업 조건 미확인) — [GitHub](https://github.com/Tencent-Hunyuan/HunyuanVideo-Foley)
- MOSS-TTS Family: Apache 2.0 표기 — [GitHub](https://github.com/OpenMOSS/MOSS-TTS)

### Inferences
- 학생 과제(비영리)라면 모든 후보를 사용할 수 있다. 추후 포트폴리오나 상업 배포 가능성까지 고려하면 SCL 계열(특히 SA3)이 가장 안전하다.

### Gaps
- Stability Community License 전문(출력물 재배포, 표기 의무)은 요약 페이지만 확인했다.
- HunyuanVideo-Foley, MOSS-SoundEffect v2.0, AudioX, Make-An-Audio 3, Kling-Foley, AudioGen의 정확한 라이선스는 미확인이다.
