# VLM이 고르고 SAM 3가 짚는 들리는 그림

2026년 11월 기준으로 "들리는 그림"에 가장 맞는 구조는 **VLM이 소리원의 이름·유형·오디오 프롬프트를 정하고, 텍스트 프롬프트 분할 모델이 그 이름으로 위치를 잡는 캐스케이드**다. 추천 스택은 Qwen3.5-4B(소리 설계, Apache-2.0) → SAM 3(그라운딩·분할, SAM License) → Depth Anything 3 Mono-Large(깊이, Apache-2.0; Windows 설치가 막히면 DA2-Large [NC]) → Stable Audio 3 small-sfx/medium(생성, Stability Community License) → LUFS 기반 음량 정규화다. 근거는 분명하다. VLM은 롱테일 인식에 강하지만 정밀 위치와 다중 인스턴스에 약하다(밀집 장면 F1@0.5 1.1). SAM 3는 제로샷 검출 1위이고, 그림에 없는 개념을 거부하는 능력이 다른 모델의 2배 이상이다. 다만 **이 모델들 중 어느 것도 회화에서 공개 평가된 적이 없다.** 기존 검출기의 회화 제로샷 mAP가 0.1까지 떨어진 사례가 있으므로, 최종 선택은 그림 20~30장으로 만든 로컬 평가셋이 결정해야 한다. AR 쪽에서는 ARCore가 세션이 리셋될 때까지 이미지를 지우지 않는다. 그래서 안정화는 앱 수준 상태 기계(Tracking일 때만 보정, Limited일 때 숨김, 앵커 고정)가 맡아야 한다. S5(Max Number Of Moving Images)가 효과 없다는 점은 패키지 소스에서 다시 확인됐다. 유사 사례는 많지만 "회화 + AI 자동 생성 + 깊이 기반 3D 배치 + 폰 AR 시각화 + 그림 간 상호작용"을 모두 갖춘 시스템은 찾지 못했다. 발표에서는 "최초"가 아니라 "조합과 적용 대상"을 차별점으로 내세우는 것이 정확하다.

| 단계 | 현재 | 1순위 | 대안 | 1순위 라이선스 |
|---|---|---|---|---|
| 소리원 결정(소리 설계) | 사람이 작성 | Qwen3.5-4B (bf16, thinking off) | Qwen3.5-9B (NF4 4-bit) / 한국어 비교군 Kanana-1.5-v-3B | Apache-2.0 |
| 위치(그라운딩·분할) | Florence-2-large `<OD>` | SAM 3 (`facebook/sam3`, transformers `Sam3Model`) | OWLv2 / Florence-2 phrase grounding 유지 | SAM License (gated, 상업 가능 요약) |
| 깊이 | Depth Anything V2 Small | DA3MONO-LARGE (0.35B, 상대 깊이 + 하늘 분할) | Depth-Anything-V2-Large-hf [NC] | Apache-2.0 |
| 소리 생성 | Stable Audio Open 1.0 (100 step) | Stable Audio 3 small-sfx (8 step) | SA3 medium(앰비언트 베드) / SAO 1.0 유지 | SCL + Gemma Terms of Use |
| 음량 정규화 | RMS -28 dB | pyloudnorm 통합 LUFS + 피크 -1 dBFS 제한 | — | MIT |

## 이름은 VLM이, 위치는 분할 모델이 맡는 구조가 각자의 약점을 상쇄한다

네 가지 구조를 비교했을 때 결정적 근거는 "VLM과 전용 검출기가 서로 반대 방향으로 강하다"는 점이다. Rex-Omni 논문의 비교에서 롱테일 LVIS(F1@0.5)는 Qwen2.5-VL-7B가 **57.7**로 Grounding DINO-T의 47.7보다 높다. 반면 정밀 위치(F1@IoU0.95)는 **12.6 대 23.0**, 밀집 장면(Dense200)은 **1.1 대 36.9**로 VLM이 크게 진다. 저자들은 MLLM 검출의 약점을 "low recall rates, coordinate drift, and duplicate predictions"로 정리했다 ([Rex-Omni](https://arxiv.org/html/2510.12798v1)). 범용 VLM의 "모든 인스턴스 찾기" 한계는 SAM 3 논문에서도 확인된다. SA-Co/Gold 박스 cgF1에서 Gemini 2.5는 **14.4**, SAM 3는 **55.7**이었다 ([SAM 3 논문](https://arxiv.org/html/2511.16719v2)). 현재 Florence-2에서 관찰된 문제("person skating on ice" 같은 오라벨, Great Wave에서 파도를 3개만 찾음)는 정확히 이 두 축에 해당한다. 오라벨은 장면 이해의 문제이고, 저재현율은 다중 인스턴스 위치의 문제다.

| 구조 | 흐름 | 강점 (근거) | 약점 (근거) | 판정 |
|---|---|---|---|---|
| A. 검출기 단독 (현재) | Florence-2 `<OD>` → 사람이 소리 설계 | 위치가 빠르고 결정적임 | 폐쇄형 어휘라 "hunter", "carriage"가 generic "person"으로 떨어짐 ([Rex-Omni](https://arxiv.org/html/2510.12798v1)); 회화 제로샷 mAP가 매우 낮음(GDINO DEArt 0.1, [CIGAr](https://arxiv.org/html/2410.12369v1)) | 기준선(baseline)으로만 유지 |
| B. VLM 탐지 겸용 | VLM 하나가 이름 + 박스/점 출력 | 모델 하나, 단일 대상 그라운딩 정확(Qwen3.5-4B RefCOCO avg 88.1, [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B)) | 다중·밀집 인스턴스와 정밀 위치에 약함(Dense200 1.1, F1@0.95 12.6, [Rex-Omni](https://arxiv.org/html/2510.12798v1)) | 보조 신호(점 좌표)로 활용 |
| **C. VLM 이름 → 그라운딩 위치** | VLM이 영어 명사구·유형·프롬프트 출력 → SAM 3가 명사구별 마스크 | VLM의 장면 이해 + SAM 3의 다중 인스턴스·부재 개념 거부; SonoWorld(CVPR 2026)와 파노라마 사운드스케이프 프로젝트가 같은 순서를 씀 ([SonoWorld](https://arxiv.org/html/2603.28757), [Panorama](https://barasakar.github.io/projects/project5)) | 모델 2개를 순차 로드해야 함(12GB), 이름이 그라운딩 어휘와 어긋나면 누락 | **추천** |
| D. 이미지 → 소리 직접 | 그림(크롭) → image/video-to-audio | 프롬프트 설계 불필요 | 정지 이미지 전용 고품질 오픈 모델 없음. MMAudio는 단일 이미지를 "not trained for this"인 실험 기능으로만 지원하고 [NC]·Ubuntu에서만 테스트됨 ([MMAudio](https://github.com/hkchengrex/MMAudio)); 위치 정보가 없어 어차피 그라운딩이 필요함 | 제외(발표용 비교 실험만) |

구조 D를 제외하는 근거는 하나 더 있다. AudioX(ICLR 2026)가 회화풍으로 변환한 키프레임에서 Im2Wav(직접 방식)와 Caption2Audio(캡션 후 T2A)를 비교했다. 결과는 지표마다 엇갈렸고, IS·FAD는 오히려 캡션 경유 방식이 나았다 ([AudioX](https://arxiv.org/pdf/2503.10522)). 직접 방식이 품질에서 앞선다는 근거가 없으니, 프롬프트를 검토하고 수정할 수 있는 C의 장점을 포기할 이유가 없다.

C를 구체적으로 짜면 이렇다. VLM이 소리원마다 `{label_ko, desc_ko, prompt_en, ground_phrase_en, source_type, loudness, point(0~1000)}`를 출력한다. `source_type`은 SonoWorld가 VLM에게 정하게 한 point / clustered / ambient 3분류를 그대로 쓴다 ([SonoWorld](https://arxiv.org/html/2603.28757)). point는 SAM 3 마스크 중 VLM 점에 가장 가까운 인스턴스의 중심에 배치한다. clustered(까마귀 떼, 군중)는 같은 명사구로 나온 모든 인스턴스의 합집합 영역에 확산 배치한다. ambient(바람, 파도 소리 전체)는 그라운딩 없이 전방위로 깐다. SAM 3가 명사구를 거부하면(presence head가 "없음"으로 판단) VLM 점과 깊이맵만으로 배치하는 폴백을 둔다. 그림의 맥락 정보를 그라운딩에 넣는 것도 효과가 있다. CIGAr는 그림 설명을 맥락으로 넣어 우키요에 그라운딩 mAP를 **19.7에서 25.1**로 올렸다 ([CIGAr](https://arxiv.org/html/2410.12369v1)). 그래서 VLM이 만든 `ground_phrase_en`은 짧은 명사구로 하되 "ocean wave", "horse-drawn carriage"처럼 구체적으로 쓰게 지시하는 것이 좋다. 12GB 제약에서는 VLM을 로드해 실행하고, 언로드한 뒤 SAM 3, 그다음 깊이 모델 순서로 돌리는 순차 실행이 안전하다(추정이며 정확하지 않을 수 있음).

| 구조 단계 로컬 검증 항목 | 방법 | 판단 기준 |
|---|---|---|
| A/B/C 정확도 비교 | 그림 20~30장에 소리원 목록과 중심점을 수동 라벨링 | 소리원 precision/recall, 중심점 거리(이미지 대각선 대비 %) |
| 다중 인스턴스 재현율 | Great Wave의 파도, 까마귀 떼 등 복수 객체 그림 | 인스턴스 수 재현율 |
| 환각률 | VLM 목록 중 그림에 없는 소리원 비율 | 수동 판정 |
| 전체 지연·VRAM | 순차 로드/언로드로 그림 1장 처리 | `torch.cuda.max_memory_allocated()` 12GB 이내, 1장당 시간 |

## 단계별 모델: 공개 수치 1위와 Windows 설치 위험을 함께 보고 고른다

### SAM 3가 제로샷 검출 1위지만 12GB에서는 여유가 거의 없다

SAM 3는 짧은 명사구를 받아 해당 개념의 **모든 인스턴스**에 대해 마스크·박스·점수를 준다. transformers에 `Sam3Model`/`Sam3Processor`로 네이티브 통합돼 있다 ([transformers SAM3](https://huggingface.co/docs/transformers/model_doc/sam3)). 제로샷 LVIS 박스 AP는 **53.6**으로 OWLv2(35.2), LLMDet-L(42.0), Grounding DINO-T(20.5)보다 높고, API 전용인 DINO-X(52.4)와도 비슷하다. "없는 개념을 거부하는 능력"까지 포함한 SA-Co/Gold cgF1은 **55.7**로 OWLv2*(24.5)의 두 배를 넘는다 ([SAM 3 논문](https://arxiv.org/html/2511.16719v2)). Florence-2의 오라벨 문제를 생각하면 이 거부 능력이 이 앱에서 가장 중요한 지표다. 위험도 있다. 체크포인트는 약관 동의가 필요한 gated 저장소다 ([HF facebook/sam3](https://huggingface.co/facebook/sam3)). 공식 저장소 요구사항은 CUDA 12.6+, Python 3.12+, PyTorch 2.7+다 ([GitHub sam3](https://github.com/facebookresearch/sam3)). 제3자 가이드는 단일 이미지 추론에 "roughly ~10–12 GB"가 든다고 보고 Windows에서는 WSL2를 권한다 ([codersera](https://codersera.com/blog/how-to-run-sam-3-locally-2026/)). 24GB A10G에서 마스크가 많은 이미지로 OOM이 났다는 보고도 있다 ([HF 토론 #301](https://huggingface.co/facebook/sam3/discussions/301)). transformers 경로가 Triton 없이 Windows에서 바로 돈다는 1차 근거는 찾지 못했다(정확하지 않을 수 있음).

회화 도메인 근거는 모든 후보에서 약하다. Grounding DINO의 제로샷 mAP는 DEArt에서 **0.1**, ArtDL에서 **1.5**였다. 그런데 ArtDL의 R@10은 **66.8**이었다. 정답 박스가 후보 안에는 있지만 점수와 순위가 틀린다는 뜻이다 ([CIGAr](https://arxiv.org/html/2410.12369v1)). 2026년 미술 도메인 비교 연구는 OWLv2가 DEArt·IconArt·Watercolor2K에서 검출과 그라운딩 모두 최고였다고 보고했다. 다만 절대 mAP는 여전히 낮았다 ([Springer MTAP 2026](https://link.springer.com/article/10.1007/s11042-026-21443-y)). 그래서 OWLv2를 대안 1순위로 둔다. 운영 원칙도 정해진다. **임계값을 낮춰 후보를 넉넉히 받고, VLM 점 좌표나 VLM 재검증으로 거르는 방식**이 회화에 맞다. 마스크 중심과 박스 중심 중 무엇이 나은지도 실험으로 정해야 한다. SEE-2-SOUND는 공간 오디오에서 마스크를 박스로 근사하는 쪽이 "대체로 더 낫다"고 보고했다 ([SEE-2-SOUND](https://arxiv.org/html/2406.06612v2)).

| 후보 | 크기 | transformers | 라이선스 | 자연 이미지 제로샷 | 회화 근거 | 판정 |
|---|---|---|---|---|---|---|
| **SAM 3** | 0.85~0.9B | 네이티브 `Sam3Model` | SAM License, gated; royalty-free 상업 가능 요약 ([Roboflow](https://roboflow.com/model-licenses/segment-anything-3)) | LVIS AP 53.6, cgF1 55.7 | 없음 | **1순위** |
| OWLv2 | base/large | `Owlv2ForObjectDetection`(학습지식, 정확하지 않을 수 있음) | Apache-2.0(학습지식, 정확하지 않을 수 있음) | LVIS 35.2 (OWLv2* 45.5) | 미술 비교 연구 최고 ([MTAP](https://link.springer.com/article/10.1007/s11042-026-21443-y)) | **대안** |
| Florence-2-large (현재) | 0.77B(학습지식) | 네이티브 `Florence2ForConditionalGeneration` ([docs](https://huggingface.co/docs/transformers/model_doc/florence2)) | MIT(학습지식) | — | 오라벨·저재현율 관찰됨 | 기준선·폴백 |
| MM-Grounding-DINO / LLMDet-L | Swin-T/B/L | 네이티브 ([docs](https://huggingface.co/docs/transformers/en/model_doc/mm-grounding-dino)) | 가중치 라이선스 미확인 | LLMDet-L LVIS 42.0, cgF1 6.8 | 없음 | 비교군 |
| Grounding DINO-T | 약 0.2B(추정) | 네이티브 | Apache-2.0(학습지식) | LVIS 20.5, cgF1 3.4 | DEArt mAP 0.1 | 오탐 위험 커서 제외 |
| Rex-Omni | 3B | 별도 `rex_omni` 패키지 ([사이트](https://rex-omni.github.io)) | IDEA License 1.0(연구용) [NC 성격] | COCO F1 72.0, Dense200 78.4 | 없음 | 비상업 허용 시 실험 |
| YOLOE / YOLO-World | 소형 | Ultralytics | AGPL-3.0 / GPL v3 표기 ([Roboflow](https://playground.roboflow.com/models/compare/yolo-world-vs-yoloe)) | OD-LVIS(예술 스타일 포함) YOLOE-v11-L 10.3 ([ODOV](https://arxiv.org/html/2508.01253)) | 도메인 강건성 낮음 | 제외 |
| Grounding DINO 1.5/1.6, DINO-X | — | API 전용 ([dino-x-api](https://github.com/idea-research/dino-x-api)) | 상용 API | DINO-X LVIS 52.4 | — | 로컬 조건 불충족 |

| 탐지 로컬 검증 항목 | 방법 | 판단 기준 |
|---|---|---|
| Windows 네이티브 SAM 3 로드 | transformers `Sam3Model.from_pretrained("facebook/sam3")`, fp16/bf16 | WSL2 없이 동작하는지 |
| VRAM 피크 | 입력 1024px 기준, 명사구 4~6개 | 12GB 이내, OOM 시 해상도 축소 |
| 부재 개념 거부 | 그림에 없는 명사구("car" 등)를 일부러 입력 | 빈 결과를 반환하는지 |
| 임계값 스윕 | threshold 0.3 / 0.4 / 0.5 | 라벨셋 대비 recall과 precision |
| 마스크 중심 vs 박스 중심 | 같은 소리원에 두 방식 적용 | 수동 라벨 중심점과의 거리 |
| SAM 3 vs OWLv2 vs Florence-2 | 같은 명사구 목록 | 다중 인스턴스 재현율, 처리 시간 |

### 깊이는 라이선스상 DA3 Mono-Large가 유일한 상향 경로이고, 후처리가 체감 품질을 더 좌우한다

Depth Anything V2는 Small만 Apache-2.0이고 Base·Large는 **CC-BY-NC-4.0**이다 ([DA2 GitHub](https://github.com/DepthAnything/Depth-Anything-V2)). 2025-11에 공개된 Depth Anything 3 제품군 중 **DA3MONO-LARGE(0.35B)는 Apache-2.0**이다. 이 모델은 상대 깊이와 하늘 분할을 함께 내고, disparity 기반인 DA2와 달리 깊이를 직접 예측한다 ([DA3 README](https://raw.githubusercontent.com/ByteDance-Seed/Depth-Anything-3/main/README.md)). "상업 사용 가능하면서 DA2-S보다 큰 단안 상대 깊이 모델"은 이것뿐이다. 문제는 설치다. 공식 패키지는 xformers를 요구하고 Windows 언급이 없다. transformers 포트는 비공식 `trust_remote_code` 체크포인트뿐이다 ([bigshanedogg/DA3-LARGE](https://huggingface.co/bigshanedogg/DA3-LARGE)). 막히면 `depth-anything/Depth-Anything-V2-Large-hf`로 체크포인트 이름만 바꾸는 것이 가장 싼 상향이다. DA-2K 정확도는 Small **95.3%**에서 Large **97.1%**로 오른다 ([DA2 논문](https://arxiv.org/pdf/2406.09414)). 단 NC이므로 발표 자료에 표기해야 한다.

새로 나온 Apple Depth Pro 2는 2026-11-19에 공개된 지 6일 된 모델이다. 연구 전용 `apple-amlr` 라이선스이고, 미터 단위 깊이와 하늘=무한대 출력을 낸다 ([HF apple/DepthPro2](https://huggingface.co/apple/DepthPro2)). 메트릭 스케일이 필요 없는 이 앱에서는 무한대 값을 처리하는 추가 작업만 생기므로 우선순위가 낮다. 회화 전용 깊이 벤치마크는 없다. 유일한 정성 근거는 Iris(CVPR 2026)의 보고다. 합성 데이터로만 학습한 Lotus가 "it almost fails to produce meaningful depth on paintings"였다 ([Iris](https://arxiv.org/html/2603.16340)). 그래서 Lotus는 제외한다. 메시가 120×93이라는 점도 판단을 바꾼다. 경계 선명도(Depth Pro 계열의 장점)는 다운샘플에서 대부분 사라진다. 전경·중경·배경 순서, 하늘 처리, 깊이 불연속에서 생기는 늘어짐 처리가 더 중요하다. 3D Ken Burns 연구도 단일 이미지 시차 효과의 주요 난제를 깊이 경계의 디스오클루전으로 짚었다 ([3D Ken Burns](https://arxiv.org/abs/1909.05483v1)). 따라서 모델 교체보다 1~99 퍼센타일 정규화, 하늘 마스크를 최원거리로 고정, 평활화, 불연속 엣지 삼각형 제거가 체감 품질을 더 좌우한다(추론이며 정확하지 않을 수 있음).

| 후보 | 크기 | 라이선스 | 출력 | 설치 경로 | 판정 |
|---|---|---|---|---|---|
| DA2 Small (현재) | 24.8M | Apache-2.0 | 상대 disparity | transformers 네이티브 | 기준선 |
| **DA3MONO-LARGE** | 0.35B | Apache-2.0 ([README](https://raw.githubusercontent.com/ByteDance-Seed/Depth-Anything-3/main/README.md)) | 상대 깊이 + 하늘 분할 | `depth-anything-3` 패키지 + xformers (Windows 미확인) | **1순위** |
| DA2 Base/Large | 97.5M / 335M | CC-BY-NC-4.0 [NC] | 상대 disparity | transformers 네이티브, 이름만 교체 ([가이드](https://huggingface.co/docs/transformers/main/en/tasks/monocular_depth_estimation)) | **대안(설치 위험 최소)** |
| DA3-BASE / SMALL | 0.12B / 0.08B | Apache-2.0 | 다중 뷰 겸용 | 같은 패키지 | 경량 비교군 |
| DA3-LARGE-1.1 | 0.35B | CC BY-NC 4.0 [NC] | 다중 뷰 겸용 | 같은 패키지 | Mono가 있어 불필요 |
| Depth Pro (v1) | — | 미확인 | metric | transformers 네이티브 `DepthProForDepthEstimation` ([docs](https://huggingface.co/docs/transformers/main/en/model_doc/depth_pro)) | "선명 경계" 비교군 |
| Depth Pro 2 | 24M~872M | apple-amlr 연구 전용 [NC] | metric, 하늘=inf | 자체 git 패키지 | 보류(공개 직후) |
| MoGe-2 | 35M~331M | 코드 MIT, 가중치 미명시 | metric + normal | 자체 패키지, Triton 의존 언급 ([GitHub](https://github.com/microsoft/MoGe)) | 보류 |
| Marigold v1-1 | — | OpenRAIL++-M | 확산 기반 | diffusers ([HF](https://huggingface.co/prs-eth/marigold-depth-v1-1)) | 비용 대비 이득 불분명 |
| Lotus | — | — | — | — | 회화 실패 보고로 제외 |

| 깊이 로컬 검증 항목 | 방법 | 판단 기준 |
|---|---|---|
| DA3 Windows 설치 | xformers 사전 빌드 휠([AI-windows-whl](https://github.com/wildminder/AI-windows-whl)) 또는 SDPA 경로 | 설치 성공 여부, 실패 시 DA2-L 확정 |
| DA3 출력 형식 | 출력이 depth인지 inverse depth인지, 하늘 마스크가 확률인지 이진인지 확인 | 정규화 코드 분기 |
| A/B 비교 | DA2-S / DA2-L / DA3MONO-L, 동일 정규화·동일 120×93 메시, 작품 5~10점 | 깊이 순서 오류, 늘어짐 아티팩트 육안 평가 |
| 평탄 배경 가짜 굴곡 | 금박·단색 배경 초상화 | 배경 표면 분산 |
| 입력 해상도 | 518 / 1036 / 1600px | VRAM 피크, 메시 품질 차이 유무 |

### Qwen3.5-4B가 환각·그라운딩·개수 지표를 모두 공개한 유일한 소형 후보다

측정 중인 다섯 후보 가운데 이 작업과 직접 관련된 지표를 모델 카드에 모두 공개한 것은 Qwen3.5-4B뿐이다. 관련 지표는 "보이는 것만"(HallusionBench), "어디에"(RefCOCO), "몇 개"(CountBench)다. 수치는 HallusionBench **65.0**, RefCOCO 평균 **88.1**, CountBench **96.3**, MMMU-Pro 66.3이고, 201개 언어를 지원한다 ([Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B)). Artificial Analysis 독립 측정에서도 MMMU-Pro는 4B 65.4%로 이전 세대 Qwen3-VL-4B의 52.0%보다 높았다 ([Artificial Analysis](https://artificialanalysis.ai/articles/qwen3-5-small-models)). 9B는 HallusionBench 69.3, RefCOCO 89.7로 한 단계 위다. bitsandbytes가 0.47부터 공식 Windows CUDA 휠과 NF4를 지원하므로 ([bitsandbytes](https://huggingface.co/docs/bitsandbytes/v0.47.0/en/installation)) 4-bit로 대안 후보가 된다. 나머지 후보의 상태는 이렇다. Gemma-4-E2B는 Apache-2.0이고 네이티브로 로드되지만 공개 비전 지표가 MMMU-Pro 44.2% 정도다. E4B(52.6%)는 임베딩 포함 8B라 bf16으로는 12GB를 넘을 수 있다(추정이며 정확하지 않을 수 있음) ([Gemma 4 E4B](https://huggingface.co/google/gemma-4-E4B-it)). MiniCPM-V-4.7-1B는 Apache-2.0이고 transformers 5.18 이상에서 네이티브로 돌지만 카드에 수치 벤치마크가 없다 ([MiniCPM-V-4.7-1B](https://huggingface.co/openbmb/MiniCPM-V-4.7-1B)). InternVL3.5-4B-HF는 2025-08 모델이고 벤치마크가 이미지로만 제공된다 ([InternVL3_5-4B-HF](https://huggingface.co/OpenGVLab/InternVL3_5-4B-HF)).

한국어 우대 조건에서는 판단이 미묘하다. Kanana-1.5-v-3B는 자체 측정 Image(KO) 평균 **68.27**로 Qwen2.5-VL-3B(60.60)를 앞선다 ([kanana](https://huggingface.co/kakaocorp/kanana-1.5-v-3b-instruct)). 하지만 비교 대상이 2025년 세대이고 MMMU는 43.89에 그친다. 독립 한국어 벤치마크 KMMMU는 "Korean-language specialization alone is not enough"라고 결론지었다 ([KMMMU](https://arxiv.org/html/2604.13058v2)). 한국어 특화 모델이 2026년 Qwen3.5를 이긴다는 근거는 없다. 그래서 기본 구성은 **Qwen3.5가 영어 오디오 프롬프트와 한국어 라벨·설명을 한 번에 출력**하는 것이다. 한국어 문장이 어색하다고 블라인드 평가에서 판정되면 그때 Kanana를 비교군이나 윤문 단계로 붙인다. VARCO-VISION-2.0-1.7B는 자유 서술형 K-LLaVA-W **73.5**로 강하지만 CC-BY-NC [NC]다 ([VARCO](https://huggingface.co/NCSOFT/VARCO-VISION-2.0-1.7B)). HyperCLOVAX-SEED-3B는 Korean VisIT-Bench **37.0**으로 Qwen2.5-VL-3B(81.5)보다 크게 낮다 ([HCX-SEED](https://huggingface.co/naver-hyperclovax/HyperCLOVAX-SEED-Vision-Instruct-3B)).

| 후보 | 크기 | 라이선스 | 로드 방식 | 환각·그라운딩 공개 지표 | 한국어 근거 | 판정 |
|---|---|---|---|---|---|---|
| **Qwen3.5-4B** | 총 5B | Apache-2.0 | 최신 transformers(main) 필요 | HallusionBench 65.0, RefCOCO 88.1, CountBench 96.3 | 201개 언어, MMMLU 76.1 | **1순위** |
| Qwen3.5-9B (NF4) | 9B | Apache-2.0 | bitsandbytes NF4 | HallusionBench 69.3, RefCOCO 89.7 | MMMLU 81.2 | **대안(품질 우선)** |
| InternVL3.5-4B-HF | 4.7B | Apache-2.0 | 네이티브, transformers≥4.52.1 | 텍스트 수치 없음 | 미확인 | 측정 결과로 판단 |
| Gemma-4-E2B | 실효 2B대 | Apache-2.0 | `AutoModelForMultimodalLM` | MMMU-Pro 44.2, 검출·포인팅 기능은 있으나 수치 없음 | 35+ 언어, 한국어 수치 없음 | 경량 비교군 |
| MiniCPM-V-4.7-1B | 1B (Hub 2B 표기) | Apache-2.0 | 네이티브, transformers≥5.18 | 수치 없음 | 명시 없음 | 경량 비교군 |
| Kanana-1.5-v-3B | 3.6B | kanana license(상업 조건 미확인) | `trust_remote_code` | MMMU 43.89, MMStar 56.32 | Image(KO) 68.27, MIABench-Ko 91.17 | **한국어 비교군** |
| VARCO-VISION-2.0-1.7B | 1.7B | CC-BY-NC-4.0 [NC] | 네이티브 LLaVA-OneVision | HallusionBench 43.0, POPE 88.6 | K-LLaVA-W 73.5 | 비상업 비교군 |
| HyperCLOVAX-SEED-3B | 3.6B | hyperclovax-seed | `trust_remote_code` | MMBench 81.8 | Korean VisIT 37.0 | 제외 |
| Molmo2-4B | 약 5B(F32 저장) | Apache-2.0, 데이터 일부 NC | `trust_remote_code`, transformers 4.57.1 고정 ([HF](https://huggingface.co/allenai/Molmo2-4B)) | 0~1000 점 출력 | 영어 전용 | 좌표 보조용만 |

구현 측면에서 세 가지를 권한다. 첫째, Outlines의 `TransformersMultiModal`로 Pydantic 스키마를 강제한다 ([Outlines](https://dottxt-ai.github.io/outlines/latest/features/models/transformers_multimodal/)). 스키마는 `source_type: Literal["point","clustered","ambient"]`, 소리원 4~6개 리스트 등으로 정의한다. xgrammar는 Windows 휠을 공식 제공한다 ([PyPI xgrammar](https://pypi.org/project/xgrammar)). 이미지→JSON 스키마 준수는 소형 모델의 공통 약점으로 보고됐으므로 ([SO-Bench](https://arxiv.org/abs/2511.21750)) 강제 디코딩을 쓰고, 실패하면 Pydantic 검증 후 재시도하는 이중 장치가 필요하다. 둘째, thinking은 끈다. Qwen3.5 소형은 기본이 off이지만 ([Unsloth](https://unsloth.ai/docs/models/qwen3.5.md)) 런타임에 따라 off 플래그가 무시돼 `<think>` 블록이 JSON 앞에 붙는 버그가 반복 보고됐다 ([llama.cpp #20182](https://github.com/ggml-org/llama.cpp/issues/20182)). 그러니 `apply_chat_template(..., enable_thinking=False)`를 직접 넘기고 출력 앞부분을 검사한다. 권장 비사고 샘플링은 temperature 0.7, top_p 0.8, top_k 20, presence_penalty 1.5다 ([Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B)). 셋째, Windows에서는 Flash Attention 2 대신 `attn_implementation="sdpa"`가 현실적이다(추정이며 정확하지 않을 수 있음). Qwen3.5의 Gated DeltaNet 커널이 Windows에서 느린 경로로 돌 가능성도 확인되지 않았다.

| VLM 로컬 검증 항목 | 방법 | 판단 기준 |
|---|---|---|
| 소리원 정확도 | 그림 20~30장 × 수동 정답 목록 | precision(환각 역지표), recall |
| JSON 성공률 | 강제 디코딩 on/off, 50회 이상 | `json.loads` + Pydantic 통과율 |
| 한국어 품질 | Qwen3.5 직접 생성 vs Qwen3.5 영어 → 번역 vs Kanana 직접 생성 | 블라인드 자연스러움 평점 |
| thinking on/off | 같은 그림 세트 | 환각률 차이, 지연, `<think>` 누출 |
| 점 좌표 정확도 | VLM `point`(0~1000) vs 수동 중심점 | 대각선 대비 오차 % |
| 4B bf16 vs 9B NF4 | 같은 세트 | VRAM 피크, 1장당 지연, 위 지표 |
| Outlines 호환성 | transformers 5.x + Qwen3.5/Gemma 4 | 오류 없이 동작하는지 |

### Stable Audio 3 small-sfx가 SAO 1.0 대비 FAD를 21% 줄이면서 30배 빠르다

현재의 Stable Audio Open 1.0은 여러 독립 표에서 하위권이다. AudioCaps 기준 FAD 4.19, CLAP 0.209로 TangoFlux(2.41 / 0.318)와 MeanAudio(1.74 / 0.321)보다 크게 뒤진다 ([MeanAudio](https://arxiv.org/html/2508.06098v1)). 지금 느끼는 "품질 불확실"과 맞아떨어진다. 2026-05에 공개된 Stable Audio 3는 BBC 효과음 벤치마크에서 이 격차를 메운다. **small-sfx는 FAD 0.395 / CLAP 0.351로 SAO의 0.501 / 0.263보다 낫다.** 8 step 핑퐁 샘플링이라 H200 기준 0.41초로, SAO 100 step의 12.30초보다 훨씬 빠르다. VRAM은 30초 생성 기준 small **1.89 GB**, medium **5.49 GB**이고, 논문은 medium이 RTX 3060급에서 돈다고 명시한다 ([Stable Audio 3](https://arxiv.org/html/2605.17991v1)). 다만 이 수치는 Stability의 자체 평가다. 같은 SAO의 CLAP이 논문마다 0.146~0.263으로 다르므로 논문 간 절대 수치는 직접 비교하면 안 된다. 실무상 걸리는 점도 있다. SA3는 diffusers가 아니라 전용 `stable-audio-3` / `stable-audio-tools` 라이브러리를 쓴다. 출력은 스테레오이고, 접근은 gated이며, 라이선스는 SCL에 T5Gemma 구성요소의 Gemma Terms of Use가 더해진다 ([HF small-sfx](https://huggingface.co/stabilityai/stable-audio-3-small-sfx)). Windows 동작은 확인되지 않았다. Unity에서 3D 공간화하려면 모노 소스가 필요하므로 다운믹스 단계를 추가해야 한다.

AudioCaps 순위가 실제 효과음 품질 순위와 다를 수 있다는 점도 기억할 만하다. Woosh 논문의 내부 SFX 테스트에서는 SAO가 TangoFlux보다 나았다(FD 341 vs 378, CLAP 0.254 vs 0.225) ([Woosh](https://arxiv.org/html/2604.01929v3)). 비상업 허용 시 비교군으로 둘 Woosh-Flow는 AudioCaps와 SFX 모두에서 SAO를 앞선다. 그러나 5초 청크로 학습해 10~12초 루프에는 길이가 불리하고, 출력이 모노 48 kHz다. 정지 이미지를 직접 받는 V2A 계열(MMAudio, HunyuanVideo-Foley, ThinkSound)은 모두 비디오 입력용이다. 회화의 분위기음에는 이들의 강점인 타이밍 동기화가 쓸모없다.

| 후보 | 크기 | 라이선스 | 길이·채널 | VRAM | 품질 근거 | 설치 | 판정 |
|---|---|---|---|---|---|---|---|
| SAO 1.0 (현재) | 1.1B | SCL | 최대 47초 | 12GB 내 동작 중 | BBC SFX FAD 0.501, AudioCaps 하위권 | diffusers `StableAudioPipeline` | 폴백 |
| **SA3 small-sfx** | DiT 459M (HF 0.6B) | SCL + Gemma ToU, gated | 최대 2분, 스테레오 44.1k | 1.89 GB(30초) | FAD 0.395, CLAP 0.351, 8 step | 전용 라이브러리, Windows 미확인 | **1순위** |
| SA3 medium | DiT 1.4B (HF 2B) | SCL + Gemma ToU | 최대 6분 20초 | 5.49 GB(30초) | FAD 0.369, CLAP 0.369, inpainting이 small보다 매끄러움 | 전용 라이브러리 | **대안(앰비언트 베드)** |
| SAO Small | 341M | SCL | 짧음(약 11초, 미검증) | 소형 | — | — | 경량 비교군 |
| MOSS-SoundEffect v2.0 | 약 1.3B | Apache 2.0 패밀리 표기(개별 확인 필요) | 최대 30초, 48k | 미확인 | 수치 미확인 ([GitHub](https://github.com/OpenMOSS/MOSS-TTS)) | 미확인 | 관찰 대상 |
| Woosh-Flow | 337M | 비상업 [NC] | 5초 학습, 모노 48k | 미보고 | AudioCaps FD 109.1 / CLAP 0.372 | 공식 코드 | 비상업 비교군 |
| TangoFlux | 약 515M | 비상업 [NC] ([HF](https://huggingface.co/declare-lab/TangoFlux)) | 최대 30초 | 12GB 내 추정 | AudioCaps 강함, SFX에서 SAO보다 낮음 | — | 비상업 비교군 |
| MMAudio | 621M급 | 가중치 CC-BY-NC [NC] | 기본 8초 | 약 6GB | 단일 이미지는 실험 기능 | Ubuntu만 테스트 | 구조 D 실험용만 |
| HunyuanVideo-Foley | XL/XXL | LICENSE 파일(상업 조건 미확인) | 48k | XL offload 8GB | 비디오+텍스트 입력 | — | 제외 |

음량은 RMS -28 dB에서 **ITU-R BS.1770 기반 LUFS**로 바꾸기를 권한다. pyloudnorm은 `Meter(rate).integrated_loudness()`로 측정하고 `normalize.loudness()`, `normalize.peak()`로 맞추며, MIT 라이선스다 ([pyloudnorm](https://github.com/csteinmetz1/pyloudnorm)). RMS에는 주파수 가중이 없다. 그래서 저역 중심의 바람 소리와 고역 중심의 까마귀 소리가 같은 RMS여도 체감 음량이 다르다. 무음이 많은 산발적 소리는 RMS가 낮게 나와 과증폭되고 노이즈가 드러난다. LUFS의 K 가중과 게이팅이 두 문제를 모두 완화한다(추론이며 정확하지 않을 수 있음). 처리 순서는 모노 다운믹스 → DC 제거·하이패스 → 루프화 → 완성 루프에 LUFS 정규화 → 피크 -1 dBFS 제한으로 한다. 앰비언트 베드는 지금처럼 크로스페이드로 충분하다. 접합부가 거슬리면 SA3의 다중 구간 inpainting으로 [끝 | 시작] 경계만 재생성할 수 있다. 포인트성 소리(까마귀, 웃음)는 루프 대신 원샷 여러 개를 Unity에서 랜덤 간격으로 재생하는 편이 반복감이 적다. 8 step이면 후보를 2개에서 4~8개로 늘리고 CLAP 텍스트-오디오 유사도로 자동 선별하는 것도 시간 안에 가능할 것으로 보인다(RTX 3060 실측 필요).

| 소리 생성 로컬 검증 항목 | 방법 | 판단 기준 |
|---|---|---|
| SA3 Windows 설치·실행 | `stable-audio-3` 라이브러리, small-sfx와 medium | 오류 없이 생성되는지 |
| RTX 3060 생성 시간·VRAM | 10~12초 클립, 8 step | 1클립당 초, VRAM 피크 |
| SAO 1.0 vs SA3 블라인드 비교 | 같은 프롬프트 10~20개 | 선호도, CLAP 점수 |
| 후보 수 × CLAP 선별 | 후보 2 / 4 / 8 | 선별된 결과의 청취 선호도 |
| RMS vs LUFS | 바람·까마귀·군중 혼합 재생 | 체감 음량 편차(청취 평가) |
| 루프 접합 | 크로스페이드 vs SA3 inpainting | 접합부 클릭·반복감 |

## ARCore는 이미지를 스스로 지우지 않으므로 안정화는 앱 상태 기계가 맡는다

이번 보강에서 확인한 핵심 사실은 네 가지다. 첫째, Unity의 `TrackingState.Tracking`이 ARCore의 FULL_TRACKING에 해당한다. ARCore XR Plugin은 2.2부터 이미지가 카메라에 보이지 않으면(ARCore의 LAST_KNOWN_POSE) `TrackingState.Limited`를 보고한다 ([ARCore XR Plugin CHANGELOG](https://docs.unity3d.com/Packages/com.unity.xr.arcore@6.5/changelog/CHANGELOG.html), [Google TrackingMethod](https://developers.google.com/ar/reference/java/com/google/ar/core/AugmentedImage.TrackingMethod)). 따라서 **Limited 프레임의 pose는 "마지막으로 알던 값"이므로 보정 입력으로 쓰면 안 된다.** 둘째, ARCore는 이미지를 정적이라 가정하고 세션이 리셋될 때까지 목록에 유지하며 removed로 표시하지 않는다 ([Unity Discussions](https://discussions.unity.com/t/ar-page-flip-and-instability/1708607/2)). `ARSession.Reset()`은 모든 trackable과 추적 원점을 초기화하는 무거운 작업이다 ([ARSession.Reset](https://docs.unity3d.com/Packages/com.unity.xr.arfoundation@4.2/api/UnityEngine.XR.ARFoundation.ARSession.Reset.html)). 게다가 Reset, 서브시스템 Destroy, 로더 재초기화로도 이전 이미지가 지워지지 않았다는 보고가 있다 ([Unity Discussions](https://discussions.unity.com/t/how-to-clear-all-images-tracked/930083)). 셋째, Google과 Unity 모두 **고정 이미지는 앵커에 붙이라고 공식 권장**한다 ([Google Augmented Images](https://developers.google.com/ar/develop/augmented-images), [AR Foundation 앵커](https://docs.unity3d.com/Packages/com.unity.xr.arfoundation@6.3/manual/features/anchors/introduction.html)). 넷째, S5는 소스 수준에서 무효가 확정됐다. 로컬 패키지 `Runtime/ARCoreImageTrackingSubsystem.cs` 91~102행에 "ARCore doesn't let you set the max number -- it just tracks everything"라는 주석이 있고, setter는 값을 저장만 한다.

| 기존 대책 | 이번 보강 내용 | 근거 |
|---|---|---|
| C1 준비 시간 | `Tracking` 연속 N프레임 + 크기 변화율 수렴 시 스폰. N은 MindAR 기본값인 warmupTolerance 5를 출발점으로 삼음 | Google: 완전 추적 전 pose·크기 추정치 사용 금지 ([Google](https://developers.google.com/ar/develop/augmented-images)); [MindAR 설정](https://hiukim.github.io/mind-ar-js-doc/quick-start/tracking-config) |
| C2 크기 고정 | 레퍼런스 라이브러리에 모니터에 표시된 실제 그림 폭(m)을 자로 재 입력. 크기를 안 주면 ARCore가 paused 상태로 시작함 | [Google](https://developers.google.com/ar/develop/augmented-images) |
| C3 앵커 | `await ARAnchorManager.TryAddAnchorAsync(pose)`로 생성 후 콘텐츠를 자식으로 둠. `AttachAnchor`는 문서상 plane 예시뿐이라 이미지 적용 여부 미확인. 앵커가 2개면 "몇 m 안에 여러 앵커 금지" 권고에 걸리므로 두 그림 중앙에 공용 앵커 1개를 두는 대안도 있음 | [ARAnchorManager 6.3](https://docs.unity3d.com/Packages/com.unity.xr.arfoundation@6.3/manual/features/anchors/aranchormanager.html), [앵커 소개](https://docs.unity3d.com/Packages/com.unity.xr.arfoundation@6.3/manual/features/anchors/introduction.html) |
| C4 데드밴드 | 보정 입력은 `Tracking` 프레임만 사용. 현재의 고정 sharpness 지수 lerp는 정지 시 지터와 이동 시 지연을 동시에 남기므로, 필터가 필요하면 One Euro로 교체(beta=0에서 시작해 정지 지터가 사라질 때까지 mincutoff를 낮추고, 빠른 이동 지연이 사라질 때까지 beta를 올림) | [1€ Filter](https://cristal.univ-lille.fr/~casiez/1euro), [Unity 구현](https://github.com/DarioMazzanti/OneEuroFilterUnity) |
| C5 튐 거부 | 상한을 넘는 편차는 버리되, 같은 방향 편차가 N프레임 연속이면 재앵커(히스테리시스). 재앵커 시 이전 앵커는 `TryRemoveAnchor`로 제거. 수치(데드밴드 1~2 cm / 2~3°, 상한 10~15 cm)는 문헌 근거가 없는 출발값 | Niantic도 "smoothing or a threshold on top"을 권장 ([Niantic](https://community.nianticspatial.com/t/resolved-vps-anchors-jumping-around/2456)) |
| C6 사라짐·겹침 | `Limited`면 숨기고 MindAR식 missTolerance 5프레임 후 lost로 판정. 두 이미지 pose가 겹치면 가장 최근에 `Tracking`된 쪽만 표시. `ARSession.Reset()`은 명시적 "다시 스캔" 버튼에만 쓰고, 세션 생성 직후에는 호출하지 않음 | [Reset 크래시 이슈](https://issuetracker.unity3d.com/issues/xr-android-player-crashes-when-arsession-dot-reset-is-called-after-arsession-is-instantiated-on-the-device), [MindAR](https://hiukim.github.io/mind-ar-js-doc/quick-start/tracking-config) |
| S5 Max Moving Images | 무효 확정. 원인 후보에서 제외 | 로컬 소스 91~102행; 문서는 "requires more CPU resources"만 언급 ([ARTrackedImageManager](https://docs.unity3d.com/Packages/com.unity.xr.arfoundation@6.3/manual/features/image-tracking/artrackedimagemanager.html)) |

기존 분석에 없던 새 점검 대상도 있다. 레퍼런스 이미지 품질은 이미 설치된 `AR_Midterm/Library/PackageCache/com.unity.xr.arcore@c47b8141d7e9/Tools~/Windows/arcoreimg.exe`로 `eval-img`를 실행해 점수를 매긴다. 0~100점 중 **75 이상**을 목표로 하고, 파일명은 ASCII만 허용된다 ([Google arcoreimg](https://developers.google.com/ar/develop/augmented-images/arcoreimg)). 모니터 위 이미지의 moiré·플리커·반사에 대한 Google·Unity 공식 문서는 찾지 못했다. 두 그림을 한 화면에 나란히 띄우면 각 그림이 화면 폭의 절반이 된다. 그러면 가까이 갈수록 한쪽만 보이고 다른 쪽은 `Limited`로 남는다(추론). autofocus 헌팅이 블러를 만들어 점프를 일으킬 가능성도 있다. 이건 근거 문헌 없는 가설이지만 `ARCameraManager.autoFocusRequested`로 쉽게 A/B할 수 있다. ARCore 네이티브 TrackingMethod는 `nativePtr`로 `ArAugmentedImage`를 얻으면 읽을 수 있다 ([ARCore XR Plugin 이미지 추적](https://docs.unity3d.com/Packages/com.unity.xr.arcore@6.3/manual/features/image-tracking.html)). 하지만 Unity 매핑이 이미 1:1이라 실익이 거의 없다(정확하지 않을 수 있음).

| AR 로컬 검증 항목 (S23) | 방법 | 판단 기준 |
|---|---|---|
| arcoreimg 점수 | 두 그림 원본과 "모니터를 폰으로 찍은 정면 크롭본" 각각 평가 | 75 이상, 크롭본 등록 시 추적 품질 차이 |
| 정지 지터 | 폰을 삼각대에 고정하고 30초간 콘텐츠 위치 로깅 | 위치 표준편차(mm), 데드밴드 값 결정 |
| warm-up N과 크기 수렴 | N = 5 / 10 / 15 프레임 | 스폰 후 크기 변화량 |
| autofocus on/off | `autoFocusRequested` A/B | 점프 빈도 |
| 카메라 config | `GetConfigurations()`에서 30fps vs 60fps | 지터, 추적 유지율 |
| 한 화면 2장 vs 1장 전체 화면 | 배치 방식 비교 | 양쪽 모두 `Tracking`인 시간 비율 |
| 앵커 2개 vs 공용 앵커 1개 | 장시간 체험 | 드리프트, 앵커 `Limited` 고착 여부 |
| 라이브러리 재설정 효과 | 같은 DB를 다시 set | 기존 tracked image가 removed로 보고되는지 |

## 선행 연구는 사진을 다뤘고, 제품은 사람이 작곡했다: 차별점은 "조합과 적용 대상"이다

학술 쪽에는 이미 같은 계열의 조합형 파이프라인이 있다. SEE-2-SOUND(2024~25, SIGGRAPH Posters 2025)는 SAM 분할 → Depth Anything 깊이 → 패치별 CoDi 생성 → 5.1채널 렌더링으로 구성되며, VLM 단계는 없다. 저자 스스로 A100에서도 실시간이 아니라고 밝혔다 ([SEE-2-SOUND](https://arxiv.org/html/2406.06612v2)). SonoWorld(CVPR 2026)는 여기에 **VLM이 소리 범주·소스 유형·프롬프트·음량을 정하는 단계**를 넣었다. 베이스라인 대비 소리 방향 오차를 약 47% 줄였다고 보고했지만, 최고 성능은 GPT-5와 Marble 같은 독점 모델에 의존한다 ([SonoWorld](https://arxiv.org/html/2603.28757)). 이 두 연구는 "들리는 그림"의 구조가 학술적으로 타당한 계열이라는 근거가 된다. 동시에 "AI 생성 공간 오디오 자체는 새롭지 않다"는 점도 인정해야 한다. 그림을 대상으로 한 연구는 대부분 비공간 음악 생성이다. 시각장애인을 위한 Krol et al.(2024)은 설계 권고로 "스테레오·리버브로 해석을 돕기"를 제시했지만 공간 오디오를 구현하지는 않았다 ([Krol et al.](https://arxiv.org/html/2405.14188v1)). 제품 쪽에서 가장 가까운 Crossroads AR은 그림 인식 + 폰 AR + 공간 음악을 갖췄다. 하지만 **사람이 녹음한 바이올린 프레이즈 500여 개**로 만들었고 특정 화가 작품에서만 동작한다 ([App Store](https://apps.apple.com/us/app/-/id1668210261)).

| 사례 | 연도 | 입력 | 소리 결정 | 공간화 | 출력·플랫폼 | 들리는 그림과의 차이 |
|---|---|---|---|---|---|---|
| SEE-2-SOUND ([arXiv](https://arxiv.org/html/2406.06612v2)) | 2024~25 | 사진·GIF·비디오 | 패치별 자동 생성, VLM 없음 | 깊이 기반, 5.1ch 직접음 | 오디오 파일, 비실시간 | 회화·AR·시각화 없음 |
| SonoWorld ([arXiv](https://arxiv.org/html/2603.28757)) | 2026 | 단일 사진 | VLM(GPT-5/LLaVA) | 앰비소닉스 + HRTF | 3DGS 자유 시점 | 독점 모델 의존, 회화·폰 AR 아님 |
| Panorama Soundscape ([프로젝트](https://barasakar.github.io/projects/project5)) | 2026 | 파노라마 | InternVL2.5 → Grounding DINO | 역제곱 음량 | 믹스 오디오 | 평가 없음, AR 아님 |
| Krol et al. ([arXiv](https://arxiv.org/html/2405.14188v1)) | 2024 | 그림 | 감정 → 음악 + YOLO 효과음 DB | 미구현(권고만) | 오디오 | 공간 배치 없음 |
| Crossroads AR ([App Store](https://apps.apple.com/us/app/-/id1668210261)) | 2023~25 | 특정 작가 그림 | 사람 녹음 500여 개 | AR 공간 음악 | iOS AR | 수작업, 작품 전용 |
| Dolby "Sound of a Masterpiece" ([Eye News](https://eyenews.uk.com/news/post/dolby-s-sound-of-a-masterpiece-hear-what-da-vincis-mona-lisa-and-monets-water-lily-pond-sound-like)) | 2025 | 명화 7점 | 사람 작곡 | Dolby Atmos | 음반 | AR·AI 없음 |
| Play a Kandinsky ([Google A&C](https://artsandculture.google.com/experiment/sgF5ivv105ukhA)) | 2021 | Kandinsky 1점 | ML + 사운드 아티스트 | 없음 | 웹 클릭 | 공간·AR 없음 |
| Imaginary Soundscape ([Qosmo](https://qosmo.jp/en/news/imaginary-soundscape-v2)) | 2017~22 | 이미지 | 6만여 개 라이브러리 검색 | 없음 | 웹 | 생성이 아닌 검색 |
| Dam et al. VT ([VTechWorks](https://vtechworks.lib.vt.edu/items/0047af18-e96c-4485-80b8-26b649eaef11)) | 2024 | 그림 8점 | 색 기반 알고리즘 vs 음악가 보강 | 오디오 AR | — | 음악가 보강판이 참여도 유의하게 높음 |

발표에서 사실에 기반해 내세울 수 있는 차별점은 네 가지다. 첫째, 사진 대상 조합형 파이프라인(SEE-2-SOUND, SonoWorld)을 **회화에** 적용하고 깊이 기반 3D 배치를 넣었다. 둘째, 기존 연구의 출력이 오디오 파일이나 VR 렌더링이었던 것과 달리 **폰 AR에서 실물 그림 위에 소리 위치를 시각화**한다(사운드 링, 시차 창). 셋째, 조사 범위에서 **여러 그림 사이의 음원 드래그·병합 상호작용** 사례를 찾지 못했다. 넷째, 무거운 생성을 오프라인에서 끝내고 기기는 재생과 공간화만 하는 구조라 SEE-2-SOUND의 비실시간 한계를 아키텍처로 우회한다. "새 그림을 수작업 작곡 없이 추가할 수 있다"는 확장성 주장(Crossroads AR, Dolby 대비)은 **VLM 소리 설계 자동화가 완료돼야 성립한다.** 지금처럼 사람이 쓰는 단계가 남아 있으면 이 주장은 빼야 한다. 반대로 Dam et al.의 결과(음악가가 보강한 오디오가 알고리즘 오디오보다 참여도가 높음)를 보면 "VLM 초안 + 사람 검수"를 단점이 아닌 설계 선택으로 제시할 수도 있다. 평가는 선행 연구를 수업 규모로 축소해 구성할 수 있다. 프롬프트와 생성 오디오 사이의 CLAP 점수, 소수 참가자의 방향·거리 식별 과제, 사실감·몰입 Likert 평가가 그 예다. Krol et al.이 지적한 위험(오해석, 역사적 부정확성, 효과음 과밀)은 한계로 명시한다. 대응책으로는 VLM 프롬프트에 시대·장소를 넣고 소리원 수에 상한을 두는 방식을 제시한다. 검색이 영문 위주였으므로 한국·중국·일본의 유사 앱이나 학생 프로젝트가 누락됐을 수 있다. "최초"라는 표현은 쓰지 않는 것이 안전하다.

## 결론

이번 조사에서 판단이 바뀐 지점은 "어떤 모델이 최강인가"보다 "어떤 근거가 비어 있는가"다. 단계별 1순위(SAM 3, DA3 Mono-Large, Qwen3.5-4B, Stable Audio 3)는 모두 사진·자연음 벤치마크에서 나온 순위다. 회화에서는 검출 mAP가 한 자릿수 이하로 무너진 전례가 있으므로, 이 순위가 그대로 유지된다고 가정할 수 없다. 그래서 그림 20~30장에 소리원 목록과 위치를 직접 라벨링한 평가셋이 모델 선택의 최종 근거가 된다. 이 평가셋은 공개 문헌에 없는 "회화 도메인 소리원 그라운딩" 데이터로서 발표의 실증 자료도 된다. 또 하나는 모델 교체보다 인터페이스 설계의 효과가 더 클 수 있다는 점이다. VLM 출력에 `source_type`(point/clustered/ambient)을 넣으면 군중·파도처럼 박스로 잡기 어려운 소리원을 그라운딩 없이 처리할 수 있다. RMS를 LUFS로 바꾸면 소리 종류 간 체감 음량 편차가 줄어든다. 둘 다 어떤 모델 조합을 고르든 유효하다.

AR 쪽 결론도 같은 방향이다. ARCore는 이미지를 지우지도, 이동 이미지 수를 제한하지도 않으며, 보이지 않을 때도 마지막 pose를 계속 보고한다. 플랫폼 설정으로 해결할 여지는 거의 남아 있지 않다. 안정성은 `Tracking`만 신뢰하고, 앵커에 고정하고, `Limited`를 숨기는 앱 쪽 상태 기계에서 나온다. 이후 개선은 S23에서 정지 지터를 mm 단위로 측정해 데드밴드와 warm-up 값을 정하는 데 집중하는 것이 효율적이다.
