# Pinned local generation worker

On 2026-11-09, a separate worker process used local Ollama 0.33.3 and an isolated synthetic PostgreSQL schema. It retrieved an indexed support article, sent only synthetic input to `huihui_ai/qwen3.5-abliterated:4b` with digest `9acbd90c2645120ea1e4a5fe7ec9c4fe000e547ccebc8a24f950315d582003e6`, validated its citation and stored a succeeded job. The model reported an Apache-2.0 license locally; provenance and production suitability have not been independently assessed.

After adding model provenance recording, two attempts failed safely with invalid_citation and invalid_output. A third succeeded with one validated citation and recorded the configured provider, model and digest. The successful response classified an access issue as bug and high priority. These examples demonstrate variability and are not an evaluation dataset. Every disposable schema was removed. The model service started for this check was stopped afterwards.

Fourteen focused generator tests passed, including digest checks before and after inference and rejection of model changes. The full backend suite passed 303 tests with zero skips. The local development migration from 0007 to 0008 preserved counts in 14 existing tables. Real deployment, model quality, license provenance and adversarial model behavior remain open.
