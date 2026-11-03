# GeoServer affine-raster fixes

[GitHub repository](https://github.com/AShapira/geoserver-affine-fix)

Reproduce and contribute two fixes for rotated/sheared GeoTIFF rendering while
preserving the source affine transform and nearest-neighbour pixel values:

- **GeoTools:** avoid premature map-space cropping of rotated source pixels.
- **Eclipse ImageN:** correct exclusive scanline bounds and empty intersections.

This is an independent reproduction and contribution project. The patches are
experimental and have not been accepted upstream. The original full matrix used
a **one-pixel gutter**, with zero failed requests or missing interior pixels and
**16 isolated footprint-edge omissions per serving path**. It is not a claim of
seamless rendering without a gutter. See the [original study](docs/rotated-geotiff-study.md),
[compatibility results](bundles/kartoza-geoserver-affine-fix/COMPATIBILITY.md), and
[upstream status](docs/upstream.md).

The [project creation validation](docs/validation.md) records the fresh local
checks separately from that historical evidence.

## Local setup and tests

Python 3.11+ is required. The locked environment was tested with Python 3.13.
From this repository root:

```bash
uv sync --frozen --all-extras
uv run python -m unittest discover -s tests -v
uv run python -m unittest discover -s bundles/kartoza-geoserver-affine-fix/tests -p 'test_*.py' -v
uv run python -m unittest discover -s bundles/kartoza-geoserver-2.28.0-affine-fix/tests -p 'test_*.py' -v
node --test viewer/tests/adapter.test.mjs
```

Without uv, create a virtual environment and run `python -m pip install -e '.[fixtures,analysis]'`.
The `fixtures` extra uses Rasterio's GDAL implementation; no separate host GDAL
installation is needed on platforms with a supported wheel. Node 22+ is needed
only for the optional viewer. The unit tests do not contact GeoServer.

## Reproduce on a fresh isolated server

The lab uses Docker or Podman, binds its HTTP port to localhost, copies synthetic
TIFFs into a new container, and puts image-declared catalog/cache volumes in
temporary filesystems. It does not mount the old benchmark volume or any host
directory. Its generated password and state stay in ignored `.runs/` files.
The lab removes only Kartoza's per-user WMS rate rule in its temporary catalog,
retaining concurrency limits, so HTTP 429 throttling does not obscure rendering
results. The original rule file is saved locally.

```bash
uv run affine-probe prepare --root .runs/fixtures
uv run affine-lab up --pull
uv run affine-validate publish --url http://127.0.0.1:18096/geoserver --password-file .runs/lab/admin-password
uv run affine-validate scan --url http://127.0.0.1:18096/geoserver --password-file .runs/lab/admin-password --quick --label stock-g0
uv run affine-lab stop
```

`affine-lab` defaults to the exact Kartoza 2.28.5 image in the historical build
lock. The first pull is approximately 1.5 GB compressed. `--engine docker`,
`--connection NAME` (Podman), `--image`, `--port`, `--root`, and `--fixtures`
select explicit alternatives. Images must use the Kartoza startup contract.
`stop` retains the container and local evidence; `down` removes only the container
whose ownership label matches that lab's saved state. Tmpfs catalogs disappear
on stop; start a fresh lab root for each new treatment.

The stock scan **is expected to expose missing pixels**. A scan records defects;
it is not a pass/fail assertion of a fix. `affine-validate regression` performs
the selected assertions and is expected to fail on stock. Results and PNGs go to
`.runs/rendering/`; use a fresh `--label` and `--output` for each treatment.
Scan labels resume previous requests, including failures.
Run `affine-validate configure` with the intended gutter before a new scan to
clear this lab's layer caches if earlier requests have populated them.

For a full matrix omit `--quick`. The 14 default fixtures are 4096 × 4096 and
occupy approximately 51 MB. A smaller `affine-probe prepare --size 32` is useful
for fixture tests, but is rejected by the rendering validator. Fixture files are
read-only and existing checksums are verified before reuse.

## Test the existing correction

The source repository carries builders and matching source archives, not compiled
JAR payloads. Build the 2.28.5 bundle using its pinned stock image:

```bash
uv run python bundles/kartoza-geoserver-affine-fix/build.py --engine podman
uv run affine-lab up --root .runs/patched-lab --port 18097 --bundle bundles/kartoza-geoserver-affine-fix
uv run affine-validate publish --url http://127.0.0.1:18097/geoserver --password-file .runs/patched-lab/admin-password --output .runs/patched
uv run affine-validate configure --url http://127.0.0.1:18097/geoserver --password-file .runs/patched-lab/admin-password --output .runs/patched --gutter 1
uv run affine-validate regression --url http://127.0.0.1:18097/geoserver --password-file .runs/patched-lab/admin-password --output .runs/patched --gutter 1
uv run affine-lab stop --root .runs/patched-lab
```

The builder checks original JAR/source hashes, compiles two classes in a unique
network-isolated container, runs the failing-original/passing-patched Java
regression, and verifies that no other JAR entries changed. Build output stays in
the bundle's ignored `jars/` and `.artifacts/` folders. For other exact versions,
see [bundle instructions](bundles/kartoza-geoserver-affine-fix/README.md) and
[compatibility tools](bundles/kartoza-geoserver-affine-fix/compatibility/README.md).

`affine-validate` defaults to fixtures at `.runs/fixtures` and server fixture
location `/opt/affine-fixtures`. Both are configurable. Only point catalog-writing
commands at an isolated test server. GWC gutter settings do not apply to direct
WMS; the validator separately expands/crops WMS requests at the same resolution.

## Project layout and provenance

| Location | Purpose |
|---|---|
| `affine_fix/` | Fixture generator, oracle, WMS/GWC probes, lab lifecycle, analysis |
| `tests/` | Lightweight regressions and original Java clipping regression |
| `patches/` | GeoTools 35.1 / ImageN 0.9.2 candidate diffs |
| `bundles/` | Version-specific builders, installers, matching sources, historical evidence |
| `viewer/` | Optional Cesium comparison; see its standalone instructions |
| `docs/` | Study, upstream plan, validation and migration notes |
| `provenance/import.json` | Original commit, file mapping and pre-adaptation SHA-256 values |

Imported from `AShapira/small-gis-demos` at commit
`45b8aeb44e594b75480b97d1cb8d9f1793d57503`. Historical snapshots remain there.
New test output must not overwrite the imported evidence. Upstream contributions
will be made in separate GeoTools/ImageN forks, not by vendoring those repositories.

Original tooling is MIT licensed. GeoTools and ImageN adaptations retain their
upstream licenses; see [license scope](LICENSING.md). Upstream submissions remain
pending; publishing this project does not mean the fixes are accepted upstream.
