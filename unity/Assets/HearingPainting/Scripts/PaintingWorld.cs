using System.Collections.Generic;
using UnityEngine;
using UnityEngine.XR.ARFoundation;

// 그림 한 장의 소리 세계 (그림마다 프리팹 하나).
// PaintingSoundWorld가 인식한 이미지 이름에 맞는 프리팹을 그림 위에 생성하고 Setup을 부른다.
// 그림을 AI 깊이 지도로 입체 창문처럼 열고, scene.json의 소리원을 그 깊이에 배치한다.
public class PaintingWorld : MonoBehaviour
{
    [Header("그림")]
    [Tooltip("Reference Image Library에 적은 이미지 이름과 같아야 함")]
    public string imageName = "rainy_day";

    [Header("AI 결과 (Assets/Resources 기준, 확장자 없이)")]
    public string sceneJsonPath = "HearingPainting/scene";
    public string soundFolder = "HearingPainting/sounds";
    public string depthMapPath = "HearingPainting/depth";

    [Tooltip("그림 텍스처를 넣은 재질 (URP Unlit, Render Face Both). 입체 창문에 쓰임")]
    public Material paintingMaterial;

    [Header("비 효과 (이 id의 소리원이 있을 때만)")]
    public bool showRain = true;
    public string rainSourceId = "rain";
    [Tooltip("초당 빗방울 수. 빗소리가 클수록 이보다 늘어남")]
    public float rainRate = 350f;

    [Header("에디터 미리보기 (폰 없이 Play할 때 그림 크기, m)")]
    public Vector2 previewSize = new Vector2(0.5f, 0.38f);

    public PaintingSoundWorld Manager { get; private set; }
    public PaintingScene Scene { get; private set; }
    public Vector2 Size { get; private set; }
    public float DepthScale { get; private set; } = 1f;
    public readonly List<SoundSource> Sources = new List<SoundSource>();

    public string Title => Scene != null ? Scene.title : imageName;

    // 그림 속 공간 끌어내기 (R3): Pulled = 목표 상태, 진행도가 0보다 크면 펼치는 중이거나 펼친 상태
    public bool Pulled { get; private set; }
    public bool PullBusy => Pulled || pullRaw > 0f;
    public bool Hidden { get; private set; }     // 다른 그림을 끌어내는 동안 숨김
    float pullRaw;      // 0~1 선형 진행
    float pullT;        // 0~1 부드럽게 가속·감속한 진행

    DepthMap depthMap;
    PaintingFrame frame;
    DepthWindow depthWindow;
    RainEffect rain;
    Transform debugCorner;
    bool layoutDirty;
    float openTime;
    float openAmount;

    float VSign => Manager.flipVertical ? -1f : 1f;
    float DSign => Manager.flipDepth ? 1f : -1f;     // 기본: 이미지 법선(+y)의 반대쪽 = 그림 뒤
    float Eye => Manager.viewDistance * Size.x;

    // 프리팹을 생성한 직후 한 번 부른다. AI 결과를 못 찾으면 false
    public bool Setup(PaintingSoundWorld manager, Vector2 size)
    {
        Manager = manager;
        Size = size;
        DepthScale = manager.depthScale;

        TextAsset json = Resources.Load<TextAsset>(sceneJsonPath);
        if (json == null)
        {
            Debug.LogError("[" + imageName + "] scene.json을 찾지 못함: Resources/" + sceneJsonPath);
            return false;
        }
        Scene = JsonUtility.FromJson<PaintingScene>(json.text);

        depthMap = DepthMap.Load(depthMapPath);
        if (depthMap == null)
            Debug.LogWarning("[" + imageName + "] 깊이 지도를 찾지 못함: Resources/" + depthMapPath + " (scene.json의 depth 값으로 배치)");

        if (manager.showDepthWindow && depthMap != null && paintingMaterial != null)
        {
            depthWindow = new GameObject("DepthWindow").AddComponent<DepthWindow>();
            depthWindow.transform.SetParent(transform, false);
            depthWindow.Init(paintingMaterial, depthMap, manager.popLayers, manager.popLayerMaterial,
                             manager.lineMaterial, manager.revealWireEvery,
                             manager.useBakedLayers ? BakedLayerFolder() : null);
            depthWindow.StartReveal(manager.revealScanTime, manager.revealOpenDelay + manager.openDuration);
        }

        frame = new GameObject("PaintingFrame").AddComponent<PaintingFrame>();
        frame.transform.SetParent(transform, false);
        frame.Init(manager.lineMaterial);
        frame.Pulse();

        for (int i = 0; i < Scene.sources.Length; i++)
        {
            SoundSourceData data = Scene.sources[i];
            GameObject go = new GameObject("Source_" + data.id);
            go.transform.SetParent(transform, false);
            SoundSource source = go.AddComponent<SoundSource>();
            AudioClip clip = Resources.Load<AudioClip>(soundFolder + "/" + data.file);
            // 스캔이 끝나고 창문이 열리기 시작한 뒤 하나씩 등장
            source.Init(this, data, clip, PaintingSoundWorld.ColorOf(data.type), manager.revealOpenDelay + 0.6f + i * 0.35f);
            Sources.Add(source);
        }

        SoundSource rainSource = Sources.Find(s => s.Data.id == rainSourceId);
        if (showRain && rainSource != null)
        {
            rain = new GameObject("Rain").AddComponent<RainEffect>();
            rain.transform.SetParent(transform, false);
            rain.Init(manager.lineMaterial, rainSource);
            rain.baseRate = rainRate;
        }

        if (manager.showDebugCorner)
        {
            // 그림의 왼쪽 위 모서리에 작은 흰 상자를 둬서 세로 방향이 맞는지 확인
            debugCorner = GameObject.CreatePrimitive(PrimitiveType.Cube).transform;
            Destroy(debugCorner.GetComponent<Collider>());
            debugCorner.SetParent(transform, false);
        }

        Layout();
        return true;
    }

    // PaintingSoundWorld가 매 프레임 부른다 (입력 처리 뒤)
    public void Tick()
    {
        Record(shown, shownJumps, transform.position);      // 측정: 화면에 보이는 그림 위치

        // 그림이 천천히 열림: 깊이 0 → DepthScale
        if (openAmount < 1f)
        {
            openTime += Time.deltaTime;
            openAmount = Mathf.SmoothStep(0f, 1f, (openTime - Manager.revealOpenDelay) / Manager.openDuration);
            layoutDirty = true;
        }
        // 끌어내기: 목표(0 또는 1)를 향해 popDuration 동안 진행
        float pullTarget = Pulled ? 1f : 0f;
        if (!Mathf.Approximately(pullRaw, pullTarget))
        {
            pullRaw = Mathf.MoveTowards(pullRaw, pullTarget, Time.deltaTime / Mathf.Max(Manager.popDuration, 0.01f));
            pullT = pullRaw;    // 층마다 따로 부드럽게 처리하므로 여기서는 선형 진행만
            layoutDirty = true;
        }
        if (layoutDirty)
        {
            layoutDirty = false;
            Layout();
        }
        if (depthWindow != null && !Hidden)
            depthWindow.UpdateReveal(Time.deltaTime);
    }

    public void MarkDirty()
    {
        layoutDirty = true;
    }

    // 등장 연출 다시 보기 (그림 빈 곳 두 번 탭): 창문을 닫았다가 스캔부터 다시
    public void ReplayReveal()
    {
        if (PullBusy)
            return;
        openTime = 0f;
        openAmount = 0f;
        layoutDirty = true;
        frame.Pulse();
        foreach (SoundSource s in Sources)
            s.RestartAppear();
        if (depthWindow != null)
            depthWindow.StartReveal(Manager.revealScanTime, Manager.revealOpenDelay + Manager.openDuration);
    }

    // 끌어내기 켜기·끄기. 펼치는 순간부터 돌아올 때까지 그림 위치를 고정한다
    public void TogglePull()
    {
        Pulled = !Pulled;
        frame.Pulse();
        layoutDirty = true;
    }

    // 다른 그림을 끌어내는 동안 이 그림을 숨김 (소리는 PaintingSoundWorld.ApplyMix가 끔)
    public void SetHidden(bool hidden)
    {
        Hidden = hidden;
        foreach (Renderer r in GetComponentsInChildren<Renderer>(true))
            r.enabled = !hidden;
        if (!hidden && depthWindow != null)
            depthWindow.ReapplyVisibility();
    }

    // 추적 안정화 상태 (C4·C5·C2)
    float offTimer;        // 떨림 무시 구간을 벗어난 시간
    float jumpTimer;       // 큰 차이가 이어진 시간
    float sizeTimer;       // 크기 차이가 이어진 시간
    bool correcting;       // 지금 따라가는 중

    public void Follow(ARTrackedImage image)
    {
        RecordRaw(image.transform.position);
        // 펼치는 중이거나 펼친 상태에서는 고정 (가까이 다가가 추적이 흔들려도 장면이 움직이지 않게)
        if (PullBusy)
            return;
        float k = 1f - Mathf.Exp(-Manager.followSharpness * Time.deltaTime);

        if (!Manager.stabilize)
        {
            // 이전 방식: 매 프레임 부드럽게 따라가고, 추정 크기 변화를 바로 반영
            transform.position = Vector3.Lerp(transform.position, image.transform.position, k);
            transform.rotation = Quaternion.Slerp(transform.rotation, image.transform.rotation, k);
            if (Vector2.Distance(image.size, Size) > 0.001f)
            {
                Size = image.size;
                layoutDirty = true;
            }
            return;
        }

        float w = Mathf.Max(Size.x, 0.05f);
        float dist = Vector3.Distance(transform.position, image.transform.position);
        float angle = Quaternion.Angle(transform.rotation, image.transform.rotation);

        // C5 튐 거부: 한 번에 크게 뛴 값은 jumpHold초 이어질 때만 실제 이동으로 인정
        if (dist > Manager.jumpReject * w)
        {
            jumpTimer += Time.deltaTime;
            if (jumpTimer < Manager.jumpHold)
                return;
            correcting = true;
        }
        else
        {
            jumpTimer = 0f;
        }

        // C4 떨림 무시: 작은 차이는 무시, 차이가 deadbandHold초 이어질 때만 천천히 따라감
        bool inside = dist < Manager.deadbandPosition * w && angle < Manager.deadbandAngle;
        if (!correcting)
        {
            if (inside)
                offTimer = 0f;
            else if ((offTimer += Time.deltaTime) >= Manager.deadbandHold)
                correcting = true;
        }
        if (correcting)
        {
            transform.position = Vector3.Lerp(transform.position, image.transform.position, k);
            transform.rotation = Quaternion.Slerp(transform.rotation, image.transform.rotation, k);
            if (dist < 0.3f * Manager.deadbandPosition * w && angle < 0.3f * Manager.deadbandAngle)
            {
                correcting = false;      // 충분히 따라붙으면 다시 멈춤
                offTimer = 0f;
            }
        }

        // C2 크기: 생성 때 고정한 크기와 sizeTolerance 넘게 다른 상태가 sizeHold초 이어질 때만 천천히 보정
        if (Mathf.Abs(image.size.x - Size.x) > Manager.sizeTolerance * Size.x)
        {
            if ((sizeTimer += Time.deltaTime) >= Manager.sizeHold)
            {
                Size = Vector2.Lerp(Size, image.size, 1f - Mathf.Exp(-2f * Time.deltaTime));
                layoutDirty = true;
            }
        }
        else
        {
            sizeTimer = 0f;
        }
    }

    // ---------- 측정 (결정사항 G4): 화면에 보이는 위치와 ARCore 원래 값의 떨림·튐 ----------
    const float StatsWindow = 30f;     // 떨림: 최근 30초 표준편차 (목표 5mm 이하)
    const float JumpMeters = 0.02f;    // 큰 튐: 한 프레임에 2cm 초과 (목표 분당 0회)
    readonly List<(float t, Vector3 p)> shown = new List<(float, Vector3)>();
    readonly List<(float t, Vector3 p)> raw = new List<(float, Vector3)>();
    readonly List<float> shownJumps = new List<float>();
    readonly List<float> rawJumps = new List<float>();

    void RecordRaw(Vector3 p) => Record(raw, rawJumps, p);

    void Record(List<(float t, Vector3 p)> list, List<float> jumps, Vector3 p)
    {
        if (list.Count > 0 && Vector3.Distance(list[list.Count - 1].p, p) > JumpMeters)
            jumps.Add(Time.time);
        list.Add((Time.time, p));
        while (list.Count > 0 && list[0].t < Time.time - StatsWindow)
            list.RemoveAt(0);
        while (jumps.Count > 0 && jumps[0] < Time.time - 60f)
            jumps.RemoveAt(0);
    }

    public void ResetStats()
    {
        shown.Clear(); raw.Clear(); shownJumps.Clear(); rawJumps.Clear();
    }

    static float JitterMm(List<(float t, Vector3 p)> list)
    {
        if (list.Count < 2) return 0f;
        Vector3 mean = Vector3.zero;
        foreach (var x in list) mean += x.p;
        mean /= list.Count;
        float sq = 0f;
        foreach (var x in list) sq += (x.p - mean).sqrMagnitude;
        return Mathf.Sqrt(sq / list.Count) * 1000f;
    }

    public string StatsLine()
    {
        float span = shown.Count > 1 ? shown[shown.Count - 1].t - shown[0].t : 0f;
        return $"jitter {JitterMm(shown):0.0} mm (raw {JitterMm(raw):0.0})  jumps/min {shownJumps.Count} (raw {rawJumps.Count})  size {Size.x * 100f:0.0} cm  [{span:0}s]";
    }

    public float ChangeDepthScale(float delta)
    {
        DepthScale = Mathf.Clamp(DepthScale + delta, Manager.minDepthScale, Manager.maxDepthScale);
        layoutDirty = true;
        return DepthScale;
    }

    // 그림 크기(추정값)·깊이 배율·소리원 위치가 바뀔 때마다 다시 계산한다
    void Layout()
    {
        float w = Size.x;
        float h = Size.y;
        float amount = DepthScale * Manager.depthRatio * openAmount;
        // 끌어내기(팝업): 크기는 1배 → popScale배, 가장 가까운 층은 (펼친 폭 × popDepthRatio)만큼 방 쪽으로
        float eased = Mathf.SmoothStep(0f, 1f, pullT);
        float scale = Mathf.Lerp(1f, Manager.popScale, eased);
        float visualScale = Mathf.Lerp(1f, Manager.popVisualScale, eased);
        float pullDepth = Manager.popDepthRatio * w * Manager.popScale * DepthScale;

        foreach (SoundSource s in Sources)
        {
            if (s.Host != null)
                continue;   // 다른 소리와 섞인 소리원은 짝 주위를 돈다
            SoundSourceData d = s.Data;
            float depth;
            float farValue;
            if (depthMap != null)
            {
                farValue = depthMap.Sample(d.u, d.v);
                depth = farValue * amount * w - Manager.coreSize * w;  // 입체 그림 표면보다 살짝 앞
            }
            else
            {
                farValue = d.depth;
                depth = (Manager.minDepth + d.depth * amount) * w;
            }
            Vector3 surface = PaintingSoundWorld.PaintingPoint(d.u, d.v, 0f, w, h, VSign, DSign, Eye);
            Vector3 target = PaintingSoundWorld.PaintingPoint(d.u, d.v, depth, w, h, VSign, DSign, Eye);
            if (pullT > 0f)
            {
                // 소리원은 자기 깊이가 속한 층과 함께 나온다. 층 조각보다 살짝 앞(방 쪽)에 놓아 묻히지 않게
                float fraction; float p;
                if (depthWindow != null && depthWindow.LayerCount > 0)
                {
                    int layer = depthWindow.LayerAt(d.u, d.v);
                    fraction = depthWindow.PulledFraction(layer);
                    p = depthWindow.LayerProgress(layer, pullT);
                }
                else
                {
                    fraction = 1f - farValue;
                    p = eased;
                }
                float layerScale = PaintingSoundWorld.PopLayerScale(fraction, Manager.popScale, pullDepth, Eye, Manager.popPerspective);
                Vector3 pulled = PaintingSoundWorld.PulledPoint(d.u, d.v, fraction, w, h, VSign, DSign, layerScale, pullDepth)
                               + new Vector3(0f, -DSign * Manager.coreSize * w * Manager.popVisualScale, 0f);
                target = Vector3.Lerp(target, pulled, p);
                surface = target;   // 이미 나타난 뒤라 등장 시작점은 쓰지 않음
            }
            s.SetLayout(surface, target, w * visualScale);   // 구·링·라벨은 popVisualScale배까지만 커짐
        }

        frame.SetSize(w, h);
        if (depthWindow != null)
            depthWindow.SetShape(w, h, VSign, DSign, amount, Eye, pullT, Manager.popScale, pullDepth, Manager.popPerspective);
        if (rain != null)
            rain.SetShape(w * scale, h * scale, VSign, DSign, amount, openAmount);

        if (debugCorner != null)
        {
            debugCorner.localPosition = new Vector3(-w * 0.5f, 0f, VSign * h * 0.5f);
            debugCorner.localScale = Vector3.one * w * 0.04f;
        }
    }

    // 미리 만든 팝업 층이 있는 Resources 폴더: scene.json과 같은 폴더의 layers
    // (rainy_day: HearingPainting/layers, 새 그림: HearingPainting/<key>/layers)
    string BakedLayerFolder()
    {
        int i = sceneJsonPath.LastIndexOf('/');
        return i >= 0 ? sceneJsonPath.Substring(0, i) + "/layers" : "layers";
    }

    // 화면에서 쏜 레이가 이 그림의 어느 위치(u, v)를 가리키는지 구한다.
    // planePoint를 지나고 그림과 평행한 평면에 레이를 맞힌 뒤, PaintingPoint의 반대 계산을 한다.
    public bool RayToUV(Ray ray, Vector3 planePoint, out Vector2 uv, out float distance)
    {
        uv = Vector2.zero;
        distance = 0f;
        Plane plane = new Plane(transform.up, planePoint);
        if (!plane.Raycast(ray, out distance))
            return false;

        Vector3 local = transform.InverseTransformPoint(ray.GetPoint(distance));
        float spread = (Eye + local.y * DSign) / Eye;   // 깊이만큼 넓어진 비율을 되돌린다
        uv.x = local.x / (Size.x * spread) + 0.5f;
        uv.y = 0.5f - local.z / (Size.y * VSign * spread);
        return true;
    }

    // 다른 그림에서 끌고 온 소리원을 이 그림의 소리원으로 받는다
    public void Adopt(SoundSource s)
    {
        if (s.World == this)
            return;
        PaintingWorld old = s.World;
        old.Sources.Remove(s);
        old.MarkDirty();
        Sources.Add(s);
        s.SetWorld(this);
        frame.Pulse();
        layoutDirty = true;
    }
}
