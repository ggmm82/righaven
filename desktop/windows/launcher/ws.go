package main

import (
	"bufio"
	"crypto/rand"
	"crypto/sha1"
	"crypto/tls"
	"encoding/base64"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

// A minimal WebSocket client (RFC 6455) for RigHaven Agent: text and binary messages, ping/pong,
// close. The launcher has no third-party dependencies, so it carries its own.

const (
	wsText   = 1
	wsBinary = 2
	wsClose  = 8
	wsPing   = 9
	wsPong   = 10
	wsLimit  = 4 << 20
)

type wsConn struct {
	conn   net.Conn
	reader *bufio.Reader
	write  sync.Mutex
}

// wsDial opens wss:// (or ws://) for an http(s) server address, with extra headers.
func wsDial(server, path string, header http.Header, timeout time.Duration) (*wsConn, error) {
	base, err := url.Parse(strings.TrimRight(server, "/"))
	if err != nil || (base.Scheme != "https" && base.Scheme != "http") || base.Host == "" {
		return nil, fmt.Errorf("invalid server address %q", server)
	}
	host := base.Host
	if base.Port() == "" {
		if base.Scheme == "https" {
			host += ":443"
		} else {
			host += ":80"
		}
	}
	dialer := &net.Dialer{Timeout: timeout, KeepAlive: 30 * time.Second}
	var conn net.Conn
	if base.Scheme == "https" {
		conn, err = tls.DialWithDialer(dialer, "tcp", host, &tls.Config{ServerName: base.Hostname(), MinVersion: tls.VersionTLS12})
	} else {
		conn, err = dialer.Dial("tcp", host)
	}
	if err != nil {
		return nil, err
	}
	keyBytes := make([]byte, 16)
	_, _ = rand.Read(keyBytes)
	key := base64.StdEncoding.EncodeToString(keyBytes)
	request := &http.Request{Method: "GET", URL: &url.URL{Scheme: base.Scheme, Host: base.Host, Path: strings.TrimRight(base.Path, "/") + path},
		Host: base.Host, Header: http.Header{}, ProtoMajor: 1, ProtoMinor: 1}
	for name, values := range header {
		request.Header[name] = values
	}
	request.Header.Set("Upgrade", "websocket")
	request.Header.Set("Connection", "Upgrade")
	request.Header.Set("Sec-WebSocket-Key", key)
	request.Header.Set("Sec-WebSocket-Version", "13")
	_ = conn.SetDeadline(time.Now().Add(timeout))
	if err := request.Write(conn); err != nil {
		conn.Close()
		return nil, err
	}
	reader := bufio.NewReader(conn)
	response, err := http.ReadResponse(reader, request)
	if err != nil {
		conn.Close()
		return nil, err
	}
	if response.StatusCode != http.StatusSwitchingProtocols {
		conn.Close()
		return nil, &wsRefused{Status: response.StatusCode}
	}
	sum := sha1.Sum([]byte(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"))
	if response.Header.Get("Sec-WebSocket-Accept") != base64.StdEncoding.EncodeToString(sum[:]) {
		conn.Close()
		return nil, errors.New("the server did not accept the WebSocket")
	}
	_ = conn.SetDeadline(time.Time{})
	return &wsConn{conn: conn, reader: reader}, nil
}

type wsRefused struct{ Status int }

func (e *wsRefused) Error() string {
	return fmt.Sprintf("the server refused the connection (HTTP %d)", e.Status)
}

func (c *wsConn) writeFrame(opcode byte, payload []byte) error {
	c.write.Lock()
	defer c.write.Unlock()
	header := []byte{0x80 | opcode}
	switch size := len(payload); {
	case size < 126:
		header = append(header, 0x80|byte(size))
	case size < 1<<16:
		header = append(header, 0x80|126, byte(size>>8), byte(size))
	default:
		header = append(header, 0x80|127)
		header = binary.BigEndian.AppendUint64(header, uint64(size))
	}
	mask := make([]byte, 4)
	_, _ = rand.Read(mask)
	header = append(header, mask...)
	masked := make([]byte, len(payload))
	for i, b := range payload {
		masked[i] = b ^ mask[i%4]
	}
	_ = c.conn.SetWriteDeadline(time.Now().Add(30 * time.Second))
	_, err := c.conn.Write(append(header, masked...))
	return err
}

func (c *wsConn) WriteText(text []byte) error   { return c.writeFrame(wsText, text) }
func (c *wsConn) WriteBinary(data []byte) error { return c.writeFrame(wsBinary, data) }
func (c *wsConn) Ping() error                   { return c.writeFrame(wsPing, nil) }
func (c *wsConn) Close() error {
	_ = c.writeFrame(wsClose, []byte{0x03, 0xe8})
	return c.conn.Close()
}

// ReadMessage returns the next text or binary message, answering pings on the way.
func (c *wsConn) ReadMessage() (int, []byte, error) {
	var message []byte
	kind := 0
	for {
		head := make([]byte, 2)
		if _, err := io.ReadFull(c.reader, head); err != nil {
			return 0, nil, err
		}
		final, opcode, masked := head[0]&0x80 != 0, head[0]&0x0f, head[1]&0x80 != 0
		size := uint64(head[1] & 0x7f)
		switch size {
		case 126:
			extra := make([]byte, 2)
			if _, err := io.ReadFull(c.reader, extra); err != nil {
				return 0, nil, err
			}
			size = uint64(binary.BigEndian.Uint16(extra))
		case 127:
			extra := make([]byte, 8)
			if _, err := io.ReadFull(c.reader, extra); err != nil {
				return 0, nil, err
			}
			size = binary.BigEndian.Uint64(extra)
		}
		if size > wsLimit || uint64(len(message))+size > wsLimit {
			return 0, nil, errors.New("message too large")
		}
		var mask []byte
		if masked {
			mask = make([]byte, 4)
			if _, err := io.ReadFull(c.reader, mask); err != nil {
				return 0, nil, err
			}
		}
		payload := make([]byte, size)
		if _, err := io.ReadFull(c.reader, payload); err != nil {
			return 0, nil, err
		}
		for i := range payload {
			if masked {
				payload[i] ^= mask[i%4]
			}
		}
		switch opcode {
		case wsPing:
			if err := c.writeFrame(wsPong, payload); err != nil {
				return 0, nil, err
			}
			continue
		case wsPong:
			continue
		case wsClose:
			return 0, nil, io.EOF
		case 0: // continuation
		default:
			kind = int(opcode)
		}
		message = append(message, payload...)
		if final {
			return kind, message, nil
		}
	}
}
