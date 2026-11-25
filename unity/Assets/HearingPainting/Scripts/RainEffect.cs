using UnityEngine;

// 그림 속 비가 테두리를 넘어 방 안(폰 쪽)까지 내리는 효과. 빗소리가 클수록 굵어진다.
public class RainEffect : MonoBehaviour
{
    public float baseRate = 350f;       // 초당 빗방울 수
    public float frontReach = 0.6f;     // 그림 앞으로 얼마나 나오는지 (그림 너비 배)

    ParticleSystem rain;
    SoundSource rainSource;
    float open;

    public void Init(Material material, SoundSource rainSource)
    {
        this.rainSource = rainSource;

        rain = gameObject.AddComponent<ParticleSystem>();
        rain.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

        ParticleSystem.MainModule main = rain.main;
        main.loop = true;
        main.simulationSpace = ParticleSystemSimulationSpace.Local;    // 그림을 따라 움직임
        main.startColor = new Color(0.75f, 0.85f, 1f, 0.45f);
        main.maxParticles = 1500;

        ParticleSystem.ShapeModule shape = rain.shape;
        shape.shapeType = ParticleSystemShapeType.Box;

        ParticleSystemRenderer particleRenderer = GetComponent<ParticleSystemRenderer>();
        particleRenderer.sharedMaterial = material;
        particleRenderer.renderMode = ParticleSystemRenderMode.Stretch;   // 떨어지는 방향으로 늘린 빗줄기
        particleRenderer.lengthScale = 3f;
        particleRenderer.velocityScale = 0.02f;
        particleRenderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        particleRenderer.receiveShadows = false;

        rain.Play();
    }

    // 그림 윗변에서 아래로 떨어지게 둔다. 뒤로는 그림 깊이만큼, 앞으로는 방 안까지
    public void SetShape(float w, float h, float vSign, float dSign, float depthAmount, float openAmount)
    {
        open = openAmount;
        float back = Mathf.Max(depthAmount, 0.1f) * w;
        float front = frontReach * w;

        // 이 오브젝트의 +z가 그림 아래쪽, +y가 그림 법선이 되도록 돌린다 (파티클은 +z로 나감)
        transform.localRotation = Quaternion.LookRotation(new Vector3(0f, 0f, -vSign), Vector3.up);
        transform.localPosition = new Vector3(0f, dSign * (back - front) * 0.5f, vSign * h * 0.5f);

        ParticleSystem.ShapeModule shape = rain.shape;
        shape.scale = new Vector3(w, back + front, 0.001f);

        float speed = h * 2.5f;
        ParticleSystem.MainModule main = rain.main;
        main.startSpeed = speed;
        main.startLifetime = h / speed;     // 그림 높이만큼 떨어지고 사라짐
        main.startSize = w * 0.004f;
    }

    void Update()
    {
        float level = rainSource != null ? rainSource.Level : 0.5f;
        ParticleSystem.EmissionModule emission = rain.emission;
        emission.rateOverTime = baseRate * open * (0.5f + level);
    }
}
