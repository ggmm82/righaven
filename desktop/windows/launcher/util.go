package main

import (
	"crypto/sha256"
	"encoding/hex"
	"io"
	"os"
)

func sha256File(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer file.Close()
	hash := sha256.New()
	if _, err := io.Copy(hash, file); err != nil {
		return "", err
	}
	return hex.EncodeToString(hash.Sum(nil)), nil
}

type crlf struct {
	w    io.Writer
	last byte
}

func (c *crlf) Write(data []byte) (int, error) {
	out := make([]byte, 0, len(data)+16)
	for _, b := range data {
		if b == '\n' && c.last != '\r' {
			out = append(out, '\r')
		}
		out = append(out, b)
		c.last = b
	}
	if _, err := c.w.Write(out); err != nil {
		return 0, err
	}
	return len(data), nil
}
