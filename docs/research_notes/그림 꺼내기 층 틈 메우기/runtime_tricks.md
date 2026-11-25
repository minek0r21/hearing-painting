# Cheap runtime tricks for hiding disocclusion gaps in separated 2.5D layers (Unity 6 URP, Galaxy S23)

Context: 4 masked-quad layers (URP Unlit, Alpha Clipping, 768px) plus a smooth continuous depth "filler" mesh behind them. Long-press fans the layers toward the viewer (up to 2.5x scale). Problems: back layers show holes or leftover foreground colors, and the filler mesh looks like a stretched "rubber sheet".

Notation: [Inference] marks my own engineering reasoning or cost estimates that no source states directly. "정확하지 않을 수 있음" marks claims I am unsure about.

---

## Q1. Edge extrusion / dilation / push-pull / mip-based hole filling of back layers, done once at load time (CPU or GPU) — how, and at what cost for 768px?

### Takeaway
Pull-push (Gortler et al. 1996, the Lumigraph) is the standard cheap, non-AI way to fill masked regions with smooth colors from nearby valid pixels. It is a mip-pyramid algorithm that runs in linear time. A 2009 GPU version took 0.60 ms for a 1024x1024 RGBA16F image on a desktop GPU. Facebook's first shipped 3D Photos used plain iterative isotropic diffusion for color, with no AI, so a smooth fill of the revealed band is good enough in production. For 768px textures it is cheap enough to run once per layer at load, on the GPU (Blit or compute) or the CPU (C#, ideally Burst).

### Cited Findings
- Pull-push is "a well-known and very efficient pyramid algorithm for the interpolation of scattered data", used for inpainting and image post-processing. It originates in Gortler et al. 1996 (Lumigraph). Lefebvre et al. 2005 used a GPU version to inpaint gaps in texture maps. Kraus & Strengert 2007 used it to disocclude pixels in their depth-of-field algorithm. — [Kraus 2009, "The Pull-Push Algorithm Revisited" (GRAPP)](https://www.cs.cit.tum.de/fileadmin/w00cfj/cg/Research/Publications/2009/Pull-Push_Algorithm/grapp09.pdf)
- Algorithm structure. In the pull phase, build a pyramid where level r+1 is half the size of level r. Each coarser pixel stores a weighted average of data values x with weights w (w=0 for holes, 1 for valid pixels). Weights are clamped to ≤1. In the push phase, recompute the levels from coarse to fine and blend each fine pixel with the upsampled coarse value, using its own weight w and the coarse value with (1−w). — [Kraus 2009](https://www.cs.cit.tum.de/fileadmin/w00cfj/cg/Research/Publications/2009/Pull-Push_Algorithm/grapp09.pdf)
- Clamping the weights is "crucial for a smooth interpolation in general", not only for limiting the influence of point clusters. — [Kraus 2009](https://www.cs.cit.tum.de/fileadmin/w00cfj/cg/Research/Publications/2009/Pull-Push_Algorithm/grapp09.pdf)
- GPU implementation:
  - Store the weights in the A channel and the pre-multiplied (weighted) color in RGB of an RGBA texture.
  - The push blend can then be done with ordinary alpha blending.
  - Each coarse pixel needs only 4 texture lookups in the pull phase, and each fine pixel needs 1 lookup in the push phase (using bilinear-filter tricks).
  - The method is bandwidth-bound: "0.60 ms for a 1024×1024 16-bit floating-point RGBA image on a NVIDIA Quadro FX 5800".
  - Their simplified "w/o weight" variant gave results very similar to the original and is easier to run on GPUs.
  — [Kraus 2009](https://www.cs.cit.tum.de/fileadmin/w00cfj/cg/Research/Publications/2009/Pull-Push_Algorithm/grapp09.pdf)
- Pull filter used in the paper's 1D examples: (1/3, 1, 1, 1/3), with the maximum normalized to 1. The alternative (1/8, 3/8, 3/8, 1/8) never needs clamping but "does not provide a smooth interpolation". — [Kraus 2009](https://www.cs.cit.tum.de/fileadmin/w00cfj/cg/Research/Publications/2009/Pull-Push_Algorithm/grapp09.pdf)
- Mip-style description: downsample with mask-based weights, then upsample and blend with the finer levels. It also handles fractional (soft) masks. — [arXiv 2007.10093 appendix (search-snippet level only)](https://arxiv.org/pdf/2007.10093)
- Point rendering uses the same pyramid: Grossman & Dally, Pintus et al. and Marroquim et al. draw points and then build an image pyramid to fill the gaps. — [Schütz et al., arXiv 2104.07526 (search-snippet level)](https://arxiv.org/pdf/2104.07526)
- Jump Flooding (JFA, Rong & Tan 2006) computes Voronoi diagrams and distance transforms. It runs log2(N) passes, each sampling 3x3 neighbors at a step size that halves every pass. It is approximate, but the errors are few and small. To dilate, seed JFA with valid texels, then copy each invalid texel's color from its nearest seed. — [Wikipedia: Jump flooding](https://www.wikipedia.org/wiki/Jump_flooding_algorithm); [Demofox blog](https://blog.demofox.org/2016/02/29/fast-voronoi-diagrams-and-distance-dield-textures-on-the-gpu-with-the-jump-flooding-algorithm/); [Rong & Tan i3D 2006](https://www.comp.nus.edu.sg/~tants/jfa/i3d06.pdf)
- Unity example of JFA as a compute shader (3D variant): — [przemyslawzaworski/Unity3D-CG-programming JumpFlooding3D.compute](https://www.github.com/przemyslawzaworski/Unity3D-CG-programming/blob/master/JumpFlooding3D.compute)
- Unity port of Ryan Brucks' UV dilation shader (`Internal/Dilate`):
  - Each empty texel searches up to `_MaxSteps` texels in 8 directions and extrapolates from the hit texel and a second sample farther out. This is "edge pixel extrusion".
  - Store the mask in alpha and treat texels with alpha<1 as invalid. Otherwise bilinear bleed creates white spots.
  - bgolus judged the result "Better, but not right"; artifacts remain.
  - Cost is up to MaxSteps×8 samples per texel. The thread gives no timings.
  — [Unity Discussions thread](https://discussions.unity.com/t/ryan-brucks-improved-uv-dilation-unity-implementation/827859); [original shaderbits article](https://shaderbits.com/blog/uv-dilation)
- Facebook 3D Photos, first production version: "we iteratively extend the backside discontinuities into the occluded region using a diffusion-based inpainting algorithm … Iterative isotropic diffusion inpaints colors into the occluded regions. This algorithm is very fast and produces predictable, albeit smooth, results." — [Kopf et al., "Practical 3D Photography" (CVPR-W 2019)](https://johanneskopf.de/publications/photo3d_practical/Practical_3D_Photography.pdf)
- Facebook marks foreground pixels "close to a discontinuity" as possibly containing mixed colors and re-inpaints them along with the occluded pixels. They also pad charts using "isotropic diffusion at step edges" so mipmapping does not bleed. — [Kopf et al., "One Shot 3D Photography" (SIGGRAPH 2020), arXiv 2008.12298](https://arxiv.org/pdf/2008.12298)

### Inferences
- **Root cause of "foreground colors left in back layers"** [Inference]: the back-layer texture probably still contains original-image pixels where the nearer layer was, or mixed pixels along the mask edge. Facebook's fix is the template: treat everything covered by any nearer layer, plus a 2–4 px band around its edge (the mixed pixels), as invalid (w=0) before filling. Then fill the invalid pixels from the remaining valid pixels of that layer only.
- **The back-layer alpha mask must grow too** [Inference]: after filling colors, expand the back layer's own alpha mask (or set it to 1 everywhere it is occluded) by at least the maximum screen-space parallax that the fan-out reveals. Otherwise the clean colors exist but are clipped away. For the farthest layer the simplest choice is a fully opaque, filled "clean plate" of the whole painting.
- **Simplest GPU version in Unity: the "premultiplied mip fill"** [Inference, based on the pull-push structure above]:
  1. Make a texture with rgb = color·w, a = w (w=0 in holes). Use RGBAHalf or RGBAFloat, because 8-bit loses precision when w is tiny at coarse mips.
  2. Generate mipmaps. `Texture2D.Apply(true)` or `RenderTexture.GenerateMips()` use a box filter, which is a pull phase without clamping.
  3. Run one fragment pass (Graphics.Blit into a RenderTexture). For each texel, walk from LOD 0 upward with `SAMPLE_TEXTURE2D_LOD` until `a` passes a threshold (for example 0.5–0.9), then output rgb/a. For a smoother result, blend coarse to fine: `c = lerp(upsampled_coarse, fine/a_fine, saturate(a_fine))`. This is the push phase. A 768px texture has 10 levels, so at most ~10 lookups per texel.
  4. Read the result back once (`AsyncGPUReadback` or `ReadPixels`), or keep it as a RenderTexture and assign it to the material.
  Expected cost on S23: well under a few ms per layer. 정확하지 않을 수 있음; this extrapolates from the 0.6 ms desktop figure and has not been measured.
- **CPU (C#) version** [Inference]: a 768² image has ~590k pixels, and the whole pyramid adds only ~1/3 more (geometric series). Pull plus push is roughly 4 reads per coarse pixel plus 1–4 per fine pixel, a few million simple float operations per layer. Expected time on an S23: tens of ms with plain managed loops over `Color[]`/`NativeArray`, and a few ms with Burst + Jobs. 정확하지 않을 수 있음 (not measured). Either way it runs once at load, so it is acceptable. CPU avoids GPU readback and format issues, so it is the lower-risk choice for a one-day implementation.
- **Which fill to choose** [Inference]:
  - Pull-push / mip fill gives a smooth, blurry fill, the same character as Facebook's diffusion.
  - JFA / nearest-color extrusion keeps sharper colors but produces streaks, the classic "smear" look.
  - Brute-force 8-direction extrusion is easiest to write but is O(MaxSteps) per texel and leaves visible streak artifacts.
  - For a painting, pull-push followed by a light blur of the filled region tends to read as "out-of-focus background", which looks more natural than streaks. This is a subjective judgment.

### Gaps
- No measured timings for pull-push or JFA on Adreno/Mali mobile GPUs or for Unity C# at 768px were found. The numbers above are estimates.
- No ready-made Unity URP pull-push package was found. The implementation has to follow the paper and the steps above.
- I could not verify exactly how Unity's mip generator weights texels (box filter is assumed) or how it behaves for premultiplied data in RGBAHalf. Check this on the device.

---

## Q2. Depth-displaced meshes: tear at depth edges vs. stitch ("rubber sheet"), discarding stretched triangles, and filling with a background layer

### Takeaway
All serious 3D-photo systems cut the mesh at depth discontinuities rather than keep one continuous sheet. They then extend background geometry behind the cut and color it with an inpainted texture. Fehn-style depth smoothing removes holes, but it does so by creating exactly the geometric "rubber sheet" distortion. Cheap runtime options are: (a) discard or fade triangles or fragments whose depth gradient or view-angle is too steep, revealing a filled clean-plate layer behind; (b) keep the filler mesh but texture it with the pull-push-filled background instead of the original image, so stretched areas at least show background colors.

### Cited Findings
- Fehn (2004) pre-smooths the depth map with a Gaussian filter to remove disocclusions, "with the cost of slightly geometric distortions". Smoothing sharp discontinuities shrinks the holes, but the whole depth map is changed. This motivated later asymmetric or edge-local smoothing filters that change only the areas around holes. — [Secondary description in PMC5391110 (depth preprocessing, PLoS ONE 2017)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5391110/); [EURASIP JIVP 2013 hole-filling paper](https://link.springer.com/10.1186/1687-5281-2013-9)
- DIBR hole-filling families include depth-map preprocessing (smoothing), interpolation/extrapolation, and image completion. Image completion splits into statistical, PDE/diffusion-based, and exemplar/patch-based methods. — [EURASIP JIVP 2013](https://link.springer.com/content/pdf/10.1186/1687-5281-2013-9.pdf); survey: [Habigt, "Hole-Filling Algorithms for DIBR" (TUM dissertation 2020)](https://mediatum.ub.tum.de/doc/1542274/document.pdf); [Atapour-Abarghouei & Breckon survey (Durham)](https://durham-repository.worktribe.com/OutputFile/1339654)
- Naive depth warping either leaves holes or stretches content at disocclusions. — [Shih et al., "3D Photography using Context-aware Layered Depth Inpainting" (CVPR 2020)](https://arxiv.org/pdf/2004.04727)
- Facebook "One Shot 3D Photography" pipeline (non-learned parts):
  - Depth is first cleaned with a 5×5 weighted median filter so that "washed-out" discontinuities become step edges.
  - Pixels with a neighbor more than τ_disp = 0.05 disparity away count as edge pixels.
  - Small components (<20 px) are merged into foreground or background.
  - The LDI connects pixels to their neighbors "except across discontinuities with a disparity difference of more than τ_disp".
  - Background geometry is then grown behind the foreground for 50 iterations, and new pixels take the average depth of their neighbors.
  - Timings on iPhone 11 Pro: layer generation 94 ms, color inpainting (a network) 540 ms, meshing 234 ms, total 1,098 ms.
  — [Kopf et al. 2020, arXiv 2008.12298](https://arxiv.org/pdf/2008.12298)
- Facebook: "To minimize holes appearing in the model we create a frame around the model and constrain the viewing angles." — [Kopf et al. 2019, Practical 3D Photography](https://johanneskopf.de/publications/photo3d_practical/Practical_3D_Photography.pdf)
- Triangle culling by depth difference:
  - Compute the depth difference between a triangle's neighboring vertices and discard the triangle if it exceeds a threshold.
  - A geometry-shader variant marks vertices next to a discontinuity as invalid, and also drops triangles seen at too oblique an angle.
  - SceneScape (2023) finds discontinuities with a Sobel filter on depth (threshold 0.3) and also uses a normal-vs-camera test to remove stretched triangles.
  - The ComfyUI DA3 mesh node exposes a `discontinuity_threshold` parameter for the same purpose.
  — [SceneScape arXiv 2302.01133](https://arxiv.org/pdf/2302.01133); [USPTO 10467805 (laser-scan rendering)](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10467805); [ComfyUI DA3GeometryToMesh docs](https://docs.comfy.org/built-in-nodes/DA3GeometryToMesh). These details come from search summaries and I did not read the full documents; 정확하지 않을 수 있음.
- An alternative to discarding is to split a triangle that crosses a depth edge into a foreground part and a background part. — [USPTO 11050994 (VR parallax correction), search-summary level](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11050994)
- Hedman & Kopf's earlier LDI growth caused clutter at T-junctions (where 3 depths meet). Kopf 2020 fixed this by limiting growth of mid-ground discontinuity curves to the perpendicular lines at their end points. — [Kopf et al. 2020](https://arxiv.org/pdf/2008.12298)

### Inferences
- **The rubber sheet is Fehn's trade-off** [Inference]: the "very smooth continuous depth mesh" is effectively Gaussian-smoothed depth. It never leaves a hole, but it pays with stretching that grows with separation. It cannot look right on its own. It must either be textured with background-only colors or be replaced or covered at steep regions.
- **Cheap fix A, re-texture the filler mesh** [Inference, likely the biggest gain per effort]: give the filler mesh the pull-push-filled "clean plate" of the farthest layer (or a heavily blurred version of it) instead of the original painting. Its stretched triangles then smear background colors, not foreground colors. Stretched low-frequency color is much less noticeable than stretched edges.
- **Cheap fix B, fade stretched regions in the fragment shader** [Inference]: in the filler mesh's URP shader, measure stretch per fragment. One way is the ratio of world-space to UV-space derivatives, `length(ddx(positionWS))/length(ddx(uv))` (and the same for ddy). Another is `1 - abs(dot(normalWS, viewDirWS))`. As stretch grows, lerp toward a blurred or darkened version of the clean plate, or toward a fog color. With Alpha Clipping, clip above a threshold and let a flat back plane show through. Cost is a few ALU ops per pixel, which is negligible.
- **Cheap fix C, tear at build time** [Inference]: when building the filler mesh from the depth map in C#, skip triangles whose max vertex depth difference exceeds a threshold, similar to Facebook's τ_disp = 0.05 in normalized disparity. Behind the torn mesh, put the farthest layer as a filled, opaque quad. This turns rubber sheets into holes that the clean plate fills. It only works if the clean plate's colors are good (Q1).
- In this layered setup, the quads already act like the LDI layers in Facebook's method. The filler mesh is then optional. A filled, fully opaque farthest layer plus filled, alpha-expanded middle layers may make the filler mesh unnecessary. Test both on the device.

### Gaps
- I found no public Unity/URP sample that does stretched-triangle culling for depth-photo meshes. The shader logic above is my own suggestion.
- The exact thresholds from SceneScape and the patents are only at search-summary level.

---

## Q3. Soft edges, feathering, dithering, depth-aware blur, fog/vignette/darkening, limiting separation, DOF blur

### Takeaway
Production 2.5D tools hide artifacts mainly by limiting how much parallax is shown and by softening what remains. Facebook used a frame plus limited viewing angles. DepthFlow recommends intermediate "isometric" values against stretching. Apple's spatial scenes keep content behind the window plane. Feathered alpha edges, a little blur on revealed or back regions, and darkening (a fake contact shadow) are cheap shader-side additions.

### Cited Findings
- DepthFlow (open-source depth-parallax shader):
  - Larger camera offsets "increase the 'incident' angle at the opposite sides, creating stretchy regions".
  - The `isometric` parameter goes from full perspective (0) to flat (1), and "intermediate values are recommended to mitigate stretchy regions".
  - `height` acts as a global parallax intensity scalar.
  - `steady` sets the depth plane that stays fixed (0 keeps the far background static).
  - Low ray-march `quality` creates a "cutout" effect where layers do not blend.
  — [DepthFlow docs: Camera](https://depth.tremeschin.com/docs/camera/); [repo](https://github.com/BrokenSource/DepthFlow)
- Facebook 3D Photos: a frame around the model plus constrained viewing angles, to minimize visible holes. — [Kopf et al. 2019](https://johanneskopf.de/publications/photo3d_practical/Practical_3D_Photography.pdf)
- Apple visionOS 26 spatial scenes:
  - Content sits behind the plane of the photo window, unlike spatial photos.
  - Apple warns about visual artifacts.
  - Hallucinated details get worse the further the view moves from the original perspective.
  - Scenes struggle when subject and background are not clearly distinct.
  — [Apple support: View spatial scenes](https://support.apple.com/en-am/124145); [UploadVR on SHARP](https://uploadvr.com/apple-sharp-open-source-on-device-gaussian-splatting); [RealityKit ImagePresentationComponent docs](https://developer.apple.com/documentation/realitykit/imagepresentationcomponent/spatial3dimage.md). Apple's actual edge handling is not public, and their method uses AI.
- Depth of field and disocclusion: Kraus & Strengert's pyramidal DOF rendering uses pull-push to disocclude pixels, so blur and hole-filling are closely related operations. — [Kraus 2009 (related-work section)](https://www.cs.cit.tum.de/fileadmin/w00cfj/cg/Research/Publications/2009/Pull-Push_Algorithm/grapp09.pdf)

### Inferences (implementation notes for URP; none of these are from a single cited source)
- **Feathered or soft edges instead of hard Alpha Clipping**:
  - Switch the layer material to Surface Type = Transparent, Blending = Alpha, and soften the mask at load. A 2–4 px Gaussian blur of the alpha channel, plus a slight erosion of the front-layer mask, removes the halo of background color around foreground objects.
  - There are only 4 layers, sorted strictly by distance, so transparency sorting is trivial.
  - Cost: some overdraw of 4 full-screen-ish quads, which is fine on an S23.
- **Dithered alpha / alpha-to-coverage**: keeps the opaque/alpha-clip path with fewer sorting issues, but noisy dithering may be visible on a painting without TAA. URP has an "Alpha To Mask" option on some shaders when MSAA is on; whether Unity 6 URP Unlit exposes it is unverified (정확하지 않을 수 있음). Soft transparency is the simpler path.
- **Contact shadow / darkening of revealed regions**: render a blurred, darkened, offset copy of each front layer's alpha onto the layer behind it, like a drop shadow. Pop-up books and diorama-style 2.5D animations read as natural largely because of these shadows. The darkening also hides the low-detail filled region directly behind each object, which is exactly where disocclusion appears. Cost: one extra quad per layer using the same texture (alpha only, tinted black, blurred via a low mip level such as `SAMPLE_TEXTURE2D_LOD(tex, s, uv, 3)`).
- **DOF / blur on back layers**: sample back layers at mip bias +1…+2 (or use pre-blurred copies) while the fan-out is active. Blur hides the smoothness of pull-push fills and stretching. Animate the bias with the long-press progress.
- **Fog / vignette**: lerp farther layers slightly toward a fog or background tone. Vignetting the frame edges hides the border regions where parallax reveals off-canvas areas.
- **Limit separation**:
  - The 2.5x scale and full fan-out distance are the main drivers of how much area is revealed.
  - Clamping the maximum separation, or easing it (most of the "pop" from the first 30–50% of travel), reduces gap size roughly linearly.
  - Keep the farthest layer fixed, which is already done, like DepthFlow's `steady`.
- **"Dolly-along-view-ray" fan-out**: if each layer moves toward the camera along the camera-to-layer ray and is scaled so its projected size stays constant (s = d_new / d_old, distances measured from the camera), there is zero disocclusion from the current viewpoint. Gaps appear only when the phone/AR viewpoint moves off-axis. Then add only a small amount of extra "pop" scale beyond that. The current setup (nearer layers move farther and scale up to 2.5x) may be over-scaling or moving layers off-axis, which reveals more of the back layers than necessary. 정확하지 않을 수 있음: this depends on the exact current transform code, which I have not seen.

### Gaps
- No source quantifies how much blur or darkening is needed perceptually. Tune it on the device.
- I could not find official documentation of Apple's or DepthFlow's exact edge/inpaint algorithms.

---

## Q4. How existing apps, tools and shaders handle it

### Takeaway
There are three tiers:
- Simple shader parallax (Depthy, three.js depth portraits, Shadertoy-style UV displacement) just accepts stretching and keeps displacement small.
- Professional 2.5D (After Effects parallax) uses manually cloned/patched background plates for each layer.
- 3D-photo systems (Facebook, Apple) cut the mesh at discontinuities and inpaint the revealed background. Facebook started with non-AI diffusion and later moved to a mobile CNN.

### Cited Findings
- **Depthy**: displays Google Camera Lens Blur photos (image + depth) with a 3D parallax effect and exports animated GIFs. MIT license, by Rafał Lindemann. I did not inspect how it handles edges in the shader source. — [github.com/bgnq/depthy (fork of panrafal/depthy)](https://github.com/bgnq/depthy)
- **three.js depth portrait**: the vertex shader reads the depth map and pushes the plane forward or backward. This is plain displacement, so it stretches at edges. — [threejs-depth-portrait docs](https://flavioow.github.io/threejs-depth-portrait/docs/en/guide/creating-the-parallax-effect.html)
- **Unity UV-offset parallax using a depth texture** (tutorial): — [Alan Zucconi, Parallax Shaders & Depth Maps](https://www.alanzucconi.com/?p=10453)
- **DepthFlow**: ray-marching GLSL shader that claims "artifact-free edges and seamless loops" but does not explain how. It exposes isometric/height/steady to control stretching (see Q3). — [BrokenSource/DepthFlow](https://github.com/BrokenSource/DepthFlow)
- **After Effects 2.5D parallax workflow**:
  - Isolate foreground objects in Photoshop and "provide sufficient elements … to create a convincing background" using the Patch, Clone Stamp or Healing Brush tools.
  - Each layer gets a mask, and the clone stamp erases traces of the layers above it.
  - Then animate with a 3D camera.
  — [Adobe: Animate a picture](https://www.adobe.com/learn/after-effects/web/animate-picture); [Tuts+: realistic camera move with parallax](https://photography.tutsplus.com/tutorials/create-a-realistic-camera-move-with-parallax--ae-453); [Videomaker 2.5D tutorial](https://www.videomaker.com/article/f2/13742-tutorial-25d-animation)
- **Facebook 3D Photos**:
  - Layered depth image converted to a lightweight mesh.
  - 2019 version: heuristic discontinuity detection plus isotropic diffusion color inpainting, 1–2 s end-to-end on a phone.
  - 2020 version: a mobile inpainting CNN running on the LDI.
  - Used "over 100 million times".
  — [Kopf 2019](https://johanneskopf.de/publications/photo3d_practical/Practical_3D_Photography.pdf); [Kopf 2020](https://arxiv.org/pdf/2008.12298); [Shih 2020](https://arxiv.org/pdf/2004.04727)
- **Apple spatial scenes**: AI-generated multiple perspectives, kept behind the window plane, with acknowledged artifacts. — [Apple support](https://support.apple.com/en-am/124145)

### Inferences
- The After Effects "clone stamp per layer" step is the manual equivalent of what this app needs: a filled background plate behind every layer. At runtime without AI, pull-push or diffusion (Q1) is the automatic, lower-quality substitute.
- Live2D-style layering (not researched in depth here) relies on artists painting the hidden parts of each layer ahead of time. It does not solve the problem at runtime.

### Gaps
- I did not read Depthy's or DepthFlow's shader source, so their exact edge handling is unverified.
- I did not research Live2D's documentation.

---

## Q5. What is feasible in one day in Unity 6 URP, ranked by visual gain vs. effort

### Takeaway
[Inference; the ranking is my judgment based on the findings above, not on a source.] Clean up and fill the back layers first: remove the foreground colors, fill with pull-push, and expand each back layer's alpha. Then make the filler mesh show only background-filled, blurred colors. Then add soft edges and contact shadows, and limit or retune the separation. Mesh tearing and JFA are optional.

### Cited Findings
- Facebook's shipped non-AI pipeline (diffusion fill, heuristic edges, limited viewing angles) shows that smooth fills plus limited parallax are acceptable in production. — [Kopf 2019](https://johanneskopf.de/publications/photo3d_practical/Practical_3D_Photography.pdf)
- Pull-push is linear-time and runs in sub-millisecond time on a desktop GPU at 1024². — [Kraus 2009](https://www.cs.cit.tum.de/fileadmin/w00cfj/cg/Research/Publications/2009/Pull-Push_Algorithm/grapp09.pdf)

### Inferences — ranked list (gain / effort / risk)
1. **Back-layer clean plates via load-time pull-push (C#)** — gain: very high (removes leftover foreground colors and holes); effort: ~2–4 h; risk: low.
   - For layer i: w = 0 where any nearer layer's mask > 0, dilated by 2–4 px. Otherwise w = the layer's own valid pixels from the original image.
   - Pull-push into an RGBA buffer, then `Texture2D.SetPixels` + `Apply`.
   - Also expand layer i's alpha over the region covered by nearer layers, plus a margin equal to the maximum parallax.
   - Make the farthest layer fully opaque and filled.
2. **Re-texture or replace the filler mesh** — gain: high (rubber-sheet smears become background colors); effort: ~0.5–1 h; risk: low.
   - Use the filled farthest-layer texture, with mip bias +2 for blur.
   - Consider removing the filler mesh entirely if (1) already covers everything.
3. **Limit or retune the fan-out** — gain: medium-high; effort: ~0.5 h; risk: very low.
   - Scale each layer to keep its projected size (dolly along the view ray) plus only a small extra pop.
   - Cap the 2.5x scale and separation, and ease the motion curve.
4. **Soft (feathered) alpha + slight erosion of front masks** — gain: medium (removes jaggy edges and color halos); effort: ~1 h; risk: low (sorting with 4 layers is easy).
5. **Contact shadow / darkening under each front layer** — gain: medium (makes depth readable and hides the bland fill directly behind objects); effort: ~1 h; risk: low.
6. **DOF-like blur of back layers + slight fog during fan-out** — gain: medium; effort: ~0.5 h (mip bias / lerp in the shader); risk: low.
7. **Stretch-aware fade in the filler-mesh shader** (derivative or normal-angle based) — gain: medium if the filler mesh is kept; effort: ~1 h; risk: medium (threshold tuning).
8. **Build-time mesh tearing at depth edges** (τ on depth difference) — gain: medium; effort: ~1–2 h; risk: medium (needs good clean plates behind; cracks may show).
9. **GPU mip-fill / JFA compute shader** — gain: same as (1) but faster. The only reason to do it is if the CPU load time is too slow. Effort: 2–4 h; risk: medium (RenderTexture formats, readback on Android/Vulkan).
- Items 1–6 together plausibly fit in one working day (정확하지 않을 수 있음; depends on the existing code structure).

### Gaps
- No on-device measurements exist yet. Profile on the S23, especially the C# pull-push time for 4×768² layers.
