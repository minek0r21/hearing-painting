using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

// 오른쪽 위 "처음" 버튼 (결정사항 B7, 리셋 그릴링 R1~R5).
// 0.5초 길게 누르면 테두리가 차오르고 처음 상태로 리셋. 짧게 탭하면 사용법 안내.
// PaintingSoundWorld가 시작할 때 기존 Canvas 안에 코드로 만든다 (Unity에서 따로 할 작업 없음).
public class ResetButton : MonoBehaviour, IPointerDownHandler, IPointerUpHandler, IPointerExitHandler
{
    PaintingSoundWorld manager;
    Image fill;
    float holdTime = 0.5f;
    bool holding;
    float held;

    void Update()
    {
        if (!holding)
            return;
        held += Time.unscaledDeltaTime;
        fill.fillAmount = Mathf.Clamp01(held / holdTime);
        if (held >= holdTime)
        {
            holding = false;
            fill.fillAmount = 0f;
            manager.ResetAll();
        }
    }

    public void OnPointerDown(PointerEventData e)
    {
        holding = true;
        held = 0f;
    }

    public void OnPointerUp(PointerEventData e)
    {
        if (holding && held < holdTime)
            manager.ShowResetTip();
        holding = false;
        fill.fillAmount = 0f;
    }

    public void OnPointerExit(PointerEventData e)
    {
        holding = false;
        fill.fillAmount = 0f;
    }

    public static ResetButton Create(PaintingSoundWorld manager, Canvas canvas, TMP_FontAsset font, float holdTime)
    {
        var root = new GameObject("ResetButton", typeof(RectTransform));
        var rt = (RectTransform)root.transform;
        rt.SetParent(canvas.transform, false);
        rt.anchorMin = rt.anchorMax = rt.pivot = new Vector2(1f, 1f);
        rt.sizeDelta = new Vector2(130f, 130f);
        rt.anchoredPosition = new Vector2(-40f, -120f);   // 상태 표시줄 아래, 오른쪽 위 구석

        var bg = root.AddComponent<Image>();
        bg.sprite = MakeCircle(128, 0f);
        bg.color = new Color(0f, 0f, 0f, 0.45f);

        var fillGo = new GameObject("Fill", typeof(RectTransform));
        var frt = (RectTransform)fillGo.transform;
        frt.SetParent(rt, false);
        frt.anchorMin = Vector2.zero; frt.anchorMax = Vector2.one; frt.offsetMin = frt.offsetMax = Vector2.zero;
        var fill = fillGo.AddComponent<Image>();
        fill.sprite = MakeCircle(128, 0.82f);               // 테두리 고리
        fill.type = Image.Type.Filled;
        fill.fillMethod = Image.FillMethod.Radial360;
        fill.fillOrigin = (int)Image.Origin360.Top;
        fill.fillClockwise = true;
        fill.fillAmount = 0f;
        fill.raycastTarget = false;

        var labelGo = new GameObject("Label", typeof(RectTransform));
        var lrt = (RectTransform)labelGo.transform;
        lrt.SetParent(rt, false);
        lrt.anchorMin = Vector2.zero; lrt.anchorMax = Vector2.one; lrt.offsetMin = lrt.offsetMax = Vector2.zero;
        var label = labelGo.AddComponent<TextMeshProUGUI>();
        if (font != null)
            label.font = font;
        label.text = "처음";
        label.fontSize = 34f;
        label.alignment = TextAlignmentOptions.Center;
        label.color = Color.white;
        label.raycastTarget = false;

        var button = root.AddComponent<ResetButton>();
        button.manager = manager;
        button.fill = fill;
        button.holdTime = holdTime;
        return button;
    }

    // 원(inner = 0) 또는 고리(inner = 안쪽 반지름 비율) 스프라이트를 코드로 만든다
    static Sprite MakeCircle(int size, float inner)
    {
        var tex = new Texture2D(size, size, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp };
        float r = size * 0.5f;
        var px = new Color32[size * size];
        for (int y = 0; y < size; y++)
            for (int x = 0; x < size; x++)
            {
                float d = Mathf.Sqrt((x + 0.5f - r) * (x + 0.5f - r) + (y + 0.5f - r) * (y + 0.5f - r)) / r;
                float a = Mathf.Clamp01((1f - d) * r);                       // 바깥 가장자리 부드럽게
                if (inner > 0f) a *= Mathf.Clamp01((d - inner) * r);         // 안쪽 구멍
                px[y * size + x] = new Color32(255, 255, 255, (byte)(a * 255));
            }
        tex.SetPixels32(px);
        tex.Apply();
        return Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f));
    }
}
