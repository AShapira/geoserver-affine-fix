> Historical experiment. For the integrated implementation on this repository’s `main`, see [current validation](../validation.md) and [current performance](../performance.md).

# Generated performance measurements

Completed 2026-11-03T07:54:55.243979+00:00. 232,704 timed requests; 0 errors.

3 independent JVMs per variant; 2 measured core rounds per JVM. For each JVM we take the median of its block statistics, then report the median and full range across JVMs. The p95 column is the same aggregation of block p95 values, not a pooled-request percentile. The range is not a confidence interval. CPU includes the entire server cgroup.

First-use means the first workload after catalog publication, without an explicit renderer warmup; it does not mean cold operating-system disk cache. Soak blocks are in the downloadable data, but are excluded from independent-replicate comparisons.

[Method and interpretation](../performance.md) · [Full results](results.json) · [Block CSV](blocks.csv) · [Request samples](requests.jsonl.gz) · [Pixel checks](quality.json.gz)

## core: gwc-hit, gutter 0, 1 client, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 1.18 | 1.05–1.38 | 1.41 | 807.62 | 1.04 | 0 |
| geotools | 1.16 | 1.11–1.22 | 1.38 | 821.71 | 1.06 | 0 |
| imagen | 1.27 | 1.14–1.30 | 1.63 | 735.35 | 1.18 | 0 |
| both | 1.16 | 1.14–1.39 | 1.40 | 810.57 | 1.17 | 0 |

## core: gwc-hit, gutter 0, 6 clients, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 4.60 | 4.24–5.17 | 10.56 | 1124.81 | 0.95 | 0 |
| geotools | 4.52 | 4.15–4.73 | 10.63 | 1103.91 | 0.99 | 0 |
| imagen | 4.48 | 4.41–4.49 | 10.79 | 1103.95 | 0.99 | 0 |
| both | 4.62 | 4.50–4.75 | 11.24 | 1096.37 | 1.03 | 0 |

## core: gwc-hit, gutter 0, 12 clients, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 9.11 | 9.00–9.49 | 22.94 | 1093.81 | 1.03 | 0 |
| geotools | 9.73 | 9.40–9.74 | 23.83 | 1054.03 | 1.23 | 0 |
| imagen | 9.46 | 8.78–10.28 | 24.39 | 1058.71 | 0.96 | 0 |
| both | 9.71 | 8.77–9.92 | 23.55 | 1056.58 | 1.07 | 0 |

## core: gwc-hit, gutter 1, 1 client, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 1.22 | 1.19–1.24 | 1.54 | 785.69 | 1.21 | 0 |
| geotools | 1.22 | 1.22–1.23 | 1.58 | 772.62 | 1.21 | 0 |
| imagen | 1.10 | 1.08–1.31 | 1.34 | 857.69 | 0.98 | 0 |
| both | 1.14 | 1.08–1.30 | 1.37 | 829.40 | 1.30 | 0 |

## core: gwc-hit, gutter 1, 6 clients, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 4.64 | 4.11–4.68 | 10.52 | 1099.12 | 0.85 | 0 |
| geotools | 4.70 | 4.57–4.85 | 11.08 | 1088.55 | 1.15 | 0 |
| imagen | 4.63 | 4.36–4.79 | 11.27 | 1083.45 | 0.89 | 0 |
| both | 4.41 | 4.20–4.89 | 10.36 | 1152.58 | 0.79 | 0 |

## core: gwc-hit, gutter 1, 12 clients, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 8.84 | 8.30–9.08 | 22.53 | 1138.11 | 0.85 | 0 |
| geotools | 8.71 | 8.47–8.80 | 22.35 | 1139.59 | 0.88 | 0 |
| imagen | 8.87 | 8.56–8.96 | 22.09 | 1129.69 | 0.80 | 0 |
| both | 8.56 | 8.32–8.62 | 22.34 | 1142.17 | 0.88 | 0 |

## core: gwc-miss, gutter 0, 1 client, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 9.03 | 8.86–10.36 | 19.14 | 101.62 | 15.44 | 0 |
| geotools | 5.68 | 5.54–6.59 | 11.64 | 155.67 | 10.95 | 0 |
| imagen | 9.95 | 9.46–10.18 | 17.66 | 97.22 | 15.68 | 0 |
| both | 5.59 | 5.25–6.67 | 13.75 | 155.25 | 11.40 | 0 |

## core: gwc-miss, gutter 0, 6 clients, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 12.85 | 9.84–16.09 | 86.96 | 187.01 | 11.01 | 0 |
| geotools | 6.94 | 6.86–9.02 | 68.03 | 310.36 | 7.00 | 0 |
| imagen | 12.07 | 10.61–19.98 | 88.43 | 174.23 | 12.04 | 0 |
| both | 7.01 | 6.06–8.16 | 67.12 | 308.43 | 6.88 | 0 |

## core: gwc-miss, gutter 0, 12 clients, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 83.64 | 76.85–86.97 | 108.84 | 190.02 | 10.98 | 0 |
| geotools | 17.32 | 13.32–18.57 | 94.73 | 280.24 | 7.35 | 0 |
| imagen | 87.42 | 87.15–91.14 | 124.76 | 170.52 | 12.03 | 0 |
| both | 26.76 | 14.19–32.67 | 91.41 | 320.53 | 6.80 | 0 |

## core: gwc-miss, gutter 1, 1 client, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 9.70 | 9.07–9.88 | 18.22 | 97.68 | 15.10 | 0 |
| geotools | 5.70 | 5.44–6.21 | 11.55 | 153.25 | 9.89 | 0 |
| imagen | 9.38 | 9.24–9.74 | 17.56 | 99.89 | 14.39 | 0 |
| both | 5.74 | 5.44–5.75 | 11.46 | 156.34 | 9.90 | 0 |

## core: gwc-miss, gutter 1, 6 clients, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 11.72 | 10.92–25.27 | 85.62 | 183.12 | 11.50 | 0 |
| geotools | 6.75 | 6.10–7.00 | 75.07 | 309.00 | 6.96 | 0 |
| imagen | 11.57 | 10.50–12.10 | 84.80 | 195.10 | 10.71 | 0 |
| both | 6.23 | 6.01–6.72 | 65.08 | 323.00 | 6.48 | 0 |

## core: gwc-miss, gutter 1, 12 clients, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 82.54 | 58.92–82.67 | 104.83 | 195.92 | 10.68 | 0 |
| geotools | 17.27 | 15.19–24.09 | 90.60 | 295.05 | 6.99 | 0 |
| imagen | 82.02 | 72.70–85.40 | 109.88 | 187.57 | 11.35 | 0 |
| both | 17.49 | 17.02–19.49 | 94.19 | 307.39 | 7.12 | 0 |

## core: wms, gutter 0, 1 client, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 8.79 | 8.64–9.11 | 16.77 | 109.61 | 13.42 | 0 |
| geotools | 5.14 | 5.09–5.16 | 11.79 | 166.52 | 8.88 | 0 |
| imagen | 8.74 | 8.16–9.49 | 16.69 | 107.44 | 13.04 | 0 |
| both | 5.10 | 4.76–6.03 | 12.12 | 164.88 | 9.01 | 0 |

## core: wms, gutter 0, 6 clients, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 10.83 | 9.63–17.97 | 82.81 | 219.87 | 9.58 | 0 |
| geotools | 5.88 | 5.18–6.19 | 65.67 | 365.25 | 5.78 | 0 |
| imagen | 11.09 | 9.75–11.61 | 85.11 | 211.92 | 9.83 | 0 |
| both | 5.99 | 5.76–6.24 | 63.58 | 373.36 | 5.80 | 0 |

## core: wms, gutter 0, 12 clients, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 70.58 | 68.50–76.79 | 107.24 | 202.01 | 10.47 | 0 |
| geotools | 16.33 | 13.26–17.05 | 87.68 | 374.15 | 6.04 | 0 |
| imagen | 71.08 | 66.34–76.60 | 107.08 | 210.09 | 9.92 | 0 |
| both | 22.79 | 15.13–38.57 | 76.20 | 355.00 | 6.20 | 0 |

## core: wms, gutter 1, 1 client, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 8.75 | 8.36–9.03 | 15.76 | 108.91 | 11.91 | 0 |
| geotools | 5.05 | 4.86–5.65 | 11.58 | 168.73 | 8.35 | 0 |
| imagen | 8.34 | 8.30–9.28 | 17.21 | 112.51 | 12.05 | 0 |
| both | 4.66 | 4.63–4.94 | 10.74 | 179.74 | 7.83 | 0 |

## core: wms, gutter 1, 6 clients, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 12.01 | 9.46–24.31 | 80.82 | 211.66 | 9.90 | 0 |
| geotools | 5.94 | 5.91–6.63 | 68.53 | 339.79 | 6.32 | 0 |
| imagen | 10.51 | 9.81–10.80 | 83.61 | 208.88 | 9.79 | 0 |
| both | 5.50 | 5.18–6.30 | 50.78 | 385.84 | 5.61 | 0 |

## core: wms, gutter 1, 12 clients, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 70.24 | 65.62–83.10 | 113.41 | 197.37 | 10.46 | 0 |
| geotools | 14.50 | 14.12–25.89 | 78.84 | 379.10 | 5.63 | 0 |
| imagen | 77.64 | 65.99–82.68 | 106.25 | 197.45 | 10.36 | 0 |
| both | 14.84 | 13.88–23.61 | 90.85 | 340.98 | 6.42 | 0 |

## first-use: wms, gutter 0, 1 client, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 13.29 | 13.23–13.73 | 31.77 | 58.04 | 34.43 | 0 |
| geotools | 9.91 | 9.48–10.66 | 24.58 | 79.71 | 25.10 | 0 |
| imagen | 13.56 | 12.99–15.33 | 32.09 | 54.97 | 36.20 | 0 |
| both | 9.41 | 8.50–10.05 | 25.16 | 81.09 | 24.68 | 0 |

## geometry: wms, gutter 1, 1 client, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 6.53 | 5.96–6.90 | 9.15 | 148.13 | 6.92 | 0 |
| geotools | 3.13 | 2.82–3.81 | 5.03 | 276.04 | 5.11 | 0 |
| imagen | 7.42 | 6.03–7.44 | 9.93 | 136.74 | 7.76 | 0 |
| both | 3.32 | 3.23–3.88 | 6.60 | 250.11 | 5.49 | 0 |

## geometry: wms, gutter 1, 6 clients, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 8.44 | 8.13–10.19 | 72.23 | 306.48 | 7.12 | 0 |
| geotools | 4.83 | 4.60–19.59 | 30.64 | 675.92 | 3.17 | 0 |
| imagen | 8.20 | 8.18–17.30 | 70.47 | 302.18 | 7.02 | 0 |
| both | 18.87 | 4.81–20.33 | 25.70 | 363.86 | 3.12 | 0 |

## interpolation: wms, gutter 1, 1 client, 256 px, bicubic

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 24.98 | 24.28–27.34 | 62.74 | 32.26 | 58.86 | 0 |
| geotools | 25.96 | 25.20–27.04 | 62.17 | 35.46 | 51.01 | 0 |
| imagen | 26.60 | 24.66–27.32 | 82.55 | 31.22 | 58.51 | 0 |
| both | 26.98 | 26.23–27.14 | 47.95 | 34.12 | 53.49 | 0 |

## interpolation: wms, gutter 1, 1 client, 256 px, bilinear

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 15.18 | 14.36–15.38 | 34.57 | 59.94 | 29.13 | 0 |
| geotools | 15.25 | 15.19–17.44 | 35.53 | 57.02 | 32.32 | 0 |
| imagen | 15.53 | 14.46–16.38 | 33.32 | 58.23 | 31.07 | 0 |
| both | 15.00 | 14.55–15.41 | 36.66 | 55.60 | 34.03 | 0 |

## interpolation: wms, gutter 1, 6 clients, 256 px, bicubic

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 97.24 | 90.93–99.35 | 162.54 | 67.66 | 30.84 | 0 |
| geotools | 93.91 | 90.82–98.23 | 246.97 | 61.27 | 33.64 | 0 |
| imagen | 83.63 | 78.85–86.09 | 143.27 | 81.55 | 26.08 | 0 |
| both | 95.89 | 93.34–106.00 | 194.42 | 53.05 | 38.55 | 0 |

## interpolation: wms, gutter 1, 6 clients, 256 px, bilinear

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 32.83 | 14.85–36.80 | 93.64 | 119.29 | 17.48 | 0 |
| geotools | 16.32 | 15.45–40.78 | 101.01 | 132.55 | 16.09 | 0 |
| imagen | 16.22 | 15.26–17.98 | 90.40 | 132.49 | 16.17 | 0 |
| both | 25.57 | 15.02–45.60 | 92.52 | 117.74 | 17.45 | 0 |

## large: gwc-hit, gutter 1, 1 client, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 1.14 | 1.14–1.18 | 1.34 | 824.33 | 0.56 | 0 |
| geotools | 1.18 | 1.03–1.20 | 1.38 | 810.13 | 0.54 | 0 |
| imagen | 1.09 | 1.05–1.19 | 1.28 | 860.52 | 0.54 | 0 |
| both | 1.17 | 1.13–1.34 | 1.44 | 803.89 | 0.60 | 0 |

## large: gwc-hit, gutter 1, 6 clients, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 5.81 | 5.29–6.37 | 12.09 | 926.04 | 0.60 | 0 |
| geotools | 5.79 | 5.19–5.95 | 11.76 | 961.39 | 0.54 | 0 |
| imagen | 6.26 | 5.22–6.43 | 11.38 | 904.62 | 0.59 | 0 |
| both | 5.68 | 5.50–5.86 | 12.00 | 916.26 | 0.60 | 0 |

## large: gwc-hit, gutter 1, 12 clients, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 11.70 | 9.97–12.50 | 23.65 | 930.85 | 0.55 | 0 |
| geotools | 10.63 | 10.15–12.85 | 23.58 | 1003.91 | 0.49 | 0 |
| imagen | 11.33 | 11.10–11.61 | 23.42 | 971.10 | 0.55 | 0 |
| both | 11.04 | 10.56–11.39 | 23.34 | 959.85 | 0.54 | 0 |

## large: gwc-miss, gutter 1, 1 client, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 9.94 | 8.83–9.96 | 32.73 | 60.10 | 17.49 | 0 |
| geotools | 5.74 | 5.56–6.67 | 27.45 | 77.50 | 12.91 | 0 |
| imagen | 8.94 | 8.65–11.64 | 30.59 | 64.26 | 16.76 | 0 |
| both | 6.25 | 5.29–6.62 | 27.43 | 74.15 | 13.52 | 0 |

## large: gwc-miss, gutter 1, 6 clients, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 13.71 | 13.17–22.93 | 143.59 | 109.12 | 18.49 | 0 |
| geotools | 7.20 | 6.80–9.27 | 100.63 | 147.82 | 13.48 | 0 |
| imagen | 10.27 | 9.65–28.61 | 122.18 | 117.67 | 17.05 | 0 |
| both | 7.39 | 7.28–12.91 | 98.86 | 143.29 | 14.14 | 0 |

## large: gwc-miss, gutter 1, 12 clients, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 90.18 | 84.26–94.72 | 249.33 | 107.33 | 18.77 | 0 |
| geotools | 45.43 | 24.62–67.69 | 199.00 | 130.07 | 15.64 | 0 |
| imagen | 88.70 | 83.15–94.51 | 243.26 | 111.11 | 17.96 | 0 |
| both | 22.49 | 21.14–45.99 | 198.68 | 141.92 | 14.56 | 0 |

## large: wms, gutter 1, 1 client, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 9.10 | 8.88–9.67 | 34.64 | 61.27 | 19.56 | 0 |
| geotools | 5.42 | 5.23–5.81 | 28.13 | 76.67 | 15.84 | 0 |
| imagen | 9.70 | 8.64–9.97 | 35.92 | 58.45 | 19.58 | 0 |
| both | 5.51 | 4.85–5.66 | 29.35 | 74.84 | 15.59 | 0 |

## large: wms, gutter 1, 6 clients, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 12.34 | 11.63–26.05 | 143.25 | 111.77 | 17.80 | 0 |
| geotools | 6.27 | 6.27–6.88 | 99.88 | 157.44 | 12.65 | 0 |
| imagen | 11.64 | 10.36–20.16 | 110.69 | 119.24 | 16.89 | 0 |
| both | 6.62 | 5.23–8.68 | 97.19 | 158.68 | 12.39 | 0 |

## large: wms, gutter 1, 12 clients, 256 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 82.87 | 48.96–88.73 | 205.17 | 123.22 | 16.60 | 0 |
| geotools | 9.98 | 8.69–11.26 | 186.77 | 166.69 | 12.27 | 0 |
| imagen | 85.69 | 77.20–88.94 | 239.82 | 109.09 | 18.29 | 0 |
| both | 18.85 | 12.35–30.91 | 198.84 | 144.76 | 13.71 | 0 |

## output-size: wms, gutter 1, 1 client, 512 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 17.46 | 16.31–18.40 | 28.12 | 58.83 | 26.21 | 0 |
| geotools | 5.86 | 5.39–6.58 | 15.38 | 136.03 | 8.16 | 0 |
| imagen | 16.35 | 16.26–17.47 | 30.48 | 62.84 | 25.64 | 0 |
| both | 5.60 | 5.45–6.66 | 14.37 | 142.68 | 7.81 | 0 |

## output-size: wms, gutter 1, 1 client, 1024 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 49.99 | 49.61–55.42 | 74.45 | 22.11 | 54.00 | 0 |
| geotools | 12.24 | 12.15–13.16 | 26.16 | 70.71 | 17.73 | 0 |
| imagen | 50.38 | 49.38–54.60 | 78.72 | 21.30 | 57.30 | 0 |
| both | 12.38 | 12.23–14.07 | 27.65 | 68.71 | 16.13 | 0 |

## output-size: wms, gutter 1, 6 clients, 512 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 28.16 | 20.48–30.87 | 92.65 | 125.55 | 17.25 | 0 |
| geotools | 7.21 | 5.25–7.25 | 65.14 | 294.14 | 6.70 | 0 |
| imagen | 27.20 | 25.01–35.50 | 102.64 | 112.50 | 19.03 | 0 |
| both | 7.03 | 6.40–8.40 | 42.58 | 374.22 | 6.45 | 0 |

## output-size: wms, gutter 1, 6 clients, 1024 px, nearest neighbor

| Variant | Median ms | JVM range ms | p95 ms | Requests/s | CPU ms/request | Errors |
|---|---:|---:|---:|---:|---:|---:|
| stock | 155.48 | 121.86–185.89 | 219.24 | 43.09 | 47.91 | 0 |
| geotools | 16.28 | 13.13–19.09 | 88.40 | 158.58 | 14.57 | 0 |
| imagen | 133.66 | 116.79–197.27 | 269.23 | 41.22 | 49.13 | 0 |
| both | 28.09 | 15.56–41.62 | 88.94 | 151.60 | 13.86 | 0 |
