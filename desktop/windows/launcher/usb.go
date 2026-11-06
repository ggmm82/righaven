package main

import (
	"bufio"
	"errors"
	"fmt"
	"io"
	"regexp"
	"strings"
)

// USB runs usbipd-win, which attaches USB devices of Windows to the WSL virtual machine.
// The interface lets tests replace the real program.
type USB interface {
	Output(args ...string) (string, error)
	// Elevated runs usbipd with administrator rights (one Windows prompt).
	Elevated(args ...string) error
	// Install installs usbipd-win with winget.
	Install() error
}

var usbTool USB = newUSB()

var busID = regexp.MustCompile(`^\d{1,3}-\d{1,3}(\.\d{1,3})*$`)

type usbDevice struct {
	BusID, VIDPID, Name, State string
}

// Shared devices can be attached without administrator rights; attached ones are in WSL.
func (d usbDevice) shared() bool   { return d.State != "Not shared" }
func (d usbDevice) attached() bool { return strings.HasPrefix(d.State, "Attached") }

// pcBluetooth reports the PC's own Bluetooth adapter: attached to WSL, Windows loses Bluetooth.
func (d usbDevice) pcBluetooth() bool { return strings.Contains(strings.ToLower(d.Name), "bluetooth") }

// serial reports devices that look like serial adapters or boards (the usual targets).
func (d usbDevice) serial() bool {
	name := strings.ToLower(d.Name)
	for _, hint := range []string{"uart", "serial", "ch340", "ch341", "cp210", "ftdi", "(com", "usb-serial", "esp", "arduino", "jtag", "cdc"} {
		if strings.Contains(name, hint) {
			return true
		}
	}
	return false
}

// parseUSB reads the "Connected:" table of `usbipd list`.
func parseUSB(text string) []usbDevice {
	var devices []usbDevice
	connected := false
	for _, line := range strings.Split(strings.ReplaceAll(text, "\r", ""), "\n") {
		trimmed := strings.TrimSpace(line)
		switch {
		case strings.HasPrefix(trimmed, "Connected:"):
			connected = true
			continue
		case strings.HasSuffix(trimmed, ":") && !strings.Contains(trimmed, " "):
			connected = false
			continue
		}
		fields := strings.Fields(trimmed)
		if !connected || len(fields) < 3 || !busID.MatchString(fields[0]) {
			continue
		}
		device := usbDevice{BusID: fields[0], VIDPID: fields[1]}
		rest := strings.TrimSpace(strings.TrimPrefix(strings.TrimSpace(strings.TrimPrefix(trimmed, fields[0])), fields[1]))
		for _, state := range []string{"Not shared", "Shared (forced)", "Shared", "Attached"} {
			index := strings.LastIndex(rest, " "+state)
			if index < 0 {
				continue
			}
			// Older usbipd versions print "Attached - <distribution>".
			if tail := strings.TrimSpace(rest[index:]); tail == state || state == "Attached" {
				device.State, rest = tail, strings.TrimSpace(rest[:index])
				break
			}
		}
		device.Name = rest
		devices = append(devices, device)
	}
	return devices
}

func usbList(a *App) ([]usbDevice, error) {
	text, err := usbTool.Output("list")
	if err != nil {
		return nil, fmt.Errorf("usbipd list: %w: %s", err, firstLine(text))
	}
	return parseUSB(text), nil
}

// usbAvailable checks for usbipd-win and offers to install it.
func usbAvailable(a *App, o options, out io.Writer, in io.Reader) bool {
	if _, err := usbTool.Output("--version"); err == nil {
		return true
	}
	fmt.Fprintln(out, a.T("usb_missing"))
	if o.yes || askYes(a, out, in, "usb_ask_install") {
		if err := usbTool.Install(); err == nil {
			fmt.Fprintln(out, a.T("usb_installed"))
		} else {
			fmt.Fprintf(out, a.T("usb_install_failed")+"\n", err)
		}
	}
	return false
}

func askYes(a *App, out io.Writer, in io.Reader, key string) bool {
	fmt.Fprint(out, a.T(key))
	answer, _ := bufio.NewReader(in).ReadString('\n')
	answer = strings.ToLower(strings.TrimSpace(answer))
	return answer == "s" || answer == "si" || answer == "sì" || answer == "y" || answer == "yes"
}

// attachUSB shares the device once (administrator prompt) and attaches it to WSL.
func attachUSB(a *App, device usbDevice, out io.Writer) error {
	if device.attached() {
		return nil
	}
	if !device.shared() {
		fmt.Fprintf(out, a.T("usb_bind")+"\n", device.Name)
		if err := usbTool.Elevated("bind", "--busid", device.BusID); err != nil {
			return fmt.Errorf(a.T("usb_bind_failed"), device.BusID, err)
		}
	}
	if text, err := usbTool.Output("attach", "--wsl", "--busid", device.BusID); err != nil {
		return fmt.Errorf(a.T("usb_attach_failed"), device.Name, firstLine(text))
	}
	fmt.Fprintf(out, a.T("usb_attached")+"\n", device.Name)
	return nil
}

// attachRemembered attaches the devices chosen earlier, when they are plugged in. It never
// stops RigHaven from starting.
func attachRemembered(a *App, w WSL, out io.Writer) {
	if len(a.Settings.USB) == 0 {
		return
	}
	devices, err := usbList(a)
	if err != nil {
		fmt.Fprintln(out, err)
		return
	}
	attached := false
	for _, id := range a.Settings.USB {
		found := false
		for _, device := range devices {
			if device.BusID == id {
				found = true
				if err := attachUSB(a, device, out); err != nil {
					fmt.Fprintln(out, err)
				} else {
					attached = true
				}
			}
		}
		if !found {
			fmt.Fprintf(out, a.T("usb_unplugged")+"\n", id)
		}
	}
	if attached {
		waitDeviceNodes(a, w)
	}
}

// waitDeviceNodes gives the WSL kernel a few seconds to create /dev/ttyUSB* or /dev/ttyACM*.
func waitDeviceNodes(a *App, w WSL) {
	_, _ = w.Output(root(a.Settings.Distribution, "sh", "-c",
		"i=0; while [ $i -lt 20 ]; do ls /dev/ttyUSB* /dev/ttyACM* >/dev/null 2>&1 && exit 0; i=$((i+1)); sleep 0.5; done")...)
}

// usbCommand lists the USB devices of Windows and attaches the chosen one to RigHaven:
//
//	RigHaven.exe usb            list and choose
//	RigHaven.exe usb 1-4        attach bus ID 1-4 (remembered for the next starts)
//	RigHaven.exe usb forget 1-4 stop attaching it at start
func usbCommand(a *App, o options, w WSL, out io.Writer, in io.Reader) error {
	if len(o.args) == 2 && o.args[0] == "forget" {
		kept := a.Settings.USB[:0]
		for _, id := range a.Settings.USB {
			if id != o.args[1] {
				kept = append(kept, id)
			}
		}
		a.Settings.USB = kept
		return a.save()
	}
	if !usbAvailable(a, o, out, in) {
		return nil
	}
	devices, err := usbList(a)
	if err != nil {
		return err
	}
	if len(devices) == 0 {
		fmt.Fprintln(out, a.T("usb_none"))
		return nil
	}
	choice := ""
	if len(o.args) > 0 {
		choice = o.args[0]
	} else {
		fmt.Fprintln(out, a.T("usb_list"))
		for i, device := range devices {
			marker := "  "
			if device.serial() {
				marker = "* "
			}
			fmt.Fprintf(out, "%s%2d. %-7s %s · %s\n", marker, i+1, device.BusID, device.Name, device.State)
		}
		fmt.Fprint(out, a.T("usb_choose"))
		line, _ := bufio.NewReader(in).ReadString('\n')
		choice = strings.TrimSpace(line)
		if choice == "" {
			return nil
		}
	}
	var device *usbDevice
	for i := range devices {
		if devices[i].BusID == choice || fmt.Sprint(i+1) == choice {
			device = &devices[i]
		}
	}
	if device == nil {
		return fmt.Errorf(a.T("usb_unknown"), choice)
	}
	ok, err := registered(w, a.Settings.Distribution)
	if err != nil {
		return err
	}
	if !ok {
		return errors.New(a.T("not_installed"))
	}
	if err := attachUSB(a, *device, out); err != nil {
		return err
	}
	remembered := false
	for _, id := range a.Settings.USB {
		remembered = remembered || id == device.BusID
	}
	if !remembered {
		a.Settings.USB = append(a.Settings.USB, device.BusID)
	}
	a.Settings.NoDevices = false
	if err := a.save(); err != nil {
		return err
	}
	waitDeviceNodes(a, w)
	nodes, _ := w.Output(root(a.Settings.Distribution, "sh", "-c", "ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true")...)
	if strings.TrimSpace(nodes) == "" {
		fmt.Fprintln(out, a.T("usb_no_node"))
		return nil
	}
	fmt.Fprintf(out, a.T("usb_nodes")+"\n", strings.Join(strings.Fields(nodes), ", "))
	// A running RigHaven offers the new port after its runtime is refreshed.
	if reachable(a.Listen()) && ready(a) {
		fmt.Fprintln(out, a.T("usb_refresh"))
		if err := install(w, a, out); err != nil {
			return err
		}
		return w.Run(nil, out, out, root(a.Settings.Distribution, "/usr/local/bin/righaven-refresh")...)
	}
	fmt.Fprintln(out, a.T("usb_next_start"))
	return nil
}

// deviceArgument is what righaven-install receives: the listed devices, "auto" (every serial
// port present in WSL, the default) or nothing.
func (a *App) deviceArgument() string {
	switch {
	case a.Settings.NoDevices:
		return ""
	case len(a.Settings.Devices) > 0:
		return strings.Join(a.Settings.Devices, ",")
	}
	return "auto"
}
