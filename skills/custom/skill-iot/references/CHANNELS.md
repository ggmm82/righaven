# Byte channels: serial ports, sockets and Bluetooth

A device connection that carries bytes (a local or RFC 2217 serial port, a COM port shared by an
agent, a raw TCP socket, a Bluetooth device classic or LE) reaches the task as one serial URL:
`socket://host:port`, `rfc2217://host:port` or `/dev/tty…`. The tools do not care which radio or
cable is behind it, and RigHaven does not read the bytes: the protocol is chosen by the tool.

- A Bluetooth classic device is its serial profile; a Bluetooth LE device is one write
  characteristic plus the notifications of another (the connection's optional channel profile).
  Both are opened by the agent of the PC or phone that has the device, one client at a time.
- Any tool that opens a serial URL works on it: `iot.capture` (reads, never writes), `iot.send`
  (one approved write, then the reply in the same connection: `reply_seconds`, `reply_until`
  for prompts such as `>` or `OK`), `iot.obd` (python-OBD), `iot.inspect`/`iot.flash` for ESP
  boards, or a tool of the environment that takes a pyserial URL.
- Manual commands are a session at a prompt: one `iot.send` per command, with the line end the
  device wants (`\r` for ELM327 and AT modems). Use `iot.capture` to listen without writing.
- Approvals: an approval is delivered when the task starts, so the coordinator asks it **before**
  the assignment, with **the same fields the task will send** (`harness_device_change` action
  send, `command_json` `{"payload": "ATRV\r", "encoding": "text"}` for `iot.send` payload
  `ATRV\r`): an approval in another form (hex bytes and a characteristic, for the chat) does not
  match. When the owner's zone of trust covers `send` on the connection, the task's writes need
  no single approvals and each one is recorded as such.
- One client at a time: while a task holds the device, the chat cannot open it; send the commands
  from the task instead of mixing the two.

## Recipe: ELM327 adapter, by hand

For a vehicle that does not answer standard OBD-II requests (many electric cars and microcars):

1. `iot.send` payload `ATZ\r`, `reply_until` `>`: the adapter answers `ELM327 v…`. No answer at
   all means the channel profile is wrong, or another app holds the adapter.
2. `iot.send` `ATRV\r`: battery voltage at the socket (needs no vehicle data).
3. `iot.send` `ATSP<n>\r` to fix the protocol (`6` CAN 11 bit 500k, `7` CAN 29 bit 500k, `8` CAN
   11 bit 250k, `9` CAN 29 bit 250k, typical of J1939-like microcars), `ATH1\r` to show CAN IDs.
4. `iot.send` `ATMA\r` with `reply_seconds` 5–10: the adapter lists the frames passing on the bus
   without asking anything; any byte sent afterwards stops it (`STOPPED`).
5. No frame on any protocol, while `ATRV` answers, means the socket carries power but no data on
   pins 6 and 14: a physical limit to tell the owner, not something to work around in software.

Raw frames are the manufacturer's: report IDs and repetition, do not invent meanings.
