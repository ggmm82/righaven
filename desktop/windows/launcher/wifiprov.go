package main

import (
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"
	"unicode"
)

// A device that is not set up yet opens its own Wi-Fi network. On the owner's request (a form in
// the RigHaven page with the home Wi-Fi password, never the chat) the launcher joins that network
// for a few seconds, gives the device the home Wi-Fi name and password through the setup page of
// its firmware, and goes back to the home Wi-Fi. Tuya devices use an encrypted setup protocol and
// are added with their app instead.

type wifiJoiner interface {
	// Current is the Wi-Fi network the PC uses now ("" on Ethernet).
	Current() (string, error)
	// JoinSetup joins a network: one the PC already knows with its own profile, any other with a
	// temporary profile (open, or with the key the owner typed). temporary says whether to Forget it.
	JoinSetup(ssid, key string) (temporary bool, err error)
	// Rejoin goes back to a network the PC already knows.
	Rejoin(ssid string) error
	// Gateway is the address of the router (or device) of the network the PC is on now.
	Gateway() (string, error)
	// Forget removes the temporary profile.
	Forget(ssid string)
}

var (
	wifiSystem wifiJoiner = windowsWifi{}
	setupWait             = 20 * time.Second
	setupHTTP             = &http.Client{Timeout: 8 * time.Second}
	// Addresses of the setup page while the PC is on the device's own network.
	setupAddresses = map[string][]string{
		"tasmota": {"http://192.168.4.1"}, "esp": {"http://192.168.4.1"}, "openbeken": {"http://192.168.4.1"},
		"shelly": {"http://192.168.33.1"}, "wled": {"http://4.3.2.1"}, "daikin": {"http://192.168.127.1"},
	}
	// What each firmware tells about itself on its setup network (read only).
	explorePaths = map[string]string{"tasmota": "/cm?cmnd=Status%200", "shelly": "/shelly", "wled": "/json/info",
		"esp": "/", "openbeken": "/", "daikin": "/common/basic_info"}
	// Factory keys of setup networks that are not open.
	setupKeys = map[string]string{"wled": "wled1234"}
)

func validSSID(text string) bool {
	if text == "" || len(text) > 32 {
		return false
	}
	for _, r := range text {
		if unicode.IsControl(r) {
			return false
		}
	}
	return true
}

// provisionRequests are the setup calls of each open firmware, tried in order until one answers.
func provisionRequests(hint, base, ssid, password string) []*http.Request {
	form := func(method, path string, values url.Values) *http.Request {
		var request *http.Request
		if method == http.MethodGet {
			request, _ = http.NewRequest(method, base+path+"?"+values.Encode(), nil)
		} else {
			request, _ = http.NewRequest(method, base+path, strings.NewReader(values.Encode()))
			request.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		}
		return request
	}
	switch hint {
	case "tasmota":
		return []*http.Request{form(http.MethodGet, "/wi", url.Values{"s1": {ssid}, "p1": {password}, "save": {""}})}
	case "esp":
		return []*http.Request{form(http.MethodGet, "/wifisave", url.Values{"ssid": {ssid}, "psk": {password}})}
	case "openbeken":
		return []*http.Request{form(http.MethodGet, "/cfg_wifi_set", url.Values{"ssid": {ssid}, "pass": {password}})}
	case "wled":
		return []*http.Request{form(http.MethodPost, "/settings/wifi", url.Values{"CS0": {ssid}, "PW0": {password}, "CS": {ssid}, "CP": {password}})}
	case "shelly":
		body := fmt.Sprintf(`{"id":1,"method":"WiFi.SetConfig","params":{"config":{"sta":{"ssid":%q,"pass":%q,"enable":true}}}}`, ssid, password)
		second, _ := http.NewRequest(http.MethodPost, base+"/rpc", strings.NewReader(body))
		second.Header.Set("Content-Type", "application/json")
		return []*http.Request{second, form(http.MethodGet, "/settings/sta", url.Values{"enabled": {"1"}, "ssid": {ssid}, "key": {password}})}
	}
	return nil
}

// provisionWifi carries the home Wi-Fi to one device in setup mode. The home password is used
// for this request only: it is not stored and not returned.
func provisionWifi(a *App, args map[string]string) map[string]any {
	device, hint, password := args["ssid"], args["hint"], args["password"]
	if hint == "tuya" {
		return failed(errors.New(a.T("wifi_tuya")))
	}
	if !validSSID(device) || setupAddresses[hint] == nil || len(provisionRequests(hint, "", "", "")) == 0 {
		return failed(errors.New(a.T("wifi_unsupported")))
	}
	if len(password) < 8 || len(password) > 63 {
		return failed(errors.New(a.T("wifi_password")))
	}
	home := args["home"]
	if home == "" {
		home, _ = wifiSystem.Current()
	}
	if !validSSID(home) {
		return failed(errors.New(a.T("wifi_home")))
	}
	temporary, err := wifiSystem.JoinSetup(device, setupKeys[hint])
	if err != nil {
		return failed(fmt.Errorf(a.T("wifi_join"), device, err))
	}
	if temporary {
		defer wifiSystem.Forget(device)
	}
	sent, problem := false, error(nil)
	deadline := time.Now().Add(setupWait)
	for !sent && time.Now().Before(deadline) {
		for _, base := range setupAddresses[hint] {
			for _, request := range provisionRequests(hint, base, home, password) {
				response, err := setupHTTP.Do(request)
				if err != nil {
					problem = err
					continue
				}
				_, _ = io.Copy(io.Discard, io.LimitReader(response.Body, 1<<16))
				response.Body.Close()
				if response.StatusCode < 400 {
					sent = true
					break
				}
				problem = fmt.Errorf("HTTP %d", response.StatusCode)
			}
			if sent {
				break
			}
		}
		if !sent {
			time.Sleep(time.Second)
		}
	}
	back := wifiSystem.Rejoin(home)
	if !sent {
		message := fmt.Sprintf(a.T("wifi_not_sent"), device)
		if problem != nil {
			message += ": " + strings.ReplaceAll(problem.Error(), password, "***")
		}
		return failed(errors.New(message))
	}
	if back != nil {
		return failed(fmt.Errorf(a.T("wifi_back"), home, back))
	}
	return map[string]any{"ok": true, "home": home}
}

var htmlTitle = regexp.MustCompile(`(?is)<title>\s*(.*?)\s*</title>`)

// exploreSetup joins a device's setup network for a few seconds and reads what the device says
// about itself (model, firmware, name): nothing is changed on the device.
func exploreSetup(a *App, args map[string]string) map[string]any {
	device, hint, key := args["ssid"], args["hint"], args["key"]
	if hint == "tuya" {
		return failed(errors.New(a.T("wifi_tuya")))
	}
	if !validSSID(device) {
		return failed(errors.New(a.T("wifi_unsupported")))
	}
	if key == "" {
		key = setupKeys[hint]
	}
	home, _ := wifiSystem.Current()
	if home != device {
		temporary, err := wifiSystem.JoinSetup(device, key)
		if err != nil {
			return failed(fmt.Errorf(a.T("wifi_join"), device, err))
		}
		if temporary {
			defer wifiSystem.Forget(device)
		}
	}
	var body []byte
	var problem error
	address := ""
	deadline := time.Now().Add(setupWait)
	for body == nil && time.Now().Before(deadline) {
		bases, path := setupAddresses[hint], explorePaths[hint]
		if len(bases) == 0 || path == "" {
			// Any other network: the home page of whatever answers as its router.
			path = "/"
			if gateway, err := wifiSystem.Gateway(); err == nil && gateway != "" {
				bases, address = []string{"http://" + gateway}, gateway
			}
		}
		for _, base := range bases {
			response, err := setupHTTP.Get(base + path)
			if err != nil {
				problem = err
				continue
			}
			body, _ = io.ReadAll(io.LimitReader(response.Body, 64<<10))
			response.Body.Close()
			break
		}
		if body == nil {
			time.Sleep(time.Second)
		}
	}
	if home != "" && home != device {
		if err := wifiSystem.Rejoin(home); err != nil {
			return failed(fmt.Errorf(a.T("wifi_back"), home, err))
		}
	}
	if body == nil {
		message := fmt.Sprintf(a.T("wifi_not_read"), device)
		if problem != nil {
			message += ": " + problem.Error()
		}
		return failed(errors.New(message))
	}
	result := map[string]any{"ok": true, "ssid": device}
	if address != "" {
		result["address"] = address
	}
	if match := htmlTitle.FindSubmatch(body); match != nil {
		result["title"] = strings.TrimSpace(string(match[1]))
	} else {
		text := strings.TrimSpace(string(body))
		if len(text) > 20000 {
			text = text[:20000]
		}
		result["info"] = text
	}
	return result
}
