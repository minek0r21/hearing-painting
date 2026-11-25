using UnityEngine;

// 인식한 그림의 테두리를 따라 그리는 빛나는 사각형.
// 처음 인식하면 2초 동안 깜빡이고, 그 뒤엔 은은하게 남는다.
[RequireComponent(typeof(LineRenderer))]
public class PaintingFrame : MonoBehaviour
{
    public Color color = new Color(0.6f, 0.9f, 1f, 1f);

    LineRenderer line;
    float width;
    float age = 10f;

    public void Init(Material material)
    {
        line = GetComponent<LineRenderer>();
        line.sharedMaterial = material;
        line.useWorldSpace = false;
        line.loop = true;
        line.positionCount = 4;
        line.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        line.receiveShadows = false;
    }

    // 추적 이미지의 로컬 좌표에서 그림은 x(가로)·z(세로) 평면에 놓인다
    public void SetSize(float w, float h)
    {
        float x = w * 0.5f;
        float z = h * 0.5f;
        line.SetPosition(0, new Vector3(-x, 0f, z));
        line.SetPosition(1, new Vector3(x, 0f, z));
        line.SetPosition(2, new Vector3(x, 0f, -z));
        line.SetPosition(3, new Vector3(-x, 0f, -z));
        width = w * 0.008f;
    }

    public void Pulse()
    {
        age = 0f;
    }

    void Update()
    {
        age += Time.deltaTime;
        bool pulsing = age < 2f;
        float glow = pulsing ? 0.6f + 0.4f * Mathf.Cos(age * Mathf.PI * 3f) : 0.35f;

        Color c = color;
        c.a = glow;
        line.startColor = c;
        line.endColor = c;
        line.widthMultiplier = width * (pulsing ? 1.5f : 1f);
    }
}
