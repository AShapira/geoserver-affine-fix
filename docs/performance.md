# Performance of the current fix

The current `main` implementation combines the complete affine candidate with
mask-processing optimizations. The comparison baseline is the previous
correctness-validated candidate [`c9aff37`](https://github.com/AShapira/geoserver-affine-fix/commit/c9aff37f393feb0638add12a2ce63d67f0f00d84),
not unmodified GeoServer or the earlier incomplete patch.

The [detailed report](research/mask-optimized.md) contains the method, per-JVM
variation, all raster types, north-up controls, CPU measurements, allocation
profiles, raw timing links and reproduction commands.

| Rotated raster | Baseline WMS ms | Current WMS ms | Median paired reduction |
|---|---:|---:|---:|
| RGB | 18.58 | 5.38 | 71.0% |
| RGBA | 18.60 | 6.58 | 64.8% |
| Four-band UInt16 | 51.97 | 25.45 | 51.0% |
| Float32 numeric NoData | 51.13 | 25.56 | 48.6% |
| Float32 NaN NoData | 51.89 | 25.82 | 48.7% |

These are single-client WMS measurements. Percentages are paired within each
JVM pair before aggregation, so they can differ from the ratio of the displayed
medians. The run used **62,640 timed requests, three fresh JVM pairs, three rounds,
1/6 clients and WMS/GWC MISS/GWC HIT**. Each server had a two-CPU quota, 6 GiB memory
limit and a 2 GiB maximum Java heap.

Six-client WMS throughput rises from 72.2 to 114.6 successful requests/second,
and CPU time falls from 27.81 to 17.72 ms/request. Separate sampled allocation
estimates fall from 58.57 to 27.52 MiB/request. Allocation is not retained heap
size. GWC HIT bypasses rendering and has no consistent improvement attributable
to mask processing. North-up controls change little; RGBA's paired median is
1.4% slower, with changes ranging from 2.7% slower to 0.7% faster.

The current candidate has **zero timed-response errors**. One invalid WMS response
on a north-up NaN fixture occurred in the baseline under six-client load. It is
retained in request/error counts; its cause is unknown. Successful-response
latency excludes failures, while throughput counts only successes.

The gains come from direct byte-mask writes, packed-bit nearest sampling and
safely avoiding masks for interior requests. Edge and NoData checks remain.
The [validity report](validation.md) distinguishes the passing tested matrix
from the additional, unchanged downsampling limitation found during documentation.
Performance results do not establish correctness at every resolution or a
production capacity guarantee.

The old 232,704-request study used an earlier patch. It remains available as
[historical performance evidence](history/initial-performance.md), together with
its [generated tables](performance/measured.md). Its speedups must not be used as
measurements of the current implementation.
