using System.Collections.Generic;
using UnityEngine;

// 앱에 들어갈 그림 프리팹 목록 (U3). 등록 메뉴(PaintingRegistrar)가 자동으로 채운다.
// PaintingSoundWorld의 Catalog 칸에 넣으면 Painting Prefabs 배열 대신 이 목록을 쓴다.
[CreateAssetMenu(menuName = "Hearing Painting/Painting Catalog", fileName = "PaintingCatalog")]
public class PaintingCatalog : ScriptableObject
{
    [Tooltip("그림마다 프리팹 하나. 등록 메뉴가 자동으로 추가함")]
    public List<PaintingWorld> paintings = new List<PaintingWorld>();
}
