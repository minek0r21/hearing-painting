using UnityEngine;

// Colab에서 만든 깊이 지도(depth.bytes)를 읽는다. 값은 0(가까움) ~ 1(멂).
// 파일 구조: 가로·세로(각 2바이트) + 가로×세로 바이트, 그림 위쪽 줄부터.
public class DepthMap
{
    public int Width { get; private set; }
    public int Height { get; private set; }

    float[] values;

    public static DepthMap Load(string resourcePath)
    {
        TextAsset asset = Resources.Load<TextAsset>(resourcePath);
        if (asset == null)
            return null;

        byte[] bytes = asset.bytes;
        DepthMap map = new DepthMap();
        map.Width = bytes[0] | (bytes[1] << 8);
        map.Height = bytes[2] | (bytes[3] << 8);
        if (bytes.Length < 4 + map.Width * map.Height)
            return null;

        map.values = new float[map.Width * map.Height];
        for (int i = 0; i < map.values.Length; i++)
            map.values[i] = bytes[4 + i] / 255f;
        return map;
    }

    // u: 왼쪽 0 ~ 오른쪽 1, v: 위 0 ~ 아래 1. 주변 네 칸을 섞어서(쌍선형 보간) 읽는다
    public float Sample(float u, float v)
    {
        float x = Mathf.Clamp01(u) * (Width - 1);
        float y = Mathf.Clamp01(v) * (Height - 1);
        int x0 = (int)x;
        int y0 = (int)y;
        int x1 = Mathf.Min(x0 + 1, Width - 1);
        int y1 = Mathf.Min(y0 + 1, Height - 1);
        float fx = x - x0;
        float fy = y - y0;

        float top = Mathf.Lerp(values[y0 * Width + x0], values[y0 * Width + x1], fx);
        float bottom = Mathf.Lerp(values[y1 * Width + x0], values[y1 * Width + x1], fx);
        return Mathf.Lerp(top, bottom, fy);
    }
}
