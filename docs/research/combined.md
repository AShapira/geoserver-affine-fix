# Combined affine candidate

Branch: `codex/affine-complete-candidate`. Published baseline: `fcbf811`. This integrates the mask and precision experiments, with additional fixes found during integration. **Experimental; not merged to main or submitted upstream.**

## Changes

1. Preserve a source-grid footprint mask while bypassing the premature map-space crop.
2. Add a NoData-validity mask before affine background substitution, preserving valid zero elevations.
3. Explicitly write zero outside transformed binary masks; never extend their border as valid data.
4. Keep affine bounds and nearest/binary sample coordinates in double precision. Use 28-bit scanline fractions and widen products before multiplication.
5. Compute nearest-neighbor output bounds from pixel centers. Separately rounding the origin and truncating width can omit an otherwise valid final column or row.

## Validity

The independent typed matrix performs **1,320 checks**, with 0 response errors, 0 missing pixels, 0 spurious opaque pixels, 0 alpha mismatches and 0 color mismatches. It covers RGB, RGBA, four-band UInt16 and Float32 with numeric/NaN NoData; north-up/30° rotation; base images/overviews; gutters 0/1. Existing tolerances remain 2/255 for color and 1/255 for alpha, with no footprint erosion. A fresh paired performance run repeats 1,320 candidate image checks, with 0 failed checks.

The original grayscale reproduction covers 14 fixtures including negative rotation, 45°/75° rotation and shear, on WMS and GWC. This older oracle counts missing data, not full color/alpha equality. Results:

| Treatment | Route | Response errors | Missing pixels | Missing interior pixels |
|---|---|---:|---:|---:|
| patched-g0 | wms | 0 | 0 | 0 |
| patched-g0 | gwc | 0 | 0 | 0 |
| patched-g1 | wms | 0 | 0 | 0 |
| patched-g1 | gwc | 0 | 0 | 0 |

Direct Java regressions cover 32,448 clipping cases, scanline drift, integer-product overflow, a rendered edge sample, an entire transformed binary mask, and a mask sample at a fractional affine boundary. The original library fails the clipping regression; the candidate passes the full Java test. Python source/patch/build checks and JavaScript adapter checks also pass.

## Exploratory performance

20,880 timed requests with 0 response/cache errors. **One fresh JVM pair**, three rounds, 1/6 clients, WMS/GWC MISS/GWC HIT. This is a paired sanity check, not the earlier three-JVM benchmark. Other test loads finish before timing begins. WMS timing remains opaque; image validity is checked separately with transparent output. Per-case numbers below are medians of single-client WMS fixture medians across rounds and overview variants.

| Case | Rotation | Stock ms | Candidate ms |
|---|---:|---:|---:|
| rgb | 0° | 5.59 | 5.20 |
| rgb | 30° | 9.80 | 19.70 |
| rgba | 0° | 6.82 | 6.69 |
| rgba | 30° | 9.28 | 19.93 |
| multispectral | 0° | 21.47 | 22.49 |
| multispectral | 30° | 45.16 | 56.15 |
| dem | 0° | 12.56 | 12.30 |
| dem | 30° | 17.76 | 51.61 |
| dem_nan | 0° | 12.69 | 12.30 |
| dem_nan | 30° | 19.15 | 49.38 |

**Performance cost:** rotated single-client WMS medians are 1.24–2.91× stock in this run. This candidate restores correctness at a measurable cost; optimizing mask processing is a separate next step.

The candidate avoids premature map-space crop/mosaic work, while restoring validity handling. These measurements do not isolate individual operation costs. Repeated JVMs and realistic datasets are still needed before making a general performance claim.

## Evidence and scope

[Typed measurements](combined-quality.json) · [Original rendering reproduction](combined-rendering.json) · [Performance measurements](combined-performance.json) · [Request timings](combined-requests.jsonl.gz) · [Machine-readable verdict](combined-verdict.json)

Source TIFF hashes are unchanged; libraries are built against the pinned official GeoServer 3.0.2 image. The previous main-branch report remains historical evidence. Rejected prototypes are discussed in the [mask experiment](mask.md) and [precision experiment](precision.md).

Remaining scope: no claim for arbitrary reprojection, bilinear/bicubic rendering, all GeoTIFF layouts or multi-band NoData combinations. A finite fixed-point scanline increment still has a precision limit. The broader ImageN precision changes need upstream interpolation regressions and review. The GeoTools bypass must also be checked against projection-domain clipping and real ImageMosaic datasets. Native RGBA is tested; explicitly selecting RGB channels is a different style and can drop alpha independently of this patch.

## Reproduce

```bash
uv sync --frozen --all-extras
uv run python -m affine_fix.typed_suite --root .runs/typed-candidate --quality-only --variants both
uv run affine-reproduce --root .runs/rendering-candidate
uv run python -m affine_fix.typed_suite --root .runs/performance-candidate --replicates 1
uv run python -m affine_fix.research_report --quality .runs/typed-candidate --rendering .runs/rendering-candidate --performance .runs/performance-candidate
```
