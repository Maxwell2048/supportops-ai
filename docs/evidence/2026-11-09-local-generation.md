# Local generation compatibility check

On 2026-11-09, an existing local Ollama 0.33.3 installation ran a synthetic prompt using `huihui_ai/qwen3.5-abliterated:4b`, digest `9acbd90c2645120ea1e4a5fe7ec9c4fe000e547ccebc8a24f950315d582003e6`. The model reported an Apache-2.0 license in its local metadata. License provenance and suitability for production were not independently assessed.

The first call timed out while the model was cold. The second returned a provider error; the local runner reported that it could not parse the structured-output grammar. The adapter was changed to omit length and array-count restrictions from the model-facing schema while preserving full Pydantic validation on the returned data. A subsequent synthetic call returned structured output with a quotation matching the supplied synthetic chunk and version. It classified a sign-in issue as billing and suggested high priority. This single example demonstrates a quality problem and is not an accuracy measurement.

The focused generation suite passed 11 tests, including rejection of an oversized response after schema simplification. The full backend suite passed 300 tests with zero skips. The worker remains configured to use the mock provider. Real-model end-to-end worker operation, injection evaluation, model selection and quality assessment remain outstanding.
