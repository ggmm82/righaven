package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

// RigHaven Agent: this PC at the disposal of a RigHaven server (for example on a VPS), with no
// WSL and no Docker. The owner pairs it once with a code from the server's web interface; then it
// keeps a channel open towards the server, carries out the actions asked from the page or the chat
// (Bluetooth, Wi-Fi, COM ports, home network, traffic recording) and carries a COM port or a device
// of the home network to the server's workers through tunnels. Writes to devices still need the
// owner's approval on the server; the agent itself only answers its owner's server.

const agentHeader = "X-RigHaven-Agent"

type agentConfig struct {
	Server string `json:"server"`
	Token  string `json:"token"` // protected with Windows DPAPI for this user
	Agent  string `json:"agent"`
	Name   string `json:"name"`
}

var (
	agentActions = []string{"bluetooth-scan", "wifi-scan", "com-list", "ble-inspect", "ble-read", "ble-write", "wifi-provision",
		"wifi-explore", "pc-devices", "net-listen", "lan-devices", "traffic-capture", "net-scan"}
	agentConfigPath = func() string {
		base := os.Getenv("LOCALAPPDATA")
		if base == "" {
			base, _ = os.UserConfigDir()
		}
		return filepath.Join(base, "RigHaven", "agent.json")
	}
	agentRetry   = 2 * time.Second
	agentPing    = 25 * time.Second
	scanPorts    = []int{80, 8080, 443, 1883, 8883, 502, 5555, 6053, 6668, 8008, 8009, 6466, 8001, 8002, 3000, 3001, 7000, 62078, 554}
	scanTimeout  = 600 * time.Millisecond
	codePattern  = regexp.MustCompile(`^[A-Za-z0-9-]{4,20}$`)
	httpClient   = &http.Client{Timeout: 30 * time.Second}
	errNotLinked = errors.New("not linked")
)

func loadAgentConfig() (agentConfig, error) {
	var config agentConfig
	data, err := os.ReadFile(agentConfigPath())
	if err != nil {
		return config, errNotLinked
	}
	if err := json.Unmarshal(data, &config); err != nil || config.Server == "" || config.Token == "" {
		return config, errNotLinked
	}
	token, err := unprotectSecret(config.Token)
	if err != nil {
		return config, fmt.Errorf("the saved access cannot be read on this account: pair again (%v)", err)
	}
	config.Token = token
	return config, nil
}

func saveAgentConfig(config agentConfig) error {
	protected, err := protectSecret(config.Token)
	if err != nil {
		return err
	}
	config.Token = protected
	data, _ := json.MarshalIndent(config, "", "  ")
	if err := os.MkdirAll(filepath.Dir(agentConfigPath()), 0o700); err != nil {
		return err
	}
	return os.WriteFile(agentConfigPath(), data, 0o600)
}

func normalizeServer(server string) string {
	server = strings.TrimRight(strings.TrimSpace(server), "/")
	if server != "" && !strings.HasPrefix(server, "http://") && !strings.HasPrefix(server, "https://") {
		server = "https://" + server
	}
	return server
}

// agentLink exchanges the pairing code for this PC's own access.
func agentLink(a *App, server, code string) (agentConfig, error) {
	server = normalizeServer(server)
	if !codePattern.MatchString(code) {
		return agentConfig{}, errors.New(a.T("agent_code"))
	}
	body, _ := json.Marshal(map[string]string{"code": code, "platform": "windows", "version": launcherVersion})
	response, err := httpClient.Post(server+"/api/webhooks/righaven-agent/pair", "application/json", bytes.NewReader(body))
	if err != nil {
		return agentConfig{}, fmt.Errorf(a.T("agent_unreachable"), server, err)
	}
	defer response.Body.Close()
	data, _ := io.ReadAll(io.LimitReader(response.Body, 1<<16))
	if response.StatusCode != http.StatusOK {
		var problem struct {
			Detail any `json:"detail"`
		}
		_ = json.Unmarshal(data, &problem)
		return agentConfig{}, fmt.Errorf(a.T("agent_refused"), response.StatusCode, problem.Detail)
	}
	var paired struct {
		Agent, Token, Name string
	}
	if err := json.Unmarshal(data, &paired); err != nil || paired.Token == "" {
		return agentConfig{}, errors.New(a.T("agent_refused_plain"))
	}
	config := agentConfig{Server: server, Token: paired.Token, Agent: paired.Agent, Name: paired.Name}
	return config, saveAgentConfig(config)
}

// agentCommand: RigHaven Agent's own commands.
//
//	agent                     pair if needed, then run
//	agent link SERVER CODE    pair this PC with a server
//	agent run                 run (used at sign-in when autostart is on)
//	agent unlink              forget the server
//	agent autostart on|off    start with Windows
func agentCommand(a *App, args []string, out io.Writer, in io.Reader) error {
	if len(args) > 0 {
		switch args[0] {
		case "link":
			if len(args) != 3 {
				return errors.New("agent link SERVER CODE")
			}
			config, err := agentLink(a, args[1], args[2])
			if err != nil {
				return err
			}
			fmt.Fprintf(out, a.T("agent_linked")+"\n", config.Name, config.Server)
			return nil
		case "unlink":
			_ = os.Remove(agentConfigPath())
			fmt.Fprintln(out, a.T("agent_unlinked"))
			return nil
		case "autostart":
			on := len(args) > 1 && args[1] == "on"
			if err := setAutostart(on); err != nil {
				return err
			}
			fmt.Fprintln(out, map[bool]string{true: a.T("agent_autostart_on"), false: a.T("agent_autostart_off")}[on])
			return nil
		case "run":
			config, err := loadAgentConfig()
			if err != nil {
				return errors.New(a.T("agent_not_linked"))
			}
			return runAgent(a, config, out, nil)
		}
	}
	config, err := loadAgentConfig()
	if errors.Is(err, errNotLinked) {
		reader := bufio.NewReader(in)
		fmt.Fprintln(out, a.T("agent_welcome"))
		fmt.Fprint(out, a.T("agent_ask_server"))
		server, _ := reader.ReadString('\n')
		fmt.Fprint(out, a.T("agent_ask_code"))
		code, _ := reader.ReadString('\n')
		if config, err = agentLink(a, strings.TrimSpace(server), strings.TrimSpace(code)); err != nil {
			return err
		}
		fmt.Fprintf(out, a.T("agent_linked")+"\n", config.Name, config.Server)
		if setAutostart(true) == nil {
			fmt.Fprintln(out, a.T("agent_autostart_on"))
		}
	} else if err != nil {
		return err
	}
	return runAgent(a, config, out, nil)
}

type agentSession struct {
	a       *App
	config  agentConfig
	conn    *wsConn
	out     io.Writer
	work    sync.Mutex // one action on the PC at a time, as the launcher does
	streams sync.Map   // stream number → net.Conn or io.ReadWriteCloser
}

// runAgent keeps the channel open, reconnecting with a growing pause; it ends when stop closes.
func runAgent(a *App, config agentConfig, out io.Writer, stop <-chan struct{}) error {
	pause := agentRetry
	for {
		header := http.Header{}
		header.Set(agentHeader, config.Token)
		conn, err := wsDial(config.Server, "/api/webhooks/righaven-agent/connect", header, 20*time.Second)
		var refused *wsRefused
		if errors.As(err, &refused) && (refused.Status == 401 || refused.Status == 403 || refused.Status == 404) {
			return errors.New(a.T("agent_revoked"))
		}
		if err == nil {
			pause = agentRetry
			fmt.Fprintf(out, a.T("agent_connected")+"\n", config.Server)
			session := &agentSession{a: a, config: config, conn: conn, out: out}
			err = session.serve(stop)
			if errors.Is(err, errAgentRevoked) {
				return errors.New(a.T("agent_revoked"))
			}
			fmt.Fprintf(out, a.T("agent_disconnected")+"\n", err)
		} else {
			fmt.Fprintf(out, a.T("agent_retry")+"\n", err, pause)
		}
		select {
		case <-stop:
			return nil
		case <-time.After(pause):
		}
		if pause *= 2; pause > time.Minute {
			pause = time.Minute
		}
	}
}

var errAgentRevoked = errors.New("revoked")

func (s *agentSession) send(value any) error {
	data, _ := json.Marshal(value)
	return s.conn.WriteText(data)
}

func (s *agentSession) serve(stop <-chan struct{}) error {
	defer s.conn.Close()
	defer s.streams.Range(func(key, value any) bool {
		value.(io.Closer).Close()
		return true
	})
	if err := s.send(map[string]any{"type": "hello", "platform": "windows", "version": launcherVersion, "actions": agentActions, "networks": localNetworks()}); err != nil {
		return err
	}
	done := make(chan struct{})
	defer close(done)
	go func() {
		ticker := time.NewTicker(agentPing)
		defer ticker.Stop()
		for {
			select {
			case <-done:
				return
			case <-stop:
				s.conn.Close()
				return
			case <-ticker.C:
				if s.send(map[string]string{"type": "ping"}) != nil {
					return
				}
			}
		}
	}()
	for {
		kind, data, err := s.conn.ReadMessage()
		if err != nil {
			return err
		}
		if kind == wsBinary {
			if len(data) < 4 {
				continue
			}
			if stream, ok := s.streams.Load(binary.BigEndian.Uint32(data)); ok {
				if _, err := stream.(io.Writer).Write(data[4:]); err != nil {
					s.closeStream(binary.BigEndian.Uint32(data), err)
				}
			}
			continue
		}
		var message struct {
			Type   string            `json:"type"`
			ID     string            `json:"id"`
			Action string            `json:"action"`
			Args   map[string]string `json:"args"`
			Stream uint32            `json:"stream"`
			Target string            `json:"target"`
		}
		if json.Unmarshal(data, &message) != nil {
			continue
		}
		switch message.Type {
		case "request":
			go func(id, action string, args map[string]string) {
				s.work.Lock()
				result := agentHandle(s.a, s.config, action, args)
				s.work.Unlock()
				_ = s.send(map[string]any{"type": "result", "id": id, "result": result})
			}(message.ID, message.Action, message.Args)
		case "open":
			go s.openStream(message.Stream, message.Target)
		case "close":
			if stream, ok := s.streams.LoadAndDelete(message.Stream); ok {
				stream.(io.Closer).Close()
			}
		}
	}
}

// openStream connects one tunnel: a COM port of this PC or a device of its private network.
func (s *agentSession) openStream(number uint32, target string) {
	var stream io.ReadWriteCloser
	var err error
	switch {
	case strings.HasPrefix(target, "com:") && comName.MatchString(strings.TrimPrefix(target, "com:")):
		stream, err = openCOM(strings.TrimPrefix(target, "com:"))
	case strings.HasPrefix(target, "tcp:"):
		host, port, splitErr := net.SplitHostPort(strings.TrimPrefix(target, "tcp:"))
		ip := net.ParseIP(host)
		if splitErr != nil || ip == nil || !(ip.IsPrivate() || ip.IsLinkLocalUnicast()) {
			err = errors.New("only devices of this PC's private network")
			break
		}
		stream, err = net.DialTimeout("tcp", net.JoinHostPort(host, port), 10*time.Second)
	default:
		err = errors.New("unknown target")
	}
	if err != nil {
		_ = s.send(map[string]any{"type": "close", "stream": number, "error": err.Error()})
		return
	}
	s.streams.Store(number, stream)
	_ = s.send(map[string]any{"type": "opened", "stream": number})
	buffer := make([]byte, 32768)
	for {
		size, err := stream.Read(buffer)
		if size > 0 {
			frame := binary.BigEndian.AppendUint32(nil, number)
			if s.conn.WriteBinary(append(frame, buffer[:size]...)) != nil {
				break
			}
		}
		if err != nil {
			break
		}
	}
	s.closeStream(number, nil)
}

func (s *agentSession) closeStream(number uint32, cause error) {
	if stream, ok := s.streams.LoadAndDelete(number); ok {
		stream.(io.Closer).Close()
		message := map[string]any{"type": "close", "stream": number}
		if cause != nil {
			message["error"] = cause.Error()
		}
		_ = s.send(message)
	}
}

// agentHandle carries out one action on this PC, without WSL: the same work as the launcher's
// host agent, with the results sent back instead of written into the distribution.
func agentHandle(a *App, config agentConfig, action string, args map[string]string) map[string]any {
	switch action {
	case "bluetooth-scan":
		bluetoothWarnings = nil
		devices, err := bluetoothScanner()
		if errors.Is(err, errBluetoothAdapter) {
			return failed(errors.New(a.T("bt_no_adapter")))
		}
		if err != nil {
			return failed(fmt.Errorf(a.T("bt_failed"), err))
		}
		return map[string]any{"ok": true, "devices": devices, "warnings": bluetoothWarnings}
	case "wifi-scan":
		networks, err := wifiScanner()
		if err != nil {
			return failed(err)
		}
		return map[string]any{"ok": true, "networks": networks}
	case "com-list":
		ports, err := comPorts()
		if err != nil {
			return failed(err)
		}
		var list []map[string]any
		for _, p := range ports {
			list = append(list, map[string]any{"name": p.Name, "label": p.Label, "bluetooth": p.bluetooth(), "shared": true})
		}
		return map[string]any{"ports": list}
	case "ble-inspect", "ble-read", "ble-write":
		return gattAction(action, args)
	case "wifi-provision":
		return provisionWifi(a, args)
	case "wifi-explore":
		return exploreSetup(a, args)
	case "pc-devices":
		return pcDevices(a)
	case "net-listen":
		return listenNetwork()
	case "lan-devices":
		return lanDevices()
	case "net-scan":
		return scanNetwork(args["network"])
	case "traffic-capture":
		return captureForServer(a, config, args)
	}
	return failed(fmt.Errorf("unknown action %q", action))
}

// captureForServer records the traffic and sends the file to the server for the owner to download.
func captureForServer(a *App, config agentConfig, args map[string]string) map[string]any {
	seconds, err := strconv.Atoi(args["seconds"])
	if err != nil || seconds < 10 || seconds > 1800 {
		return failed(errors.New(a.T("capture_seconds")))
	}
	file, err := trafficRecorder(seconds)
	if err != nil {
		return failed(fmt.Errorf(a.T("capture_failed"), err))
	}
	defer os.Remove(file)
	data, err := os.ReadFile(file)
	if err != nil {
		return failed(err)
	}
	summary, err := summarizeTraffic(data)
	if err != nil {
		return failed(fmt.Errorf(a.T("capture_failed"), err))
	}
	summary["ok"], summary["seconds"], summary["size"] = true, seconds, len(data)
	if len(data) <= 64<<20 {
		request, _ := http.NewRequest(http.MethodPut, config.Server+"/api/webhooks/righaven-agent/capture", bytes.NewReader(data))
		request.Header.Set(agentHeader, config.Token)
		request.Header.Set("Content-Type", "application/octet-stream")
		upload := &http.Client{Timeout: 10 * time.Minute}
		if response, err := upload.Do(request); err == nil {
			response.Body.Close()
			summary["download"] = response.StatusCode == http.StatusOK
		}
	}
	return summary
}

type scannedHost struct {
	Address string `json:"address"`
	Ports   []int  `json:"ports"`
	Name    string `json:"name,omitempty"`
	Page    string `json:"page,omitempty"`
}

var scanDial = func(ctx context.Context, address string) error {
	conn, err := (&net.Dialer{Timeout: scanTimeout}).DialContext(ctx, "tcp", address)
	if err == nil {
		conn.Close()
	}
	return err
}

// scanNetwork tries the usual ports of IoT devices, TVs and phones on each address of one private
// network of this PC and reads the home page of those with a web page: the server identifies them.
func scanNetwork(value string) map[string]any {
	_, network, err := net.ParseCIDR(value)
	if err != nil || network.IP.To4() == nil || !network.IP.IsPrivate() {
		return failed(errors.New("a private IPv4 network, for example 192.168.1.0/24"))
	}
	ones, bits := network.Mask.Size()
	if bits-ones > 12 {
		return failed(errors.New("network too large: at most 4096 addresses"))
	}
	base := binary.BigEndian.Uint32(network.IP.To4())
	count := uint32(1) << (bits - ones)
	var addresses []string
	for i := uint32(0); i < count; i++ {
		if count > 2 && (i == 0 || i == count-1) {
			continue
		}
		ip := make(net.IP, 4)
		binary.BigEndian.PutUint32(ip, base+i)
		addresses = append(addresses, ip.String())
	}
	type answer struct {
		address string
		port    int
		open    bool
		present bool
	}
	jobs := make(chan [2]any)
	answers := make(chan answer)
	var workers sync.WaitGroup
	for i := 0; i < 128; i++ {
		workers.Add(1)
		go func() {
			defer workers.Done()
			for job := range jobs {
				address, port := job[0].(string), job[1].(int)
				err := scanDial(context.Background(), net.JoinHostPort(address, strconv.Itoa(port)))
				refused := err != nil && strings.Contains(strings.ToLower(err.Error()), "refused")
				answers <- answer{address, port, err == nil, refused}
			}
		}()
	}
	go func() {
		for _, address := range addresses {
			for _, port := range scanPorts {
				jobs <- [2]any{address, port}
			}
		}
		close(jobs)
		workers.Wait()
		close(answers)
	}()
	found := map[string]*scannedHost{}
	for item := range answers {
		if !item.open && !item.present {
			continue
		}
		host := found[item.address]
		if host == nil {
			host = &scannedHost{Address: item.address, Ports: []int{}}
			found[item.address] = host
		}
		if item.open {
			host.Ports = append(host.Ports, item.port)
		}
	}
	var hosts []scannedHost
	for _, host := range found {
		sort.Ints(host.Ports)
		if names, err := net.LookupAddr(host.Address); err == nil && len(names) > 0 {
			host.Name = strings.TrimSuffix(names[0], ".")
		}
		for _, port := range []int{80, 8080} {
			if containsInt(host.Ports, port) {
				host.Page = homePage(host.Address, port)
				break
			}
		}
		hosts = append(hosts, *host)
	}
	sort.Slice(hosts, func(i, j int) bool {
		return binary.BigEndian.Uint32(net.ParseIP(hosts[i].Address).To4()) < binary.BigEndian.Uint32(net.ParseIP(hosts[j].Address).To4())
	})
	return map[string]any{"devices": hosts}
}

func containsInt(list []int, value int) bool {
	for _, item := range list {
		if item == value {
			return true
		}
	}
	return false
}

func homePage(address string, port int) string {
	client := &http.Client{Timeout: 2 * time.Second}
	response, err := client.Get(fmt.Sprintf("http://%s:%d/", address, port))
	if err != nil {
		return ""
	}
	defer response.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(response.Body, 8192))
	return response.Header.Get("Server") + " " + string(body)
}
