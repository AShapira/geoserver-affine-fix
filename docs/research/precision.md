# Affine boundary precision experiment

Branch: `codex/affine-boundary-precision`. Baseline: `fcbf811`.

The first experiment raised the fraction denominator from 20 to 28 bits (and widened multiplication before clipping). This reduced but did not eliminate edge errors. Inspection then found coordinate narrowing to float both before nearest sampling and in affine bounds calculations. Keeping these coordinates as doubles eliminates all measured RGBA and RGB color mismatches in the final test.

The final run checks RGB/RGBA, north-up/30 degrees, base/overview, gutters 0/1, using official GeoServer 3.0.2. At gutter 1, RGBA has zero missing, spurious, alpha or color errors, compared with 6 missing, 2 spurious and 16 color errors on the baseline. RGB color errors fall from 22 to zero, but its 516,580 spurious opaque pixels remain: precision alone does not repair missing validity masks. Counts include repeated observations across requests.

The direct Java tests retain 32,448 enumerated clipping cases and add scanline drift, integer-product overflow, and a rendered edge sample at source coordinate 2047.999964. The tests are compiled separately against original and candidate classes because Java inlines constants.

Four sibling ImageN classes are included from the verified 0.9.3 source archive and recompiled against the changed constant. AffineNearestOpImage is also modified; the other three sources are unchanged. The builder and installer verify the complete declared class set and preserve all other archive entries. See `patches/imagen.patch` and `patches/imagen-nearest.patch`.

This is an experimental candidate, not a universal accuracy guarantee. A finite 28-bit increment can still drift at sufficiently close boundaries or long scanlines. The wider precision also affects other affine interpolation classes; this run does not certify bilinear/bicubic behavior, arbitrary CRSs or large global pixel coordinates. Combine with the independently tested mask work before considering promotion. No performance claim is made from validity-only runs.

[Full final measurements](precision-results.json).

Reproduce:

```bash
uv sync --frozen --all-extras
uv run python -m affine_fix.typed_suite --root .runs/precision-check --quality-only --variants both --kinds rgb rgba
```

The full 9,440-request original grayscale rendering reproduction also completes. At gutter 1, missing footprint pixels fall from 16 to 8 per route; at gutter 0, 1,536 missing interior pixels remain. Thus this branch alone does not remove the need for request padding. [Measurements](precision-rendering.json).
