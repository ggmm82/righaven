package main

import (
	"bufio"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"regexp"
	"strings"
	"sync"
)

// A Bluetooth device as a byte channel, the same for every protocol: what the device sends is
// read, what is written reaches the device. A classic device paired in Windows already is a COM
// port; a Bluetooth LE device is carried through one write characteristic and the notifications
// of one characteristic (its "channel profile"). Tunnels open it with the target
//
//	ble:AA:BB:CC:DD:EE:FF[/service/write/notify]
//
// RigHaven never reads the bytes: protocols (OBD-II, AT commands, Modbus...) belong to the tools
// of the environment that opens the channel. One client per device at a time.

var (
	bleTarget  = regexp.MustCompile(`^([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})(?:/([0-9a-fA-F-]{36})/([0-9a-fA-F-]{36})/([0-9a-fA-F-]{36}))?$`)
	bleBusy    sync.Map // address → struct{}: the device has a client
	gattStream = startGATTStream
)

// bleChannel is where one device is reached: its address and, when known, its LE channel profile.
type bleChannel struct {
	Address, Service, Write, Notify string
}

func parseBLETarget(target string) (bleChannel, error) {
	parts := bleTarget.FindStringSubmatch(strings.TrimPrefix(target, "ble:"))
	if parts == nil || !strings.HasPrefix(target, "ble:") {
		return bleChannel{}, errors.New("Bluetooth target: ble:AA:BB:CC:DD:EE:FF[/service/write/notify]")
	}
	channel := bleChannel{Address: strings.ToUpper(parts[1])}
	if parts[2] != "" {
		for _, uuid := range parts[2:5] {
			if !bleUUID.MatchString(uuid) {
				return bleChannel{}, errors.New("the channel profile needs three UUIDs")
			}
		}
		channel.Service, channel.Write, channel.Notify = strings.ToLower(parts[2]), strings.ToLower(parts[3]), strings.ToLower(parts[4])
	}
	return channel, nil
}

// classicPort is the COM port Windows created for this paired classic device, if any.
func classicPort(address string) string {
	ports, err := comPorts()
	if err != nil {
		return ""
	}
	compact := strings.ReplaceAll(address, ":", "")
	for _, port := range ports {
		if port.Address != "" && strings.EqualFold(port.Address, compact) {
			return port.Name
		}
	}
	return ""
}

// openBluetooth opens the channel of one device: its COM port when it is a paired classic device,
// otherwise its Bluetooth LE channel.
func openBluetooth(target string) (io.ReadWriteCloser, error) {
	channel, err := parseBLETarget(target)
	if err != nil {
		return nil, err
	}
	if _, taken := bleBusy.LoadOrStore(channel.Address, struct{}{}); taken {
		return nil, errors.New("the Bluetooth device is already in use by another client: close it first")
	}
	release := func() { bleBusy.Delete(channel.Address) }
	var stream io.ReadWriteCloser
	if name := classicPort(channel.Address); name != "" {
		stream, err = openCOM(name)
	} else {
		stream, err = gattStream(channel)
	}
	if err != nil {
		release()
		return nil, err
	}
	return &releasing{ReadWriteCloser: stream, release: release}, nil
}

type releasing struct {
	io.ReadWriteCloser
	release func()
	once    sync.Once
}

func (r *releasing) Close() error {
	err := r.ReadWriteCloser.Close()
	r.once.Do(r.release)
	return err
}

// helperStream speaks to the GATT helper running in stream mode: lines "W|hex" go to the device,
// lines "R|hex" are what it notified, "S|service|write|notify" says which channel was opened and
// "E|message" ends it with an error.
type helperStream struct {
	in     io.WriteCloser
	lines  *bufio.Scanner
	stop   func() error
	buffer []byte
	mu     sync.Mutex
}

func newHelperStream(in io.WriteCloser, out io.Reader, stop func() error) (*helperStream, error) {
	stream := &helperStream{in: in, lines: bufio.NewScanner(out), stop: stop}
	stream.lines.Buffer(make([]byte, 64*1024), 1<<20)
	// The helper answers S| once the channel is open (or E| when it cannot open it).
	for stream.lines.Scan() {
		line := strings.TrimSpace(stream.lines.Text())
		switch {
		case strings.HasPrefix(line, "S|"):
			return stream, nil
		case strings.HasPrefix(line, "E|"):
			_ = stream.Close()
			message := strings.TrimPrefix(line, "E|")
			if strings.Contains(message, "Unreachable") || strings.Contains(message, "not found or not in range") {
				return nil, errors.New(gattUnreachable)
			}
			return nil, errors.New(message)
		}
	}
	_ = stream.Close()
	return nil, errors.New("the Bluetooth helper stopped before opening the channel")
}

func (s *helperStream) Read(buffer []byte) (int, error) {
	for len(s.buffer) == 0 {
		if !s.lines.Scan() {
			return 0, io.EOF
		}
		line := strings.TrimSpace(s.lines.Text())
		switch {
		case strings.HasPrefix(line, "R|"):
			data, err := hex.DecodeString(strings.TrimPrefix(line, "R|"))
			if err == nil {
				s.buffer = data
			}
		case strings.HasPrefix(line, "E|"):
			return 0, errors.New(strings.TrimPrefix(line, "E|"))
		}
	}
	size := copy(buffer, s.buffer)
	s.buffer = s.buffer[size:]
	return size, nil
}

func (s *helperStream) Write(data []byte) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, err := fmt.Fprintf(s.in, "W|%x\n", data); err != nil {
		return 0, err
	}
	return len(data), nil
}

func (s *helperStream) Close() error {
	_ = s.in.Close() // the helper ends when its input ends
	if s.stop != nil {
		return s.stop()
	}
	return nil
}
