using System.Collections.Generic;
using UnityEngine;

// AI 깊이 지도로 그림을 입체 면으로 만든다. 실제 그림 위에 겹쳐 그려서,
// 폰을 옆으로 움직이면 앞의 사람과 뒤의 건물이 따로 움직이는(시차) 창문처럼 보인다.
// "그림 속 공간 끌어내기" 때는 깊이를 몇 개 층으로 나눈 그림 조각들이 팝업북처럼 방 쪽으로 미끄러져 나온다.
[RequireComponent(typeof(MeshFilter), typeof(MeshRenderer))]
public class DepthWindow : MonoBehaviour
{
    // 이 창이 만든 메시·재질·텍스처. 리셋으로 소리 세계를 지울 때 함께 정리 (11/26, 메모리 누적 방지)
    readonly System.Collections.Generic.List<Object> owned = new System.Collections.Generic.List<Object>();

    void OnDestroy()
    {
        foreach (Object o in owned)
            if (o != null)
                Destroy(o);
        owned.Clear();
    }

    const int Columns = 120;    // 가로 격자 수. 클수록 매끈하지만 무거워짐

    Mesh mesh;
    Vector3[] vertices;
    float[] far;
    float[] farSmooth;          // 아주 부드럽게 다듬은 깊이 (펼쳤을 때 층 사이 틈을 메우는 경사면용)
    MaterialPropertyBlock fillerTint;   // 필드 초기화에서 만들면 Unity가 막음 → 처음 쓸 때 만든다
    int nx;
    int ny;
    MeshRenderer meshRenderer;

    // 팝업 층: 0 = 가장 가까운 층 ... N-1 = 가장 먼 층, 그리고 맨 뒤 바닥판(원본 전체, 어둡게)
    Transform[] layers;
    float[] layerAvgFar;
    float[] thresholds;         // 층 경계 깊이값 (오름차순)
    Transform baseCard;
    bool layersShown;

    public int LayerCount => layers != null ? layers.Length : 0;

    // ---------- V1 AI 스캔 등장: 스캔선이 훑고 지나간 자리에 깊이 격자(가까움 주황 → 멂 파랑)가 나타났다 사라짐 ----------
    Mesh wireMesh;
    MeshRenderer wireRenderer;
    Color[] wireColors;
    Color[] wireBase;           // 깊이별 기본 색
    LineRenderer scanLine;
    float revealTime = -1f;     // 0 이상이면 연출 진행 중
    float scanDuration = 1.2f;
    float wireFadeEnd = 2.6f;
    float lastW, lastH, lastVSign = 1f, lastDSign = -1f;

    // 처음 인식 또는 다시 보기(두 번 탭) 때 호출
    public void StartReveal(float scanTime, float fadeEnd)
    {
        if (wireMesh == null)
            return;
        scanDuration = Mathf.Max(0.2f, scanTime);
        wireFadeEnd = Mathf.Max(scanDuration + 0.2f, fadeEnd);
        revealTime = 0f;
        wireRenderer.enabled = true;
        scanLine.enabled = true;
    }

    void BuildReveal(Material lineMaterial, int every)
    {
        if (lineMaterial == null)
            return;
        every = Mathf.Max(1, every);
        var idx = new List<int>();
        for (int j = 0; j < ny; j += every)          // 가로줄
            for (int i = 0; i < nx - 1; i++) { idx.Add(j * nx + i); idx.Add(j * nx + i + 1); }
        for (int i = 0; i < nx; i += every)          // 세로줄
            for (int j = 0; j < ny - 1; j++) { idx.Add(j * nx + i); idx.Add((j + 1) * nx + i); }

        wireBase = new Color[nx * ny];
        wireColors = new Color[nx * ny];
        Color nearC = new Color(1f, 0.55f, 0.15f, 1f), farC = new Color(0.3f, 0.6f, 1f, 1f);
        for (int k = 0; k < far.Length; k++)
            wireBase[k] = Color.Lerp(nearC, farC, far[k]);

        GameObject go = new GameObject("DepthWire", typeof(MeshFilter), typeof(MeshRenderer));
        go.transform.SetParent(transform, false);
        wireMesh = new Mesh { name = "DepthWire" };
        owned.Add(wireMesh);
        wireMesh.vertices = vertices;
        wireMesh.colors = wireColors;
        wireMesh.SetIndices(idx, MeshTopology.Lines, 0);
        go.GetComponent<MeshFilter>().sharedMesh = wireMesh;
        wireRenderer = go.GetComponent<MeshRenderer>();
        wireRenderer.sharedMaterial = lineMaterial;
        wireRenderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        wireRenderer.receiveShadows = false;
        wireRenderer.enabled = false;

        scanLine = new GameObject("ScanLine").AddComponent<LineRenderer>();
        scanLine.transform.SetParent(transform, false);
        scanLine.useWorldSpace = false;
        scanLine.positionCount = 2;
        scanLine.sharedMaterial = lineMaterial;
        scanLine.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        scanLine.receiveShadows = false;
        scanLine.startColor = scanLine.endColor = new Color(0.75f, 0.95f, 1f, 1f);
        scanLine.enabled = false;
    }

    // PaintingWorld.Tick에서 매 프레임 호출
    public void UpdateReveal(float dt)
    {
        if (revealTime < 0f || wireMesh == null)
            return;
        revealTime += dt;
        float scan = Mathf.Clamp01(revealTime / scanDuration);                 // 스캔선 위치 0(위) ~ 1(아래)
        float fade = 1f - Mathf.Clamp01((revealTime - scanDuration) / (wireFadeEnd - scanDuration));

        // 격자: 스캔선이 지나간 줄부터 밝게, 끝나면 서서히 사라짐
        for (int j = 0; j < ny; j++)
        {
            float v = j / (ny - 1f);
            float shown = Mathf.Clamp01((scan - v) * 12f);  // 스캔선 바로 뒤는 살짝 번지듯 켜짐
            for (int i = 0; i < nx; i++)
            {
                int k = j * nx + i;
                Color c = wireBase[k];
                c.a = shown * fade * 0.9f;
                wireColors[k] = c;
            }
        }
        wireMesh.vertices = vertices;       // 입체 창문이 열리며 휘는 모양을 그대로 따라감
        wireMesh.colors = wireColors;
        wireMesh.RecalculateBounds();

        // 스캔선: 그림 면 바로 앞을 위에서 아래로
        if (scan < 1f)
        {
            float z = (0.5f - scan) * lastH * lastVSign;
            float y = -lastDSign * lastW * 0.01f;
            scanLine.SetPosition(0, new Vector3(-lastW * 0.5f, y, z));
            scanLine.SetPosition(1, new Vector3(lastW * 0.5f, y, z));
            scanLine.widthMultiplier = lastW * 0.008f;
        }
        else
        {
            scanLine.enabled = false;
        }
        if (fade <= 0f)
        {
            wireRenderer.enabled = false;
            revealTime = -1f;
        }
    }

    Material layerTemplate;     // Alpha Clipping 재질 (있으면 층을 매끈한 윤곽으로 오려 냄, 없으면 격자 칸 모양)

    // bakedFolder: 파이프라인이 미리 만든 층(layer0..N-1.png + layers.bytes)이 있는 Resources 폴더. null이거나 없으면 예전 방식
    public void Init(Material material, DepthMap depthMap, int layerCount, Material popLayerTemplate, Material lineMaterial = null, int wireEvery = 4,
                     string bakedFolder = null)
    {
        this.bakedFolder = bakedFolder;
        pendingLineMaterial = lineMaterial;
        pendingWireEvery = wireEvery;
        layerTemplate = popLayerTemplate;
        meshRenderer = GetComponent<MeshRenderer>();
        meshRenderer.sharedMaterial = material;
        meshRenderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        meshRenderer.receiveShadows = false;

        nx = Columns;
        ny = Mathf.Max(2, Mathf.RoundToInt(Columns * depthMap.Height / (float)depthMap.Width));
        vertices = new Vector3[nx * ny];
        far = new float[nx * ny];
        Vector2[] uvs = new Vector2[nx * ny];
        int[] triangles = new int[(nx - 1) * (ny - 1) * 6];

        for (int j = 0; j < ny; j++)
        {
            for (int i = 0; i < nx; i++)
            {
                int k = j * nx + i;
                float u = i / (nx - 1f);
                float v = j / (ny - 1f);
                uvs[k] = new Vector2(u, 1f - v);    // 텍스처 좌표는 아래쪽이 0
                far[k] = depthMap.Sample(u, v);
            }
        }
        farSmooth = far;
        for (int pass = 0; pass < 8; pass++)
            farSmooth = BoxBlur(farSmooth, nx, ny);

        int t = 0;
        for (int j = 0; j < ny - 1; j++)
        {
            for (int i = 0; i < nx - 1; i++)
            {
                int k = j * nx + i;
                triangles[t++] = k;
                triangles[t++] = k + 1;
                triangles[t++] = k + nx;
                triangles[t++] = k + 1;
                triangles[t++] = k + nx + 1;
                triangles[t++] = k + nx;
            }
        }

        mesh = new Mesh();
        owned.Add(mesh);
        mesh.name = "DepthWindow";
        mesh.vertices = vertices;
        mesh.uv = uvs;
        mesh.triangles = triangles;
        GetComponent<MeshFilter>().sharedMesh = mesh;

        BuildLayers(material, depthMap, Mathf.Clamp(layerCount, 2, 8));
        BuildReveal(pendingLineMaterial, pendingWireEvery);
    }

    Material pendingLineMaterial;
    int pendingWireEvery = 4;

    const int LayerColumns = 200;   // 층 조각은 더 촘촘한 격자로 (계단 가장자리를 작게)
    int lcx, lcy;                    // 층 격자 칸 수 (가로, 세로)
    int[] cellLabel;                 // 정리된 층 지도 (칸마다 층 번호)

    // 그림 속 위치(u, v)가 속한 층 (소리원이 자기 그림 조각과 함께 움직이게)
    public int LayerAt(float u, float v)
    {
        int i = Mathf.Clamp((int)(u * lcx), 0, lcx - 1);
        int j = Mathf.Clamp((int)(v * lcy), 0, lcy - 1);
        return cellLabel[j * lcx + i];
    }

    // 깊이값을 면적이 비슷하게 나눠 층을 만든다. 층마다 평평한 그림 조각(격자 칸 단위)이고,
    // 좌표는 -0.5~0.5 정규화 평면이라 매 프레임 꼭짓점을 바꾸지 않고 Transform만 움직인다.
    // 잡음 대책: ① 깊이를 주변과 평균 ② 외톨이 칸을 주변 다수 층으로 ③ 앞 층을 한 칸 넓혀 경계 틈 제거
    void BuildLayers(Material material, DepthMap depthMap, int n)
    {
        if (bakedFolder != null && layerTemplate != null && TryLoadBaked(depthMap, bakedFolder))
        {
            Debug.Log("[DepthWindow] 미리 만든 층 사용: Resources/" + bakedFolder + " (" + layers.Length + "층)");
            MakeBaseCard(material);
            return;
        }
        lcx = LayerColumns;
        lcy = Mathf.Max(2, Mathf.RoundToInt(LayerColumns * depthMap.Height / (float)depthMap.Width));
        float[] cell = new float[lcx * lcy];
        for (int j = 0; j < lcy; j++)
            for (int i = 0; i < lcx; i++)
                cell[j * lcx + i] = depthMap.Sample((i + 0.5f) / lcx, (j + 0.5f) / lcy);
        for (int pass = 0; pass < 3; pass++)
            cell = BoxBlur(cell, lcx, lcy);

        float[] sorted = (float[])cell.Clone();
        System.Array.Sort(sorted);
        thresholds = new float[n - 1];
        for (int q = 1; q < n; q++)
            thresholds[q - 1] = sorted[Mathf.Clamp(Mathf.RoundToInt(sorted.Length * q / (float)n), 0, sorted.Length - 1)];

        int[] label = new int[cell.Length];
        for (int c = 0; c < cell.Length; c++)
            label[c] = LayerOf(cell[c]);
        for (int pass = 0; pass < 2; pass++)
            label = MajorityFilter(label, lcx, lcy, n);
        cellLabel = label;

        var verts = new List<Vector3>[n];
        var uvs = new List<Vector2>[n];
        var tris = new List<int>[n];
        float[] sum = new float[n];
        int[] count = new int[n];
        for (int l = 0; l < n; l++)
        {
            verts[l] = new List<Vector3>(); uvs[l] = new List<Vector2>(); tris[l] = new List<int>();
        }

        // 매끈한 윤곽 방식: 층마다 판 하나 + 투명 가장자리 텍스처 (실패하면 아래 격자 칸 방식으로)
        Texture2D[] masked = layerTemplate != null ? BuildMaskedTextures(material, label, n) : null;
        if (masked != null)
        {
            layers = new Transform[n];
            layerAvgFar = new float[n];
            for (int c = 0; c < cell.Length; c++) { sum[label[c]] += cell[c]; count[label[c]]++; }
            for (int l = 0; l < n; l++)
            {
                layerAvgFar[l] = count[l] > 0 ? sum[l] / count[l] : (l + 0.5f) / n;
                var qv = new List<Vector3>(); var qu = new List<Vector2>();
                AddCorner(qv, qu, 0, 0); AddCorner(qv, qu, nx - 1, 0); AddCorner(qv, qu, 0, ny - 1); AddCorner(qv, qu, nx - 1, ny - 1);
                Material m = new Material(layerTemplate);
                owned.Add(m);
                if (m.HasProperty("_BaseMap")) m.SetTexture("_BaseMap", masked[l]);
                m.mainTexture = masked[l];
                if (m.HasProperty("_Cutoff")) m.SetFloat("_Cutoff", 0.5f);
                layers[l] = MakeCard("PopLayer_" + l, m, qv, qu, new List<int> { 0, 1, 2, 1, 3, 2 }, Color.white);
            }
            MakeBaseCard(material);
            return;
        }

        for (int j = 0; j < lcy; j++)
        {
            for (int i = 0; i < lcx; i++)
            {
                int c = j * lcx + i;
                int own = label[c];
                sum[own] += cell[c]; count[own]++;
                // 자기 층 + (이웃 중 더 가까운 층이 있으면 그 층에도 한 칸 넓혀 넣음)
                for (int l = 0; l <= own; l++)
                {
                    if (l != own && !HasNeighborLabel(label, i, j, l))
                        continue;
                    int b = verts[l].Count;
                    AddCellCorner(verts[l], uvs[l], i, j);
                    AddCellCorner(verts[l], uvs[l], i + 1, j);
                    AddCellCorner(verts[l], uvs[l], i, j + 1);
                    AddCellCorner(verts[l], uvs[l], i + 1, j + 1);
                    tris[l].AddRange(new[] { b, b + 1, b + 2, b + 1, b + 3, b + 2 });
                }
            }
        }

        layers = new Transform[n];
        layerAvgFar = new float[n];
        for (int l = 0; l < n; l++)
        {
            layerAvgFar[l] = count[l] > 0 ? sum[l] / count[l] : (l + 0.5f) / n;
            layers[l] = MakeCard("PopLayer_" + l, material, verts[l], uvs[l], tris[l], Color.white);
        }

        MakeBaseCard(material);
    }

    // ---------- 미리 만든 층 (틈 메우기 11/26) ----------
    // 파이프라인(layers.py)이 층마다 앞 층에 가려진 곳을 LaMa로 채운 RGBA PNG와 층 지도를 만든다.
    // 층 0 = 가장 가까움, 마지막 층 = 불투명 배경판. 층 지도: 가로·세로(각 2바이트) + 칸마다 층 번호, 그림 위쪽 줄부터.
    // 재질은 기존 알파 잘라내기 템플릿 그대로 (보이는 픽셀만 깊이를 써서 소리 구·선과 가림 순서가 맞음)
    string bakedFolder;
    bool baked;

    bool TryLoadBaked(DepthMap depthMap, string folder)
    {
        TextAsset map = Resources.Load<TextAsset>(folder + "/layers");
        if (map == null)
            return false;
        byte[] b = map.bytes;
        if (b.Length < 4)
            return false;
        int cx = b[0] | (b[1] << 8), cy = b[2] | (b[3] << 8);
        if (cx < 2 || cy < 2 || b.Length < 4 + cx * cy)
        {
            Debug.LogWarning("[DepthWindow] 층 지도 크기가 맞지 않음: Resources/" + folder + "/layers");
            return false;
        }
        var tex = new List<Texture2D>();
        for (int k = 0; k < 8; k++)
        {
            Texture2D t = Resources.Load<Texture2D>(folder + "/layer" + k);
            if (t == null)
                break;
            tex.Add(t);
        }
        int n = tex.Count;
        if (n < 2)
        {
            Debug.LogWarning("[DepthWindow] 층 그림이 2장 미만: Resources/" + folder);
            return false;
        }

        lcx = cx; lcy = cy;
        cellLabel = new int[cx * cy];
        for (int c = 0; c < cellLabel.Length; c++)
            cellLabel[c] = Mathf.Min(b[4 + c], n - 1);

        // 층별 평균 깊이 = 접힌 상태(입체 창문)에서 그 층이 그림 뒤 어디에 있는지
        float[] sum = new float[n];
        int[] count = new int[n];
        for (int j = 0; j < cy; j++)
            for (int i = 0; i < cx; i++)
            {
                int l = cellLabel[j * cx + i];
                sum[l] += depthMap.Sample((i + 0.5f) / cx, (j + 0.5f) / cy);
                count[l]++;
            }
        layers = new Transform[n];
        layerAvgFar = new float[n];
        for (int l = 0; l < n; l++)
            layerAvgFar[l] = count[l] > 0 ? sum[l] / count[l] : (l + 0.5f) / n;
        thresholds = new float[n - 1];                  // LayerOf용: 이웃 층 평균 깊이의 중간
        for (int q = 0; q < n - 1; q++)
            thresholds[q] = (layerAvgFar[q] + layerAvgFar[q + 1]) * 0.5f;

        for (int l = 0; l < n; l++)
        {
            var qv = new List<Vector3>(); var qu = new List<Vector2>();
            AddCorner(qv, qu, 0, 0); AddCorner(qv, qu, nx - 1, 0); AddCorner(qv, qu, 0, ny - 1); AddCorner(qv, qu, nx - 1, ny - 1);
            Material m = new Material(layerTemplate);
            owned.Add(m);                               // 텍스처는 에셋이라 지우지 않음
            if (m.HasProperty("_BaseMap")) m.SetTexture("_BaseMap", tex[l]);
            m.mainTexture = tex[l];
            if (m.HasProperty("_Cutoff")) m.SetFloat("_Cutoff", 0.5f);
            layers[l] = MakeCard("PopLayer_" + l, m, qv, qu, new List<int> { 0, 1, 2, 1, 3, 2 }, Color.white);
        }
        baked = true;
        return true;
    }

    // 바닥판: 원본 그림 전체를 어둡게. 앞 층이 빠져나간 자리에 구멍 대신 그림이 보이게 한다
    void MakeBaseCard(Material material)
    {
        var bv = new List<Vector3>(); var bu = new List<Vector2>();
        AddCorner(bv, bu, 0, 0); AddCorner(bv, bu, nx - 1, 0); AddCorner(bv, bu, 0, ny - 1); AddCorner(bv, bu, nx - 1, ny - 1);
        baseCard = MakeCard("PopBase", material, bv, bu, new List<int> { 0, 1, 2, 1, 3, 2 }, new Color(0.45f, 0.45f, 0.5f, 1f));
        ShowLayers(false);
    }

    // 층마다 "그림 색 + 그 층 모양의 투명 가장자리" 텍스처를 만든다.
    // 층 모양(칸 단위)을 한 번 흐리게 한 뒤 쌍선형으로 크게 늘려, 잘라 낸 윤곽이 계단이 아니라 매끈한 곡선이 되게 한다.
    // 그림 텍스처를 읽을 수 없으면 null (격자 칸 방식으로 대체)
    Texture2D[] BuildMaskedTextures(Material material, int[] label, int n)
    {
        Texture2D src = (material.HasProperty("_BaseMap") ? material.GetTexture("_BaseMap") : material.mainTexture) as Texture2D;
        if (src == null || !src.isReadable)
        {
            Debug.LogWarning("그림 텍스처를 읽을 수 없어 층을 격자 칸 모양으로 만듭니다 (Read/Write 켜기 필요)");
            return null;
        }
        try
        {
            // 빠른 길: 그림 텍스처의 작은 사본(밉맵) 중 가로 1024 이하인 첫 단계를 통째로 읽는다
            // (픽셀을 하나씩 읽는 느린 길은 밉맵이 없거나 읽기에 실패할 때만)
            int texW, texH;
            Color32[] rgb = null;
            int mip = 0;
            while (mip < src.mipmapCount - 1 && (src.width >> mip) > 1024)
                mip++;
            try
            {
                if ((src.width >> mip) <= 1024)
                    rgb = src.GetPixels32(mip);
            }
            catch (System.Exception) { rgb = null; }
            if (rgb != null)
            {
                texW = Mathf.Max(1, src.width >> mip);
                texH = Mathf.Max(1, src.height >> mip);
            }
            else
            {
                texW = 768;
                texH = Mathf.Max(2, Mathf.RoundToInt(texW * lcy / (float)lcx));
                rgb = new Color32[texW * texH];
                for (int y = 0; y < texH; y++)
                    for (int x = 0; x < texW; x++)
                        rgb[y * texW + x] = src.GetPixelBilinear((x + 0.5f) / texW, (y + 0.5f) / texH);
            }

            Texture2D[] result = new Texture2D[n];
            float[] member = new float[lcx * lcy];
            Color32[] px = new Color32[texW * texH];
            for (int l = 0; l < n; l++)
            {
                // 자기 층 + 더 먼 칸 중 이 층과 맞닿은 칸(한 칸 넓힘, 경계 틈 방지)
                for (int j = 0; j < lcy; j++)
                    for (int i = 0; i < lcx; i++)
                    {
                        int c = j * lcx + i;
                        member[c] = label[c] == l || (label[c] > l && HasNeighborLabel(label, i, j, l)) ? 1f : 0f;
                    }
                float[] soft = BoxBlur(member, lcx, lcy);
                for (int y = 0; y < texH; y++)
                {
                    float vImg = 1f - (y + 0.5f) / texH;          // 텍스처 0행은 그림 아래쪽
                    float gy = vImg * lcy - 0.5f;
                    for (int x = 0; x < texW; x++)
                    {
                        float gx = (x + 0.5f) / texW * lcx - 0.5f;
                        float a = Bilinear(soft, lcx, lcy, gx, gy);
                        a = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.3f, 0.7f, a));
                        Color32 c = rgb[y * texW + x];
                        c.a = (byte)(a * 255f);
                        px[y * texW + x] = c;
                    }
                }
                Texture2D t = new Texture2D(texW, texH, TextureFormat.RGBA32, true);
                owned.Add(t);
                t.wrapMode = TextureWrapMode.Clamp;
                t.SetPixels32(px);
                t.Apply(true, true);    // 밉맵 생성 후 CPU 사본은 버려 메모리 절약
                result[l] = t;
            }
            return result;
        }
        catch (System.Exception e)
        {
            Debug.LogWarning("층 텍스처 생성 실패, 격자 칸 모양으로 대체: " + e.Message);
            return null;
        }
    }

    static float Bilinear(float[] g, int w, int h, float x, float y)
    {
        x = Mathf.Clamp(x, 0f, w - 1f); y = Mathf.Clamp(y, 0f, h - 1f);
        int x0 = (int)x, y0 = (int)y;
        int x1 = Mathf.Min(x0 + 1, w - 1), y1 = Mathf.Min(y0 + 1, h - 1);
        float fx = x - x0, fy = y - y0;
        float top = Mathf.Lerp(g[y0 * w + x0], g[y0 * w + x1], fx);
        float bottom = Mathf.Lerp(g[y1 * w + x0], g[y1 * w + x1], fx);
        return Mathf.Lerp(top, bottom, fy);
    }

    void AddCellCorner(List<Vector3> v, List<Vector2> uv, int i, int j)
    {
        float u = i / (float)lcx;
        float vv = j / (float)lcy;
        v.Add(new Vector3(u - 0.5f, 0f, 0.5f - vv));
        uv.Add(new Vector2(u, 1f - vv));
    }

    static float[] BoxBlur(float[] src, int w, int h)
    {
        float[] dst = new float[src.Length];
        for (int j = 0; j < h; j++)
        {
            for (int i = 0; i < w; i++)
            {
                float s = 0f; int c = 0;
                for (int dj = -1; dj <= 1; dj++)
                    for (int di = -1; di <= 1; di++)
                    {
                        int x = i + di, y = j + dj;
                        if (x < 0 || y < 0 || x >= w || y >= h) continue;
                        s += src[y * w + x]; c++;
                    }
                dst[j * w + i] = s / c;
            }
        }
        return dst;
    }

    // 3x3 이웃에서 가장 많은 층으로 맞춘다 (외톨이 칸 제거)
    static int[] MajorityFilter(int[] src, int w, int h, int n)
    {
        int[] dst = new int[src.Length];
        int[] votes = new int[n];
        for (int j = 0; j < h; j++)
        {
            for (int i = 0; i < w; i++)
            {
                System.Array.Clear(votes, 0, n);
                for (int dj = -1; dj <= 1; dj++)
                    for (int di = -1; di <= 1; di++)
                    {
                        int x = i + di, y = j + dj;
                        if (x < 0 || y < 0 || x >= w || y >= h) continue;
                        votes[src[y * w + x]]++;
                    }
                int best = src[j * w + i];
                for (int l = 0; l < n; l++)
                    if (votes[l] > votes[best])
                        best = l;
                dst[j * w + i] = best;
            }
        }
        return dst;
    }

    bool HasNeighborLabel(int[] label, int i, int j, int l)
    {
        for (int dj = -1; dj <= 1; dj++)
            for (int di = -1; di <= 1; di++)
            {
                int x = i + di, y = j + dj;
                if (x < 0 || y < 0 || x >= lcx || y >= lcy) continue;
                if (label[y * lcx + x] == l) return true;
            }
        return false;
    }

    void AddCorner(List<Vector3> v, List<Vector2> uv, int i, int j)
    {
        float u = i / (nx - 1f);
        float vv = j / (ny - 1f);
        v.Add(new Vector3(u - 0.5f, 0f, 0.5f - vv));
        uv.Add(new Vector2(u, 1f - vv));
    }

    Transform MakeCard(string name, Material material, List<Vector3> v, List<Vector2> uv, List<int> tri, Color tint)
    {
        GameObject go = new GameObject(name, typeof(MeshFilter), typeof(MeshRenderer));
        go.transform.SetParent(transform, false);
        Mesh m = new Mesh();
        owned.Add(m);
        m.name = name;
        if (v.Count > 65000)
            m.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
        m.SetVertices(v);
        m.SetUVs(0, uv);
        m.SetTriangles(tri, 0);
        m.RecalculateBounds();
        go.GetComponent<MeshFilter>().sharedMesh = m;
        MeshRenderer r = go.GetComponent<MeshRenderer>();
        r.sharedMaterial = material;
        r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        r.receiveShadows = false;
        if (tint != Color.white)
        {
            var block = new MaterialPropertyBlock();
            block.SetColor("_BaseColor", tint);
            r.SetPropertyBlock(block);
        }
        return go.transform;
    }

    // 0 = 가장 가까운 층 ... N-1 = 가장 먼 층
    public int LayerOf(float farValue)
    {
        int l = 0;
        foreach (float th in thresholds)
            if (farValue > th)
                l++;
        return l;
    }

    // 펼쳤을 때 이 층이 방 쪽으로 나오는 비율: 가장 가까운 층 1 ... 가장 먼 층 0 (배경은 그림 면에 그대로)
    public float PulledFraction(int layer)
    {
        int n = layers.Length;
        return (n - 1 - layer) / (float)(n - 1);
    }

    // 층 사이를 잇는 연속 비율: 층별 평균 깊이를 꼭짓점으로 한 꺾은선 (틈 메우는 경사면용)
    float ContinuousFraction(float f)
    {
        int n = layers.Length;
        if (f <= layerAvgFar[0]) return PulledFraction(0);
        if (f >= layerAvgFar[n - 1]) return PulledFraction(n - 1);
        for (int l = 0; l < n - 1; l++)
        {
            if (f <= layerAvgFar[l + 1])
            {
                float t = Mathf.InverseLerp(layerAvgFar[l], layerAvgFar[l + 1], f);
                return Mathf.Lerp(PulledFraction(l), PulledFraction(l + 1), t);
            }
        }
        return 0f;
    }

    // 층마다 시작을 조금씩 늦춰, 가까운 층이 나중에 더 멀리 미끄러져 나오는 팝업 연출
    public float LayerProgress(int layer, float pull)
    {
        int n = layers.Length;
        float delay = (n - 1 - layer) / (float)n * 0.25f;   // 먼 층 먼저, 가까운 층은 최대 0.25 늦게
        return Mathf.SmoothStep(0f, 1f, Mathf.Clamp01((pull - delay) / (1f - 0.25f)));
    }

    // 숨겼던 그림을 다시 보일 때(모든 렌더러를 켠 뒤) 매끈한 면과 층 중 맞는 쪽만 남긴다
    public void ReapplyVisibility()
    {
        ShowLayers(layersShown);
        if (wireRenderer != null)
        {
            wireRenderer.enabled = revealTime >= 0f;
            scanLine.enabled = revealTime >= 0f && revealTime < scanDuration;
        }
    }

    // 펼친 상태: 층(또렷한 윤곽) + 그 뒤의 매끈한 경사면(틈 메움, 살짝 어둡게). 평소: 매끈한 입체 창문만
    void ShowLayers(bool show)
    {
        layersShown = show;
        meshRenderer.enabled = !(show && baked);        // 미리 만든 층: 가장 먼 층이 불투명 배경판이라 경사면이 필요 없음
        if (show && !baked)
        {
            if (fillerTint == null)
                fillerTint = new MaterialPropertyBlock();
            fillerTint.SetColor("_BaseColor", new Color(0.8f, 0.8f, 0.85f, 1f));
            meshRenderer.SetPropertyBlock(fillerTint);
        }
        else
        {
            meshRenderer.SetPropertyBlock(null);
        }
        foreach (Transform l in layers)
            l.GetComponent<MeshRenderer>().enabled = show;
        baseCard.GetComponent<MeshRenderer>().enabled = false;   // 경사면이 바닥판 역할을 대신함
    }

    // depthAmount: 가장 먼 곳이 그림 뒤로 들어가는 거리 (그림 너비의 몇 배인지)
    // eye: 정면에서 원래 그림과 똑같이 보이게 할 기준 시점 거리(m)
    // pull: 끌어내기 진행도 0~1, popScale: 펼친 크기 배율, popDepth: 펼쳤을 때 가장 가까운 층이 튀어나오는 거리(m)
    public void SetShape(float w, float h, float vSign, float dSign, float depthAmount, float eye,
                         float pull = 0f, float popScale = 1f, float popDepth = 0f, bool popPerspective = false)
    {
        lastW = w; lastH = h; lastVSign = vSign; lastDSign = dSign;
        bool wantLayers = pull > 0.001f;
        if (wantLayers != layersShown)
            ShowLayers(wantLayers);

        if (wantLayers)
        {
            float scale = Mathf.Lerp(1f, popScale, Mathf.SmoothStep(0f, 1f, pull));
            for (int l = 0; l < layers.Length; l++)
            {
                // 시작: 그 층의 평균 깊이(그림 뒤), 끝: 방 쪽으로 PulledFraction × popDepth
                float startDepth = layerAvgFar[l] * depthAmount * w;
                float spread = (eye + startDepth) / eye;
                float p = LayerProgress(l, pull);
                float y = Mathf.Lerp(dSign * startDepth, -dSign * PulledFraction(l) * popDepth, p);
                float s = Mathf.Lerp(spread, PaintingSoundWorld.PopLayerScale(PulledFraction(l), popScale, popDepth, eye, popPerspective), p);
                layers[l].localPosition = new Vector3(0f, y, 0f);
                layers[l].localScale = new Vector3(w * s, 1f, h * vSign * s);
            }
            if (baked)
                return;     // 경사면은 꺼져 있음 (평소 모양으로 돌아갈 때 아래에서 다시 계산)
            // 틈 메우는 경사면: 평소 입체 창문 → 아주 부드러운 깊이로 층들 바로 뒤에 펼침
            float bp = Mathf.SmoothStep(0f, 1f, pull);
            float eps = 0.03f * popDepth;      // 층보다 살짝 뒤 (층이 항상 앞에 보이게)
            for (int j = 0; j < ny; j++)
            {
                for (int i = 0; i < nx; i++)
                {
                    int k = j * nx + i;
                    float u = i / (nx - 1f);
                    float v = j / (ny - 1f);
                    Vector3 normal = PaintingSoundWorld.PaintingPoint(u, v, far[k] * depthAmount * w, w, h, vSign, dSign, eye);
                    float fr = ContinuousFraction(farSmooth[k]);
                    float fs = PaintingSoundWorld.PopLayerScale(fr, popScale, popDepth, eye, popPerspective);
                    Vector3 filler = new Vector3((u - 0.5f) * w * fs, -dSign * (fr * popDepth - eps), (0.5f - v) * h * vSign * fs);
                    vertices[k] = Vector3.Lerp(normal, filler, bp);
                }
            }
            mesh.vertices = vertices;
            mesh.RecalculateBounds();
            return;
        }

        for (int j = 0; j < ny; j++)
        {
            for (int i = 0; i < nx; i++)
            {
                int k = j * nx + i;
                float u = i / (nx - 1f);
                float v = j / (ny - 1f);
                // 소리원과 같은 식(PaintingPoint)으로 깊이만큼 그림 뒤로
                vertices[k] = PaintingSoundWorld.PaintingPoint(u, v, far[k] * depthAmount * w, w, h, vSign, dSign, eye);
            }
        }
        mesh.vertices = vertices;
        mesh.RecalculateBounds();
    }
}
