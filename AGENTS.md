# Project instructions

This project prepares two independent upstream contributions: ImageN affine
scanline clipping and GeoTools rotated-grid cropping. Keep remaining tile seams
and footprint-edge omissions explicit and separate from those fixes.

- Preserve source raster geometry and nearest-neighbour values.
- Historical evidence under bundles/ and the original study is dated evidence,
  not proof of current upstream behavior. Never rewrite it with a new test run.
- Use generated synthetic fixtures and isolated lab containers. Do not use or
  alter retained benchmark services, catalogs, volumes or credentials.
- Keep generated JARs, fixture data, raw responses, passwords and build outputs
  out of Git. Preserve all upstream licenses and source provenance.
- Run `python -m unittest discover -s tests -v`, each bundle's startup tests,
  and `node --test viewer/tests/adapter.test.mjs` for relevant changes.
- Upstream forks belong in separate checkouts (the ignored upstream/ directory
  is an option). Contributions target upstream main before backports.
- Prepare concrete issue/PR drafts before requesting publication approval.
  The user handles contributor agreements and reviews the code before submission.
- Existing small-gis-demos files are historical snapshots; development belongs
  here. Do not delete or synchronize those snapshots.
