# GeoServer affine-raster fixes

**Research branch:** see the [mask-preserving experiment](docs/research/mask.md).
The published baseline report below is retained for comparison.

Reproduce two raster-rendering defects on **official GeoServer 3.0.2** and test
candidate source fixes in **GeoTools 35.2** and **Eclipse ImageN 0.9.3**.
GeoServer 3.0.2 is the [current stable release](https://geoserver.org/download/),
verified on 2026-11-03. The test runtime uses the project's
[official container image](https://github.com/geoserver/docker), pinned by digest
in [runtime/lock.json](runtime/lock.json).

These are experimental source corrections, **not an accepted upstream fix**.
The tests preserve the TIFF's rotation/shear, source pixels and nearest-neighbour
sampling. No north-up conversion, smoothing or resampling of the source is used.

**Extended validity tests found regressions:** rotated RGB and multispectral
footprints gain opaque pixels where transparency is required, and rotated
Float32 elevation loses NoData transparency. The earlier interior performance
gains do not establish general correctness. See the
[RGB, RGBA, UInt16 and Float32 test report](docs/typed-raster-tests/README.md).

## The visible bug

A rotated GeoTIFF contains valid data throughout this map tile, but the stock
server drops triangular areas. White pixels inside this tile are missing output,
not gaps in the source TIFF. Each row compares stock and patched code with the
**same request gutter** and the same map extent. The right column is calculated
independently from the source affine transform.

![Actual stock and patched GeoServer responses compared with independently expected pixels](docs/assets/triangles.png)

**GeoTools correction:** `GridCoverageReaderHelper.cropCoverage` crops a rotated
source grid in map coordinates before final rendering. That crop can discard
source pixels that the output still needs. For same-CRS rotated/sheared grids
using nearest interpolation, the candidate change keeps the reader-selected
pixels available to the renderer. See the [source diff](patches/geotools.patch).

The checkerboard example shows that the correction retains sharp source pixels:

![Checkerboard rendering before and after the source corrections](docs/assets/checkerboard.png)

## The separate clipping defect

ImageN's affine scanline clipping includes a sample at the exclusive upper source
bound. This can select an invalid sample and cause an array-bounds exception.
The second correction fixes endpoint rounding for both traversal directions and
represents a disjoint intersection as empty. See the [source diff](patches/imagen.patch).

![Illustration of the exclusive source bound and the incorrect extra sample](docs/assets/scanline-bounds.png)

This diagram is an illustration; the two comparisons above contain actual server
responses. A direct Java regression fails against the original ImageN library
and passes against the correction, including **32,448 enumerated scanlines**
with positive, negative, fractional and zero increments.

Across the original single-band Byte matrix, the patch with gutter 1 removed all
rendering errors and missing interior pixels. **Sixteen outer-footprint pixels per route still remain
missing**; this is a separate limitation. See the [measured results](docs/validation.md).

## Reproduce the comparison

Requirements: Python 3.11+ (tested with 3.13), [uv](https://docs.astral.sh/uv/),
and Podman or Docker. The pinned runtime was validated on Linux/WSL amd64.
Rasterio supplies GDAL through its wheel; no host GDAL installation is required.

```bash
git clone https://github.com/AShapira/geoserver-affine-fix.git
cd geoserver-affine-fix
uv sync --frozen --all-extras
uv run affine-reproduce --pull --root .runs/geoserver-3.0.2
```

Use `--engine docker` for Docker. The command generates 14 immutable synthetic
TIFFs, compiles the two corrected classes against the exact official libraries,
and runs stock and patched servers sequentially. Each server gets a fresh
catalog and is tested with gutters **0 and 1**, using direct WMS and GWC/WMTS.
Caches are cleared between treatments and cache MISS responses are verified.

The servers bind to localhost, copy fixtures into their containers and use
temporary catalogs. They do not mount host directories. Generated credentials,
logs, JARs and raw responses remain under the ignored run directory. Both test
servers are stopped when their work finishes. Choose a new `--root` for each run;
existing run directories are not silently reused. `--quick` runs an interior
subset instead of the full matrix, and `--port` selects another localhost port.

The selected rendering regression checks missing interior pixels, source values
and the footprint-edge exception. The [validation report](docs/validation.md)
records the full matrix and remaining limitations. **A gutter is still relevant
at tile boundaries; the code changes alone are not a claim of seamless output.**
For direct WMS the runner expands the request at unchanged resolution and crops
the central tile; for GWC it configures the layer's gutter.

To regenerate the README figures and compact evidence from a completed run:

```bash
uv run affine-report --run .runs/geoserver-3.0.2 --output docs
```

## Performance tests

The performance suite compares stock code, each correction independently, and
both corrections on the same official image. The published run completed
**232,704 timed requests across 12 fresh JVMs, with zero timed-response errors**.
It uses three fresh JVMs per
variant, repeated measurements, 1/6/12 clients, WMS and verified GWC MISS/HIT
responses, 4096- and 16,384-pixel sources, interpolation controls and larger
output images. Separate pixel checks and JVM profiles accompany the timings.

For the core workload with one client and a one-pixel gutter:

| Request path | Stock median | Both corrections |
|---|---:|---:|
| Direct WMS | 8.75 ms | 4.66 ms |
| GWC cache MISS | 9.70 ms | 5.74 ms |
| GWC cache HIT | 1.22 ms | 1.14 ms |

Across paired fresh-JVM runs, WMS latency fell **44–49%** and cache-MISS latency
fell **37–44%**. Cache-HIT differences changed direction between runs, so there
is no consistent cache-HIT improvement to attribute to the patch. Table cells
are medians across JVMs; percentage changes compare corresponding JVMs.

**Why it is faster:** the GeoTools correction avoids the premature crop and
its extra mask processing while preserving the source pixels. Independent-fix
tests identify it as the main gain, and JVM profiles show the expensive binary
mask path disappearing from the hot methods. Sampled allocation per request
fell from about **22.8 MB to 8.8 MB**. The ImageN correction fixes scanline bounds;
it does not account for the large speedup. Larger-source and interpolation
controls have different results, detailed in the report.

![Measured latency across stock code, each correction separately, and both corrections](docs/assets/performance.png)

```bash
uv run affine-benchmark --pull --root .runs/benchmark-3.0.2
uv run affine-benchmark-report --run .runs/benchmark-3.0.2 --output docs
```

See the [performance analysis and method](docs/performance.md),
[all measured conditions](docs/performance/measured.md) and
[downloadable samples](docs/performance/requests.jsonl.gz). The test uses four
localhost ports starting at 18106 and removes its own containers when finished.
GitHub CI runs the benchmark's accounting/workload tests; full container timing
and profiling are explicit local runs, not noisy CI speed thresholds.

## Work on one server

For an interactive lab and the optional [Cesium gutter viewer](viewer/README.md):

```bash
uv run affine-probe prepare --root .runs/fixtures
uv run affine-lab up --pull --root .runs/lab
uv run affine-validate publish --password-file .runs/lab/admin-password
# Inspect or test the stock server at http://127.0.0.1:18096/geoserver
uv run affine-lab stop --root .runs/lab

uv run affine-build
uv run affine-lab up --root .runs/patched-lab --patch .artifacts/patch
uv run affine-validate publish --password-file .runs/patched-lab/admin-password --output .runs/patched
uv run affine-validate configure --password-file .runs/patched-lab/admin-password --output .runs/patched --gutter 1
uv run affine-validate regression --password-file .runs/patched-lab/admin-password --output .runs/patched --gutter 1
uv run affine-lab stop --root .runs/patched-lab
```

`affine-lab down --root …` removes only that lab's labelled container and keeps
local evidence. The builder verifies source and JAR hashes and changes exactly
one class per JAR. No custom server image is built.

## Tests and contribution status

```bash
uv run python -m unittest discover -s tests -v
node --test viewer/tests/adapter.test.mjs
```

Node 22+ is only needed for the optional viewer and its tests. GitHub CI runs
these lightweight tests; the container rendering matrix is a separate integration
check. [docs/upstream.md](docs/upstream.md) describes the two upstream contribution
paths and the additional current-main tests needed before submission.

Matching source files, patches and license notices are under [source/](source/README.md).
The original tooling is MIT licensed; GeoTools and ImageN code retain their
upstream licenses. See [LICENSING.md](LICENSING.md).
