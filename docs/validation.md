# Project creation validation — 2026-11-02

The independent project was tested on Linux/WSL with local Podman, using its
own fresh containers and catalogs. No retained benchmark service or data volume
was used. Both test servers were stopped afterward.

- A clean copy of the staged repository installed from `uv.lock` and passed
  25 Python tests plus 3 JavaScript adapter tests without the old checkout.
- All 14 generated TIFFs matched the historical transforms, CRS, base pixels,
  and overview pixels (42 array comparisons). The seven TIFFs without overviews
  also matched the historical file hashes. The seven overview TIFFs have
  different container bytes; their pixels and geometry are identical.
- The stock Kartoza 2.28.5 minimal request reproduced 29,022 missing pixels
  through both direct WMS and GWC.
- The 2.28.5 builder compiled the two classes, confirmed failure on the original
  clipping implementation and success on the correction, and verified exactly
  one changed class entry per JAR. Packaging produced a valid local ZIP.
- With the matched patch and gutter 1, all ten selected regression requests
  passed and GWC MISS → HIT behavior was verified.
- A separate quick scan, after clearing test caches, completed 224 WMS and
  224 GWC requests with zero errors or missing pixels. All 224 GWC requests were
  cache MISS. These are interior requests, not the full footprint-edge matrix.
- All 101 imported historical evidence files remained byte-identical. The
  original 2.28.5 snapshot's checksum manifest still verifies after adding the
  separate relocation notice.

See the [machine-readable record](validation-2026-11-02.json). Raw outputs,
private lab state and generated payloads are local ignored artifacts.

The full 1,180-request-per-path edge matrix and six-version compatibility matrix
remain historical evidence. Browser UI, Windows-native acceptance and current
upstream-main validation were not rerun. The old full-matrix finding still
includes 16 isolated outer-edge omissions per path with gutter 1; the interior
quick scan does not supersede that limitation. GitHub CI is configured but has
not run remotely because the repository has not been published.
