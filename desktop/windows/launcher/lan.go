package main

import (
	"encoding/binary"
	"net"
	"sort"
	"strings"
	"time"
)

// Every device on the PC's network, whatever ports it has: the PC sends one empty packet to each
// address of its networks, which makes Windows ask "who has this address?" (ARP). Every device
// connected to the network must answer, so Windows' neighbour table then lists them all with
// their hardware (MAC) address. Nothing is sent to any service of the devices.

type neighbour struct {
	Address string `json:"address"`
	MAC     string `json:"mac"`
	Vendor  string `json:"vendor,omitempty"`
	Private bool   `json:"private_mac,omitempty"`
}

var (
	neighbourTable = readNeighbours
	arpWait        = 3 * time.Second
	// Hardware makers by the first three bytes of the MAC address (common home devices).
	ouiVendors = map[string]string{
		"B827EB": "Raspberry Pi", "DCA632": "Raspberry Pi", "E45F01": "Raspberry Pi", "D83ADD": "Raspberry Pi", "2CCF67": "Raspberry Pi",
		"24A160": "Espressif", "240AC4": "Espressif", "30AEA4": "Espressif", "84CCA8": "Espressif", "A4CF12": "Espressif", "BCDDC2": "Espressif",
		"C44F33": "Espressif", "DC4F22": "Espressif", "ECFABC": "Espressif", "E868E7": "Espressif", "7C9EBD": "Espressif", "3C71BF": "Espressif",
		"001788": "Philips Hue (Signify)", "ECB5FA": "Philips Hue (Signify)", "10D561": "Tuya", "508A06": "Tuya", "D81F12": "Tuya", "68572D": "Tuya",
		"001132": "Synology", "FCECDA": "Ubiquiti", "18E829": "Ubiquiti", "44D9E7": "Ubiquiti",
	}
)

// lanDevices wakes up the neighbour table for the PC's networks and lists every device that answered.
func lanDevices() map[string]any {
	networks := localNetworks()
	if conn, err := net.ListenPacket("udp4", ":0"); err == nil {
		for _, network := range networks {
			_, ipnet, err := net.ParseCIDR(network)
			if err != nil {
				continue
			}
			base := binary.BigEndian.Uint32(ipnet.IP.To4())
			ones, bits := ipnet.Mask.Size()
			for host := uint32(1); host < 1<<(bits-ones)-1 && host < 1024; host++ {
				address := make(net.IP, 4)
				binary.BigEndian.PutUint32(address, base+host)
				_, _ = conn.WriteTo([]byte{0}, &net.UDPAddr{IP: address, Port: 9}) // discard port: no service is reached
			}
		}
		conn.Close()
	}
	time.Sleep(arpWait)
	found, err := neighbourTable()
	if err != nil {
		return failed(err)
	}
	inside := func(address string) bool {
		ip := net.ParseIP(address)
		for _, network := range networks {
			if _, ipnet, err := net.ParseCIDR(network); err == nil && ip != nil && ipnet.Contains(ip) {
				return true
			}
		}
		return false
	}
	seen := map[string]bool{}
	var devices []neighbour
	for _, n := range found {
		mac := strings.ToUpper(strings.NewReplacer("-", "", ":", "").Replace(n.MAC))
		if len(mac) != 12 || mac == "000000000000" || mac == "FFFFFFFFFFFF" || strings.HasPrefix(mac, "01005E") || !inside(n.Address) || seen[n.Address] {
			continue
		}
		seen[n.Address] = true
		n.MAC = strings.Join([]string{mac[0:2], mac[2:4], mac[4:6], mac[6:8], mac[8:10], mac[10:12]}, ":")
		n.Vendor = ouiVendors[mac[:6]]
		if first := mac[1]; first == '2' || first == '6' || first == 'A' || first == 'E' {
			n.Private = true // locally administered: phones and PCs that hide their real address
		}
		devices = append(devices, n)
	}
	sort.Slice(devices, func(i, j int) bool {
		a, b := net.ParseIP(devices[i].Address).To4(), net.ParseIP(devices[j].Address).To4()
		return a != nil && b != nil && binary.BigEndian.Uint32(a) < binary.BigEndian.Uint32(b)
	})
	return map[string]any{"devices": devices, "networks": networks}
}
