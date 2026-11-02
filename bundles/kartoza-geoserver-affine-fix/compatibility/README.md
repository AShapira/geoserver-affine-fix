# Compatibility tools

Historical results are in `evidence/` and [COMPATIBILITY.md](../COMPATIBILITY.md).
The tag inventory is the snapshot checked on 2026-10-20, not a live registry query.
New generated files go under the bundle's `.artifacts/compatibility/` directory.

From the repository root, install the project and generate full fixtures as
explained in [README](../../../README.md). Build the original 2.28.5 payload
first: compatibility inspection tests rejection of that payload by older images.
Pull the exact selected image digest from `evidence/published-tags.json` into the
chosen engine, then:

```bash
uv run python bundles/kartoza-geoserver-affine-fix/compatibility/inspect_versions.py 2.28.0 --engine podman
uv run python bundles/kartoza-geoserver-affine-fix/compatibility/render_versions.py 2.28.0 --phase stock --fixtures .runs/fixtures
uv run python bundles/kartoza-geoserver-affine-fix/compatibility/render_versions.py 2.28.0 --phase patched --fixtures .runs/fixtures --full
```

Inspection downloads exact-version source archives, applies the existing patch
with exact context, compiles in a unique network-isolated container, and verifies
the original/patched clipping regression. It creates a version-matched candidate.
It does not change existing containers or build an image.

Rendering uses the standalone lab lifecycle: fresh tmpfs catalog, copied fixtures,
localhost HTTP binding, unique name and private local credentials. No old
benchmark volume or secret is used. Each treatment stops its own container when
done. `--engine`, `--connection` and `--port` select the runtime explicitly.

`analyze_versions.py` requires completed stock and full patched runs for its six
historical tags. Set `AFFINE_FIXTURES` to the generated fixture root. New summaries
go under `.artifacts/compatibility/analysis`, preserving the imported evidence.
This six-version live matrix has not been rerun merely by importing the project.
