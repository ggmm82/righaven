package main

import (
	"encoding/binary"
	"errors"
	"net"
	"sort"
	"strings"
	"time"
)

// Listening to the network: devices that announce themselves (mDNS / Bonjour, SSDP / UPnP) are
// found even when they answer no port of the search. RigHaven asks once on the PC's network
// (the same questions a phone app or Windows itself asks) and collects the answers for a few
// seconds. Nothing is written to any device.

type announced struct {
	Address  string   `json:"address"`
	Names    []string `json:"names,omitempty"`
	Services []string `json:"services,omitempty"`
	Server   string   `json:"server,omitempty"`
	Location string   `json:"location,omitempty"`
	Kinds    []string `json:"kinds,omitempty"`
}

var (
	listenTime = 8 * time.Second
	// The kinds of services asked by name besides the general list: the usual home devices.
	mdnsQuestions = []string{"_services._dns-sd._udp.local", "_http._tcp.local", "_hap._tcp.local", "_googlecast._tcp.local",
		"_esphomelib._tcp.local", "_shelly._tcp.local", "_hue._tcp.local", "_matter._tcp.local", "_matterc._udp.local",
		"_airplay._tcp.local", "_ipp._tcp.local", "_printer._tcp.local", "_spotify-connect._tcp.local", "_miio._udp.local"}
	ssdpSearch = "M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: \"ssdp:discover\"\r\nMX: 2\r\nST: ssdp:all\r\n\r\n"
)

// mdnsQuery is one DNS question per name, PTR, with the "answer me directly" bit (QU), so the
// answers reach this socket without joining the multicast group.
func mdnsQuery(names []string) []byte {
	message := make([]byte, 12)
	binary.BigEndian.PutUint16(message[4:], uint16(len(names)))
	for _, name := range names {
		for _, label := range strings.Split(strings.TrimSuffix(name, "."), ".") {
			message = append(message, byte(len(label)))
			message = append(message, label...)
		}
		message = append(message, 0, 0, 12, 0x80, 1) // PTR, class IN with the unicast-response bit
	}
	return message
}

// dnsName reads a (possibly compressed) name at offset; it returns the name and the offset after it.
func dnsName(message []byte, offset int) (string, int, error) {
	var labels []string
	end, jumps := -1, 0
	for {
		if offset >= len(message) {
			return "", 0, errors.New("short name")
		}
		size := int(message[offset])
		switch {
		case size == 0:
			if end < 0 {
				end = offset + 1
			}
			return strings.Join(labels, "."), end, nil
		case size&0xC0 == 0xC0:
			if offset+1 >= len(message) || jumps > 10 {
				return "", 0, errors.New("bad pointer")
			}
			if end < 0 {
				end = offset + 2
			}
			offset, jumps = int(binary.BigEndian.Uint16(message[offset:])&0x3FFF), jumps+1
		default:
			if offset+1+size > len(message) {
				return "", 0, errors.New("short label")
			}
			labels = append(labels, string(message[offset+1:offset+1+size]))
			offset += 1 + size
		}
	}
}

// parseMDNS reads the answers of one mDNS message: names of services and devices, their addresses.
func parseMDNS(message []byte) (names, services []string, err error) {
	if len(message) < 12 {
		return nil, nil, errors.New("short message")
	}
	questions := int(binary.BigEndian.Uint16(message[4:]))
	records := int(binary.BigEndian.Uint16(message[6:])) + int(binary.BigEndian.Uint16(message[8:])) + int(binary.BigEndian.Uint16(message[10:]))
	offset := 12
	for i := 0; i < questions; i++ {
		if _, offset, err = dnsName(message, offset); err != nil {
			return
		}
		offset += 4
	}
	for i := 0; i < records && offset+10 <= len(message); i++ {
		var owner string
		if owner, offset, err = dnsName(message, offset); err != nil {
			return
		}
		if offset+10 > len(message) {
			break
		}
		kind := binary.BigEndian.Uint16(message[offset:])
		length := int(binary.BigEndian.Uint16(message[offset+8:]))
		data := offset + 10
		if data+length > len(message) {
			break
		}
		switch kind {
		case 12: // PTR: a service type → an instance (the device's name)
			if target, _, e := dnsName(message, data); e == nil {
				if strings.HasPrefix(owner, "_services.") {
					services = append(services, target)
				} else {
					services = append(services, owner)
					names = append(names, strings.SplitN(target, "._", 2)[0])
				}
			}
		case 33: // SRV: the host of an instance
			if length > 6 {
				if target, _, e := dnsName(message, data+6); e == nil {
					names = append(names, strings.TrimSuffix(target, ".local"))
				}
			}
		case 1: // A
			names = append(names, strings.TrimSuffix(owner, ".local"))
		}
		offset = data + length
	}
	return
}

// parseSSDP reads the headers that say what a UPnP device is.
func parseSSDP(text string) (server, location, kind string) {
	for _, line := range strings.Split(strings.ReplaceAll(text, "\r", ""), "\n") {
		name, value, ok := strings.Cut(line, ":")
		if !ok {
			continue
		}
		value = strings.TrimSpace(value)
		switch strings.ToUpper(strings.TrimSpace(name)) {
		case "SERVER":
			server = value
		case "LOCATION":
			location = value
		case "ST", "NT":
			kind = value
		}
	}
	return
}

func addUnique(list []string, values ...string) []string {
	for _, value := range values {
		value = strings.TrimSpace(value)
		if value == "" || len(value) > 160 {
			continue
		}
		found := false
		for _, item := range list {
			if item == value {
				found = true
			}
		}
		if !found && len(list) < 20 {
			list = append(list, value)
		}
	}
	return list
}

// listenNetwork asks the network once and collects what devices say about themselves.
func listenNetwork() map[string]any {
	found := map[string]*announced{}
	get := func(address string) *announced {
		if found[address] == nil {
			found[address] = &announced{Address: address}
		}
		return found[address]
	}
	var problems []string
	collect := func(conn net.PacketConn, handle func(net.IP, []byte)) {
		buffer := make([]byte, 9000)
		_ = conn.SetReadDeadline(time.Now().Add(listenTime))
		for {
			size, from, err := conn.ReadFrom(buffer)
			if err != nil {
				return
			}
			if address, ok := from.(*net.UDPAddr); ok {
				handle(address.IP, append([]byte(nil), buffer[:size]...))
			}
		}
	}
	done := make(chan struct{}, 2)
	if conn, err := net.ListenPacket("udp4", ":0"); err == nil {
		defer conn.Close()
		_, _ = conn.WriteTo(mdnsQuery(mdnsQuestions), &net.UDPAddr{IP: net.IPv4(224, 0, 0, 251), Port: 5353})
		go func() {
			collect(conn, func(ip net.IP, message []byte) {
				names, services, _ := parseMDNS(message)
				item := get(ip.String())
				item.Names, item.Services = addUnique(item.Names, names...), addUnique(item.Services, services...)
				item.Kinds = addUnique(item.Kinds, "mDNS")
			})
			done <- struct{}{}
		}()
	} else {
		problems = append(problems, "mDNS: "+err.Error())
		done <- struct{}{}
	}
	if conn, err := net.ListenPacket("udp4", ":0"); err == nil {
		defer conn.Close()
		_, _ = conn.WriteTo([]byte(ssdpSearch), &net.UDPAddr{IP: net.IPv4(239, 255, 255, 250), Port: 1900})
		go func() {
			collect(conn, func(ip net.IP, message []byte) {
				server, location, kind := parseSSDP(string(message))
				item := get(ip.String())
				if item.Server == "" {
					item.Server = server
				}
				if item.Location == "" {
					item.Location = location
				}
				item.Services = addUnique(item.Services, kind)
				item.Kinds = addUnique(item.Kinds, "UPnP")
			})
			done <- struct{}{}
		}()
	} else {
		problems = append(problems, "SSDP: "+err.Error())
		done <- struct{}{}
	}
	<-done
	<-done
	var devices []*announced
	for _, item := range found {
		devices = append(devices, item)
	}
	sort.Slice(devices, func(i, j int) bool {
		a, b := net.ParseIP(devices[i].Address).To4(), net.ParseIP(devices[j].Address).To4()
		if a != nil && b != nil {
			return binary.BigEndian.Uint32(a) < binary.BigEndian.Uint32(b)
		}
		return devices[i].Address < devices[j].Address
	})
	return map[string]any{"devices": devices, "problems": problems, "seconds": int(listenTime.Seconds())}
}
