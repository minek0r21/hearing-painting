# 들리는 그림: 소리 나는 물체 위치 찾기(검출 / 오픈 보캐뷸러리 그라운딩 / 분할) 모델 조사

> 조사 시점: 2026-11-25. 환경: Windows PC, RTX 3060 12GB, PyTorch + Hugging Face transformers. 아래 내용 중 출처 URL이 없는 것은 Inferences 또는 Gaps에만 두었다. "(학습지식, 정확하지 않을 수 있음)" 표시는 이번 조사에서 웹으로 확인하지 못한 내용이다.

## Q1. 12GB VRAM에서 돌아가는 최신 오픈 보캐뷸러리 검출기/그라운딩 모델과 transformers 네이티브 지원 여부

### Takeaway
transformers에서 네이티브로 쓸 수 있는 현실적 후보는 Grounding DINO, MM-Grounding-DINO와 LLMDet 체크포인트, Florence-2, SAM 3(텍스트 프롬프트로 마스크와 박스를 출력)이다. 자연 이미지 제로샷 벤치마크에서 가장 앞선 것은 SAM 3이다(LVIS box AP 53.6, SA-Co/Gold cgF1 55.7, OWLv2* 24.5). Grounding DINO 1.5/1.6과 DINO-X는 API로만 제공되어 오프라인 파이프라인에는 맞지 않는다. Rex-Omni(3B)는 transformers 백엔드로 돌릴 수 있지만 별도 패키지가 필요하고 IDEA 연구용 라이선스다.

### Cited Findings
**SAM 3 (Meta, 2025-11 공개)**
- 짧은 명사구, 이미지 예시, 또는 둘 다를 프롬프트로 받아 해당 개념의 **모든 인스턴스**를 검출·분할·추적한다(Promptable Concept Segmentation). transformers에 `Sam3Model`/`Sam3Processor`로 들어가 있고 체크포인트는 `facebook/sam3`이다 — [transformers SAM3 docs](https://huggingface.co/docs/transformers/model_doc/sam3)
- transformers 공식 예시는 `processor.post_process_instance_segmentation(..., threshold=0.5, mask_threshold=0.5)`로 인스턴스 마스크, 박스, 점수를 얻는다 — [transformers SAM3 docs](https://huggingface.co/docs/transformers/model_doc/sam3)
- transformers에 2025-11-19 기여됐다. 파라미터는 848M이다 — [transformers SAM3 docs](https://huggingface.co/docs/transformers/model_doc/sam3), [arXiv 2511.16719](https://arxiv.org/abs/2511.16719v1)
- HF 모델 카드 기준 0.9B 파라미터(F32 safetensors)이고 **gated**(약관 동의 후 다운로드)이며 라이선스 표기는 "other"(SAM License)다 — [HF facebook/sam3](https://huggingface.co/facebook/sam3)
- 공식 저장소 요구사항은 CUDA 12.6 이상, Python 3.12 이상, PyTorch 2.7 이상이다 — [GitHub facebookresearch/sam3](https://github.com/facebookresearch/sam3)
- 제로샷 비교(SAM 3 논문 Table 1)
  - LVIS box AP: SAM 3 53.6 / OWLv2 35.2 / OWLv2*(LVIS로 일부 학습) 45.5 / Grounding DINO-T 20.5 / LLMDet-L 42.0 / DINO-X 52.4
  - COCO box AP: SAM 3 56.4 / OWLv2 38.2 / gDino-T 45.7 / LLMDet-L 55.6 / DINO-X 56.0
  - SA-Co/Gold box cgF1: SAM 3 55.7 / OWLv2* 24.5 / gDino-T 3.4 / LLMDet-L 6.8 / DINO-X 22.5 / Gemini 2.5 14.4
  - 출처: [SAM 3 paper (arXiv 2511.16719v2)](https://arxiv.org/html/2511.16719v2)
- ODinW13 제로샷 AP: SAM 3 61.0 / Grounding DINO 1.5 Pro 58.7 / gDino-T 49.7 / Gemini 2.5 Pro 33.7. RF-100VL에서는 SAM 3 15.2, gDino-T 15.7로 거의 같다 — [SAM 3 paper](https://arxiv.org/html/2511.16719v2)
- 속도: H200에서 객체가 100개 넘는 이미지 한 장을 30ms에 처리한다. 대화형 분할은 43.5 FPS로 SAM 2.1 L의 93.0 FPS보다 느리다 — [SAM 3 paper](https://arxiv.org/html/2511.16719v2)

**Grounding DINO / MM-Grounding-DINO / LLMDet**
- Grounding DINO는 transformers에서 `AutoModelForZeroShotObjectDetection`과 `post_process_grounded_object_detection`으로 쓸 수 있다. 문서는 COCO 제로샷 52.5 AP를 보고한다 — [transformers Grounding DINO docs](https://huggingface.co/docs/transformers/model_doc/grounding-dino)
- MM-Grounding-DINO는 2025-08-01 transformers에 추가됐다. Swin-T/B/L 체크포인트가 있고 COCO 제로샷 50.6 AP다(문서 버전마다 수치가 조금 다르다) — [transformers MM Grounding DINO docs](https://huggingface.co/docs/transformers/en/model_doc/mm-grounding-dino)
- LLMDet 체크포인트는 MM-Grounding-DINO와 같은 방식으로 추론한다. 학습에 쓴 LLM은 포함되지 않은 추론 전용 체크포인트다 — [HF iSEE-Laboratory/llmdet_large README](https://huggingface.co/iSEE-Laboratory/llmdet_large/blob/main/README.md), [transformers MM Grounding DINO docs](https://huggingface.co/docs/transformers/en/model_doc/mm-grounding-dino)

**Florence-2**
- transformers에 네이티브 클래스 `Florence2ForConditionalGeneration`과 `Florence2Processor`가 있다. 변환된 체크포인트(예: `florence-community/Florence-2-base`)는 trust_remote_code 없이 로드되고, 4bit(bitsandbytes) 예시도 있다 — [transformers Florence2 docs](https://huggingface.co/docs/transformers/model_doc/florence2)

**Grounding DINO 1.5/1.6, DINO-X**
- DINO-X는 DeepDataSpace에서 호스팅되는 API로 제공된다. V1 API는 폐기되어 새 SDK가 필요하다 — [GitHub IDEA-Research/dino-x-api](https://github.com/idea-research/dino-x-api)
- Grounding DINO 1.5도 DeepDataSpace에서 호스팅되며, 데모를 돌리려면 API 키가 필요하다 — [GitHub grounding-dino-1.5-api](https://github.com/idea-research/grounding-dino-1.5-api)

**Rex-Omni (IDEA-Research, 2025-10)**
- Qwen2.5-VL-3B 기반의 3B MLLM이다. 검출을 "다음 점(좌표 토큰) 예측"으로 풀고, 박스 하나를 특수 토큰 4개로 표현한다 — [arXiv 2510.12798](https://arxiv.org/html/2510.12798v1)
- `RexOmniWrapper(model_path="IDEA-Research/Rex-Omni", backend="transformers")`로 쓰며, 처리량이 필요하면 vLLM 백엔드도 있다. 별도 `rex_omni` 패키지 설치가 필요하다 — [rex-omni.github.io](https://rex-omni.github.io)
- 라이선스는 IDEA License 1.0이고, 기반 모델인 Qwen 라이선스도 함께 적용된다는 표기가 있다(연구용 성격) — [HF Rex-Omni 모델 페이지(미러)](https://hg.istephan-squireso.workers.dev/IDEA-Research/Rex-Omni)
- AWQ 양자화본이 있다 — [HF IDEA-Research/Rex-Omni-AWQ](https://huggingface.co/IDEA-Research/Rex-Omni-AWQ)

**YOLO-World / YOLOE**
- YOLO-World는 LVIS minival에서 35.4 AP, V100(TensorRT 없이)에서 52.0 FPS다 — [YOLO-World paper](https://arxiv.org/pdf/2401.17270)
- YOLOE-v8-S는 YOLO-Worldv2-S보다 LVIS AP가 3.5 높고, 학습 비용은 1/3, 추론은 1.4배 빠르다 — [YOLOE paper](https://arxiv.org/html/2503.07465v2)
- YOLOE는 Ultralytics 코드베이스 위에서 AGPL-3.0이다. Roboflow 비교표는 YOLO-World를 GPL v3로 적어 두었는데, 공식 저장소에서 확인이 필요하다 — [Roboflow YOLOE](https://playground.roboflow.com/models/thu-mig/yoloe), [Roboflow YOLO-World vs YOLOE](https://playground.roboflow.com/models/compare/yolo-world-vs-yoloe)

### Inferences
- 이 프로젝트의 "이름 목록 → 위치" 단계에는 SAM 3이 가장 유력하다. 텍스트 개념당 모든 인스턴스의 마스크를 주므로 "crows" 같은 복수 객체에 맞고, presence head가 있어 이미지에 없는 개념을 거부하는 능력(SA-Co cgF1)이 다른 모델보다 2배 이상 높다. Florence-2의 "person skating on ice" 같은 환각성 라벨링 문제를 줄이는 데 직접 도움이 될 수 있다(그림 도메인에서는 미검증).
- transformers 5.x에서 SAM 3, Grounding DINO, MM-GDINO/LLMDet, Florence-2를 같은 API(`from_pretrained` + processor post-process)로 쓸 수 있어 파이프라인 교체 비용이 낮다.
- 0.9B인 SAM 3, Grounding DINO base(약 0.2B), OWLv2 base/large는 12GB에서 단일 이미지 추론에 충분할 것으로 보인다(학습지식 기반 추정, 정확하지 않을 수 있음).
- YOLO-World/YOLOE는 실시간성이 강점이지만, 오프라인 분석 단계에서는 속도 이점이 의미가 적다. 아래 OD-LVIS에서 YOLOE의 도메인 강건성이 낮게 나와 우선순위가 낮다.

### Gaps
- OWLv2의 transformers 지원(`Owlv2ForObjectDetection`)과 라이선스(Apache-2.0)는 학습지식이며 이번에 직접 확인하지 않았다(정확하지 않을 수 있음). Grounding DINO 가중치 라이선스(Apache-2.0)도 같은 상태다.
- LLMDet 가중치 라이선스와 MM-GDINO 가중치 라이선스는 확인하지 못했다.
- Grounding DINO 1.6, DINO-X의 오픈 가중치 공개 여부는 확인하지 못했다. 검색 결과상 API 전용으로 보인다.
- SAM 3 이후 후속(예: SAM 3.x)이 2026년에 나왔는지는 확인하지 못했다.
- 각 모델의 RTX 3060 실측 VRAM과 지연시간 데이터는 찾지 못했다.

## Q2. 회화/미술 작품(도메인 시프트)에서의 성능 근거

### Takeaway
사전학습된 오픈 보캐뷸러리 검출기는 그림에서 성능이 크게 떨어진다. Grounding DINO의 DEArt 제로샷 검출 mAP는 0.1이다. 2026년 미술 도메인 비교 연구에서는 OWLv2가 DEArt, IconArt, Watercolor2K 전반에서 가장 좋았다고 보고했지만 절대 mAP는 여전히 낮다. 그림 도메인에서 SAM 3, Florence-2, Qwen3-VL을 직접 비교한 공개 벤치마크는 찾지 못했다.

### Cited Findings
- (2026, Multimedia Tools and Applications) "Open-vocabulary models for object detection and segmentation in visual art: survey and comparative study": 사진과 미술 작품 사이에 도메인 시프트가 있다. DEArt에서 Grounding DINO와 OWLv2는 그림의 오픈 보캐뷸러리 검출 능력을 "일부" 보였지만 mAP는 낮다. 붓 터치, 질감, 왜곡 때문에 물체 경계를 잡기 어렵다 — [Springer MTAP 2026](https://link.springer.com/article/10.1007/s11042-026-21443-y), [ResearchGate](https://www.researchgate.net/publication/401361249_Open-vocabulary_models_for_object_detection_and_segmentation_in_visual_art_survey_and_comparative_study)
- 같은 논문 초록 요약: OWLv2가 DEArt, IconArt, Watercolor2K에서 검출과 그라운딩 모두 최고 성능이었다 — [synapsesocial 초록 페이지](https://synapsesocial.com/papers/69a528ecf1e85e5c73bf04b4) (검색 스니펫 기준. 본문 수치는 접근 실패)
- CIGAr(Khan & van Noord, U. Amsterdam): "trained on natural images and generalise poorly to art." Grounding DINO 제로샷과 미세조정 결과(mAP / mAP@0.5)
  - DEArt 검출: 제로샷 0.1 / 0.4, 미세조정 14.4 / 25.3 (기존 SOTA mAP@0.5 31.2)
  - IconArt: 제로샷 5.4 / 9.2, 미세조정 17.8 / 35.2
  - ArtDL: 제로샷 1.5 / 2.1. 반면 R@10은 66.8로, 후보 상위 10개 안에는 정답이 꽤 들어 있다
  - Ukiyo-eVG(우키요에 그라운딩): GD 제로샷 mAP 19.7, CIGAr 25.1
  - 작은 데이터로 미세조정하면 그라운딩 성능이 오히려 떨어진 경우도 있다
  - 출처: [arXiv 2410.12369](https://arxiv.org/html/2410.12369v1)
- ODOV/OD-LVIS(CVPR 2026 Findings): 유화, 수채화, 인상주의, 고딕 등 예술 스타일을 포함한 15개 도메인, 1,203개 카테고리의 벤치마크다. 전체 AP는 OWL-ViT(ViT-L/14) 21.5, YOLO-World-L 20.2, YOLOE-v11-L 10.3, 제안 방법 DVtor 23.6이다. 도메인별(예술 스타일별) 분해 수치는 없다 — [arXiv 2508.01253](https://arxiv.org/html/2508.01253), [CVF](https://openaccess.thecvf.com/content/CVPR2026F/papers/Zhang_ODOV_Benchmark_the_Open-Domain_Open-Vocabulary_Object_Detection_CVPRF_2026_paper.pdf)
- 기존 미술 검출 데이터셋(Watercolor2K, Clipart1k, Comic2k, Paintings, CASPApaintings)은 대부분 PASCAL-VOC 클래스나 COCO 동물 클래스로 범위가 좁다 — [arXiv 2508.01253](https://arxiv.org/pdf/2508.01253)

### Inferences
- 그림에서는 "정답 박스가 후보에 들어 있지만 순위나 점수가 낮은" 경우가 많다(ArtDL R@10 66.8 대비 mAP 1.5). 그래서 임계값을 낮게 두고 후보를 많이 뽑은 뒤 VLM이나 규칙으로 재검증하는 구조가 유리할 가능성이 높다.
- OWLv2가 미술 비교 연구에서 최고였고 SAM 3 논문에서도 OWLv2*가 SAM 3 다음 수준이었다. 그림 도메인 1차 후보로 OWLv2와 SAM 3을 둘 다 실험할 가치가 있다. 단, SAM 3의 그림 도메인 성능은 근거가 없다.
- Grounding DINO-T는 SA-Co cgF1이 3.4로 매우 낮아, 없는 개념에도 박스를 내는 경향이 강하다. 그림에서 오탐이 많을 수 있다.
- 우키요에(Hokusai) 같은 비서구 판화 양식은 Ukiyo-eVG 결과처럼 특히 어렵다. "waves"처럼 배경·스터프 성격의 음원은 박스 검출보다 분할(semantic mask) 쪽이 더 맞을 수 있다.

### Gaps
- 미술 비교 연구(MTAP 2026) 본문의 모델별 정확한 mAP 표는 접근 실패(Springer 리다이렉트, ResearchGate 403, synapsesocial 429)로 확인하지 못했다.
- PeopleArt 데이터셋 기준 최신 모델 수치는 찾지 못했다.
- SAM 3, Florence-2, Qwen3-VL, Rex-Omni를 미술 작품에서 평가한 공개 결과는 찾지 못했다.
- SA-Co 벤치마크 도메인에 회화나 일러스트가 포함되는지는 확인하지 못했다(논문 부록 미열람).

## Q3. 소형 VLM(Qwen3-VL 4B/8B, InternVL3.5, Gemma 4, MiniCPM-V, Molmo2)의 박스/포인트 그라운딩 신뢰도

### Takeaway
Qwen3-VL과 Molmo2는 0~1000 스케일의 상대 좌표로 박스나 포인트를 출력하며, 단일 지시 대상 그라운딩(RefCOCO)에서는 90% 안팎으로 정확하다. 하지만 "장면 속 모든 인스턴스" 검출에서는 재현율이 낮고, 좌표가 흔들리며(coordinate drift), 중복 예측이 생겨 전용 검출기보다 IoU 정밀도가 떨어진다. 밀집 장면에서는 특히 약하다.

### Cited Findings
- Qwen3-VL: 2B/4B/8B/32B/30B-A3B/235B-A22B(Instruct/Thinking)가 있고 Apache-2.0이며 transformers 4.57.0 이상이 필요하다. 그라운딩은 "Using relative position coordinates, it supports both boxes and points"로 안내된다 — [GitHub QwenLM/Qwen3-VL](https://github.com/QwenLM/Qwen3-VL)
- 여러 논문이 Qwen 계열 좌표를 0~1000 정규화 그리드로 다룬다. 공식 README는 스케일을 명시하지 않았다 — [arXiv 2610.38957](https://arxiv.org/pdf/2610.38957), [arXiv 2605.08560](https://arxiv.org/pdf/2605.08560)
- RefCOCO Acc@0.5(제3자 평가, 각 split 앞 3,000개): Qwen3-VL-2B 88.53, Qwen3-VL-4B 90.60 — [arXiv 2610.35053](https://arxiv.org/pdf/2610.35053)
- Qwen3-VL-8B-Instruct RefCOCO val/testA/testB = 91.6/93.3/87.8. RefCOCO/+/g 8개 split 평균은 88.26이다 — [arXiv 2610.01710](https://arxiv.org/pdf/2610.01710)
- Molmo2(Ai2, 2025-12): 4B, 8B, 7B-O가 있고 포인팅/트래킹 특화 버전도 있다 — [Ai2 blog](https://allenai.org/blog/molmo2), [BusinessWire](https://www.businesswire.com/news/home/20251216910167/en)
- Molmo2-4B: Apache 2.0이지만 학습 데이터 일부는 "academic and non-commercial research use only"다. 포인트는 `<points>` 태그로 나오며 "coordinates are scaled by 1000"이다. `trust_remote_code=True`, transformers==4.57.1 고정, 파라미터 약 5B — [HF allenai/Molmo2-4B](https://huggingface.co/allenai/Molmo2-4B)
- VLM과 검출기 비교(Rex-Omni 논문)
  - COCO 제로샷 F1@IoU0.5: Grounding DINO-T 69.8 / Qwen2.5-VL-3B 64.7 / Qwen2.5-VL-7B 64.0 / Rex-Omni 72.0
  - F1@IoU0.95(정밀 위치): GDINO 23.0 vs Qwen2.5-VL-7B 12.6. VLM의 위치 정밀도가 낮다
  - LVIS(롱테일) F1@0.5: GDINO 47.7 / Qwen2.5-VL-7B 57.7 / Rex-Omni 64.3. 희귀 카테고리 인식은 VLM이 우세하다
  - Dense200(밀집) F1@0.5: GDINO 36.9 / Qwen2.5-VL-7B 1.1 / Rex-Omni 78.4
  - MLLM 검출의 약점으로 "low recall rates, coordinate drift, and duplicate predictions", "large-box prediction"을 지적한다
  - 출처: [arXiv 2510.12798](https://arxiv.org/html/2510.12798v1)
- Gemini 2.5의 SA-Co/Gold box cgF1은 14.4로 SAM 3(55.7)보다 크게 낮다. 범용 VLM의 "모든 인스턴스 찾기" 한계를 보여준다 — [SAM 3 paper](https://arxiv.org/html/2511.16719v2)
- 다른 VLM(ZAYA1-VL-8B) 보고서는 0~1000 정규화를 확인한 뒤에도 박스가 일관되게 부정확했다고 썼다 — [arXiv 2605.08560](https://arxiv.org/pdf/2605.08560)

### Inferences
- VLM 단독 그라운딩은 "소리 나는 대상 하나의 대략적 위치(점)"에는 쓸 만하다. 반면 "까마귀 떼 전부", "군중" 같은 다중·밀집 인스턴스나 정확한 박스 크기가 필요하면 전용 검출기나 SAM 3이 낫다.
- AR 공간 음향에는 2D 중심점만으로도 충분할 수 있으므로, Molmo2/Qwen3-VL 포인팅 결과(0~1000을 이미지 크기로 환산)를 SAM 3 마스크 중심과 교차검증하는 용도가 실용적이다.
- 4B급 VLM은 bf16 기준 약 8~10GB여서 12GB에 들어가지만, 검출기와 동시에 올리면 빠듯할 수 있다(추정, 정확하지 않을 수 있음). 순차 로드/언로드나 4bit 양자화를 고려해야 한다.

### Gaps
- InternVL3.5-4B, Gemma 4, MiniCPM-V 4.x의 그라운딩 출력 형식과 RefCOCO 수치는 이번 조사에서 확인하지 못했다.
- Qwen3-VL 공식 좌표 스케일(0~1000) 명시 문서는 찾지 못했다(제3자 논문에서 간접 확인).
- Qwen3-VL과 Molmo2의 그림 도메인 그라운딩 정확도는 찾지 못했다.
- Rex-Omni 논문의 추론 속도 수치(6.2절)는 미열람이다.

## Q4. 분할(SAM 2/2.1, SAM 3, EfficientSAM)로 음원 위치(마스크 중심)와 크기 보정하기

### Takeaway
SAM 3은 텍스트만으로 마스크를 주므로 "검출 + 분할"을 한 모델로 끝낼 수 있다. 마스크 중심과 면적으로 음원 위치와 크기(음량, 확산 정도)를 계산하기 좋다. 12GB에서 단일 이미지 추론은 가능하다는 보고가 있지만, 객체가 많은 장면에서는 OOM 보고가 있고 공식 Windows 네이티브 지원은 불확실하다.

### Cited Findings
- SAM 3은 SAM 2의 시각 프롬프트(점, 박스) 분할 능력도 개선했다고 주장한다. 트래커는 SAM 2 인코더-디코더 설계를 계승한다 — [SAM 3 paper](https://arxiv.org/html/2511.16719v2)
- 제3자 설치 가이드는 SAM 3 단일 이미지 추론이 12GB에서 가능하다고 보지만 "roughly ~10–12 GB"로 여유가 적고, 배치 시 18~22GB라고 한다. Windows는 WSL2 경로를 권장한다 — [codersera SAM 3 local guide](https://codersera.com/blog/how-to-run-sam-3-locally-2026/)
- A10G(24GB)에서도 후보 검출이나 마스크가 많은 이미지에서 CUDA OOM이 났다는 HF 토론이 있다 — [HF facebook/sam3 discussion #301](https://huggingface.co/facebook/sam3/discussions/301)
- SAM License: Apache 2.0인 SAM/SAM 2와 달리 커스텀 라이선스지만 royalty-free이고 상업 사용이 가능하다는 요약이 있다. 파생물에는 SAM License 사본과 Meta 출처 표기가 필요하다. 군사, 핵, 첩보 용도 금지와 역공학 금지 조항이 있다는 미러 표기도 있다(원문 확인 필요) — [Roboflow SAM 3 license](https://roboflow.com/model-licenses/segment-anything-3), [HF facebook/sam3 LICENSE](https://huggingface.co/facebook/sam3/blob/main/LICENSE), [scancode licensedb sam-2025-11-19](https://scancode-licensedb.aboutcode.org/sam-2025-11-19.html)
- SAM 3의 대화형 이미지 분할 속도는 43.5 FPS로 SAM 2.1 L(93.0 FPS)보다 느리다(H200 기준) — [SAM 3 paper](https://arxiv.org/html/2511.16719v2)

### Inferences
- 마스크 중심은 박스 중심보다 실제 물체 위치를 더 잘 나타낸다. 예를 들어 "마차"처럼 박스 안에 배경이 많은 경우다. 마스크 면적 비율은 소리 크기나 공간 확산(spread)의 가중치로 쓸 수 있다.
- "파도", "군중"처럼 경계가 불분명한 스터프성 음원은 인스턴스 박스보다 SAM 3의 semantic/인스턴스 마스크 합집합이 더 적합할 수 있다.
- Windows 네이티브 transformers 경로(`Sam3Model`)는 공식 저장소의 Triton이나 커스텀 CUDA 의존 없이 PyTorch만으로 돈다고 보이지만, 이번에 확인하지는 못했다(정확하지 않을 수 있음). OOM이 나면 입력 해상도를 낮추거나 fp16/bf16 로드를 시도할 수 있다.
- 다른 검출기(OWLv2, Florence-2, VLM 포인트)로 위치를 얻은 경우, SAM 2.1이나 SAM 3에 박스/점 프롬프트를 넣어 마스크로 정제하는 2단계도 가능하다.

### Gaps
- SAM 2/2.1, EfficientSAM의 transformers 지원 상태와 라이선스는 이번에 직접 확인하지 못했다. 학습지식으로는 SAM 2가 Apache-2.0이고 transformers에 `Sam2Model`이 있지만, 정확하지 않을 수 있다.
- SAM 3의 RTX 3060 실측 VRAM과 속도, Windows 네이티브 동작 여부에 대한 1차 출처는 찾지 못했다.
- SAM License 원문(Meta)은 직접 열람하지 못했다(gated).

## Q5. 파이프라인 구조 비교: (1) 검출기 단독, (2) VLM 그라운딩 단독, (3) VLM이 음원 이름 결정 → 그라운딩 모델이 위치 지정

### Takeaway
이 세 구조를 그림 도메인에서 직접 비교한 연구는 찾지 못했다. 다만 간접 근거는 (3)을 지지한다. VLM은 장면 이해와 롱테일 인식(LVIS)에 강하고, 전용 검출기나 SAM 3은 위치 정밀도(F1@0.95), 다중 인스턴스, 부재 개념 거부(cgF1)에 강하다. 그래서 "VLM이 무엇이 소리를 내는지 정하고, SAM 3/OWLv2가 위치를 잡는" 조합이 각자의 강점을 쓰는 구조다.

### Cited Findings
- 폐쇄형 클래스 검출(Florence-2 `<OD>` 류)은 COCO/LVIS 어휘에 묶여 그림 속 "hunter", "carriage" 같은 맥락 라벨이 generic "person"으로 떨어지기 쉽다. 반면 LVIS 롱테일에서는 VLM(Qwen2.5-VL-7B F1@0.5 57.7)이 Grounding DINO-T(47.7)보다 낫다 — [Rex-Omni paper](https://arxiv.org/html/2510.12798v1)
- 그러나 VLM은 위치 정밀도(F1@IoU0.95: Qwen2.5-VL-7B 12.6 vs GDINO 23.0)와 밀집 장면(Dense200 1.1 vs 36.9)에서 약하다 — [Rex-Omni paper](https://arxiv.org/html/2510.12798v1)
- SAM 3은 presence head로 인식과 위치를 분리한다. 개념이 없을 때 거부하는 능력을 포함한 cgF1이 OWLv2*의 2배 이상이고 Gemini 2.5(14.4)보다 크게 높다. 같은 논문에서 SAM 3을 MLLM과 결합한 "SAM 3 Agent"(MLLM이 질의를 명사구로 분해하고 SAM 3을 도구로 호출) 구성도 제시한다 — [SAM 3 paper](https://arxiv.org/html/2511.16719v2) (SAM 3 Agent 언급은 논문 초록·소개 기준)
- 그림에서는 텍스트 맥락을 넣으면 그라운딩이 좋아진다. CIGAr는 그림 설명 맥락을 넣어 Ukiyo-eVG mAP를 19.7에서 25.1로, DEArt Captions 그라운딩을 19.6에서 29.1로 올렸다 — [arXiv 2410.12369](https://arxiv.org/html/2410.12369v1)
- Grounding DINO 제로샷은 그림에서 R@10은 높지만 mAP는 매우 낮다(ArtDL 66.8 vs 1.5). 후보는 찾지만 점수와 순위가 부정확하다 — [arXiv 2410.12369](https://arxiv.org/html/2410.12369v1)

### Inferences
- 추천 구조 (3) 변형안:
  1. VLM(Qwen3-VL-4B/8B 등)이 그림을 보고 음원 목록을 짧은 영어 명사구로 출력한다. 예: "horse-drawn carriage", "dog", "crow", "ocean wave", "crowd of people". 가능하면 대략적 포인트(0~1000)도 함께 출력한다.
  2. SAM 3(1순위)이나 OWLv2(2순위)에 각 명사구를 넣어 마스크/박스를 얻는다. 임계값은 낮게 두고 후보를 넉넉히 받는다.
  3. VLM 포인트와 가장 가까운 후보를 고르거나, VLM에게 후보 크롭이나 번호 박스를 보여 주고 재검증(verify)시킨다.
  4. 마스크 중심을 음원 위치로, 면적을 크기로 저장한다.
- 이 구조는 Florence-2의 "person skating on ice" 같은 오라벨을 VLM의 장면 이해로, Great Wave에서 3개만 찾은 저재현율을 SAM 3의 개념별 다중 인스턴스 검출로 보완할 수 있다(그림 도메인 실측 근거는 없음, 정확하지 않을 수 있음).
- 12GB 제약에서는 모델을 동시에 올리지 말고 VLM → 언로드 → SAM 3 순서로 순차 실행하는 것이 안전하다(추정).
- 소규모 자체 평가셋(예: 그림 20~30장, 음원 위치 수동 라벨)으로 (1)/(2)/(3)을 직접 비교하는 것이 가장 확실한 근거가 된다. 공개 근거가 부족하기 때문이다.

### Gaps
- "VLM → 그라운딩 검출기" 캐스케이드와 단독 방식의 정확도를 미술 작품에서 직접 비교한 연구는 찾지 못했다.
- SAM 3 Agent의 구체적 벤치마크 수치는 이번에 확인하지 못했다.
