using System;

// scene.json 구조. Colab 노트북이 만드는 JSON과 필드 이름이 같아야 JsonUtility가 읽는다.
[Serializable]
public class PaintingScene
{
    public string title;
    public string artist;
    public string year;
    public SoundSourceData[] sources;
}

[Serializable]
public class SoundSourceData
{
    public string id;
    public string label;        // 화면에 보일 이름 (예: 마차)
    public string type;         // nature, people, vehicle, music → 음파 링 색
    public float u;             // 그림 가로 위치 0(왼쪽) ~ 1(오른쪽)
    public float v;             // 그림 세로 위치 0(위) ~ 1(아래)
    public float depth;         // 0(그림 표면) ~ 1(가장 깊은 곳). AI 깊이 추정 결과
    public string file;         // Resources/HearingPainting/sounds 안의 파일 이름 (확장자 없이)
    public float volume;        // 0 ~ 1
    public string description;  // 탭했을 때 보일 한 줄 설명
}
