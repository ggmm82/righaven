package main

import (
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

// Matter devices are found with multicast and IPv6 on the local network, which WSL shows to
// its distributions only in "mirrored" networking (Windows 11 22H2 or later). `RigHaven.exe
// matter enable` turns it on, allows the Matter traffic into WSL in the Hyper-V firewall and
// starts RigHaven's Matter controller with the next start.

// matterPlatform holds the Windows parts, replaced in tests.
type matterPlatform interface {
	WindowsBuild() (int, error)
	ConfigPath() string
	AllowFirewall() error
	ShutdownWSL() error
}

var matterSystem matterPlatform = windowsMatter{}

const minimumMirroredBuild = 22621

var networkingMode = regexp.MustCompile(`(?im)^\s*networkingMode\s*=\s*(\w+)\s*$`)

// mirrored reports whether the WSL configuration already uses mirrored networking.
func mirrored(config string) bool {
	match := networkingMode.FindStringSubmatch(config)
	return match != nil && strings.EqualFold(match[1], "mirrored")
}

// withMirrored returns the .wslconfig text with networkingMode=mirrored in [wsl2], keeping the rest.
func withMirrored(config string) string {
	if mirrored(config) {
		return config
	}
	if networkingMode.MatchString(config) {
		return networkingMode.ReplaceAllString(config, "networkingMode=mirrored")
	}
	lines := strings.Split(strings.ReplaceAll(config, "\r\n", "\n"), "\n")
	for i, line := range lines {
		if strings.EqualFold(strings.TrimSpace(line), "[wsl2]") {
			out := append([]string{}, lines[:i+1]...)
			out = append(out, "networkingMode=mirrored")
			return strings.Join(append(out, lines[i+1:]...), "\n")
		}
	}
	prefix := strings.TrimRight(config, "\n")
	if prefix != "" {
		prefix += "\n\n"
	}
	return prefix + "[wsl2]\nnetworkingMode=mirrored\n"
}

func matterCommand(a *App, o options, w WSL, out io.Writer, in io.Reader) error {
	action := "status"
	if len(o.args) > 0 {
		action = o.args[0]
	}
	path := matterSystem.ConfigPath()
	current, _ := os.ReadFile(path)
	switch action {
	case "status":
		state := a.T("matter_off")
		if a.Settings.Matter {
			state = a.T("matter_on")
		}
		fmt.Fprintf(out, "%s · %s: %v\n", state, a.T("matter_mirrored"), mirrored(string(current)))
		return nil
	case "disable":
		a.Settings.Matter = false
		if err := a.save(); err != nil {
			return err
		}
		fmt.Fprintln(out, a.T("matter_disabled"))
		return nil
	case "enable":
	default:
		return errors.New(a.T("matter_usage"))
	}
	build, err := matterSystem.WindowsBuild()
	if err == nil && build < minimumMirroredBuild {
		return fmt.Errorf(a.T("matter_windows"), build)
	}
	fmt.Fprintf(out, a.T("matter_explain")+"\n", path)
	if !o.yes && !askYes(a, out, in, "matter_ask") {
		fmt.Fprintln(out, a.T("cancelled"))
		return nil
	}
	if !mirrored(string(current)) {
		if len(current) > 0 {
			_ = os.WriteFile(path+".righaven-backup", current, 0o644)
		}
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			return err
		}
		if err := os.WriteFile(path, []byte(withMirrored(string(current))), 0o644); err != nil {
			return err
		}
	}
	if err := matterSystem.AllowFirewall(); err != nil {
		fmt.Fprintf(out, a.T("matter_firewall")+"\n", err)
	}
	a.Settings.Matter = true
	if err := a.save(); err != nil {
		return err
	}
	if reachable(a.Listen()) && ready(a) {
		fmt.Fprintln(out, a.T("matter_restart"))
		return nil
	}
	if err := matterSystem.ShutdownWSL(); err != nil {
		return err
	}
	fmt.Fprintln(out, a.T("matter_ready"))
	return nil
}

func (a *App) matterArgument() string {
	if a.Settings.Matter {
		return "1"
	}
	return "0"
}
