using UnityEditor;
using UnityEngine;

// 파이프라인이 만든 팝업 층 그림(Resources/HearingPainting/.../layers/layerN.png)의 가져오기 설정을 자동으로 맞춘다.
// 가장자리 늘림(Clamp): 층 가장자리에 반대편 색이 번지지 않게. 알파 = 투명: 층 모양대로 오려 냄.
public class LayerTextureImporter : AssetPostprocessor
{
    void OnPreprocessTexture()
    {
        string p = assetPath.Replace('\\', '/');
        if (!p.Contains("/Resources/HearingPainting/") || !p.Contains("/layers/layer") || !p.EndsWith(".png"))
            return;
        var ti = (TextureImporter)assetImporter;
        ti.textureType = TextureImporterType.Default;
        ti.sRGBTexture = true;
        ti.alphaSource = TextureImporterAlphaSource.FromInput;
        ti.alphaIsTransparency = true;
        ti.wrapMode = TextureWrapMode.Clamp;
        ti.mipmapEnabled = true;
        ti.maxTextureSize = 1024;
        ti.isReadable = false;
    }
}
