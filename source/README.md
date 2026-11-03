# Source provenance

The official GeoServer **3.0.2** runtime contains GeoTools **35.2** and
ImageN **0.9.3**. These files were fetched from their release tags and verified
byte for byte against the published Maven source archives on 2026-11-03.

| Component | Original source | Candidate change |
|---|---|---|
| GeoTools 35.2 | [GridCoverageReaderHelper](https://github.com/geotools/geotools/blob/35.2/modules/library/render/src/main/java/org/geotools/renderer/lite/gridcoverage2d/GridCoverageReaderHelper.java) | [diff](../patches/geotools.patch) |
| ImageN 0.9.3 | [AffineOpImage](https://github.com/eclipse-imagen/imagen/blob/0.9.3/modules/affine/src/main/java/org/eclipse/imagen/media/affine/AffineOpImage.java) | [diff](../patches/imagen.patch) |

Files ending in `.java.original` are unmodified upstream source; adjacent `.java`
files contain the candidate fixes. Original copyright and license notices are
preserved. Modifications were prepared by this project and are not upstream
releases or endorsements.

Complete matching source archives are available from OSGeo Maven:

- [gt-render-35.2-sources.jar](https://repo.osgeo.org/repository/release/org/geotools/gt-render/35.2/gt-render-35.2-sources.jar)
- [imagen-affine-0.9.3-sources.jar](https://repo.osgeo.org/repository/release/org/eclipse/imagen/imagen-affine/0.9.3/imagen-affine-0.9.3-sources.jar)

[runtime/lock.json](../runtime/lock.json) records the image digest, original JAR
hashes, source archive hashes, modified source hashes and regression source hash.
The builder replaces only the classes declared in the runtime lock, verifies all
other archive entries are unchanged, and keeps generated binaries outside Git. Distribute the
matching upstream source archives and these modifications with any derived
binaries, respecting the [license scope](../LICENSING.md).

The integrated fix on this repository's `main` also uses these files from the same locked ImageN 0.9.3 source archive:

- `AffineNearestOpImage.java` and `AffineGeneralOpImage.java`: retain double coordinates, including binary masks; the general operator also samples pure nearest binary masks directly.
- `AffineDescriptor.java`: initialize transformed masks with zero outside their valid domain.
- `AffineBicubicOpImage.java` and `AffineBilinearOpImage.java`: unchanged source, recompiled against the updated fraction constant.

`GridCoverageReaderHelper.java` now includes the additional `NoDataMaskOpImage`
helper class. It computes byte validity masks with primitive comparisons and
preserves unsigned NoData ranges. The coverage reader also skips a synthetic footprint
mask only for requests entirely inside the read image with a one-source-pixel guard.

The additional `patches/imagen-*.patch` files describe each modification. Adjacent
`.original` files preserve upstream source. The build manifest lists every replaced
and added class; all other archive entries remain unchanged. The wider interpolation
impact still needs upstream testing. See [current validity and limits](../docs/validation.md).
