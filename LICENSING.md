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

See [source provenance](source/README.md), [GeoTools license](source/geotools/LICENSE.md)
and [ImageN license](source/imagen/LICENSE.md).
Keep the source distribution with each runtime distribution. Synthetic fixtures
are generated from this project's deterministic pattern, not downloaded imagery.
