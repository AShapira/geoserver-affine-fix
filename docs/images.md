# Reproduce the raster comparison images

The README contains actual WMS responses from official GeoServer 3.0.2 with its
original libraries, and from the same image with this project's current fix.
A third server running the previous validated candidate is used to check whether
additional image cases expose an optimization regression.

All images use synthetic 2048 × 2048 tiled GeoTIFFs, 30° rotation, EPSG:3857,
nearest-neighbor interpolation and gutter 1. The source files are copied into
fresh temporary catalogs. No host data directories are mounted into the labs.

## Capture and plot

From this repository's `main` checkout, with the official image available locally:

```bash
uv sync --frozen --all-extras
git worktree add --detach /tmp/geoserver-affine-previous c9aff37f393feb0638add12a2ce63d67f0f00d84
(cd /tmp/geoserver-affine-previous && uv run affine-build --output .runs/image-reference)
uv run python -m affine_fix.documentation_figures --root .runs/readme-images \
  --baseline-patch /tmp/geoserver-affine-previous/.runs/image-reference \
  --baseline-lock /tmp/geoserver-affine-previous/runtime/lock.json
```

The image command builds the current patch automatically. Use `--pull` if the
pinned official image is not yet present, `--port` to change the localhost port,
or `--engine docker` for Docker. When building the previous candidate, use the
same engine and `--pull` as needed. An optional `--patch` may reuse a build only
when its source hashes match the current lock.

The command captures 215 requests per variant, removes its own containers, and
writes these composed figures plus [public evidence](assets/raster-comparisons.json):

- [RGB and four-band UInt16](assets/rgb-multiband.png): valid colored pixels lost by the stock crop.
- [RGBA and footprint transparency](assets/rgba-transparency.png): transparent holes,
  alpha 128 and the transparent exterior of the raster.
- [Float32 numeric/NaN NoData](assets/nodata-transparency.png): transparent NoData
  beside valid zero and negative elevations.

The original RGBA responses and independently calculated references stay under
`.runs/readme-images/images/`. To replot retained captures without starting servers:

```bash
uv run python -m affine_fix.documentation_figures --root .runs/readme-images --render-only
```

## What the figures mean

The checkerboard is a display background, composited **after** measuring the
original RGBA arrays. It never changes the measured alpha or color values.
The expected column comes from inverse-transforming destination pixel centers
and sampling the synthetic source pattern. No footprint tolerance band is removed.

Color examples are selected from opaque, multicolor interior tiles with visible
stock crop loss. Transparency examples require enough transparent, opaque and,
for RGBA, partly transparent pixels to explain the behavior. **Every selected
current panel has zero measured mismatches** at the existing 1/255 alpha and
2/255 color tolerances. The selection and image hashes are recorded in the evidence.
Some preservation controls, such as the selected native-RGBA view, are already
correct in stock GeoServer; their caption and counters make that explicit.

All other captures remain in the evidence. The added zoom-15/16 alpha cases have
[documented boundary mismatches](validation.md#additional-wide-view-checks), identical
to the previous candidate. The exporter requires that comparison before recording
an existing limitation; a new visible/alpha difference causes export to fail.
It also recalculates every stored measurement before plotting.

Raw PNGs, credentials, logs and JARs remain ignored. The committed PNGs are
annotated comparison figures, not raw server responses.
