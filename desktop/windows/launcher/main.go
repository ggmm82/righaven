// RigHaven.exe: runs the verified RigHaven release on Windows in a dedicated WSL 2
// distribution, keeping the same isolation as the server (containers in a VM).
package main

import (
	"bufio"
	"errors"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"
)

var launcherVersion = "dev"

type options struct {
	command   string
	args      []string
	port      int
	name      string
	noBrowser bool
	yes       bool
	devices   string
	bind      string
}

func parse(args []string, a *App) (options, error) {
	o := options{command: "start"}
	fs := flag.NewFlagSet("RigHaven", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	fs.IntVar(&o.port, "port", 0, "")
	fs.StringVar(&o.name, "name", "", "")
	fs.BoolVar(&o.noBrowser, "no-browser", false, "")
	fs.BoolVar(&o.yes, "yes", false, "")
	fs.StringVar(&o.devices, "devices", "", "")
	fs.StringVar(&o.bind, "bind", "", "")
	// Flags may come before or after the command.
	var rest []string
	for len(args) > 0 {
		if err := fs.Parse(args); err != nil {
			return o, err
		}
		args = fs.Args()
		if len(args) > 0 {
			rest = append(rest, args[0])
			args = args[1:]
		}
	}
	if len(rest) > 0 {
		o.command, o.args = rest[0], rest[1:]
	}
	if o.port != 0 {
		a.Settings.Port = o.port
	}
	if o.name != "" {
		a.Settings.Distribution = o.name
	}
	if o.bind != "" {
		a.Settings.Bind = o.bind
	}
	switch o.devices {
	case "":
	case "none":
		a.Settings.Devices, a.Settings.NoDevices = nil, true
	case "auto":
		a.Settings.Devices, a.Settings.NoDevices = nil, false
	default:
		a.Settings.Devices, a.Settings.NoDevices = nil, false
		for _, device := range strings.Split(o.devices, ",") {
			if device = strings.TrimSpace(device); device != "" {
				a.Settings.Devices = append(a.Settings.Devices, device)
			}
		}
	}
	return o, a.validate()
}

func main() {
	home := executableHome()
	language := uiLanguage()
	a, err := newApp(home, language)
	if err == nil {
		var o options
		if o, err = parse(os.Args[1:], a); err == nil {
			err = run(a, o, newWSL(), console(os.Stdout))
		}
	}
	if err != nil {
		fmt.Fprintln(console(os.Stderr), err)
		pauseIfOwnConsole(a)
		os.Exit(1)
	}
}

func executableHome() string {
	exe, err := os.Executable()
	if err != nil {
		return "."
	}
	if resolved, err := filepath.EvalSymlinks(exe); err == nil {
		exe = resolved
	}
	return filepath.Dir(exe)
}

func run(a *App, o options, w WSL, out io.Writer) error {
	switch o.command {
	case "start":
		return start(a, o, w, out)
	case "stop":
		return stop(a, w, out)
	case "status":
		if err := requireInstalled(a, w); err != nil {
			return err
		}
		return w.Run(nil, out, out, root(a.Settings.Distribution, "/usr/local/bin/righaven-status")...)
	case "logs":
		if err := requireInstalled(a, w); err != nil {
			return err
		}
		service := "gateway"
		if len(o.args) > 0 {
			service = o.args[0]
		}
		return w.Run(nil, out, out, root(a.Settings.Distribution, "/usr/local/bin/righaven-logs", service)...)
	case "shell":
		if err := requireInstalled(a, w); err != nil {
			return err
		}
		return w.Run(os.Stdin, out, out, "--distribution", a.Settings.Distribution, "--user", "root", "--cd", "/opt/righaven")
	case "doctor":
		return doctor(a, w, out)
	case "remove":
		return remove(a, o, w, out, os.Stdin)
	case "repair":
		return reattach(w, a, o, out, os.Stdin)
	case "matter":
		return matterCommand(a, o, w, out, os.Stdin)
	case "serial":
		return serialCommand(a, o, out, os.Stdin)
	case "bluetooth":
		return bluetoothCommand(a, o, w, out)
	case "usb":
		return usbCommand(a, o, w, out, os.Stdin)
	case "version":
		release, _ := a.release()
		fmt.Fprintf(out, "RigHaven %s (launcher %s)\n", release.Version, launcherVersion)
		return nil
	case "help", "-h", "--help":
		fmt.Fprintln(out, a.T("usage"))
		return nil
	}
	return fmt.Errorf("%s\n\n%s", o.command, a.T("usage"))
}

// checkWSL verifies that a WSL version with --import-in-place is present, and offers
// to install it (one administrator prompt and a restart) when it is missing.
func checkWSL(a *App, w WSL, out io.Writer, in io.Reader) error {
	if _, err := w.Output("--version"); err == nil {
		return nil
	}
	if _, err := w.Output("--status"); err == nil {
		return errors.New(a.T("old_wsl"))
	}
	fmt.Fprintln(out, a.T("no_wsl"))
	fmt.Fprint(out, a.T("ask_wsl"))
	answer, _ := bufio.NewReader(in).ReadString('\n')
	answer = strings.ToLower(strings.TrimSpace(answer))
	if answer == "s" || answer == "si" || answer == "sì" || answer == "y" || answer == "yes" {
		if err := installWSLElevated(); err == nil {
			return errors.New(a.T("wsl_started"))
		}
	}
	return errors.New(a.T("wsl_manual"))
}

func ready(a *App) bool {
	// Each connection starts a wsl.exe relay, which can take seconds on some PCs.
	client := http.Client{Timeout: 20 * time.Second}
	response, err := client.Get(a.URL() + "/health/ready")
	if err != nil {
		return false
	}
	response.Body.Close()
	return response.StatusCode == http.StatusOK
}

func waitReady(a *App, wait time.Duration) bool {
	deadline := time.Now().Add(wait)
	for !ready(a) {
		if time.Now().After(deadline) {
			return false
		}
		time.Sleep(time.Second)
	}
	return true
}

func portFree(address string) bool {
	listener, err := net.Listen("tcp", address)
	if err != nil {
		return false
	}
	listener.Close()
	return true
}

func start(a *App, o options, w WSL, out io.Writer) error {
	release, err := a.release()
	if err != nil {
		return err
	}
	fmt.Fprintf(out, a.T("title")+"\n\n", release.Version)
	if err := checkWSL(a, w, out, os.Stdin); err != nil {
		return err
	}
	if err := a.save(); err != nil {
		return err
	}
	if reachable(a.Listen()) && ready(a) {
		fmt.Fprintf(out, a.T("already")+"\n", a.URL())
		if !o.noBrowser {
			openBrowser(a.URL())
		}
		return nil
	}
	if !portFree(a.Listen()) {
		return fmt.Errorf(a.T("port_busy"), a.Settings.Port)
	}
	if err := ensureDistribution(w, a, out); err != nil {
		return err
	}
	// The hold process keeps the WSL instance alive while this window is open; it starts
	// first so USB peripherals can be attached to the running WSL before the install.
	hold, err := w.Start(root(a.Settings.Distribution, "/usr/local/bin/righaven-hold")...)
	if err != nil {
		return err
	}
	attachRemembered(a, w, out)
	if a.Settings.Matter {
		if config, _ := os.ReadFile(matterSystem.ConfigPath()); !mirrored(string(config)) {
			fmt.Fprintln(out, a.T("matter_not_mirrored"))
		}
	}
	if err := install(w, a, out); err != nil {
		_ = hold.Process.Kill()
		return err
	}
	signals := make(chan os.Signal, 2)
	signal.Notify(signals, os.Interrupt, syscall.SIGTERM)
	p := &progress{a: a, out: out}
	err = w.Run(nil, p, p, root(a.Settings.Distribution, "/usr/local/bin/righaven-start")...)
	p.flush()
	if err != nil || !p.ready {
		fmt.Fprintln(out, a.T("start_failed"))
		_ = hold.Process.Kill()
		if err == nil {
			err = errors.New("righaven-start")
		}
		return err
	}
	// RigHaven.exe always serves the Windows address and relays into the distribution, where
	// the proxy uses an inner port: WSL port forwarding differs between NAT and mirrored modes
	// and can reserve the port on Windows without answering.
	listener, err := forward(w, a)
	if err != nil {
		_ = hold.Process.Kill()
		_ = stop(a, w, out)
		return fmt.Errorf(a.T("port_unavailable"), a.Listen(), err)
	}
	defer listener.Close()
	if waitReady(a, 90*time.Second) {
		if !a.Loopback() {
			fmt.Fprintf(out, a.T("exposed")+"\n", a.Listen())
		}
		fmt.Fprintf(out, "\n"+a.T("ready")+"\n%s\n\n", a.URL(), a.T("keep_open"))
		if len(a.Settings.USB) == 0 {
			fmt.Fprintln(out, a.T("usb_hint"))
		}
		startSerialBridges(a, w, out)
		go runHostAgent(a, w, out, stopBridging)
		if !o.noBrowser {
			openBrowser(a.URL())
		}
	} else {
		// Stay up so the problem can be examined; the diagnosis names the failing leg.
		fmt.Fprintf(out, "\n"+a.T("unreachable_ui")+"\n", a.URL())
		diagnose(a, w, out)
		fmt.Fprintln(out, a.T("diag_keep"))
	}
	exited := make(chan error, 1)
	go func() { exited <- hold.Wait() }()
	select {
	case sig := <-signals:
		if sig == syscall.SIGTERM {
			// The window is closing: Windows allows only a few seconds, so the clean
			// stop continues in a detached process.
			stopDetached(a)
			return nil
		}
	case <-exited:
	}
	close(stopBridging)
	return stop(a, w, out)
}

func requireInstalled(a *App, w WSL) error {
	ok, err := registered(w, a.Settings.Distribution)
	if err != nil {
		return err
	}
	if !ok {
		return errors.New(a.T("not_installed"))
	}
	return nil
}

func stop(a *App, w WSL, out io.Writer) error {
	ok, err := registered(w, a.Settings.Distribution)
	if err != nil || !ok {
		return err
	}
	fmt.Fprintln(out, a.T("stopping"))
	_ = w.Run(nil, io.Discard, out, root(a.Settings.Distribution, "/usr/local/bin/righaven-stop")...)
	_ = w.Run(nil, io.Discard, io.Discard, "--terminate", a.Settings.Distribution)
	fmt.Fprintln(out, a.T("stopped"))
	return nil
}

func doctor(a *App, w WSL, out io.Writer) error {
	release, err := a.release()
	fmt.Fprintf(out, "folder:        %s\n", a.Home)
	fmt.Fprintf(out, "launcher:      %s\n", launcherVersion)
	if err != nil {
		fmt.Fprintf(out, "release:       %v\n", err)
	} else {
		fmt.Fprintf(out, "release:       %s (%s)\n", release.Version, release.SourceCommit)
		fmt.Fprintf(out, "files:         %s\n", verifyFiles(a, release))
	}
	version, err := w.Output("--version")
	if err != nil {
		fmt.Fprintf(out, "wsl:           not available (%v)\n", err)
	} else {
		fmt.Fprintf(out, "wsl:           %s\n", firstLine(version))
		ok, err := registered(w, a.Settings.Distribution)
		fmt.Fprintf(out, "distribution:  %s registered=%v %v\n", a.Settings.Distribution, ok, errText(err))
	}
	fmt.Fprintf(out, "address:       %s free=%v ready=%v\n", a.Listen(), portFree(a.Listen()), ready(a))
	if ok, _ := registered(w, a.Settings.Distribution); ok {
		diagnose(a, w, out)
	}
	return nil
}

func verifyFiles(a *App, release Release) string {
	var problems []string
	for name, expected := range release.Files {
		if digest, err := sha256File(filepath.Join(a.Home, "app", name)); err != nil || digest != expected {
			problems = append(problems, name)
		}
	}
	if !fileExists(filepath.Join(a.Home, "app", "rootfs.tar")) {
		problems = append(problems, "rootfs.tar")
	}
	if len(problems) > 0 {
		return "changed or missing: " + strings.Join(problems, ", ")
	}
	return "ok"
}

func remove(a *App, o options, w WSL, out io.Writer, in io.Reader) error {
	if err := requireInstalled(a, w); err != nil {
		return err
	}
	if !confirmed(a, o, out, in, "confirm_remove", "ELIMINA", "DELETE") {
		return nil
	}
	_ = stop(a, w, out)
	if err := w.Run(nil, out, out, "--unregister", a.Settings.Distribution); err != nil {
		return err
	}
	fmt.Fprintln(out, a.T("removed"))
	return nil
}

func firstLine(text string) string {
	return strings.TrimSpace(strings.SplitN(strings.TrimSpace(text), "\n", 2)[0])
}

func errText(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}

// confirmed asks to type a word: dangerous commands never run on a bare Enter.
func confirmed(a *App, o options, out io.Writer, in io.Reader, key, italian, english string) bool {
	if o.yes {
		return true
	}
	fmt.Fprintf(out, a.T(key), a.Settings.Distribution)
	answer, _ := bufio.NewReader(in).ReadString('\n')
	answer = strings.TrimSpace(answer)
	if answer == italian || answer == english {
		return true
	}
	fmt.Fprintln(out, a.T("cancelled"))
	return false
}
