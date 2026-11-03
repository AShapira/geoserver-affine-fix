# Project instructions

This project prepares two independent upstream contributions: ImageN affine
scanline clipping and GeoTools rotated-grid cropping. Keep remaining tile seams
and footprint-edge omissions explicit and separate from those fixes.

- Preserve source raster geometry and nearest-neighbour values.
- Target the official GeoServer 3.0.2 release and the exact libraries pinned in
  runtime/lock.json. Update evidence only from a fresh, controlled reproduction.
- Use generated synthetic fixtures and isolated lab containers. Do not use or
  alter retained benchmark services, catalogs, volumes or credentials.
- Keep generated JARs, fixture data, raw responses, passwords and build outputs
  out of Git. Preserve all upstream licenses and source provenance.
- Run `python -m unittest discover -s tests -v` and
  `node --test viewer/tests/adapter.test.mjs` for relevant changes. Runtime and
  Java changes also require the official-image build and rendering reproduction.
- Upstream forks belong in separate checkouts (the ignored upstream/ directory
  is an option). Contributions target upstream main before backports.
- Prepare concrete issue/PR drafts before requesting publication approval.
  The user handles contributor agreements and reviews the code before submission.
- Existing small-gis-demos files are historical snapshots; development belongs
  here. Do not delete or synchronize those snapshots.
