# Official GeoServer 3.0.2 validation

Checked on **2026-11-03**, on Linux/WSL amd64 with local Podman. The source
image is the official `docker.osgeo.org/geoserver:3.0.2` image, pinned by digest
in [runtime/lock.json](../runtime/lock.json). Runtime REST metadata confirmed
GeoServer 3.0.2, GeoTools 35.2 and GeoWebCache 2.0.2; the pinned affine library
is ImageN 0.9.3. No optional server extensions were installed.

## Full rendering matrix

Each treatment attempted **1,180 requests per route**, for **9,440 requests**
in total. Direct WMS and GWC/WMTS produced identical error and missing-pixel
counts. Values below are **per route**, not combined totals. Missing-pixel
counts cover successful responses; failed requests are counted separately.

| Code | Gutter | Successful requests | Rendering errors | Missing pixels | Missing interior pixels |
|---|---:|---:|---:|---:|---:|
| Stock | 0 | 1,178 | 2 | 3,980,676 | 3,645,102 |
| Stock | 1 | 1,178 | 2 | 3,646,979 | 3,389,890 |
| Patched | 0 | 1,180 | 0 | 1,714 | 1,536 |
| Patched | 1 | 1,180 | 0 | 16 | 0 |

The patch with gutter 1 has no rendering errors and no missing interior pixels,
but retains **16 isolated outer-footprint omissions per route**. Without a gutter,
the patch still leaves tile-boundary rows. A gutter alone does not fix the stock
renderer. The project does not claim seamless output for every raster or request.

## Controls and independent checks

- Fourteen immutable 4096 × 4096 Byte GeoTIFFs: north-up, rotations of 15°, 30°,
  45°, 75° and −30°, and a sheared grid; each with and without nearest overviews.
- Source and request CRS are EPSG:3857, using ordinary GeoTIFF stores and nearest
  interpolation. The source transform and all fixture SHA-256 hashes remained
  unchanged throughout the run. No source pixels were warped or resampled.
- The matrix covers zooms 14–24 and interior/footprint-edge locations. The
  independent oracle inversely maps output pixel centres through the TIFF's
  affine transform. It does not erase a tolerance band around the footprint.
- Fresh server catalogs isolate stock and patched treatments. Caches are cleared
  for every gutter treatment; every successful WMTS matrix response was a cache
  MISS. A separate repeated request verified MISS followed by HIT.
- North-up controls had zero missing pixels in every treatment.
- The selected ten-request rendering regression passed with the patch and gutter
  1, checking interior gaps, source values and the footprint-edge exception.
- The builder confirmed the clipping regression fails on the official ImageN
  JAR and passes after correction, including 32,448 independently enumerated
  positive, negative, fractional, zero-step and empty scanlines.
- Exactly one class entry changed in each JAR; all other archive entries retained
  their original bytes. Modified sources match the reviewable patches and the
  build lock. The original source files also match their Maven source archives.
- The Python suite passed 14 tests and the JavaScript adapter suite passed three
  tests. Both integration servers were stopped at completion.

## Images and reproducibility

[triangles.png](assets/triangles.png) and [checkerboard.png](assets/checkerboard.png)
use actual WMS responses from this run, grouped by identical request gutter.
The expected panels are independently calculated from the unchanged source.
The [scanline-bounds diagram](assets/scanline-bounds.png) is explicitly illustrative.

The [machine-readable report](validation.json) contains the exact runtime/source
hashes, fixture hashes, aggregate counts, selected image measurements and cache
check. Regenerate everything using the root [README](../README.md) commands.
Full response PNGs, per-request logs, private credentials and build outputs remain
in the ignored run directory; none are required from a previous checkout.

## Limits

This validates the release-pinned candidates and this defined nearest-neighbour
matrix. Upstream main has not been built or tested. Broader interpolation,
reprojection, NoData/ROI, numeric-type and bounded-read regressions are still
needed for upstream review. Native Windows, ARM and browser UI acceptance were
not run. The 16 remaining outer-footprint omissions are a separate open problem.
