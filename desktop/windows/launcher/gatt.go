package main

import (
	"errors"
	"fmt"
	"regexp"
	"strings"
	"time"
	"unicode"
)

// Bluetooth LE devices that are commanded (lamps, LED controllers, scales, boards with a BLE
// module): RigHaven reaches them through the PC's Bluetooth. Reading (services, characteristics
// and their values) is free; a write reaches the launcher only after the owner approved that exact
// write in RigHaven (the gateway checks it before asking).

var (
	bleAddress = regexp.MustCompile(`^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$`)
	bleUUID    = regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$`)
	bleValue   = regexp.MustCompile(`^(?:[0-9a-fA-F]{2})+$`)
	bleByte    = regexp.MustCompile(`^[0-9a-fA-F]{2}$`)
	gattTool   = runGATT
	gattRetry  = 2 * time.Second
)

// gattUnreachable explains Windows' "Unreachable": the device was seen but does not accept a connection now.
const gattUnreachable = "Il dispositivo non accetta il collegamento adesso (Windows: Unreachable). Succede quando non è più in modalità di " +
	"accoppiamento (molti restano in attesa solo pochi minuti, finché la luce lampeggia), quando è lontano o quando è già collegato " +
	"a un'altra app, per esempio sul telefono. Rimettilo in accoppiamento, chiudi l'app sul telefono e riprova subito."

type gattCharacteristic struct {
	UUID       string   `json:"uuid"`
	Properties []string `json:"properties"`
	Value      string   `json:"value,omitempty"`
	Text       string   `json:"text,omitempty"`
	Error      string   `json:"error,omitempty"`
}

type gattService struct {
	UUID            string               `json:"uuid"`
	Characteristics []gattCharacteristic `json:"characteristics"`
}

type gattReport struct {
	Name     string        `json:"name"`
	Services []gattService `json:"services"`
	Value    string        `json:"value,omitempty"`
	Text     string        `json:"text,omitempty"`
	// Responses: what the device notified after each command of an exchange, in order.
	Responses []string `json:"responses,omitempty"`
}

// maxExchange is how many commands one exchange sends in the same connection.
const maxExchange = 16

// gattArgs checks what the page or the chat asked before anything reaches the device.
func gattArgs(action string, args map[string]string) ([]string, error) {
	address := args["address"]
	if !bleAddress.MatchString(address) {
		return nil, fmt.Errorf("invalid Bluetooth address %q", address)
	}
	switch action {
	case "ble-inspect":
		return []string{"inspect", address}, nil
	case "ble-read", "ble-write":
		if !bleUUID.MatchString(args["service"]) || !bleUUID.MatchString(args["characteristic"]) {
			return nil, errors.New("service and characteristic must be UUIDs")
		}
		if action == "ble-read" {
			return []string{"read", address, args["service"], args["characteristic"]}, nil
		}
		if !bleValue.MatchString(args["value"]) || len(args["value"]) > 1024 {
			return nil, errors.New("the value to write must be hexadecimal bytes (at most 512)")
		}
		return []string{"write", address, args["service"], args["characteristic"], strings.ToLower(args["value"])}, nil
	case "ble-exchange":
		// Devices that answer only by notification (OBD-II adapters, serial bridges): the commands are
		// written one after the other in one connection while the notify characteristic is listened to.
		if !bleUUID.MatchString(args["service"]) || !bleUUID.MatchString(args["characteristic"]) ||
			(args["notify"] != "" && !bleUUID.MatchString(args["notify"])) {
			return nil, errors.New("service and characteristics must be UUIDs")
		}
		commands := strings.Split(strings.ToLower(args["commands"]), ",")
		if len(commands) == 0 || len(commands) > maxExchange {
			return nil, fmt.Errorf("an exchange sends from 1 to %d commands", maxExchange)
		}
		for _, command := range commands {
			if !bleValue.MatchString(command) || len(command) > 128 {
				return nil, errors.New("each command must be hexadecimal bytes (at most 64)")
			}
		}
		until := strings.ToLower(args["until"])
		if until != "" && !bleByte.MatchString(until) {
			return nil, errors.New("until must be one hexadecimal byte")
		}
		wait := 3000
		if args["wait"] != "" {
			if _, err := fmt.Sscanf(args["wait"], "%d", &wait); err != nil || wait < 200 || wait > 10000 {
				return nil, errors.New("wait must be from 200 to 10000 milliseconds")
			}
		}
		return []string{"exchange", address, args["service"], args["characteristic"], args["notify"], strings.Join(commands, ","), until, fmt.Sprint(wait)}, nil
	}
	return nil, fmt.Errorf("unknown action %q", action)
}

// printable shows a value as text when it is text (a name, a firmware version).
func printable(hexValue string) string {
	var text []rune
	for i := 0; i+1 < len(hexValue); i += 2 {
		var b byte
		if _, err := fmt.Sscanf(hexValue[i:i+2], "%02x", &b); err != nil {
			return ""
		}
		r := rune(b)
		if b == 0 && i+2 == len(hexValue) {
			break
		}
		if r > unicode.MaxASCII || !unicode.IsPrint(r) {
			return ""
		}
		text = append(text, r)
	}
	return string(text)
}

// parseGATT reads the lines of the GATT program: N|name, C|service|characteristic|properties|value|error,
// V|value, E|message.
func parseGATT(output string) (gattReport, error) {
	var report gattReport
	index := map[string]int{}
	for _, line := range strings.Split(strings.ReplaceAll(output, "\r", ""), "\n") {
		parts := strings.Split(strings.TrimSpace(line), "|")
		switch parts[0] {
		case "N":
			if len(parts) > 1 {
				report.Name = strings.Join(parts[1:], " ")
			}
		case "E":
			return report, errors.New(strings.Join(parts[1:], " "))
		case "V":
			if len(parts) > 1 {
				report.Value = parts[1]
				report.Text = printable(parts[1])
			}
		case "R":
			if len(parts) > 2 {
				report.Responses = append(report.Responses, parts[2])
			}
		case "C":
			if len(parts) < 6 {
				continue
			}
			position, ok := index[parts[1]]
			if !ok {
				position = len(report.Services)
				index[parts[1]] = position
				report.Services = append(report.Services, gattService{UUID: parts[1]})
			}
			var properties []string
			for _, p := range strings.Split(parts[3], ",") {
				if p = strings.TrimSpace(p); p != "" && p != "None" {
					properties = append(properties, p)
				}
			}
			report.Services[position].Characteristics = append(report.Services[position].Characteristics,
				gattCharacteristic{UUID: parts[2], Properties: properties, Value: parts[4], Text: printable(parts[4]), Error: strings.Join(parts[5:], " ")})
		}
	}
	return report, nil
}

func gattAction(action string, args map[string]string) map[string]any {
	command, err := gattArgs(action, args)
	if err != nil {
		return failed(err)
	}
	output, err := gattTool(command...)
	if err == nil && strings.Contains(output, "Unreachable") {
		// Devices that advertise rarely often answer at the second attempt.
		time.Sleep(gattRetry)
		output, err = gattTool(command...)
	}
	if err != nil {
		return failed(err)
	}
	report, err := parseGATT(output)
	if err != nil {
		if strings.Contains(err.Error(), "Unreachable") || strings.Contains(err.Error(), "not found or not in range") {
			return failed(errors.New(gattUnreachable))
		}
		return failed(err)
	}
	switch action {
	case "ble-inspect":
		return map[string]any{"name": report.Name, "services": report.Services}
	case "ble-read":
		return map[string]any{"value": report.Value, "text": report.Text}
	case "ble-exchange":
		texts := make([]string, len(report.Responses))
		for i, response := range report.Responses {
			texts[i] = printable(response)
		}
		return map[string]any{"responses": report.Responses, "texts": texts}
	}
	return map[string]any{"ok": true}
}
