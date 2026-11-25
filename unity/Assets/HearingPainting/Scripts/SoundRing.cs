using UnityEngine;

// 소리원에서 퍼져 나가는 음파 링 하나. 커지면서 옅어지다가 스스로 사라진다.
[RequireComponent(typeof(LineRenderer))]
public class SoundRing : MonoBehaviour
{
    const int Segments = 48;

    LineRenderer line;
    readonly Vector3[] points = new Vector3[Segments];
    Color color;
    float startRadius;
    float endRadius;
    float width;
    float life;
    float age;

    public void Init(Material material, Color color, float startRadius, float endRadius, float width, float life)
    {
        line = GetComponent<LineRenderer>();
        line.sharedMaterial = material;
        line.useWorldSpace = true;
        line.loop = true;
        line.positionCount = Segments;
        line.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        line.receiveShadows = false;

        this.color = color;
        this.startRadius = startRadius;
        this.endRadius = endRadius;
        this.width = width;
        this.life = life;
        Apply(0f);
    }

    void Update()
    {
        age += Time.deltaTime;
        float t = age / life;
        if (t >= 1f)
        {
            Destroy(gameObject);
            return;
        }
        Apply(t);
    }

    void Apply(float t)
    {
        // 처음엔 빠르게 퍼지고 끝으로 갈수록 느려짐
        float eased = 1f - (1f - t) * (1f - t);
        float radius = Mathf.Lerp(startRadius, endRadius, eased);

        // 카메라를 정면으로 보는 원: 카메라의 오른쪽·위쪽 축으로 원을 그린다
        Camera cam = Camera.main;
        Vector3 right = cam != null ? cam.transform.right : Vector3.right;
        Vector3 up = cam != null ? cam.transform.up : Vector3.up;
        Vector3 center = transform.position;
        for (int i = 0; i < Segments; i++)
        {
            float a = i * Mathf.PI * 2f / Segments;
            points[i] = center + (right * Mathf.Cos(a) + up * Mathf.Sin(a)) * radius;
        }
        line.SetPositions(points);

        line.widthMultiplier = width * (1f - 0.5f * t);
        Color c = color;
        c.a = color.a * (1f - t);
        line.startColor = c;
        line.endColor = c;
    }
}
