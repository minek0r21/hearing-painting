using System.Collections.Generic;
using UnityEngine;
using TMPro;

// 소리원 하나: 3D 소리 재생, 음량 측정, 음파 링, 이름 라벨, 충돌 감지
public class SoundSource : MonoBehaviour
{
    public SoundSourceData Data { get; private set; }
    public float Level => level;    // 지금 소리 크기 0~1 (비 효과가 읽음)
    public PaintingWorld World { get; private set; }
    public SoundSource Host { get; private set; }   // 내가 섞여 들어간 소리원 (없으면 null)
    public SoundSource Guest { get; private set; }  // 나에게 섞여 들어온 소리원 (없으면 null)
    public bool IsFree => Host == null && Guest == null;
    public Color Color => color;
    // 지금 닿아 있는 다른 소리원들 (OnTriggerEnter/Exit로 관리)
    public readonly List<SoundSource> Touching = new List<SoundSource>();

    PaintingSoundWorld manager;
    AudioSource audioSource;
    SphereCollider hitbox;
    Transform core;
    TextMeshPro label;
    Color color;

    Vector3 surfacePosition;    // 그림 표면 위 위치 (등장 시작점)
    Vector3 targetPosition;     // 깊이만큼 그림 뒤로 들어간 최종 위치
    float paintingWidth = 0.5f;

    float appearDelay;
    float appearTime;
    float gain;
    float mixGain = 1f;         // 솔로·다가가기에 따른 음량 배율
    bool highlighted;
    float highlight;            // 강조 정도 0~1 (부드럽게 바뀜)
    float level;
    float peak = 0.01f;
    float ringTimer;
    float orbit;                // 섞였을 때 짝 주위를 도는 각도
    bool appearBurstDone;       // 등장 순간 음파를 이미 냈는지
    readonly float[] samples = new float[256];

    public void Init(PaintingWorld world, SoundSourceData data, AudioClip clip, Color color, float appearDelay)
    {
        World = world;
        manager = world.Manager;
        Data = data;
        this.color = color;
        this.appearDelay = appearDelay;

        // 3D 소리
        audioSource = gameObject.AddComponent<AudioSource>();
        audioSource.clip = clip;
        audioSource.loop = true;
        audioSource.playOnAwake = false;
        audioSource.spatialBlend = 1f;                          // 완전한 3D: 거리·방향에 따라 크기와 좌우가 바뀜
        audioSource.rolloffMode = AudioRolloffMode.Logarithmic; // 가까울수록 커짐
        audioSource.dopplerLevel = 0f;                          // 폰을 움직여도 음 높이가 흔들리지 않게
        audioSource.maxDistance = 20f;
        audioSource.volume = 0f;
        if (clip != null)
        {
            audioSource.time = Random.Range(0f, clip.length * 0.9f); // 소리원마다 시작 지점을 달리함
            audioSource.Play();
        }
        else
        {
            Debug.LogWarning("소리 파일을 찾지 못함: " + data.file);
        }

        // 충돌 감지 (10주차 충돌 이벤트): 움직이는 물체라 Kinematic Rigidbody + Trigger 콜라이더.
        // 같은 콜라이더를 탭 판정(레이캐스트)에도 쓴다
        Rigidbody body = gameObject.AddComponent<Rigidbody>();
        body.isKinematic = true;
        body.useGravity = false;
        hitbox = gameObject.AddComponent<SphereCollider>();
        hitbox.isTrigger = true;
        hitbox.radius = 0.001f;

        // 소리원 표시용 구 (보이기만 함)
        GameObject sphere = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        sphere.name = "Core";
        Destroy(sphere.GetComponent<Collider>());
        sphere.transform.SetParent(transform, false);
        MeshRenderer meshRenderer = sphere.GetComponent<MeshRenderer>();
        if (manager.coreMaterial != null)
            meshRenderer.sharedMaterial = manager.coreMaterial;
        meshRenderer.material.color = color;
        meshRenderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        core = sphere.transform;

        // 이름 라벨
        GameObject labelObject = new GameObject("Label");
        labelObject.transform.SetParent(transform, false);
        label = labelObject.AddComponent<TextMeshPro>();
        if (manager.koreanFont != null)
            label.font = manager.koreanFont;
        label.fontSize = 10f;
        label.alignment = TextAlignmentOptions.Center;
        label.rectTransform.sizeDelta = new Vector2(40f, 3f);   // 줄바꿈되지 않게 넓게
        label.color = Color.white;
        RefreshLabel();
    }

    public void SetLayout(Vector3 surface, Vector3 target, float width)
    {
        surfacePosition = surface;
        targetPosition = target;
        paintingWidth = width;
        audioSource.minDistance = width * manager.minDistance;  // 이 거리 안에서는 최대 음량
    }

    // 다른 그림으로 옮겨 감. 월드 위치를 유지한 채 부모만 바꿔서 화면에서는 부드럽게 미끄러진다
    public void SetWorld(PaintingWorld world)
    {
        World = world;
        transform.SetParent(world.transform, true);
        transform.localRotation = Quaternion.identity;
        transform.localScale = Vector3.one;
    }

    // volumeScale: 1 = 그대로, 0.3 = 줄임, 0 = 끔 / highlighted: 크게·자주 빛나게
    public void SetMix(float volumeScale, bool highlighted)
    {
        mixGain = volumeScale;
        this.highlighted = highlighted;
        label.fontStyle = highlighted ? FontStyles.Bold : FontStyles.Normal;
    }

    // ---------- V3: 끌 때 빛 꼬리, 섞일 때 불꽃 ----------
    TrailRenderer trail;

    public void SetTrail(bool on)
    {
        if (trail == null)
        {
            trail = gameObject.AddComponent<TrailRenderer>();
            trail.sharedMaterial = manager.lineMaterial;
            trail.time = 0.4f;
            trail.minVertexDistance = 0.002f;
            trail.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            trail.receiveShadows = false;
            Gradient g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(color, 0f), new GradientColorKey(color, 1f) },
                      new[] { new GradientAlphaKey(0.9f, 0f), new GradientAlphaKey(0f, 1f) });
            trail.colorGradient = g;
            trail.widthCurve = AnimationCurve.Linear(0f, 1f, 1f, 0f);
            trail.emitting = false;
        }
        trail.widthMultiplier = paintingWidth * manager.coreSize * 0.9f;
        if (on)
            trail.Clear();
        trail.emitting = on;
    }

    // 두 색이 섞인 작은 불꽃 입자가 한 번 터진다
    void SpawnSparks(Color a, Color b)
    {
        GameObject go = new GameObject("MergeSparks");
        go.transform.position = transform.position;
        ParticleSystem ps = go.AddComponent<ParticleSystem>();
        ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

        ParticleSystem.MainModule main = ps.main;
        main.duration = 0.5f;
        main.loop = false;
        main.startLifetime = new ParticleSystem.MinMaxCurve(0.45f, 0.8f);
        main.startSpeed = new ParticleSystem.MinMaxCurve(paintingWidth * 0.4f, paintingWidth * 0.9f);
        main.startSize = new ParticleSystem.MinMaxCurve(paintingWidth * 0.006f, paintingWidth * 0.013f);
        main.startColor = new ParticleSystem.MinMaxGradient(a, b);
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.gravityModifier = 0f;
        main.maxParticles = 60;

        ParticleSystem.EmissionModule emission = ps.emission;
        emission.rateOverTime = 0f;
        emission.SetBursts(new[] { new ParticleSystem.Burst(0f, 36) });

        ParticleSystem.ShapeModule shape = ps.shape;
        shape.shapeType = ParticleSystemShapeType.Sphere;
        shape.radius = paintingWidth * 0.01f;

        ParticleSystem.ColorOverLifetimeModule col = ps.colorOverLifetime;
        col.enabled = true;
        Gradient fade = new Gradient();
        fade.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                     new[] { new GradientAlphaKey(1f, 0f), new GradientAlphaKey(0f, 1f) });
        col.color = new ParticleSystem.MinMaxGradient(fade);

        ParticleSystemRenderer r = go.GetComponent<ParticleSystemRenderer>();
        r.sharedMaterial = manager.lineMaterial;
        r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        r.receiveShadows = false;

        ps.Play();
        Destroy(go, 1.5f);
    }

    // 등장 연출 다시 보기: 그림 표면에서 다시 튀어나오게 (소리도 0에서 다시 커짐)
    public void RestartAppear()
    {
        appearTime = 0f;
        appearBurstDone = false;
    }

    // ---------- 섞기 ----------

    // host에 섞여 들어간다. host와 같은 그림에 있어야 한다 (PaintingWorld.Adopt 먼저)
    public void MergeInto(SoundSource host)
    {
        Host = host;
        host.Guest = this;
        Data.u = host.Data.u;
        Data.v = host.Data.v;
        orbit = Random.Range(0f, Mathf.PI * 2f);
        RefreshLabel();
        host.RefreshLabel();
        host.Burst(color);
        Burst(host.color);
        host.SpawnSparks(host.color, color);
    }

    // 섞인 짝에서 빠져나온다
    public void Separate()
    {
        if (Host == null)
            return;
        SoundSource host = Host;
        host.Guest = null;
        Host = null;
        host.RefreshLabel();
        RefreshLabel();
    }

    void RefreshLabel()
    {
        label.text = Guest != null ? Data.label + " + " + Guest.Data.label : Data.label;
        label.enabled = Host == null;   // 섞여 들어간 쪽은 짝의 라벨에 함께 표시
    }

    // ---------- 충돌 이벤트 ----------

    void OnTriggerEnter(Collider other)
    {
        SoundSource o = other.GetComponent<SoundSource>();
        if (o != null && o != this && !Touching.Contains(o))
            Touching.Add(o);
    }

    void OnTriggerExit(Collider other)
    {
        SoundSource o = other.GetComponent<SoundSource>();
        if (o != null)
            Touching.Remove(o);
    }

    // ---------- 매 프레임 ----------

    void Update()
    {
        // 1) 위치: 처음엔 그림 표면에서 깊이 쪽으로 들어가며 등장, 그 뒤엔 목표 위치를 부드럽게 따라감
        appearTime += Time.deltaTime;
        float appear = Mathf.Clamp01((appearTime - appearDelay) / 1.2f);
        float eased = 1f - Mathf.Pow(1f - appear, 3f);
        if (!appearBurstDone && appear > 0f && World != null && !World.Hidden)
        {
            appearBurstDone = true;
            Burst(color);       // 튀어나오는 순간 큰 음파 한 번
        }
        Vector3 desired;
        if (Host != null)
        {
            // 섞였으면 짝 주위를 그림과 나란한 원을 그리며 돈다
            orbit += Time.deltaTime * 1.8f;
            float r = paintingWidth * manager.coreSize * 1.4f;
            desired = Host.transform.localPosition + new Vector3(Mathf.Cos(orbit), 0f, Mathf.Sin(orbit)) * r;
        }
        else
        {
            desired = Vector3.Lerp(surfacePosition, targetPosition, eased);
        }
        if (appear < 1f)
            transform.localPosition = desired;
        else
            transform.localPosition = Vector3.Lerp(transform.localPosition, desired, 1f - Mathf.Exp(-18f * Time.deltaTime));

        // 2) 음량: 솔로·다가가기 상태에 따라 부드럽게 커지고 작아짐
        gain = Mathf.MoveTowards(gain, mixGain * appear, Time.deltaTime * 2f);
        audioSource.volume = Data.volume * gain;
        highlight = Mathf.MoveTowards(highlight, highlighted ? 1f : 0f, Time.deltaTime * 4f);

        // 3) 지금 재생 중인 소리의 크기(RMS)를 재서 0~1 레벨로 바꿈
        audioSource.GetOutputData(samples, 0);
        float sum = 0f;
        for (int i = 0; i < samples.Length; i++)
            sum += samples[i] * samples[i];
        float rms = Mathf.Sqrt(sum / samples.Length);
        // 소리원마다 크기가 달라서, 최근 최댓값(peak) 대비 비율로 맞춘다
        peak = Mathf.Max(rms, Mathf.Lerp(peak, rms, Time.deltaTime * 0.3f), 0.0001f);
        float raw = gain > 0.01f ? Mathf.Clamp01(rms / peak) : 0f;
        level = Mathf.Lerp(level, raw, Time.deltaTime * 12f);

        // 4) 구는 소리에 맞춰 살짝 커졌다 작아지고, 강조되면 더 커짐
        float baseScale = paintingWidth * manager.coreSize;
        float coreScale = baseScale * eased * (1f + 0.4f * level) * (1f + 0.6f * highlight);
        core.localScale = Vector3.one * coreScale;
        // 충돌·탭 판정 크기는 보이는 구보다 넉넉하게, 소리에 따라 흔들리지 않게 고정
        hitbox.radius = Mathf.Max(baseScale * 1.5f * eased, 0.001f);
        UpdateLabel(coreScale, eased);

        // 5) 음파 링: 소리가 클수록(또는 강조될수록) 자주, 크게 내보냄
        ringTimer -= Time.deltaTime;
        if (manager.showRings && gain > 0.05f && ringTimer <= 0f && !World.Hidden)
        {
            // 섞인 짝이 있으면 두 색을 번갈아 내보낸다
            Color ringColor = Guest != null && Random.value < 0.5f ? Guest.color : color;
            SpawnRing(coreScale * 0.5f, 1f, ringColor);
            ringTimer = Mathf.Lerp(0.8f, 0.25f, Mathf.Max(level, highlight * 0.8f));
        }
    }

    void UpdateLabel(float coreScale, float eased)
    {
        Camera cam = Camera.main;
        if (cam == null)
            return;

        float labelHeight = paintingWidth * manager.labelSize * (1f + 0.4f * highlight);
        Transform t = label.transform;
        t.position = transform.position + cam.transform.up * (coreScale * 0.5f + labelHeight);
        t.rotation = Quaternion.LookRotation(t.position - cam.transform.position, cam.transform.up);
        t.localScale = Vector3.one * labelHeight * eased;

        Color c = label.color;
        c.a = Mathf.Lerp(0.3f, 1f, mixGain);
        label.color = c;
    }

    // 섞이는 순간 크게 퍼지는 링
    void Burst(Color c)
    {
        SpawnRing(paintingWidth * manager.coreSize * 0.5f, 3f, c);
        ringTimer = 0.15f;
    }

    void SpawnRing(float startRadius, float sizeScale, Color ringColor)
    {
        GameObject ringObject = new GameObject("Ring");
        ringObject.transform.SetParent(transform, false);
        SoundRing ring = ringObject.AddComponent<SoundRing>();

        float size = paintingWidth * manager.ringSize * (0.5f + level) * (1f + 0.5f * highlight) * sizeScale;
        Color c = ringColor;
        c.a = 0.9f * Mathf.Max(gain, sizeScale > 1f ? 1f : 0f);
        ring.Init(manager.lineMaterial, c, startRadius, startRadius + size, paintingWidth * 0.004f * (0.6f + level), 1.4f);
    }
}
