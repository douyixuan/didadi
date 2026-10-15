# Serializer performance and source preservation

Same Mac, same pinned inputs and benchmark, baseline 396904e versus this slice (Node/Vitest/jsdom). Mean milliseconds over 10 successive serializations:

| Input | Metric | Before | After |
| --- | --- | ---: | ---: |
| NVIDIA__cutlass/05.md (760 lines) | First uncached serializer pass | 31.97 | 0.60 |
| NVIDIA__cutlass/05.md (760 lines) | Same immutable document | 25.26 | 0.00 |
| NVIDIA__cutlass/05.md (760 lines) | Paragraph edit | 24.54 | 1.83 |
| NVIDIA__cutlass/05.md (760 lines) | Table edit | 28.07 | 2.14 |
| microsoft__vscode-docs/03.md (910 lines) | First uncached serializer pass | 61.04 | 1.80 |
| microsoft__vscode-docs/03.md (910 lines) | Same immutable document | 57.80 | 0.00 |
| microsoft__vscode-docs/03.md (910 lines) | Paragraph edit | 56.71 | 1.44 |

Raw samples: baseline.json and optimized.json. The baseline has no document/piece result caches. For optimized first-pass timing, the benchmark explicitly clears those two caches. The baseline fails the new 5ms/16ms regression budget as expected; the optimized suite passes. CI retains its own machine-specific samples with the roundtrip artifact.

These are serializer-only timings after view.dispatch. They exclude dispatch, DOM rendering, other plugin work and native typing/IME. They do not prove end-to-end input latency below 16ms. Same-document timing measures the full result cache. Initialization/parser cost is outside this experiment.

Final local verification: 62 frontend tests PASS, 33 pinned documents and 1586 block edits byte-exact, lossy=0, unstable=0, unrelated rewrites=0; production build PASS. Backend unchanged, Python not rerun locally for this slice; remote CI runs it. /tmp/didadi-editor-performance-tests-final-2.log and /tmp/didadi-editor-performance-build.log.

Independent reviewer /root/review_runtime_transport found no blocker. Independently ran 31 source/roundtrip/editor tests, including undo and structural edits; performance/source focused tests passed. Reviewer required serializer-only wording; applied. No native GUI/IME performance acceptance yet. No merge after automatic approval rejection.

First head aacc037 failed shared-runner CI table budget (22.82ms mean >16ms). Kept budget unchanged. Removed unnecessary separator reparse only for original-adjacent rich paragraph/heading/table/code/hr pairs already separated by a blank line; raw/list/quote/single-newline boundaries still parse. Independent static review found no merge counterexample; added table single-newline conversion, cached code conversion, indented-code adjacency and unclosed-fence boundary tests, all pass. A first boundary test used an invalid GFM fixture, then an over-specific canonical spelling assertion; both were corrected and never shipped as passing evidence. Final local full suite62 passes. New final-head CI remains to verify.
