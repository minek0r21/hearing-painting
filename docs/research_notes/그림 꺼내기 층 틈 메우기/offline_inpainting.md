# Offline inpainting for background-completed RGBA depth layers (Windows, RTX 3060 12GB, Python)

Research date: 2026-11-26. Notes are mixed English/Korean. Anything without a [Source] link is in Inferences or Gaps. Speed and VRAM numbers were **not measured on an RTX 3060** unless stated (정확하지 않을 수 있음).

---

## Q1. OpenCV inpainting (cv2.inpaint Telea / Navier-Stokes): quality on large holes, speed, limits

### Takeaway
Classical diffusion/PDE inpainting only propagates colours inward. On holes the size of a human figure in a painting it gives smeared, overly smooth fills with no texture. It is fine as a zero-dependency fallback, or for very thin cracks such as 1–5 px dilation margins, but it is not suitable as the main filler.

### Cited Findings
- The 3D Photography paper (Shih et al., CVPR 2020) criticises Facebook 3D Photos' layer inpainting: "it uses a isotropic diffusion algorithm for inpainting colors, which produces overly smooth results and is unable to extrapolate texture and structures." This is the same class of algorithm as cv2.inpaint. — [Shih et al. 2020 (search summary of arXiv 2004.04727)](https://arxiv.org/abs/2004.04727v2)
- The OpenCV inpainting tutorial page (docs.opencv.org) returned HTTP 403 to the fetch tool, so its wording could not be quoted. — [OpenCV tutorial](https://docs.opencv.org/4.x/df/d3d/tutorial_py_inpainting.html)

### Inferences
- From general knowledge, not re-verified this session (정확하지 않을 수 있음): `cv2.inpaint(img, mask, inpaintRadius, cv2.INPAINT_TELEA | cv2.INPAINT_NS)` is CPU-only and meant for small damaged regions such as scratches and text. Large holes give streaks and blur, and it can be slow (seconds or more) on large masks at 1500 px.
- Practical role in this pipeline:
  1. A cheap pre-fill so nothing is left as black or garbage before a learned model runs.
  2. Filling small residual pinholes in the alpha margin.
  3. A no-GPU fallback.
- Windows + Korean path pitfall (well known, not sourced here): `cv2.imread`/`cv2.imwrite` fail silently on non-ASCII paths on Windows. Use `cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_UNCHANGED)` and `cv2.imencode('.png', img)[1].tofile(path)`, or do all file I/O with PIL.

### Gaps
- No measured timing for cv2.inpaint at 1024–1600 px with large masks was found.
- The official OpenCV doc text could not be fetched (403).

---

## Q2. LaMa (big-lama) and packaged forms: license, VRAM, speed, quality on paintings and large masks, Windows pitfalls

### Takeaway
big-lama is the best default for "fill behind the foreground" in this pipeline:
- Apache-2.0, 51M parameters, feed-forward (one pass, no prompt).
- Deliberately trained for **large masks**.
- Generalises from 256 px training up to about 2K.
- It does not invent new objects.

The cleanest integration is to load the TorchScript `big-lama.pt` directly with `torch.jit.load`, either through `simple-lama-inpainting` or copying its ~30 lines of logic. Do **not** `pip install simple-lama-inpainting` into the existing env without `--no-deps`. It pins `pillow<10` and `numpy<2`, which would downgrade the transformers 5.x / diffusers 0.43 environment.

### Cited Findings
**Official repo (advimman/lama)**
- The official code is licensed **Apache License 2.0**. — [advimman/lama LICENSE](https://raw.githubusercontent.com/advimman/lama/main/LICENSE)
- The README says LaMa "generalizes surprisingly well to much higher resolutions (~2k❗️) than it saw during training (256x256)" and handles "completion of periodic structures".
- Big-LaMa is described as "the best model (Places2, Places Challenge)", with weights on Hugging Face (`smartywu/big-lama`).
- The README states no license specifically for the weights.
- It has no Windows notes; setup is virtualenv/conda/Docker with Linux-style commands.
- It also offers a refinement option (`refine=True`, "Feature Refinement to Improve High Resolution Image Inpainting").
- Source for the five points above: [advimman/lama README](https://github.com/advimman/lama)

**LaMa paper**
- Big LaMa has "18 residual blocks, all based on FFC, resulting in 51M parameters". It was trained "on a subset of 4.5M images from Places-Challenge" on "256×256 crops" (8×V100, ~240 h).
- Stated limitation: it "usually struggles when a strong perspective distortion gets involved."
- The paper does not report Big LaMa inference time.
- Source: [LaMa paper, arXiv 2109.07161](https://ar5iv.labs.arxiv.org/html/2109.07161)
- Design rationale: for wide masks a normal CNN's receptive field can sit entirely inside the hole, "especially pronounced for high-resolution images". LaMa uses fast Fourier convolutions for an image-wide receptive field, a high-receptive-field perceptual loss, and large training masks. — [LaMa paper abstract/intro](https://arxiv.org/abs/2109.07161)
- Samsung's blog compares LaMa (trained 256×256) with MADF (trained 512×512) and says LaMa "still performs better in 1920x1536". — [Samsung Research blog](https://research.samsung.com/blog/LaMa-New-Photo-Editing-Technology-that-Helps-Removing-Objects-from-Images-Seamlessly)
- Blur on large holes: the RORem authors (diffusion remover, 2025) report that LaMa scores **higher PSNR** than diffusion removers, which lose detail through VAE compression. They also say LaMa "generates blurry synthesis output in most cases". This is the authors' own, self-interested claim. — [RORem arXiv 2501.00740 (via search summary)](https://arxiv.org/pdf/2501.00740)

**simple-lama-inpainting**
- License Apache-2.0. Install with `pip install simple-lama-inpainting`.
- API: `SimpleLama()(image, mask)`. The image is 3-channel PIL or ndarray; the mask is 1-channel and 255 means inpaint. Output is a PIL Image.
- CLI: `simple_lama <img> <mask> <out>`.
- Source: [simple-lama-inpainting README](https://github.com/enesmsahin/simple-lama-inpainting)
- Latest version **0.1.2, released 2023-07-28** (stale). `requires_dist` is `numpy (>=1.24.3,<2.0.0)`, `opencv-python (>=4.8.0.74,<5)`, `pillow (>=9.5.0,<10.0.0)`, `torch (>=1.13.1,!=2.0.1)`, `torchvision (>=0.14.1)`, `fire (>=0.5.0,<0.6.0)`. — [PyPI JSON](https://pypi.org/pypi/simple-lama-inpainting/json)
- Model loading:
  - It downloads the TorchScript file `https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt`. The URL can be overridden with env `LAMA_MODEL_URL`.
  - Env `LAMA_MODEL` points to a local file instead.
  - The default device is `cuda` if available, chosen at import time.
  - Source: [model.py](https://raw.githubusercontent.com/enesmsahin/simple-lama-inpainting/main/simple_lama_inpainting/models/model.py)
- Preprocessing:
  - The image is float32 in 0–1. It is padded bottom/right to a **multiple of 8** with `np.pad(..., mode="symmetric")`.
  - No resizing by default; there is an optional `scale_factor` using INTER_AREA for the image and INTER_NEAREST for the mask.
  - The mask is binarised as `mask > 0`, so **any non-zero value becomes hole**. Feathered masks must be thresholded before LaMa.
  - Source: [util.py](https://raw.githubusercontent.com/enesmsahin/simple-lama-inpainting/main/simple_lama_inpainting/utils/util.py)

**IOPaint (formerly lama-cleaner)**
- Apache-2.0.
- Erase models include LaMa, MAT, MI-GAN, LDM, ZITS, FcF and Manga. Diffusion models include SD1.5 inpainting, SDXL inpainting, BrushNet, PowerPaintV2, AnyText and Paint-by-Example.
- It has a batch CLI: `iopaint run --model=lama --device=cuda --image=<folder> --mask=<folder> --output=<dir>`. A single mask file is applied to all images.
- It has a Windows 1-click installer; install CUDA PyTorch first for GPU use.
- **The repo was archived (read-only) on Aug 13, 2025.**
- Source for the points above: [Sanster/IOPaint](https://github.com/Sanster/IOPaint)
- The IOPaint model page marks LaMa, MAT and MI-GAN as recommended. It describes MI-GAN as "Minimal in size, requiring the least amount of resources". It gives no VRAM or speed numbers. — [iopaint.com/models](https://www.iopaint.com/models)

### Inferences
**Recommended integration (avoids dependency conflicts):**
- Download `big-lama.pt` once and load it with `torch.jit.load`.
- Feed it a float32 image `[1,3,H,W]` in 0–1 and a mask `[1,1,H,W]` in {0,1}. Pad to a multiple of 8 and crop back afterwards.
- This avoids `pip install simple-lama-inpainting` pulling `pillow<10` and `numpy<2` into the PyTorch 2.7.1 / transformers 5.x env. If you do install the package, use `pip install --no-deps simple-lama-inpainting` (untested on this exact env).

**Korean path:**
- Untested guess, 정확하지 않을 수 있음: `torch.jit.load` with a non-ASCII Windows path may fail in some torch versions.
- Safe pattern: `torch.jit.load(io.BytesIO(open(path,'rb').read()), map_location='cuda')`. Alternatively, keep the model file in an ASCII path (e.g. `C:\models\big-lama.pt`).

**Speed and VRAM (estimate, not measured on a 3060; 정확하지 않을 수 있음):**
- 51M parameters, single forward pass. Expect roughly 0.2–1 s per 1024–1600 px image on an RTX 3060, plus a few seconds for first-call TorchScript warm-up.
- VRAM is likely a few GB at 1.5K.
- If VRAM or time becomes an issue, run at a downscaled resolution, then upsample only the hole and composite.

**Quality on paintings:**
- LaMa reproduces local texture and periodic patterns (brush-stroke texture, sky, water, foliage, ground) and does not hallucinate new objects. This is the property we want for "background behind a figure".
- Its weaknesses are blurrier centres in very wide holes and perspective-heavy structure (architecture lines).
- For Bruegel crowds, large hidden areas will get plausible texture, not plausible people. That is arguably desirable for a background layer.

**MI-GAN** is an even lighter option bundled in IOPaint. It is not researched in depth here.

### Gaps
- No measured LaMa time/VRAM at 1024 or 1600 px on any consumer GPU was found. The paper and README do not report Big-LaMa inference time.
- No published evaluation of LaMa specifically on paintings, ukiyo-e or ink paintings was found. Places-trained models are photo-domain; behaviour on flat ukiyo-e colour areas and ink wash is unverified (likely fine for flat areas, uncertain for line work).
- Weight license: the repo LICENSE is Apache-2.0, but the README does not state the weights' license separately.
- ONNX ports (e.g., Carve/LaMa-ONNX) were not checked this session.

---

## Q3. MAT, ZITS and other non-diffusion inpainters

### Takeaway
MAT (CVPR 2022) is a strong large-hole model, but it is "research purposes only", built on old StyleGAN2-ADA code (PyTorch 1.7, CUDA 11.0), and works in 512-multiples. It is not worth the integration pain over LaMa unless LaMa visibly fails. ZITS and FcF are mainly available through IOPaint, which is archived.

### Cited Findings
- MAT: "The code and models in this repo are for research purposes only."
- MAT pretrained models run at 512×512; "generated image sizes must be multiples of 512".
- MAT models: CelebA-HQ, FFHQ, and Places365-Standard (Places-512 trained on 8M images).
- MAT dependencies: Python 3.7, PyTorch 1.7.1, CUDA 11.0, built on StyleGAN2-ADA. CVPR 2022 Oral.
- Source for the four points above: [fenglinglwb/MAT](https://github.com/fenglinglwb/MAT)
- IOPaint lists LaMa, MAT and MI-GAN as recommended erase models, and LDM, ZITS, FcF and Manga without descriptions. — [iopaint.com/models](https://www.iopaint.com/models)

### Inferences
- MAT is GAN-based, so it can produce sharper but more "invented" structure than LaMa. Its license is unclear and possibly non-commercial. Usable via IOPaint (`--model=mat`) for an A/B test, but not as the main path.
- ZITS (structure-guided, ~2022) targets lines and structure (architecture). It might help Bruegel buildings, but setup is heavier. Not investigated further.

### Gaps
- No ZITS license, VRAM or speed data was gathered. The exact MAT LICENSE text was not read.

---

## Q4. Diffusion inpainting (SD2 / SDXL inpainting, FLUX.1 Fill [dev], SD3.5, 2025–26 models): VRAM on 12 GB, time, style consistency, prompts, licenses

### Takeaway
SDXL inpainting runs on 12 GB in fp16 through diffusers 0.43 and gives sharper, more painterly fills than LaMa. However:
- It needs a prompt.
- It is stochastic, so it can invent objects or figures in a large hole.
- It alters unmasked pixels through the VAE unless you overlay the original back.

FLUX.1 Fill [dev] is higher quality, but it is 12B parameters, gated, and under the **FLUX.1 [dev] Non-Commercial License**. On 12 GB it needs GGUF/NF4 quantisation or offload, and it is slow. Use diffusion only as an optional "refine" pass on top of a LaMa fill, not as the default.

### Cited Findings
**SDXL inpainting (`diffusers/stable-diffusion-xl-1.0-inpainting-0.1`)**
- License **CreativeML Open RAIL++-M**. Trained at 1024×1024.
- The card says "make sure to use `strength` below 1.0" (the example uses 0.99) because quality drops and the output is less sharp at 1.0.
- Example settings: `guidance_scale=8.0`, `num_inference_steps=20`. Steps "between 15 and 30 work well".
- Limitations: no perfect photorealism; faces and people may not generate properly; the autoencoder is lossy.
- Source for the four points above: [HF model card](https://huggingface.co/diffusers/stable-diffusion-xl-1.0-inpainting-0.1)

**Diffusers inpainting docs (v0.43)**
- Memory saving: `enable_model_cpu_offload()`. With PyTorch 2.x, SDPA attention is automatic, so xFormers is unnecessary.
- `mask_processor.blur(mask, blur_factor=33)` softens the transition between original and inpainted areas.
- Inpaint-specific checkpoints "are more likely to change your unmasked area". `image_processor.apply_overlay(mask, init, result)` forces unmasked pixels to stay identical.
- `padding_mask_crop=32` crops around the mask, upscales the crop for inpainting, and pastes it back, which improves quality.
- Source for the three points above: [diffusers inpaint guide](https://huggingface.co/docs/diffusers/using-diffusers/inpaint)

**FLUX.1 Fill [dev]**
- 12B-parameter rectified-flow transformer, BF16 weights.
- **Gated**, under the FLUX.1 [dev] Non-Commercial License + Acceptable Use Policy. The card says outputs may be used for "personal, scientific, and commercial purposes".
- Example: `guidance_scale=30`, `num_inference_steps=50`, `max_sequence_length=512`.
- No VRAM guidance on the card.
- Source for the points above: [HF model card](https://huggingface.co/black-forest-labs/FLUX.1-Fill-dev)
- GGUF quants exist (e.g., Q4_K_M ≈ 6.9 GB file, Q8_0 ≈ 12.7 GB). These figures come from a search summary and are unverified. — [YarvixPA/FLUX.1-Fill-dev-gguf](https://huggingface.co/YarvixPA/FLUX.1-Fill-dev-gguf)
- A third-party estimator lists ≈8.7 GB at INT4 at 1024² with an RTX 3060 12GB as minimum hardware.
- A stable-diffusion-art guide says 24 GB is needed for its (unquantised) workflow.
- Source for both estimates above: [apxml](https://apxml.com/models/flux-1-fill-dev); [stable-diffusion-art](https://stable-diffusion-art.com/flux1-fill-inpaint/)
- No measured RTX 3060 seconds-per-image was found for FLUX Fill. — (search, no source)

**Hallucination**
- The ObjectClear authors state that diffusion-based inpainting/removal methods "often introduce artifacts, hallucinate contents, alter background". — [ObjectClear arXiv 2505.22636](https://arxiv.org/html/2505.22636v2)
- The AdaEraser (2026) authors say OmniPaint "tends to fill target regions with content inconsistent or semantically irrelevant to the surrounding background". — [AdaEraser arXiv 2605.15921 (search summary)](https://arxiv.org/pdf/2605.15921)

### Inferences
**SDXL-inpaint on a 3060 12GB (estimate, 정확하지 않을 수 있음):**
- fp16 with `enable_model_cpu_offload()` should fit.
- Expect roughly 10–25 s per 1024² image at 20–30 steps. 1600 px is outside the training distribution: crop around each hole with `padding_mask_crop`, or tile.

**SD1.5 / SD2 inpainting:**
- Lighter and faster (512 px native), but painterly quality is lower and resolution mismatches matter.
- SD2-inpainting and SD3.5 inpainting cards/licenses were not checked this session. SD3.5 falls under the Stability Community License, from memory, unverified.

**Prompting for "background":**
- An empty prompt or a generic prompt like "background, oil painting, impressionist brushwork" is typical.
- A negative prompt listing "person, figure, people, animal, text" is the usual mitigation against inventing figures in the hole.
- Large holes still invite new objects: diffusion models complete semantics, not just texture. This is general practice, not measured on paintings here.

**Must-do when using diffusion:**
- Use `apply_overlay` or manual compositing so pixels outside the hole stay byte-identical to the original. The VAE round-trip otherwise shifts colours and softens brushwork.
- A good hybrid is a LaMa fill first, then SDXL img2img/inpaint at low `strength` (≈0.3–0.5) over the hole only. This adds painterly texture while keeping LaMa's layout and lowering hallucination risk. This is a common community practice, not formally sourced.

**FLUX Fill:**
- Best quality is likely, but the non-commercial license, gated download, 12B size and multi-minute runtimes on a 3060 with offload make it a poor default for an automated per-layer loop. Fine for a few hero images if the project stays non-commercial (a student project probably qualifies, but check the license text).

### Gaps
- No measured SDXL-inpaint or FLUX-Fill timings on an RTX 3060 were found.
- No study found on diffusion inpainting style consistency specifically on Impressionist, ukiyo-e or ink paintings.
- SD3.5 / Qwen-Image-Edit / FLUX Kontext-style 2025–26 editors were not investigated for this use.

---

## Q5. Object-removal-specific models (PowerPaint, BrushNet, ObjectClear, RORem, OmniEraser)

### Takeaway
These target "remove an object and its shadow or reflection" in photos. In our case the "object" is the nearer depth layer, and we want the background continued behind it, so the goal matches.

However, all the 2025 removers are built on SD/SDXL, are photo-trained, and need extra setup. ObjectClear is **non-commercial** (NTU S-Lab License). Rankings are self-reported. For painted inputs and a 4-layer automatic loop, LaMa remains the pragmatic choice. PowerPaint/BrushNet via IOPaint are the easiest to A/B.

### Cited Findings
**ObjectClear**
- License: "The code, models, and datasets are licensed under NTU S-Lab License 1.0", non-commercial only.
- Built on SDXL-Inpainting plus a CLIP ViT-L/14 image encoder.
- Inputs: image + mask; supports folder batch inference.
- `--guidance_scale 2.5 --use_fp16`. Higher values give stronger removal, lower values preserve more background.
- No VRAM, timing or Windows notes.
- Source for the points above: [zjx0101/ObjectClear](https://github.com/zjx0101/ObjectClear)

**RORem**
- The authors report LaMa has higher PSNR because diffusion VAE compression loses detail in unmasked regions.
- AdaEraser (2026) says RORem "performs suboptimally in preserving details and restoring content".
- Source for both points above: [RORem](https://arxiv.org/pdf/2501.00740); [AdaEraser](https://arxiv.org/pdf/2605.15921)

**OmniEraser**
- Trained on paired video-frame data and claims superiority over LaMa and diffusion methods on RemovalBench/RORD-Val (author-reported). — [OmniEraser arXiv 2501.07397](https://arxiv.org/html/2501.07397v3)

**PowerPaint**
- Uses "learnable task prompts" for object removal, among other tasks.
- PowerPaintV2/BrushNet "can turn any sd1.5 model into an inpainting model".
- Both are available in IOPaint.
- Source for the points above: [iopaint.com/models](https://www.iopaint.com/models)
- Community (ComfyUI-BrushNet) advice for PowerPaint removal: add "empty scene blur" to the prompt. It "is often hard to completely remove the object, especially if it is at the front"; put the object description in the negative prompt. — [ComfyUI-BrushNet README](https://github.com/nullquant/ComfyUI-BrushNet/blob/main/README.md)

### Inferences
- In our setup the hole equals the exact silhouette of nearer layers plus dilation, with no shadow or reflection to chase. The main advantage of the removers (removing object effects) is mostly irrelevant here.
- Their other advantage, less hallucination than plain SD inpainting, is useful, but LaMa already does not hallucinate objects.
- BrushNet and PowerPaint weight licenses were not confirmed. Do not assume they are commercial-OK.

### Gaps
- No independent benchmark comparing these on artwork was found. VRAM and time on 12 GB are unknown. The BrushNet/PowerPaint weight licenses are unverified.

---

## Q6. Tricks from 3D-photo / layered-depth pipelines for background-layer inpainting

### Takeaway
Established practice from Shih et al. (CVPR 2020):
- Inpaint only the **background side** of each depth edge.
- **Dilate the synthesis (hole) region by ~5 px** into the foreground side to absorb depth-edge misalignment.
- Use only connected background pixels as context.
- Iterate until no new holes appear.

For a fixed 4-band pipeline, the simple, robust analogue is a back-to-front pass where layer k's hole is the union of all nearer layers (dilated). Filling the farthest layer once with everything in front masked gives a full background plate.

### Cited Findings
**Shih et al., 3D Photography using Context-aware Layered Depth Inpainting (CVPR 2020)**
- The synthesis region near the depth edge is dilated "by 5 pixels (the context region erodes correspondingly)" to compensate for imperfect alignment between depth edges and occlusion boundaries.
- The synthesis region is grown by flood fill for 40 iterations and the context region for 100 iterations.
- The pixels are split into foreground and background silhouettes at the depth edge, and **only the background silhouette is inpainted**. The synthesis region does not step back across the silhouette.
- The process is reapplied "until no further inpainted depth edges are generated".
- The code is MIT-licensed and builds on EdgeConnect + MiDaS.
- Source for the points above: [arXiv 2004.04727 (ar5iv)](https://ar5iv.labs.arxiv.org/html/2004.04727); [CVPR open access](https://openaccess.thecvf.com/content_CVPR_2020/html/Shih_3D_Photography_Using_Context-Aware_Layered_Depth_Inpainting_CVPR_2020_paper.html)
- Facebook 3D Photos' diffusion colour fill is "overly smooth", which motivated learned inpainting. — [Shih et al. 2020](https://arxiv.org/abs/2004.04727v2)
- Diffusers inpainting provides `mask_processor.blur` for soft transitions and `apply_overlay` to keep unmasked pixels identical. — [diffusers inpaint guide](https://huggingface.co/docs/diffusers/using-diffusers/inpaint)

### Inferences
Concrete recipe for the 4-band case (layer 0 = nearest … layer 3 = farthest). This is my synthesis, not from one source:

1. **Masks**
   - `own_k` = pixels with band == k.
   - `nearer_k` = OR of `own_j` for j < k.
   - `hole_k = dilate(nearer_k, r)` with r ≈ 5–15 px at 1.5K (Shih uses 5 px). The dilation deliberately eats a few px of `own_k` (and farther bands) along the boundary, removing depth-edge fringe ("halo") colour that belongs to the foreground. The rest of `own_k` stays as unmasked context.
   - Pixels of farther layers (j > k) are valid context. Leave them visible in the LaMa input; do not add them to the hole.
2. **Back-to-front, independent fills.** For each k ≥ 1, run LaMa on the **original image** with `hole_k`. Layer 3's hole is all of layers 0–2, which gives a full background plate.
   - Optionally do k = 3 first, then build layer 2's input from the original with layer 3's region intact. Each fill is independent because farther content is always original pixels.
   - The nearest layer (k = 0) needs no fill.
3. **Keep the original under each layer's own band.** Composite `out_k = original where own_k else filled_k`. Never replace own-band pixels with model output; this avoids VAE or LaMa softening of real brushwork.
4. **Alpha**
   - `alpha_k = own_k ∪ (filled margin band of width m around own_k within hole_k)`. Alternatively, for the farthest layer, alpha = 1 everywhere, as a full plate.
   - Feather the alpha edge with a Gaussian of ~2–4 px, but only on the **outer** edge (toward nearer layers). The nearer layer's alpha covers the seam, so soft edges do not ghost.
   - Ghosting comes from semi-transparent duplicated foreground colour in the back layer. The dilation in step 1 is what removes the foreground halo from the back layer.
5. **Threshold before LaMa.** simple-lama treats any mask value > 0 as hole. Pass a hard binary mask to the inpainter and apply feathering only in the final alpha.
6. **Margin size.** The margin must exceed the maximum parallax shift in the Unity/AR viewer (pixels revealed when the camera moves). If parallax is small, a margin of ~5–10 % of image width is plenty, and the rest of the hole can be left transparent or filled anyway.
7. **Second pass (optional).** Shih iterates because inpainted regions can create new depth edges. With fixed bands and full-plate filling, one pass per layer is usually enough.

Write PNGs with PIL (`Image.fromarray(rgba).save(path)`) to avoid OpenCV's non-ASCII path issue.

### Gaps
- No source specific to 4-band "parallax layer" pipelines with measured margin sizes was found. The margin/feather numbers above are heuristics, not sourced.

---

## Q7. Rough wall-clock for 4 layers per painting on an RTX 3060

### Takeaway
All estimates are unmeasured (정확하지 않을 수 있음):
- **With big-lama:** about 3 LaMa calls (layers 1–3; layer 0 needs none) at ~1–2 s each including I/O, plus a one-time model load of ~5–10 s. Expect **under ~10 s per painting**, with mask dilation, compositing and PNG writing dominating.
- **With SDXL-inpaint refinement:** roughly 15–30 s per layer, i.e. **~1–2 min per painting**.
- **With FLUX Fill quantised:** likely **several minutes per painting**.

### Cited Findings
- Big LaMa is a 51M-parameter feed-forward network. The paper gives no absolute timing. — [LaMa paper](https://ar5iv.labs.arxiv.org/html/2109.07161)
- SDXL-inpaint recommends 15–30 steps at 1024². — [HF card](https://huggingface.co/diffusers/stable-diffusion-xl-1.0-inpainting-0.1)
- FLUX Fill example uses 50 steps on a 12B model. — [HF card](https://huggingface.co/black-forest-labs/FLUX.1-Fill-dev)
- No measured RTX 3060 numbers were found for any of these. — (searches returned none)

### Inferences
- Model loading (TorchScript ~200 MB; SDXL ~7 GB fp16) dominates for single images. Keep the model resident across the 4 layers and across paintings.
- Recommendation order for this project:
  1. big-lama via TorchScript, the default.
  2. Optional SDXL-inpaint low-strength refine on hero images.
  3. cv2.inpaint as a no-GPU fallback.
  4. MAT, FLUX Fill and ObjectClear only for experiments, given license and setup costs.

### Gaps
- Actual timing must be measured locally: time `torch.jit.load` and one forward pass at 1024 and 1600 px with `torch.cuda.synchronize()`, and check `torch.cuda.max_memory_allocated()`.
