package main

import (
	"bytes"
	"encoding/json"
	"io"
	"regexp"
	"strconv"
	"strings"
	"time"
)

// Wi-Fi networks near the PC, read with the PC's Wi-Fi adapter. Devices that are not set up
// yet (plugs, bulbs, IR remotes, ESP boards) open their own setup network: RigHaven shows them
// with what to do. Nothing connects to any network.

type wifiNetwork struct {
	SSID   string `json:"ssid"`
	BSSID  string `json:"bssid,omitempty"`
	Signal int    `json:"signal"`
	Open   bool   `json:"open"`
}

var (
	wifiScanner = scanWifi
	netshSSID   = regexp.MustCompile(`^\s*SSID\s+\d+\s*:\s?(.*)$`)
	netshBSSID  = regexp.MustCompile(`^\s*BSSID\s+\d+\s*:\s*([0-9a-fA-F:]{17})\s*$`)
	netshSignal = regexp.MustCompile(`:\s*(\d{1,3})\s?%\s*$`)
	openWords   = []string{"open", "aperta", "offen", "ouvert", "abierta", "aberta"}
)

// parseNetsh reads `netsh wlan show networks mode=bssid` in any Windows language: the labels
// change, the SSID/BSSID lines and the percentages do not.
func parseNetsh(text string) []wifiNetwork {
	strongest := map[string]int{}
	var networks []wifiNetwork
	current := -1
	for _, line := range strings.Split(strings.ReplaceAll(text, "\r", ""), "\n") {
		if match := netshSSID.FindStringSubmatch(line); match != nil {
			networks = append(networks, wifiNetwork{SSID: strings.TrimSpace(match[1])})
			current = len(networks) - 1
			continue
		}
		if current < 0 {
			continue
		}
		network := &networks[current]
		if match := netshBSSID.FindStringSubmatch(line); match != nil && network.BSSID == "" {
			network.BSSID = strings.ToLower(match[1])
		} else if match := netshSignal.FindStringSubmatch(line); match != nil {
			if value, _ := strconv.Atoi(match[1]); value > network.Signal && value <= 100 {
				network.Signal = value
			}
		} else if parts := strings.SplitN(line, ":", 2); len(parts) == 2 && network.BSSID == "" {
			value := strings.ToLower(strings.TrimSpace(parts[1]))
			for _, word := range openWords {
				if value == word {
					network.Open = true
				}
			}
		}
	}
	var unique []wifiNetwork
	for _, network := range networks {
		key := network.SSID
		if key == "" {
			key = network.BSSID
		}
		if index, seen := strongest[key]; seen {
			if network.Signal > unique[index].Signal {
				unique[index] = network
			}
			continue
		}
		strongest[key] = len(unique)
		unique = append(unique, network)
	}
	return unique
}

func wifiOnce(a *App, w WSL) (int, error) {
	networks, err := wifiScanner()
	if err != nil {
		return 0, err
	}
	report, _ := json.Marshal(map[string]any{"scanned_at": time.Now().UTC().Format(time.RFC3339), "networks": networks})
	err = w.Run(bytes.NewReader(report), io.Discard, io.Discard, root(a.Settings.Distribution, "/usr/local/bin/righaven-discovery", "wifi")...)
	return len(networks), err
}
