using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;
using Debug = UnityEngine.Debug;

// 새 그림 만들기 창 (결정사항 6-3): 그림 선택 + 제목·작가·연도 → AI 파이프라인(pipeline.py) → 자동 등록
// 메뉴: Hearing Painting > 새 그림 만들기
// 여러 장을 줄 세우면 한 장씩 차례로 처리한다. 결과는 report.html로 듣고, 소리 하나만 다시 만들 수 있다.
public class PaintingMakerWindow : EditorWindow
{
    [Serializable]
    class Job
    {
        public string kind = "build";      // build | regen
        public string imagePath, title, artist, year, key, sourceId, sourceLabel;
        public string status = "대기";      // 대기 | 진행 중 | 완료 | 실패
        public string message = "";
    }

    [SerializeField] List<Job> jobs = new List<Job>();
    [SerializeField] List<string> logLines = new List<string>();
    Vector2 scroll, logScroll;
    bool showSettings;
    readonly Dictionary<string, Texture2D> thumbs = new Dictionary<string, Texture2D>();

    Process process;
    Job current;
    float stepProgress;
    string stepText = "";
    readonly ConcurrentQueue<string> incoming = new ConcurrentQueue<string>();

    // 11/26 청취 결과 Stable Audio 3 medium이 기본 (결정사항 6-2)
    static readonly string[] AudioModels = { "sa3m", "sa3s", "sao1" };
    static readonly string[] AudioNames = { "Stable Audio 3 medium (기본)", "Stable Audio 3 small-sfx (빠름)", "Stable Audio Open 1.0 (이전)" };

    static string LocalAiDir
    {
        get => EditorPrefs.GetString("HP.localAi", DefaultLocalAiDir());
        set => EditorPrefs.SetString("HP.localAi", value);
    }
    // 파이프라인 폴더: GitHub 저장소 구조(unity/ 옆의 pipeline/) 또는 작업 폴더 구조(03_제작/local_ai)
    static string DefaultLocalAiDir()
    {
        string repo = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "pipeline"));
        if (File.Exists(Path.Combine(repo, "pipeline.py")))
            return repo;
        return Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "03_제작", "local_ai"));
    }

    static string PythonPath
    {
        get => EditorPrefs.GetString("HP.python", Path.Combine(LocalAiDir, ".venv", "Scripts", "python.exe"));
        set => EditorPrefs.SetString("HP.python", value);
    }
    static int AudioIndex
    {
        get => EditorPrefs.GetInt("HP.audio", 0);
        set => EditorPrefs.SetInt("HP.audio", value);
    }

    [MenuItem("Hearing Painting/새 그림 만들기", priority = 10)]
    static void Open() => GetWindow<PaintingMakerWindow>("새 그림 만들기").minSize = new Vector2(460, 520);

    void OnEnable() => EditorApplication.update += Pump;
    void OnDisable() => EditorApplication.update -= Pump;

    // ---------------- 화면 ----------------
    void OnGUI()
    {
        bool running = process != null;
        scroll = EditorGUILayout.BeginScrollView(scroll);

        showSettings = EditorGUILayout.Foldout(showSettings, "설정", true);
        if (showSettings)
        {
            EditorGUI.indentLevel++;
            LocalAiDir = EditorGUILayout.TextField("local_ai 폴더", LocalAiDir);
            PythonPath = EditorGUILayout.TextField("Python", PythonPath);
            EditorGUI.indentLevel--;
            if (!File.Exists(PythonPath))
                EditorGUILayout.HelpBox("Python을 찾지 못함: " + PythonPath, MessageType.Error);
        }
        AudioIndex = EditorGUILayout.Popup("소리 생성 모델", AudioIndex, AudioNames);

        EditorGUILayout.Space();
        EditorGUILayout.LabelField("만들 그림", EditorStyles.boldLabel);
        using (new EditorGUI.DisabledScope(running))
            if (GUILayout.Button("그림 추가… (jpg, png)", GUILayout.Height(26)))
                AddImage();

        Job remove = null;
        foreach (Job j in jobs)
        {
            if (j.kind != "build") continue;
            using (new EditorGUILayout.VerticalScope("box"))
            {
                using (new EditorGUILayout.HorizontalScope())
                {
                    Texture2D t = Thumb(j.imagePath);
                    if (t != null)
                        GUILayout.Label(t, GUILayout.Width(90), GUILayout.Height(90 * t.height / Mathf.Max(1, t.width)));
                    using (new EditorGUILayout.VerticalScope())
                    {
                        using (new EditorGUI.DisabledScope(j.status != "대기" || running))
                        {
                            j.title = EditorGUILayout.TextField("제목", j.title);
                            j.artist = EditorGUILayout.TextField("작가", j.artist);
                            j.year = EditorGUILayout.TextField("연도", j.year);
                        }
                        if (j.status == "대기")
                            EditorGUILayout.LabelField("제목과 화가를 정확히 적으면 소리 설계가 더 정확해집니다", EditorStyles.miniLabel);
                        EditorGUILayout.LabelField($"{j.key} · {j.status}" + (string.IsNullOrEmpty(j.message) ? "" : " — " + j.message), EditorStyles.miniLabel);
                    }
                }
                using (new EditorGUILayout.HorizontalScope())
                {
                    if (j.status == "완료" && GUILayout.Button("결과 보기 (소리 듣기)"))
                        OpenReport(j.key);
                    if (j.status != "진행 중" && !running && GUILayout.Button("목록에서 빼기", GUILayout.Width(100)))
                        remove = j;
                }
                if (j.status == "완료")
                    DrawRegen(j.key, running);
            }
        }
        if (remove != null) jobs.Remove(remove);

        EditorGUILayout.Space();
        int pending = jobs.FindAll(x => x.status == "대기").Count;
        using (new EditorGUILayout.HorizontalScope())
        {
            using (new EditorGUI.DisabledScope(running || pending == 0 || !File.Exists(PythonPath)))
                if (GUILayout.Button($"모두 만들기 ({pending}장)", GUILayout.Height(32)))
                    StartNext();
            using (new EditorGUI.DisabledScope(!running))
                if (GUILayout.Button("멈추기", GUILayout.Width(80), GUILayout.Height(32)))
                    Stop();
        }
        if (running)
        {
            Rect r = GUILayoutUtility.GetRect(18, 20, GUILayout.ExpandWidth(true));
            EditorGUI.ProgressBar(r, stepProgress, $"{current.key} {current.title}{current.sourceLabel}: {stepText}");
            EditorGUILayout.HelpBox("그림 한 장에 약 5~10분 걸립니다. 진행 중에는 스크립트를 고치지 마세요(다시 컴파일되면 진행 표시가 끊김).", MessageType.Info);
        }

        EditorGUILayout.Space();
        if (GUILayout.Button("등록만 다시 하기 (Resources 훑기)"))
        {
            string result = string.Join("\n", PaintingRegistrar.RegisterAll());
            EditorUtility.DisplayDialog("등록", result.Length > 0 ? result : "새로 등록할 것이 없습니다.", "확인");
        }

        EditorGUILayout.LabelField("진행 기록", EditorStyles.boldLabel);
        logScroll = EditorGUILayout.BeginScrollView(logScroll, GUILayout.Height(160));
        foreach (string line in logLines)
            EditorGUILayout.LabelField(line, EditorStyles.miniLabel);
        EditorGUILayout.EndScrollView();

        EditorGUILayout.EndScrollView();
    }

    void DrawRegen(string key, bool running)
    {
        string scenePath = Path.Combine(LocalAiDir, "out_" + key, "scene.json");
        if (!File.Exists(scenePath)) return;
        PaintingScene scene = JsonUtility.FromJson<PaintingScene>(File.ReadAllText(scenePath));
        if (scene?.sources == null) return;
        EditorGUILayout.LabelField("소리 하나 다시 만들기 (새 시드)", EditorStyles.miniBoldLabel);
        using (new EditorGUI.DisabledScope(running))
            foreach (SoundSourceData s in scene.sources)
                if (GUILayout.Button("↻ " + s.label, EditorStyles.miniButton))
                {
                    jobs.Add(new Job { kind = "regen", key = key, sourceId = s.id, sourceLabel = " · " + s.label, title = scene.title });
                    StartNext();
                }
    }

    void AddImage()
    {
        string path = EditorUtility.OpenFilePanelWithFilters("그림 선택", "", new[] { "그림", "jpg,jpeg,png" });
        if (string.IsNullOrEmpty(path)) return;
        // 파일 이름이 '제목_작가_연도'면 칸을 미리 채움
        string[] parts = Path.GetFileNameWithoutExtension(path).Split('_');
        jobs.Add(new Job
        {
            imagePath = path,
            title = parts[0],
            artist = parts.Length > 1 ? parts[1] : "",
            year = parts.Length > 2 ? parts[2] : "",
            key = NextKey(),
        });
    }

    // 내부 이름 p001, p002 … (Resources, out_ 폴더, 줄 선 작업과 겹치지 않게)
    string NextKey()
    {
        for (int n = 1; n < 1000; n++)
        {
            string k = $"p{n:000}";
            bool used = Directory.Exists(Path.Combine(Application.dataPath, "Resources", "HearingPainting", k))
                        || Directory.Exists(Path.Combine(LocalAiDir, "out_" + k))
                        || jobs.Exists(j => j.key == k);
            if (!used) return k;
        }
        return "p" + DateTime.Now.ToString("HHmmss");
    }

    Texture2D Thumb(string path)
    {
        if (string.IsNullOrEmpty(path) || !File.Exists(path)) return null;
        if (thumbs.TryGetValue(path, out var t) && t != null) return t;
        t = new Texture2D(2, 2);
        t.LoadImage(File.ReadAllBytes(path));
        thumbs[path] = t;
        return t;
    }

    void OpenReport(string key)
    {
        string report = Path.Combine(LocalAiDir, "out_" + key, "report.html");
        if (File.Exists(report)) Application.OpenURL("file:///" + report.Replace('\\', '/'));
        else Debug.LogWarning("report.html 없음: " + report);
    }

    // ---------------- 실행 ----------------
    void StartNext()
    {
        if (process != null) return;
        current = jobs.Find(j => j.status == "대기");
        if (current == null) { Repaint(); return; }
        current.status = "진행 중";
        stepProgress = 0; stepText = "시작";
        string q(string s) => "\"" + (s ?? "").Replace("\"", "'") + "\"";
        string args = current.kind == "regen"
            ? $"-X utf8 pipeline.py --key {current.key} --regen {current.sourceId} --to-unity"
            : $"-X utf8 pipeline.py {q(current.imagePath)} --key {current.key} --title {q(current.title)} --artist {q(current.artist)} --year {q(current.year)} --audio {AudioModels[AudioIndex]} --to-unity";
        var psi = new ProcessStartInfo(PythonPath, args)
        {
            WorkingDirectory = LocalAiDir,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
        psi.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";
        AddLog($"▶ {current.key} {current.title}{current.sourceLabel}");
        try
        {
            process = new Process { StartInfo = psi, EnableRaisingEvents = true };
            process.OutputDataReceived += (_, e) => { if (e.Data != null) incoming.Enqueue(e.Data); };
            process.ErrorDataReceived += (_, e) => { if (e.Data != null) incoming.Enqueue("[err] " + e.Data); };
            process.Exited += (_, __) => incoming.Enqueue("@@EXIT");
            process.Start();
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();
        }
        catch (Exception e)
        {
            current.status = "실패"; current.message = e.Message; process = null;
            AddLog("실행 실패: " + e.Message);
        }
    }

    void Stop()
    {
        try { if (process != null && !process.HasExited) process.Kill(); } catch { }
        if (current != null) { current.status = "실패"; current.message = "멈춤"; }
        process = null;
        AddLog("■ 멈춤");
    }

    // 에디터 매 프레임: 파이프라인 출력 줄을 읽어 진행 표시·기록 갱신
    void Pump()
    {
        bool changed = false;
        while (incoming.TryDequeue(out string line))
        {
            changed = true;
            if (line.StartsWith("@@STEP "))
            {
                // @@STEP 2/4 깊이 (auto)
                string[] p = line.Substring(7).Split(new[] { ' ' }, 2);
                string[] nm = p[0].Split('/');
                if (nm.Length == 2 && int.TryParse(nm[0], out int n) && int.TryParse(nm[1], out int m))
                    stepProgress = (n - 1f) / m;
                stepText = p.Length > 1 ? p[1] : "";
                AddLog(stepText);
            }
            else if (line.StartsWith("@@SUB "))
            {
                stepText = "소리 생성 " + line.Substring(6);
            }
            else if (line.StartsWith("@@DONE "))
            {
                if (current != null) current.message = "";
            }
            else if (line.StartsWith("@@ERROR "))
            {
                if (current != null) current.message = line.Substring(8);
                AddLog("오류: " + line.Substring(8));
            }
            else if (line == "@@EXIT")
            {
                Finish();
            }
            else if (!line.StartsWith("[err]") || line.Contains("Error") || line.Contains("Traceback"))
            {
                if (!line.StartsWith("[err]")) AddLog(line.Trim());
                else if (line.Contains("Error")) AddLog(line);
            }
        }
        if (changed) Repaint();
    }

    void Finish()
    {
        int code = -1;
        try { code = process.ExitCode; } catch { }
        process = null;
        if (current == null) return;
        if (code == 0)
        {
            AssetDatabase.Refresh();
            if (current.kind == "build")
            {
                bool ok = PaintingRegistrar.Register(current.key, out string msg);
                current.status = ok ? "완료" : "실패";
                current.message = ok ? "등록됨: " + msg + QualityText(current.key) : "등록 실패: " + msg;
                AddLog((ok ? "✔ 등록 " : "✖ 등록 실패 ") + current.key + " — " + current.message);
            }
            else
            {
                current.status = "완료";
                AddLog("✔ 다시 만듦: " + current.sourceLabel.Trim(' ', '·'));
            }
        }
        else
        {
            current.status = "실패";
            if (string.IsNullOrEmpty(current.message)) current.message = "종료 코드 " + code;
            AddLog("✖ 실패: " + current.key + " " + current.message);
        }
        jobs.RemoveAll(j => j.kind == "regen" && j.status != "대기" && j.status != "진행 중");
        current = null;
        StartNext();      // 줄 선 다음 그림
    }

    // scene.json의 quality (Gemini 답지 기준 채점, 결정사항 6-3 N1) → 한 줄
    [Serializable] class Score { public float required_found = -1; public string required; public float invented; public string invented_n; }
    [Serializable] class QualitySet { public Score gemini; public Score claude; }
    [Serializable] class QualityRoot { public QualitySet quality; public int arcore_score = -1; public string[] name_warnings; }

    string QualityText(string key)
    {
        string path = Path.Combine(LocalAiDir, "out_" + key, "scene.json");
        if (!File.Exists(path)) return "";
        QualityRoot q = JsonUtility.FromJson<QualityRoot>(File.ReadAllText(path));
        string arcore = q == null || q.arcore_score < 0 ? "" :
            $" | ARCore 인식 {q.arcore_score}점" + (q.arcore_score < 75 ? " ⚠ 75점 미만: 인식 불안정 가능" : "");
        if (q?.name_warnings != null && q.name_warnings.Length > 0)
            arcore += " | ⚠ 이름 확인 필요(한자 섞임): " + string.Join(", ", q.name_warnings);
        Score s = q?.quality?.claude != null && q.quality.claude.required_found >= 0 ? q.quality.claude : q?.quality?.gemini;
        if (s == null || s.required_found < 0 || string.IsNullOrEmpty(s.required)) return " | 품질: 답지 없음" + arcore;
        bool warn = s.required_found < 0.7f || s.invented > 0.15f;
        return $" | 품질: 필수 {s.required}, 지어냄 {s.invented_n}" + (warn ? " ⚠ 확인 필요 (결과 보기)" : "") + arcore;
    }

    void AddLog(string line)
    {
        if (string.IsNullOrEmpty(line)) return;
        logLines.Add(DateTime.Now.ToString("HH:mm:ss ") + line);
        if (logLines.Count > 300) logLines.RemoveRange(0, logLines.Count - 300);
        logScroll.y = float.MaxValue;
    }
}
