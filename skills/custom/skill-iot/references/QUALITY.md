# Quality: IoT toolkit

- A capture is a sample: report its window, rate and gaps; do not generalise beyond it.
- Units and scales: Modbus registers are raw integers; apply the documented scale and offset and keep the mapping as a source.
- Timestamps are UTC from the capturing container; device timestamps in payloads may differ: say which you used.
- Writes: show what was written (`written.json`), the read-back or the observed effect, and who consented (the task grant).
- Firmware: the delivery names the image, its SHA-256, the board identity before flashing and the verification result; behaviour is proven only by observing the board afterwards.
- Simulation: list the assumptions (baselines, profiles, failure rates, events) next to every conclusion and keep the scenario JSON as a source.
