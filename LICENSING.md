# License scope

Original tooling, tests, documentation and configuration use the root
[MIT License](LICENSE), originally copyright 2026 Alexander Shapira.

The root license does not relicense upstream material:

- GeoTools Java sources, original sources, patches, source archives and derived
  JARs retain LGPL-2.1. Preserve matching sources when distributing binaries.
- ImageN sources, patches, source archives and derived JARs retain Apache-2.0,
  including notices and modification attribution.
- Installed Python, CesiumJS and Playwright dependencies retain their package
  licenses; they are not vendored into this repository.

Each bundle includes its upstream license texts and source provenance. See
[2.28.5 source provenance](bundles/kartoza-geoserver-affine-fix/source/README.md)
and [2.28.0 notices](bundles/kartoza-geoserver-2.28.0-affine-fix/NOTICE.md).
Keep the source distribution with each runtime distribution. Synthetic fixtures
are generated from this project's deterministic pattern, not downloaded imagery.
