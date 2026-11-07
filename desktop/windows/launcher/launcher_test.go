package main

import (
	"archive/tar"
	"bufio"
	"bytes"
	"compress/gzip"
	"context"
	"crypto/sha1"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"runtime"
	"strings"
	"testing"
	"time"
)

type call struct {
	args  []string
	stdin []byte
}

type fakeWSL struct {
	calls   []call
	outputs map[string]string
	fail    map[string]bool
	run     func(args []string, stdout io.Writer) error
}

func (f *fakeWSL) key(args []string) string { return strings.Join(args, " ") }

func (f *fakeWSL) Output(args ...string) (string, error) {
	f.calls = append(f.calls, call{args: args})
	k := f.key(args)
	if f.fail[k] {
		return f.outputs[k], errors.New("exit status 1")
	}
	return f.outputs[k], nil
}

func (f *fakeWSL) Run(stdin io.Reader, stdout, stderr io.Writer, args ...string) error {
	var data []byte
	if stdin != nil {
		data, _ = io.ReadAll(stdin)
	}
	f.calls = append(f.calls, call{args: args, stdin: data})
	if f.run != nil {
		return f.run(args, stdout)
	}
	return nil
}

func (f *fakeWSL) Start(args ...string) (*exec.Cmd, error) {
	f.calls = append(f.calls, call{args: args})
	return nil, errors.New("not supported in tests")
}

func (f *fakeWSL) Bridge(conn io.ReadWriteCloser, args ...string) error {
	f.calls = append(f.calls, call{args: args})
	data := make([]byte, 64)
	n, _ := conn.Read(data)
	_, err := conn.Write(append([]byte("echo:"), data[:n]...))
	conn.Close()
	return err
}

func (f *fakeWSL) find(prefix string) *call {
	for i := range f.calls {
		if strings.HasPrefix(f.key(f.calls[i].args), prefix) {
			return &f.calls[i]
		}
	}
	return nil
}

func portable(t *testing.T) *App {
	t.Helper()
	previous := localNetworks
	localNetworks = func() []string { return []string{"192.168.1.0/24"} }
	t.Cleanup(func() { localNetworks = previous })
	home := t.TempDir()
	app := filepath.Join(home, "app")
	must(t, os.MkdirAll(filepath.Join(app, "bin"), 0o755))
	for name, content := range map[string]string{
		"compose.yaml": "services: {}\n", "Caddyfile": ":2026 {}\n", "rootfs.tar": "tar",
		"release.json":       `{"version":"0.7.5","source_commit":"abc","files":{"compose.yaml":"x"}}`,
		"bin/righaven-start": "#!/bin/sh\r\necho start\r\n", "bin/README": "ignored",
	} {
		must(t, os.WriteFile(filepath.Join(app, name), []byte(content), 0o644))
	}
	a, err := newApp(home, "it")
	must(t, err)
	return a
}

func must(t *testing.T, err error) {
	t.Helper()
	if err != nil {
		t.Fatal(err)
	}
}

func untar(t *testing.T, data []byte) map[string]string {
	t.Helper()
	files := map[string]string{}
	reader := tar.NewReader(bytes.NewReader(data))
	for {
		header, err := reader.Next()
		if err == io.EOF {
			return files
		}
		must(t, err)
		content, _ := io.ReadAll(reader)
		files[header.Name] = string(content)
	}
}

func TestDecodeHandlesUTF16AndUTF8(t *testing.T) {
	utf16 := []byte{0xFF, 0xFE, 'R', 0, 'i', 0, 'g', 0, '\r', 0, '\n', 0, 'U', 0, 'b', 0}
	if got := decode(utf16); got != "Rig\r\nUb" {
		t.Fatalf("utf16: %q", got)
	}
	if got := decode([]byte("RigHaven\n")); got != "RigHaven\n" {
		t.Fatalf("utf8: %q", got)
	}
}

func TestDistributionsTrimsAndToleratesEmptyList(t *testing.T) {
	f := &fakeWSL{outputs: map[string]string{"--list --quiet": "Ubuntu\r\n\r\nrighaven\r\n"}}
	ok, err := registered(f, "RigHaven")
	if err != nil || !ok {
		t.Fatalf("registered = %v %v", ok, err)
	}
	f = &fakeWSL{outputs: map[string]string{"--list --quiet": "Windows Subsystem for Linux has no installed distributions."},
		fail: map[string]bool{"--list --quiet": true}}
	ok, err = registered(f, "RigHaven")
	if err != nil || ok {
		t.Fatalf("empty list = %v %v", ok, err)
	}
}

func TestFirstStartImportsTheRootfsIntoTheDataFolder(t *testing.T) {
	a := portable(t)
	f := &fakeWSL{outputs: map[string]string{"--list --quiet": "Ubuntu\n"}}
	must(t, ensureDistribution(f, a, io.Discard))
	got := f.find("--import RigHaven")
	if got == nil {
		t.Fatalf("no import: %+v", f.calls)
	}
	want := []string{"--import", "RigHaven", filepath.Join(a.Home, "data", "wsl"), filepath.Join(a.Home, "app", "rootfs.tar"), "--version", "2"}
	if strings.Join(got.args, "|") != strings.Join(want, "|") {
		t.Fatalf("import args %v", got.args)
	}
}

func TestExistingDiskIsReattachedNotReplaced(t *testing.T) {
	a := portable(t)
	must(t, os.MkdirAll(filepath.Join(a.Data, "wsl"), 0o755))
	must(t, os.WriteFile(filepath.Join(a.Data, "wsl", "ext4.vhdx"), []byte("disk"), 0o644))
	f := &fakeWSL{outputs: map[string]string{"--list --quiet": ""}}
	must(t, ensureDistribution(f, a, io.Discard))
	if f.find("--import-in-place RigHaven "+filepath.Join(a.Data, "wsl", "ext4.vhdx")) == nil || f.find("--import RigHaven") != nil {
		t.Fatalf("calls %+v", f.calls)
	}
}

func TestDistributionOfAnotherCopyIsRefused(t *testing.T) {
	a := portable(t)
	home := strings.Join(root("RigHaven", "/usr/local/bin/righaven-home"), " ")
	f := &fakeWSL{outputs: map[string]string{"--list --quiet": "RigHaven\n", home: "D:\\Altro\\RigHaven\n"}}
	err := ensureDistribution(f, a, io.Discard)
	if err == nil || !strings.Contains(err.Error(), "D:\\Altro\\RigHaven") || !strings.Contains(err.Error(), "--name") {
		t.Fatalf("err = %v", err)
	}
	f.outputs[home] = a.Home + "\n"
	must(t, ensureDistribution(f, a, io.Discard))
	if f.find("--import") != nil {
		t.Fatal("own distribution must not be imported again")
	}
}

func TestInstallSendsScriptsAndReleaseFiles(t *testing.T) {
	a := portable(t)
	a.Settings.Port = 2030
	f := &fakeWSL{}
	must(t, install(f, a, io.Discard))
	scripts := f.find(strings.Join(root("RigHaven", "tar"), " "))
	if scripts == nil {
		t.Fatalf("calls %+v", f.calls)
	}
	files := untar(t, scripts.stdin)
	if files["righaven-start"] != "#!/bin/sh\necho start\n" || len(files) != 1 {
		t.Fatalf("scripts %q", files)
	}
	installed := f.find(strings.Join(root("RigHaven", "/usr/local/bin/righaven-install", "32030", "it", "auto", "127.0.0.1", "2030", "192.168.1.0/24", "0"), " "))
	if installed == nil {
		t.Fatalf("calls %+v", f.calls)
	}
	files = untar(t, installed.stdin)
	if files["home.txt"] != a.Home+"\n" || files["compose.yaml"] != "services: {}\n" || files["release.json"] == "" || files["Caddyfile"] == "" {
		t.Fatalf("files %q", files)
	}
}

func TestProgressTranslatesMarkers(t *testing.T) {
	var out bytes.Buffer
	p := &progress{a: &App{Language: "it"}, out: &out}
	_, _ = p.Write([]byte("@@step images 3\nPulling\n@@st"))
	_, _ = p.Write([]byte("ep start\n@@ready\n"))
	if !p.ready || !strings.Contains(out.String(), "Scarico 3 immagini") || !strings.Contains(out.String(), "Avvio RigHaven") || strings.Contains(out.String(), "@@") {
		t.Fatalf("%q ready=%v", out.String(), p.ready)
	}
}

func TestSettingsArePersistedAndValidated(t *testing.T) {
	a := portable(t)
	o, err := parse([]string{"status", "--port", "2040", "--name", "RigHaven-2"}, a)
	must(t, err)
	if o.command != "status" || a.Settings.Port != 2040 || a.Settings.Distribution != "RigHaven-2" {
		t.Fatalf("%+v %+v", o, a.Settings)
	}
	must(t, a.save())
	again, err := newApp(a.Home, "en")
	must(t, err)
	if !reflect.DeepEqual(again.Settings, a.Settings) {
		t.Fatalf("saved %+v", again.Settings)
	}
	if _, err := parse([]string{"--port", "80"}, again); err == nil {
		t.Fatal("privileged port accepted")
	}
	if _, err := parse([]string{"--name", "bad name;rm"}, portable(t)); err == nil {
		t.Fatal("unsafe distribution name accepted")
	}
}

func TestMissingWSLExplainsTheOneTimeInstall(t *testing.T) {
	a := portable(t)
	f := &fakeWSL{fail: map[string]bool{"--version": true, "--status": true}}
	err := checkWSL(a, f, io.Discard, strings.NewReader("n\n"))
	if err == nil || !strings.Contains(err.Error(), "wsl --install --no-distribution") {
		t.Fatalf("err = %v", err)
	}
	f = &fakeWSL{fail: map[string]bool{"--version": true}}
	if err := checkWSL(a, f, io.Discard, strings.NewReader("")); err == nil || !strings.Contains(err.Error(), "wsl --update") {
		t.Fatalf("old wsl: %v", err)
	}
}

func TestRemoveNeedsTheTypedConfirmation(t *testing.T) {
	a := portable(t)
	f := &fakeWSL{outputs: map[string]string{"--list --quiet": "RigHaven\n"}}
	must(t, remove(a, options{}, f, io.Discard, strings.NewReader("si\n")))
	if f.find("--unregister") != nil {
		t.Fatal("removed without confirmation")
	}
	must(t, remove(a, options{}, f, io.Discard, strings.NewReader("ELIMINA\n")))
	if f.find("--unregister RigHaven") == nil || f.find(strings.Join(root("RigHaven", "/usr/local/bin/righaven-stop"), " ")) == nil {
		t.Fatalf("calls %+v", f.calls)
	}
}

func TestDoctorReportsChangedFiles(t *testing.T) {
	a := portable(t)
	var out bytes.Buffer
	must(t, doctor(a, &fakeWSL{outputs: map[string]string{"--version": "Versione WSL: 2.4.13.0\n"}}, &out))
	if !strings.Contains(out.String(), "changed or missing: compose.yaml") || !strings.Contains(out.String(), "2.4.13.0") {
		t.Fatal(out.String())
	}
}

func TestMovedFolderIsReattachedOnlyOnRequest(t *testing.T) {
	a := portable(t)
	home := strings.Join(root("RigHaven", "/usr/local/bin/righaven-home"), " ")
	f := &fakeWSL{outputs: map[string]string{"--list --quiet": "RigHaven\n", home: "Impossibile trovare il file specificato.\n"},
		fail: map[string]bool{home: true}}
	err := ensureDistribution(f, a, io.Discard)
	if err == nil || !strings.Contains(err.Error(), "RigHaven.exe repair") || f.find("--unregister") != nil {
		t.Fatalf("err = %v calls %+v", err, f.calls)
	}
	if err := reattach(f, a, options{}, io.Discard, strings.NewReader("")); err == nil {
		t.Fatal("repair without a disk in this folder")
	}
	must(t, os.MkdirAll(filepath.Join(a.Data, "wsl"), 0o755))
	must(t, os.WriteFile(filepath.Join(a.Data, "wsl", "ext4.vhdx"), []byte("disk"), 0o644))
	must(t, reattach(f, a, options{}, io.Discard, strings.NewReader("\n")))
	if f.find("--unregister") != nil {
		t.Fatal("unregistered on a bare Enter")
	}
	must(t, reattach(f, a, options{}, io.Discard, strings.NewReader("RICOLLEGA\n")))
	if f.find("--unregister RigHaven") == nil || f.find("--import-in-place RigHaven "+filepath.Join(a.Data, "wsl", "ext4.vhdx")) == nil {
		t.Fatalf("calls %+v", f.calls)
	}
}

func TestDevicesAreValidatedRememberedAndSentToTheDistribution(t *testing.T) {
	a := portable(t)
	if _, err := parse([]string{"--devices", "/dev/ttyUSB0, /dev/ttyACM1"}, a); err != nil {
		t.Fatal(err)
	}
	f := &fakeWSL{}
	must(t, install(f, a, io.Discard))
	if f.find(strings.Join(root("RigHaven", "/usr/local/bin/righaven-install", "32026", "it", "/dev/ttyUSB0,/dev/ttyACM1", "127.0.0.1", "2026", "192.168.1.0/24", "0"), " ")) == nil {
		t.Fatalf("calls %+v", f.calls)
	}
	if _, err := parse([]string{"--devices", "/dev/sda"}, portable(t)); err == nil {
		t.Fatal("a disk was accepted as a device")
	}
	if _, err := parse([]string{"--devices", "none"}, a); err != nil || a.Settings.Devices != nil || a.deviceArgument() != "" {
		t.Fatalf("none keeps %v %v", a.Settings.Devices, err)
	}
	if _, err := parse([]string{"--devices", "auto"}, a); err != nil || a.deviceArgument() != "auto" {
		t.Fatalf("auto: %q %v", a.deviceArgument(), err)
	}
	if portable(t).deviceArgument() != "auto" {
		t.Fatal("serial ports present in WSL are offered by default")
	}
}

const usbipdList = `Connected:
BUSID  VID:PID    DEVICE                                                        STATE
1-4    10c4:ea60  Silicon Labs CP210x USB to UART Bridge (COM3)                 Not shared
2-1    046d:c52b  Logitech USB Input Device, USB Input Device                   Shared
3-2    1a86:7523  USB-SERIAL CH340 (COM5)                                       Attached

Persisted:
GUID                                  DEVICE
`

type fakeUSB struct {
	list     string
	calls    [][]string
	elevated [][]string
	missing  bool
}

func (f *fakeUSB) Output(args ...string) (string, error) {
	f.calls = append(f.calls, args)
	if f.missing {
		return "", errors.New("not found")
	}
	if len(args) > 0 && args[0] == "list" {
		return f.list, nil
	}
	return "", nil
}
func (f *fakeUSB) Elevated(args ...string) error { f.elevated = append(f.elevated, args); return nil }
func (f *fakeUSB) Install() error                { return errors.New("no winget") }

func useUSB(t *testing.T, f *fakeUSB) {
	t.Helper()
	previous := usbTool
	usbTool = f
	t.Cleanup(func() { usbTool = previous })
}

func TestUsbipdListIsParsed(t *testing.T) {
	devices := parseUSB(usbipdList)
	if len(devices) != 3 {
		t.Fatalf("%+v", devices)
	}
	if devices[0].BusID != "1-4" || devices[0].State != "Not shared" || devices[0].shared() || !devices[0].serial() ||
		devices[0].Name != "Silicon Labs CP210x USB to UART Bridge (COM3)" {
		t.Fatalf("%+v", devices[0])
	}
	if !devices[1].shared() || devices[1].attached() || devices[1].serial() {
		t.Fatalf("%+v", devices[1])
	}
	if !devices[2].attached() || !devices[2].serial() {
		t.Fatalf("%+v", devices[2])
	}
	old := parseUSB("Connected:\nBUSID  VID:PID    DEVICE          STATE\n1-1    1a86:7523  CH340 (COM4)    Attached - Ubuntu\n")
	if len(old) != 1 || !old[0].attached() || old[0].Name != "CH340 (COM4)" {
		t.Fatalf("%+v", old)
	}
}

func TestUsbCommandSharesOnceAttachesAndRemembers(t *testing.T) {
	a := portable(t)
	usb := &fakeUSB{list: usbipdList}
	useUSB(t, usb)
	f := &fakeWSL{outputs: map[string]string{
		"--list --quiet": "RigHaven\n",
		strings.Join(root("RigHaven", "sh", "-c", "ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true"), " "): "/dev/ttyUSB0\n",
	}}
	var out bytes.Buffer
	must(t, usbCommand(a, options{command: "usb"}, f, &out, strings.NewReader("1\n")))
	if len(usb.elevated) != 1 || strings.Join(usb.elevated[0], " ") != "bind --busid 1-4" {
		t.Fatalf("elevated %v", usb.elevated)
	}
	attached := false
	for _, c := range usb.calls {
		attached = attached || strings.Join(c, " ") == "attach --wsl --busid 1-4"
	}
	if !attached {
		t.Fatalf("calls %v", usb.calls)
	}
	reloaded, err := newApp(a.Home, "it")
	must(t, err)
	if strings.Join(reloaded.Settings.USB, ",") != "1-4" {
		t.Fatalf("remembered %v", reloaded.Settings.USB)
	}
	if text := out.String(); !strings.Contains(text, "* ") || !strings.Contains(text, "/dev/ttyUSB0") || !strings.Contains(text, "prossimo avvio") {
		t.Fatalf("%s", text)
	}
	// Already shared: no administrator prompt; forget removes it.
	usb.elevated = nil
	must(t, usbCommand(a, options{command: "usb", args: []string{"2-1"}}, f, io.Discard, strings.NewReader("")))
	if len(usb.elevated) != 0 {
		t.Fatalf("elevated again %v", usb.elevated)
	}
	must(t, usbCommand(a, options{command: "usb", args: []string{"forget", "1-4"}}, f, io.Discard, strings.NewReader("")))
	if strings.Join(a.Settings.USB, ",") != "2-1" {
		t.Fatalf("after forget %v", a.Settings.USB)
	}
	if err := usbCommand(a, options{command: "usb", args: []string{"9-9"}}, f, io.Discard, strings.NewReader("")); err == nil {
		t.Fatal("unknown bus ID accepted")
	}
}

func TestUsbCommandOffersToInstallUsbipd(t *testing.T) {
	a := portable(t)
	useUSB(t, &fakeUSB{missing: true})
	var out bytes.Buffer
	must(t, usbCommand(a, options{command: "usb"}, &fakeWSL{}, &out, strings.NewReader("n\n")))
	if !strings.Contains(out.String(), "usbipd-win") {
		t.Fatalf("%s", out.String())
	}
}

func TestRememberedUsbIsAttachedAtStartWithoutFailing(t *testing.T) {
	a := portable(t)
	a.Settings.USB = []string{"1-4", "7-7"}
	usb := &fakeUSB{list: usbipdList}
	useUSB(t, usb)
	var out bytes.Buffer
	attachRemembered(a, &fakeWSL{}, &out)
	if len(usb.elevated) != 1 || !strings.Contains(out.String(), "7-7") {
		t.Fatalf("%v %s", usb.elevated, out.String())
	}
}

func TestProgressShowsEachImageDownload(t *testing.T) {
	var out bytes.Buffer
	p := &progress{a: &App{Language: "it"}, out: &out}
	_, _ = p.Write([]byte("@@step images 2\n@@pull 1 2 righaven-gateway\n@@pull 2 2 righaven-frontend\n@@step start\n@@ready\n"))
	text := out.String()
	if !strings.Contains(text, "Scarico 2 immagini") || !strings.Contains(text, "[1/2] righaven-gateway") || !strings.Contains(text, "[2/2] righaven-frontend") || !p.ready {
		t.Fatal(text)
	}
}

func TestForwarderCarriesConnectionsIntoTheDistribution(t *testing.T) {
	a := portable(t)
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	must(t, err)
	a.Settings.Port = listener.Addr().(*net.TCPAddr).Port
	listener.Close()
	if reachable(a.Listen()) {
		t.Skip("port in use")
	}
	f := &fakeWSL{}
	forwarder, err := forward(f, a)
	must(t, err)
	defer forwarder.Close()
	conn, err := net.Dial("tcp", forwarder.Addr().String())
	must(t, err)
	_, _ = conn.Write([]byte("GET /"))
	reply, _ := io.ReadAll(conn)
	if string(reply) != "echo:GET /" {
		t.Fatalf("%q", reply)
	}
	if f.find(strings.Join(root("RigHaven", "/usr/local/bin/righaven-relay", fmt.Sprint(a.InnerPort())), " ")) == nil {
		t.Fatalf("calls %+v", f.calls)
	}
}

func TestConsoleLinesEndWithCarriageReturn(t *testing.T) {
	var out bytes.Buffer
	w := &crlf{w: &out}
	_, _ = w.Write([]byte("uno\ndue\r\n"))
	_, _ = w.Write([]byte("tre\n"))
	if out.String() != "uno\r\ndue\r\ntre\r\n" {
		t.Fatalf("%q", out.String())
	}
}

func TestBindAddressIsConfigurableAndTheUrlNeverUsesLocalhost(t *testing.T) {
	a := portable(t)
	if a.URL() != "http://127.0.0.1:2026" || a.Listen() != "127.0.0.1:2026" || !a.Loopback() {
		t.Fatalf("default %s %s", a.URL(), a.Listen())
	}
	if _, err := parse([]string{"--bind", "192.168.1.20", "--port", "2030"}, a); err != nil {
		t.Fatal(err)
	}
	if a.URL() != "http://192.168.1.20:2030" || a.Loopback() {
		t.Fatalf("lan %s", a.URL())
	}
	f := &fakeWSL{}
	must(t, install(f, a, io.Discard))
	if f.find(strings.Join(root("RigHaven", "/usr/local/bin/righaven-install", "32030", "it", "auto", "192.168.1.20", "2030", "192.168.1.0/24", "0"), " ")) == nil {
		t.Fatalf("the login address follows the bind address: %+v", f.calls)
	}
	if _, err := parse([]string{"--bind", "0.0.0.0"}, a); err != nil || a.URL() != "http://127.0.0.1:2030" || a.Listen() != "0.0.0.0:2030" {
		t.Fatalf("all interfaces %s %s %v", a.URL(), a.Listen(), err)
	}
	if _, err := parse([]string{"--bind", "::1"}, a); err != nil || a.URL() != "http://[::1]:2030" {
		t.Fatalf("ipv6 %s %v", a.URL(), err)
	}
	if _, err := parse([]string{"--bind", "localhost"}, portable(t)); err == nil {
		t.Fatal("a name instead of an address was accepted")
	}
}

func TestDiagnosisNamesEachLeg(t *testing.T) {
	a := portable(t)
	inner := strings.Join(root("RigHaven", "/usr/local/bin/righaven-probe", "32026"), " ")
	f := &fakeWSL{outputs: map[string]string{inner: "ok-from-gateway"}}
	var out bytes.Buffer
	diagnose(a, f, &out)
	text := out.String()
	for _, want := range []string{"1. inside WSL", "   ok-from-gateway", "2. relay", "righaven-relay 32026: ok echo:GET /health/ready", "3. Windows", "ready=false"} {
		if !strings.Contains(text, want) {
			t.Fatalf("missing %q in\n%s", want, text)
		}
	}
}

func TestSearchableNetworksArePrivateAndAtMostA24(t *testing.T) {
	cases := map[string]string{"192.168.1.37/24": "192.168.1.0/24", "10.0.5.9/16": "10.0.5.0/24", "172.20.1.2/28": "172.20.1.0/28", "8.8.8.8/24": "", "fe80::1/64": ""}
	for value, want := range cases {
		ip, network, err := net.ParseCIDR(value)
		must(t, err)
		network.IP = ip
		if got := searchable(network); got != want {
			t.Fatalf("%s: %q, want %q", value, got, want)
		}
	}
	if !isVirtual("vEthernet (WSL (Hyper-V firewall))") || isVirtual("Wi-Fi") {
		t.Fatal("virtual adapter filter")
	}
}

func TestBluetoothResultsAreParsedExplainedAndPassedToRigHaven(t *testing.T) {
	devices, err := parseBluetooth([]byte("\xef\xbb\xbf" + `[{"name":"OBDII","address":"00:1d:a5:68:98:8b","kind":"classic","paired":true},
		{"name":"TY","address":"dc:23:4d:aa:bb:cc","kind":"ble","paired":false,"signal":-60},
		{"name":"Standard Serial over Bluetooth link (COM5)","port":"COM5","kind":"serial","paired":true,"address":""},
		{"name":"TY","address":"dc:23:4d:aa:bb:cc","kind":"ble","paired":false},{"name":"","address":"","kind":"ble"}]`))
	must(t, err)
	if len(devices) != 3 || devices[0].Hint != "obd" || !devices[0].Paired || devices[2].Hint != "tuya" || *devices[2].Signal != -60 {
		t.Fatalf("%+v", devices)
	}
	single, err := parseBluetooth([]byte(`{"name":"ESP32-Sensor","address":"aa","kind":"ble","paired":false}`))
	must(t, err)
	if len(single) != 1 || single[0].Hint != "esp32" {
		t.Fatalf("%+v", single)
	}
	a := portable(t)
	previous := bluetoothScanner
	bluetoothScanner = func() ([]btDevice, error) { return devices, nil }
	t.Cleanup(func() { bluetoothScanner = previous })
	f := &fakeWSL{outputs: map[string]string{"--list --quiet": "RigHaven\n"}}
	var out bytes.Buffer
	must(t, bluetoothCommand(a, options{command: "bluetooth"}, f, &out))
	saved := f.find(strings.Join(root("RigHaven", "/usr/local/bin/righaven-discovery", "bluetooth"), " "))
	if saved == nil || !strings.Contains(string(saved.stdin), `"scanned_at"`) || !strings.Contains(string(saved.stdin), "COM5") {
		t.Fatalf("calls %+v", f.calls)
	}
	if text := out.String(); !strings.Contains(text, "OBDII") || !strings.Contains(text, "adattatore OBD-II") || !strings.Contains(text, "Connessioni") {
		t.Fatalf("%s", text)
	}
}

type fakePort struct{ bytes.Buffer }

func (fakePort) Close() error { return nil }

func TestCOMPortsAreSharedRememberedAndReported(t *testing.T) {
	a := portable(t)
	previousList, previousOpen := comPorts, openCOM
	comPorts = func() ([]comPort, error) {
		return []comPort{{Name: "COM3", Label: "USB Serial Device (COM3)"}, {Name: "COM5", Label: "Standard Serial over Bluetooth link (COM5)"}}, nil
	}
	opened := make(chan string, 4)
	openCOM = func(name string) (io.ReadWriteCloser, error) { opened <- name; return &fakePort{}, nil }
	t.Cleanup(func() { comPorts, openCOM = previousList, previousOpen })
	var out bytes.Buffer
	must(t, serialCommand(a, options{command: "serial"}, &out, strings.NewReader("2\n")))
	if !strings.Contains(out.String(), "*  2. COM5") || strings.Join(a.Settings.Serial, ",") != "COM5" {
		t.Fatalf("%s %v", out.String(), a.Settings.Serial)
	}
	reloaded, err := newApp(a.Home, "it")
	must(t, err)
	if strings.Join(reloaded.Settings.Serial, ",") != "COM5" || comTCPPort("COM5") != 41005 {
		t.Fatal("not remembered")
	}
	f := &fakeWSL{outputs: map[string]string{strings.Join(root("RigHaven", "/usr/local/bin/righaven-serial-bridge", "--address"), " "): "172.18.0.1\n"}}
	startSerialBridges(a, f, io.Discard)
	if name := <-opened; name != "COM5" {
		t.Fatalf("opened %s", name)
	}
	report := f.find(strings.Join(root("RigHaven", "/usr/local/bin/righaven-discovery", "serial"), " "))
	if report == nil || !strings.Contains(string(report.stdin), `"host":"172.18.0.1","port":41005`) || !strings.Contains(string(report.stdin), "Bluetooth") {
		t.Fatalf("calls %+v", f.calls)
	}
	must(t, serialCommand(a, options{command: "serial", args: []string{"forget", "com5"}}, io.Discard, strings.NewReader("")))
	if len(a.Settings.Serial) != 0 {
		t.Fatal("forget")
	}
	if err := serialCommand(a, options{command: "serial", args: []string{"COM9"}}, io.Discard, strings.NewReader("")); err == nil {
		t.Fatal("unknown port accepted")
	}
	a.Settings.Serial = []string{"COM1;rm"}
	if a.validate() == nil {
		t.Fatal("invalid COM name accepted")
	}
}

type fakeMatter struct {
	build              int
	path               string
	firewall, shutdown int
}

func (f *fakeMatter) WindowsBuild() (int, error) { return f.build, nil }
func (f *fakeMatter) ConfigPath() string         { return f.path }
func (f *fakeMatter) AllowFirewall() error       { f.firewall++; return nil }
func (f *fakeMatter) ShutdownWSL() error         { f.shutdown++; return nil }

func TestWSLConfigGetsMirroredNetworkingKeepingTheRest(t *testing.T) {
	cases := map[string]string{
		"":                                       "[wsl2]\nnetworkingMode=mirrored\n",
		"[wsl2]\nmemory=8GB\n":                   "[wsl2]\nnetworkingMode=mirrored\nmemory=8GB\n",
		"[wsl2]\nnetworkingMode=NAT\nmemory=8GB": "[wsl2]\nnetworkingMode=mirrored\nmemory=8GB",
		"[experimental]\nsparseVhd=true\n":       "[experimental]\nsparseVhd=true\n\n[wsl2]\nnetworkingMode=mirrored\n",
	}
	for config, want := range cases {
		if got := withMirrored(config); got != want || !mirrored(got) {
			t.Fatalf("%q -> %q, want %q", config, got, want)
		}
	}
}

func TestMatterEnableAsksConfiguresAndRemembers(t *testing.T) {
	a := portable(t)
	system := &fakeMatter{build: 22631, path: filepath.Join(t.TempDir(), ".wslconfig")}
	must(t, os.WriteFile(system.path, []byte("[wsl2]\nmemory=8GB\n"), 0o644))
	previous := matterSystem
	matterSystem = system
	t.Cleanup(func() { matterSystem = previous })
	var out bytes.Buffer
	must(t, matterCommand(a, options{command: "matter", args: []string{"enable"}}, &fakeWSL{}, &out, strings.NewReader("n\n")))
	if a.Settings.Matter || system.firewall != 0 {
		t.Fatal("changed without confirmation")
	}
	must(t, matterCommand(a, options{command: "matter", args: []string{"enable"}}, &fakeWSL{}, &out, strings.NewReader("s\n")))
	config, _ := os.ReadFile(system.path)
	backup, _ := os.ReadFile(system.path + ".righaven-backup")
	if !mirrored(string(config)) || !strings.Contains(string(config), "memory=8GB") || string(backup) != "[wsl2]\nmemory=8GB\n" {
		t.Fatalf("config %q backup %q", config, backup)
	}
	if !a.Settings.Matter || system.firewall != 1 || system.shutdown != 1 || a.matterArgument() != "1" {
		t.Fatalf("%+v %+v", a.Settings, system)
	}
	system.build = 19045
	a.Settings.Matter = false
	if err := matterCommand(a, options{command: "matter", args: []string{"enable"}, yes: true}, &fakeWSL{}, io.Discard, strings.NewReader("")); err == nil || a.Settings.Matter {
		t.Fatal("Windows 10 accepted")
	}
}

func TestHostAgentCarriesOutPageRequests(t *testing.T) {
	a := portable(t)
	poll := strings.Join(root("RigHaven", "/usr/local/bin/righaven-host", "poll", "windows", strings.Join(hostActions, ","), "false"), " ")
	f := &fakeWSL{outputs: map[string]string{
		poll: `{"id":"a1","action":"usb-list","args":{}}` + "\nnot json\n" + `{"id":"a2","action":"com-share","args":{"name":"COM5"}}` + "\n",
	}}
	requests := pollHost(a, f)
	if len(requests) != 2 || requests[1].Args["name"] != "COM5" {
		t.Fatalf("%+v", requests)
	}
	useUSB(t, &fakeUSB{list: usbipdList})
	listed := handleHost(a, f, io.Discard, requests[0])
	devices, _ := listed["devices"].([]map[string]any)
	if listed["usbipd"] != true || len(devices) != 3 || devices[0]["serial"] != true {
		t.Fatalf("%+v", listed)
	}
	previousList, previousOpen := comPorts, openCOM
	comPorts = func() ([]comPort, error) { return []comPort{{Name: "COM5", Label: "OBDII (COM5)"}}, nil }
	openCOM = func(string) (io.ReadWriteCloser, error) { return nil, errors.New("busy") }
	t.Cleanup(func() { comPorts, openCOM = previousList, previousOpen })
	if result := handleHost(a, f, io.Discard, requests[1]); result["ok"] != true || strings.Join(a.Settings.Serial, ",") != "COM5" {
		t.Fatalf("%+v %v", result, a.Settings.Serial)
	}
	if f.find(strings.Join(root("RigHaven", "/usr/local/bin/righaven-discovery", "serial"), " ")) == nil {
		t.Fatal("shared port not reported")
	}
	system := &fakeMatter{build: 22631, path: filepath.Join(t.TempDir(), ".wslconfig")}
	previous := matterSystem
	matterSystem = system
	t.Cleanup(func() { matterSystem = previous })
	result := handleHost(a, f, io.Discard, hostRequest{ID: "a3", Action: "matter-enable"})
	config, _ := os.ReadFile(system.path)
	if result["restart"] != true || !a.Settings.Matter || system.firewall != 1 || !mirrored(string(config)) {
		t.Fatalf("%+v %s", result, config)
	}
	if result := handleHost(a, f, io.Discard, hostRequest{ID: "a4", Action: "format-disk"}); result["error"] == nil {
		t.Fatal("unknown action accepted")
	}
}

func TestNetshNetworksAreReadInAnyLanguage(t *testing.T) {
	italian := "Nome interfaccia : Wi-Fi\r\nAttualmente sono visibili 3 reti.\r\n\r\nSSID 1 : CasaRossi\r\n    Tipo di rete            : Infrastruttura\r\n    Autenticazione          : WPA2-Personal\r\n    BSSID 1                 : AA:BB:CC:DD:EE:01\r\n         Segnale            : 88%\r\n" +
		"SSID 2 : SmartLife-1A2B\r\n    Autenticazione          : Aperta\r\n    BSSID 1                 : 10:d5:61:00:00:02\r\n         Segnale            : 64%  \r\n" +
		"SSID 3 : CasaRossi\r\n    Autenticazione          : WPA2-Personal\r\n    BSSID 1                 : aa:bb:cc:dd:ee:03\r\n         Segnale            : 95%\r\n"
	networks := parseNetsh(italian)
	if len(networks) != 2 || networks[0].SSID != "CasaRossi" || networks[0].Signal != 95 || networks[0].Open {
		t.Fatalf("%+v", networks)
	}
	if networks[1].SSID != "SmartLife-1A2B" || !networks[1].Open || networks[1].Signal != 64 || networks[1].BSSID != "10:d5:61:00:00:02" {
		t.Fatalf("%+v", networks[1])
	}
	a := portable(t)
	previous := wifiScanner
	wifiScanner = func() ([]wifiNetwork, error) { return networks, nil }
	t.Cleanup(func() { wifiScanner = previous })
	f := &fakeWSL{}
	if result := handleHost(a, f, io.Discard, hostRequest{ID: "w1", Action: "wifi-scan"}); result["networks"] != 2 {
		t.Fatalf("%+v", result)
	}
	saved := f.find(strings.Join(root("RigHaven", "/usr/local/bin/righaven-discovery", "wifi"), " "))
	if saved == nil || !strings.Contains(string(saved.stdin), "SmartLife-1A2B") {
		t.Fatalf("%+v", f.calls)
	}
}

func TestPCBluetoothAdapterStaysWithWindows(t *testing.T) {
	a := portable(t)
	f := &fakeWSL{outputs: map[string]string{}}
	usb := &fakeUSB{list: strings.Replace(usbipdList, "2-1    046d:c52b  Logitech USB Input Device, USB Input Device                   Shared",
		"2-1    0bda:b00c  Realtek Bluetooth 4.2 Adapter                                 Attached", 1)}
	useUSB(t, usb)
	a.Settings.USB = []string{"2-1", "1-4"}
	if result := handleHost(a, f, io.Discard, hostRequest{ID: "b1", Action: "usb-attach", Args: map[string]string{"busid": "2-1"}}); result["error"] == nil {
		t.Fatal("the PC's Bluetooth adapter was attached without confirmation")
	}
	previous := bluetoothScanner
	bluetoothScanner = func() ([]btDevice, error) { return nil, errors.New("radio missing") }
	t.Cleanup(func() { bluetoothScanner = previous })
	result := handleHost(a, f, io.Discard, hostRequest{ID: "b2", Action: "bluetooth-scan"})
	if message, _ := result["error"].(string); !strings.Contains(message, "RigHaven") {
		t.Fatalf("attached adapter not explained: %+v", result)
	}
	if result := handleHost(a, f, io.Discard, hostRequest{ID: "b3", Action: "usb-detach", Args: map[string]string{"busid": "2-1"}}); result["ok"] != true {
		t.Fatalf("%+v", result)
	}
	if strings.Join(a.Settings.USB, ",") != "1-4" || strings.Join(usb.calls[len(usb.calls)-1], " ") != "detach --busid 2-1" {
		t.Fatalf("%v %v", a.Settings.USB, usb.calls)
	}
	bluetoothScanner = func() ([]btDevice, error) { return nil, errBluetoothAdapter }
	if err := bluetoothOnce(a, f, io.Discard); err == nil || !strings.Contains(err.Error(), "Bluetooth") {
		t.Fatalf("%v", err)
	}
}

func TestGATTActionsAreCheckedAndParsed(t *testing.T) {
	previous := gattTool
	t.Cleanup(func() { gattTool = previous })
	var asked []string
	gattTool = func(args ...string) (string, error) {
		asked = args
		return "N|LED Strip\r\nC|0000180a-0000-1000-8000-00805f9b34fb|00002a29-0000-1000-8000-00805f9b34fb|Read|4c454400|\n" +
			"C|0000ffe0-0000-1000-8000-00805f9b34fb|0000ffe1-0000-1000-8000-00805f9b34fb|WriteWithoutResponse,Notify||\n", nil
	}
	result := gattAction("ble-inspect", map[string]string{"address": "38:A5:C9:3C:2E:9F"})
	services, _ := result["services"].([]gattService)
	if result["name"] != "LED Strip" || len(services) != 2 || services[0].Characteristics[0].Text != "LED" || services[1].Characteristics[0].Properties[1] != "Notify" {
		t.Fatalf("%+v", result)
	}
	if strings.Join(asked, " ") != "inspect 38:A5:C9:3C:2E:9F" {
		t.Fatal(asked)
	}
	for _, bad := range []map[string]string{{"address": "38:A5"}, {"address": "38:A5:C9:3C:2E:9F", "service": "x", "characteristic": "y"},
		{"address": "38:A5:C9:3C:2E:9F", "service": "0000ffe0-0000-1000-8000-00805f9b34fb", "characteristic": "0000ffe1-0000-1000-8000-00805f9b34fb", "value": "zz"}} {
		if result := gattAction("ble-write", bad); result["error"] == nil {
			t.Fatalf("accepted %v", bad)
		}
	}
	gattTool = func(args ...string) (string, error) { asked = args; return "N|x\nV|\n", nil }
	ok := gattAction("ble-write", map[string]string{"address": "38:A5:C9:3C:2E:9F", "service": "0000ffe0-0000-1000-8000-00805f9b34fb",
		"characteristic": "0000ffe1-0000-1000-8000-00805f9b34fb", "value": "7E0004F00001FF00EF"})
	if ok["ok"] != true || asked[4] != "7e0004f00001ff00ef" {
		t.Fatalf("%+v %v", ok, asked)
	}
	previousRetry := gattRetry
	gattRetry = 0
	t.Cleanup(func() { gattRetry = previousRetry })
	calls := 0
	gattTool = func(args ...string) (string, error) {
		calls++
		return "N|TY\nE|services not readable: Unreachable\n", nil
	}
	if result := gattAction("ble-inspect", map[string]string{"address": "38:A5:C9:3C:2E:9F"}); calls != 2 || !strings.Contains(fmt.Sprint(result["error"]), "accoppiamento") {
		t.Fatalf("%d %+v", calls, result)
	}
	gattTool = func(args ...string) (string, error) { return "E|device not found or not in range\n", nil }
	if result := gattAction("ble-read", map[string]string{"address": "38:A5:C9:3C:2E:9F", "service": "0000180a-0000-1000-8000-00805f9b34fb",
		"characteristic": "00002a29-0000-1000-8000-00805f9b34fb"}); result["error"] != gattUnreachable {
		t.Fatalf("%+v", result)
	}
}

type fakeWifi struct{ current, joined, back, forgotten, gateway string }

func (f *fakeWifi) Current() (string, error)                 { return f.current, nil }
func (f *fakeWifi) JoinSetup(ssid, key string) (bool, error) { f.joined = ssid; return true, nil }
func (f *fakeWifi) Rejoin(ssid string) error                 { f.back = ssid; return nil }
func (f *fakeWifi) Gateway() (string, error)                 { return f.gateway, nil }
func (f *fakeWifi) Forget(ssid string)                       { f.forgotten = ssid }

func TestDeviceIsGivenTheHomeWifiAndThePCGoesBack(t *testing.T) {
	a := portable(t)
	var got url.Values
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/wi" {
			got = r.URL.Query()
		}
	}))
	t.Cleanup(server.Close)
	previous, addresses, wait := wifiSystem, setupAddresses, setupWait
	t.Cleanup(func() { wifiSystem, setupAddresses, setupWait = previous, addresses, wait })
	fake := &fakeWifi{current: "CasaRossi"}
	wifiSystem, setupAddresses, setupWait = fake, map[string][]string{"tasmota": {server.URL}}, 3*time.Second
	result := handleHost(a, &fakeWSL{}, io.Discard, hostRequest{ID: "w1", Action: "wifi-provision", Args: map[string]string{"ssid": "tasmota-1A2B", "hint": "tasmota", "password": "segreta123"}})
	if result["ok"] != true || got.Get("s1") != "CasaRossi" || got.Get("p1") != "segreta123" {
		t.Fatalf("%+v %v", result, got)
	}
	if fake.joined != "tasmota-1A2B" || fake.back != "CasaRossi" || fake.forgotten != "tasmota-1A2B" {
		t.Fatalf("%+v", fake)
	}
	if strings.Contains(fmt.Sprint(result), "segreta123") {
		t.Fatal("password returned")
	}
	for _, args := range []map[string]string{{"ssid": "SmartLife-1A2B", "hint": "tuya", "password": "segreta123"}, {"ssid": "x", "hint": "tasmota", "password": "short"}} {
		if result := handleHost(a, &fakeWSL{}, io.Discard, hostRequest{ID: "w2", Action: "wifi-provision", Args: args}); result["error"] == nil {
			t.Fatalf("accepted %v", args)
		}
	}
	setupAddresses = map[string][]string{"tasmota": {"http://127.0.0.1:1"}}
	fake.back = ""
	result = handleHost(a, &fakeWSL{}, io.Discard, hostRequest{ID: "w3", Action: "wifi-provision", Args: map[string]string{"ssid": "tasmota-1A2B", "hint": "tasmota", "password": "segreta123"}})
	if result["error"] == nil || fake.back != "CasaRossi" || strings.Contains(fmt.Sprint(result), "segreta123") {
		t.Fatalf("%+v %+v", result, fake)
	}
}

func TestSetupNetworkIsExploredWithoutChanges(t *testing.T) {
	a := portable(t)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/common/basic_info" {
			_, _ = w.Write([]byte("ret=OK,type=aircon,reg=eu,ver=1_14_88,name=%53%61%6c%6f%74%74%6f"))
		}
	}))
	t.Cleanup(server.Close)
	previous, addresses, wait := wifiSystem, setupAddresses, setupWait
	t.Cleanup(func() { wifiSystem, setupAddresses, setupWait = previous, addresses, wait })
	fake := &fakeWifi{current: "CasaRossi"}
	wifiSystem, setupAddresses, setupWait = fake, map[string][]string{"daikin": {server.URL}}, 3*time.Second
	result := handleHost(a, &fakeWSL{}, io.Discard, hostRequest{ID: "e1", Action: "wifi-explore", Args: map[string]string{"ssid": "DaikinAP72288", "hint": "daikin", "key": "0123456789"}})
	if result["ok"] != true || !strings.Contains(fmt.Sprint(result["info"]), "type=aircon") || fake.joined != "DaikinAP72288" || fake.back != "CasaRossi" {
		t.Fatalf("%+v %+v", result, fake)
	}
	if result := handleHost(a, &fakeWSL{}, io.Discard, hostRequest{ID: "e2", Action: "wifi-provision", Args: map[string]string{"ssid": "DaikinAP72288", "hint": "daikin", "password": "segreta123"}}); result["error"] == nil {
		t.Fatal("Daikin provisioning is not supported and must say so at once")
	}
}

func TestAnyWifiNetworkIsExploredWhenTheOwnerAsks(t *testing.T) {
	a := portable(t)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte("<html><head><title> Home&amp;Life SuperWiFi </title></head></html>"))
	}))
	t.Cleanup(server.Close)
	previous, wait := wifiSystem, setupWait
	t.Cleanup(func() { wifiSystem, setupWait = previous, wait })
	fake := &fakeWifi{current: "CasaRossi", gateway: strings.TrimPrefix(server.URL, "http://")}
	wifiSystem, setupWait = fake, 3*time.Second
	result := handleHost(a, &fakeWSL{}, io.Discard, hostRequest{ID: "e3", Action: "wifi-explore", Args: map[string]string{"ssid": "Home&Life SuperWiFi-EBBD", "key": "chiave-etichetta"}})
	if result["ok"] != true || result["title"] != "Home&amp;Life SuperWiFi" || fake.back != "CasaRossi" {
		t.Fatalf("%+v %+v", result, fake)
	}
}

func TestBluetoothRowsAreMergedAndHeardOnesComeFirst(t *testing.T) {
	devices, err := parseBluetooth([]byte(`[{"name":"TY","address":"38:a5:c9:3c:2e:9f","kind":"classic","paired":false,"present":false},
		{"name":"","address":"38:A5:C9:3C:2E:9F","kind":"ble","present":true,"signal":-60},
		{"name":"Vecchio","address":"11:22:33:44:55:66","kind":"ble","present":false},
		{"name":"ProvaRigHaven","address":"4A:00:11:22:33:44","kind":"ble","present":true,"signal":-50}]`))
	if err != nil || len(devices) != 3 {
		t.Fatalf("%v %+v", err, devices)
	}
	if devices[2].Name != "Vecchio" || devices[2].Present {
		t.Fatalf("not heard now must come last: %+v", devices)
	}
	for _, d := range devices[:2] {
		if !d.Present {
			t.Fatalf("%+v", devices)
		}
	}
	ty := devices[0]
	if devices[1].Name == "TY" {
		ty = devices[1]
	}
	if ty.Name != "TY" || ty.Kind != "ble" || ty.Signal == nil || ty.Address != "38:A5:C9:3C:2E:9F" {
		t.Fatalf("%+v", ty)
	}
}

func TestAllPCDevicesAreGroupedAndMatchedToUSB(t *testing.T) {
	a := portable(t)
	useUSB(t, &fakeUSB{list: usbipdList})
	previous := pnpLister
	t.Cleanup(func() { pnpLister = previous })
	pnpLister = func() ([]pnpDevice, error) {
		return []pnpDevice{{"Ports", "Silicon Labs CP210x USB to UART Bridge (COM3)", `USB\VID_10C4&PID_EA60\0001`, "OK"},
			{"Keyboard", "Tastiera PS/2 standard", `ACPI\PNP0303\4&1`, "OK"},
			{"Bluetooth", "WH-CH710N", `BTHENUM\{0000110b}\x`, "OK"},
			{"USB", "Hub USB generico", `USB\VID_05E3&PID_0610\5&2`, "OK"},
			{"SoftwareDevice", "Rete Wi-Fi Direct", `SWD\x`, "OK"}}, nil
	}
	result := pcDevices(a)
	rows, _ := result["devices"].([]map[string]any)
	if len(rows) != 5 || rows[0]["bus"] != "usb" || rows[3]["bus"] != "internal" || rows[4]["bus"] != "system" {
		t.Fatalf("%+v", rows)
	}
	for _, row := range rows {
		if row["vidpid"] == "10c4:ea60" && row["busid"] != "1-4" {
			t.Fatalf("not matched to usbipd: %+v", row)
		}
		if row["vidpid"] == "05e3:0610" && row["busid"] != nil {
			t.Fatalf("a hub cannot be attached: %+v", row)
		}
	}
}

func dnsLabels(name string) []byte {
	var out []byte
	for _, label := range strings.Split(name, ".") {
		out = append(out, byte(len(label)))
		out = append(out, label...)
	}
	return append(out, 0)
}

func TestAnnouncementsAreRead(t *testing.T) {
	// One mDNS answer: _shelly._tcp.local PTR "shellyplug-s-1A2B._shelly._tcp.local".
	message := []byte{0, 0, 0x84, 0, 0, 0, 0, 1, 0, 0, 0, 0}
	owner := dnsLabels("_shelly._tcp.local")
	target := dnsLabels("shellyplug-s-1A2B._shelly._tcp.local")
	message = append(message, owner...)
	message = append(message, 0, 12, 0, 1, 0, 0, 0, 120, 0, byte(len(target)))
	message = append(message, target...)
	names, services, err := parseMDNS(message)
	if err != nil || len(names) != 1 || names[0] != "shellyplug-s-1A2B" || services[0] != "_shelly._tcp.local" {
		t.Fatalf("%v %v %v", names, services, err)
	}
	if query := mdnsQuery([]string{"_hap._tcp.local"}); query[5] != 1 || query[len(query)-2] != 0x80 {
		t.Fatalf("% x", query)
	}
	server, location, kind := parseSSDP("HTTP/1.1 200 OK\r\nSERVER: Linux UPnP/1.0 Sonos/70.3\r\nLOCATION: http://192.168.1.30:1400/xml/device_description.xml\r\nST: urn:schemas-upnp-org:device:ZonePlayer:1\r\n\r\n")
	if !strings.Contains(server, "Sonos") || !strings.HasSuffix(location, ".xml") || !strings.Contains(kind, "ZonePlayer") {
		t.Fatal(server, location, kind)
	}
	if _, _, err := parseMDNS([]byte{1, 2}); err == nil {
		t.Fatal("short message accepted")
	}
}

func pcapngWith(packets ...[]byte) []byte {
	le := binary.LittleEndian
	block := func(kind uint32, body []byte) []byte {
		for len(body)%4 != 0 {
			body = append(body, 0)
		}
		out := make([]byte, 8, 12+len(body))
		le.PutUint32(out, kind)
		le.PutUint32(out[4:], uint32(12+len(body)))
		out = append(out, body...)
		return le.AppendUint32(out, uint32(12+len(body)))
	}
	shb := make([]byte, 16)
	le.PutUint32(shb, 0x1A2B3C4D)
	le.PutUint16(shb[4:], 1)
	for i := 8; i < 16; i++ {
		shb[i] = 0xff
	}
	data := block(0x0A0D0D0A, shb)
	data = append(data, block(1, []byte{1, 0, 0, 0, 0, 0, 0, 0})...)
	for _, packet := range packets {
		epb := make([]byte, 20)
		le.PutUint32(epb[12:], uint32(len(packet)))
		le.PutUint32(epb[16:], uint32(len(packet)))
		data = append(data, block(6, append(epb, packet...))...)
	}
	return data
}

func ipv4Frame(src, dst string, proto byte, sport, dport int, payload []byte) []byte {
	frame := append(make([]byte, 12), 0x08, 0x00)
	ip := make([]byte, 20)
	ip[0], ip[9] = 0x45, proto
	copy(ip[12:], net.ParseIP(src).To4())
	copy(ip[16:], net.ParseIP(dst).To4())
	l4 := make([]byte, 8)
	binary.BigEndian.PutUint16(l4, uint16(sport))
	binary.BigEndian.PutUint16(l4[2:], uint16(dport))
	return append(append(append(frame, ip...), l4...), payload...)
}

func TestTrafficIsSummarisedAndOffered(t *testing.T) {
	dns := []byte{0, 1, 0x81, 0x80, 0, 1, 0, 1, 0, 0, 0, 0}
	name := dnsLabels("a1.tuyaeu.com")
	dns = append(dns, name...)
	dns = append(dns, 0, 1, 0, 1)
	dns = append(dns, name...)
	dns = append(dns, 0, 1, 0, 1, 0, 0, 0, 60, 0, 4, 18, 185, 1, 2)
	capture := pcapngWith(
		ipv4Frame("192.168.137.1", "192.168.137.50", 17, 53, 40000, dns),
		ipv4Frame("192.168.137.50", "18.185.1.2", 6, 51000, 8883, make([]byte, 100)),
		ipv4Frame("18.185.1.2", "192.168.137.50", 6, 8883, 51000, make([]byte, 50)))
	summary, err := summarizeTraffic(capture)
	if err != nil {
		t.Fatal(err)
	}
	talks := summary["conversations"].([]*conversation)
	if summary["packets"] != 3 || talks[0].Remote != "18.185.1.2" || talks[0].Port != 8883 || talks[0].Packets != 2 || talks[0].Name != "a1.tuyaeu.com" || talks[0].Local != "192.168.137.50" {
		t.Fatalf("%+v %+v", summary, talks[0])
	}
	a := portable(t)
	file := filepath.Join(t.TempDir(), "capture.pcapng")
	if err := os.WriteFile(file, capture, 0o600); err != nil {
		t.Fatal(err)
	}
	previous := trafficRecorder
	t.Cleanup(func() { trafficRecorder = previous })
	trafficRecorder = func(seconds int) (string, error) { return file, nil }
	f := &fakeWSL{}
	result := handleHost(a, f, io.Discard, hostRequest{ID: "c1", Action: "traffic-capture", Args: map[string]string{"seconds": "30"}})
	if result["ok"] != true || result["download"] != true || f.find(strings.Join(root("RigHaven", "/usr/local/bin/righaven-discovery", "capture"), " ")) == nil {
		t.Fatalf("%+v", result)
	}
	if result := handleHost(a, f, io.Discard, hostRequest{ID: "c2", Action: "traffic-capture", Args: map[string]string{"seconds": "99999"}}); result["error"] == nil {
		t.Fatal("unbounded recording accepted")
	}
	if err := parsePCAPNG([]byte{1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13}, func(uint16, []byte) {}); err == nil {
		t.Fatal("damaged file accepted")
	}
}

func TestEveryDeviceOfTheNetworkIsListed(t *testing.T) {
	previous, wait, networks := neighbourTable, arpWait, localNetworks
	t.Cleanup(func() { neighbourTable, arpWait, localNetworks = previous, wait, networks })
	arpWait = 0
	localNetworks = func() []string { return []string{"127.0.0.0/30"} }
	neighbourTable = func() ([]neighbour, error) {
		return []neighbour{{Address: "127.0.0.2", MAC: "b8-27-eb-12-34-56"}, {Address: "127.0.0.1", MAC: "da-a1-19-00-00-01"},
			{Address: "127.0.0.3", MAC: "ff-ff-ff-ff-ff-ff"}, {Address: "10.0.0.1", MAC: "00-11-22-33-44-55"}}, nil
	}
	result := lanDevices()
	devices, _ := result["devices"].([]neighbour)
	if len(devices) != 2 || devices[0].Address != "127.0.0.1" || !devices[0].Private || devices[1].Vendor != "Raspberry Pi" || devices[1].MAC != "B8:27:EB:12:34:56" {
		t.Fatalf("%+v", result)
	}
}

// wsServerConn is the server side of a test WebSocket (server frames are not masked).
type wsServerConn struct {
	conn   net.Conn
	reader *bufio.Reader
}

func (c *wsServerConn) send(opcode byte, payload []byte) {
	header := []byte{0x80 | opcode}
	if len(payload) < 126 {
		header = append(header, byte(len(payload)))
	} else {
		header = append(header, 126, byte(len(payload)>>8), byte(len(payload)))
	}
	_, _ = c.conn.Write(append(header, payload...))
}

func (c *wsServerConn) read(t *testing.T) (byte, []byte) {
	t.Helper()
	head := make([]byte, 2)
	if _, err := io.ReadFull(c.reader, head); err != nil {
		t.Fatal(err)
	}
	size := int(head[1] & 0x7f)
	if size == 126 {
		extra := make([]byte, 2)
		_, _ = io.ReadFull(c.reader, extra)
		size = int(binary.BigEndian.Uint16(extra))
	}
	mask := make([]byte, 4)
	_, _ = io.ReadFull(c.reader, mask)
	payload := make([]byte, size)
	_, _ = io.ReadFull(c.reader, payload)
	for i := range payload {
		payload[i] ^= mask[i%4]
	}
	return head[0] & 0x0f, payload
}

func (c *wsServerConn) readJSON(t *testing.T) map[string]any {
	t.Helper()
	for {
		kind, payload := c.read(t)
		if kind != wsText {
			continue
		}
		var value map[string]any
		must(t, json.Unmarshal(payload, &value))
		if value["type"] != "ping" {
			return value
		}
	}
}

type fakeCOM struct{ written chan []byte }

func (f *fakeCOM) Read(p []byte) (int, error) { time.Sleep(time.Hour); return 0, io.EOF }
func (f *fakeCOM) Write(p []byte) (int, error) {
	f.written <- append([]byte(nil), p...)
	return len(p), nil
}
func (f *fakeCOM) Close() error { return nil }

func TestAgentPairsConnectsAnswersAndCarriesATunnel(t *testing.T) {
	a := portable(t)
	config := filepath.Join(t.TempDir(), "agent.json")
	previousPath, previousDial, previousCOM := agentConfigPath, scanDial, openCOM
	t.Cleanup(func() { agentConfigPath, scanDial, openCOM = previousPath, previousDial, previousCOM })
	agentConfigPath = func() string { return config }
	scanDial = func(ctx context.Context, address string) error {
		if address == "192.168.1.44:6668" {
			return nil
		}
		if strings.HasPrefix(address, "192.168.1.45:") {
			return errors.New("connect: connection refused")
		}
		return errors.New("i/o timeout")
	}
	com := &fakeCOM{written: make(chan []byte, 1)}
	openCOM = func(name string) (io.ReadWriteCloser, error) {
		if name != "COM5" {
			return nil, errors.New("no such port")
		}
		return com, nil
	}
	sockets := make(chan *wsServerConn, 1)
	mux := http.NewServeMux()
	mux.HandleFunc("/api/webhooks/righaven-agent/pair", func(w http.ResponseWriter, r *http.Request) {
		var body map[string]string
		_ = json.NewDecoder(r.Body).Decode(&body)
		if body["code"] != "ABCDE-FGHJK" || body["platform"] != runtime.GOOS {
			w.WriteHeader(403)
			return
		}
		_, _ = w.Write([]byte(`{"agent":"ag_0123456789ab","token":"rha_secret","name":"PC di casa"}`))
	})
	mux.HandleFunc("/api/webhooks/righaven-agent/connect", func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get(agentHeader) != "rha_secret" {
			w.WriteHeader(403)
			return
		}
		sum := sha1.Sum([]byte(r.Header.Get("Sec-WebSocket-Key") + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"))
		conn, buffer, _ := w.(http.Hijacker).Hijack()
		_, _ = buffer.WriteString("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: " +
			base64.StdEncoding.EncodeToString(sum[:]) + "\r\n\r\n")
		_ = buffer.Flush()
		sockets <- &wsServerConn{conn: conn, reader: buffer.Reader}
	})
	server := httptest.NewServer(mux)
	t.Cleanup(server.Close)

	if _, err := agentLink(a, server.URL, "WRONG-CODE1"); err == nil {
		t.Fatal("a wrong code was accepted")
	}
	linked, err := agentLink(a, server.URL, "ABCDE-FGHJK")
	must(t, err)
	saved, _ := os.ReadFile(config)
	if strings.Contains(string(saved), `"token": "rha_secret"`) || linked.Agent != "ag_0123456789ab" {
		t.Fatalf("token stored as is: %s", saved)
	}
	loaded, err := loadAgentConfig()
	must(t, err)
	if loaded.Token != "rha_secret" {
		t.Fatal(loaded)
	}

	stop := make(chan struct{})
	finished := make(chan error, 1)
	go func() { finished <- runAgent(a, loaded, io.Discard, stop) }()
	socket := <-sockets
	hello := socket.readJSON(t)
	if hello["type"] != "hello" || hello["platform"] != runtime.GOOS || !strings.Contains(fmt.Sprint(hello["actions"]), "net-scan") {
		t.Fatalf("%v", hello)
	}
	// The server asks a search of the home network.
	socket.send(wsText, []byte(`{"type":"request","id":"j1","action":"net-scan","args":{"network":"192.168.1.0/26"}}`))
	result := socket.readJSON(t)
	devices := result["result"].(map[string]any)["devices"].([]any)
	if result["id"] != "j1" || len(devices) != 2 || devices[0].(map[string]any)["address"] != "192.168.1.44" ||
		fmt.Sprint(devices[0].(map[string]any)["ports"]) != "[6668]" || fmt.Sprint(devices[1].(map[string]any)["ports"]) != "[]" {
		t.Fatalf("%v", result)
	}
	// A worker of the server opens COM5 through the tunnel.
	socket.send(wsText, []byte(`{"type":"open","stream":7,"target":"com:COM5"}`))
	if opened := socket.readJSON(t); opened["type"] != "opened" || opened["stream"] != float64(7) {
		t.Fatalf("%v", opened)
	}
	socket.send(wsBinary, append([]byte{0, 0, 0, 7}, []byte("ATZ\r")...))
	if got := <-com.written; string(got) != "ATZ\r" {
		t.Fatalf("%q", got)
	}
	// Only private addresses of the PC's network are reachable through a tunnel.
	socket.send(wsText, []byte(`{"type":"open","stream":8,"target":"tcp:8.8.8.8:53"}`))
	if refused := socket.readJSON(t); refused["type"] != "close" || refused["stream"] != float64(8) {
		t.Fatalf("%v", refused)
	}
	close(stop)
	select {
	case err := <-finished:
		must(t, err)
	case <-time.After(10 * time.Second):
		t.Fatal("the agent did not stop")
	}
}

func TestTunnelsReachOnlyThePrivateNetworkOfThePC(t *testing.T) {
	previous := homeResolve
	defer func() { homeResolve = previous }()
	homeResolve = func(_ context.Context, host string) ([]net.IPAddr, error) {
		switch host {
		case "sql01.office.local":
			return []net.IPAddr{{IP: net.ParseIP("10.255.255.1")}}, nil
		case "rebind.example":
			return []net.IPAddr{{IP: net.ParseIP("10.0.0.5")}, {IP: net.ParseIP("8.8.8.8")}}, nil
		}
		return nil, errors.New("no such host")
	}
	for _, target := range []string{"8.8.8.8:53", "127.0.0.1:1433", "rebind.example:1433", "unknown.local:1433", "no-port"} {
		if conn, err := homeDial(target, time.Second); err == nil {
			conn.Close()
			t.Fatalf("%s should be refused", target)
		}
	}
	// An internal name resolving to a private address is dialled (nothing answers there: a dial error, not a refusal).
	_, err := homeDial("sql01.office.local:1433", 300*time.Millisecond)
	if err == nil || strings.Contains(err.Error(), "not an address") || strings.Contains(err.Error(), "not resolved") {
		t.Fatalf("an internal name should be dialled, got %v", err)
	}
}

// fakeDocker writes a docker command for the node tests: info, images, run (writes into the
// folder mounted at /out and prints a JSON answer), inspect, rm, stop.
func fakeDocker(t *testing.T) string {
	dir := t.TempDir()
	script := `#!/bin/sh
case "$1" in
info) echo "8 17179869184 27.1.1" ;;
image) exit 0 ;;
inspect) echo false ;;
rm|stop) exit 0 ;;
run)
  shift
  while [ $# -gt 0 ]; do
    if [ "$1" = "--mount" ]; then
      case "$2" in
        *dst=/out) out=$(echo "$2" | sed 's/^type=bind,src=//; s/,dst=.*$//') ;;
        *dst=/progress) progress=$(echo "$2" | sed 's/^type=bind,src=//; s/,dst=.*$//') ;;
        *dst=/job.json,readonly) job=$(echo "$2" | sed 's/^type=bind,src=//; s/,dst=.*$//') ;;
      esac
    fi
    shift
  done
  echo '{"phase":"done"}' > "$progress/status.json"
  cat "$job" > "$out/report.md"
  echo '{"ok": true}'
  ;;
*) exit 2 ;;
esac
`
	path := filepath.Join(dir, "docker")
	must(t, os.WriteFile(path, []byte(script), 0o755))
	return path
}

func TestNodeRunsASandboxAndSendsBackItsFiles(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("the fake docker is a shell script")
	}
	a := portable(t)
	docker := fakeDocker(t)
	previousDocker, previousRuns := nodeDockerCmd, nodeRunsDir
	runs := t.TempDir()
	nodeDockerCmd, nodeRunsDir = func() []string { return []string{docker} }, func() string { return runs }
	t.Cleanup(func() { nodeDockerCmd, nodeRunsDir = previousDocker, previousRuns })
	job := nodeRun{ID: "rh-job-0123456789ab", Image: "righaven-env:abc", Timeout: 60, Mounts: []nodeMount{
		{Key: "m0", Mode: "ro", Kind: "file", Target: "/job.json"}, {Key: "m1", Mode: "rw", Kind: "dir", Target: "/out"},
		{Key: "m2", Mode: "live", Kind: "dir", Target: "/progress"}},
		Args: []string{"run", "--name", "rh-job-0123456789ab", "--init", "--cap-drop=ALL", "--memory=4096m", "--cpus=4", "--network=bridge",
			"--mount", "type=bind,src={m0},dst=/job.json,readonly", "--mount", "type=bind,src={m1},dst=/out", "--mount", "type=bind,src={m2},dst=/progress",
			"--env", "A=1", "righaven-env:abc", "python3", "/opt/righaven-worker/run_agent.py", "/job.json"}}
	var result map[string]any
	files := map[string]string{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get(agentHeader) != "rha_test" {
			w.WriteHeader(401)
			return
		}
		switch r.URL.Path {
		case "/api/webhooks/righaven-agent/runs/rh-job-0123456789ab/bundle":
			gz := gzip.NewWriter(w)
			archive := tar.NewWriter(gz)
			for name, body := range map[string]string{"m0": `{"task":"ciao"}`, "../evil": "x"} {
				must(t, archive.WriteHeader(&tar.Header{Name: name, Mode: 0o644, Size: int64(len(body)), Typeflag: tar.TypeReg}))
				_, _ = archive.Write([]byte(body))
			}
			archive.Close()
			gz.Close()
		case "/api/webhooks/righaven-agent/runs/rh-job-0123456789ab/live":
			w.WriteHeader(200)
		case "/api/webhooks/righaven-agent/runs/rh-job-0123456789ab/result":
			gz, err := gzip.NewReader(r.Body)
			must(t, err)
			archive := tar.NewReader(gz)
			for {
				header, err := archive.Next()
				if err != nil {
					break
				}
				data, _ := io.ReadAll(archive)
				if header.Name == "result.json" {
					must(t, json.Unmarshal(data, &result))
				} else if header.Typeflag == tar.TypeReg {
					files[header.Name] = string(data)
				}
			}
			w.WriteHeader(200)
		default:
			w.WriteHeader(404)
		}
	}))
	defer server.Close()
	session := &agentSession{a: a, config: agentConfig{Server: server.URL, Token: "rha_test", Node: &nodeConfig{Jobs: 2}}, out: io.Discard,
		conn: nil}
	dir := filepath.Join(runs, job.ID)
	// The bundle with a path outside it is refused: nothing runs.
	refused := session.executeJob(dir, job)
	if refused["returncode"] != 125 || !strings.Contains(refused["stderr"].(string), "outside the bundle") {
		t.Fatalf("a bundle escaping its folder must be refused: %v", refused)
	}
	server.Config.Handler = wrapBundle(server.Config.Handler)
	done := session.executeJob(dir, job)
	if done["returncode"] != 0 || done["stdout"] != "{\"ok\": true}\n" {
		t.Fatalf("run: %v", done)
	}
	session.uploadResult(dir, job, done)
	if result["returncode"] != float64(0) || files["m1/report.md"] != `{"task":"ciao"}` || files["m2/status.json"] != "{\"phase\":\"done\"}\n" {
		t.Fatalf("result sent back: %v %v", result, files)
	}
	if _, ok := files["m0"]; ok {
		t.Fatal("read-only folders are not sent back")
	}
	if _, err := os.Stat(dir); !os.IsNotExist(err) {
		t.Fatal("the run's folder stays on the machine after the server took the result")
	}
}

// wrapBundle answers the bundle without the escaping entry.
func wrapBundle(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, "/bundle") {
			gz := gzip.NewWriter(w)
			archive := tar.NewWriter(gz)
			body := `{"task":"ciao"}`
			_ = archive.WriteHeader(&tar.Header{Name: "m0", Mode: 0o644, Size: int64(len(body)), Typeflag: tar.TypeReg})
			_, _ = archive.Write([]byte(body))
			archive.Close()
			gz.Close()
			return
		}
		next.ServeHTTP(w, r)
	})
}

func TestNodeRefusesCommandsOutsideItsSandboxRules(t *testing.T) {
	limits := map[string]any{"cpus": 8.0, "memory_mib": 16384}
	base := func(extra ...string) nodeRun {
		// The options exactly as the server's base_arguments writes them.
		args := append([]string{"run", "--name", "rh-job-0123456789ab", "--label", "org.righaven.harness.owner=gateway", "--init", "--cap-drop=ALL",
			"--security-opt=no-new-privileges", "--pids-limit=256", "--memory=2048m", "--memory-swap=2048m", "--cpus=2", "--network=bridge",
			"--tmpfs", "/tmp:rw,size=512m", "--env", "RIGHAVEN_CPU_THREADS=2", "--env", "TZ=Europe/Rome"}, extra...)
		return nodeRun{ID: "rh-job-0123456789ab", Image: "img", Mounts: []nodeMount{{Key: "m0", Mode: "ro", Kind: "dir", Target: "/data"}},
			Args: append(args, "img", "python3", "x.py")}
	}
	if args, name, err := nodeArgs(base("--mount", "type=bind,src={m0},dst=/data,readonly"), "/runs/x/m", limits); err != nil || name != "rh-job-0123456789ab" ||
		!strings.Contains(strings.Join(args, " "), "src="+dockerPath(filepath.Join("/runs/x/m", "m0"))+",dst=/data,readonly") {
		t.Fatalf("a plain command is accepted: %v %v", args, err)
	}
	for _, extra := range [][]string{{"--privileged"}, {"--device", "/dev/sda"}, {"--network=host"}, {"-v", "/:/host"}, {"--cap-add", "SYS_ADMIN"},
		{"--mount", "type=bind,src=/etc,dst=/etc"}, {"--mount", "type=bind,src={m0},dst=/data"}, {"--mount", "type=bind,src={m9},dst=/data,readonly"},
		{"--cpus=64"}, {"--memory=999999m"}, {"--env", "LD_PRELOAD=/x.so"}, {"--label", "com.other=1"}, {"--pid=host"}, {"--pids-limit=99999"}} {
		if _, _, err := nodeArgs(base(extra...), "/runs/x/m", limits); err == nil {
			t.Fatalf("refused: %v", extra)
		}
	}
	wrongName := base()
	wrongName.Args[2] = "rh-job-ffffffffffff"
	if _, _, err := nodeArgs(wrongName, "/runs/x/m", limits); err == nil {
		t.Fatal("the container name is the run's")
	}
	wrongImage := base()
	wrongImage.Image = "other"
	if _, _, err := nodeArgs(wrongImage, "/runs/x/m", limits); err == nil {
		t.Fatal("the image is the run's")
	}
}

// With RIGHAVEN_NODE_DOCKER_TEST=1 (the Linux job of CI, which has Docker) a real container runs
// through the node's checks, mounts and result upload.
func TestNodeRunsARealContainer(t *testing.T) {
	if os.Getenv("RIGHAVEN_NODE_DOCKER_TEST") != "1" {
		t.Skip("set RIGHAVEN_NODE_DOCKER_TEST=1 on a machine with Docker")
	}
	a := portable(t)
	must(t, exec.Command("docker", "pull", "-q", "busybox:1.36").Run())
	runs := t.TempDir()
	previousRuns := nodeRunsDir
	nodeRunsDir = func() string { return runs }
	t.Cleanup(func() { nodeRunsDir = previousRuns })
	job := nodeRun{ID: "rh-job-0a1b2c3d4e5f", Image: "busybox:1.36", Timeout: 120, Mounts: []nodeMount{
		{Key: "m0", Mode: "ro", Kind: "file", Target: "/job.json"}, {Key: "m1", Mode: "rw", Kind: "dir", Target: "/out"}},
		Args: []string{"run", "--name", "rh-job-0a1b2c3d4e5f", "--init", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=64",
			"--memory=256m", "--memory-swap=256m", "--cpus=1", "--network=bridge", "--tmpfs", "/tmp:rw,size=16m",
			"--mount", "type=bind,src={m0},dst=/job.json,readonly", "--mount", "type=bind,src={m1},dst=/out",
			"busybox:1.36", "sh", "-c", `cat /job.json > /out/report.md && echo '{"ok": true}' && ! touch /job.json 2>/dev/null`}}
	var files = map[string]string{}
	var result map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case strings.HasSuffix(r.URL.Path, "/bundle"):
			gz := gzip.NewWriter(w)
			archive := tar.NewWriter(gz)
			body := `{"task":"real"}`
			_ = archive.WriteHeader(&tar.Header{Name: "m0", Mode: 0o644, Size: int64(len(body)), Typeflag: tar.TypeReg})
			_, _ = archive.Write([]byte(body))
			_ = archive.WriteHeader(&tar.Header{Name: "m1/", Mode: 0o777, Typeflag: tar.TypeDir})
			archive.Close()
			gz.Close()
		case strings.HasSuffix(r.URL.Path, "/result"):
			gz, _ := gzip.NewReader(r.Body)
			archive := tar.NewReader(gz)
			for header, err := archive.Next(); err == nil; header, err = archive.Next() {
				data, _ := io.ReadAll(archive)
				if header.Name == "result.json" {
					_ = json.Unmarshal(data, &result)
				} else {
					files[header.Name] = string(data)
				}
			}
		}
	}))
	defer server.Close()
	session := &agentSession{a: a, config: agentConfig{Server: server.URL, Token: "rha_test", Node: &nodeConfig{Jobs: 1}}, out: io.Discard}
	dir := filepath.Join(runs, job.ID)
	done := session.executeJob(dir, job)
	if done["returncode"] != 0 || !strings.Contains(done["stdout"].(string), `"ok": true`) {
		t.Fatalf("real container: %v", done)
	}
	session.uploadResult(dir, job, done)
	if files["m1/report.md"] != `{"task":"real"}` || result["returncode"] != float64(0) {
		t.Fatalf("files back: %v %v", files, result)
	}
	if exec.Command("docker", "inspect", job.ID).Run() == nil {
		t.Fatal("the container is removed after the run")
	}
}

// The server's own worker command (testdata/server-args.json, kept equal to docker_runtime by
// tests/test_compute_nodes.py) passes the node's sandbox rules.
func TestNodeAcceptsTheServersCommand(t *testing.T) {
	data, err := os.ReadFile(filepath.Join("testdata", "server-args.json"))
	must(t, err)
	var fixture struct {
		Image  string      `json:"image"`
		Mounts []nodeMount `json:"mounts"`
		Args   []string    `json:"args"`
	}
	must(t, json.Unmarshal(data, &fixture))
	job := nodeRun{ID: "rh-job-0123456789ab", Image: fixture.Image, Mounts: fixture.Mounts, Args: fixture.Args}
	args, name, err := nodeArgs(job, "/runs/x/m", map[string]any{"cpus": 8.0, "memory_mib": 16384})
	if err != nil || name != job.ID {
		t.Fatalf("the server's command must pass: %v", err)
	}
	if !strings.Contains(strings.Join(args, " "), "src="+dockerPath(filepath.Join("/runs/x/m", "m0"))+",dst=/mnt/user-data,readonly") || args[len(args)-1] != "/job.json" {
		t.Fatalf("command on the node: %v", args)
	}
}

// A proxy error while the server restarts is not a revocation: the agent keeps its pairing and retries.
func TestAgentRevocationIsTheServersAnswerOnly(t *testing.T) {
	answer := ""
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch answer {
		case "revoked":
			w.WriteHeader(401)
			_, _ = w.Write([]byte(`{"code":"agent_revoked"}`))
		case "proxy":
			w.WriteHeader(404)
			_, _ = w.Write([]byte("404 page not found"))
		default:
			_, _ = w.Write([]byte(`{"ok":true}`))
		}
	}))
	defer server.Close()
	config := agentConfig{Server: server.URL, Token: "rha_x"}
	for value, revoked := range map[string]bool{"revoked": true, "proxy": false, "ok": false} {
		answer = value
		if agentRevoked(config) != revoked {
			t.Fatalf("%s: revoked should be %v", value, revoked)
		}
	}
	if agentRevoked(agentConfig{Server: "http://127.0.0.1:9", Token: "rha_x"}) {
		t.Fatal("an unreachable server is not a revocation")
	}
}
