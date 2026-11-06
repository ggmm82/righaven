# Native recipe: IoT toolkit

Discover the exact schema with `iot-cli commands`. Supported operations: `iot.capture`, `iot.send`, `iot.simulate`, `iot.inspect`, `iot.flash`, `iot.android`, `iot.obd`.

1. List the device connections of the task in the project context (ID, transport, protocol); use only those your role declares.
2. Invoke `iot-cli call OPERATION 'JSON_ARGUMENTS'` with a fresh absolute `output` directory inside `$RIGHAVEN_OUTPUT_DIR`, for example:
   - `iot-cli call capture '{"connection":"sensori","seconds":60,"output":"/…/capture-1"}'`
   - `iot-cli call capture '{"connection":"plc","register_kind":"holding","register_address":1,"register_count":10,"interval_seconds":1,"seconds":30,"output":"/…/plc-1"}'`
   - `iot-cli call send '{"connection":"plc","address":3,"values":[1],"output":"/…/send-1"}'` (approval of this exact command required)
   - `iot-cli call simulate '{"input":"/…/scenario.json","seed":7,"output":"/…/sim-1"}'`
   - `iot-cli call flash '{"connection":"esp32","input":"/…/firmware.bin","offset":"0x0","output":"/…/flash-1"}'` (approval of this file required)
   - `iot-cli call android '{"connection":"tv","command":"info","output":"/…/tv-1"}'`, then `packages`, `logcat`; `install`, `disable`, `reboot`… only as approved
   - `iot-cli call obd '{"connection":"auto","command":"codes","output":"/…/obd-1"}'`, `live` with `"pids":["RPM","SPEED","COOLANT_TEMP"]`
3. Inspect `receipt.json`, `summary.json` and the logs, not only the exit code. "not allowed" means the task write consent is missing; "harness_device_change" means the exact change was not approved: report it, never retry differently.
4. Reopen the telemetry with DuckDB or a notebook and compare it with a known expected value (a register you know, a sensor at rest, the scenario totals).
5. Populate `delivery.files`, `delivery.components`, checks and limitations with the observed evidence.

The executable minimum fixture is `scripts/acceptance_iot.py`, case `iot`: deterministic simulation, Modbus read without writes, writes refused without consent, without approval and when different from the approved command, and the approved write verified by read-back.
