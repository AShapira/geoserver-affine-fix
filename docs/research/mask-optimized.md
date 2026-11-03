# Mask processing optimization

Implementation incorporated into this repository’s `main` from `codex/mask-performance`, based on the correctness-validated combined candidate [`c9aff37`](https://github.com/AShapira/geoserver-affine-fix/commit/c9aff37f393feb0638add12a2ce63d67f0f00d84). **Experimental; not accepted or shipped upstream.**

## What changed

- NoData validity is calculated lazily into a byte image using direct buffer writes. A primitive range test replaces the generic range lookup, boxed values, temporary band images and band reduction. A pixel remains valid when any source band is valid; NaN and endpoint inclusivity are preserved.
- Nearest-neighbor binary affine sampling reads packed BYTE/USHORT/INT bits directly when there is no additional ROI or NoData. Other interpolation and validity paths retain their existing implementation.
- A synthetic footprint mask is omitted only if there is no NoData or existing ROI and every corner of the full request maps at least one source pixel inside the reader-selected image. Boundary tiles keep their masks; RGBA keeps its intrinsic alpha.
- Existing ROI and NoData masks still intersect. Redundant intersection with a full-image rectangle is avoided.

The code keeps the combined candidate’s precision, pixel-center bounds and zero-outside-mask fixes. It does not change the source TIFFs, output sampling, validity tolerances or output resolution.

## Validity

**1,320 optimized image checks**, repeated on **1,320 images** in the paired benchmark: **zero missing pixels, spurious opaque pixels, alpha/color mismatches or response errors**. The correct baseline also passes 1,320 checks with the same oracle.

Twenty fixtures cover RGB, native RGBA (including partial alpha), four-band UInt16 and Float32 numeric/NaN NoData; north-up/30° grids; base images/nearest overviews; gutters 0/1. Expected pixels come from the independent inverse-transform oracle. Tolerances remain 2/255 color and 1/255 alpha, with no footprint erosion.

The separate 14-fixture grayscale reproduction includes negative rotation, 45°/75° and shear. Patched WMS and GWC have zero missing pixels and response errors at both gutters 0 and 1. That older oracle measures missing coverage, not full color/alpha equality.

Direct Java regressions exercise six sample storage types, one/three/four bands, NaN, infinities, unsigned values, open/closed ranges, nonzero image origins and tile offsets. Additional tests check packed-bit offsets/row padding, the conservative interior guard, and all existing 32,448 clipping cases and precision/edge regressions. The pinned official-image build, Python build/oracle/report checks and JavaScript adapter checks pass.

## Performance against the correct baseline

**62,640 timed requests, 3 fresh JVM pairs**. Response errors: **optimized 0, baseline 1**. Three rounds per pair, 1/6 clients, WMS/GWC MISS/GWC HIT, balanced variant order. Both variants run the same pinned official GeoServer 3.0.2 image with 2 CPUs, 6 GiB container memory and a 2 GiB Java heap. Profiling and other experiment loads run separately from timings.

The table reports the median across JVM pairs of each pair’s median fixture latency across three rounds and base/overview variants, for single-client WMS. A positive reduction means faster. Reduction is computed within each pair before taking the median, so it can differ from the ratio of the displayed medians. The range shows the three paired reductions, not a statistical confidence interval. North-up controls do not use the new GeoTools mask path.

| Case | Rotation | Correct baseline ms | Optimized ms | Median reduction | Range across JVM pairs |
|---|---:|---:|---:|---:|---:|
| rgb | 0° | 5.14 | 4.86 | 3.2% | 0.7% to 8.0% |
| rgb | 30° | 18.58 | 5.38 | 71.0% | 70.8% to 71.4% |
| rgba | 0° | 6.12 | 6.21 | -1.4% | -2.7% to 0.7% |
| rgba | 30° | 18.60 | 6.58 | 64.8% | 64.6% to 65.8% |
| multispectral | 0° | 20.98 | 20.77 | 1.0% | 0.9% to 1.3% |
| multispectral | 30° | 51.97 | 25.45 | 51.0% | 43.8% to 55.2% |
| dem | 0° | 12.53 | 11.41 | 6.4% | 1.8% to 8.9% |
| dem | 30° | 51.13 | 25.56 | 48.6% | 46.5% to 51.4% |
| dem_nan | 0° | 12.00 | 11.49 | 3.3% | 1.9% to 7.6% |
| dem_nan | 30° | 51.89 | 25.82 | 48.7% | 48.0% to 50.6% |

Across all 20 fixtures (north-up and rotated mixed), medians of block measurements:

| Route | Clients | Baseline ms | Optimized ms | Baseline req/s | Optimized req/s | Baseline CPU ms/request | Optimized CPU ms/request |
|---|---:|---:|---:|---:|---:|---:|---:|
| wms | 1 | 18.22 | 13.22 | 38.6 | 63.1 | 29.77 | 19.00 |
| wms | 6 | 78.80 | 36.97 | 72.2 | 114.6 | 27.81 | 17.72 |
| gwc-miss | 1 | 18.61 | 13.60 | 38.3 | 61.8 | 29.63 | 19.76 |
| gwc-miss | 6 | 81.17 | 39.78 | 72.5 | 114.5 | 27.62 | 17.66 |
| gwc-hit | 1 | 1.10 | 1.03 | 867.1 | 916.0 | 0.75 | 0.69 |
| gwc-hit | 6 | 3.68 | 3.64 | 1499.6 | 1499.6 | 0.68 | 0.71 |

**Baseline failures are retained.** Their cause is not established; this optimization is not claimed to fix them. Failed responses remain in request/error counts and reduce successful throughput; latency summaries include successful responses only.

| Variant | Replicate | Round | Route | Clients | Fixture | Tile | Error |
|---|---:|---:|---|---:|---|---|---|
| stock | 1 | 1 | wms | 6 | dem_nan_r0_base | [18, 156581, 106216] | invalid_image_response |

GWC HIT bypasses rendering; differences there measure cache/HTTP noise, not mask speed. WMS timings use opaque output, while the separate validity checks use transparent output.

## Why it improves

The baseline repeatedly applies general-purpose range lookup and image-combination operations to construct a mask. The replacement writes the same validity decision directly into a byte buffer and stops scanning bands as soon as one is valid. ImageN performs the final binarization. Interior tiles without NoData or ROI avoid constructing and transforming a footprint mask. Packed affine sampling avoids a boxed copy of the source mask. These changes reduce work while retaining validity at edges and holes.

Separate JFR profiles use the same rotated workload at six clients after warmup. Allocation figures below are sampled estimates, not exact allocation accounting or retained heap size.

| Variant | Completed requests | Errors | Sampled allocation MiB/request | Execution samples |
|---|---:|---:|---:|---:|
| Correct baseline | 580 | 0 | 58.57 | 3,046 |
| Optimized | 1,160 | 0 | 27.52 | 3,008 |

Sampled allocation per request falls by 53.0%. The optimized profile still spends substantial CPU time reading and testing NoData samples; these results do not establish a maximum possible speedup.

See the [profile summary](mask-optimized-profile.json) for leaf and inclusive stacks. Inclusive frame counts overlap and must not be added as CPU percentages. These profiles support the mechanism; they do not isolate the contribution of each optimization.

## Scope and evidence

The results apply to this synthetic, nearest-neighbor, same-CRS workload on Linux/WSL. They are not a throughput guarantee for production data. Arbitrary reprojection, bilinear/bicubic rendering, projection-domain clipping, real ImageMosaic datasets and all TIFF layouts still need upstream testing. Direct multi-band NoData unit tests do not replace end-to-end tests of every GeoServer style. The finite scanline precision limit is unchanged.

Additional documentation captures subsequently found zoom-15/16 alpha-boundary mismatches, identical to the previous candidate. Those low zooms were timed here but were outside this run’s typed validity checks at zooms 20/22/24. See [current validation](../validation.md#additional-wide-view-checks).

[Validity](mask-optimized-quality.json) · [Rendering](mask-optimized-rendering.json) · [Performance](mask-optimized-performance.json) · [Request timings](mask-optimized-requests.jsonl.gz) · [Verdict](mask-optimized-verdict.json) · [Profile](mask-optimized-profile.json)

In raw files, `stock` is the **correct patched baseline**, and `both` is the **optimized candidate**. The baseline lock and both build manifests identify the exact libraries. JARs, TIFFs, credentials, JFR recordings and raw image responses remain ignored.

Per-pixel and batched direct one-bit NoData outputs were also tried. Preliminary timings favored the byte intermediate, so the final implementation retains ImageN’s [ROI binarization](https://github.com/eclipse-imagen/imagen/blob/0.9.3/modules/core/src/main/java/org/eclipse/imagen/ROI.java). Those exploratory runs are not included in the final paired results.

## Reproduce

```bash
git switch main
git worktree add --detach /tmp/affine-correct-baseline c9aff37f393feb0638add12a2ce63d67f0f00d84
(cd /tmp/affine-correct-baseline && uv run python -m affine_fix.build --output .runs/patch)
uv run python -m affine_fix.typed_suite --root .runs/optimized-quality --quality-only --variants both
uv run python -m affine_fix.typed_suite --root .runs/optimized-performance --replicates 3 \
  --patch .runs/optimized-quality/patch \
  --baseline-patch /tmp/affine-correct-baseline/.runs/patch \
  --baseline-lock /tmp/affine-correct-baseline/runtime/lock.json
uv run affine-reproduce --root .runs/optimized-rendering
uv run python -m affine_fix.typed_suite --root .runs/optimized-profile --profile-only \
  --patch .runs/optimized-quality/patch \
  --baseline-patch /tmp/affine-correct-baseline/.runs/patch \
  --baseline-lock /tmp/affine-correct-baseline/runtime/lock.json
uv run python -m affine_fix.mask_report --quality .runs/optimized-quality \
  --performance .runs/optimized-performance --rendering .runs/optimized-rendering \
  --profile .runs/optimized-profile
```
