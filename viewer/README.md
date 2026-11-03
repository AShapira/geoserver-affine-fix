# Cesium WMS gutter comparison

Optional visual comparison for the affine-raster study. The browser adapter
expands a WMS request at unchanged resolution, then crops its central tile.
Nearest-neighbour texture sampling preserves sharp source values. The viewer
does not modify TIFFs.

First generate the full fixtures and publish them to a fresh lab using the
[repository-root instructions](../README.md). With that lab running:

```bash
uv run python viewer/tests/prepare.py --fixtures .runs/fixtures
cd viewer
npm ci
GEOSERVER_WMS=http://127.0.0.1:18096/geoserver/wms npm start
```

Open `http://127.0.0.1:18120`. The server binds to localhost and proxies only
GetMap to the configured upstream. `PORT`, `HOST` and `GEOSERVER_WMS` are explicit
settings. Stop the viewer with Ctrl+C and the lab with `uv run affine-lab stop`
from the repository root.

Node 22+ is required. Browser automation also needs Playwright's browser for
this platform. Reference preparation checks TIFF hashes, generates PNGs under
`.artifacts/references`, and refreshes the fixture/case metadata. It never writes
TIFF pixels. From the repository root, run the lightweight adapter checks with:

```bash
node --test viewer/tests/adapter.test.mjs
```

Run `npm run test:browser`, `test:smoke` and `test:gutters` from this folder only
when the viewer and intended lab are running. Browser outputs go to ignored
`evidence/` and `.artifacts/` folders. The authoritative server comparison is
the official GeoServer 3.0.2 [validation report](../docs/validation.md).

This optional viewer compares request gutters on one selected server. The main
reproduction compares stock and patched code separately and uses actual server
responses for its README illustrations. See the root instructions for creating
a lab with `affine-lab up` and publishing the fixtures before opening the viewer.
