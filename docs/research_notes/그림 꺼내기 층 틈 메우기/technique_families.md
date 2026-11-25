# Technique families for disocclusion filling in single-image 2.5D / layered parallax scenes

(Researched 2026-11-26. Notes in mixed English/Korean. "[미확인]" means uncertain or undocumented. "[older]" flags pre-2019 sources.)

## Q1. Naive depth warping / single continuous mesh (baseline; what the app's "smooth filler mesh" is)

### Takeaway
If you warp or extrude the image onto a depth map with no layered hidden content, a disocclusion either becomes a **gap** (when the mesh is torn at depth edges) or a **stretched "rubber-sheet"** (when the mesh stays connected). Both are standard, well-known artifacts. Google Cinematic Photos mostly *avoids* them by choosing the camera path rather than filling them. The app's smooth filler surface behind the layers belongs to this family, so the stretching it shows is expected.

### Cited Findings
- Shih et al. say directly that "naïve depth-based warping techniques either produce gaps here or stretched content" at parallax disocclusions — [Shih et al. 2020, arXiv 2004.04727](https://arxiv.org/abs/2004.04727)
- Google Cinematic Photos builds the scene by "extruding the RGB image onto the depth map". Neighbouring mesh points can then differ greatly in depth, and the "photo appears to be stretched" as the camera moves off the face-on view — [Google Research blog, "The Technology Behind Cinematic Photos" (Feb 2021)](https://research.google/blog/the-technology-behind-cinematic-photos/)
- Cinematic Photos handles this by optimizing the camera trajectory per photo. The loss "triggers more heavily in areas with a greater number of connected artifact pixels", and padded head/body/background masks bias the path toward "artifacts in the background regions". The blog does not describe an inpainting step — [Google Research blog](https://research.google/blog/the-technology-behind-cinematic-photos/)
- Cinematic Photos uses DeepLab person segmentation to "pull forward pixels of the depth map that were incorrectly predicted to be in the background". It may also shrink the field of view so the mesh fully covers every frame — [Google Research blog](https://research.google/blog/the-technology-behind-cinematic-photos/)
- The pre-learning version of Facebook 3D Photos (an LDI plus a mesh) inpainted occluded color with "isotropic diffusion", which "produces overly smooth results and is unable to extrapolate texture and structures" — [Shih et al. 2020](https://arxiv.org/abs/2004.04727). This describes the 2018 product, cited through a 2020 paper.

### Inferences
- The app has 4 hard depth bands, a far layer on the painting plane, and a very smooth continuous depth mesh behind them. That is in effect "naive warp + diffusion-like fill". A smooth mesh textured with the original painting colors is the same thing as isotropic diffusion or stretching: it has no texture of its own in the hidden region, and its UVs still sample the foreground's pixels. That explains both symptoms the user sees, the stretching and the foreground colors showing through.
- Cinematic Photos' approach of hiding artifacts by limiting motion is relevant: the fan-out distance and viewing angle decide how much hidden area gets exposed.

### Gaps
- Whether Cinematic Photos runs on device or on a server is not stated in the blog. Whether it later added generative inpainting was not found.

---

## Q2. Layered Depth Images (LDI): concept and how holes are represented and filled

### Takeaway
An LDI stores **zero to many pixels per image location**, each with color and depth. Explicit 4-connectivity is cut at depth discontinuities, so hidden surfaces sit as extra "behind" pixels instead of as stretched triangles. The holes are the locations on the far side of a cut edge that have no pixels yet. Both learned 3D-photo systems (Shih 2020, Kopf 2020) grow new LDI pixels into those locations and inpaint their color and depth. The result converts to a lightweight textured mesh that renders in real time on phones.

### Cited Findings
- In an LDI, each location holds "from zero to many" pixels, each pixel stores color and depth, and pixels are 4-connected "like normal image pixels within smooth regions, but do not have neighbors across depth discontinuities" — [Shih et al. 2020](https://arxiv.org/abs/2004.04727)
- LDI is "more compact due to its sparsity" than an MPI and "can be converted into a light-weight mesh representation for rendering" — [Shih et al. 2020](https://arxiv.org/abs/2004.04727)
- Shih et al. criticize the "rigid" multi-layer schemes (a fixed N layers per pixel, nearest surface in layer 1, and so on): "across depth discontinuities the content within a layer changes abruptly, which destroys locality in receptive fields of convolution kernels". Their LDI instead uses variable layers with explicit connectivity — [Shih et al. 2020](https://arxiv.org/abs/2004.04727)
- Kopf et al. 2020 (One Shot 3D Photography) start from a one-layer LDI with pixels disconnected across disparity jumps > τ = 0.05. They grow occluded geometry behind discontinuities for 50 iterations, drop groups under 20 pixels, and say they are "not limited to two layers" — [Kopf et al. 2020, ar5iv 2008.12298](https://ar5iv.labs.arxiv.org/html/2008.12298)
- The original LDI concept is Shade et al. 1998 [older], cited as reference [51] in [Shih et al. 2020](https://arxiv.org/abs/2004.04727)

### Inferences
- The app's 4 RGBA layers are a "rigid, fixed-N" layering, closer to a coarse MPI or a set of sprites than to an LDI. The LDI's key advantage is that new pixels are added only where an occluding edge exists, and each layer region gets exactly the hidden band it needs. You can copy this offline: for each layer k, the hidden region to fill is a band behind the silhouettes of layers nearer than k. Its width is bounded by the maximum fan-out offset, not the whole object area.

### Gaps
- No standard, maintained LDI file format or Unity importer was found.

---

## Q3. 3D Photo Inpainting (Shih, Su, Kopf, Huang, CVPR 2020)

### Takeaway
Offline pipeline: estimate depth (MiDaS) → sharpen depth and link depth edges → build an LDI cut at those edges → for each edge, inpaint a local **context → synthesis** region with three CNNs (edge, then color, then depth), repeating until no new edges appear → export a textured mesh (.ply). Code is MIT-licensed, Python 3.7 / PyTorch 1.4 / CUDA. It takes about 2–3 minutes per image including the demo video renders. The output is a mesh, not RGBA layer images. It is the strongest "classic" reference design for the app's problem.

### Cited Findings
- **Preprocess:** the paper's parameters are tuned for 1024 px on the long side. The depth map is sharpened with a bilateral median filter (7×7 window). Raw discontinuities come from thresholding the disparity difference between neighbouring pixels, then get cleaned and linked into connected depth edges, and segments under 10 px are removed (the threshold was set by 5-fold cross-validation) — [Shih et al. 2020 PDF](https://arxiv.org/pdf/2004.04727)
- **Context and synthesis regions:** the LDI is disconnected across each edge, and only the background side is inpainted. The synthesis region is grown flood-fill style from the silhouette pixels for 40 iterations, staying strictly in the occluded area. The context region is grown for 100 iterations along real LDI connections and stops at silhouettes. "Synthesis performs better with slightly larger context regions" — [Shih et al. 2020 PDF](https://arxiv.org/pdf/2004.04727)
- **Edge dilation:** depth edges may not align with the color edges, so "we dilate the synthesis region near the depth edge by 5 pixels (the context region erodes correspondingly)". The paper says this reduces artifacts, and Fig. 5 compares results with and without dilation — [Shih et al. 2020 PDF](https://arxiv.org/pdf/2004.04727)
- **Networks:** an edge-inpainting network predicts depth edges in the synthesis region first. The color and depth networks are conditioned on those edges, so the inpainted color and depth stay aligned. They are built on EdgeConnect and partial-convolution inpainting — [Shih et al. 2020 PDF](https://arxiv.org/pdf/2004.04727); [GitHub vt-vl-lab/3d-photo-inpainting](https://github.com/vt-vl-lab/3d-photo-inpainting)
- **Multi-layer:** "we apply our inpainting model until no further inpainted depth edges are generated", because one pass can leave holes visible through newly inpainted discontinuities — [Shih et al. 2020 PDF](https://arxiv.org/pdf/2004.04727)
- **Training data:** COCO images with MegaDepth pseudo-depth. Real context/synthesis region shapes are pasted onto other images, so ground truth exists under the simulated occlusion. Training used 1 V100 — [Shih et al. 2020 PDF](https://arxiv.org/pdf/2004.04727)
- **Output and rendering:** the inpainted LDI becomes a 3D textured mesh that "can easily be rendered using standard graphics engines on edge devices" with no per-view inference — [Shih et al. 2020 PDF](https://arxiv.org/pdf/2004.04727)
- **Code:** MIT license. Python 3.7.4, PyTorch 1.4.0, CUDA 10.1, tested on Ubuntu 18.04. Outputs are a MiDaS depth map (.npy/.png, editable, with `require_midas: False` to reuse an edited one), an optional `.ply` mesh (`save_ply`), and zoom-in / swing / circle / dolly-zoom videos. It "usually takes about 2-3 minutes" per image. Config lives in `argument.yml` — [GitHub README](https://github.com/vt-vl-lab/3d-photo-inpainting)
- **Runtime conflict:** the SLIDE paper says 3D-Photo "takes several seconds per image" — [SLIDE, ar5iv 2109.01068](https://ar5iv.labs.arxiv.org/html/2109.01068). The README's 2–3 minutes likely includes mesh building and video rendering on the CPU. The two numbers disagree, so check them on your own hardware.
- **Comparison:** the paper argues that MPI "produces artifacts on sloped surfaces" and that MPI redundancy makes it "memory and storage inefficient and costly to render" — [Shih et al. 2020](https://arxiv.org/abs/2004.04727)
- **Failure cases:** single-image depth has trouble with thin and complex structures, and the method then fails to give plausible parallax — [Shih et al. 2020 PDF](https://arxiv.org/pdf/2004.04727)
- **Soft-edge criticism:** it uses hard depth layers and "does not model fine structures like hair", and it inpaints only local patches iteratively — [SLIDE, ar5iv 2109.01068](https://ar5iv.labs.arxiv.org/html/2109.01068)

### Inferences
- For the app, the code's *ideas* carry over better than the code itself: bilateral-median depth sharpening, edge linking, a ~5 px synthesis dilation toward the foreground, and context taken only from the background side. The old PyTorch 1.4 / Python 3.7 stack would need porting to run on a modern Windows GPU [미확인: not tested]. Its output is a mesh with many small inpainted patches, not 4 RGBA layers, so you would have to re-bake it per depth band.
- The model is trained on photos (COCO). How well it inpaints painting brushwork is unknown.

### Gaps
- Peak GPU memory is not documented in the README.

---

## Q4. 3D Ken Burns (Niklaus, Mai, Yang, Liu; SIGGRAPH Asia / TOG 2019)

### Takeaway
3D Ken Burns builds a point cloud from depth that is semantic-aware and refined at object boundaries. It then renders the extreme views of the camera path, and **context-aware color and depth inpainting** fills the disoccluded pixels there. Those inpainted pixels are added back into the point cloud, which extends the background geometry before the final frames are rendered.

### Cited Findings
- Its depth comes from a semantic-aware network combined with segmentation-based depth adjustment, plus a refinement network that sharpens depth at object boundaries. The image is mapped to a point cloud and rendered along the camera path — [arXiv 1909.05483](https://arxiv.org/abs/1909.05483)
- "Context-aware color and depth inpainting" fills the regions that become visible at the extreme views and so "extends the point cloud's scene geometry". It has automatic and interactive modes — [arXiv 1909.05483](https://arxiv.org/abs/1909.05483)

### Inferences
- The key idea for the app is to **extend the background before rendering**: inpaint once at the largest planned displacement, then reuse it for every in-between view. This matches the app's fixed, known fan-out maximum: precompute the fill for the fully fanned-out state.

### Gaps
- Runtime and code license were not checked this session. The repo is believed to be sniklaus/3d-ken-burns with a non-commercial license [미확인]. Details of how boundaries are segmented into separate point groups were not read beyond the abstract.

---

## Q5. Multiplane Images (MPI) and single-view MPI (Tucker & Snavely 2020; Luvizon WACV 2021; AdaMPI SIGGRAPH 2022; SMPI)

### Takeaway
An MPI is a stack of fronto-parallel RGBA planes at fixed (or adaptive) depths. A network predicts color and alpha for every plane, *including* plane content behind foreground edges, learned from multi-view, video or warp-back data. It is the representation closest to the app's "N RGBA depth layers": the app is basically a 4-plane MPI with no hidden content. Rendering is just alpha-blended textured quads, so it is GPU-friendly. But dozens of planes cost heavy overdraw and memory, and few planes cause visible slicing and sloped-surface artifacts.

### Cited Findings
- **Tucker & Snavely (CVPR 2020):** predicts an MPI from a single image, "learns to fill in content behind foreground object edges in background layers", and trains on online video with a scale-invariant view-synthesis loss — [arXiv 2004.11364](https://arxiv.org/abs/2004.11364)
- **AdaMPI (Han, Wang, Yang; SIGGRAPH 2022):** takes an image plus an off-the-shelf monocular depth map and predicts an MPI "with plane depth adjustment". It builds stereo training data from single-view collections with a "warp-back" strategy and inpaints occluded regions "with contents consistent with the background texture". Code: [github.com/yxuhan/AdaMPI](https://github.com/yxuhan/AdaMPI) — [arXiv 2205.11733](https://arxiv.org/abs/2205.11733)
- **Luvizon et al. (WACV 2021):** an "adaptive slicing algorithm" makes a variable number of planes, and a "lightweight CNN" inpaints occluded regions. It is trained with constructed masks because occluded areas have no ground truth. The inpainting targets are "typically thin margins along the contours", so the planes are very sparse — [WACV 2021 paper](https://openaccess.thecvf.com/content/WACV2021/papers/Luvizon_Adaptive_Multiplane_Image_Generation_From_a_Single_Internet_Picture_WACV_2021_paper.pdf); [arXiv 2011.13317](https://arxiv.org/abs/2011.13317)
- **MPI criticisms:** artifacts on sloped surfaces, plus redundancy that makes it memory/storage-inefficient and "costly to render" — [Shih et al. 2020](https://arxiv.org/abs/2004.04727)
- **SMPI vs SLIDE:** SLIDE reports that single-image MPI "generalizes poorly to in-the-wild images and produces blurrier views". On RE10K t=10, SMPI scores LPIPS 0.19 vs SLIDE's 0.10, and on Mannequin Challenge LPIPS 0.31 / PSNR 17.8 vs 0.18 / 20.0. Users preferred SLIDE over SMPI more than 99% of the time — [SLIDE, ar5iv 2109.01068](https://ar5iv.labs.arxiv.org/html/2109.01068)

### Inferences
- Luvizon's point that the needed fill is a **thin margin along the contours** is directly usable. With fan-out offsets of a few percent of the painting width, each back layer needs only a band behind the front layer's silhouette, as wide as the maximum relative screen shift, not a full reconstruction of the hidden object area.
- Running an MPI network offline and then merging its 32–64 planes into the app's 4 depth bands (alpha-compositing the planes in each band) is a plausible way to get hidden content for each band [미확인: not tested; merging can blur].
- Real-time on S23: 4 alpha-clipped quads is cheap. 32+ alpha-blended full-screen planes would add a lot of overdraw on a mobile GPU [미확인: no S23 benchmark found].

### Gaps
- Exact plane counts were not verified this session. From memory, Tucker & Snavely uses 32 planes and AdaMPI uses a fixed N with learned depth adjustment, likely 64 [미확인]. AdaMPI's license was not checked.

---

## Q6. Soft-layer + background inpainting (Google SLIDE, ICCV 2021): the "2-layer RGBA + inpainted background" family

### Takeaway
SLIDE is the most directly transferable design for the app. It uses **two layers**: a foreground RGBDA layer whose alpha comes from depth gradients (optionally refined by matting), and a background RGBD layer whose disoccluded region is filled by a **depth-aware** inpainting network trained to borrow from the far side. It runs in a single forward pass in about 0.07 s on a P100 (0.35 s with matting), renders in real time, and beat 3D Photo Inpainting in both metrics and user studies.

### Cited Findings
- It splits the scene into a "simple two-layer decomposition": an FG RGBDA layer and a BG RGBD layer — [SLIDE, ar5iv 2109.01068](https://ar5iv.labs.arxiv.org/html/2109.01068)
- **Soft FG visibility:** A = exp(−β‖∇D‖²) on the Sobel gradient of the MiDaS disparity, so stretched triangles at depth edges become transparent and reveal the background. A soft disocclusion map is a tanh of the max disparity difference to neighbours along horizontal and vertical scanlines, computable at low resolution — [SLIDE](https://ar5iv.labs.arxiv.org/html/2109.01068)
- **Optional matting:** U2Net saliency plus FBA matting. A′ = A·(1−(M̄−M)(1−Ŝ)) keeps hair detail while respecting depth edges — [SLIDE](https://ar5iv.labs.arxiv.org/html/2109.01068)
- **Depth-aware inpainting:** a DeepFill-style gated-conv coarse+refine network trained on Places2 with **occlusion-shaped masks around foreground objects** plus random strokes. It learns to borrow from regions with larger depth, while standard inpainters such as HiFill and DeepFill "often complete foreground objects", which is undesirable here — [SLIDE](https://ar5iv.labs.arxiv.org/html/2109.01068)
- **Runtime** (672×1008, P100): depth 0.023 s, soft layering 0.013 s, inpainting 0.037 s, total 0.07 s. With U2Net (0.069 s) and FBA matting (0.203 s), the total is 0.35 s. The two-layer representation renders in real time on modern GPUs — [SLIDE](https://ar5iv.labs.arxiv.org/html/2109.01068)
- **vs 3D-Photo:** on RE10K t=5, LPIPS 0.06 vs 0.09. On Mannequin Challenge, LPIPS 0.18 vs 0.22 and PSNR 20.0 vs 18.8. Users preferred SLIDE, especially on hair-detail images — [SLIDE](https://ar5iv.labs.arxiv.org/html/2109.01068)
- Google holds a patent on this approach: US 12,260,572 B2, "Single image 3D photography with soft-layering and depth-aware inpainting" (granted March 2025) — [USPTO gazette](https://patentsgazette.uspto.gov/week12/OG/html/1532-4/US12260572-20250325.html)

### Inferences
- Concrete lessons for the app:
  1. Each back layer's hidden region should be filled **from that layer's own (far) side only**. Mask out all nearer-layer pixels, then dilate the mask a few pixels into the foreground, as with Shih's 5 px. This stops front-object colors from bleeding in.
  2. A general-purpose inpainter (LaMa, SD inpainting) given just a hole tends to "complete the foreground object" (SLIDE's warning). Give it only the background context, and/or make the hole the region *behind* the silhouette rather than the object itself.
  3. Soft alpha from depth gradients is the principled version of the app's current soft edges plus alpha clipping. Alpha *clipping* throws away the softness, so an alpha-blend (or dithered) edge on the front layers avoids hard halos.
- SLIDE's code and weights were not found to be public [미확인]. The patent may matter for commercial use, but it is less of a concern for a course project. This is not legal advice.

### Gaps
- No public SLIDE code was confirmed. The β, γ and ρ parameter values are not given in the paper text that was retrieved.

---

## Q7. Commercial 2.5D parallax products

### Takeaway
- **Facebook 3D Photos (Kopf 2020):** fully documented. It builds an on-device LDI, inpaints it with a tiny partial-conv network, and exports a glTF mesh with a texture atlas, in about 1.1 s on an iPhone 11 Pro.
- **Google Cinematic Photos:** a mesh over depth. It hides stretching by choosing the camera path, and no inpainting is documented.
- **Apple Spatial Scenes (iOS 26)** and **Immersity AI / LeiaPix:** both say they separate foreground and background and "fill in" hidden content, but neither documents how.

### Cited Findings
- **Kopf et al. 2020, One Shot 3D Photography:** runs on device in "just a few seconds". Its mobile depth network has "an order of magnitude fewer parameters". The result is lifted to an LDI and inpainted for "color texture and structures in the parallax regions", then converted to a mesh that can be "efficiently transmitted and rendered even on low-end devices" — [arXiv 2008.12298](https://arxiv.org/abs/2008.12298)
- **Kopf 2020 details:**
  - Depth cleanup uses a 5×5 weighted median filter (σ_disp = 0.2), a disparity threshold of 0.05, and merging of components under 20 px.
  - The inpainting network, "Farbrausch", is a partial-conv U-Net converted to run directly on the LDI by BFS-gathering LDI neighbours into kernels, with silhouettes zero-padded. It has 0.37 M params (~1.9 MiB) and was found by Chameleon architecture search (about 3 days on 400 V100s).
  - Output is glTF, about 300–500 KB for a 1152×1536 input, with charts packed into one atlas. JPEG macroblock padding shrinks textures by about 40%.

  — [Kopf et al., ar5iv 2008.12298](https://ar5iv.labs.arxiv.org/html/2008.12298)
- **Kopf 2020 runtime on iPhone 11 Pro** (1152×1536): depth (at 288×384) 230 ms, depth filter 51 ms, connected components 12 ms, occluded geometry 31 ms, color inpainting 540 ms, texture chart generation 72 ms, chart padding 151 ms, meshing 11 ms. **Total 1,098 ms.** The table says "mean" while the text says "median" — [ar5iv 2008.12298](https://ar5iv.labs.arxiv.org/html/2008.12298)
- **Kopf 2020 limitations:** one depth value per pixel, so semi-transparency, fog and smoke are poorly represented. Depth degrades on out-of-distribution scenes — [ar5iv 2008.12298](https://ar5iv.labs.arxiv.org/html/2008.12298)
- **The earlier (2018) Facebook 3D Photos** used isotropic-diffusion color inpainting, which was overly smooth — [Shih et al. 2020](https://arxiv.org/abs/2004.04727)
- **Google Cinematic Photos:** see Q1. Mesh extrusion, camera-path optimization against "stretchy" artifacts, and no inpainting described — [Google Research blog](https://research.google/blog/the-technology-behind-cinematic-photos/)
- **Apple Spatial Scenes (iOS 26, 2025):**
  - Press coverage says it uses on-device computer vision on the Neural Engine to infer depth. It works on iPhone 12 and later without Apple Intelligence, and images without a clear foreground/background split are not eligible — [9to5Mac](https://9to5mac.com/2025/06/10/psa-spatial-scenes-will-work-on-any-iphone-running-ios-26/); [MacRumors](https://www.macrumors.com/how-to/ios-3d-lock-screen-effect-spatial-scenes/)
  - MacRumors calls it "generative AI". Six Colors says it partly "invents reality" — [Six Colors](https://sixcolors.com/?p=39996)
  - There is an Apple Developer Forums thread asking for a Spatial Scene API — [Apple Developer Forums 787237](https://developer.apple.com/forums/thread/787237)
  - No Apple technical document on the fill method was found [미확인].
- **Immersity AI (formerly LeiaPix):** powered by Leia's "Neural Depth Engine". In version 4.0, "Neural Depth Rendering" separates foreground and background into distinct layers, renders them individually, and "fills in previously obscured details". The method is undocumented — [Immersity 4.0 newsroom](https://immersity.ai/newsroom/immersity-4-0); [SVG News 2024](https://www.sportsvideo.org/2024/05/24/leia-inc-launches-immersity-ai-platform-adds-new-2d-to-3d-video-conversion-tool)

### Inferences
- The Kopf 2020 numbers show that **runtime** LDI inpainting is feasible on a 2019 phone in about 0.5 s. For the app, though, doing it **offline** costs nothing at runtime, since the app only needs to display precomputed RGBA textures.
- The current consumer products (Apple, Immersity) all describe the same pattern: split foreground and background, generatively fill the background, then render 2+ layers. This matches the app's architecture once background filling is added.

### Gaps
- Apple's spatial scene algorithm (number of layers, whether it inpaints or uses Gaussian splats) is undocumented. No WWDC session detail was found. The Immersity inpainting method is undocumented, and the patent search results were not linked to Leia specifically.

---

## Q8. Recent (2024–2026) single-image → layers / 3D methods

### Takeaway
There are two practical directions for an *offline* pipeline on a consumer GPU:
1. **Generative RGBA layer decomposition** (Qwen-Image-Layered, Dec 2025), which outputs N RGBA layers with occluded parts hallucinated by diffusion. It fits the app's format, but its layers are *semantic*, not depth bands.
2. **Mask + diffusion/LaMa inpainting per depth layer**, i.e. a modern SLIDE-style approach.

Gaussian-splat world generators (WonderWorld, etc.) also fill occlusions with layered generation. They are heavier, output splats rather than RGBA layers, and are more than the app needs.

### Cited Findings
- **Qwen-Image-Layered (arXiv 2512.15603, Dec 2025):**
  - An end-to-end diffusion model that decomposes one RGB image into multiple semantically disentangled RGBA layers. Its components are an RGBA-VAE, a VLD-MMDiT, and multi-stage training — [arXiv 2512.15603](https://arxiv.org/abs/2512.15603)
  - The layer count is variable, with a usage-example default of 4. It is available through diffusers (`QwenImageLayeredPipeline`) and in Gradio apps that export pptx/zip/psd — [GitHub QwenLM/Qwen-Image-Layered](https://github.com/QwenLM/Qwen-Image-Layered); [HF model card](https://huggingface.co/qwen/qwen-image-layered)
  - The repo advises that the text prompt should describe the whole image, "including elements that may be partially occluded". It is "not designed to control the semantic content of individual layers explicitly" — [GitHub](https://github.com/QwenLM/Qwen-Image-Layered)
  - A tutorial says strong shadows produce more visible artifacts — [DataCamp tutorial](https://www.datacamp.com/tutorial/qwen-image-layered)
  - There is a ComfyUI workflow — [Comfy docs](https://docs.comfy.org/tutorials/image/qwen/qwen-image-layered)
- **WonderWorld (Yu et al., 2024):**
  - Generates each scene in under 10 s on a single A6000 (latest arXiv version), using Fast LAyered Gaussian Surfels (FLAGS).
  - A "single-view layer generation method" uncovers and inpaints occluded regions, avoiding slow progressive multi-view generation.
  - Guided depth diffusion allows partial conditioning of the depth.

  — [arXiv 2406.09394](https://arxiv.org/abs/2406.09394); [HTML v4](https://arxiv.org/html/2406.09394v4)

### Inferences
- **Qwen-Image-Layered for the app:** a 20B-class MMDiT base (Qwen-Image) likely needs a 24 GB+ GPU, or offloading/quantization [미확인: VRAM not verified]. Its layers are semantic (objects, text, background), so they would have to be re-sorted by mean depth from Depth Anything to form 4 depth bands. Its big advantage is that each layer is *already completed behind occluders*, which is exactly what the app is missing.
- **WonderWorld-style splats:** these would need a Gaussian-splat renderer in Unity URP on mobile. That is possible with third-party packages but heavy and off-format for the app [미확인].
- **Cheapest robust offline option** (inferred from SLIDE + Shih): for each depth band k = far…near, set the hole H_k to the union of the masks of bands nearer than k, dilated by about 5–15 px, and clipped to a margin no wider than the maximum fan-out shift. Inpaint band k's RGBA over H_k using only band ≤k context, with LaMa or an SD/Flux inpainting model. Then set alpha = 1 in the filled area so the band becomes opaque behind its front neighbours.

### Gaps
- The following were **not researched this session** due to the call budget: Flash3D (2024, feed-forward multi-Gaussian per pixel), LucidDreamer (2023), WonderJourney (2023), LayerDiffuse (2024; generates transparent layers rather than decomposing an existing image), and the Gen3C / ViewCrafter-type video-diffusion NVS methods. Their occlusion handling, VRAM and licenses are unverified.
- Qwen-Image-Layered's license, VRAM needs and quality on paintings were not checked.

---

## Q9. Typical artifacts per family and mitigations

### Takeaway
- **Stretching / rubber-sheet** comes from a connected mesh across depth edges. Fix it by tearing the mesh at edges, or by soft-alpha fading of stretched triangles.
- **Holes or gaps** come from torn meshes or empty layers. Fix them by inpainting the hidden band.
- **Ghosting or foreground bleeding into the background** happens when the depth edge and color edge are misaligned, or when the inpainter takes foreground context. Fix it by dilating the synthesis region toward the foreground, taking context only from the background side, and using depth-aware inpainting.
- **Halos at hair or thin structures** come from hard depth layers. Fix them with matting / soft alpha.
- **Blurry or over-smooth fill** comes from diffusion inpainting or few-plane MPIs. Fix it with learned or generative inpainting.
- **Slicing / sloped-surface artifacts** come from MPI's fronto-parallel planes.

### Cited Findings
- Gaps vs stretched content are the two failure modes of naive warping — [Shih et al. 2020](https://arxiv.org/abs/2004.04727). The "stretchy artifacts" of mesh extrusion are discussed in the [Google Cinematic blog](https://research.google/blog/the-technology-behind-cinematic-photos/)
- **Misalignment fix:** dilate the synthesis region by 5 px near the depth edge, with the context region eroded correspondingly — [Shih et al. 2020 PDF](https://arxiv.org/pdf/2004.04727)
- **Depth cleanup** before layering, to align depth edges to color edges and remove spurious edges:
  - Bilateral median filter (7×7) — [Shih](https://arxiv.org/pdf/2004.04727)
  - Weighted median (5×5) and merging of components under 20 px — [Kopf](https://ar5iv.labs.arxiv.org/html/2008.12298)
- **Soft visibility** makes stretched triangles transparent. Matting preserves hair. Depth-aware inpainting avoids completing the foreground object into the hole — [SLIDE](https://ar5iv.labs.arxiv.org/html/2109.01068)
- **Isotropic diffusion fill** is overly smooth and cannot extrapolate texture — [Shih et al. 2020](https://arxiv.org/abs/2004.04727)
- **MPI** shows artifacts on sloped surfaces and is costly to render — [Shih et al. 2020](https://arxiv.org/abs/2004.04727). Single-image MPI is blurrier on in-the-wild images — [SLIDE](https://ar5iv.labs.arxiv.org/html/2109.01068)
- **Thin and complex structures** break single-image depth, and therefore parallax — [Shih](https://arxiv.org/pdf/2004.04727). So do semi-transparency, fog and smoke — [Kopf](https://ar5iv.labs.arxiv.org/html/2008.12298)
- **Shadows** cause artifacts in Qwen-Image-Layered decomposition — [DataCamp](https://www.datacamp.com/tutorial/qwen-image-layered)
- **Camera or motion limiting** keeps artifacts in the background regions — [Google Cinematic blog](https://research.google/blog/the-technology-behind-cinematic-photos/)

### Inferences (mapping to the app's symptoms)
- **"The back layer shows the front object's colors":** the back layer's texture was not inpainted, or its mask overlaps the front object's band because depth and color edges are misaligned. Fix it by **removing nearer-band pixels plus an N px dilation** from the back layer, then inpainting that region from background-only context.
- **"The back layer is empty where the front object was":** this is expected without inpainting. Fill a band at least as wide as the maximum relative screen shift between adjacent layers during the fan-out.
- **"The smooth filler surface looks stretched":** this is the rubber-sheet artifact. Once every band, including the farthest, has its hidden region inpainted (making the farthest layer fully opaque and complete), the filler mesh is unnecessary. Alternatively, texture it with an inpainted "clean plate" of the painting with all foreground removed, instead of the original painting.
- **Alpha clipping** produces hard, aliased edges. Switch the front layers to alpha blending (sorted back-to-front, which is easy with 4 quads), or use a slightly feathered alpha, to avoid halos. On mobile this costs about 4 layers of overdraw, which should be fine on an S23 [미확인: not benchmarked].
- **Painting-specific:** all learned inpainters above were trained on photos (COCO, Places2, RE10K). Brushwork and texture continuity in paintings may favour generative diffusion inpainting (SD/Flux/Qwen) over LaMa/DeepFill [미확인: no painting-specific benchmark found].

### Gaps
- No quantitative study comparing these artifacts on paintings or artworks was found.
- No mobile (Snapdragon 8 Gen 2 / S23) rendering benchmarks were found for MPI vs mesh vs few-layer approaches.
