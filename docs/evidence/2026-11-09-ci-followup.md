# Remote browser regression follow-up

Commit 71e35155ec24a93ba8df0e3394621985e40c415e, run [42578171723](https://github.com/Maxwell2048/supportops-ai/actions/runs/42578171723), finished with api success and web failure. The desktop lifecycle case waited for an action form after the former agent had lost ticket access. Thirteen other browser cases passed. The corrected test waits directly for the unavailable page and passed locally in the complete 14-case Chromium suite. Its remote run is checked independently after publication.

Fix commit 341461e9fc00b1bde16db53b750d2b0be68baa72 passed both api and web jobs in [run 42578603629](https://github.com/Maxwell2048/supportops-ai/actions/runs/42578603629). Security regression commit 9486f390733213794e81e0ee4ad7da84d8df810b independently passed both jobs in [run 42578398142](https://github.com/Maxwell2048/supportops-ai/actions/runs/42578398142).
