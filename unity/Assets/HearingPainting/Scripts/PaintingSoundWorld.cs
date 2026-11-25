using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.ARSubsystems;
using TMPro;

// 들리는 그림의 중심 스크립트 (씬에 하나).
// 인식한 그림마다 이름에 맞는 프리팹(PaintingWorld)을 생성하고, 모든 그림의 소리원을 함께 조작한다.
// 조작: 탭 = 솔로, 끌기 = 옮기기(옆 그림으로도), 다른 소리원 위에 놓기 = 섞기,
//       두 손가락 = 깊이 조절, 소리원 쪽으로 다가가기 = 강조 + 진동
public class PaintingSoundWorld : MonoBehaviour
{
    const string DefaultHint = "소리원을 탭하거나 끌어 보세요\n<size=75%>다른 소리 위에 놓으면 섞이고 · 그림을 길게 누르면 그림 속 공간이 나와요</size>";
    const string PulledHint = "그림 속 공간에 들어왔어요\n<size=75%>소리 쪽으로 걸어가 보세요 · 길게 누르면 돌아가요</size>";

    [Header("AR")]
    public ARTrackedImageManager imageManager;
    [Tooltip("그림마다 프리팹 하나. 프리팹의 Image Name이 Reference Image Library의 이름과 같아야 함")]
    public PaintingWorld[] paintingPrefabs;
    [Tooltip("그림 목록 에셋. 넣으면 위 배열 대신 이 목록을 씀 (Hearing Painting 메뉴로 새 그림을 등록하면 자동으로 추가됨)")]
    public PaintingCatalog catalog;

    [Header("모양")]
    public Material coreMaterial;
    public Material lineMaterial;
    public TMP_FontAsset koreanFont;

    [Header("UI")]
    public TMP_Text titleText;
    public TMP_Text hintText;

    [Header("크기·배치 (모두 그림 너비에 대한 비율)")]
    [Tooltip("처음 깊이 배율. 두 손가락으로 그림마다 바뀜")]
    public float depthScale = 1.0f;
    public float minDepthScale = 0.2f;
    public float maxDepthScale = 2.5f;
    [Tooltip("깊이 배율 1일 때 가장 먼 곳이 그림 뒤로 들어가는 거리 (그림 너비 배)")]
    public float depthRatio = 0.35f;
    [Tooltip("정면에서 이 거리(그림 너비 배)로 볼 때 원래 그림과 똑같이 보이도록 깊이를 보정")]
    public float viewDistance = 1.5f;
    public float minDepth = 0.05f;
    public float coreSize = 0.035f;
    public float ringSize = 0.15f;
    public float labelSize = 0.05f;
    [Tooltip("이 거리 안에서는 소리가 최대 크기. 멀어지면 줄어듦")]
    public float minDistance = 0.6f;
    public bool showRings = true;
    [Tooltip("클수록 그림을 빠르게 따라감. 작을수록 떨림이 적음")]
    public float followSharpness = 10f;

    [Header("추적 안정화 (결정사항 4장 C1·C2·C4·C5, 실기기: 네 손가락 탭으로 켜기·끄기)")]
    public bool stabilize = true;
    [Tooltip("C1: 처음 인식 후 이 프레임 수 동안 위치가 안정되면 생성")]
    public int warmupFrames = 10;
    [Tooltip("C1: 준비 시간 동안 허용하는 위치 흔들림 (그림 폭 비율)")]
    public float warmupTolerance = 0.01f;
    [Tooltip("C4: 이보다 작은 차이(그림 폭 비율)는 무시")]
    public float deadbandPosition = 0.02f;
    [Tooltip("C4: 이보다 작은 각도 차이(도)는 무시")]
    public float deadbandAngle = 3f;
    [Tooltip("C4: 차이가 이 시간(초) 이어질 때만 따라감")]
    public float deadbandHold = 0.5f;
    [Tooltip("C5: 한 번에 이보다 크게(그림 폭 비율) 뛰면 튐으로 보고 무시")]
    public float jumpReject = 0.10f;
    [Tooltip("C5: 큰 차이가 이 시간(초) 이어지면 실제 이동으로 인정")]
    public float jumpHold = 0.5f;
    [Tooltip("C2: 추정 크기가 이 비율 넘게 다른 상태가 sizeHold초 이어지면 천천히 보정")]
    public float sizeTolerance = 0.05f;
    public float sizeHold = 1f;
    [Tooltip("측정 표시 (실기기: 세 손가락 탭으로 켜기·끄기)")]
    public bool showStats = false;

    [Header("집중 모드: 화면 가운데 그림의 소리만 또렷하게 (F1~F4, 실기기에서 값 조정)")]
    public bool focusMode = true;
    [Tooltip("가운데가 아닌 그림의 음량 배율 (0.25 = 약 -12dB). 링도 함께 흐려짐")]
    public float focusOthersVolume = 0.25f;
    [Tooltip("화면 가운데에서 이 각도(도) 안에 그림이 없으면 모두 원래 크기")]
    public float focusMaxAngle = 35f;
    [Tooltip("새 그림이 지금 그림보다 이 각도(도) 이상 가운데에 가까워야 전환")]
    public float focusSwitchAngle = 5f;
    [Tooltip("그 상태가 이 시간(초) 이어져야 전환 (두 그림 사이에서 왔다 갔다 방지)")]
    public float focusSwitchHold = 0.3f;

    [Header("처음 상태로 리셋 (오른쪽 위 버튼 길게 누르기)")]
    public bool showResetButton = true;
    [Tooltip("비우면 씬에서 자동으로 찾음")]
    public ARSession arSession;
    public float resetHoldTime = 0.5f;
    [Tooltip("리셋할 때 소리를 줄이며 끝내는 시간(초)")]
    public float resetFadeTime = 0.3f;

    [Header("기능 켜기·끄기")]
    [Tooltip("AI 깊이 지도로 그림을 입체로 열기")]
    public bool showDepthWindow = true;
    [Tooltip("그림이 열리는 데 걸리는 시간(초)")]
    public float openDuration = 2f;
    [Tooltip("소리원 쪽으로 폰을 가까이 가져가면 강조 + 진동")]
    public bool enableFocus = true;
    [Tooltip("이 거리 안으로 다가가면 강조 (그림 너비 배)")]
    public float focusDistance = 1.2f;
    [Tooltip("화면 가운데에서 이 각도 안에 있어야 강조")]
    public float focusAngle = 10f;
    public bool enableDrag = true;
    [Tooltip("손가락이 이만큼(픽셀) 움직이면 탭이 아니라 끌기로 봄")]
    public float dragThreshold = 25f;
    [Tooltip("끌던 소리원을 다른 소리원에 겹쳐 놓으면 섞기")]
    public bool enableMerge = true;

    [Header("AI 스캔 등장 연출 (처음 인식 / 그림 빈 곳 두 번 탭으로 다시 보기)")]
    [Tooltip("스캔선이 그림을 위에서 아래로 훑는 시간(초)")]
    public float revealScanTime = 1.2f;
    [Tooltip("인식 후 입체 창문이 열리기 시작할 때까지(초). 소리원 등장도 이만큼 늦춤")]
    public float revealOpenDelay = 1.0f;
    [Tooltip("깊이 격자선 간격 (입체 창문 격자 몇 칸마다 한 줄). 작을수록 촘촘")]
    public int revealWireEvery = 4;
    [Tooltip("두 번 탭으로 볼 시간 간격(초)")]
    public float doubleTapTime = 0.35f;

    [Header("그림 속 공간 끌어내기 = 팝업 층 (그림을 길게 누르기)")]
    [Tooltip("이 시간(초) 동안 누르고 있으면 끌어내기 / 돌아가기")]
    public float longPressTime = 1f;
    [Tooltip("깊이를 몇 개 층으로 나눌지 (2~8)")]
    public int popLayers = 4;
    [Tooltip("URP Unlit + Alpha Clipping 켠 재질. 있으면 층 윤곽을 매끈하게 오려 냄, 비우면 격자 칸 모양")]
    public Material popLayerMaterial;
    [Tooltip("펼친 크기 (그림의 몇 배)")]
    public float popScale = 2.5f;
    [Tooltip("가장 가까운 층이 방 쪽으로 나오는 거리 (펼친 폭의 몇 배). 보는 거리보다 짧아야 함")]
    public float popDepthRatio = 0.3f;
    [Tooltip("소리원 구·링·라벨이 커지는 배율")]
    public float popVisualScale = 1.5f;
    [Tooltip("펼치거나 접는 데 걸리는 시간(초)")]
    public float popDuration = 1.5f;
    [Tooltip("파이프라인이 미리 만든 층(가려진 곳을 AI로 채운 PNG, 그림 폴더/layers)이 있으면 사용. 끄면 앱에서 깊이로 층을 만듦(예전 방식)")]
    public bool useBakedLayers = true;
    [Tooltip("펼칠 때 층마다 크기를 원근에 맞춤: 정면에서는 원래 그림과 똑같이 맞물리고 옆으로 볼 때만 층이 벌어짐. 끄면 모든 층 popScale배(예전 방식)")]
    public bool popPerspective = true;

    [Header("축 보정 (실기기에서 방향이 틀리면 체크)")]
    public bool flipVertical = false;
    public bool flipDepth = false;
    public bool showDebugCorner = false;

    [Header("에디터 미리보기 (폰 없이 Play로 확인, 휠 = 깊이 조절)")]
    public bool editorPreview = true;
    public float previewDistance = 1.0f;
    [Tooltip("미리보기에서 그림 사이 간격(m)")]
    public float previewGap = 0.15f;

    readonly List<PaintingWorld> worlds = new List<PaintingWorld>();
    readonly HashSet<string> failedImages = new HashSet<string>();
    PaintingWorld active;       // 화면 가운데에 가장 가까운 그림 (제목·두 손가락 깊이 조절 대상)

    SoundSource soloTarget;
    SoundSource focusTarget;

    bool pressActive;
    bool dragging;
    Vector2 pressStart;
    SoundSource pressSource;
    SoundSource dragSource;
    SoundSource mergeCandidate;
    float hintRestoreTime;

    // 추적 안정화: 생성 전 준비 시간(C1) 기록, 처음 보인 시각, 등장까지 걸린 시간
    readonly Dictionary<string, List<Pose>> warmupPoses = new Dictionary<string, List<Pose>>();
    readonly Dictionary<string, List<Vector2>> warmupSizes = new Dictionary<string, List<Vector2>>();
    readonly Dictionary<string, float> firstSeen = new Dictionary<string, float>();
    readonly Dictionary<string, float> appearDelay = new Dictionary<string, float>();
    int gestureMaxTouches;              // 세·네 손가락 탭 판정

    float pressTime;
    bool longPressDone;
    PaintingWorld pulledWorld;          // 지금 끌어낸 그림 (없으면 null)
    LineRenderer pressRing;             // 길게 누르는 동안 차오르는 원

    void Start()
    {
        // 데모 촬영 중 화면이 꺼지지 않게
        Screen.sleepTimeout = SleepTimeout.NeverSleep;

        // 카탈로그가 있으면 그 목록을 쓴다 (비어 있으면 기존 배열 그대로)
        if (catalog != null && catalog.paintings.Count > 0)
            paintingPrefabs = catalog.paintings.FindAll(p => p != null).ToArray();

        if (paintingPrefabs == null || paintingPrefabs.Length == 0)
            Debug.LogError("Painting Prefabs가 비어 있음: 그림 프리팹을 넣어야 함");

        if (titleText != null)
            titleText.text = "";
        SetHint("그림을 화면 가운데에 비춰 주세요");

        pressRing = new GameObject("LongPressRing").AddComponent<LineRenderer>();
        pressRing.sharedMaterial = lineMaterial;
        pressRing.useWorldSpace = true;
        pressRing.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        pressRing.receiveShadows = false;
        pressRing.startColor = pressRing.endColor = new Color(1f, 1f, 1f, 0.9f);
        pressRing.enabled = false;

        if (arSession == null)
            arSession = FindFirstObjectByType<ARSession>();
        if (showResetButton && hintText != null && hintText.canvas != null)
            ResetButton.Create(this, hintText.canvas.rootCanvas, koreanFont, resetHoldTime);
    }

    // ---------- 처음 상태로 리셋 (B7): 소리 세계 전부 + AR 세션 초기화 ----------

    bool resetting;

    public void ShowResetTip()
    {
        SetHint("길게 누르면 처음 상태로 돌아갑니다");
        hintRestoreTime = Time.time + 1.5f;
    }

    public void ResetAll()
    {
        if (!resetting)
            StartCoroutine(ResetRoutine());
    }

    System.Collections.IEnumerator ResetRoutine()
    {
        resetting = true;
        Vibrate();
        SetHint("처음 상태로 돌아갑니다\n<size=75%>그림을 다시 비춰 주세요</size>");

        // 소리가 뚝 끊기지 않게 resetFadeTime 동안 줄이며 끝냄
        var sources = new List<AudioSource>();
        foreach (PaintingWorld w in worlds)
            if (w != null)
                sources.AddRange(w.GetComponentsInChildren<AudioSource>());
        var start = sources.ConvertAll(a => a.volume);
        for (float t = 0f; t < resetFadeTime; t += Time.unscaledDeltaTime)
        {
            float k = 1f - t / resetFadeTime;
            for (int i = 0; i < sources.Count; i++)
                if (sources[i] != null)
                    sources[i].volume = start[i] * k;
            yield return null;
        }

        // 지운 소리원을 가리키는 상태를 모두 비움 (솔로·강조·끌기·섞기·꺼낸 그림)
        soloTarget = null;
        focusTarget = null;
        active = null;
        pressActive = false;
        dragging = false;
        pressSource = null;
        dragSource = null;
        mergeCandidate = null;
        pulledWorld = null;
        longPressDone = false;
        if (pressRing != null)
            pressRing.enabled = false;
        hintRestoreTime = 0f;

        foreach (PaintingWorld w in worlds)
            if (w != null)
                Destroy(w.gameObject);
        worlds.Clear();
        failedImages.Clear();
        warmupPoses.Clear();
        warmupSizes.Clear();
        firstSeen.Clear();          // 등장 시간을 다시 잴 수 있게
        appearDelay.Clear();
        if (titleText != null)
            titleText.text = "";

        // ARCore가 기억하던 그림 위치·쌓인 오차를 비우는 유일한 방법
        if (arSession != null && !(Application.isEditor && editorPreview))
            arSession.Reset();
        resetting = false;
    }

    void Update()
    {
        if (Application.isEditor && editorPreview)
            SpawnPreview();
        else
            TrackImages();

        HandleMultiFingerTap();
        if (worlds.Count == 0)
            return;

        UpdateActive();
        HandlePointer();
        UpdateFocus();
        foreach (PaintingWorld world in worlds)
            world.Tick();

        if (hintRestoreTime > 0f && Time.time > hintRestoreTime)
        {
            hintRestoreTime = 0f;
            RefreshHint();
        }
    }

    // ---------- 그림 인식 → 프리팹 생성 (다중 마커 + 다중 프리팹) ----------

    void TrackImages()
    {
        if (imageManager == null)
            return;
        foreach (ARTrackedImage image in imageManager.trackables)
        {
            // 그림이 또렷하게 추적되는 동안만 위치를 갱신한다.
            // 가까이 가서 추적이 끊기면 마지막 위치에 그대로 남는다.
            string imageName = image.referenceImage.name;
            if (!firstSeen.ContainsKey(imageName) && image.trackingState != TrackingState.None)
                firstSeen[imageName] = Time.time;            // 측정: 인식 → 등장 시간의 시작
            if (image.trackingState != TrackingState.Tracking || image.size.x <= 0.02f)
                continue;
            PaintingWorld world = worlds.Find(w => w.imageName == imageName);
            if (world != null)
                world.Follow(image);
            else if (!stabilize)
                SpawnTracked(imageName, image.transform.position, image.transform.rotation, image.size);
            else
                WarmUp(image, imageName);
        }
    }

    // C1 준비 시간 + C2 크기: 위치가 warmupFrames 동안 그림 폭의 warmupTolerance 안에서 안정되면,
    // 그 평균 위치와 크기 중앙값으로 생성 (첫 프레임의 튀는 추정값을 쓰지 않음)
    void WarmUp(ARTrackedImage image, string imageName)
    {
        if (!warmupPoses.TryGetValue(imageName, out var poses))
        {
            warmupPoses[imageName] = poses = new List<Pose>();
            warmupSizes[imageName] = new List<Vector2>();
        }
        List<Vector2> sizes = warmupSizes[imageName];
        poses.Add(new Pose(image.transform.position, image.transform.rotation));
        sizes.Add(image.size);
        if (poses.Count > warmupFrames)
        {
            poses.RemoveAt(0);
            sizes.RemoveAt(0);
        }
        if (poses.Count < warmupFrames)
            return;

        Vector3 mean = Vector3.zero;
        foreach (Pose p in poses)
            mean += p.position;
        mean /= poses.Count;
        float tolerance = warmupTolerance * image.size.x;
        foreach (Pose p in poses)
        {
            if (Vector3.Distance(p.position, mean) > tolerance)
                return;                                       // 아직 흔들림 → 계속 기다림
        }
        var xs = new List<float>(); var ys = new List<float>();
        foreach (Vector2 s in sizes) { xs.Add(s.x); ys.Add(s.y); }
        xs.Sort(); ys.Sort();
        Vector2 median = new Vector2(xs[xs.Count / 2], ys[ys.Count / 2]);
        SpawnTracked(imageName, mean, poses[poses.Count - 1].rotation, median);
        warmupPoses.Remove(imageName);
        warmupSizes.Remove(imageName);
    }

    void SpawnTracked(string imageName, Vector3 position, Quaternion rotation, Vector2 size)
    {
        int before = worlds.Count;
        Spawn(imageName, position, rotation, size);
        if (worlds.Count > before && firstSeen.TryGetValue(imageName, out float t0))
            appearDelay[imageName] = Time.time - t0;
    }

    // ---------- 측정 (결정사항 G4): 세 손가락 탭 = 표시 켜기·끄기, 네 손가락 탭 = 안정화 켜기·끄기 ----------

    void HandleMultiFingerTap()
    {
        if (Input.touchCount > 0)
        {
            gestureMaxTouches = Mathf.Max(gestureMaxTouches, Input.touchCount);
            return;
        }
        if (gestureMaxTouches == 3)
            showStats = !showStats;
        else if (gestureMaxTouches == 4)
        {
            stabilize = !stabilize;
            foreach (PaintingWorld w in worlds)
                w.ResetStats();
            SetHint(stabilize ? "추적 안정화 켬" : "추적 안정화 끔 (비교용)");
        }
        gestureMaxTouches = 0;
    }

    void OnGUI()
    {
        if (!showStats)
            return;
        var style = new GUIStyle(GUI.skin.label) { fontSize = Mathf.Max(14, Screen.height / 45), richText = true };
        var sb = new System.Text.StringBuilder();
        sb.Append($"<b>STABILIZE {(stabilize ? "ON" : "OFF")}</b>   (3-finger tap: stats, 4-finger tap: stabilize)\n");
        sb.Append("target: jitter <= 5 mm, jumps(>2cm) = 0/min, appear <= 2 s\n");
        foreach (PaintingWorld w in worlds)
        {
            string appear = appearDelay.TryGetValue(w.imageName, out float a) ? $"{a:0.00}s" : "-";
            sb.Append($"<b>{w.imageName}</b>  appear {appear}  {w.StatsLine()}\n");
        }
        var rect = new Rect(20, 20, Screen.width - 40, Screen.height * 0.4f);
        GUI.color = new Color(0, 0, 0, 0.55f);
        GUI.DrawTexture(new Rect(10, 10, Screen.width - 20, style.lineHeight * (3 + worlds.Count) + 20), Texture2D.whiteTexture);
        GUI.color = Color.white;
        GUI.Label(rect, sb.ToString(), style);
    }

    void SpawnPreview()
    {
        // 에디터: 카메라 앞에 프리팹 수만큼 가상의 그림을 나란히 놓고 바로 생성
        if (worlds.Count > 0 || failedImages.Count > 0 || paintingPrefabs == null)
            return;
        Camera cam = Camera.main;
        if (cam == null)
            return;

        float total = -previewGap;
        foreach (PaintingWorld prefab in paintingPrefabs)
        {
            if (prefab != null)
                total += prefab.previewSize.x + previewGap;
        }
        float x = -total * 0.5f;
        Quaternion rotation = Quaternion.LookRotation(Vector3.up, -cam.transform.forward);
        foreach (PaintingWorld prefab in paintingPrefabs)
        {
            if (prefab == null)
                continue;
            Vector3 center = cam.transform.position + cam.transform.forward * previewDistance
                           + cam.transform.right * (x + prefab.previewSize.x * 0.5f);
            Spawn(prefab.imageName, center, rotation, prefab.previewSize);
            x += prefab.previewSize.x + previewGap;
        }
    }

    void Spawn(string imageName, Vector3 position, Quaternion rotation, Vector2 size)
    {
        if (failedImages.Contains(imageName))
            return;
        PaintingWorld prefab = PrefabFor(imageName);
        if (prefab == null)
        {
            Debug.LogWarning("'" + imageName + "' 이미지에 맞는 프리팹이 없음 (Painting Prefabs의 Image Name 확인)");
            failedImages.Add(imageName);
            return;
        }

        PaintingWorld world = Instantiate(prefab, position, rotation);
        world.name = "SoundWorld_" + imageName;
        if (!world.Setup(this, size))
        {
            Destroy(world.gameObject);
            failedImages.Add(imageName);
            SetHint("'" + imageName + "'의 AI 결과를 찾지 못했습니다");
            return;
        }
        worlds.Add(world);
        RefreshHint();
    }

    PaintingWorld PrefabFor(string imageName)
    {
        if (paintingPrefabs == null)
            return null;
        foreach (PaintingWorld prefab in paintingPrefabs)
        {
            if (prefab != null && prefab.imageName == imageName)
                return prefab;
        }
        return null;
    }

    void UpdateActive()
    {
        Camera cam = Camera.main;
        if (cam == null)
            return;
        PaintingWorld best = null;
        float bestAngle = float.MaxValue;
        float activeAngle = float.MaxValue;
        foreach (PaintingWorld world in worlds)
        {
            if (world.Hidden)
                continue;
            float angle = Vector3.Angle(cam.transform.forward, world.transform.position - cam.transform.position);
            if (world == active)
                activeAngle = angle;
            if (angle < bestAngle)
            {
                best = world;
                bestAngle = angle;
            }
        }

        if (pulledWorld != null)
        {
            best = pulledWorld;             // 끌어낸 그림이 있으면 그 그림이 항상 대상 (바로 전환)
            pendingActive = null;
            pendingSet = false;
        }
        else
        {
            if (bestAngle > focusMaxAngle)
                best = null;                // 가운데 근처에 그림이 없음 → 모두 원래 크기
            if (best == active)
            {
                pendingActive = null;
                pendingSet = false;
                return;
            }
            // 집중 모드 전환 규칙: 새 그림이 확실히(focusSwitchAngle 이상) 더 가운데이고, 그 상태가 focusSwitchHold초 이어질 때만
            bool clearly = best == null || active == null || activeAngle > focusMaxAngle || bestAngle < activeAngle - focusSwitchAngle;
            if (!clearly)
            {
                pendingActive = null;
                pendingSet = false;
                return;
            }
            if (best != pendingActive || !pendingSet)
            {
                pendingActive = best;
                pendingSet = true;
                pendingTime = Time.time;
            }
            if (Time.time - pendingTime < focusSwitchHold)
                return;
        }
        pendingActive = null;
        pendingSet = false;
        if (best == active)
            return;
        active = best;
        if (titleText != null && active != null && active.Scene != null)
            titleText.text = active.Scene.title + "\n<size=70%>" + active.Scene.artist + " · " + active.Scene.year + "</size>";
        ApplyMix();         // 집중 모드: 가운데 그림이 바뀌면 음량 다시 계산
    }

    PaintingWorld pendingActive;    // 전환 대기 중인 그림 (null = 가운데에 그림 없음 상태로 전환 대기)
    bool pendingSet;
    float pendingTime;

    IEnumerable<SoundSource> AllSources()
    {
        foreach (PaintingWorld world in worlds)
            foreach (SoundSource s in world.Sources)
                yield return s;
    }

    // 그림 속 위치(u, v)를 그림 평면(x, z) 위 좌표로 바꾸고 깊이만큼 그림 뒤(-y)로 민다.
    // 정면 eye 거리의 시점에서 그림 표면 점을 지나는 직선을 따라 밀기 때문에, 뒤로 갈수록 그만큼 넓어져
    // 정면에서는 원래 그림과 똑같이 보이고 폰을 옆으로 움직일 때만 입체감이 생긴다
    public static Vector3 PaintingPoint(float u, float v, float depth, float w, float h, float vSign, float dSign, float eye)
    {
        float spread = (eye + depth) / eye;
        return new Vector3((u - 0.5f) * w * spread, dSign * depth, (0.5f - v) * h * vSign * spread);
    }

    // 끌어낸(팝업) 그림 공간 속 위치: 크기는 popScale배, 앞뒤 순서는 유지한 채 그림 앞(방 쪽)으로.
    // fraction: 방 쪽으로 나오는 비율(가장 가까운 층 1 ~ 가장 먼 층 0), popDepth: 가장 가까운 층이 나오는 거리(m)
    // scale: 그 층의 펼친 크기 배율 (PopLayerScale)
    public static Vector3 PulledPoint(float u, float v, float fraction, float w, float h, float vSign, float dSign, float scale, float popDepth)
    {
        return new Vector3((u - 0.5f) * w * scale, -dSign * fraction * popDepth, (0.5f - v) * h * vSign * scale);
    }

    // 펼친 층의 크기 배율. perspective면 기준 시점(eye)에서 볼 때 모든 층이 popScale배 그림과 똑같이 맞물리도록
    // 방 쪽으로 나온 만큼 줄인다 (PaintingPoint의 "뒤로 갈수록 넓힘"과 같은 식의 반대 방향).
    // 틈 메우기 11/26: 예전처럼 모든 층을 같은 배율로 키우면 정면에서도 가까운 층이 커 보여 층끼리 어긋나고 틈이 드러남
    public static float PopLayerScale(float fraction, float popScale, float popDepth, float eye, bool perspective)
    {
        if (!perspective || eye <= 0f)
            return popScale;
        return popScale * Mathf.Max(0.3f, (eye - fraction * popDepth) / eye);
    }

    // ---------- 그림 속 공간 끌어내기 ----------

    void TogglePullAt(Vector2 screenPos)
    {
        if (pulledWorld != null)
        {
            // 돌아가기: 어디를 길게 눌러도 끌어낸 그림이 접힘
            pulledWorld.TogglePull();
            pulledWorld = null;
            foreach (PaintingWorld w in worlds)
                if (w.Hidden)
                    w.SetHidden(false);
            ApplyMix();
            RefreshHint();
            Vibrate();
            return;
        }

        // 손가락 아래의 그림, 없으면 화면 가운데 그림
        PaintingWorld target = PaintingUnder(screenPos) ?? active;
        if (target == null || target.PullBusy)
            return;

        pulledWorld = target;
        target.TogglePull();
        // 펼친 그림이 옆 그림을 덮으므로 다른 그림은 숨기고 소리를 끈다
        foreach (PaintingWorld w in worlds)
            if (w != target)
                w.SetHidden(true);
        soloTarget = null;
        focusTarget = null;
        active = target;
        ApplyMix();
        RefreshHint();
        Vibrate();
    }

    // 화면 위치 아래에 있는 그림 (그림 면 안쪽일 때만, 숨긴 그림 제외)
    PaintingWorld PaintingUnder(Vector2 screenPos)
    {
        Camera cam = Camera.main;
        if (cam == null)
            return null;
        Ray ray = cam.ScreenPointToRay(screenPos);
        PaintingWorld found = null;
        float best = float.MaxValue;
        foreach (PaintingWorld w in worlds)
        {
            if (w.Hidden)
                continue;
            if (w.RayToUV(ray, w.transform.position, out Vector2 uv, out float d)
                && uv.x >= 0f && uv.x <= 1f && uv.y >= 0f && uv.y <= 1f && d < best)
            {
                found = w;
                best = d;
            }
        }
        return found;
    }

    // 길게 누르는 동안 손가락 위치에 차오르는 원 (0.25초 뒤부터 보임)
    void UpdatePressRing(Vector2 screenPos, float held)
    {
        Camera cam = Camera.main;
        float progress = (held - 0.25f) / Mathf.Max(longPressTime - 0.25f, 0.01f);
        if (cam == null || progress <= 0f || longPressDone)
        {
            pressRing.enabled = false;
            return;
        }
        progress = Mathf.Clamp01(progress);
        const float distance = 0.3f;
        const float radius = 0.025f;
        Vector3 center = cam.ScreenToWorldPoint(new Vector3(screenPos.x, screenPos.y, distance));
        int count = Mathf.Max(2, Mathf.CeilToInt(48 * progress) + 1);
        pressRing.positionCount = count;
        for (int i = 0; i < count; i++)
        {
            float a = Mathf.PI * 0.5f - (i / 48f) * Mathf.PI * 2f;     // 12시 방향부터 시계 방향
            pressRing.SetPosition(i, center + (cam.transform.right * Mathf.Cos(a) + cam.transform.up * Mathf.Sin(a)) * radius);
        }
        pressRing.widthMultiplier = 0.003f;
        pressRing.enabled = true;
    }

    // ---------- 조작: 탭·끌기·핀치 ----------

    void HandlePointer()
    {
        // 두 손가락: 탭·끌기를 취소하고 깊이 조절 (세·네 손가락은 측정용 탭이라 핀치하지 않음)
        if (Input.touchCount >= 2 || gestureMaxTouches >= 3)
        {
            if (dragging)
                EndDrag(false);
            pressActive = false;
            pressRing.enabled = false;
            if (Input.touchCount == 2 && gestureMaxTouches <= 2)
                HandlePinch();
            return;
        }
        if (Application.isEditor && Input.mouseScrollDelta.y != 0f)
            ChangeDepthScale(Input.mouseScrollDelta.y * 0.1f);

        if (!ReadPointer(out Vector2 position, out int pointerId, out bool down, out bool up))
            return;

        if (down)
        {
            // 화면 UI를 누른 경우는 무시
            pressActive = !(EventSystem.current != null && EventSystem.current.IsPointerOverGameObject(pointerId));
            pressStart = position;
            dragging = false;
            pressSource = pressActive ? SourceAt(position) : null;
            pressTime = Time.time;
            longPressDone = false;
            return;
        }
        if (!pressActive)
            return;

        if (up)
        {
            pressActive = false;
            pressRing.enabled = false;
            if (longPressDone)
                return;         // 길게 누르기로 이미 처리함 (탭으로 치지 않음)
            if (dragging)
                EndDrag(true);
            else
                Tap(pressSource);
            return;
        }

        // 움직이지 않고 오래 누르고 있으면: 그림 속 공간 끌어내기 / 돌아가기
        if (!dragging && !longPressDone && (position - pressStart).magnitude <= dragThreshold)
        {
            float held = Time.time - pressTime;
            UpdatePressRing(position, held);
            if (held >= longPressTime)
            {
                longPressDone = true;
                pressRing.enabled = false;
                TogglePullAt(pressStart);
                return;
            }
        }
        else
        {
            pressRing.enabled = false;
        }

        // 누른 채 움직임: 일정 거리 이상이면 소리원 끌기 (끌어낸 상태에서는 끌기·섞기를 쓰지 않음)
        if (enableDrag && !dragging && !longPressDone && pulledWorld == null && pressSource != null
            && (position - pressStart).magnitude > dragThreshold)
            BeginDrag(pressSource);
        if (dragging)
            DragSource(dragSource, position);
    }

    bool ReadPointer(out Vector2 position, out int pointerId, out bool down, out bool up)
    {
        position = Vector2.zero;
        pointerId = -1;
        down = false;
        up = false;
        if (Input.touchCount == 1)
        {
            Touch touch = Input.GetTouch(0);
            position = touch.position;
            pointerId = touch.fingerId;
            down = touch.phase == TouchPhase.Began;
            up = touch.phase == TouchPhase.Ended || touch.phase == TouchPhase.Canceled;
            return true;
        }
        // 에디터에서는 마우스를 손가락 하나로 취급
        if (Application.isEditor && (Input.GetMouseButton(0) || Input.GetMouseButtonUp(0)))
        {
            position = Input.mousePosition;
            down = Input.GetMouseButtonDown(0);
            up = Input.GetMouseButtonUp(0);
            return true;
        }
        return false;
    }

    SoundSource SourceAt(Vector2 screenPos)
    {
        Camera cam = Camera.main;
        if (cam == null)
            return null;
        // 수업의 ObjectController처럼 레이를 쏴서 맞은 대상을 찾는다 (소리원 콜라이더는 Trigger라 Collide로 지정)
        Ray ray = cam.ScreenPointToRay(screenPos);
        if (Physics.Raycast(ray, out RaycastHit hit, 20f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Collide))
            return hit.collider.GetComponent<SoundSource>();
        return null;
    }

    float lastEmptyTapTime = -10f;

    void Tap(SoundSource tapped)
    {
        // 그림 빈 곳을 두 번 빠르게 탭하면 그 그림의 등장 연출 다시 보기 (데모 재촬영용)
        if (tapped == null && pulledWorld == null)
        {
            if (Time.time - lastEmptyTapTime <= doubleTapTime)
            {
                lastEmptyTapTime = -10f;
                PaintingWorld w = PaintingUnder(pressStart);
                if (w != null)
                {
                    w.ReplayReveal();
                    soloTarget = null;
                    focusTarget = null;
                    ApplyMix();
                    RefreshHint();
                    return;
                }
            }
            else
            {
                lastEmptyTapTime = Time.time;
            }
        }
        // 섞인 소리는 짝 전체를 하나로 본다
        if (tapped != null && tapped.Host != null)
            tapped = tapped.Host;
        // 같은 소리원을 다시 누르거나 빈 곳을 누르면 전체 소리로 돌아감
        soloTarget = (tapped == null || tapped == soloTarget) ? null : tapped;
        focusTarget = null;
        ApplyMix();
        RefreshHint();
    }

    void BeginDrag(SoundSource s)
    {
        // 섞인 짝을 끌면 섞여 들어갔던 소리를 빼낸다
        if (s.Host != null)
        {
            s.Separate();
        }
        else if (s.Guest != null)
        {
            SoundSource guest = s.Guest;
            guest.Separate();
            s = guest;
        }

        dragging = true;
        dragSource = s;
        s.SetTrail(true);       // 끄는 동안 빛 꼬리
        mergeCandidate = null;
        soloTarget = null;
        focusTarget = null;
        hintRestoreTime = 0f;
        ApplyMix();
        SetHint("<b>" + s.Data.label + "</b> 옮기는 중");
    }

    void DragSource(SoundSource s, Vector2 screenPos)
    {
        Camera cam = Camera.main;
        if (cam == null)
            return;
        Ray ray = cam.ScreenPointToRay(screenPos);

        // 손가락이 가리키는 그림을 찾는다. 지금 그림은 소리원 깊이의 평면, 다른 그림은 그림 표면으로 판정
        PaintingWorld target = null;
        Vector2 uv = Vector2.zero;
        float best = float.MaxValue;
        foreach (PaintingWorld world in worlds)
        {
            Vector3 planePoint = world == s.World ? s.transform.position : world.transform.position;
            if (world.RayToUV(ray, planePoint, out Vector2 hitUV, out float distance)
                && hitUV.x >= 0f && hitUV.x <= 1f && hitUV.y >= 0f && hitUV.y <= 1f && distance < best)
            {
                target = world;
                uv = hitUV;
                best = distance;
            }
        }
        if (target == null)
        {
            // 어느 그림도 가리키지 않으면 지금 그림의 가장자리에 붙여 둔다
            target = s.World;
            if (!target.RayToUV(ray, s.transform.position, out uv, out _))
                return;
        }

        if (target != s.World)
        {
            // 옆 그림으로 넘어감: 그 그림의 소리원이 되어 그 그림의 AI 깊이를 따른다
            target.Adopt(s);
            Vibrate();
            if (mergeCandidate == null)
                SetHint("<b>" + s.Data.label + "</b> → " + target.Title);
        }
        s.Data.u = Mathf.Clamp01(uv.x);
        s.Data.v = Mathf.Clamp01(uv.y);
        target.MarkDirty();     // 새 위치의 AI 깊이로 앞뒤도 함께 바뀐다

        UpdateMergeCandidate(s);
    }

    // 끌고 있는 소리원과 닿아 있는(OnTriggerEnter) 소리원 중 가장 가까운 것을 섞을 후보로
    void UpdateMergeCandidate(SoundSource s)
    {
        SoundSource candidate = null;
        if (enableMerge)
        {
            float best = float.MaxValue;
            foreach (SoundSource other in s.Touching)
            {
                if (other == null || !other.IsFree)
                    continue;
                float d = (other.transform.position - s.transform.position).sqrMagnitude;
                if (d < best)
                {
                    candidate = other;
                    best = d;
                }
            }
        }
        if (candidate == mergeCandidate)
            return;

        mergeCandidate = candidate;
        ApplyMix();
        if (candidate != null)
        {
            SetHint("놓으면 <b>" + s.Data.label + "</b>와(과) <b>" + candidate.Data.label + "</b>이(가) 섞여요");
            Vibrate();
        }
        else
        {
            SetHint("<b>" + s.Data.label + "</b> → " + s.World.Title);
        }
    }

    void EndDrag(bool allowMerge)
    {
        SoundSource s = dragSource;
        SoundSource host = mergeCandidate;
        if (s != null)
            s.SetTrail(false);
        dragging = false;
        dragSource = null;
        mergeCandidate = null;

        if (allowMerge && s != null && host != null && s.IsFree && host.IsFree)
        {
            host.World.Adopt(s);
            s.MergeInto(host);
            host.World.MarkDirty();
            // 섞인 소리만 들려준다. 빈 곳을 탭하면 전체로 돌아감
            soloTarget = host;
            Vibrate();
        }
        ApplyMix();
        RefreshHint();
    }

    void HandlePinch()
    {
        // 수업 TouchController와 같은 방식: 이전 두 손가락 거리와 지금 거리를 비교
        Touch t0 = Input.GetTouch(0);
        Touch t1 = Input.GetTouch(1);
        float prev = ((t0.position - t0.deltaPosition) - (t1.position - t1.deltaPosition)).magnitude;
        float now = (t0.position - t1.position).magnitude;
        ChangeDepthScale((now - prev) / Screen.height * 3f);
    }

    void ChangeDepthScale(float delta)
    {
        if (active == null || Mathf.Approximately(delta, 0f))
            return;
        float scale = active.ChangeDepthScale(delta);
        SetHint(active.Title + " 깊이 " + scale.ToString("0.0") + "배");
        hintRestoreTime = Time.time + 1.2f;
    }

    // ---------- 다가가기: 화면 가운데에 두고 가까이 가면 강조 ----------

    void UpdateFocus()
    {
        if (!enableFocus || soloTarget != null || dragging)
        {
            if (focusTarget != null)
                SetFocus(null);
            return;
        }
        Camera cam = Camera.main;
        if (cam == null)
            return;

        SoundSource best = null;
        float bestAngle = float.MaxValue;
        foreach (SoundSource s in AllSources())
        {
            if (s.Host != null || s.World.Hidden)
                continue;   // 섞인 소리는 짝(Host) 기준으로, 숨긴 그림은 제외
            Vector3 toSource = s.transform.position - cam.transform.position;
            float angle = Vector3.Angle(cam.transform.forward, toSource);
            // 이미 강조 중인 소리원은 조금 더 넉넉하게 봐서 깜빡이지 않게 한다
            bool current = s == focusTarget;
            float maxAngle = current ? focusAngle * 1.5f : focusAngle;
            float maxDistance = (current ? focusDistance * 1.2f : focusDistance) * s.World.Size.x;
            if (angle < maxAngle && toSource.magnitude < maxDistance && angle < bestAngle)
            {
                best = s;
                bestAngle = angle;
            }
        }
        if (best != focusTarget)
            SetFocus(best);
    }

    void SetFocus(SoundSource target)
    {
        focusTarget = target;
        ApplyMix();
        RefreshHint();
        if (target != null)
            Vibrate();
    }

    static SoundSource RootOf(SoundSource s)
    {
        return s != null && s.Host != null ? s.Host : s;
    }

    // 솔로 > 다가가기 > 보통 순서로 소리원마다 음량과 강조를 정한다. 섞인 짝은 함께 움직인다
    void ApplyMix()
    {
        foreach (SoundSource s in AllSources())
        {
            bool inTarget;
            if (s.World.Hidden)
            {
                s.SetMix(0f, false);    // 다른 그림을 끌어낸 동안은 소리를 끈다
                continue;
            }
            if (soloTarget != null)
            {
                inTarget = RootOf(s) == soloTarget;
                s.SetMix(inTarget ? 1f : 0f, inTarget);
            }
            else if (focusTarget != null)
            {
                inTarget = RootOf(s) == focusTarget;
                s.SetMix(inTarget ? 1f : 0.3f, inTarget);
            }
            else
            {
                // 끌고 있는 소리원과 섞을 후보는 강조해서 보여 준다
                // 집중 모드: 그림이 두 장 이상이면 가운데가 아닌 그림의 소리를 줄임 (끌기 중에는 멈춤)
                bool others = focusMode && !dragging && active != null && worlds.Count >= 2 && s.World != active;
                s.SetMix(others ? focusOthersVolume : 1f, dragging && (s == dragSource || s == mergeCandidate));
            }
        }
    }

    void RefreshHint()
    {
        if (worlds.Count == 0)
        {
            SetHint("그림을 화면 가운데에 비춰 주세요");
            return;
        }
        SoundSource target = soloTarget != null ? soloTarget : focusTarget;
        if (target == null)
        {
            SetHint(pulledWorld != null ? PulledHint : DefaultHint);
            return;
        }

        string title = target.Data.label;
        string description = target.Data.description;
        if (target.Guest != null)
        {
            title += " + " + target.Guest.Data.label;
            description = "섞인 소리: " + target.Data.description + " / " + target.Guest.Data.description;
        }
        if (target == soloTarget)
        {
            string back = target.Guest != null ? "빈 곳을 탭하면 모든 소리 · 끌어내면 다시 나뉨" : "다시 탭하면 모든 소리";
            SetHint("<b>" + title + "</b>\n<size=80%>" + description + "</size>\n<size=65%>" + back + "</size>");
        }
        else
        {
            SetHint("<b>" + title + "</b>\n<size=80%>" + description + "</size>");
        }
    }

    void SetHint(string text)
    {
        if (hintText != null)
            hintText.text = text;
    }

    static void Vibrate()
    {
#if UNITY_ANDROID && !UNITY_EDITOR
        Handheld.Vibrate();
#endif
    }

    public static Color ColorOf(string type)
    {
        switch (type)
        {
            case "nature": return new Color(0.35f, 0.65f, 1f);   // 자연: 파랑
            case "people": return new Color(0.4f, 0.9f, 0.5f);   // 사람: 초록
            case "vehicle": return new Color(1f, 0.6f, 0.2f);    // 탈것: 주황
            case "music": return new Color(0.75f, 0.5f, 1f);     // 음악: 보라
            case "animal": return new Color(1f, 0.85f, 0.3f);    // 동물: 노랑
            default: return Color.white;
        }
    }
}
