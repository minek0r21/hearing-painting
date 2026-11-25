# ARCore 이미지 트래킹 콘텐츠 안정화 (AR Foundation 6.x / ARCore XR Plugin 6.3.5) — 보충 조사

기준일: 2026-11-25. 기존 1차 분석에서 이미 찾은 원인 7개와 계획한 대책은 반복하지 않고, 빠진 부분만 다룸.
로컬 근거: 사용자 프로젝트에 설치된 패키지 소스 `AR_Midterm/Library/PackageCache/com.unity.xr.arcore@c47b8141d7e9/` (설치된 버전 = 6.3.5로 가정함. package.json은 확인하지 않음).

## Q1. ARCore TrackingMethod(FULL_TRACKING / LAST_KNOWN_POSE)와 Unity TrackingState의 대응, Unity에서 TrackingMethod를 읽을 수 있는가

### Takeaway
ARCore XR Plugin은 2.2부터 이미지가 카메라에 보이지 않으면(=LAST_KNOWN_POSE) `TrackingState.Limited`, 카메라로 직접 추적 중이면(=FULL_TRACKING) `Tracking`을 보고함. 따라서 Unity에서는 **`trackingState == Tracking`이 사실상 FULL_TRACKING에 해당**함. 별도 TrackingMethod 프로퍼티는 없고, `nativePtr`로 native `ArAugmentedImage` 핸들을 얻어야만 직접 읽을 수 있음.

### Cited Findings
- Google 원문: FULL_TRACKING = "The Augmented Image is currently being tracked using the camera image." / LAST_KNOWN_POSE = "currently being tracked based on its last known pose, because it can no longer be tracked using the camera image." 두 값 모두 "This state can only occur when the image motion TrackingState is TRACKING." NOT_TRACKING은 PAUSED/STOPPED에 대응 — [Google AugmentedImage.TrackingMethod](https://developers.google.com/ar/reference/java/com/google/ar/core/AugmentedImage.TrackingMethod)
- 즉 native ARCore에서는 LAST_KNOWN_POSE여도 TrackingState는 TRACKING임. 그런데 Unity ARCore XR Plugin 2.2.0-preview.2(2019) 변경 이력: 이미지 tracking state를 "will change the tracking state to `TrackingState.Limited` if the image cannot be seen." (오래된 정보지만 이후 이를 뒤집는 변경 이력은 6.5 changelog에 없음) — [ARCore XR Plugin CHANGELOG 6.5](https://docs.unity3d.com/Packages/com.unity.xr.arcore@6.5/changelog/CHANGELOG.html)
- Google 권장: 처음 감지된 이미지는 pose/size 추정치를 full tracking 전에는 쓰지 말 것. 물리 크기를 안 주면 처음에 paused 상태로 시작 — [Google ARCore Augmented Images](https://developers.google.com/ar/develop/augmented-images)
- `XRTrackedImage.nativePtr`는 `UnityXRNativeImage` 구조체(version + `imageTrackable` 포인터)를 가리키며, 헤더는 패키지의 `Includes~/UnityXRNativePtrs.h`; 문서에 `ArAugmentedImage` 핸들로 캐스팅하는 C++ 예제가 있음 — [ARCore XR Plugin 6.3 Image tracking](https://docs.unity3d.com/Packages/com.unity.xr.arcore@6.3/manual/features/image-tracking.html)
- 패키지 자체도 `[DllImport("arcore_sdk_c", EntryPoint = "ArConfig_create")]`처럼 ARCore C API를 C#에서 직접 호출함 (로컬 소스 `Runtime/ArConfig.cs` 181행). 그리고 `ARCoreSessionSubsystem.beforeSetConfiguration` 이벤트 인자가 `(session, config)`를 넘김 (`Runtime/ARCoreSessionSubsystem.cs` 365행) — 로컬 패키지 소스 (URL 없음, 사용자 PC의 PackageCache)

### Inferences
- 현재 코드의 "Tracking이고 size>0.02이면 즉시 스폰"은 FULL_TRACKING 첫 프레임에서 바로 스폰하는 것. 물리 크기 미지정이면 이 시점의 size/pose는 아직 수렴 전이므로 warm-up(연속 N프레임 Tracking + 크기 변화율 수렴) 게이팅이 맞는 방향.
- `Limited` 프레임의 pose는 "마지막으로 알던 pose"이므로 보정(lerp/앵커 갱신)에 쓰면 안 됨. Tracking 프레임만 보정 입력으로 사용.
- TrackingMethod를 정말 직접 읽고 싶으면 `ArAugmentedImage_getTrackingMethod`를 `arcore_sdk_c`에서 DllImport하고 ArSession 포인터를 넘기면 될 것으로 보이나, Unity 쪽 매핑이 이미 1:1이므로 실익이 거의 없음 (정확하지 않을 수 있음 — 직접 검증 안 함).

### Gaps
- AR Foundation 6.x 문서에서 이미지 Tracking/Limited 매핑을 명시한 최신 문장은 찾지 못함 (6.3 image-tracking 매뉴얼 페이지 URL 일부가 404). 근거는 2019년 changelog뿐.
- `UnityXRNativeImage` 구조체 레이아웃과 ArSession 포인터를 C#에서 얻는 정확한 6.3 API는 확인 못 함.

## Q2. requestedMaxNumberOfMovingImages의 효과, ARCore 세션 설정(카메라 config, 포커스, FPS, depth)이 안정성에 주는 영향

### Takeaway
**ARCore에서 `requestedMaxNumberOfMovingImages`(Max Number Of Moving Images)는 아무 효과가 없음** — 패키지 소스가 값을 저장만 하고 native로 넘기지 않음. 이미지 트래킹 전용 "mode"(정적/이동) 설정도 ARCore에는 없음. 조정 가능한 것은 카메라 config(해상도/FPS), autofocus, 그리고 `beforeSetConfiguration`으로 ArConfig를 직접 만지는 것 정도.

### Cited Findings
- 로컬 소스 `Runtime/ARCoreImageTrackingSubsystem.cs` 91–102행: 주석 "ARCore doesn't let you set the max number -- it just tracks everything", setter는 필드 저장만, `currentMaxNumberOfMovingImages => Mathf.Max(m_RequestedMaxNumberOfMovingImages, GetNumberOfTrackedImages())`. 같은 파일 135행 `supportsMovingImages = true` — 로컬 패키지 소스 (PackageCache)
- AR Foundation 문서는 Max Number Of Moving Images에 대해 "Tracking moving images requires more CPU resources."라고만 하고 플랫폼별 지원표를 참조하게 함 — [ARTrackedImageManager 6.3](https://docs.unity3d.com/Packages/com.unity.xr.arfoundation@6.3/manual/features/image-tracking/artrackedimagemanager.html); 지원표에서 ARCore 이동 이미지 = "Yes" — [Image tracking platform support 6.3](https://docs.unity3d.com/Packages/com.unity.xr.arfoundation@6.3/manual/features/image-tracking/platform-support.html)
- Google: ARCore는 이미지가 시야를 벗어나도 정적이라 가정하고 계속 추적, 움직이는 이미지도 지원하지만 그 정적 가정 때문에 정확도가 떨어질 수 있음. 동시 추적 최대 20개, 같은 이미지의 여러 인스턴스는 동시 감지 안 함, 활성 DB는 1개 — [Google ARCore Augmented Images](https://developers.google.com/ar/develop/augmented-images)
- `ARCoreSessionSubsystem.beforeSetConfiguration`: native ArConfig가 dirty일 때 호출, `SetConfigurationDirty()`로 강제 트리거 가능 (CHANGELOG 667–668행); 이후 이 이벤트가 안 불리는 회귀가 수정됨 (622행) — 로컬 패키지 CHANGELOG
- 카메라/세션 관련 과거 버그(모두 5.1에서 수정, 6.3.5에는 해당 없음으로 보임): "changing ARCameraManager.currentConfiguration could disable some ARCore features, including autofocus" (5.1.0-pre.8), "ARSession.Reset could have unintended side effects such as disabling the device camera's autofocus" (5.1.0-pre.4) — [ARCore XR Plugin CHANGELOG 6.5](https://docs.unity3d.com/Packages/com.unity.xr.arcore@6.5/changelog/CHANGELOG.html)
- ARCore XR Plugin 6.3 카메라 기능표에 `supportsFocusModes` = Yes — [ARCore XR Plugin 6.3 Camera](https://docs.unity3d.com/Packages/com.unity.xr.arcore@6.3/manual/features/camera.html)

### Inferences
- Inspector의 Max Number Of Moving Images = 1은 ARCore에서 무의미하므로 원인 후보에서 제외해도 됨. 그림이 고정이라면 "정적 이미지 + 앵커"가 ARCore의 기본 가정과 일치.
- 모니터까지 거리가 짧고 일정하므로 autofocus 헌팅(초점이 왔다 갔다 함)이 블러 → 특징점 손실 → 점프를 만들 수 있음. `ARCameraManager.autoFocusRequested` 켜기/끄기를 S23에서 A/B 테스트할 가치 있음 (근거 문헌은 못 찾음, 추론).
- 카메라 config는 `ARCameraManager.GetConfigurations()` / `currentConfiguration`으로 고를 수 있음. 30fps보다 60fps config가 모션 블러에는 유리할 수 있으나 S23에서 지원 여부와 트래킹 품질 영향은 미확인.

### Gaps
- ARCore C API의 ArConfig에 이미지 트래킹 안정성에 직접 관여하는 옵션(예: 이미지 전용 모드)은 찾지 못함. Depth API 사용 여부가 이미지 pose 안정성에 영향 준다는 근거도 찾지 못함.
- 카메라 해상도/FPS별 이미지 트래킹 지터 비교 자료 없음.

## Q3. 안정화 코드 패턴과 파라미터 (ARAnchor, One Euro, deadband/hysteresis, 크기 고정)

### Takeaway
Google·Unity 모두 "고정된 이미지는 앵커에 붙여라"를 공식 권장함. AR Foundation 6에서는 `await ARAnchorManager.TryAddAnchorAsync(pose)`로 이미지 pose에 앵커를 만들고 콘텐츠를 그 자식으로 둠(이미지에 대한 `AttachAnchor`는 문서상 plane만 언급). 스무딩은 One Euro 필터가 표준이며, 웹 AR 라이브러리 MindAR의 기본값(warm-up 5프레임, miss 5프레임)이 warm-up/hide 판정의 참고 수치가 됨.

### Cited Findings
- Google: 벽 포스터처럼 움직이지 않는 이미지는 앵커를 붙이면 더 안정적으로 추적됨 — [Google ARCore Augmented Images](https://developers.google.com/ar/develop/augmented-images)
- Unity: "Image tracking is a great way to track an image while the image is in frame" 하지만 이미지가 안 보이면 품질이 떨어지므로 콘텐츠를 앵커에 parent하는 것을 고려하라. 앵커는 비싸므로 "Avoid creating multiple anchors within a couple meters of each other", 안 쓰는 앵커는 제거하라 — [AR Foundation 6.3 Introduction to anchors](https://docs.unity3d.com/Packages/com.unity.xr.arfoundation@6.3/manual/features/anchors/introduction.html)
- API: `var result = await manager.TryAddAnchorAsync(pose); if (result.status.IsSuccess()) { var anchor = result.value; }` (모든 플랫폼 지원). `AttachAnchor(plane, pose)`는 `descriptor.supportsTrackableAttachments` 확인 필요, plane만 예시. 제거는 `TryRemoveAnchor(anchor)` → 다음 `trackablesChanged`의 removed에 나옴 — [ARAnchorManager 6.3](https://docs.unity3d.com/Packages/com.unity.xr.arfoundation@6.3/manual/features/anchors/aranchormanager.html)
- Unity 포럼: 앵커가 Limited에 머무는 사례, "AR Foundation reports the tracking state to you, but ARCore controls it", ARCore는 tracking을 잃은 뒤 앵커 재위치화를 어려워함 — [Unity Discussions: ARAnchor stuck with Limited trackingState](https://discussions.unity.com/t/aranchor-stuck-with-limited-trackingstate/1515544)
- AR Foundation: Tracked Image Prefab은 "not the recommended way to place content in the world"; 콘텐츠는 ARTrackedImage에 parent하라 (이미지가 계속 보이는 경우) — [ARTrackedImageManager 6.3](https://docs.unity3d.com/Packages/com.unity.xr.arfoundation@6.3/manual/features/image-tracking/artrackedimagemanager.html)
- One Euro 필터 튜닝 절차(원저자): beta=0, mincutoff는 중간값으로 시작 → 천천히 움직이며 지터가 사라질 때까지 mincutoff를 낮춤 → 빠른 움직임에서 지연이 사라질 때까지 beta를 올림. "if high speed lag is a problem, increase beta; if slow speed jitter is a problem, decrease fcmin". beta 시작값 예 0.001/0.0001 (단위에 따라 다름) — [Casiez 1€ Filter 페이지](https://cristal.univ-lille.fr/~casiez/1euro); 원 논문 CHI 2012 — [core.ac.uk PDF](https://core.ac.uk/download/49919969.pdf)
- Unity용 구현체(Vector3/Quaternion 지원): [DarioMazzanti/OneEuroFilterUnity](https://github.com/DarioMazzanti/OneEuroFilterUnity)
- MindAR(이미지 트래킹 AR)의 실사용 기본값: `filterMinCF` 0.001, `filterBeta` 1000, `warmupTolerance` 5 (연속 5프레임 감지돼야 found, 오탐 방지 목적), `missTolerance` 5 (연속 5프레임 미감지여야 lost) — [MindAR Tracking Config](https://hiukim.github.io/mind-ar-js-doc/quick-start/tracking-config)
- Vuforia 포럼: 자체 damping으로 지터를 "moderate success"로 줄였지만 평면 타깃 pose 지터는 근본적으로 존재 — [Vuforia forum: image tracking jitter](https://developer.vuforia.com/forum/unity/image-tracking-jitter?sort=2)
- Niantic(다른 SDK) 포럼: 새 추정이 올 때마다 업데이트되니 작은 점프는 정상, "Adding smoothing or a threshold on top" 권장 — [Niantic community: VPS anchors jumping](https://community.nianticspatial.com/t/resolved-vps-anchors-jumping-around/2456)

### Inferences
- 권장 구조(추론): ① Tracking 연속 ≥5~10프레임 + 그 구간 크기 변화 < 1~2%일 때 크기를 중앙값으로 고정 → ② 그 pose로 `TryAddAnchorAsync` → 콘텐츠를 앵커 자식으로 → ③ 이후 Tracking 프레임에서 이미지 pose와 앵커 기준 콘텐츠의 차이가 deadband(예: 1–2 cm / 2–3°) 이하면 무시, 상한(예: 10–15 cm) 초과면 이상치로 무시하되 그런 값이 N프레임 연속이면 재앵커(hysteresis) → ④ 재앵커 시 이전 앵커 `TryRemoveAnchor`. 수치는 근거 문헌 없는 출발값이므로 S23에서 측정해 조정해야 함.
- 현재의 "sharpness 10 지수 lerp"는 속도에 관계없이 같은 cutoff라서 정지 시 지터는 남고 이동 시는 지연됨. One Euro(위치 미터 단위 기준 mincutoff ~0.5–1 Hz, beta는 0에서 시작)로 바꾸는 것이 표준적이나, 앵커 고정 후 deadband 방식이면 per-frame 필터 자체가 거의 필요 없음.
- 이미지 1장당 앵커 1개(두 그림 = 2개)면 "몇 m 안에 여러 앵커 금지" 권고에 걸리지만 2개 수준은 현실적으로 문제 없을 가능성이 큼 (정확하지 않을 수 있음). 대안: 두 그림 중앙에 앵커 1개를 두고 두 콘텐츠를 상대 오프셋으로 배치.

### Gaps
- ARCore에서 `AttachAnchor`를 ARTrackedImage에 쓸 수 있는지(=`supportsTrackableAttachments`가 이미지에도 적용되는지) 공식 문서 확인 못 함.
- ARCore 이미지 pose 지터의 정량 수치(mm 단위 표준편차)와 One Euro 파라미터의 AR Foundation 사례값은 찾지 못함.

## Q4. 모니터/화면 위 이미지 추적의 특유 문제

### Takeaway
모니터 상의 moiré·리프레시 플리커·반사에 대한 Google/Unity 공식 문서는 **찾지 못함**. 커뮤니티에서 확인된 것은 "모니터의 같은 위치에서 이미지를 바꾸면 ARCore가 인식 못 함"(기존 원인 6과 동일)뿐임.

### Cited Findings
- Unity 포럼(2026-02, AR Foundation 6.2 태그): ARCore는 이미지를 정적이라 가정해 "until the session is reset" 목록에 유지, 이미지를 removed나 None으로 표시하지 않음; 모니터에서 Alt+Tab으로 같은 위치에 두 이미지를 번갈아 띄우면 ARCore가 변화를 인지 못 함. 해결책으로 reference image 품질 점수 개선, 다른 AR 엔진 사용, 이미지 1장만 스캔하고 나머지는 가상으로 구성하는 방식 제안 — [Unity Discussions: AR Page Flip and Instability](https://discussions.unity.com/t/ar-page-flip-and-instability/1708607/2)
- Google 가이드는 화면/디스플레이에 대한 언급이 없음. 다만 색 정보는 사용하지 않음(그레이스케일 가능), 과도한 압축 금지, 반복 패턴·특징이 너무 많거나 적은 이미지 금지, 최소 300×300 px, 고해상도는 성능 향상 없음 — [Google ARCore Augmented Images](https://developers.google.com/ar/develop/augmented-images)
- (오래된 정보, 2019 수정됨) Tracked Image Manager 사용 시 카메라 플리커 버그는 카메라 파이프라인 문제였고 3.0.3에서 수정 — [Unity Issue Tracker](https://issuetracker.unity3d.com/issues/arfoundation-arcore-camera-flickers-rapidly-in-a-scene-with-ar-tracked-image-manager-and-match-camera-frame-rate-disabled)

### Inferences
- 두 그림이 한 화면에 나란히 있으면 각 그림이 화면 폭의 절반이라, 25% 프레임 점유 조건을 동시에 만족시키기 어렵고 카메라가 가까워질수록 한쪽만 보이게 됨 → 한쪽은 Limited(마지막 pose)로 남음. 그림을 한 번에 하나씩 전체 화면으로 띄우거나, 두 그림을 한 장의 합성 레퍼런스 이미지로 등록하는 방식도 검토할 만함 (추론).
- 모니터 표면 반사, 밝기 과다로 인한 하이라이트 클리핑, moiré는 특징점 추출을 해친다고 일반적으로 알려져 있으나 ARCore 근거 자료는 없음. 실험적으로 모니터 밝기 중간, 주변 조명 반사 차단, 화면 정면 촬영을 권장 (추론).
- 레퍼런스 이미지를 원본 그림 파일이 아니라 **모니터를 폰으로 찍은 사진(정면, 크롭)**으로 등록하면 화면 감마/색/픽셀 격자 차이를 줄일 수 있음 (추론, 근거 없음 — 검증 필요).
- Specify Size: 모니터에 표시된 실제 그림 폭을 자로 재서 입력하면 Google 권장(크기 지정 시 ARCore가 해당 크기를 사용)과 일치.

### Gaps
- 화면 리프레시(PWM 밝기 조절 플리커)와 카메라 노출 간 간섭이 ARCore 이미지 트래킹에 미치는 영향에 대한 자료 없음.

## Q5. 이미지 트래킹 상태 리셋 방법과 부작용

### Takeaway
공식적으로 문서화된 유일한 방법은 `ARSession.Reset()`(모든 trackable 파괴 + 디바이스 추적 원점 리셋). 다만 커뮤니티에는 Reset/서브시스템 Destroy/Loader 재초기화로도 이전 이미지가 안 지워졌다는 보고가 있음. 라이브러리 교체 시 기존 tracked image가 어떻게 되는지는 문서화되지 않음.

### Cited Findings
- `ARSession.Reset`: "destroys all trackables and resets device tracking (for example, the position of the session is reset to the origin)" (4.2 문서, 오래된 정보이나 개념은 동일할 것으로 보임) — [ARSession.Reset 4.2 API](https://docs.unity3d.com/Packages/com.unity.xr.arfoundation@4.2/api/UnityEngine.XR.ARFoundation.ARSession.Reset.html)
- ARCore XR Plugin 6.1.0-pre.1(2024-08): "Fixed the `ARCoreSessionSubsystem` so that your app no longer quits unexpectedly if you call `ARSession.Reset`" → 6.3.5는 수정 이후 버전 — [ARCore XR Plugin CHANGELOG 6.5](https://docs.unity3d.com/Packages/com.unity.xr.arcore@6.5/changelog/CHANGELOG.html); 관련 이슈(세션 생성 직후 Reset 시 크래시, 회피책: 세션이 tracking 될 때까지 지연) — [Unity Issue Tracker](https://issuetracker.unity3d.com/issues/xr-android-player-crashes-when-arsession-dot-reset-is-called-after-arsession-is-instantiated-on-the-device)
- 2023-09 포럼: 씬을 나갔다 오면 이전 이미지가 기억돼 `added`에 다시 안 나옴. `subsystem.Destroy()`, `ARSession.Reset()`, `LoaderUtility.Deinitialize()/Initialize()` 모두 실패 보고, 확정 해법 없음 (arfoundation-samples #1107 참조) — [Unity Discussions: How to clear all images tracked](https://discussions.unity.com/t/how-to-clear-all-images-tracked/930083)
- 라이브러리 교체: 런타임에 여러 라이브러리 간 전환 가능, 단 enable 시 null이면 매니저가 스스로 disable됨 — [ARTrackedImageManager 6.3](https://docs.unity3d.com/Packages/com.unity.xr.arfoundation@6.3/manual/features/image-tracking/artrackedimagemanager.html). ARCore 구현은 라이브러리 설정 시 `UnityARCore_imageTracking_setDatabase(...)`를 호출(null이면 `IntPtr.Zero`) — 로컬 소스 `Runtime/ARCoreImageTrackingSubsystem.cs` 36–53행
- 과거(5.1 이전) Reset이 autofocus를 꺼버리는 부작용이 있었음(수정됨) — [ARCore XR Plugin CHANGELOG 6.5](https://docs.unity3d.com/Packages/com.unity.xr.arcore@6.5/changelog/CHANGELOG.html)

### Inferences
- Reset은 디바이스 원점까지 초기화하므로 모든 앵커·평면도 사라지고 SLAM이 재초기화됨(수 초간 tracking 불가). 따라서 "그림 교체"마다 Reset하는 것은 무겁고, 체험 흐름상 명시적 "다시 스캔" 버튼에만 쓰는 것이 적절 (추론).
- 그림 교체 문제의 앱 레벨 우회: ARCore가 이미지를 지우지 않으므로, "현재 FULL_TRACKING(=Tracking)인 이미지만 콘텐츠 표시, Limited는 숨김" + "두 이미지 pose가 일정 거리 내에서 겹치면 가장 최근 Tracking된 쪽만 표시" 규칙이 현실적 (기존 계획과 일치).
- 같은 DB를 다시 set해서 native 쪽 추적 이미지가 초기화되는지는 소스상 native 구현이라 불명. 실험 필요.

### Gaps
- AR Foundation 6.x 문서에서 Reset이 tracked image를 확실히 제거하는지, 라이브러리 교체 시 기존 ARTrackedImage가 removed로 보고되는지 명시한 자료 없음.

## Q6. Windows에서 arcoreimg 품질 평가 도구 사용법

### Takeaway
사용자 PC에 이미 Unity 패키지와 함께 Windows용 바이너리가 들어 있음: `c:/Users/minek/Desktop/Unity_System/AR_Midterm/Library/PackageCache/com.unity.xr.arcore@c47b8141d7e9/Tools~/Windows/arcoreimg.exe`. `eval-img`로 0–100 점수를 확인하고 75 이상을 목표로 함.

### Cited Findings
- 사용법(Windows): `arcoreimg.exe eval-img --input_image_path=dog.png` → 0–100 점수, 권장 ≥75. DB 빌드: `arcoreimg.exe build-db --input_image_list_path=list.txt --output_db_path=my.imgdb`, 리스트 형식 `name|path|폭(m, 선택)` 예 `mouse|path/to/mouse.png|0.1`. PNG/JPEG만, 파일명은 ASCII만 — [Google arcoreimg](https://developers.google.com/ar/develop/augmented-images/arcoreimg)
- 원 배포처는 ARCore SDK for Android 릴리스의 tools 폴더 — 같은 페이지 및 [google-ar/arcore-android-sdk releases](https://github.com/google-ar/arcore-android-sdk/releases)
- ARCore XR Plugin 6.0.0-pre.5(2023-12)부터 arcoreimg 점수 75 미만 이미지가 포함된 라이브러리는 빌드 시 리포트를 생성 — [ARCore XR Plugin CHANGELOG 6.5](https://docs.unity3d.com/Packages/com.unity.xr.arcore@6.5/changelog/CHANGELOG.html)
- 로컬 확인: `Tools~/Windows/arcoreimg.exe`, `Tools~/MacOS/arcoreimg`, `Tools~/Linux/arcoreimg` 존재 — 로컬 PackageCache (Glob 결과)

### Inferences
- PowerShell 예: `& "C:\Users\minek\Desktop\Unity_System\AR_Midterm\Library\PackageCache\com.unity.xr.arcore@c47b8141d7e9\Tools~\Windows\arcoreimg.exe" eval-img --input_image_path="C:\path\painting1.png"` — 한글 파일명은 ASCII 제한에 걸리므로 영문으로 복사 후 평가.
- PackageCache 폴더 해시는 패키지 업데이트 시 바뀔 수 있으므로 exe를 별도 폴더로 복사해 쓰는 편이 안전함.
- 두 그림이 서로 비슷하면(같은 화가/톤) 개별 점수가 높아도 교차 오인식 가능 → 기존 원인 6과 연결.

### Gaps
- arcoreimg 점수와 실제 pose 지터 크기의 상관관계에 대한 자료는 찾지 못함.
