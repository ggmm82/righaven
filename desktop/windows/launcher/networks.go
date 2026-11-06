package main

import (
	"net"
	"strings"
)

// Virtual adapters (WSL, Hyper-V, VirtualBox, VMware, VPN tunnels) are not the network where
// the user's devices are.
var virtualAdapter = []string{"vethernet", "wsl", "hyper-v", "virtualbox", "vmware", "loopback", "docker", "tailscale", "zerotier", "vpn", "bluetooth"}

// localNetworks returns the private IPv4 networks of this PC's real adapters, each as a /24 at
// most, for "Find devices on the network" in RigHaven: inside WSL the Wi-Fi network is not
// visible. Searching still needs the owner's click in RigHaven.
var localNetworks = detectNetworks

func detectNetworks() []string {
	interfaces, err := net.Interfaces()
	if err != nil {
		return nil
	}
	var found []string
	seen := map[string]bool{}
	for _, adapter := range interfaces {
		if adapter.Flags&net.FlagUp == 0 || adapter.Flags&net.FlagLoopback != 0 || isVirtual(adapter.Name) {
			continue
		}
		addresses, err := adapter.Addrs()
		if err != nil {
			continue
		}
		for _, address := range addresses {
			if network := searchable(address); network != "" && !seen[network] {
				seen[network] = true
				found = append(found, network)
			}
		}
	}
	return found
}

func isVirtual(name string) bool {
	name = strings.ToLower(name)
	for _, word := range virtualAdapter {
		if strings.Contains(name, word) {
			return true
		}
	}
	return false
}

// searchable turns an adapter address into its private network, narrowed to a /24.
func searchable(address net.Addr) string {
	ipNet, ok := address.(*net.IPNet)
	if !ok {
		return ""
	}
	ip := ipNet.IP.To4()
	if ip == nil || !ip.IsPrivate() {
		return ""
	}
	ones, _ := ipNet.Mask.Size()
	if ones < 24 {
		ones = 24
	}
	return (&net.IPNet{IP: ip.Mask(net.CIDRMask(ones, 32)), Mask: net.CIDRMask(ones, 32)}).String()
}
