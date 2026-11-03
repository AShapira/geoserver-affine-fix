> Historical report for the initial patch. See [current validation](../validation.md) and [current performance](../performance.md).

# Performance of the affine corrections

This is a controlled comparison of **official GeoServer 3.0.2**, with its pinned
GeoTools 35.2 and ImageN 0.9.3 libraries. The benchmark runs stock code, the
GeoTools correction alone, the ImageN correction alone, and both corrections.
Every variant uses the same image digest, Java configuration, fixtures and
requests. Installed JAR hashes are checked separately for every server.

The [generated tables](../performance/measured.md) include every measured condition.
[Results and metadata](../performance/results.json), [block CSV](../performance/blocks.csv),
[per-request samples](../performance/requests.jsonl.gz) and
[pixel checks](../performance/quality.json.gz) support independent analysis.

Measured on 2026-11-03: **232,704 timed requests, zero timed-response errors,
12 fresh JVMs**, and 5,376 separate pixel checks. The host was an AMD Ryzen 9
9950X3D running Linux/WSL2, with 28 logical CPUs and 47 GiB RAM visible to WSL.
The measured run took about 40 minutes, including startup, profiling and cleanup.
All 17 fixture hashes remained unchanged and all benchmark containers were
removed. The full 9,440-request rendering reproduction also passed again,
retaining its documented 16 outer-footprint omissions per route. The Python
suite passed 27 tests, the viewer suite passed three, and the official-image
build passed the 32,448-scanline Java regression.

## Main timing results

For the core workload with gutter 1 and one client, the three-JVM medians were
8.75 → 4.66 ms for direct WMS and 9.70 → 5.74 ms for GWC MISS. Paired per-JVM
latency changes had medians of **−44.3%** (range −48.7% to −43.6%) and **−41.8%**
(range −43.9% to −36.7%), respectively. These paired percentages intentionally
use corresponding JVMs rather than the ratio of two separately aggregated
medians.

At six concurrent clients, median WMS throughput rose from **212 to 386
requests/s**, and GWC MISS from **183 to 323 requests/s**. The paired median
throughput gains were 82% and 76%; their JVM ranges were 58–105% and 58–91%.
Paired CPU time per request fell about 44% on both uncached paths at six clients.
These figures apply to the configured two-CPU server quota and synthetic core
workload, not to production capacity.

GWC HIT was effectively unchanged: the six-client paired throughput change was
−0.9%, with a −3.6% to +5.2% range. Single-client HIT latency was 1.22 → 1.14 ms,
but paired changes ranged from a 9.3% reduction to a 5.2% increase. Because hits
do not render the raster, small differences that change direction are not
evidence that the source corrections accelerate cached tile retrieval.

The secondary controls were mixed and should not be hidden:

- On 16,384-pixel sources, one-client WMS median latency fell 39–45%, but paired
  throughput improved only 18–33%. Median throughput was 61 → 75 requests/s.
  At six clients, large-source throughput improved 34–44%, below the core gain.
- At one client, 512-pixel output showed 62–70% lower median latency; 1024-pixel
  output showed 75–76% lower latency (50.0 → 12.4 ms across-JVM medians). This is
  consistent with a larger output magnifying the cost of unnecessary mask work.
- Bilinear median latency changed by −2.5% to +1.5%, but its short-block
  throughput was **4–20% lower with both corrections in all three JVM pairs**.
  Bicubic median latency ranged from 4% lower to 12% higher, while throughput
  improved 3–6%. These are one-block, 64-request controls without a dedicated
  interpolation warmup. They do not isolate JIT/tail variation from a possible
  regression. A longer warmed interpolation study is still needed before
  claiming equivalent performance on unaffected paths.

The evidence supports a repeatable nearest-rendering gain; it does **not**
establish a universal speedup or prove that every other path is unaffected.

The final two-minute load sequences completed 29,952 stock requests and 56,832
patched requests without errors. Aggregate active-load throughput was **249 →
475 requests/s**, and CPU time was **8.06 → 4.21 ms/request**. These rates divide
requests by the sum of timed block durations; small gaps for saving each block's
evidence are excluded. The sequences are a sustained-load check on the last
JVM pair, not extra independent replicates or a long-term stability test.

## Reproduce

```bash
uv sync --frozen --all-extras
uv run affine-benchmark --pull --root .runs/benchmark-3.0.2
uv run affine-benchmark-report --run .runs/benchmark-3.0.2 --output docs
```

The default run creates **three fresh JVMs and catalogs per variant**, with two
measured core rounds in each JVM. It requires four consecutive free localhost
ports, starting at 18106; change `--port` if needed. All test containers use two
CPU cores of quota, a 6 GiB memory limit and a 2 GiB maximum Java heap. They have
copied fixtures and temporary catalogs, without host directory mounts. Only one
server receives benchmark traffic at a time. Startup order rotates between JVM
replicates, and measurement order rotates/reverses between paired blocks.

All created benchmark containers are stopped and removed after use. Private
catalogs, credentials, raw JFR recordings and build outputs stay in the ignored
run directory. The report exporter selects public fields; it does not publish
credentials, request URLs, server logs or raw JFR events. Choose a fresh `--root`
for every run. `--replicates`, `--rounds`, `--profile-seconds` and `--soak-seconds`
can shorten development runs; smaller runs do not provide the same evidence.
Docker is supported through `--engine docker`, but host cgroup CPU/memory
collection currently requires a verified local Podman engine on Linux cgroup v2.
Use `--profile-seconds 0` if the selected platform cannot attach JFR.
The default profiling export expands large JFR event streams and needs additional
host RAM beyond the server processes; this full run used a 47 GiB WSL instance.
The report exporter streams those events when producing public summaries.

## Workloads and controls

- **Core:** 256 distinct interior tiles per block, equally divided among north-up,
  rotated 30° without overviews, rotated 30° with nearest overviews, and shear.
  Zooms 16, 18, 20, 22 and 24; gutters 0 and 1; 1, 6 and 12 concurrent clients;
  direct WMS, GWC MISS and GWC HIT. Each condition is measured twice per JVM.
- **Large sources:** three 16,384 × 16,384 tiled Byte GeoTIFFs, versus the core
  4096 × 4096 sources. North-up and 30° rotation, with and without nearest
  overviews. Each block uses 192 tiles over zooms 14, 16, 18, 20 and 22, gutter 1,
  all three client loads and all three routes/cache states.
- **Geometry and image content:** 224 tiles across all 14 standard fixtures,
  including rotations 0°, 15°, 30°, 45°, 75°, −30° and shear, with and without
  overviews. Checkerboard, ramp, texture and line regions are represented.
- **Interpolation controls:** bilinear and bicubic WMS requests. The GeoTools
  crop bypass is restricted to nearest interpolation, so these help identify
  unrelated run variation. They are secondary controls, with one measured block
  per condition and JVM, without a dedicated warmup of each interpolation path.
  They check response validity and performance, not interpolated pixel accuracy.
- **Output sizes:** 512 × 512 and 1024 × 1024 WMS output, plus the same one-pixel
  gutter. Like interpolation controls, these have one measured block per JVM.
- **First-use:** the first workload after catalog publication, before explicit
  renderer warmup. This is not a cold-disk test: host filesystem caches are not
  dropped or manipulated.
- **Sustained load:** a separate two-minute direct-WMS run for stock and both
  corrections at six clients, after the last JVM replicate. Its blocks do not
  count as additional independent JVMs or prove long-term stability.

## Measurement and correctness

HTTP latency covers the complete response body. Each worker reuses an HTTP
session. Timed throughput includes dispatch and lightweight PNG signature/size
validation. HTTP failures, invalid images and incorrect cache states are retained
as errors; failed requests cannot inflate successful throughput or become fast
successful responses. GWC caches are explicitly cleared before each MISS block
and primed before each HIT block. Every timed GWC response must have the expected
MISS or HIT header. Paired variants receive the same deterministic shuffled job
order. There is no network latency simulation or production traffic.

Each JVM receives six explicit WMS renderer warmup blocks before core timing
(1/6/12 clients at both gutters). The first GWC MISS block has no separate GWC
endpoint warmup; repeated core rounds include the subsequently warmed path.
HIT blocks always receive a separate priming pass. PNG decoding and
independent pixel-oracle checks run separately, outside timing. The pixel checks
cover every core, large-source and geometry workload tile at both gutters in
the first JVM replicate of all four variants. They inverse-map output pixel
centres and evaluate the unchanged synthetic source pattern, without loading an
entire large TIFF into memory. TIFF hashes are verified before and after the
run. Low-resolution overview selection can legitimately differ from a
full-resolution source-value oracle; missing-pixel counts remain independent of
that value difference. The separate [rendering regression](../validation.md) covers
footprint edges and source-value preservation in its selected cases.

At gutter 1, the benchmark's separate interior pixel checks produced:

| Variant | Checked requests | Failed responses | Missing pixels in successful images |
|---|---:|---:|---:|
| Stock | 672 | 1 | 1,542,061 |
| GeoTools only | 672 | 0 | 0 |
| ImageN only | 672 | 0 | 1,543,131 |
| Both | 672 | 0 | 0 |

The failed stock response was for a sheared fixture with overviews. It is
excluded from missing-pixel totals, not counted as a correct image. At gutter
0, the combined fix still had 8,192 missing pixels in the geometry/content
subset, reinforcing that tile-edge handling remains necessary. These checks
are distinct from both the timed-request error counts and the broader
footprint-edge regression.

Within each JVM, the report takes the median of repeated block statistics. It
then reports the median and minimum/maximum across the three independent JVMs.
Paired percentage changes compare corresponding JVM replicates. A p95 column
aggregates block p95 statistics using this same method; it is not a pooled p95.
The whisker/range is **not a confidence interval**. Individual requests and
repeated blocks are not treated as independent JVM replicates.

CPU throttling was recorded under concurrent load. Individual high-concurrency
blocks sometimes reverse median-latency rankings even while throughput improves.
Inspect p95, CPU cost and throughput alongside the median; all such blocks are
retained in the downloadable samples.

CPU time comes from the entire isolated server cgroup, including JVM background
work. It is divided by attempted requests; error counts are always reported.
Cgroup memory includes Java heap, native memory and charged filesystem cache.
Its high-water mark is not a heap-allocation measurement, and accumulated peaks
across different workloads cannot establish memory savings for one operation.

## Profiling the cause

Separate 30-second [Java Flight Recorder](https://docs.oracle.com/en/java/javase/21/docs/specs/man/jcmd.html)
`profile` recordings exercise rotated/sheared nearest WMS requests at six
clients. They run after the timed workloads and do not contribute to benchmark
latencies. The JDK's [JFR tool](https://docs.oracle.com/en/java/javase/21/docs/specs/man/jfr.html)
exports execution-stack and allocation samples for analysis. Published summaries
include inclusive method-stack counts, allocation-sample weights and GC event
counts. Stack counts overlap, and allocation weights are statistical estimates
for the JVM, not exact per-request allocation counters.

In the separate profiling run, estimated allocation per completed request was:

| Variant | Profiled requests | Estimated allocated MB/request |
|---|---:|---:|
| Stock | 3,456 | 22.81 |
| GeoTools only | 7,296 | 8.65 |
| ImageN only | 3,072 | 20.21 |
| Both | 7,104 | 8.80 |

MB here means 1,000,000 bytes. Both corrections reduced this estimate by about
61% relative to stock. These are one recording per variant, including JVM
background work and recording overhead; they are supporting evidence, not
three-replicate allocation measurements or retained-memory savings.

The stock profile's hottest sampled method was
`AffineGeneralOpImage.byteLoopBinary`: 753 of 1,651 Java execution samples
(45.6%). The synthetic source is an 8-bit grayscale image; this method processes
packed one-bit images. Together with the ROI intersection/rasterization and
mosaic stacks, this points to substantial work transforming the crop's binary
mask. The GeoTools-only profile instead spends its hot samples in ordinary
nearest rendering and TIFF decoding. Both profiles with the GeoTools correction
recorded zero execution-stack samples in that binary-affine method.
Some `CropOpImage` calls remain: skipping
this particular map-space crop does not remove all cropping from the reader or
renderer. The public profile summaries retain both leaf-method and relevant
inclusive-stack counts so this interpretation can be checked.

The source change retains the reader-selected window, bypassing the subsequent
`CoverageCrop` operation only for same-CRS rotated/sheared nearest rendering.
This avoids constructing and processing that crop's region of interest while
preserving pixels needed by the renderer. The reader still chooses a bounded
source window; the patch does not request an entire TIFF. The independent-fix
timings and profiler stacks test whether avoiding this work explains the speedup.

The ImageN change corrects rounding and empty intersections when determining
scanline bounds. It adds no new per-pixel loop. Its purpose is correct clipping
and avoiding exceptions; the tests measure whether its arithmetic has a material
end-to-end cost.

## Limits

These are synthetic, single-band Byte TIFFs on one Linux/WSL amd64 workstation,
with warm local filesystem data and an isolated temporary GWC cache. They do not
establish production capacity, remote/S3 I/O performance, native Windows or ARM
behavior, behavior under other heap/CPU limits, or support for other numeric
types, NoData/ROI combinations and reprojection. Large-source timing is useful
evidence against an obvious read-cost regression in this workload, not an I/O
trace or proof of bounded reads for every reader.

Stock responses can be fast and still wrong: missing pixels are counted
separately from request failures. The benchmark's fully interior tiles also do
not replace the footprint-edge matrix. The known **16 outer-footprint omissions
per route** remain documented, and upstream-main regression and maintainer
review are still required before submitting or shipping these candidates.
