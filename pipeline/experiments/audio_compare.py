# 소리 생성 모델 비교 (Q5): 「눈 속의 사냥꾼」 소리 6개를 세 모델로 만들어 들어 보고 고르기
#   python audio_compare.py
# 모델: Stable Audio Open 1.0(현재, 100 step) / Stable Audio 3 small-sfx(8 step) / Stable Audio 3 medium(8 step)
# 공정하게: 같은 프롬프트, 같은 길이(12초), 같은 시드, 모노로 합친 뒤 같은 RMS 음량으로 맞춤
# 결과: bench/audio3/<모델>/<소리>.wav, bench/audio3/index.html (들어 보고 소리마다 가장 좋은 것 고르기)
import gc, html, json, os, sys, time, traceback
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['HF_HUB_DISABLE_XET'] = '1'
for line in open(os.path.join(HERE, '.env'), encoding='utf-8-sig'):
    if '=' in line and not line.startswith('#'):
        k, v = line.strip().split('=', 1)
        if v.strip():
            os.environ[k.strip()] = v.strip()
OUT = os.path.join(HERE, 'bench', 'audio3'); os.makedirs(OUT, exist_ok=True)
SEC, SEED, TARGET_DB = 12.0, 1234, -20.0
scene = json.load(open(os.path.join(HERE, 'out_hunters', 'scene.json'), encoding='utf-8'))
SOUNDS = [(s['id'], s['label'], s['prompt']) for s in scene['sources']]


def finish(y, sr, path):
    import soundfile as sf
    y = np.asarray(y, np.float32)
    if y.ndim == 2:                       # (채널, 샘플) → 모노 (Unity 3D 공간화용)
        y = y.mean(axis=0)
    y = y[:int(SEC * sr)]
    rms = np.sqrt(np.mean(y ** 2)) + 1e-9
    y = np.clip(y * (10 ** (TARGET_DB / 20) / rms), -1, 1)
    sf.write(path, y, sr)


def run_sao():
    import torch
    from diffusers import StableAudioPipeline
    pipe = StableAudioPipeline.from_pretrained('stabilityai/stable-audio-open-1.0', torch_dtype=torch.float16).to('cuda')
    sr = pipe.vae.sampling_rate
    secs = []
    for sid, _, prompt in SOUNDS:
        g = torch.Generator('cuda').manual_seed(SEED)
        t = time.time()
        a = pipe(prompt, negative_prompt='low quality, music', num_inference_steps=100, audio_end_in_s=SEC,
                 num_waveforms_per_prompt=1, generator=g).audios[0]
        secs.append(time.time() - t)
        finish(a.float().cpu().numpy(), sr, os.path.join(OUT, 'sao1', sid + '.wav'))
    peak = torch.cuda.max_memory_allocated() / 1e9
    del pipe; gc.collect(); torch.cuda.empty_cache()
    return np.mean(secs), peak


def run_sa3(name):
    import torch
    from stable_audio_3 import StableAudioModel
    model = StableAudioModel.from_pretrained(name)
    sr = model.model.sample_rate
    secs = []
    for sid, _, prompt in SOUNDS:
        t = time.time()
        a = model.generate(prompt=prompt, duration=SEC, steps=8, cfg_scale=1, seed=SEED, batch_size=1)
        secs.append(time.time() - t)
        finish(a[0].float().cpu().numpy(), sr, os.path.join(OUT, name.replace('-', '_'), sid + '.wav'))
    peak = torch.cuda.max_memory_allocated() / 1e9
    del model; gc.collect(); torch.cuda.empty_cache()
    return np.mean(secs), peak


def main():
    import torch
    models = [('sao1', 'Stable Audio Open 1.0 (현재)', run_sao),
              ('small_sfx', 'Stable Audio 3 small-sfx', lambda: run_sa3('small-sfx')),
              ('medium', 'Stable Audio 3 medium', lambda: run_sa3('medium'))]
    status = {}
    for key, label, fn in models:
        os.makedirs(os.path.join(OUT, key), exist_ok=True)
        torch.cuda.reset_peak_memory_stats()
        try:
            sec, peak = fn()
            status[key] = f'평균 {sec:.1f}초/소리, 최대 VRAM {peak:.1f}GB'
        except Exception as e:
            status[key] = f'실패: {type(e).__name__}: {str(e)[:200]}'
            traceback.print_exc()
            gc.collect(); torch.cuda.empty_cache()
        print(f'{label}: {status[key]}', flush=True)
    json.dump(status, open(os.path.join(OUT, 'status.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    head = ''.join(f'<th>{html.escape(label)}<br><span class=m>{html.escape(status[key])}</span></th>' for key, label, _ in models)
    rows = ''
    for sid, name, prompt in SOUNDS:
        cells = ''
        for key, _, _ in models:
            f = os.path.join(key, sid + '.wav')
            if os.path.exists(os.path.join(OUT, f)):
                cells += (f'<td><audio controls preload=none src="{f}"></audio><br>'
                          f'<label><input type=radio name="{sid}" value="{key}"> 이게 가장 좋음</label></td>')
            else:
                cells += '<td class=m>없음</td>'
        rows += f'<tr><td><b>{html.escape(name)}</b><br><span class=m>{html.escape(prompt)}</span></td>{cells}</tr>'
    js = """<script>
const K='hp_audio_pick_v1'; let S=JSON.parse(localStorage.getItem(K)||'{}');
document.querySelectorAll('input[type=radio]').forEach(r=>{ if(S[r.name]===r.value) r.checked=true;
  r.addEventListener('change',()=>{S[r.name]=r.value; localStorage.setItem(K,JSON.stringify(S)); tally();}); });
function tally(){ const c={}; Object.values(S).forEach(v=>c[v]=(c[v]||0)+1);
  document.getElementById('tally').textContent='고른 수: '+(Object.entries(c).map(([k,v])=>k+' '+v).join(', ')||'아직 없음'); }
tally();
</script>"""
    open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(
        "<!doctype html><meta charset=utf-8><title>소리 생성 모델 비교</title><style>body{font-family:'Malgun Gothic';margin:24px;background:#f6f6f4}"
        "table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:8px;vertical-align:top}.m{color:#666;font-size:12px;font-weight:normal}audio{width:260px}</style>"
        "<h1>소리 생성 모델 비교 — 「눈 속의 사냥꾼」</h1>"
        "<p>같은 프롬프트, 12초, 같은 시드. 모두 모노로 합치고 같은 음량(RMS -20dB)으로 맞춤. 소리마다 가장 좋은 것을 고르세요(브라우저에 저장됨). "
        "기준: 프롬프트와 맞는지, 잡음·음악 섞임이 없는지, 반복해 들어도 자연스러운지.</p>"
        f"<p id=tally></p><table><tr><th>소리</th>{head}</tr>{rows}</table>{js}")
    print('보고서:', os.path.join(OUT, 'index.html'))


if __name__ == '__main__':
    main()
