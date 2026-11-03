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

On the mask research branch, `AffineDescriptor.java` comes from the same locked ImageN 0.9.3 archive. Its AffinePropertyGenerator explicitly initializes out-of-domain mask pixels to zero. `patches/imagen-mask.patch` records that change. The builder verifies the complete declared class replacement set, including the property generator.
