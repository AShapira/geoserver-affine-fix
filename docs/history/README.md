# Historical experiments

Use [current validation](../validation.md), [current performance](../performance.md)
and the root [README](../../README.md) for the implementation on `main`.
The files below preserve earlier results rather than silently rewriting them.

| Stage | Evidence | Interpretation |
|---|---|---|
| Initial two-part patch | [Validation](initial-validation.md), [performance](initial-performance.md) | Fixed most grayscale crop loss; retained tile seams and 16 outer-footprint omissions. |
| Expanded type testing | [RGB/RGBA/UInt16/Float32](../typed-raster-tests/README.md) | Exposed opacity, NoData and small edge regressions in that initial patch. |
| Separate experiments | [Masks](../research/mask.md), [precision](../research/precision.md) | Each addressed part of the remaining problem. |
| Combined candidate | [Results](../research/combined.md) | Passed the established typed and grayscale matrices; became the optimization baseline. |
| Mask optimization | [Results](../research/mask-optimized.md) | Current implementation, now incorporated into this repository's main branch. |

All stages target the same official GeoServer 3.0.2 runtime. They are different
project patches, not different GeoServer distributions. No stage is an accepted
upstream fix. Additional zoomed-out alpha-boundary discrepancies discovered while
preparing the current README are documented in [current validation](../validation.md).
