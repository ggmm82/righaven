package main

import (
	"bufio"
	"errors"
	"fmt"
	"io"
	"net"
	"strings"
	"sync"
	"time"
)

// WSL forwards a port bound to 127.0.0.1 in the distribution to 127.0.0.1 on Windows, but
// not in every configuration and never to another address. Otherwise RigHaven.exe listens on
// the bind address itself and carries each connection into the distribution through wsl.exe.

// The last relay failure, shown by the diagnosis.
var (
	relayMu    sync.Mutex
	relayError string
)

func noteRelay(err error, stderr string) {
	if err == nil && strings.TrimSpace(stderr) == "" {
		return
	}
	relayMu.Lock()
	defer relayMu.Unlock()
	relayError = strings.TrimSpace(fmt.Sprintf("%v %s", err, stderr))
}

func lastRelayError() string {
	relayMu.Lock()
	defer relayMu.Unlock()
	return relayError
}

// diagnose checks the three legs separately: RigHaven inside WSL, the relay from Windows into
// WSL, and the Windows address; each line names what works and the real error otherwise.
func diagnose(a *App, w WSL, out io.Writer) {
	started := time.Now()
	text, err := w.Output(root(a.Settings.Distribution, "/usr/local/bin/righaven-probe", fmt.Sprint(a.InnerPort()))...)
	fmt.Fprintf(out, "1. inside WSL   righaven-probe %d: %s (%s)\n", a.InnerPort(), strings.TrimSpace(verdict(err, "")), time.Since(started).Round(time.Millisecond))
	for _, line := range strings.Split(strings.TrimSpace(text), "\n") {
		if line = strings.TrimSpace(line); line != "" {
			fmt.Fprintf(out, "   %s\n", line)
		}
	}
	started = time.Now()
	client, server := net.Pipe()
	go func() {
		_ = w.Bridge(server, root(a.Settings.Distribution, "/usr/local/bin/righaven-relay", fmt.Sprint(a.InnerPort()))...)
	}()
	_ = client.SetDeadline(time.Now().Add(20 * time.Second))
	_, err = client.Write([]byte("GET /health/ready HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n"))
	line := ""
	if err == nil {
		line, err = bufio.NewReader(client).ReadString('\n')
	}
	client.Close()
	fmt.Fprintf(out, "2. relay        wsl.exe -> righaven-relay %d: %s (%s)\n", a.InnerPort(), verdict(err, line), time.Since(started).Round(time.Millisecond))
	if detail := lastRelayError(); detail != "" {
		fmt.Fprintf(out, "   relay error: %s\n", detail)
	}
	started = time.Now()
	fmt.Fprintf(out, "3. Windows      %s: ready=%v (%s)\n", a.URL(), ready(a), time.Since(started).Round(time.Millisecond))
}

func verdict(err error, text string) string {
	text = strings.TrimSpace(text)
	if len(text) > 120 {
		text = text[:120]
	}
	if err != nil {
		return "ERROR " + err.Error() + " " + text
	}
	return "ok " + text
}

func reachable(address string) bool {
	conn, err := net.DialTimeout("tcp", address, time.Second)
	if err != nil {
		return false
	}
	conn.Close()
	return true
}

func waitReachable(address string, wait time.Duration) bool {
	deadline := time.Now().Add(wait)
	for {
		if reachable(address) {
			return true
		}
		if time.Now().After(deadline) {
			return false
		}
		time.Sleep(500 * time.Millisecond)
	}
}

// forward serves 127.0.0.1:port on Windows until the listener is closed.
func forward(w WSL, a *App) (net.Listener, error) {
	listener, err := net.Listen("tcp", a.Listen())
	if err != nil {
		return nil, err
	}
	go func() {
		for {
			conn, err := listener.Accept()
			if err != nil {
				if errors.Is(err, net.ErrClosed) {
					return
				}
				continue
			}
			go func() {
				defer conn.Close()
				_ = w.Bridge(conn, root(a.Settings.Distribution, "/usr/local/bin/righaven-relay", fmt.Sprint(a.InnerPort()))...)
			}()
		}
	}()
	return listener, nil
}

// bridge copies a connection to and from a process; it returns when the process ends.
func bridge(conn io.ReadWriteCloser, stdin io.WriteCloser, wait func() error) error {
	go func() {
		_, _ = io.Copy(stdin, conn)
		stdin.Close()
	}()
	err := wait()
	conn.Close()
	return err
}
