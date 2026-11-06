//go:build !windows

package main

import (
	"io"
	"os"
	"strings"
)

// Non-Windows builds exist for tests and development only.

func uiLanguage() string {
	if strings.HasPrefix(os.Getenv("LANG"), "it") {
		return "it"
	}
	return "en"
}

func openBrowser(string) {}

func pauseIfOwnConsole(*App) {}

func installWSLElevated() error { return os.ErrNotExist }

func stopDetached(*App) {}

func console(w io.Writer) io.Writer { return w }

type noUSB struct{}

func newUSB() USB { return noUSB{} }

func (noUSB) Output(...string) (string, error) { return "", os.ErrNotExist }
func (noUSB) Elevated(...string) error         { return os.ErrNotExist }
func (noUSB) Install() error                   { return os.ErrNotExist }

func scanBluetooth() ([]btDevice, error) { return nil, os.ErrNotExist }

func openSerialPort(string) (io.ReadWriteCloser, error) { return nil, os.ErrNotExist }

func listCOMPorts() ([]comPort, error) { return nil, os.ErrNotExist }

type windowsMatter struct{}

func (windowsMatter) WindowsBuild() (int, error) { return 0, os.ErrNotExist }
func (windowsMatter) ConfigPath() string         { return os.ExpandEnv("$HOME/.wslconfig") }
func (windowsMatter) AllowFirewall() error       { return os.ErrNotExist }
func (windowsMatter) ShutdownWSL() error         { return os.ErrNotExist }

func scanWifi() ([]wifiNetwork, error) { return nil, os.ErrNotExist }

func runGATT(...string) (string, error) { return "", os.ErrNotExist }

type windowsWifi struct{}

func (windowsWifi) Current() (string, error)               { return "", os.ErrNotExist }
func (windowsWifi) JoinSetup(string, string) (bool, error) { return false, os.ErrNotExist }
func (windowsWifi) Rejoin(string) error                    { return os.ErrNotExist }
func (windowsWifi) Gateway() (string, error)               { return "", os.ErrNotExist }
func (windowsWifi) Forget(string)                          {}

func listPnPDevices() ([]pnpDevice, error) { return nil, os.ErrNotExist }

func recordTraffic(int) (string, error) { return "", os.ErrNotExist }

func readNeighbours() ([]neighbour, error) { return nil, os.ErrNotExist }
