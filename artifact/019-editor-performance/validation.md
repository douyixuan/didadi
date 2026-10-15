# Serializer performance and source preservation

Same Mac, same pinned inputs and benchmark, baseline 396904e versus this slice (Node/Vitest/jsdom). Mean milliseconds over 10 successive serializations:

| Input | Metric | Before | After |
| --- | --- | ---: | ---: |
| CUTLASS 05, 760 lines | First uncached serializer pass | 31.97 | 0.54 |
| CUTLASS 05 | Same immutable document | 25.26 | <0.01 |
| CUTLASS 05 | Paragraph edit | 24.54 | 0.67 |
| CUTLASS 05 | Table edit | 28.07 | 4.19 |
| VS Code docs 03, 910 lines | First uncached serializer pass | 61.04 | 1.37 |
| VS Code docs 03 | Same immutable document | 57.80 | <0.01 |
| VS Code docs 03 | Paragraph edit | 56.71 | 1.19 |

Raw samples: baseline.json and optimized.json. The baseline has no document/piece result caches. For optimized first-pass timing, the benchmark explicitly clears those two caches. The baseline fails the new 5ms/16ms regression budget as expected; the optimized suite passes. CI retains its own machine-specific samples with the roundtrip artifact.

These are serializer-only timings after view.dispatch. They exclude dispatch, DOM rendering, other plugin work and native typing/IME. They do not prove end-to-end input latency below 16ms. Same-document timing measures the full result cache. Initialization/parser cost is outside this experiment.

Final local verification: 60 frontend tests PASS, 33 pinned documents and 1586 block edits byte-exact, lossy=0, unstable=0, unrelated rewrites=0; production build PASS. Backend unchanged, Python not rerun locally for this slice; remote CI runs it. /tmp/didadi-editor-performance-tests-final.log and /tmp/didadi-editor-performance-build.log.

Independent reviewer /root/review_runtime_transport found no blocker. Independently ran 31 source/roundtrip/editor tests, including undo and structural edits; performance/source focused tests passed. Reviewer required serializer-only wording; applied. No native GUI/IME performance acceptance yet. No merge after automatic approval rejection.
