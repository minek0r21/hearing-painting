# 그림 꺼내기 층 만들기 (11/26, 보고서 "그림 꺼내기 층 틈 메우기" 추천안)
# 깊이 → 면적이 비슷한 층 n개 → 층마다 앞 층에 가려진 곳을 LaMa로 채운 RGBA PNG + 층 지도(layers.bytes).
# 앱은 층을 펼칠 때 이 PNG를 그대로 쓴다. 층 0이 가장 가깝고 n-1이 가장 멀다(불투명 배경판).
#
# 단독 실행 (기존 그림에 층만 추가):
#   python layers.py <그림 파일> <출력 폴더> [--depth auto|da3|da2s]
import io, os, sys, time
import numpy as np
import cv2
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
LAMA_PATH = os.path.join(HERE, 'models', 'lama', 'big-lama.pt')
LAMA_URL = 'https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt'

N_LAYERS = 4          # Unity popLayers와 같아야 함
WORK_SIDE = 1024      # 층 PNG 긴 변 (Unity 층 텍스처도 1024 이하로 씀)
LABEL_COLS = 200      # 층 지도 가로 칸 수 (Unity LayerColumns와 같음)
HOLE_DILATE = 0.04    # 앞 층 경계에서 이만큼(그림 폭 비율) 더 파서 LaMa에 줌. 깊이 경계가 실제 윤곽보다 안쪽이라 0.012면 앞 물체 잔상이 남음 (11/26 rainy_day 0.012·0.03·0.05 비교)
MARGIN = 0.18         # 층 알파를 자기 영역 밖(앞 층 뒤)으로 넓히는 폭 (그림 폭 비율) — 펼쳤을 때 드러나는 곳
FEATHER = 0.006       # 뒤쪽(먼 층과 닿는) 가장자리 부드럽게 (그림 폭 비율)


def load_lama(device='cuda'):
    import torch
    if not os.path.exists(LAMA_PATH):
        os.makedirs(os.path.dirname(LAMA_PATH), exist_ok=True)
        torch.hub.download_url_to_file(LAMA_URL, LAMA_PATH)
    with open(LAMA_PATH, 'rb') as f:              # 한글 경로라 파일 경로 대신 메모리로 읽음
        model = torch.jit.load(io.BytesIO(f.read()), map_location=device)
    return model.eval()


def inpaint(model, rgb, hole):
    # rgb: HxWx3 uint8, hole: HxW bool (True = 채울 곳). H, W는 8의 배수
    import torch
    x = torch.from_numpy(rgb.astype(np.float32) / 255).permute(2, 0, 1)[None].cuda()
    m = torch.from_numpy(hole.astype(np.float32))[None, None].cuda()
    with torch.inference_mode():
        y = model(x, m)
    out = (y[0].permute(1, 2, 0).cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
    return np.where(hole[..., None], out, rgb)


def disk(r):
    r = max(1, int(round(r)))
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def labels_from_depth(near, n=N_LAYERS):
    # near: HxW 0..1 (1 = 가까움). 반환: HxW uint8 층 번호 (0 = 가장 가까움)
    H, W = near.shape
    far = 1 - near
    far = cv2.GaussianBlur(far.astype(np.float32), (0, 0), W / 250)      # 붓 터치 단위 잡음 제거
    th = np.quantile(far, [q / n for q in range(1, n)])                  # 면적이 같게 (Unity와 같은 규칙)
    lab = (far[..., None] > th[None, None, :]).sum(-1).astype(np.uint8)
    k = int(W / 120) | 1                                                 # 외톨이 조각을 주변 층으로
    for _ in range(2):
        lab = cv2.medianBlur(lab, min(k, 255))
    return lab


def build_layers(model, img, near, out_dir, n=N_LAYERS, log=print):
    # img: PIL RGB, near: img 크기의 0..1 깊이. out_dir에 layer0..n-1.png + layers.bytes
    W0, H0 = img.size
    s = WORK_SIDE / max(W0, H0)
    W, H = max(8, int(round(W0 * s / 8)) * 8), max(8, int(round(H0 * s / 8)) * 8)
    rgb = np.asarray(img.resize((W, H), Image.LANCZOS).convert('RGB'))
    nr = cv2.resize(near.astype(np.float32), (W, H), interpolation=cv2.INTER_AREA)
    lab = labels_from_depth(nr, n)
    os.makedirs(out_dir, exist_ok=True)

    hole_k, margin_k, feather = disk(W * HOLE_DILATE), disk(W * MARGIN), W * FEATHER
    info = []
    for k in range(n):
        own = lab == k
        nearer = lab < k
        if k == 0:
            fill = rgb
        else:
            hole = cv2.dilate(nearer.astype(np.uint8), hole_k) > 0
            t = time.time()
            # 넓게 판 구멍은 LaMa 맥락을 깨끗이 하는 데만 쓰고(앞 물체 잔상 방지), 자기 층 영역은 원본 픽셀을 다시 붙임.
            # 11/26 투영 시뮬레이션: 안 붙이면 정면에서 앞 물체 주변이 뿌옇게 번지고 가로등 같은 가는 물체가 지워짐
            fill = np.where(own[..., None], rgb, inpaint(model, rgb, hole))
            log(f'      층 {k}: 구멍 {hole.mean() * 100:.0f}% 채움 ({time.time() - t:.1f}초)')
        if k == n - 1:
            alpha = np.ones((H, W), np.float32)                          # 가장 먼 층 = 불투명 배경판
        else:
            # 자기 영역 + 앞 층 뒤로 MARGIN까지 (펼치면 드러나는 곳). 먼 층 쪽 경계만 살짝 부드럽게.
            reach = cv2.dilate(own.astype(np.uint8), margin_k) > 0
            body = own | (reach & nearer)
            # 부드러운 가장자리는 바깥(먼 층 쪽)으로만. 안쪽으로 부드럽게 하면 앱의 알파 잘라내기(0.5)에서 윤곽 안쪽 몇 px가
            # 잘려 뒤 층의 채운 색이 가는 선으로 비침 (11/26 투영 시뮬레이션에서 사람·나무 윤곽선으로 확인)
            dist_out = cv2.distanceTransform((~body).astype(np.uint8), cv2.DIST_L2, 5)
            alpha = np.clip(1 - dist_out / max(1.0, feather), 0, 1).astype(np.float32)
            # 앞 층 뒤로 뻗은 부분은 바깥 끝으로 갈수록 서서히 사라지게 (갑자기 끊긴 선 방지)
            d_own = cv2.distanceTransform((~own).astype(np.uint8), cv2.DIST_L2, 5)
            fade = np.clip(1 - (d_own - W * MARGIN * 0.6) / (W * MARGIN * 0.4), 0, 1)
            alpha = np.where(nearer, np.minimum(alpha, fade), alpha)
        rgba = np.dstack([fill, (alpha * 255 + 0.5).astype(np.uint8)])  # 알파 0인 곳도 RGB는 채운 색 유지 (가장자리 검은 테 방지)
        Image.fromarray(rgba, 'RGBA').save(os.path.join(out_dir, f'layer{k}.png'), optimize=True)
        info.append(dict(index=k, area=round(float(own.mean()), 3), visible=round(float(alpha.mean()), 3)))

    rows = max(2, round(LABEL_COLS * H / W))
    small = cv2.resize(lab, (LABEL_COLS, rows), interpolation=cv2.INTER_NEAREST)
    with open(os.path.join(out_dir, 'layers.bytes'), 'wb') as f:
        f.write(np.array([LABEL_COLS, rows], dtype='<u2').tobytes())
        f.write(small.astype(np.uint8).tobytes())
    return dict(count=n, size=[W, H], files=[f'layer{k}' for k in range(n)], map='layers', layers=info,
                hole_dilate=HOLE_DILATE, margin=MARGIN)


def preview(out_dir, n=N_LAYERS):
    # 확인용: 층마다 체크무늬 위에 얹은 그림을 가로로 이어 붙임
    tiles = []
    for k in range(n):
        im = Image.open(os.path.join(out_dir, f'layer{k}.png'))
        im.thumbnail((512, 512))
        c = np.indices(im.size[::-1]).sum(0) // 16 % 2
        bg = Image.fromarray(np.where(c[..., None], 255, 170).astype(np.uint8).repeat(4, 2)).convert('RGBA')
        bg.alpha_composite(im)
        tiles.append(bg.convert('RGB'))
    W = sum(t.width for t in tiles) + 8 * (n - 1)
    sheet = Image.new('RGB', (W, tiles[0].height), 'white')
    x = 0
    for t in tiles:
        sheet.paste(t, (x, 0)); x += t.width + 8
    path = os.path.join(out_dir, 'layers_preview.jpg')
    sheet.save(path, quality=90)
    return path


def main():
    # out은 묶음 폴더 (pipeline의 out_<key>와 같은 구조): out/layers/ 아래에 층 파일이 생김
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('image'); p.add_argument('out')
    p.add_argument('--depth', default='auto', choices=['auto', 'da3', 'da2s'])
    p.add_argument('--to-unity', metavar='FOLDER', help="Resources/HearingPainting 아래 그림 폴더 (rainy_day는 '.', hunters는 'hunters')")
    a = p.parse_args()
    sys.path.insert(0, HERE)
    from pipeline import depth_map, free
    img = Image.open(a.image).convert('RGB'); img.thumbnail((1600, 1600))
    t = time.time()
    near, name, agree = depth_map(img, a.depth)
    print(f'깊이 {name}' + (f' (일치도 {agree:.2f})' if agree is not None else '') + f' {time.time() - t:.0f}초')
    free()
    layer_dir = os.path.join(a.out, 'layers')
    info = build_layers(load_lama(), img, near, layer_dir)
    print(info)
    print(preview(layer_dir))
    if a.to_unity:
        from pipeline import UNITY_RES, copy_layers
        dst = os.path.normpath(os.path.join(UNITY_RES, a.to_unity))
        copy_layers(a.out, dst)
        print('Unity로 복사:', os.path.join(dst, 'layers'))


if __name__ == '__main__':
    main()
