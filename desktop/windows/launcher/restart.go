package main

import (
	"io"
	"os"
	"os/exec"
)

// restartLauncher stops RigHaven, restarts WSL (needed after a WSL networking change) and starts
// this launcher again in the same window, without opening the browser a second time.
func restartLauncher(a *App, w WSL, out io.Writer) {
	_ = stop(a, w, out)
	_ = matterSystem.ShutdownWSL()
	exe, err := os.Executable()
	if err != nil {
		return
	}
	cmd := exec.Command(exe, "start", "--no-browser")
	cmd.Stdin, cmd.Stdout, cmd.Stderr = os.Stdin, os.Stdout, os.Stderr
	if cmd.Start() == nil {
		os.Exit(0)
	}
}
