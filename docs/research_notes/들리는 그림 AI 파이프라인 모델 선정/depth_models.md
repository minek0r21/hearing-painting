# 회화(미술 작품)용 단안 깊이 추정 모델 비교 (2026-11 기준)

> 작성일: 2026-11-25. 용도: "들리는 그림" 오프라인 파이프라인 (Windows, RTX 3060 12GB, PyTorch + HF transformers). 현재 사용 중: Depth Anything V2 Small (25M, Apache-2.0, 2024-06).
> 필요 조건: 상대 깊이 순서 + 매끄럽고 아티팩트 없는 표면 (120x93 메시, 음원 배치). metric scale 불필요.
> 표기: [검증] = 이번 조사에서 1차 출처(모델 카드/README/arXiv) 직접 확인, [2차] = 검색 요약/미러/커뮤니티 출처, [구정보] = 2025년 이전 정보.

## 1. 후보 모델: 크기 / 라이선스 / 공개일

### Takeaway
2026-11 현재 실질 후보는 Depth Anything 3 계열(2025-11 공개, DA3MONO-LARGE 0.35B Apache-2.0), Depth Anything V2(S만 Apache, B/L은 CC-BY-NC), Apple Depth Pro 2(2026-11-19 arXiv, 24M~872M, 연구 전용 라이선스), MoGe-2, Marigold v1-1(OpenRAIL++)이다. 상업적 제약 없이 "DA2-S보다 큰" 단안 상대 깊이 모델은 DA3MONO-LARGE(및 DA3-BASE/SMALL)가 사실상 유일하다.

### Cited Findings
**Depth Anything 3 (ByteDance Seed)** [검증]
- 논문·코드·모델 공개일 2025-11-14 (arXiv 2511.10647). 2025-12-11 신규 모델 및 DA3-Streaming 공개 — [DA3 README](https://raw.githubusercontent.com/ByteDance-Seed/Depth-Anything-3/main/README.md)
- 모델 표: DA3NESTED-GIANT-LARGE-1.1 1.40B CC BY-NC 4.0 / DA3-GIANT-1.1 1.15B CC BY-NC 4.0 / DA3-LARGE-1.1 0.35B CC BY-NC 4.0 / DA3-BASE 0.12B Apache 2.0 / DA3-SMALL 0.08B Apache 2.0 / DA3METRIC-LARGE 0.35B Apache 2.0 (metric depth + sky seg) / **DA3MONO-LARGE 0.35B Apache 2.0 (relative depth + sky seg)** — [DA3 README](https://raw.githubusercontent.com/ByteDance-Seed/Depth-Anything-3/main/README.md)
- "-1.1" 체크포인트는 학습 버그 수정 후 재학습된 것으로 기존 버전보다 권장됨(구 버전 deprecated). 단 1.1 공개 날짜는 README에 없음 — [DA3 README](https://raw.githubusercontent.com/ByteDance-Seed/Depth-Anything-3/main/README.md)
- DA3MONO-LARGE 라이선스: README·PyPI·ONNX/LibreYOLO 파생물 모두 Apache-2.0. 단 한 MLX 변환본 페이지는 CC-BY-NC-4.0이라 기재(오기로 보임) — [PyPI depth-anything-3](https://pypi.org/project/depth-anything-3/), [ONNX 변환본](https://huggingface.co/Jens-Duttke/Depth-Anything-3-MONO-ONNX), [LibreYOLO 변환본](https://huggingface.co/LibreYOLO/LibreDepthAnything3l-depth); 상충: [DA3Mono-LARGE-MLX](https://huggingface.co/Jup33QE/DA3Mono-LARGE-MLX)
- README 주장: DA3가 단안 깊이에서 DA2를 "significantly outperforms", DA3 Mono 시리즈는 disparity 기반 DA2와 달리 "directly predicts depth, resulting in superior geometric accuracy". README에는 단안 정량 수치 없음 — [DA3 README](https://raw.githubusercontent.com/ByteDance-Seed/Depth-Anything-3/main/README.md)

**Depth Anything V2** [검증, 구정보 2024-06]
- Small(24.8M) Apache-2.0, Base(97.5M)/Large(335.3M)/Giant(1.3B) CC-BY-NC-4.0 — [DA2 GitHub](https://github.com/DepthAnything/Depth-Anything-V2)
- DA-2K 정확도: Marigold 86.8%, DA2 ViT-S 95.3%, ViT-B 97.0%, ViT-L 97.1%, ViT-G 97.4% — [DA2 논문](https://arxiv.org/pdf/2406.09414)

**Apple Depth Pro 2** [검증, 매우 최신]
- arXiv 2611.26603, v1 제출 2026-11-19. 저자 Peiyun Hu ... Vladlen Koltun. 이미지·비디오 모두에 대해 full resolution dense metric depth; "temporal consistency vs boundary sharpness" 트레이드오프를 해소했다고 주장 — [arXiv 2611.26603](https://arxiv.org/abs/2611.26603)
- 변형: S 24M(97MB) / B 97M(386MB) / L 334M(1.3GB) / H+ 872M(3.5GB) + 공용 focal 추정기 23.5M — [HF apple/DepthPro2](https://huggingface.co/apple/DepthPro2)
- **라이선스: Apple Machine Learning Research Model license (`apple-amlr`), 연구 전용(non-commercial scientific research / academic development)** — [HF apple/DepthPro2](https://huggingface.co/apple/DepthPro2)
- 프로젝트 페이지: Boundary F1(선명도)·Jitter(시간 안정성)를 Sintel/Spring 평균으로 비교(수치는 페이지에 없음). 회화/비사진 이미지 언급 없음 — [Depth Pro 2 프로젝트 페이지](https://apple-aiml-research.github.io/ml-depth-pro-2/)

**Apple Depth Pro (v1)** [구정보 2024-10]
- 2.25MP 깊이맵을 표준 GPU에서 0.3초, metric depth + focal length 추정, 경계 선명도 강조 — [transformers DepthPro 문서](https://huggingface.co/docs/transformers/main/en/model_doc/depth_pro)

**MoGe / MoGe-2 (Microsoft)** [검증(코드), 가중치 라이선스 미확인]
- MoGe-1 `Ruicheng/moge-vitl` 314M (metric 없음) / MoGe-2 `moge-2-vitl` 326M, `-vitl-normal` 331M, `-vitb-normal` 104M, `-vits-normal` 35M (metric scale 지원, normal 옵션) — [MoGe GitHub](https://github.com/microsoft/MoGe)
- 코드 MIT(DINOv2 부분 Apache-2.0); **가중치 라이선스는 README에 명시 없음** — [MoGe GitHub](https://github.com/microsoft/MoGe)
- README에 "MoGe-3 dependency FlexGEMM"(Triton 의존) 언급 → 레포가 MoGe-3까지 진행된 것으로 보이나 세부는 미확인 — [MoGe GitHub](https://github.com/microsoft/MoGe)

**Marigold (ETH, 확산 기반)** [2차]
- marigold-depth-v1-1: CreativeML Open RAIL++-M, diffusers 라이브러리용. marigold-depth-lcm-v1-0은 Apache-2.0이지만 deprecated → v1-1 사용 권장. 코드 자체는 Apache-2.0 — [HF prs-eth/marigold-depth-v1-1](https://huggingface.co/prs-eth/marigold-depth-v1-1), [HF marigold-depth-lcm-v1-0](https://huggingface.co/prs-eth/marigold-depth-lcm-v1-0), [Marigold GitHub](https://github.com/prs-eth/marigold)

**Distill-Any-Depth** [2차]
- small/base/large ≈ 24.8M/97.5M/335.3M; 코드 MIT, **가중치 라이선스 미확인**. Base/Large는 DA2 teacher에서 증류되어 비상업 조건 승계 가능성 있음(추정) — [Gitee 미러](https://gitee.com/xueyoo/Distill-Any-Depth), [PromptLayer 요약](https://www.promptlayer.com/models/distill-any-depth)

**Iris (CVPR 2026)** [검증]
- 확산 모델에 실세계 prior를 주입하는 결정론적 MDE, arXiv 2603.16340 (2026-03-17). 코드 레포 링크 존재, 가중치 공개 여부는 논문에 명시 없음 — [arXiv 2603.16340](https://arxiv.org/abs/2603.16340), [Iris GitHub](https://github.com/NUST-Machine-Intelligence-Laboratory/Iris)

### Inferences
- "상업 사용 가능 + DA2-S 대비 대형"이라는 조건을 만족하는 것은 DA3MONO-LARGE(0.35B), DA3-BASE(0.12B)뿐. 과제(비상업) 용도라면 DA2-Large, DA3-LARGE-1.1, Depth Pro 2도 라이선스상 사용 가능하나 반드시 "비상업/연구 전용" 표기 필요.
- Depth Pro 2는 공개 6일차라 커뮤니티 검증·Windows 사례가 거의 없음.

### Gaps
- Lotus, Metric3D v2, UniDepth v2, VGGT의 2026-11 현재 라이선스·버전은 이번 조사에서 1차 확인하지 못함(도구 호출 한도). VGGT는 다중 뷰 재구성 모델이라 단일 회화 이미지 용도엔 부적합할 가능성이 높지만 확인 안 됨.
- DA3MONO-LARGE 공식 HF 페이지(huggingface.co/depth-anything/DA3MONO-LARGE)를 직접 열지 못함 — README 표와 파생물 기준으로만 Apache-2.0 확인.
- Depth Pro v1(`apple/DepthPro-hf`)의 정확한 가중치 라이선스 미확인.
- 2026년에 나온 기타 신규 단안 모델(예: DA3 후속, Marigold 후속)은 체계적으로 조사하지 못함.

## 2. transformers 네이티브 지원(pipeline('depth-estimation')) vs 별도 레포

### Takeaway
transformers에 네이티브로 들어있는 것은 Depth Anything(V1/V2), DepthPro(v1), ZoeDepth, DPT 계열 등이며, DA3·Depth Pro 2·MoGe는 각자 레포(pip 패키지)가 필요하다. Marigold는 transformers가 아니라 diffusers. 현재 파이프라인을 가장 적게 바꾸는 업그레이드는 `depth-anything/Depth-Anything-V2-Base-hf`/`-Large-hf` 체크포인트 교체다.

### Cited Findings
- transformers 깊이 추정 가이드는 Depth Anything V2(상대 깊이)와 ZoeDepth(절대 깊이)를 예시로 사용, `pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-base-hf")` — [transformers 단안 깊이 가이드](https://huggingface.co/docs/transformers/main/en/tasks/monocular_depth_estimation)
- DepthPro(v1)는 transformers에 `DepthProForDepthEstimation`, 체크포인트 `apple/DepthPro-hf`; 기본 입력 1536x1536, `use_fov_model=False`로 FOV 인코더 끄면 연산 절감, SDPA 기본 사용, fp16/bf16 권장 — [transformers DepthPro 문서](https://huggingface.co/docs/transformers/main/en/model_doc/depth_pro)
- DA3 사용법: 자체 패키지 `DepthAnything3.from_pretrained(...).inference(images)`, 출력 depth/conf/extrinsics/intrinsics. README에 transformers 통합 언급 없음 — [DA3 README](https://raw.githubusercontent.com/ByteDance-Seed/Depth-Anything-3/main/README.md)
- DA3의 공식 transformers 통합은 확인되지 않음; 커뮤니티 포트(`bigshanedogg/DA3-*`)가 `AutoModelForDepthEstimation.from_pretrained(..., trust_remote_code=True)`로 로드 가능하며 "not an official release"라고 명시 — [bigshanedogg/DA3-BASE](https://huggingface.co/bigshanedogg/DA3-BASE), [bigshanedogg/DA3-LARGE](https://huggingface.co/bigshanedogg/DA3-LARGE)
- Depth Pro 2: `pip install "git+https://github.com/apple-aiml-research/ml-depth-pro-2"` 후 자체 `DepthPro2.from_pretrained(...)`; 카드에 transformers 지원 언급 없음 — [HF apple/DepthPro2](https://huggingface.co/apple/DepthPro2)
- MoGe: 자체 패키지(`moge infer` CLI, Python ≥3.10) — [MoGe GitHub](https://github.com/microsoft/MoGe)
- Marigold v1-1: diffusers 파이프라인으로 사용 — [HF prs-eth/marigold-depth-v1-1](https://huggingface.co/prs-eth/marigold-depth-v1-1)

### Inferences
- 비공식 `trust_remote_code` 포트는 임의 원격 코드를 실행하므로, DA3를 쓸 경우 공식 `depth-anything-3` 패키지 사용이 더 안전.
- DepthPro(v1)는 transformers 네이티브라 설치 부담이 가장 적은 "선명 경계형" 대안.

### Gaps
- transformers 최신 릴리스(v5.x)의 depth-estimation 지원 아키텍처 전체 목록을 1차 문서로 확인하지 못함(작업 페이지는 "Depth Estimation task page"로 위임).

## 3. 회화/일러스트/비사진 이미지에서의 성능 근거

### Takeaway
회화 전용 깊이 벤치마크는 찾지 못했다. 근거는 정성적 사례 수준: Iris 논문(CVPR 2026)이 "Lotus는 회화에서 거의 의미 있는 깊이를 못 만든다"고 보고했고, 2022년 만화(comics) 연구는 자연 이미지 학습 모델이 비사진 도메인에서 실패한다고 보고했다. 즉 모델 선택만큼이나 실제 작품 몇 장으로 직접 비교 테스트하는 것이 중요하다.

### Cited Findings
- Iris 부록 D / Fig. S3: Lotus는 "it almost fails to produce meaningful depth on paintings", Iris는 "recovers plausible and detailed depth for these challenging artistic images". 부록에서 Iris가 "Lotus and Depth Anything V2"보다 경계가 선명하다고 하나 회화 패널과 직접 연결되진 않음 — [Iris arXiv HTML](https://arxiv.org/html/2603.16340)
- One Diffusion 논문: 회화 등 open-world 이미지 처리에 강하다고 주장하지만 정량평가는 NYUv2/DIODE뿐 — [One Diffusion arXiv](https://arxiv.org/pdf/2411.16318) [2차, 구정보]
- 만화 도메인 깊이(WACV 2022): SOTA 자연 이미지 깊이 모델이 만화에서 실패 → 만화를 자연 이미지 도메인으로 변환 후 추정. scale/shift-invariant loss 기반 다중 데이터 학습이 회화·만화로 잘 일반화되지 않는다고 기술 — [Bhattacharjee et al. WACV 2022](https://openaccess.thecvf.com/content/WACV2022/papers/Bhattacharjee_Estimating_Image_Depth_in_the_Comics_Domain_WACV_2022_paper.pdf), [ar5iv 2110.03575](https://ar5iv.labs.arxiv.org/html/2110.03575) [구정보, MiDaS 세대 대상]
- Art2Real: 회화→사실 이미지 변환으로 도메인 갭 감소(분류/검출/분할 실험, 깊이 아님) — [Art2Real arXiv](https://arxiv.org/html/1811.10666) [구정보]
- 3D Ken Burns (Niklaus et al., SIGGRAPH Asia/TOG 2019): 단일 이미지 → 깊이 추정 → 가상 카메라 경로로 시차(parallax) 합성 + 디스오클루전 inpainting. 기존 단안 깊이의 기하/의미 왜곡이 주요 난제라고 지적 — [arXiv 1909.05483](https://arxiv.org/abs/1909.05483v1), [Adobe Research](https://research.adobe.com/publication/3d-ken-burns-effect-from-a-single-image) [구정보]
- Depth Pro 2 프로젝트 페이지·HF 카드에 회화/비사진 이미지 언급 없음 — [Depth Pro 2 프로젝트 페이지](https://apple-aiml-research.github.io/ml-depth-pro-2/)

### Inferences
- 순수 합성 데이터 학습 확산 모델(Lotus)은 회화에서 취약하다는 보고가 있으므로 Lotus는 후보에서 제외 권장.
- DA2/DA3는 대규모 실사 pseudo-label(unlabeled real images)로 학습되어 도메인 일반화가 강한 편으로 알려져 있으나, 회화에 대한 정량 근거는 없음 → 사용할 작품 5~10점으로 A/B 테스트 권장.
- 3D Ken Burns 연구가 보여주듯 "시차 창(3D window)" 품질은 깊이 경계에서의 디스오클루전 처리에 크게 좌우되며, 120x93 저해상 메시에선 오히려 경계 블러/평활화가 늘어짐(stretching) 아티팩트를 줄이는 데 유리할 수 있음.

### Gaps
- 회화(유화·수묵화·인상파 등) 대상 정량 벤치마크/데이터셋은 찾지 못함.
- DA3 vs DA2 vs Depth Pro 2를 회화에서 비교한 커뮤니티 자료 미발견.

## 4. 선명도 vs 매끄러움, 하늘/평탄 배경, 출력 유형(relative/affine/metric)의 함의

### Takeaway
Depth Pro/Depth Pro 2/Marigold는 "선명한 경계"를 목표로 하고, DA2는 disparity(역깊이, affine-invariant)를 출력해 하늘이 자연히 0 근처로 수렴한다. DA3MONO-LARGE는 깊이를 직접 예측하고 sky segmentation을 함께 제공하므로, 하늘/무한원 영역을 마스크로 따로 처리해야 한다. 메시용으로는 "부드러운 상대 깊이 + 하늘 마스크" 조합이 가장 다루기 쉽다.

### Cited Findings
- DA2는 disparity 기반, DA3 Mono는 depth 직접 예측 — [DA3 README](https://raw.githubusercontent.com/ByteDance-Seed/Depth-Anything-3/main/README.md)
- DA3MONO-LARGE/DA3METRIC-LARGE는 Sky Seg 지원, DA3METRIC 출력은 `metric_depth = focal * net_output / 300` — [DA3 README](https://raw.githubusercontent.com/ByteDance-Seed/Depth-Anything-3/main/README.md)
- Depth Pro 2 출력: 미터 단위 metric depth (H, W), **하늘 등 무한원 영역은 infinite depth**; 디코더는 내부적으로 inverse depth 예측. bf16 GPU 실행 — [HF apple/DepthPro2](https://huggingface.co/apple/DepthPro2)
- Depth Pro 2는 "단일 프레임 방법은 선명도를 선호"한다는 트레이드오프를 언급하며 선명도+안정성 동시 달성을 주장 — [arXiv 2611.26603](https://arxiv.org/abs/2611.26603)
- Depth Pro(v1)는 "unparalleled sharpness and high-frequency details" 강조 — [transformers DepthPro 문서](https://huggingface.co/docs/transformers/main/en/model_doc/depth_pro)
- Marigold는 선명하지만 때로 grainy(입자성) 아티팩트, Depth Anything은 일부 데이터셋에서 덜 선명 — [PrimeDepth arXiv](https://arxiv.org/html/2409.09144v1) [2차 검색 요약 경유, 구정보]
- DA2 논문: Marigold는 반사(reflection) 처리 부족 — [DA2 논문](https://arxiv.org/pdf/2406.09414) [2차 검색 요약 경유]
- MoGe-2: metric scale 지원, `-normal` 변형은 법선맵 동시 출력 — [MoGe GitHub](https://github.com/microsoft/MoGe)

### Inferences
- 우리 용도(메트릭 불필요, 매끄러운 표면)에서는 metric 모델(Depth Pro 2, DA3METRIC, MoGe-2)의 장점이 거의 없고, 오히려 하늘=inf 같은 값 처리(클램프/마스크)가 추가 작업이 됨.
- DA2/DA3 출력은 affine-invariant(스케일·시프트 미정)이므로 메시 생성 시 정규화(예: 1–99 percentile clip → [near, far] 매핑)가 필수. disparity 출력을 depth로 바꿀 때 1/x 변환은 원경을 폭발적으로 늘리므로, "3D window"용으로는 disparity를 그대로 선형 매핑하는 편이 안정적일 가능성이 높음(추론).
- 120x93 메시는 원본의 1/10 이하 해상도이므로 고주파 경계 선명도(Depth Pro 계열의 장점)는 대부분 다운샘플 시 사라짐 → 선명도보다 대규모 깊이 순서의 정확성(전경/중경/배경 레이어)과 하늘 처리가 더 중요.
- Marigold의 grainy 아티팩트는 다운샘플·가우시안 블러로 상당 부분 제거 가능하나, 확산 추론 비용 대비 이득이 불분명.

### Gaps
- DA3MONO-LARGE 출력이 depth인지 inverse depth인지, 하늘 마스크 출력 형식(확률/이진)을 1차 코드로 확인하지 못함.
- 회화의 평탄한 배경(금박, 단색 배경, 초상화 배경)에서 각 모델이 만드는 가짜 굴곡(hallucinated relief) 비교 자료 없음.

## 5. 실무: VRAM(~1600px, 12GB), 속도, Windows 이슈

### Takeaway
1차 출처에 RTX 3060에서 1600px 입력 시 VRAM 수치를 제공한 모델은 없었다. DA3 공식 레포는 xformers를 요구하며 Windows 언급이 없고, 커뮤니티에서 xformers 빌드 문제 회피 사례가 보고된다. transformers 네이티브 모델(DA2, DepthPro v1)이 Windows 설치 리스크가 가장 낮다.

### Cited Findings
- DA3 설치: `xformers`, `torch>=2`, `torchvision`, `pip install -e .`; Gradio 앱은 Python ≥3.10; Gaussian head는 특정 gsplat 커밋 필요(우리 용도엔 불필요). xformers 미지원 GPU 우회법은 Issue #11 참조. Windows 언급 없음 — [DA3 README](https://raw.githubusercontent.com/ByteDance-Seed/Depth-Anything-3/main/README.md)
- DA3 HF Space 커밋: "Manual dependencies to avoid xformers build issue" — [HF Space 커밋](https://huggingface.co/spaces/tonyyang2000/depth-anything-v3/commit/a4bb6233c6772d9ac55ce5e9a2120252b41b58dc) [2차]
- Windows용 xformers 사전 빌드 휠은 커뮤니티 제공(특정 torch/CUDA/Python 조합만) — [AI-windows-whl](https://github.com/wildminder/AI-windows-whl) [2차]
- DA3-Streaming은 긴 비디오를 12GB 미만 GPU 메모리로 처리 — [DA3 README](https://raw.githubusercontent.com/ByteDance-Seed/Depth-Anything-3/main/README.md)
- 커뮤니티 DA3 포트(`bigshanedogg/DA3-BASE`)는 `depth_anything_3` 패키지 없이 trust_remote_code로 로드된다고 기술 → xformers 회피 경로 가능성 — [bigshanedogg/DA3-BASE](https://huggingface.co/bigshanedogg/DA3-BASE) [2차]
- MoGe: ViT-L FP16 기준 A100 또는 RTX 3090에서 이미지당 60ms; `--resolution_level` 0–9(기본 9), `--num_tokens` 1200–2500으로 속도/디테일 조절(출력 크기는 불변). uv 설치 시 torch가 CUDA 13.0 휠 인덱스로 고정 → 변경 필요할 수 있음. macOS 미지원(FlexGEMM/Triton), Windows 언급 없음 — [MoGe GitHub](https://github.com/microsoft/MoGe)
- Depth Pro(v1): 2.25MP를 표준 GPU에서 0.3초; 기본 1536x1536 입력; FOV 끄면 연산 절감; fp16/bf16 권장 — [transformers DepthPro 문서](https://huggingface.co/docs/transformers/main/en/model_doc/depth_pro)
- Depth Pro 2: 속도·VRAM 수치 없음; bf16 GPU 실행, 입력 full resolution 처리; 비디오는 16프레임 단위; 예제가 `av` 패키지 사용 — [HF apple/DepthPro2](https://huggingface.co/apple/DepthPro2)

### Inferences
- Triton 의존(MoGe 최신 레포)은 Windows에서 공식 Triton 휠이 없어 문제가 될 수 있음(Linux 우선 요구사항으로 간주, 확인 필요).
- Depth Pro 2 H+(872M)를 1600px full-resolution으로 돌리면 12GB에서 빠듯할 수 있음 → S/B/L 중 선택 또는 입력 축소 필요(추론, 미검증).
- DA2/DA3는 ViT 패치 14 기반이라 입력을 키우면 토큰 수가 제곱으로 늘어남. 메시가 120x93이므로 518~1036px 입력으로 충분하고, 1600px까지 올릴 이유는 작음(추론).
- 오프라인 일괄 처리이므로 속도는 사실상 결정 요인이 아님(작품 수십 점 × 수 초).

### Gaps
- RTX 3060 12GB, 1600px 기준 각 모델 VRAM/시간 실측 자료 미발견 → 직접 측정 필요(`torch.cuda.max_memory_allocated()`).
- DA3 Issue #11(xformers 미지원 GPU 우회) 내용 미확인.
- Depth Pro 2 레포의 Windows 호환성(av, 커스텀 CUDA 커널 여부) 미확인.

## 6. 종합 추천

### Takeaway
1순위: **DA3MONO-LARGE (0.35B, Apache-2.0, 상대 깊이 + sky seg)** — 라이선스 제약 없이 DA2-S 대비 큰 개선이 기대되는 유일한 단안 전용 모델. 단 별도 패키지 + xformers로 Windows 설치 리스크가 있음. 2순위(설치 리스크 최소): **Depth-Anything-V2-Large/Base-hf** — transformers 체크포인트만 바꾸면 되나 CC-BY-NC(과제용으론 허용, 표기 필요). Depth Pro 2는 연구 전용 라이선스·공개 직후·metric/inf-sky 출력이라 이번 용도엔 우선순위 낮음.

### Cited Findings
- DA3MONO-LARGE: 0.35B, Rel. Depth + Sky Seg, Apache 2.0; DA2 대비 우월 주장 — [DA3 README](https://raw.githubusercontent.com/ByteDance-Seed/Depth-Anything-3/main/README.md)
- DA2-B/L: CC-BY-NC-4.0, transformers 네이티브 — [DA2 GitHub](https://github.com/DepthAnything/Depth-Anything-V2), [transformers 단안 깊이 가이드](https://huggingface.co/docs/transformers/main/en/tasks/monocular_depth_estimation)
- DA2 S→L DA-2K 정확도 95.3% → 97.1% — [DA2 논문](https://arxiv.org/pdf/2406.09414)
- Depth Pro 2: apple-amlr 연구 전용, metric + 하늘 inf, 2026-11-19 공개 — [HF apple/DepthPro2](https://huggingface.co/apple/DepthPro2), [arXiv 2611.26603](https://arxiv.org/abs/2611.26603)
- Lotus의 회화 실패 사례 — [Iris arXiv HTML](https://arxiv.org/html/2603.16340)

### Inferences
- 권장 절차: (1) 대표 작품 5~10점으로 DA2-S(현행) / DA2-L / DA3MONO-LARGE를 동일 정규화·동일 120x93 메시로 비교, (2) DA3 설치가 Windows에서 막히면 xformers 사전빌드 휠 또는 xformers 없는 경로(SDPA) 시도, 그래도 안 되면 DA2-L로 확정. (3) 선택 사항으로 Depth Pro(v1, transformers 네이티브)를 "선명 경계" 비교군으로 추가.
- 어떤 모델이든 메시용 후처리(percentile 정규화, 하늘 마스크 → 최원거리 고정, 가우시안/bilateral 평활, 깊이 불연속 엣지의 삼각형 제거 또는 늘림 제한)가 모델 교체보다 체감 품질에 더 큰 영향을 줄 가능성이 높음(추론, 3D Ken Burns의 디스오클루전 문제 지적에 근거 — [arXiv 1909.05483](https://arxiv.org/abs/1909.05483v1)).
- 정확하지 않을 수 있음: DA3가 회화에서도 DA2보다 낫다는 직접 증거는 없음(README 주장은 실사 벤치마크 기준).

### Gaps
- 회화 도메인에서의 정량 비교 부재 → 사용자 측 직접 실험이 유일한 근거가 됨.
- DA3MONO-LARGE의 Windows 설치 성공 사례 미확인.
