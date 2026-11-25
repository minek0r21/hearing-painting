using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.XR.ARSubsystems;
using UnityEngine;
using UnityEngine.XR.ARSubsystems;

// 소리 묶음(Resources/HearingPainting/<key>/) → 앱 등록 (결정사항 6-3, U1~U6)
//   1 검사: scene.json 형식, 소리 파일, depth.bytes, 참조 이미지(ReferenceImages/<key>.jpg)
//   2 참조 이미지: 텍스처 설정(hunters와 같게, 읽기 허용) + PaintingLibrary에 이름 = key로 추가
//   3 재질: M_Painting_hunters 복사 → M_Painting_<key> (그림 텍스처)
//   4 프리팹: Painting_Base(없으면 hunters 프리팹을 복사해 만듦)의 변형 → Painting_<key>
//   5 카탈로그: PaintingCatalog에 추가 (처음 만들 때 기존 그림 프리팹도 함께 넣음)
// 이미 등록된 그림은 프리팹을 유지하고 재질 텍스처와 비 효과 설정만 다시 맞춘다 (소리 묶음 파일은 경로로 읽으므로 자동 반영).
public static class PaintingRegistrar
{
    const string Root = "Assets/HearingPainting";
    const string ResRoot = "Assets/Resources/HearingPainting";
    const string LibraryPath = Root + "/PaintingLibrary.asset";
    const string CatalogPath = Root + "/PaintingCatalog.asset";
    const string PrefabDir = Root + "/Prefabs";
    const string BasePrefabPath = PrefabDir + "/Painting_Base.prefab";
    const string BaseSourcePath = PrefabDir + "/Painting_hunters.prefab";
    const string MaterialSourcePath = Root + "/Materials/M_Painting_hunters.mat";
    const string TextureSourcePath = Root + "/ReferenceImages/hunters.jpg";

    [MenuItem("Hearing Painting/새 그림 등록 (Resources 훑기)", priority = 20)]
    static void RegisterAllMenu()
    {
        List<string> lines = RegisterAll();
        string text = lines.Count == 0 ? "새로 등록할 소리 묶음이 없습니다." : string.Join("\n", lines);
        Debug.Log("[등록]\n" + text);
        EditorUtility.DisplayDialog("새 그림 등록", text, "확인");
    }

    // Resources/HearingPainting 아래에서 scene.json이 있는 폴더를 모두 훑어 등록. 결과 한 줄씩 반환
    public static List<string> RegisterAll()
    {
        AssetDatabase.Refresh();
        var lines = new List<string>();
        string full = Path.GetFullPath(ResRoot);
        if (!Directory.Exists(full))
            return lines;
        foreach (string dir in Directory.GetDirectories(full))
        {
            string key = Path.GetFileName(dir);
            if (!File.Exists(Path.Combine(dir, "scene.json")))
                continue;
            bool known = FindPrefab(key) != null;
            bool ok = Register(key, out string msg);
            if (!known || !ok)
                lines.Add((ok ? "등록: " : "건너뜀: ") + key + " — " + msg);
        }
        return lines;
    }

    // 그림 하나 등록. 실패하면 false와 이유
    public static bool Register(string key, out string message)
    {
        // ---------- 1 검사 ----------
        string sceneAssetPath = $"{ResRoot}/{key}/scene.json";
        string refPath = $"{Root}/ReferenceImages/{key}.jpg";
        if (!File.Exists(Path.GetFullPath(sceneAssetPath))) { message = "scene.json 없음"; return false; }
        PaintingScene scene;
        try { scene = JsonUtility.FromJson<PaintingScene>(File.ReadAllText(Path.GetFullPath(sceneAssetPath))); }
        catch (System.Exception e) { message = "scene.json 형식 오류: " + e.Message; return false; }
        if (scene == null || scene.sources == null || scene.sources.Length == 0) { message = "scene.json에 소리원이 없음"; return false; }
        var missing = new List<string>();
        bool hasRain = false;
        foreach (SoundSourceData s in scene.sources)
        {
            if (!File.Exists(Path.GetFullPath($"{ResRoot}/{key}/sounds/{s.file}.wav")))
                missing.Add(s.file);
            hasRain |= s.id == "rain";
        }
        if (missing.Count > 0) { message = "소리 파일 없음: " + string.Join(", ", missing); return false; }
        if (!File.Exists(Path.GetFullPath($"{ResRoot}/{key}/depth.bytes"))) { message = "depth.bytes 없음"; return false; }
        if (!File.Exists(Path.GetFullPath(refPath))) { message = "참조 이미지 없음: " + refPath; return false; }

        AssetDatabase.ImportAsset(refPath, ImportAssetOptions.ForceSynchronousImport);

        // ---------- 2 참조 이미지 ----------
        var srcImporter = AssetImporter.GetAtPath(TextureSourcePath) as TextureImporter;
        var dstImporter = AssetImporter.GetAtPath(refPath) as TextureImporter;
        if (dstImporter == null) { message = "참조 이미지를 텍스처로 읽지 못함"; return false; }
        if (srcImporter != null)
        {
            var settings = new TextureImporterSettings();
            srcImporter.ReadTextureSettings(settings);
            dstImporter.SetTextureSettings(settings);
            dstImporter.maxTextureSize = srcImporter.maxTextureSize;
            dstImporter.textureCompression = srcImporter.textureCompression;
        }
        dstImporter.isReadable = true;        // 그림 속 공간 꺼내기가 그림 픽셀을 읽음
        dstImporter.mipmapEnabled = true;
        dstImporter.SaveAndReimport();
        var texture = AssetDatabase.LoadAssetAtPath<Texture2D>(refPath);

        var library = AssetDatabase.LoadAssetAtPath<XRReferenceImageLibrary>(LibraryPath);
        if (library == null) { message = "PaintingLibrary 없음: " + LibraryPath; return false; }
        int index = -1;
        for (int i = 0; i < library.count; i++)
            if (library[i].name == key) index = i;
        if (index < 0)
        {
            library.Add();
            index = library.count - 1;
        }
        library.SetName(index, key);
        library.SetTexture(index, texture, false);   // 기존 항목과 같게: 텍스처는 라이브러리에 직접 담지 않음
        library.SetSpecifySize(index, false);
        EditorUtility.SetDirty(library);

        // ---------- 3 재질 ----------
        string matPath = $"{Root}/Materials/M_Painting_{key}.mat";
        var mat = AssetDatabase.LoadAssetAtPath<Material>(matPath);
        if (mat == null)
        {
            var srcMat = AssetDatabase.LoadAssetAtPath<Material>(MaterialSourcePath);
            if (srcMat == null) { message = "원본 재질 없음: " + MaterialSourcePath; return false; }
            mat = new Material(srcMat);
            AssetDatabase.CreateAsset(mat, matPath);
        }
        mat.SetTexture("_BaseMap", texture);
        mat.mainTexture = texture;
        EditorUtility.SetDirty(mat);

        // ---------- 4 프리팹 (Base의 변형) ----------
        Vector2 preview = new Vector2(0.5f, texture != null ? 0.5f * texture.height / Mathf.Max(1, texture.width) : 0.38f);
        PaintingWorld prefab = FindPrefab(key);
        string prefabPath = $"{PrefabDir}/Painting_{key}.prefab";
        if (prefab == null)
        {
            GameObject baseGo = EnsureBasePrefab();
            if (baseGo == null) { message = "Base 프리팹을 만들지 못함 (" + BaseSourcePath + " 확인)"; return false; }
            var instance = (GameObject)PrefabUtility.InstantiatePrefab(baseGo);
            Apply(instance.GetComponent<PaintingWorld>(), key, mat, preview, hasRain);
            instance.name = "Painting_" + key;
            GameObject saved = PrefabUtility.SaveAsPrefabAsset(instance, prefabPath);   // 프리팹 인스턴스를 저장 → 변형(Variant)으로 저장됨
            Object.DestroyImmediate(instance);
            prefab = saved != null ? saved.GetComponent<PaintingWorld>() : null;
            if (prefab == null) { message = "프리팹 저장 실패: " + prefabPath; return false; }
        }
        else
        {
            Apply(prefab, key, mat, preview, hasRain);
            EditorUtility.SetDirty(prefab);
            PrefabUtility.SavePrefabAsset(prefab.gameObject);
        }

        // ---------- 5 카탈로그 ----------
        PaintingCatalog catalog = EnsureCatalog();
        if (!catalog.paintings.Contains(prefab))
            catalog.paintings.Add(prefab);
        EditorUtility.SetDirty(catalog);
        AssetDatabase.SaveAssets();

        message = $"{scene.title} ({scene.sources.Length}개 소리원{(hasRain ? ", 비 효과" : "")})";
        return true;
    }

    static void Apply(PaintingWorld w, string key, Material mat, Vector2 preview, bool hasRain)
    {
        w.imageName = key;
        w.sceneJsonPath = $"HearingPainting/{key}/scene";
        w.soundFolder = $"HearingPainting/{key}/sounds";
        w.depthMapPath = $"HearingPainting/{key}/depth";
        w.paintingMaterial = mat;
        w.previewSize = preview;
        w.showRain = hasRain;
        w.rainSourceId = "rain";
    }

    // 이미 있는 그림 프리팹 찾기 (imageName 기준)
    public static PaintingWorld FindPrefab(string key)
    {
        foreach (string guid in AssetDatabase.FindAssets("t:Prefab", new[] { PrefabDir }))
        {
            string path = AssetDatabase.GUIDToAssetPath(guid);
            if (path == BasePrefabPath) continue;
            var w = AssetDatabase.LoadAssetAtPath<PaintingWorld>(path);
            if (w != null && w.imageName == key) return w;
        }
        return null;
    }

    static GameObject EnsureBasePrefab()
    {
        var baseGo = AssetDatabase.LoadAssetAtPath<GameObject>(BasePrefabPath);
        if (baseGo != null) return baseGo;
        if (!AssetDatabase.CopyAsset(BaseSourcePath, BasePrefabPath)) return null;
        AssetDatabase.ImportAsset(BasePrefabPath);
        return AssetDatabase.LoadAssetAtPath<GameObject>(BasePrefabPath);
    }

    public static PaintingCatalog EnsureCatalog()
    {
        var catalog = AssetDatabase.LoadAssetAtPath<PaintingCatalog>(CatalogPath);
        if (catalog != null) return catalog;
        catalog = ScriptableObject.CreateInstance<PaintingCatalog>();
        // 처음 만들 때: 지금 있는 그림 프리팹(rainy_day, hunters 등)을 먼저 넣어 기존 동작을 유지
        foreach (string guid in AssetDatabase.FindAssets("t:Prefab", new[] { PrefabDir }))
        {
            string path = AssetDatabase.GUIDToAssetPath(guid);
            if (path == BasePrefabPath) continue;
            var w = AssetDatabase.LoadAssetAtPath<PaintingWorld>(path);
            if (w != null) catalog.paintings.Add(w);
        }
        AssetDatabase.CreateAsset(catalog, CatalogPath);
        AssetDatabase.SaveAssets();
        return catalog;
    }

    [MenuItem("Hearing Painting/그림 카탈로그 만들기·선택", priority = 21)]
    static void SelectCatalog()
    {
        Selection.activeObject = EnsureCatalog();
        EditorGUIUtility.PingObject(Selection.activeObject);
    }
}
