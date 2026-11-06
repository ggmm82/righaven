package main

import (
	"archive/tar"
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"time"
	"unicode/utf16"
)

// WSL runs wsl.exe. The interface lets tests replace the real executable.
type WSL interface {
	Output(args ...string) (string, error)
	Run(stdin io.Reader, stdout, stderr io.Writer, args ...string) error
	Start(args ...string) (*exec.Cmd, error)
	Bridge(conn io.ReadWriteCloser, args ...string) error
}

type execWSL struct{ exe string }

func newWSL() WSL {
	exe := "wsl.exe"
	if root := os.Getenv("SystemRoot"); root != "" {
		if path := filepath.Join(root, "System32", "wsl.exe"); fileExists(path) {
			exe = path
		}
	}
	return execWSL{exe: exe}
}

func (w execWSL) command(args ...string) *exec.Cmd {
	return w.commandContext(context.Background(), args...)
}

func (w execWSL) commandContext(ctx context.Context, args ...string) *exec.Cmd {
	cmd := exec.CommandContext(ctx, w.exe, args...)
	// Recent WSL prints UTF-8 with this variable; older builds print UTF-16, handled by decode.
	cmd.Env = append(os.Environ(), "WSL_UTF8=1")
	return cmd
}

func (w execWSL) Output(args ...string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	cmd := w.commandContext(ctx, args...)
	var out bytes.Buffer
	cmd.Stdout, cmd.Stderr = &out, &out
	err := cmd.Run()
	return decode(out.Bytes()), err
}

func (w execWSL) Run(stdin io.Reader, stdout, stderr io.Writer, args ...string) error {
	cmd := w.command(args...)
	cmd.Stdin, cmd.Stdout, cmd.Stderr = stdin, stdout, stderr
	return cmd.Run()
}

func (w execWSL) Bridge(conn io.ReadWriteCloser, args ...string) error {
	cmd := w.command(args...)
	cmd.Stdout = conn
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return err
	}
	if err := cmd.Start(); err != nil {
		noteRelay(err, "")
		return err
	}
	err = bridge(conn, stdin, cmd.Wait)
	noteRelay(err, stderr.String())
	return err
}

func (w execWSL) Start(args ...string) (*exec.Cmd, error) {
	cmd := w.command(args...)
	return cmd, cmd.Start()
}

// decode returns wsl.exe output as text, whether it is UTF-8 or UTF-16LE.
func decode(raw []byte) string {
	if len(raw) >= 2 && raw[0] == 0xFF && raw[1] == 0xFE {
		raw = raw[2:]
	}
	if bytes.IndexByte(raw, 0) >= 0 {
		units := make([]uint16, 0, len(raw)/2)
		for i := 0; i+1 < len(raw); i += 2 {
			units = append(units, uint16(raw[i])|uint16(raw[i+1])<<8)
		}
		return string(utf16.Decode(units))
	}
	return string(raw)
}

func distributions(w WSL) ([]string, error) {
	out, err := w.Output("--list", "--quiet")
	if err != nil {
		// With no distribution installed, wsl.exe exits with an error and a message.
		if strings.Contains(strings.ToLower(out), "no installed distributions") || strings.Contains(strings.ToLower(out), "nessuna distribuzione") {
			return nil, nil
		}
		return nil, fmt.Errorf("wsl --list: %w: %s", err, strings.TrimSpace(out))
	}
	var names []string
	for _, line := range strings.Split(out, "\n") {
		if name := strings.TrimSpace(strings.TrimPrefix(line, string(rune(0xFEFF)))); name != "" {
			names = append(names, name)
		}
	}
	return names, nil
}

func registered(w WSL, name string) (bool, error) {
	names, err := distributions(w)
	if err != nil {
		return false, err
	}
	for _, item := range names {
		if strings.EqualFold(item, name) {
			return true, nil
		}
	}
	return false, nil
}

func root(name string, command ...string) []string {
	return append([]string{"--distribution", name, "--user", "root", "--exec"}, command...)
}

// ensureDistribution imports the distribution of this portable copy, or re-registers
// the disk that is already in the data folder (for example after moving the folder).
func ensureDistribution(w WSL, a *App, out io.Writer) error {
	ok, err := registered(w, a.Settings.Distribution)
	if err != nil {
		return err
	}
	disk := filepath.Join(a.Data, "wsl", "ext4.vhdx")
	if ok {
		owner, err := w.Output(root(a.Settings.Distribution, "/usr/local/bin/righaven-home")...)
		owner = strings.TrimSpace(owner)
		if err != nil {
			// Typically the folder was moved: the registration points to a disk that is gone.
			return fmt.Errorf(a.T("unreachable"), a.Settings.Distribution, firstLine(owner))
		}
		if owner != "" && !strings.EqualFold(filepath.Clean(owner), filepath.Clean(a.Home)) {
			return fmt.Errorf(a.T("other_copy"), a.Settings.Distribution, owner)
		}
		return nil
	}
	if fileExists(disk) {
		fmt.Fprintln(out, a.T("reattach"))
		return w.Run(nil, out, out, "--import-in-place", a.Settings.Distribution, disk)
	}
	image := filepath.Join(a.Home, "app", "rootfs.tar")
	if !fileExists(image) {
		return errors.New(a.T("missing_app"))
	}
	if err := os.MkdirAll(filepath.Join(a.Data, "wsl"), 0o755); err != nil {
		return err
	}
	fmt.Fprintln(out, a.T("importing"))
	return w.Run(nil, out, out, "--import", a.Settings.Distribution, filepath.Join(a.Data, "wsl"), image, "--version", "2")
}

// bundle packs files as a tar stream; scripts are executable.
func bundle(files map[string][]byte, mode int64) []byte {
	var buf bytes.Buffer
	tw := tar.NewWriter(&buf)
	names := make([]string, 0, len(files))
	for name := range files {
		names = append(names, name)
	}
	sort.Strings(names)
	for _, name := range names {
		_ = tw.WriteHeader(&tar.Header{Name: name, Mode: mode, Size: int64(len(files[name])), ModTime: time.Unix(0, 0)})
		_, _ = tw.Write(files[name])
	}
	_ = tw.Close()
	return buf.Bytes()
}

// install copies the scripts and the release files of this copy into the distribution,
// so an updated portable folder also updates an existing distribution.
func install(w WSL, a *App, out io.Writer) error {
	scripts := map[string][]byte{}
	entries, err := os.ReadDir(filepath.Join(a.Home, "app", "bin"))
	if err != nil {
		return errors.New(a.T("missing_app"))
	}
	for _, entry := range entries {
		if strings.HasPrefix(entry.Name(), "righaven-") {
			content, err := os.ReadFile(filepath.Join(a.Home, "app", "bin", entry.Name()))
			if err != nil {
				return err
			}
			scripts[entry.Name()] = bytes.ReplaceAll(content, []byte("\r\n"), []byte("\n"))
		}
	}
	if err := w.Run(bytes.NewReader(bundle(scripts, 0o755)), out, out, root(a.Settings.Distribution, "tar", "-x", "-o", "-C", "/usr/local/bin", "-f", "-")...); err != nil {
		return fmt.Errorf("scripts: %w", err)
	}
	files := map[string][]byte{"home.txt": []byte(a.Home + "\n")}
	for _, name := range []string{"compose.yaml", "Caddyfile", "release.json"} {
		content, err := os.ReadFile(filepath.Join(a.Home, "app", name))
		if err != nil {
			return errors.New(a.T("missing_app"))
		}
		files[name] = content
	}
	return w.Run(bytes.NewReader(bundle(files, 0o644)), out, out,
		root(a.Settings.Distribution, "/usr/local/bin/righaven-install", fmt.Sprint(a.InnerPort()), a.Language, a.deviceArgument(),
			strings.Trim(a.Host(), "[]"), fmt.Sprint(a.Settings.Port), strings.Join(localNetworks(), ","), a.matterArgument())...)
}

// progress turns the markers printed by righaven-start into readable messages.
type progress struct {
	a     *App
	out   io.Writer
	line  []byte
	ready bool
}

func (p *progress) Write(data []byte) (int, error) {
	for _, b := range data {
		if b != '\n' {
			p.line = append(p.line, b)
			continue
		}
		p.flush()
	}
	return len(data), nil
}

func (p *progress) flush() {
	line := strings.TrimRight(string(p.line), "\r")
	p.line = p.line[:0]
	fields := strings.Fields(line)
	switch {
	case len(fields) == 3 && fields[0] == "@@step" && fields[1] == "images":
		fmt.Fprintf(p.out, p.a.T("step_images")+"\n", fields[2])
	case line == "@@step start":
		fmt.Fprintln(p.out, p.a.T("step_start"))
	case len(fields) == 4 && fields[0] == "@@pull":
		fmt.Fprintf(p.out, "  [%s/%s] %s…\n", fields[1], fields[2], fields[3])
	case line == "@@ready":
		p.ready = true
	default:
		fmt.Fprintln(p.out, line)
	}
}

// reattach replaces the registration of the distribution with the disk in this folder,
// after the folder was moved. The old registration is removed by WSL, together with
// any disk still at its old location, so it needs a typed confirmation.
func reattach(w WSL, a *App, o options, out io.Writer, in io.Reader) error {
	disk := filepath.Join(a.Data, "wsl", "ext4.vhdx")
	if !fileExists(disk) {
		return errors.New(a.T("no_disk"))
	}
	ok, err := registered(w, a.Settings.Distribution)
	if err != nil {
		return err
	}
	if ok {
		if !confirmed(a, o, out, in, "confirm_repair", "RICOLLEGA", "REATTACH") {
			return nil
		}
		_ = w.Run(nil, io.Discard, io.Discard, "--terminate", a.Settings.Distribution)
		if err := w.Run(nil, out, out, "--unregister", a.Settings.Distribution); err != nil {
			return err
		}
	}
	fmt.Fprintln(out, a.T("reattach"))
	return w.Run(nil, out, out, "--import-in-place", a.Settings.Distribution, disk)
}
