> Historical experiment. For the integrated implementation on this repository’s `main`, see [current validation](../validation.md) and [current performance](../performance.md).

# Mask-preserving crop experiment

Branch: `codex/mask-preserving-crop`. Baseline: `fcbf811`.

The candidate retains the rotated source window, attaches a tiled source-grid footprint mask, and intersects it with a NoData-validity mask before affine rendering. NoData is classified before background substitution, preserving valid zero elevation even when the renderer uses zero as its background. For multi-band NoData, a pixel is excluded only when all bands match NoData; the current typed fixtures exercise the single-band case.

A second correction in ImageN's AffinePropertyGenerator explicitly fills transformed validity masks with zero outside the source and uses zero border extension. The binary affine loop otherwise reuses its previous sample when destination filling is disabled. A direct Java regression checks the entire transformed mask under inherited border-copy hints.

Several approaches were rejected during investigation: a geometric ROIShape allocated huge images under high magnification; a bitmap ROI alone leaked outside the footprint; changing border extension alone did not fix the binary stale-sample behavior; a vector ROI added multispectral color discrepancies. The retained candidate uses a tiled bitmap and explicit zero fill.

The final official GeoServer 3.0.2 run contains 1,320 checks: five types, north-up/30 degrees, base/overview, gutters 0/1, patched server. Every response succeeds. All north-up controls pass. At gutter 1, every rotated type has only 6 missing and 2 spurious pixels. Color mismatches are 22 for RGB/UInt16 and 16 for RGBA/Float32. Compare baseline spurious counts of 516,580 for RGB/UInt16 and 1,709,882 for elevation. These are repeated output-pixel observations, not unique source pixels.

This fixes the large transparency/NoData regressions but leaves precision-boundary discrepancies. It is not an exact validity pass. Combine with the separate precision candidate and validate before promotion. No performance conclusion is drawn from this validity-only run.

[Full final measurements](mask-results.json).

```bash
uv sync --frozen --all-extras
uv run python -m affine_fix.typed_suite --root .runs/mask-check --quality-only --variants both
```
