# 소형 오픈 VLM을 "그림 사운드 디자이너"로 쓰기 위한 모델 조사 (2026-11-25 기준)

> 조사 범위: RTX 3060 12GB / Windows / PyTorch + transformers 5.x 로컬 실행. 그림 1장(+선택적 캡션·탐지 목록) → 4~6개 음원 JSON(한국어 라벨·설명, 영어 오디오 프롬프트, type, 탐지 index 또는 좌표).
> 표기: [구버전]=2025년 이전/초반 정보, [Linux 전용]=Windows 미지원, [NC]=비상업 라이선스, [추정]=출처 없는 계산·추론.
> 수치 대부분은 모델 개발사 자체 보고값이라 모델 간 직접 비교는 조심해야 함.

## Q1. 12GB VRAM에 들어가는 가장 강한 VLM은? (출시일·라이선스·transformers 지원)

### Takeaway
공개 수치상 이 작업에 가장 유력한 후보는 **Qwen3.5-4B**(bf16로 거의 꽉 참)와 **Qwen3.5-9B**(4-bit 필요)다. 둘 다 Apache-2.0이고, HallusionBench·RefCOCO·CountBench 점수를 공식 카드에 공개해 둔 소형 모델은 조사 범위 안에서 이 둘뿐이었다. Gemma 4 E2B/E4B는 Apache-2.0이고 native 지원이지만 공개된 비전 벤치가 MMMU-Pro 등 일부뿐이다. MiniCPM-V-4.7-1B는 실재하는 모델(2026-10, Apache-2.0)이지만 카드에 수치 벤치가 없다. Molmo2는 포인팅에 특화돼 있지만 영어 전용이고 trust_remote_code가 필요하다.

### Cited Findings
**Qwen3.5 (Alibaba)**
- Qwen3.5-4B: Apache-2.0, 인용 표기 "February 2026", LM 4B(Safetensors 기준 총 5B). Gated DeltaNet + Gated Attention 하이브리드 구조, 컨텍스트 262,144. "The latest transformers is required"라며 main 브랜치 설치를 권장함 — [Qwen/Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B)
- 비전 벤치(4B / 9B): MMMU 77.6/78.4, MMMU-Pro 66.3/70.1, MMStar 78.3/79.7, MMBench-EN-v1.1 89.4/90.1, RealWorldQA 79.5/80.3, **HallusionBench 65.0/69.3**, OCRBench 85.0/89.2, **CountBench 96.3/97.2**, **RefCOCO(avg) 88.1/89.7**, VlmsAreBlind 92.6/93.7, RefSpatialBench 54.6/58.5. POPE는 표에 없음 — [Qwen/Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B)
- 다국어: "201 languages and dialects" 지원. MMMLU 76.1(4B)/81.2(9B), WMT24++ 66.6/72.6 — [Qwen/Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B)
- Qwen3.5-2B: MMMU 64.2, MMMU-Pro 50.3, MathVista(mini) 76.7(미러 카드 기준) — [Qwen3.5-2B 미러](https://huggingface.co/richiehakim/Qwen3.5-2B), [Qwen/Qwen3.5-2B](https://huggingface.co/qwen/qwen3.5-2b)
- Artificial Analysis 측정 MMMU-Pro: 9B 69.2%, 4B 65.4%. 비교 대상은 Qwen3-VL-8B 56.6%, Qwen3-VL-4B 52.0%, Ministral 3 8B 46.0%(2026-03-05) — [Artificial Analysis](https://artificialanalysis.ai/articles/qwen3-5-small-models)
- 2026년 11월 중순 기준 소형 모델 순위에서 Qwen3.5-9B를 1위로 꼽은 2차 블로그가 있음. 다만 aggregator 성격이라 신뢰도는 중간 — [tinyweights.dev](https://tinyweights.dev/posts/best-local-vision-language-models-2026/), [SiliconFlow](https://www.siliconflow.com/articles/best-small-llms-under-10b-parameters)

**Qwen3-VL (이전 세대)**
- Qwen3-VL-4B-Instruct: Apache-2.0. 카드는 transformers 소스 설치를 안내함(4.57.0 이상 필요로 보임). OCR 32개 언어 지원. 카드의 벤치는 이미지로만 제공되고 grounding 좌표 형식은 카드 본문에 명시돼 있지 않음 — [Qwen/Qwen3-VL-4B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct) [구버전: 2025년 하반기]

**Gemma 4 (Google)**
- gemma-4-E4B-it: Apache-2.0. 실효 4.5B, 임베딩 포함 8B(safetensors 8B). `AutoModelForMultimodalLM`으로 native 로드. 지원 이미지 토큰 예산은 70/140/280/560/1120. 이미지 이해 기능에 object detection·pointing이 포함돼 있으나 해당 벤치 수치는 없음. 35+ 언어를 바로 지원하고 140+ 언어로 사전학습. Korean 전용 수치 없음 — [google/gemma-4-E4B-it](https://huggingface.co/google/gemma-4-E4B-it)
- 비전 벤치: MMMU-Pro E4B 52.6% / E2B 44.2% / **12B Unified 69.1%** / 26B-A4B 73.8% / 31B 76.9%. MATH-Vision E4B 59.5 / E2B 52.4 — [google/gemma-4-E4B-it](https://huggingface.co/google/gemma-4-E4B-it), [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4.md)
- 출시일: Wikipedia는 2026-04-02라고 기재해 사용자 메모(2026-03)와 다름 — [Wikipedia Gemma](https://en.wikipedia.org/wiki/Gemma_(language_model))

**MiniCPM-V (OpenBMB)**
- MiniCPM-V 4.6: 2026-05-11 출시. 약 1.3B(SigLIP2-400M + Qwen3.5-0.8B). Instruct와 Thinking이 별도 체크포인트이고 GGUF/AWQ/GPTQ/BNB 양자화본이 있음 — [NYU Shanghai RITS](https://rits.shanghai.nyu.edu/ai/minicpm-v-4-6-a-1-3b-multimodal-model-built-for-phones/), [openbmb/MiniCPM-V-4.6](https://huggingface.co/openbmb/MiniCPM-V-4.6)
- MiniCPM-V 4.7: 1B dense와 35B-A3B MoE 두 종. 출시일은 2026-10-12(Magica) 또는 10-06(ApX)으로 출처마다 다름 — [Magica](https://magica.com/news/openbmb-minicpm-v-4-7-35b-a3b-open-source), [ApX](https://apxml.com/models/minicpm-v-4-7-1b)
- MiniCPM-V-4.7-1B 카드: Apache-2.0. `transformers[torch]>=5.18.0`, `AutoModelForImageTextToText` 사용(trust_remote_code 언급 없음). thinking 기본 off(`enable_thinking=False`). Hub 메타데이터는 "2B params"로 표기됨. bnb int4·AWQ·GPTQ·GGUF 제공. **수치 벤치 없음**(차트 이미지만 있고, "substantially outperforms Qwen3.5 0.8B"라고만 적음). 다국어 지원 여부도 명시 없음 — [openbmb/MiniCPM-V-4.7-1B](https://huggingface.co/openbmb/MiniCPM-V-4.7-1B)

**InternVL3.5 (OpenGVLab)**
- InternVL3_5-4B-HF: Apache-2.0. InternViT-300M과 Qwen3 계열 LM, 총 4.7B. transformers>=4.52.1. thinking은 R1 스타일 시스템 프롬프트로 켬. 벤치는 이미지로만 제공돼 텍스트 수치 없음. 논문은 2025-08-25 — [OpenGVLab/InternVL3_5-4B-HF](https://huggingface.co/OpenGVLab/InternVL3_5-4B-HF) [구버전]

**Molmo 2 (Ai2) — 포인팅 특화**
- 2025-12 출시. 4B / 8B(Qwen3 기반) / 7B(Molmo2-O, Olmo 기반) 세 종이 있고, 포인팅·트래킹 특화 버전도 있음 — [Ai2 blog](https://allenai.org/blog/molmo2), [BusinessWire](https://www.businesswire.com/news/home/20251216910167/en)
- Molmo2-4B: Apache-2.0이지만 학습 데이터 일부가 "academic and non-commercial research use only" 조건임. Qwen3-4B-Instruct-2507 + SigLIP2. `trust_remote_code=True`(custom_code)이고 Quick Start는 `transformers==4.57.1`에 고정돼 있어 **transformers 5.x 호환이 불확실**. 포인팅은 `<points ... coords="...">` 형식에 0~1000 스케일. 영어 전용 태그. 가중치가 F32로 저장됨(5B) — [allenai/Molmo2-4B](https://huggingface.co/allenai/Molmo2-4B)

**한국어 특화 모델**
- kakaocorp/kanana-1.5-v-3b-instruct: 2025-07-24 출시, "kanana license", 3.6B. `trust_remote_code=True`, transformers>=4.45. 자체 측정 평균에서 Image(KO) 68.27로 Qwen2.5-VL-3B 60.60, InternVL2.5-4B 54.68, HCX-SEED-Vision-3B 51.96보다 높음. MMB 78.44, MMStar 56.32, MMMU 43.89. 지시 따르기 MIABench-Ko 91.17 — [kakaocorp/kanana-1.5-v-3b-instruct](https://huggingface.co/kakaocorp/kanana-1.5-v-3b-instruct) [구버전]
- naver-hyperclovax/HyperCLOVAX-SEED-Vision-Instruct-3B: 2025-04-22 출시, "hyperclovax-seed" 라이선스(카드에 상업 조건 명시 없음). LLM 3.2B + 비전 0.43B. `AutoModelForCausalLM` + `trust_remote_code=True`이고 transformers 4.52.4에서 검증됨. 데이터 컷오프는 2024-08 이전. MMBench-Val 81.8, Korean VisIT-Bench 37.0(Qwen2.5-VL-3B 81.5보다 크게 낮음). OCR을 빼면 KoNet이 69.2에서 36.6으로 떨어짐 — [HyperCLOVAX-SEED-Vision-Instruct-3B](https://huggingface.co/naver-hyperclovax/HyperCLOVAX-SEED-Vision-Instruct-3B) [구버전]
- NCSOFT/VARCO-VISION-2.0-1.7B: 2025-07-28 출시. **CC-BY-NC-4.0 [NC]**. Qwen3-1.7B + SigLIP2, LLaVA-OneVision 구조라 native `LlavaOnevisionForConditionalGeneration`으로 로드되고 transformers>=4.53.1. K-MMBench 77.9, K-LLaVA-W 73.5, POPE 88.6, HallusionBench 43.0 — [NCSOFT/VARCO-VISION-2.0-1.7B](https://huggingface.co/NCSOFT/VARCO-VISION-2.0-1.7B) [구버전]

**기타**
- LiquidAI LFM2.5-VL-1.6B: 라이선스 "LFM Open License v1.0"(Apache 기반의 맞춤 라이선스로, 상업 조건은 LICENSE 파일을 확인해야 함). transformers v5.1 이상에서 `AutoModelForImageTextToText`. 구조화 추출 특화 변형 "LFM2.5-VL-1.6B-Extract"가 있음 — [LiquidAI/LFM2.5-VL-1.6B](https://huggingface.co/LiquidAI/LFM2.5-VL-1.6B), [LFM2.5-VL-1.6B-Extract](https://huggingface.co/LiquidAI/LFM2.5-VL-1.6B-Extract)
- Ministral 3 8B는 FP8 기준 12GB에 들어가고 이미지와 function calling을 지원한다는 2차 블로그 언급이 있음(원문 미확인) — [tinyweights.dev](https://tinyweights.dev/posts/best-local-vision-language-models-2026/)

### Inferences
- [추정] VRAM(가중치만): Qwen3.5-4B 총 5B × 2 byte ≈ 10GB라 12GB에서 이미지 토큰·KV 캐시 여유가 빠듯함. 이미지 해상도(max_pixels)를 제한하거나 8-bit/4-bit 양자화가 필요할 수 있음. Gemma-4-E4B는 임베딩 포함 8B라 bf16 전체 적재 시 약 16GB로 12GB를 넘을 가능성이 있음(PLE 오프로딩 여부는 미확인). E2B는 들어감. Qwen3.5-9B·Gemma 4 12B는 4-bit에서 약 5~7GB가 될 것으로 보임. **정확하지 않을 수 있음**
- 이 작업("보이는 것만, 환각 없이, 위치 포함")과 가장 직접적으로 관련된 공개 지표(HallusionBench, CountBench, RefCOCO)를 모두 갖춘 소형 모델은 Qwen3.5뿐이었음. 그래서 1순위는 Qwen3.5-4B(bf16)이고, 품질을 더 원하면 Qwen3.5-9B(4-bit)가 다음 후보.
- 한국어 특화 3B급 모델(kanana/HCX/VARCO)은 2025년 중반 Qwen2.5-VL 세대를 기준으로 비교했기 때문에, 2026년 Qwen3.5-4B보다 일반 시각 이해가 앞선다는 근거는 찾지 못함.
- Molmo2는 좌표 정확도가 강점이지만 한국어 미지원, transformers 4.57.1 고정, F32 저장 때문에 메인 모델로는 부적합해 보임. 좌표만 별도로 뽑는 보조 단계로는 검토할 가치가 있음.

### Gaps
- Phi-4-multimodal, SmolVLM2, Kimi-VL, GLM-4.xV 소형, Ovis2.x의 2026년 최신 상태(라이선스·transformers 5 지원)는 이번 조사에서 확인하지 못함.
- Qwen3.5와 Gemma 4의 POPE·AMBER 점수는 찾지 못함.
- MiniCPM-V-4.7-1B의 수치 벤치와 한국어 지원 여부는 카드에 없음.
- InternVL3.5-4B, Qwen3-VL-4B는 카드 벤치가 이미지로만 제공돼 텍스트 수치를 확보하지 못함.
- HyperCLOVAX-SEED 라이선스의 상업 이용 조건은 카드 본문에 없음.

## Q2. 관련 벤치마크 근거 (환각 / 일반 / 미술 이해 / 한국어 / grounding / 구조화 출력)

### Takeaway
환각·grounding 지표는 Qwen3.5 카드에만 체계적으로 공개돼 있다. 미술 작품 전용으로 소형 VLM을 평가한 연구는 거의 없다. 독립적인 한국어 평가(KMMMU)에서는 한국어 특화 소형 모델이 범용 모델을 확실히 이기지 못했다. 이미지→JSON 스키마 준수(SO-Bench)는 소형 모델의 약점으로 보고됐다.

### Cited Findings
**환각**
- HallusionBench: Qwen3.5-4B 65.0, 9B 69.3 — [Qwen/Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B)
- VARCO-VISION-2.0-1.7B는 HallusionBench 43.0 / POPE 88.6, InternVL3-2B는 41.9 / 90.1, Ovis2-2B는 50.2 / 87.8 — [NCSOFT/VARCO-VISION-2.0-1.7B](https://huggingface.co/NCSOFT/VARCO-VISION-2.0-1.7B) [구버전 비교]
- 2026년 환각 연구로 ReactBench(원인 기반 멀티모달 환각 벤치)와 프롬프트 유도 환각 메커니즘 연구가 있음(본문 미확인) — [ReactBench arXiv 2605.29579](https://arxiv.org/pdf/2605.29579), [arXiv 2601.05201](https://arxiv.org/pdf/2601.05201)

**일반**
- MMStar/MMBench/MMMU: Qwen3.5-4B 78.3 / 89.4 / 77.6. kanana-1.5-v-3b 56.32 / 78.44 / 43.89. VARCO-2.0-1.7B MMStar 54.5, MMMU 44.1 — [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B), [kanana](https://huggingface.co/kakaocorp/kanana-1.5-v-3b-instruct), [VARCO](https://huggingface.co/NCSOFT/VARCO-VISION-2.0-1.7B)

**미술 이해**
- "Have large vision-language models mastered art history?"(arXiv 2409.03521, 2024): CLIP, LLaVA, GPT-4o로 작품의 화풍·작가·시기를 zero-shot 분류하고 프롬프트 민감도를 분석함(초록에 수치 없음) — [arXiv 2409.03521](https://arxiv.org/abs/2409.03521) [구버전]
- 2026년 미술 관련 VLM 연구로 "Cross-Cultural Expert-Level Art Critique Evaluation with VLMs"(2601.07984)와 VULCA-Bench(다문화 이해, 2601.07986)가 있음(내용 미확인) — [arXiv 2601.07984](https://arxiv.org/pdf/2601.07984), [arXiv 2601.07986](https://arxiv.org/pdf/2601.07986)

**한국어**
- KMMMU(2026-04, 3,466문항, 한국어로 작성된 시험 문제): Qwen3-VL-2B 14.24, Qwen3-VL-4B 19.88, Qwen3-VL-8B 24.56, VARCO-2.0-1.7B 23.59, VARCO-2.0-14B 27.55, HyperCLOVAX-SEED-Vision-3B 18.14, Gemma-3-4B 20.49. 결론은 "Korean-language specialization alone is not enough". HCX-SEED만 한국 특화 문항(24.22)이 비한국 문항(17.57)보다 높았음. kanana·Qwen3.5·Gemma 4는 미평가 — [KMMMU arXiv 2604.13058](https://arxiv.org/html/2604.13058v2)
- KorMedMCQA-V: 최고 오픈 모델 Qwen3-VL-32B-Thinking 83.7%, 최고 한국 특화 모델 VARCO-2.0-14B 43.2% — [arXiv 2602.13650](https://arxiv.org/html/2602.13650v1)
- K-MMBench: VARCO-2.0-1.7B 77.9, InternVL3-2B 76.9 — [VARCO card](https://huggingface.co/NCSOFT/VARCO-VISION-2.0-1.7B)
- HyperCLOVA X 32B Think는 K-MMBench 88.1(Qwen3-VL-32B-Thinking 91.1)로, 12GB 범위 밖 모델임 — [arXiv 2601.03286](https://arxiv.org/html/2601.03286v1)
- KoNET(교육 표준 기반 평가) 논문이 있고, HCX-SEED-3B의 KoNet 점수는 69.2(OCR 포함) — [arXiv 2502.15422](https://arxiv.org/pdf/2502.15422), [HCX card](https://huggingface.co/naver-hyperclovax/HyperCLOVAX-SEED-Vision-Instruct-3B)

**Grounding**
- RefCOCO(avg): Qwen3.5-4B 88.1, 9B 89.7 — [Qwen/Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B)
- Molmo2: "precise pixel coordinates, object positions"를 반환하고, 카드상 출력은 0~1000 스케일 points 태그 — [Ai2 blog](https://allenai.org/blog/molmo2), [Molmo2-4B](https://huggingface.co/allenai/Molmo2-4B)

**구조화 출력**
- SO-Bench(Apple, 2025-11): 이미지 기반 JSON 스키마 준수 벤치(6.5K 스키마, 1.8K 이미지-스키마 쌍, UI/자연 이미지/문서/차트). 결론은 "persistent gaps in predicting accurate, schema compliant outputs". 검색 요약에 따르면 3B·7B 소형 모델의 준수율 격차가 큼 — [arXiv 2511.21750](https://arxiv.org/abs/2511.21750), [SO-Bench html](https://arxiv.org/html/2511.21750v2)

### Inferences
- 미술 이미지에서 소형 VLM의 환각률을 직접 측정한 공개 수치는 없음. 따라서 사용자가 진행 중인 로컬 벤치(예: 명화 20~30장 × 수동 정답 음원 목록 → precision/recall, JSON 파싱 성공률)가 사실상 유일한 판단 근거가 됨.
- KMMMU는 지식형 시험 문제 위주라 "자연스러운 한국어 문장 작성"과는 성격이 다름. 한국어 생성 품질을 판단하는 근거로는 약함.

### Gaps
- ArtBench류 미술 벤치에서 Qwen3.5/Gemma 4/MiniCPM-V 4.7의 점수는 찾지 못함.
- SO-Bench의 모델별 수치는 초록만 확인했고 본문 표는 미확인.
- AMBER 점수는 어떤 후보에서도 확인하지 못함.

## Q3. transformers에서 JSON 강제(constrained) 디코딩 — Windows에서 가능한가?

### Takeaway
가능해 보인다. Outlines의 `TransformersMultiModal`(`outlines.from_transformers(model, processor)`)이 HF VLM에 Pydantic/JSON 스키마 강제를 지원하고, xgrammar는 공식 Windows 휠을 제공한다. vLLM/SGLang 기반 경로는 Linux 위주라 이 환경에는 맞지 않는다.

### Cited Findings
- Outlines `TransformersMultiModal`: `AutoModelForImageTextToText` 모델과 `AutoProcessor`를 감싸 Pydantic 모델을 output_type으로 넘기는 방식. 예시 모델은 Qwen2.5-VL-3B/7B. 제약은 프로세서가 요구하는 `<image>` 태그를 넣어야 한다는 점(Chat 인터페이스를 쓰면 자동 처리) — [Outlines docs](https://dottxt-ai.github.io/outlines/latest/features/models/transformers_multimodal/)
- xgrammar: PyPI에 Linux/macOS/Windows 지원으로 표기, Windows x86-64·ARM64 휠, CPython 3.12~3.14 — [PyPI xgrammar](https://pypi.org/project/xgrammar)
- 속도 비교: lm-format-enforcer는 Python 중심의 매 스텝 마스크 계산 때문에 토큰당 지연이 Outlines·llguidance·xgrammar보다 큼. xgrammar와 guidance가 outlines보다 대체로 빠르지만, RTX 4090 등에서는 xgrammar의 CPU–GPU 동기화 오버헤드로 outlines가 더 빠른 경우도 보고됨 — [vLLM forum](https://discuss.vllm.ai/t/general-questions-on-structured-output-backend/1444), [nanonets cookbook](https://nanonets.com/cookbooks/structured-llm-outputs/constrained-decoding/backends/lm-format-enforcer/)
- llguidance도 별도 구조화 디코딩 백엔드로 MaskBench 성능을 공개함 — [guidance-ai/llguidance](https://github.com/guidance-ai/llguidance)
- Alibaba Model Studio의 JSON Schema 모드는 일부 Qwen-VL에서 비사고(non-thinking) 모드에서만 지원됨(API 기능이며 로컬 기능 아님) — [Aliyun structured output](https://help.aliyun.com/en/model-studio/qwen-structured-output)
- 강제 디코딩 없이 프롬프트에 스키마만 넣으면 코드펜스나 부가 설명 때문에 `json.loads()`가 깨질 수 있다는 튜토리얼 경고 — [theneuralbase](https://theneuralbase.com/multimodal-generation/learn/beginner/structured-output-generation/)
- Qwen3.5 카드에는 JSON 모드 안내가 없고 tool calling 파서(`qwen3_coder`)만 있음 — [Qwen/Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B)

### Inferences
- 권장 [추정]: (1) Outlines `from_transformers` + Pydantic 스키마. 이때 `type`은 `Literal["nature","people","animal","vehicle","music"]`, 음원 수는 `conlist(min_length=4, max_length=6)`, 위치는 `Union[int 인덱스, 좌표]`로 정의. (2) 이것이 실패하면 프롬프트 + `json` 추출 + Pydantic 검증 + 재시도. 강제 디코딩은 형식은 보장하지만 내용(환각)은 보장하지 않음.
- Qwen3.5의 Gated DeltaNet 하이브리드나 Gemma 4 등 최신 아키텍처에서 Outlines가 transformers 5.x와 함께 문제없이 돌아가는지는 미검증이라 직접 테스트가 필요함. **정확하지 않을 수 있음**

### Gaps
- Outlines·xgrammar를 Windows + transformers 5.x + Qwen3.5/Gemma 4 조합으로 쓴 사례는 찾지 못함.
- transformers 5.x 자체에 JSON 스키마 강제 기능이 내장됐는지는 확인하지 못함.

## Q4. Thinking 모드(Qwen3.5 enable_thinking)는 끄는 게 맞나?

### Takeaway
끄는 쪽을 권장한다. Qwen3.5 소형(0.8B~9B)은 thinking이 기본 off라는 Unsloth 문서가 있고, MiniCPM-V-4.7-1B도 기본 off다. 단, 런타임에 따라 off 플래그가 무시돼 `<think>` 블록이 JSON 앞에 붙는 버그 보고가 많으므로 `apply_chat_template(..., enable_thinking=False)`를 직접 넘기고 출력 꼬리를 확인해야 한다. thinking의 정확도 이득은 KMMMU에서 대형 모델 기준 2~6점으로 제한적이었다.

### Cited Findings
- Qwen3.5 비사고 모드 권장 샘플링(일반 작업): temperature 0.7, top_p 0.8, top_k 20, presence_penalty 1.5. `/think`, `/nothink` 소프트 스위치는 미지원. 끄는 방법은 `chat_template_kwargs: {"enable_thinking": False}` — [Qwen/Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B)
- Unsloth: "for Qwen3.5 0.8B, 2B, 4B and 9B, reasoning is disabled by default" — [Unsloth Qwen3.5 docs](https://unsloth.ai/docs/models/qwen3.5.md)
- off 플래그가 무시되는 버그 보고: LM Studio, llama.cpp, vLLM — [LM Studio #1990](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/1990), [llama.cpp #20182](https://github.com/ggml-org/llama.cpp/issues/20182), [vLLM #35574](https://github.com/vllm-project/vllm/issues/35574)
- Ollama에서 qwen3.5:35b-a3b의 thinking을 끄면 `format`(JSON)이 무시되는 이슈 — [Ollama #14645](https://github.com/ollama/ollama/issues/14645)
- 출력 앞에 약 200토큰짜리 `<think>` 독백이 붙어 JSON 파싱이 깨졌고, `apply_chat_template`에 `enable_thinking=False`를 넘겨 해결한 사례(Qwen3.6 MoE) — [DEV Community](https://dev.to/sleepyquant/qwen-36-enablethinking-the-moe-pitfall-that-broke-my-agent-json-parsing-71a)
- Gemma 4: 시스템 프롬프트의 `<|think|>` 토큰으로 thinking을 켜고, E2B/E4B는 thinking off일 때 빈 thought 블록을 만들지 않음 — [google/gemma-4-E4B-it](https://huggingface.co/google/gemma-4-E4B-it)
- MiniCPM-V-4.7-1B는 `enable_thinking=False`가 기본 — [openbmb/MiniCPM-V-4.7-1B](https://huggingface.co/openbmb/MiniCPM-V-4.7-1B)
- KMMMU: thinking 이득은 Qwen3-VL-30B-A3B +6.0, 32B +2.2, 235B +2.6. 남은 오류는 추론 깊이보다 지식·grounding 문제라는 분석 — [KMMMU](https://arxiv.org/html/2604.13058v2)

### Inferences
- [추정] thinking을 켜면 출력 토큰이 수백~수천 개 늘어 3060에서 그림 1장당 지연이 몇 배로 커지고, `max_new_tokens`에 걸려 JSON이 잘릴 위험도 생김. 이 작업은 지각·기술 과제라 추론 이득이 작을 것으로 보임. 다만 "보이는 것만" 고르는 판단에 thinking이 도움이 되는지는 로컬 A/B로 확인할 가치가 있음.

### Gaps
- 소형 VLM에서 thinking on/off별 JSON 성공률이나 환각률을 비교한 공개 데이터는 없음.

## Q5. Windows 4-bit 양자화(bitsandbytes)와 RTX 3060 속도

### Takeaway
bitsandbytes는 0.47 이후 공식 Windows x86-64 CUDA 휠을 제공하고 NF4를 지원한다(3060은 compute capability 8.6이라 충족). AWQ/GPTQ 사전 양자화본은 MiniCPM-V 4.6/4.7 등에 있다. RTX 3060 실측 속도는 찾지 못했다.

### Cited Findings
- bitsandbytes 문서(0.47.0): Windows x86-64 CUDA 빌드, MSVC 19.43+(VS2022), CUDA 11.8~12.8. 0.50.0 릴리스 노트에는 Windows ROCm 빌드 등이 추가됨. NF4/FP4는 compute capability 6.0+ — [bitsandbytes 0.47 install](https://huggingface.co/docs/bitsandbytes/v0.47.0/en/installation), [bitsandbytes 0.50 install](https://huggingface.co/docs/bitsandbytes/v0.50.0/installation)
- PyPI에 `bitsandbytes-...-win_amd64.whl`이 있어 `pip install bitsandbytes`로 설치 가능 — [PyPI bitsandbytes](https://pypi.org/p/bitsandbytes)
- 이전의 "Windows not supported" 문서는 오래된 캐시 — [bitsandbytes en/installation](https://huggingface.co/docs/bitsandbytes/en/installation)
- transformers의 NF4 사용법은 `BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4")` — [Transformers v5.13 bitsandbytes](https://huggingface.co/docs/transformers/v5.13.0/quantization/bitsandbytes)
- MiniCPM-V-4.7-1B는 bnb int4, AWQ, GPTQ(W4A16), GGUF를 제공하고 Flash Attention 2를 권장 — [openbmb/MiniCPM-V-4.7-1B](https://huggingface.co/openbmb/MiniCPM-V-4.7-1B)
- Qwen3-VL-8B는 Q4에서 약 6GB(GGUF/llama.cpp 기준, 2차 블로그) — [tinyweights.dev](https://tinyweights.dev/posts/best-local-vision-language-models-2026/)

### Inferences
- [추정] Flash Attention 2는 Windows 공식 휠이 없어 설치가 어려운 경우가 많음. `attn_implementation="sdpa"`가 현실적인 기본값. **정확하지 않을 수 있음**
- [추정] 사용자 메모에 따르면 Qwen3.5-4B를 이미 로컬 벤치 중이므로, bf16 4B와 NF4 9B를 같은 그림 세트에서 지연·VRAM·JSON 성공률로 비교하는 것이 가장 확실함. Qwen3.5의 Gated DeltaNet 커널(fla 등)이 Windows에서 느린 폴백 경로로 돌 가능성도 있음(미확인).

### Gaps
- RTX 3060에서 Qwen3.5-4B/9B, Gemma 4 E4B의 tokens/s 실측 자료는 찾지 못함.
- Qwen3.5 Gated DeltaNet의 Windows 커널 지원 상태는 미확인.

## Q6. VLM이 한국어를 직접 쓰기 vs 영어로 쓰고 별도 한국어 LLM으로 번역

### Takeaway
결정적인 근거는 없지만, 기존 근거로 보면 **VLM이 영어 프롬프트와 한국어 라벨·문장을 한 번에 출력하고, 한국어 품질이 부족할 때만 후처리(번역/윤문) 단계를 붙이는** 하이브리드가 합리적이다. text-to-audio 프롬프트는 어차피 영어라야 하고, 소형 다국어 모델의 한국어 생성 품질은 직접 평가해야 한다.

### Cited Findings
- Qwen3.5-4B는 201개 언어 지원, WMT24++(55개 언어 평균) 66.6, 9B는 72.6 — [Qwen/Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B)
- kanana-1.5-v-3b는 MIABench-Ko 91.17, Image(KO) 평균 68.27로 2025년 중반 Qwen2.5-VL-3B(60.60)보다 높음 — [kanana card](https://huggingface.co/kakaocorp/kanana-1.5-v-3b-instruct)
- HCX-SEED-Vision-3B는 Korean VisIT-Bench(자유 생성형) 37.0으로 Qwen2.5-VL-3B 81.5보다 크게 낮음 — [HCX card](https://huggingface.co/naver-hyperclovax/HyperCLOVAX-SEED-Vision-Instruct-3B)
- KMMMU: "Korean-language specialization alone is not enough" — [KMMMU](https://arxiv.org/html/2604.13058v2)
- VARCO-2.0-1.7B는 K-LLaVA-W(자유 서술형) 73.5로 InternVL3-2B 47.6보다 높음. 단 [NC] — [VARCO card](https://huggingface.co/NCSOFT/VARCO-VISION-2.0-1.7B)

### Inferences
- [추정] 2단계(영어 VLM → 한국어 LLM)는 VRAM에 모델 2개를 올리거나 순차 로드해야 해서 12GB에서 지연이 늘고, 라벨과 설명 사이 일관성이 깨질 위험도 있음. 반면 한국어 문장이 "번역투"이거나 어색하면 텍스트 전용 한국어 LLM(예: kanana/EXAONE 계열)으로 윤문하는 효과가 클 수 있음.
- 4~6개 음원 × 짧은 문장 정도는 소량이므로, 오프라인 사전 생성 파이프라인이라면 2단계의 지연 비용은 크게 문제되지 않을 수 있음.
- 권장 평가: 같은 그림 세트에서 (a) Qwen3.5-4B가 한국어를 직접 생성, (b) Qwen3.5-4B 영어 생성 → 한국어 LLM 번역, (c) kanana-1.5-v-3b가 직접 생성을 비교하고 한국어 자연스러움을 사람이 블라인드로 평가.

### Gaps
- 소형 VLM의 한국어 자유 서술(묘사 문장) 품질을 2026년 모델 기준으로 비교한 공개 벤치는 찾지 못함(K-LLaVA-W, Korean VisIT-Bench는 2025년 모델 비교뿐).
- Qwen3.5·Gemma 4·MiniCPM-V 4.7의 한국어 전용 수치는 없음.
- "직접 생성 vs 번역" 파이프라인을 비교한 VLM 연구는 찾지 못함.
