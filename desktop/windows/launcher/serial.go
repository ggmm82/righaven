package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"regexp"
	"strconv"
	"strings"
	"time"
)

// Windows serial ports (COM), including the ones Windows creates for paired Bluetooth devices
// such as OBD-II adapters, shared with RigHaven: while RigHaven runs, RigHaven.exe opens the port
// and carries it to a TCP port inside the distribution, reachable only from RigHaven's
// containers. A connection uses it as a serial port server ("raw TCP").

type comPort struct {
	Name  string `json:"name"`
	Label string `json:"label"`
	// Address is the Bluetooth address (12 hex digits) of the paired classic device behind the port.
	Address string `json:"address,omitempty"`
}

var (
	comName      = regexp.MustCompile(`^COM[0-9]{1,3}$`)
	comPorts     = listCOMPorts
	openCOM      = openSerialPort
	bridgeWait   = 10 * time.Second
	stopBridging = make(chan struct{})
)

// comTCPPort is the TCP port of a COM port inside the distribution (COM5 → 41005).
func comTCPPort(name string) int {
	number, _ := strconv.Atoi(strings.TrimPrefix(name, "COM"))
	return 41000 + number
}

func (p comPort) bluetooth() bool { return strings.Contains(strings.ToLower(p.Label), "bluetooth") }

// serialCommand lists the COM ports and shares the chosen one with RigHaven:
//
//	RigHaven.exe serial            list and choose
//	RigHaven.exe serial COM5       share COM5 (remembered)
//	RigHaven.exe serial forget COM5
func serialCommand(a *App, o options, out io.Writer, in io.Reader) error {
	if len(o.args) == 2 && o.args[0] == "forget" {
		kept := a.Settings.Serial[:0]
		for _, name := range a.Settings.Serial {
			if !strings.EqualFold(name, o.args[1]) {
				kept = append(kept, name)
			}
		}
		a.Settings.Serial = kept
		return a.save()
	}
	ports, err := comPorts()
	if err != nil {
		return fmt.Errorf(a.T("com_failed"), err)
	}
	if len(ports) == 0 {
		fmt.Fprintln(out, a.T("com_none"))
		return nil
	}
	choice := ""
	if len(o.args) > 0 {
		choice = strings.ToUpper(o.args[0])
	} else {
		fmt.Fprintln(out, a.T("com_list"))
		for i, port := range ports {
			marker := "  "
			if port.bluetooth() {
				marker = "* "
			}
			fmt.Fprintf(out, "%s%2d. %-6s %s\n", marker, i+1, port.Name, port.Label)
		}
		fmt.Fprint(out, a.T("com_choose"))
		line, _ := bufio.NewReader(in).ReadString('\n')
		choice = strings.ToUpper(strings.TrimSpace(line))
		if choice == "" {
			return nil
		}
	}
	var chosen *comPort
	for i := range ports {
		if ports[i].Name == choice || fmt.Sprint(i+1) == choice {
			chosen = &ports[i]
		}
	}
	if chosen == nil {
		return fmt.Errorf(a.T("com_unknown"), choice)
	}
	for _, name := range a.Settings.Serial {
		if name == chosen.Name {
			fmt.Fprintf(out, a.T("com_shared")+"\n", chosen.Name)
			return nil
		}
	}
	a.Settings.Serial = append(a.Settings.Serial, chosen.Name)
	if err := a.save(); err != nil {
		return err
	}
	fmt.Fprintf(out, a.T("com_shared")+"\n", chosen.Name)
	if reachable(a.Listen()) && ready(a) {
		fmt.Fprintln(out, a.T("com_restart"))
	}
	return nil
}

// startSerialBridges shares the remembered COM ports while RigHaven runs and tells RigHaven
// where to reach them. A port that is not available now is retried.
func startSerialBridges(a *App, w WSL, out io.Writer) {
	if len(a.Settings.Serial) == 0 {
		return
	}
	labels := reportSerial(a, w)
	for _, name := range a.Settings.Serial {
		go bridgeCOM(a, w, out, name)
		fmt.Fprintf(out, a.T("com_bridged")+"\n", name, labels[name])
	}
}

// reportSerial tells RigHaven which COM ports are shared and where its containers reach them.
func reportSerial(a *App, w WSL) map[string]string {
	address, _ := w.Output(root(a.Settings.Distribution, "/usr/local/bin/righaven-serial-bridge", "--address")...)
	address = strings.TrimSpace(address)
	labels := map[string]string{}
	if ports, err := comPorts(); err == nil {
		for _, port := range ports {
			labels[port.Name] = port.Label
		}
	}
	type shared struct {
		Name  string `json:"name"`
		Label string `json:"label"`
		Host  string `json:"host"`
		Port  int    `json:"port"`
	}
	var report []shared
	for _, name := range a.Settings.Serial {
		report = append(report, shared{Name: name, Label: labels[name], Host: address, Port: comTCPPort(name)})
	}
	data, _ := json.Marshal(map[string]any{"scanned_at": time.Now().UTC().Format(time.RFC3339), "ports": report})
	_ = w.Run(bytes.NewReader(data), io.Discard, io.Discard, root(a.Settings.Distribution, "/usr/local/bin/righaven-discovery", "serial")...)
	return labels
}

func bridgeCOM(a *App, w WSL, out io.Writer, name string) {
	warned := false
	for {
		select {
		case <-stopBridging:
			return
		default:
		}
		port, err := openCOM(name)
		if err != nil {
			if !warned {
				fmt.Fprintf(out, a.T("com_unavailable")+"\n", name, err)
				warned = true
			}
			time.Sleep(bridgeWait)
			continue
		}
		warned = false
		// One client at a time: the bridge ends when the client disconnects, then waits again.
		_ = w.Bridge(port, root(a.Settings.Distribution, "/usr/local/bin/righaven-serial-bridge", fmt.Sprint(comTCPPort(name)))...)
		time.Sleep(time.Second)
	}
}
