package main

import (
	"bytes"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"net"
	"os"
	"sort"
	"strconv"
)

// Recording the traffic of the PC (or of the Windows mobile hotspot, where a device can be
// connected so that its traffic passes through the PC). The owner starts it from the page, Windows
// asks for administrator rights (pktmon), it lasts at most five minutes and only the PC's own
// adapters are recorded. RigHaven summarises who talks with whom and keeps the .pcapng file for
// download (Wireshark).

var (
	trafficRecorder = recordTraffic
	maxCaptureBytes = int64(256 << 20)
)

type conversation struct {
	Local   string `json:"local"`
	Remote  string `json:"remote"`
	Name    string `json:"name,omitempty"`
	Proto   string `json:"proto"`
	Port    int    `json:"port"`
	Packets int    `json:"packets"`
	Bytes   int    `json:"bytes"`
}

// parsePCAPNG walks the packets of a pcapng file and calls visit with the link type and the packet.
func parsePCAPNG(data []byte, visit func(link uint16, packet []byte)) error {
	var order binary.ByteOrder = binary.LittleEndian
	var links []uint16
	for offset := 0; offset+12 <= len(data); {
		kind := order.Uint32(data[offset:])
		if kind == 0x0A0D0D0A && offset+12 <= len(data) {
			if binary.BigEndian.Uint32(data[offset+8:]) == 0x1A2B3C4D {
				order = binary.BigEndian
			} else {
				order = binary.LittleEndian
			}
			links = nil
		}
		length := int(order.Uint32(data[offset+4:]))
		if length < 12 || offset+length > len(data) {
			return errors.New("damaged capture file")
		}
		body := data[offset+8 : offset+length-4]
		switch kind {
		case 1: // interface description
			if len(body) >= 2 {
				links = append(links, order.Uint16(body))
			}
		case 6: // enhanced packet
			if len(body) >= 20 {
				iface, captured := int(order.Uint32(body)), int(order.Uint32(body[12:]))
				if iface < len(links) && 20+captured <= len(body) {
					visit(links[iface], body[20:20+captured])
				}
			}
		}
		offset += length
	}
	return nil
}

// summarizeTraffic groups the packets by conversation (addresses, protocol, service port) and
// names the remote addresses from the DNS answers seen in the same recording.
func summarizeTraffic(data []byte) (map[string]any, error) {
	type key struct {
		a, b, proto string
		port        int
	}
	talks := map[key]*conversation{}
	names := map[string]string{}
	var asked []string
	total := 0
	err := parsePCAPNG(data, func(link uint16, packet []byte) {
		var ip []byte
		switch link {
		case 1: // Ethernet
			if len(packet) < 14 {
				return
			}
			kind, rest := binary.BigEndian.Uint16(packet[12:]), packet[14:]
			if kind == 0x8100 && len(rest) >= 4 {
				kind, rest = binary.BigEndian.Uint16(rest[2:]), rest[4:]
			}
			if kind != 0x0800 && kind != 0x86DD {
				return
			}
			ip = rest
		case 101, 228, 229: // raw IP
			ip = packet
		default:
			return
		}
		if len(ip) < 20 {
			return
		}
		var src, dst net.IP
		var proto byte
		var payload []byte
		if ip[0]>>4 == 4 {
			header := int(ip[0]&15) * 4
			if header < 20 || len(ip) < header {
				return
			}
			src, dst, proto, payload = net.IP(ip[12:16]), net.IP(ip[16:20]), ip[9], ip[header:]
		} else if ip[0]>>4 == 6 && len(ip) >= 40 {
			src, dst, proto, payload = net.IP(ip[8:24]), net.IP(ip[24:40]), ip[6], ip[40:]
		} else {
			return
		}
		name := map[byte]string{6: "TCP", 17: "UDP", 1: "ICMP", 58: "ICMPv6"}[proto]
		if name == "" {
			name = "IP " + strconv.Itoa(int(proto))
		}
		sport, dport := 0, 0
		if (proto == 6 || proto == 17) && len(payload) >= 4 {
			sport, dport = int(binary.BigEndian.Uint16(payload)), int(binary.BigEndian.Uint16(payload[2:]))
		}
		if proto == 17 && len(payload) > 8 && (sport == 53 || sport == 5353) {
			readDNS(payload[8:], names, &asked)
		}
		// The service is the lower port; the local side is the private address.
		local, remote, port := src.String(), dst.String(), dport
		if sport != 0 && (sport < dport || dport == 0) {
			local, remote, port = dst.String(), src.String(), sport
		}
		if !privateAddress(net.ParseIP(local)) && privateAddress(net.ParseIP(remote)) {
			local, remote = remote, local
		}
		k := key{local, remote, name, port}
		if talks[k] == nil {
			talks[k] = &conversation{Local: local, Remote: remote, Proto: name, Port: port}
		}
		talks[k].Packets++
		talks[k].Bytes += len(packet)
		total++
	})
	if err != nil {
		return nil, err
	}
	var list []*conversation
	for _, c := range talks {
		c.Name = names[c.Remote]
		list = append(list, c)
	}
	sort.Slice(list, func(i, j int) bool { return list[i].Bytes > list[j].Bytes })
	if len(list) > 80 {
		list = list[:80]
	}
	if len(asked) > 80 {
		asked = asked[:80]
	}
	return map[string]any{"packets": total, "conversations": list, "dns": asked}, nil
}

func privateAddress(ip net.IP) bool {
	return ip != nil && (ip.IsPrivate() || ip.IsLoopback() || ip.IsLinkLocalUnicast() || ip.IsMulticast())
}

// readDNS keeps the names asked and the addresses they resolved to.
func readDNS(message []byte, names map[string]string, asked *[]string) {
	if len(message) < 12 {
		return
	}
	questions, answers := int(binary.BigEndian.Uint16(message[4:])), int(binary.BigEndian.Uint16(message[6:]))
	offset := 12
	for i := 0; i < questions; i++ {
		name, next, err := dnsName(message, offset)
		if err != nil {
			return
		}
		*asked = addUnique(*asked, name)
		offset = next + 4
	}
	for i := 0; i < answers && offset+10 <= len(message); i++ {
		name, next, err := dnsName(message, offset)
		if err != nil || next+10 > len(message) {
			return
		}
		kind, length := binary.BigEndian.Uint16(message[next:]), int(binary.BigEndian.Uint16(message[next+8:]))
		data := next + 10
		if data+length > len(message) {
			return
		}
		if (kind == 1 && length == 4) || (kind == 28 && length == 16) {
			names[net.IP(message[data:data+length]).String()] = name
		}
		offset = data + length
	}
}

// captureTraffic records, summarises and hands the file to RigHaven for download.
func captureTraffic(a *App, w WSL, args map[string]string) map[string]any {
	seconds, err := strconv.Atoi(args["seconds"])
	if err != nil || seconds < 10 || seconds > 1800 {
		return failed(errors.New(a.T("capture_seconds")))
	}
	file, err := trafficRecorder(seconds)
	if err != nil {
		return failed(fmt.Errorf(a.T("capture_failed"), err))
	}
	defer os.Remove(file)
	info, err := os.Stat(file)
	if err != nil {
		return failed(fmt.Errorf(a.T("capture_failed"), err))
	}
	data, err := os.ReadFile(file)
	if err != nil {
		return failed(err)
	}
	summary, err := summarizeTraffic(data)
	if err != nil {
		return failed(fmt.Errorf(a.T("capture_failed"), err))
	}
	summary["ok"], summary["seconds"], summary["size"] = true, seconds, info.Size()
	if info.Size() <= maxCaptureBytes {
		if err := w.Run(io.LimitReader(bytes.NewReader(data), maxCaptureBytes), io.Discard, io.Discard, root(a.Settings.Distribution, "/usr/local/bin/righaven-discovery", "capture")...); err == nil {
			summary["download"] = true
		}
	}
	return summary
}
