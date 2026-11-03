# Upstream contribution plan

Project repository published on 2026-11-03:
[AShapira/geoserver-affine-fix](https://github.com/AShapira/geoserver-affine-fix).

The reproduction targets the official GeoServer 3.0.2 release, with GeoTools
35.2 and ImageN 0.9.3. See the [validation report](validation.md) for the tested
release behavior. No upstream issues, forks, PRs or current-main regression
builds have been created by this project. Check current upstream main and
existing issues before preparing contributions; release validation does not
establish the behavior of a newer development branch.

The [performance suite](performance.md) separately tests each correction on the
release, with fresh JVM replicates, larger sources, interpolation controls and
JFR profiles. Include its measured gains, variation and limitations in the
submission evidence; it does not replace upstream-main correctness tests.

## Two independent contributions

1. ImageN `AffineOpImage.performScanlineClipping`: exclusive upper-bound rounding
   for forward/reverse increments and empty intersections. Convert the standalone
   Java regression to project tests and cover both axes, fractional/zero steps,
   supported numeric types and interpolation callers.
2. GeoTools `GridCoverageReaderHelper.cropCoverage`: same-CRS rotated/sheared
   nearest-neighbour premature cropping. Add a pixel-based renderer regression;
   preserve bounded reads, NoData/ROI and unaffected projection/interpolation paths.

Each regression must fail on its unmodified upstream branch and pass with only
the corresponding correction. Run normal Maven/QA checks. Keep remaining
gutter-0 seams and any measured footprint-edge omissions separate; no public
API changes or source TIFF transformations are intended.

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
