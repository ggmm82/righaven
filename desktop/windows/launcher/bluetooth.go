package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"sort"
	"strconv"
	"strings"
	"time"
)

// btDevice is one Bluetooth device seen by the PC: nearby (Low Energy or classic), paired, or a
// paired serial port (COM) such as an OBD-II adapter.
type btDevice struct {
	Name    string `json:"name"`
	Address string `json:"address,omitempty"`
	Kind    string `json:"kind"` // ble, classic, serial
	Paired  bool   `json:"paired"`
	Port    string `json:"port,omitempty"`
	Signal  *int   `json:"signal,omitempty"`
	// Present says the device was heard during this search; Windows also lists devices it remembers.
	Present bool `json:"present"`
	// Connected says a paired device is connected to the PC now (headphones playing, a mouse in use).
	Connected bool `json:"connected,omitempty"`
	// Company is the Bluetooth company identifier in the manufacturer data (hex), when the device sends one.
	Company string `json:"company,omitempty"`
	Hint    string `json:"hint,omitempty"`
	// ServiceData holds what a Bluetooth LE sensor broadcasts (16-bit UUID → hex), decoded by RigHaven.
	ServiceData map[string]string `json:"service_data,omitempty"`
}

// bluetoothScanner runs the platform search; tests replace it.
var bluetoothScanner = scanBluetooth

// bluetoothWarnings holds what part of the last search could not do (for example the sensor
// readings), so the page can say it instead of showing a list that only looks complete.
var bluetoothWarnings []string

// errBluetoothAdapter means Windows has no working Bluetooth adapter (off, missing, or given to WSL).
var errBluetoothAdapter = errors.New("no Bluetooth adapter")

// hint tells what a device probably is and how RigHaven can use it.
func (d btDevice) hint() string {
	name := strings.ToLower(d.Name)
	switch {
	case strings.Contains(name, "obd") || strings.Contains(name, "elm327") || strings.Contains(name, "v-link") || strings.Contains(name, "vgate"):
		return "obd"
	case strings.HasPrefix(name, "ty") || strings.Contains(name, "tuya") || strings.Contains(name, "smart life"):
		return "tuya"
	case strings.Contains(name, "esp32") || strings.Contains(name, "esp-") || strings.Contains(name, "esphome"):
		return "esp32"
	case strings.HasPrefix(name, "mj_") || strings.HasPrefix(name, "lywsd") || strings.Contains(name, "xiaomi") || strings.Contains(name, "mi "):
		return "xiaomi"
	case strings.Contains(name, "shelly"):
		return "shelly"
	case strings.Contains(name, "tv") || strings.Contains(name, "bravia") || strings.Contains(name, "android"):
		return "tv"
	}
	return ""
}

func parseBluetooth(raw []byte) ([]btDevice, error) {
	raw = bytes.TrimSpace(bytes.TrimPrefix(raw, []byte{0xEF, 0xBB, 0xBF}))
	if len(raw) == 0 || string(raw) == "null" {
		return nil, nil
	}
	if raw[0] == '{' { // PowerShell prints a single object without brackets
		raw = append(append([]byte{'['}, raw...), ']')
	}
	var devices []btDevice
	if err := json.Unmarshal(raw, &devices); err != nil {
		return nil, err
	}
	// One row per device: what Windows remembers and what was heard now are merged by address.
	index := map[string]int{}
	var unique []btDevice
	for _, d := range devices {
		d.Name = strings.TrimSpace(d.Name)
		d.Address = strings.ToUpper(d.Address)
		if d.Name == "" && d.Address == "" {
			continue
		}
		key := d.Address
		if d.Address == "" || d.Port != "" {
			key = d.Kind + "|" + d.Port + "|" + d.Name
		}
		at, ok := index[key]
		if !ok {
			index[key] = len(unique)
			unique = append(unique, d)
			continue
		}
		u := &unique[at]
		u.Present, u.Paired, u.Connected = u.Present || d.Present, u.Paired || d.Paired, u.Connected || d.Connected
		if u.Name == "" {
			u.Name = d.Name
		}
		if u.Signal == nil {
			u.Signal = d.Signal
		}
		if d.Kind == "ble" {
			u.Kind = "ble"
		}
		if len(u.ServiceData) == 0 {
			u.ServiceData = d.ServiceData
		}
		if u.Company == "" {
			u.Company = d.Company
		}
	}
	for i := range unique {
		unique[i].Hint = unique[i].hint()
	}
	sort.SliceStable(unique, func(i, j int) bool {
		if unique[i].Present != unique[j].Present {
			return unique[i].Present
		}
		if unique[i].Paired != unique[j].Paired {
			return unique[i].Paired
		}
		return strings.ToLower(unique[i].Name) < strings.ToLower(unique[j].Name)
	})
	return unique, nil
}

// bluetoothCommand searches Bluetooth devices near the PC, prints them and passes them to
// RigHaven, where they appear in Connections. Nothing is paired or written to any device.
func bluetoothCommand(a *App, o options, w WSL, out io.Writer) error {
	minutes := 0
	if len(o.args) > 0 {
		value, err := strconv.Atoi(o.args[0])
		if err != nil || value < 1 || value > 1440 {
			return errors.New(a.T("bt_every"))
		}
		minutes = value
	}
	for {
		if err := bluetoothOnce(a, w, out); err != nil || minutes == 0 {
			return err
		}
		fmt.Fprintf(out, a.T("bt_next")+"\n", minutes)
		time.Sleep(time.Duration(minutes) * time.Minute)
	}
}

func bluetoothOnce(a *App, w WSL, out io.Writer) error {
	fmt.Fprintln(out, a.T("bt_searching"))
	bluetoothWarnings = nil
	devices, err := bluetoothScanner()
	for _, warning := range bluetoothWarnings {
		fmt.Fprintf(out, "  ! %s\n", warning)
	}
	if errors.Is(err, errBluetoothAdapter) {
		return errors.New(a.T("bt_no_adapter"))
	}
	if err != nil {
		return fmt.Errorf(a.T("bt_failed"), err)
	}
	if len(devices) == 0 {
		fmt.Fprintln(out, a.T("bt_none"))
	}
	for _, d := range devices {
		state := a.T("bt_nearby")
		if d.Paired {
			state = a.T("bt_paired")
		}
		where := d.Address
		if d.Port != "" {
			where = d.Port
		}
		fmt.Fprintf(out, "  %-28s %-17s %-8s %s\n", d.Name, where, d.Kind, state)
		if d.Hint != "" {
			fmt.Fprintf(out, "      → %s\n", a.T("bt_hint_"+d.Hint))
		}
		if len(d.ServiceData) > 0 {
			fmt.Fprintf(out, "      → %s\n", a.T("bt_sensor"))
		}
	}
	ok, err := registered(w, a.Settings.Distribution)
	if err != nil || !ok {
		return err
	}
	at := time.Now().UTC().Format(time.RFC3339)
	report, _ := json.Marshal(map[string]any{"scanned_at": at, "devices": devices, "warnings": bluetoothWarnings})
	// Sensor broadcasts are also appended to a history that RigHaven offers as CSV.
	var history bytes.Buffer
	for _, d := range devices {
		if len(d.ServiceData) > 0 {
			line, _ := json.Marshal(map[string]any{"at": at, "address": d.Address, "name": d.Name, "service_data": d.ServiceData})
			history.Write(append(line, '\n'))
		}
	}
	if history.Len() > 0 {
		_ = w.Run(&history, io.Discard, io.Discard, root(a.Settings.Distribution, "/usr/local/bin/righaven-discovery", "ble-history")...)
	}
	if err := w.Run(bytes.NewReader(report), io.Discard, out, root(a.Settings.Distribution, "/usr/local/bin/righaven-discovery", "bluetooth")...); err != nil {
		return errors.New(a.T("bt_not_saved"))
	}
	fmt.Fprintln(out, a.T("bt_saved"))
	return nil
}
