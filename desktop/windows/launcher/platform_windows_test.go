//go:build windows

package main

import (
	"os"
	"os/exec"
	"strings"
	"testing"
)

// The Bluetooth helper is C# built on the owner's PC by the compiler that ships with Windows:
// build it here too, so that a mistake in its source fails the CI and not the owner's first use.
func TestGATTHelperBuilds(t *testing.T) {
	program, err := dotnetProgram("gatt-test", gattSource)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = os.Remove(program) })
	// Without a device it answers with an error line, never a crash.
	output, err := exec.Command(program, "exchange", "00:00:00:00:00:00", "0000fff0-0000-1000-8000-00805f9b34fb",
		"0000fff2-0000-1000-8000-00805f9b34fb", "", "30330d", "3e", "500").Output()
	if err != nil || !strings.HasPrefix(strings.TrimSpace(string(output)), "E|") {
		t.Fatalf("%q %v", output, err)
	}
	// The stream mode too: without a device, an error line before any channel line.
	output, err = exec.Command(program, "stream", "00:00:00:00:00:00", "", "", "").Output()
	if err != nil || !strings.HasPrefix(strings.TrimSpace(string(output)), "E|") {
		t.Fatalf("%q %v", output, err)
	}
}
