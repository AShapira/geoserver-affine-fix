# Upstream contribution plan

Project repository published on 2026-11-03:
[AShapira/geoserver-affine-fix](https://github.com/AShapira/geoserver-affine-fix).

The reproduction targets the official GeoServer 3.0.2 release, with GeoTools
35.2 and ImageN 0.9.3. See the [validation report](validation.md) for the tested
release behavior. No upstream issues, forks, PRs or current-main regression
builds have been created by this project. Check current upstream main and
existing issues before preparing contributions; release validation does not
establish the behavior of a newer development branch.

This repository's `main` now contains the integrated mask, precision and performance
changes. The established release matrix passes, including its former footprint-edge
omissions. Additional zoomed-out alpha-boundary mismatches remain, unchanged from
the pre-optimization candidate; see [current validation](validation.md).

The [current performance report](performance.md) compares the optimized code with
the previous correctness-validated candidate. Earlier component ablations remain
historical evidence. Include measured gains, variation and limitations in submission
evidence; they do not replace upstream-main correctness tests.

## Two upstream codebases

1. ImageN `AffineOpImage.performScanlineClipping`: exclusive upper-bound rounding
   for forward/reverse increments and empty intersections. Convert the standalone
   Java regression to project tests and cover both axes, fractional/zero steps,
   supported numeric types and interpolation callers. The integrated candidate also
   changes mask extension, pixel-center output bounds, coordinate/fraction precision
   and packed nearest sampling; split these into reviewable changes and test the
   wider interpolation impact.
2. GeoTools `GridCoverageReaderHelper.cropCoverage`: same-CRS rotated/sheared
   nearest-neighbour premature cropping. Add a pixel-based renderer regression;
   preserve bounded reads, NoData/ROI and unaffected projection/interpolation paths.
   Include the lazy NoData mask, unsigned-range handling and conservative interior
   shortcut, with direct and end-to-end regressions.

Each regression must fail on its unmodified upstream branch and pass with only
the corresponding correction. Run normal Maven/QA checks. Track the known
downsampling alpha-boundary discrepancy explicitly; do not describe the release
matrix as proof for all resolutions. No public API changes or source TIFF
transformations are intended.

## Submission and human review

Prepare compact synthetic reproductions and concrete issue/PR drafts first.
Recheck duplicates and the contribution instructions before publication.
GeoTools uses developer-list discussion, a Jira issue and a PR targeting main;
ImageN uses a GitHub issue and PR targeting main. The user selected submission
through AShapira, with review and publication approval before external writes.
The user handles Eclipse contributor coverage, any required OSGeo agreement,
account verification and appropriate employer authorization. Explain all changes
and disclose AI assistance according to the current project policies.

References checked during the planning investigation:

- [GeoTools contribution instructions](https://github.com/geotools/geotools/blob/main/CONTRIBUTING.md)
- [GeoTools Jira and communication](https://docs.geotools.org/latest/developer/communication.html)
- [ImageN contribution instructions](https://github.com/eclipse-imagen/imagen/blob/main/CONTRIBUTING.md)
- [GeoServer AI policy](https://geoserver.org/ai/)
- [Eclipse handbook](https://www.eclipse.org/projects/handbook/)

After acceptance, track ImageN release, GeoTools dependency adoption/release,
GeoServer release and official packaging. Verify an official binary with the
reproduction before calling it fixed in a shipped version. Request compatible
backports after main acceptance. Maintainers control release timing.
