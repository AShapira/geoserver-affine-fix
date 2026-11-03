# Current GeoServer 3.0.2 validation

The implementation on `main` is the integrated and optimized candidate, tested on Linux/WSL amd64 with the pinned official image, GeoTools 35.2 and ImageN 0.9.3. It is not an accepted upstream fix.

## Established validity matrix

The optimized candidate passed 1,320 typed image checks, repeated on another 1,320 requests during the paired benchmark. RGB, native RGBA, four-band UInt16 and Float32 numeric/NaN NoData have zero missing, spurious, alpha or color mismatches within the unchanged tolerances (1/255 alpha; 2/255 color).

This matrix covers north-up/30° rotation, base images/nearest overviews, gutters 0/1 and zooms 20/22/24. Expected values come from independent inverse-transform sampling, without excluding a footprint tolerance band. See the [typed evidence](research/mask-optimized-quality.json) and [paired-run evidence](research/mask-optimized-performance.json).

## Broader grayscale matrix

Fourteen 4096 × 4096 Byte fixtures include north-up, 15°, 30°, 45°, 75°, −30° and shear, with and without nearest overviews. Each treatment runs 1,180 WMS and 1,180 GWC requests across zooms 14–24. All fixture hashes remain unchanged. The full stock/current comparison contains 9,440 requests.

Counts below combine WMS and GWC. This older oracle measures missing coverage rather than full RGBA equality.

| Code | Gutter | Requests | Response errors | Missing pixels | Missing interior pixels |
|---|---:|---:|---:|---:|---:|
| Official stock | 0 | 2,360 | 4 | 7,961,352 | 7,290,204 |
| Official stock | 1 | 2,360 | 4 | 7,293,958 | 6,779,780 |
| Current fix | 0 | 2,360 | 0 | 0 | 0 |
| Current fix | 1 | 2,360 | 0 | 0 | 0 |

The current code has zero response errors and missing pixels at both gutters. The earlier 16-pixel outer-footprint exception is resolved in this matrix; it is retained only in the [historical report](history/initial-validation.md). All successful matrix WMTS responses are verified MISSes; a separate check verifies MISS followed by HIT. [Full machine-readable reproduction](validation.json).

## Additional wide-view checks

The README image work adds 215 transparent WMS requests per variant on five rotated base-image fixtures, at gutter 1 and zooms 15/16/17/20/22/24. Three fresh servers run official stock, the previous candidate (`c9aff37`) and the optimized candidate: **645 additional requests**.

Of the 215 optimized requests, **197 pass** and **18 have boundary mismatches**. All 18 are zoom-15/16 views of RGBA or Float32 NoData. Their alpha and all visible RGB values are **pixel-for-pixel identical to the previous candidate**; this is an existing limitation, not a regression introduced by mask optimization. The exact root cause has not been established.

For each type, the table aggregates the six additional zoom-15/16 requests. Counts are output-pixel observations across requests, not unique source pixels.

| Type | Requests | Missing | Spurious | Alpha mismatches | Color mismatches |
|---|---:|---:|---:|---:|---:|
| rgb | 6 | 0 | 0 | 0 | 0 |
| rgba | 6 | 89 | 88 | 300 | 89 |
| multispectral | 6 | 0 | 0 | 0 | 0 |
| dem | 6 | 89 | 88 | 177 | 89 |
| dem_nan | 6 | 89 | 88 | 177 | 89 |

RGB and UInt16 pass the additional wide-view cases. All types pass the additional zoom-17 requests and the captured zoom-20/22/24 requests. These findings qualify the performance workload, whose low-zoom requests were timed but were not part of its earlier typed validity matrix.

The three README figures deliberately show passing current views. Every capture, including the 18 failures and the previous-candidate comparison, is retained in [image evidence](assets/raster-comparisons.json). See [image reproduction and selection](images.md).

## Regression and build checks

The official-image build demonstrates failure of the original clipping regression and success of the corrected Java tests: 32,448 scanline cases, precision and pixel-center boundaries, zero-outside masks, packed BYTE/USHORT/INT storage, six NoData sample types, multi-band validity, unsigned ranges and translated/padded raster layouts. Python oracle/build/report tests and JavaScript adapter tests pass.

The runtime lock names every replaced and added class. The build preserves unrelated archive entries and metadata, and generated JARs remain outside Git. Fresh lab containers use copied fixtures and temporary catalogs; their credentials and raw responses are never published.

## Remaining scope

Exact output at arbitrary downsampled resolutions is not established: the wide-view alpha-boundary cases above are a known issue. Arbitrary reprojection, bilinear/bicubic rendering, real ImageMosaic datasets, every GeoTIFF layout, native Windows and ARM still require testing. The finite affine scanline precision limit remains. Upstream main has not been built or tested.

Performance is separately documented in [the current performance report](performance.md), including one intermittent invalid response from the comparison baseline and zero timed-response errors from the optimized candidate.
