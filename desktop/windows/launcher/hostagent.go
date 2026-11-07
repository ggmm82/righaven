package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"
	"sync"
	"time"
)

// The host agent carries out on the PC the actions asked from the RigHaven page (Connections):
// Bluetooth search, USB peripherals, COM ports, Matter. The page writes a request into the
// distribution, the agent picks it up every two seconds while RigHaven.exe runs and writes the
// result back. The click on the page is the owner's request; Windows still asks its own
// permission where it requires one.

type hostRequest struct {
	ID     string            `json:"id"`
	Action string            `json:"action"`
	Args   map[string]string `json:"args"`
}

var hostActions = []string{"bluetooth-scan", "wifi-scan", "usb-list", "usb-install", "usb-attach", "usb-detach", "com-list", "com-share", "matter-enable", "matter-disable", "ble-inspect", "ble-read", "ble-write", "ble-exchange", "wifi-provision", "wifi-explore", "pc-devices", "net-listen", "traffic-capture", "lan-devices"}

var (
	hostMutex  sync.Mutex
	hostPoll   = 2 * time.Second
	restartApp = restartLauncher
)

func runHostAgent(a *App, w WSL, out io.Writer, stop <-chan struct{}) {
	for {
		select {
		case <-stop:
			return
		default:
		}
		for _, request := range pollHost(a, w) {
			go func(request hostRequest) {
				hostMutex.Lock()
				defer hostMutex.Unlock()
				result := handleHost(a, w, out, request)
				data, _ := json.Marshal(result)
				_ = w.Run(bytes.NewReader(data), io.Discard, io.Discard, root(a.Settings.Distribution, "/usr/local/bin/righaven-host", "result", request.ID)...)
				if result["restart"] == true {
					restartApp(a, w, out)
				}
			}(request)
		}
		time.Sleep(hostPoll)
	}
}

func pollHost(a *App, w WSL) []hostRequest {
	matter := "false"
	if a.Settings.Matter {
		matter = "true"
	}
	text, err := w.Output(root(a.Settings.Distribution, "/usr/local/bin/righaven-host", "poll", "windows", strings.Join(hostActions, ","), matter)...)
	if err != nil {
		return nil
	}
	var requests []hostRequest
	scanner := bufio.NewScanner(strings.NewReader(text))
	for scanner.Scan() {
		var request hostRequest
		if json.Unmarshal([]byte(strings.TrimSpace(scanner.Text())), &request) == nil && request.ID != "" {
			requests = append(requests, request)
		}
	}
	return requests
}

func failed(err error) map[string]any { return map[string]any{"error": err.Error()} }

func handleHost(a *App, w WSL, out io.Writer, request hostRequest) map[string]any {
	quiet := io.Discard
	switch request.Action {
	case "bluetooth-scan":
		if err := bluetoothOnce(a, w, quiet); err != nil {
			if devices, listErr := usbList(a); listErr == nil {
				for _, d := range devices {
					if d.pcBluetooth() && d.attached() {
						return failed(errors.New(a.T("bt_no_adapter")))
					}
				}
			}
			return failed(err)
		}
		return map[string]any{"ok": true}
	case "wifi-scan":
		count, err := wifiOnce(a, w)
		if err != nil {
			return failed(err)
		}
		return map[string]any{"ok": true, "networks": count}
	case "usb-list", "usb-install":
		if request.Action == "usb-install" {
			if err := usbTool.Install(); err != nil {
				return failed(fmt.Errorf(a.T("usb_install_failed"), err))
			}
		}
		if _, err := usbTool.Output("--version"); err != nil {
			return map[string]any{"usbipd": false}
		}
		devices, err := usbList(a)
		if err != nil {
			return failed(err)
		}
		var list []map[string]any
		for _, d := range devices {
			list = append(list, map[string]any{"busid": d.BusID, "vidpid": d.VIDPID, "name": d.Name, "state": d.State, "serial": d.serial(), "attached": d.attached(), "pc_bluetooth": d.pcBluetooth()})
		}
		return map[string]any{"usbipd": true, "devices": list}
	case "usb-attach":
		devices, err := usbList(a)
		if err != nil {
			return failed(err)
		}
		for _, d := range devices {
			if d.BusID != request.Args["busid"] {
				continue
			}
			if d.pcBluetooth() && request.Args["confirm"] != "yes" {
				return failed(fmt.Errorf(a.T("usb_pc_bluetooth"), d.Name))
			}
			if err := attachUSB(a, d, quiet); err != nil {
				return failed(err)
			}
			if !contains(a.Settings.USB, d.BusID) {
				a.Settings.USB = append(a.Settings.USB, d.BusID)
			}
			a.Settings.NoDevices = false
			_ = a.save()
			waitDeviceNodes(a, w)
			nodes, _ := w.Output(root(a.Settings.Distribution, "sh", "-c", "ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true")...)
			if err := install(w, a, quiet); err != nil {
				return failed(err)
			}
			_ = w.Run(nil, quiet, quiet, root(a.Settings.Distribution, "/usr/local/bin/righaven-refresh")...)
			return map[string]any{"ok": true, "ports": strings.Fields(nodes)}
		}
		return failed(fmt.Errorf(a.T("usb_unknown"), request.Args["busid"]))
	case "usb-detach":
		busid := request.Args["busid"]
		kept := a.Settings.USB[:0]
		for _, id := range a.Settings.USB {
			if id != busid {
				kept = append(kept, id)
			}
		}
		a.Settings.USB = kept
		_ = a.save()
		if text, err := usbTool.Output("detach", "--busid", busid); err != nil {
			return failed(fmt.Errorf(a.T("usb_detach_failed"), busid, fmt.Errorf("%v: %s", err, firstLine(strings.TrimSpace(text)))))
		}
		return map[string]any{"ok": true}
	case "com-list":
		ports, err := comPorts()
		if err != nil {
			return failed(err)
		}
		var list []map[string]any
		for _, p := range ports {
			list = append(list, map[string]any{"name": p.Name, "label": p.Label, "bluetooth": p.bluetooth(), "shared": contains(a.Settings.Serial, p.Name)})
		}
		return map[string]any{"ports": list}
	case "com-share":
		name := request.Args["name"]
		if !comName.MatchString(name) {
			return failed(fmt.Errorf(a.T("com_unknown"), name))
		}
		if !contains(a.Settings.Serial, name) {
			a.Settings.Serial = append(a.Settings.Serial, name)
			_ = a.save()
			go bridgeCOM(a, w, quiet, name)
		}
		reportSerial(a, w)
		return map[string]any{"ok": true}
	case "lan-devices":
		return lanDevices()
	case "net-listen":
		return listenNetwork()
	case "traffic-capture":
		return captureTraffic(a, w, request.Args)
	case "pc-devices":
		return pcDevices(a)
	case "wifi-explore":
		return exploreSetup(a, request.Args)
	case "wifi-provision":
		return provisionWifi(a, request.Args)
	case "ble-inspect", "ble-read", "ble-write", "ble-exchange":
		return gattAction(request.Action, request.Args)
	case "matter-enable":
		build, err := matterSystem.WindowsBuild()
		if err == nil && build < minimumMirroredBuild {
			return failed(fmt.Errorf(a.T("matter_windows"), build))
		}
		path := matterSystem.ConfigPath()
		current, _ := os.ReadFile(path)
		if !mirrored(string(current)) {
			if len(current) > 0 {
				_ = os.WriteFile(path+".righaven-backup", current, 0o644)
			}
			if err := os.WriteFile(path, []byte(withMirrored(string(current))), 0o644); err != nil {
				return failed(err)
			}
		}
		warning := ""
		if err := matterSystem.AllowFirewall(); err != nil {
			warning = fmt.Sprintf(a.T("matter_firewall"), err)
		}
		a.Settings.Matter = true
		if err := a.save(); err != nil {
			return failed(err)
		}
		return map[string]any{"ok": true, "restart": true, "warning": warning}
	case "matter-disable":
		a.Settings.Matter = false
		if err := a.save(); err != nil {
			return failed(err)
		}
		return map[string]any{"ok": true, "restart": true}
	}
	return failed(fmt.Errorf("unknown action %q", request.Action))
}

func contains(list []string, value string) bool {
	for _, item := range list {
		if item == value {
			return true
		}
	}
	return false
}
