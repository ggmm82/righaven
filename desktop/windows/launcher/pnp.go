package main

import (
	"regexp"
	"sort"
	"strings"
)

// All the devices Windows sees (Device Manager), grouped by how they are connected, so the owner
// finds what is missing from the USB list: internal devices, hubs, Bluetooth ones. A device that
// takes only power from a USB port does not appear anywhere: it exchanges no data with the PC.

type pnpDevice struct {
	Class      string `json:"class"`
	Name       string `json:"name"`
	InstanceID string `json:"instance_id"`
	Status     string `json:"status"`
}

var (
	pnpLister = listPnPDevices
	pnpVIDPID = regexp.MustCompile(`(?i)VID_([0-9A-F]{4})&PID_([0-9A-F]{4})`)
	// Classes that are parts of Windows itself, not devices the owner plugged in.
	pnpNoise = map[string]bool{"System": true, "SoftwareDevice": true, "SoftwareComponent": true, "Volume": true, "VolumeSnapshot": true,
		"Computer": true, "Processor": true, "LegacyDriver": true, "Firmware": true, "SecurityDevices": true, "PrintQueue": true, "WPD": false}
)

func pnpBus(id string) string {
	upper := strings.ToUpper(id)
	switch {
	case strings.HasPrefix(upper, "USB\\"), strings.HasPrefix(upper, "USBSTOR\\"), strings.HasPrefix(upper, "HID\\VID_"):
		return "usb"
	case strings.HasPrefix(upper, "BTHENUM\\"), strings.HasPrefix(upper, "BTHLE\\"), strings.HasPrefix(upper, "BTHLEDEVICE\\"), strings.HasPrefix(upper, "BTH\\"):
		return "bluetooth"
	case strings.HasPrefix(upper, "ROOT\\"), strings.HasPrefix(upper, "SWD\\"), strings.HasPrefix(upper, "SW\\"):
		return "software"
	}
	return "internal"
}

// pcDevices lists the devices, marks which USB ones RigHaven can attach (they appear in usbipd).
func pcDevices(a *App) map[string]any {
	devices, err := pnpLister()
	if err != nil {
		return failed(err)
	}
	attachable := map[string]string{}
	if list, err := usbList(a); err == nil {
		for _, d := range list {
			attachable[strings.ToLower(d.VIDPID)] = d.BusID
		}
	}
	seen := map[string]bool{}
	var rows []map[string]any
	for _, d := range devices {
		bus := pnpBus(d.InstanceID)
		if strings.TrimSpace(d.Name) == "" {
			continue
		}
		if bus == "software" || pnpNoise[d.Class] {
			bus = "system" // parts of Windows itself: shown in their own closed group
		}
		row := map[string]any{"class": d.Class, "name": strings.TrimSpace(d.Name), "bus": bus, "ok": d.Status == "OK" || d.Status == ""}
		if match := pnpVIDPID.FindStringSubmatch(d.InstanceID); match != nil {
			vidpid := strings.ToLower(match[1] + ":" + match[2])
			row["vidpid"] = vidpid
			if busid, ok := attachable[vidpid]; ok {
				row["busid"] = busid
			}
		}
		key := bus + "|" + d.Class + "|" + row["name"].(string)
		if seen[key] {
			continue
		}
		seen[key] = true
		rows = append(rows, row)
	}
	order := map[string]int{"usb": 0, "bluetooth": 1, "internal": 2, "system": 3}
	sort.SliceStable(rows, func(i, j int) bool {
		if order[rows[i]["bus"].(string)] != order[rows[j]["bus"].(string)] {
			return order[rows[i]["bus"].(string)] < order[rows[j]["bus"].(string)]
		}
		return rows[i]["class"].(string)+rows[i]["name"].(string) < rows[j]["class"].(string)+rows[j]["name"].(string)
	})
	return map[string]any{"devices": rows}
}
