//go:build windows

package main

import (
	"bufio"
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"encoding/xml"
	"errors"
	"fmt"
	"io"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"sync/atomic"
	"syscall"
	"time"
	"unsafe"
)

var (
	kernel32                     = syscall.NewLazyDLL("kernel32.dll")
	procGetUserDefaultUILanguage = kernel32.NewProc("GetUserDefaultUILanguage")
	procGetConsoleProcessList    = kernel32.NewProc("GetConsoleProcessList")
)

const (
	detachedProcess       = 0x00000008
	createNewProcessGroup = 0x00000200
	langItalian           = 0x10
)

func uiLanguage() string {
	if id, _, _ := procGetUserDefaultUILanguage.Call(); id&0x3ff == langItalian {
		return "it"
	}
	return "en"
}

func openBrowser(url string) {
	_ = exec.Command("rundll32", "url.dll,FileProtocolHandler", url).Start()
}

// pauseIfOwnConsole keeps the window open after an error when RigHaven.exe was
// started with a double click (the console belongs to this process only).
func pauseIfOwnConsole(a *App) {
	var ids [4]uint32
	count, _, _ := procGetConsoleProcessList.Call(uintptr(unsafe.Pointer(&ids[0])), uintptr(len(ids)))
	if count != 1 {
		return
	}
	message := "Press Enter to close."
	if a != nil {
		message = a.T("press_enter")
	} else if uiLanguage() == "it" {
		message = "Premi Invio per chiudere."
	}
	fmt.Fprintln(os.Stderr, message)
	_, _ = bufio.NewReader(os.Stdin).ReadString('\n')
}

func installWSLElevated() error {
	return exec.Command("powershell.exe", "-NoProfile", "-Command",
		"Start-Process -FilePath wsl.exe -ArgumentList '--install','--no-distribution' -Verb RunAs -Wait").Run()
}

// stopDetached continues the clean stop after the console window has been closed.
func stopDetached(a *App) {
	w := newWSL().(execWSL)
	cmd := exec.Command(w.exe, root(a.Settings.Distribution, "/usr/local/bin/righaven-stop")...)
	cmd.SysProcAttr = &syscall.SysProcAttr{CreationFlags: detachedProcess | createNewProcessGroup, HideWindow: true}
	_ = cmd.Start()
}

// console writes CRLF line ends: after wsl.exe the console no longer returns the carriage on LF.
func console(w io.Writer) io.Writer { return &crlf{w: w} }

// execUSB runs usbipd-win from PATH or its default installation folder.
type execUSB struct{}

func newUSB() USB { return execUSB{} }

func usbipdPath() string {
	if path, err := exec.LookPath("usbipd.exe"); err == nil {
		return path
	}
	return filepath.Join(os.Getenv("ProgramFiles"), "usbipd-win", "usbipd.exe")
}

func (execUSB) Output(args ...string) (string, error) {
	cmd := exec.Command(usbipdPath(), args...)
	var out bytes.Buffer
	cmd.Stdout, cmd.Stderr = &out, &out
	err := cmd.Run()
	return out.String(), err
}

func quoteArgs(args []string) string {
	quoted := make([]string, len(args))
	for i, arg := range args {
		quoted[i] = "'" + strings.ReplaceAll(arg, "'", "''") + "'"
	}
	return strings.Join(quoted, ",")
}

func (execUSB) Elevated(args ...string) error {
	script := fmt.Sprintf("$p = Start-Process -FilePath '%s' -ArgumentList %s -Verb RunAs -Wait -PassThru -WindowStyle Hidden; exit $p.ExitCode",
		strings.ReplaceAll(usbipdPath(), "'", "''"), quoteArgs(args))
	return exec.Command("powershell.exe", "-NoProfile", "-Command", script).Run()
}

func (execUSB) Install() error {
	cmd := exec.Command("winget", "install", "--exact", "--id", "dorssel.usbipd-win", "--accept-package-agreements", "--accept-source-agreements")
	cmd.Stdout, cmd.Stderr, cmd.Stdin = os.Stdout, os.Stderr, os.Stdin
	return cmd.Run()
}

// bluetoothScript asks Windows for Bluetooth devices: nearby and paired ones (Low Energy and
// classic, through the Windows device enumeration, which scans for some seconds) and the serial
// ports Windows created for paired devices (for example an OBD-II adapter, "COM5").
const bluetoothScript = `
$ErrorActionPreference = 'Stop'
$found = @(); $problems = @()
# Windows PowerShell cannot subscribe to Windows Runtime events nor wait for their asynchronous
# calls reliably, so the .NET Framework compiler of Windows builds a small program that listens for
# 15 seconds to Bluetooth LE broadcasts (sensor readings) and meanwhile asks Windows for the nearby
# and paired devices (Low Energy and classic). Only Windows Runtime types are used, no extension.
try {
  $runtime = [System.Runtime.InteropServices.RuntimeEnvironment]::GetRuntimeDirectory()
  $winmd = Join-Path $env:windir 'System32\WinMetadata'
  $work = Join-Path $env:TEMP 'righaven-ble'; $null = New-Item -ItemType Directory -Force -Path $work
  $source = Join-Path $work 'scan.cs'; $program = Join-Path $work 'scan.exe'
  Set-Content -Path $source -Encoding UTF8 -Value @'
using System; using System.Collections.Generic; using System.Linq; using System.Threading;
using Windows.Foundation; using Windows.Devices.Bluetooth.Advertisement; using Windows.Devices.Enumeration; using Windows.Storage.Streams;
public static class Scan {
  static string Clean(object value) { return value == null ? "" : value.ToString().Replace("|", " ").Replace("\r", " ").Replace("\n", " "); }
  static object Get(DeviceInformation item, string key) { object value; return item.Properties.TryGetValue(key, out value) ? value : null; }
  public static void Main(string[] args) {
    var started = DateTime.UtcNow; int seconds = int.Parse(args[0]);
    var heard = new Dictionary<ulong, string[]>(); var service = new Dictionary<ulong, Dictionary<string, string>>();
    BluetoothLEAdvertisementWatcher watcher = null;
    try {
      watcher = new BluetoothLEAdvertisementWatcher(); watcher.ScanningMode = BluetoothLEScanningMode.Active;
      watcher.Received += (sender, e) => { lock (heard) {
        string[] entry; if (!heard.TryGetValue(e.BluetoothAddress, out entry)) { entry = new string[] { "", "0", "" }; heard[e.BluetoothAddress] = entry; service[e.BluetoothAddress] = new Dictionary<string, string>(); }
        if (!String.IsNullOrEmpty(e.Advertisement.LocalName)) entry[0] = Clean(e.Advertisement.LocalName);
        foreach (var maker in e.Advertisement.ManufacturerData) { entry[2] = maker.CompanyId.ToString("x4"); break; }
        entry[1] = e.RawSignalStrengthInDBm.ToString();
        foreach (var section in e.Advertisement.DataSections) {
          if (section.DataType != 0x16 || section.Data.Length <= 2) continue;
          var bytes = new byte[section.Data.Length]; DataReader.FromBuffer(section.Data).ReadBytes(bytes);
          service[e.BluetoothAddress][bytes[1].ToString("x2") + bytes[0].ToString("x2")] = String.Concat(bytes.Skip(2).Select(b => b.ToString("x2")));
        } } };
      watcher.Start();
    } catch (Exception error) { Console.WriteLine("E|readings|" + Clean(error.Message)); watcher = null; }
    try {
      var selector = "System.Devices.Aep.ProtocolId:=\"{bb7bb05e-5972-42b5-94fc-76eaa7084d49}\" OR System.Devices.Aep.ProtocolId:=\"{e0cbf06c-cd8b-4647-bb8a-263b43f0f974}\"";
      var properties = new string[] { "System.Devices.Aep.DeviceAddress", "System.Devices.Aep.IsPaired", "System.Devices.Aep.SignalStrength", "System.Devices.Aep.ProtocolId", "System.Devices.Aep.IsPresent", "System.Devices.Aep.IsConnected" };
      var search = DeviceInformation.FindAllAsync(selector, properties, DeviceInformationKind.AssociationEndpoint);
      while (search.Status == AsyncStatus.Started && (DateTime.UtcNow - started).TotalSeconds < 60) Thread.Sleep(100);
      if (search.Status != AsyncStatus.Completed) throw search.ErrorCode ?? new TimeoutException("no answer from Windows");
      foreach (var item in search.GetResults()) {
        var paired = Get(item, "System.Devices.Aep.IsPaired") as bool?;
        var kind = Clean(Get(item, "System.Devices.Aep.ProtocolId")).ToLowerInvariant().Contains("bb7bb05e") ? "ble" : "classic";
        var present = Get(item, "System.Devices.Aep.IsPresent") as bool?;
        var connected = Get(item, "System.Devices.Aep.IsConnected") as bool?;
        Console.WriteLine("D|" + kind + "|" + (paired == true ? "1" : "0") + "|" + Clean(Get(item, "System.Devices.Aep.SignalStrength")) + "|" + Clean(Get(item, "System.Devices.Aep.DeviceAddress")) + "|" + (present == true || connected == true ? "1" : "0") + (connected == true ? "c" : "") + "|" + Clean(item.Name));
      }
    } catch (Exception error) { Console.WriteLine("E|devices|" + Clean(error.Message)); }
    if (watcher == null) return;
    var left = seconds * 1000 - (int)(DateTime.UtcNow - started).TotalMilliseconds; if (left > 0) Thread.Sleep(left);
    watcher.Stop();
    // Every device heard now: sensors with their readings (S), the others with name and signal (H).
    lock (heard) { foreach (var pair in heard) {
      if (service[pair.Key].Count == 0) { Console.WriteLine("H|" + pair.Key.ToString("X12") + "|" + pair.Value[1] + "|" + pair.Value[2] + "|" + pair.Value[0]); continue; }
      Console.WriteLine("S|" + pair.Key.ToString("X12") + "|" + pair.Value[1] + "|" + String.Join(";", service[pair.Key].Select(s => s.Key + "=" + s.Value)) + "|" + pair.Value[2] + "|" + pair.Value[0]); } }
  }
}
'@
  $references = @('System.Runtime.dll', 'System.Runtime.WindowsRuntime.dll', 'System.Runtime.InteropServices.WindowsRuntime.dll', 'System.Threading.Tasks.dll') |
    ForEach-Object { Join-Path $runtime $_ } | Where-Object { Test-Path $_ }
  $references += @('Windows.Foundation.winmd', 'Windows.Devices.winmd', 'Windows.Storage.winmd') | ForEach-Object { Join-Path $winmd $_ }
  $arguments = @('/nologo', '/target:exe', ('/out:' + $program)) + ($references | ForEach-Object { '/r:' + $_ }) + @($source)
  $ErrorActionPreference = 'Continue'
  $compiler = & (Join-Path $runtime 'csc.exe') $arguments 2>&1
  $built = $LASTEXITCODE -eq 0
  $ErrorActionPreference = 'Stop'
  if (-not $built) { throw ('search program not built: ' + (($compiler | Where-Object { "$_" -match 'error' } | Select-Object -First 2) -join ' ')) }
  foreach ($line in (& $program 15)) {
    $parts = "$line" -split '\|'
    switch ($parts[0]) {
      'E' { $problems += ($parts[1] + ': ' + ($parts[2..($parts.Length - 1)] -join ' ')) }
      'D' { $found += [pscustomobject]@{ name = ($parts[6..($parts.Length - 1)] -join ' '); address = $parts[4].ToUpper(); kind = $parts[1]; paired = $parts[2] -eq '1'; present = $parts[5].StartsWith('1'); connected = $parts[5].EndsWith('c'); signal = $(if ($parts[3]) { [int]$parts[3] } else { $null }) } }
      'H' { $found += [pscustomobject]@{ name = ($parts[4..($parts.Length - 1)] -join ' '); address = ($parts[1] -replace '(..)(?!$)', '$1:'); kind = 'ble'; paired = $false; present = $true; signal = [int]$parts[2]; company = $parts[3] } }
      'S' {
        $data = @{}
        foreach ($pair in ($parts[3] -split ';')) { $kv = $pair -split '=', 2; $data[$kv[0]] = $kv[1] }
        $found += [pscustomobject]@{ name = ($parts[5..($parts.Length - 1)] -join ' '); address = ($parts[1] -replace '(..)(?!$)', '$1:'); kind = 'ble'; paired = $false; present = $true; signal = [int]$parts[2]; service_data = $data; company = $parts[4] }
      }
    }
  }
} catch { $problems += 'devices: ' + $_.Exception.Message }
# Serial ports Windows created for paired devices (for example an OBD-II adapter, "COM5").
foreach ($port in (Get-PnpDevice -Class Ports -PresentOnly -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like 'BTHENUM*' })) {
  if ($port.FriendlyName -match '\((COM\d+)\)') { $found += [pscustomobject]@{ name = $port.FriendlyName; port = $Matches[1]; kind = 'serial'; paired = $true; present = $true; address = '' } }
}
if ($found.Count -eq 0 -and $problems.Count -gt 0) {
  if (-not (Get-PnpDevice -Class Bluetooth -PresentOnly -Status OK -ErrorAction SilentlyContinue)) { [Console]::Error.WriteLine('no-adapter') } else { [Console]::Error.WriteLine($problems[-1]) }
  exit 1
}
foreach ($problem in $problems) { [Console]::Error.WriteLine($problem) }
ConvertTo-Json -InputObject @($found) -Compress
`

func scanBluetooth() ([]btDevice, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()
	cmd := exec.CommandContext(ctx, "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", bluetoothScript)
	var out, errs bytes.Buffer
	cmd.Stdout, cmd.Stderr = &out, &errs
	if err := cmd.Run(); err != nil {
		message := strings.TrimSpace(errs.String())
		if lines := strings.Split(message, "\n"); len(lines) > 0 {
			message = strings.TrimSpace(lines[len(lines)-1])
		}
		if message == "no-adapter" {
			return nil, errBluetoothAdapter
		}
		return nil, fmt.Errorf("%s", message)
	}
	for _, line := range strings.Split(errs.String(), "\n") {
		if line = strings.TrimSpace(line); strings.HasPrefix(line, "readings: ") || strings.HasPrefix(line, "devices: ") {
			bluetoothWarnings = append(bluetoothWarnings, line)
		}
	}
	return parseBluetooth(out.Bytes())
}

var procSetCommTimeouts = kernel32.NewProc("SetCommTimeouts")

type commTimeouts struct {
	ReadIntervalTimeout, ReadTotalTimeoutMultiplier, ReadTotalTimeoutConstant, WriteTotalTimeoutMultiplier, WriteTotalTimeoutConstant uint32
}

// openSerialPort opens a COM port as it is configured in Windows (speed set by the driver; a
// Bluetooth serial link ignores it). Reads return what arrived within 100 ms.
func openSerialPort(name string) (io.ReadWriteCloser, error) {
	if !comName.MatchString(name) {
		return nil, fmt.Errorf("invalid port %q", name)
	}
	path, err := syscall.UTF16PtrFromString(`\\.\` + name)
	if err != nil {
		return nil, err
	}
	handle, err := syscall.CreateFile(path, syscall.GENERIC_READ|syscall.GENERIC_WRITE, 0, nil, syscall.OPEN_EXISTING, 0, 0)
	if err != nil {
		return nil, err
	}
	timeouts := commTimeouts{ReadIntervalTimeout: 0xFFFFFFFF, ReadTotalTimeoutMultiplier: 0xFFFFFFFF, ReadTotalTimeoutConstant: 100, WriteTotalTimeoutConstant: 2000}
	if ok, _, err := procSetCommTimeouts.Call(uintptr(handle), uintptr(unsafe.Pointer(&timeouts))); ok == 0 {
		syscall.CloseHandle(handle)
		return nil, err
	}
	return &serialPort{File: os.NewFile(uintptr(handle), name)}, nil
}

// serialPort waits for the next bytes: a COM port returns nothing after its 100 ms read timeout,
// which os.File reports as the end of the file.
type serialPort struct {
	*os.File
	closed atomic.Bool
}

func (p *serialPort) Read(buffer []byte) (int, error) {
	for {
		n, err := p.File.Read(buffer)
		if n > 0 || err != io.EOF || p.closed.Load() {
			return n, err
		}
	}
}

func (p *serialPort) Close() error {
	p.closed.Store(true)
	return p.File.Close()
}

// listCOMPorts returns the present serial ports with their Windows names.
func listCOMPorts() ([]comPort, error) {
	// Ports Windows creates for paired classic Bluetooth devices carry the device's address in
	// their instance ID (BTHENUM\{...}\...&661E32FA3C20_C00000000); incoming ports have zeros.
	script := `Get-PnpDevice -Class Ports -PresentOnly -ErrorAction SilentlyContinue | ForEach-Object { if ($_.FriendlyName -match '\((COM\d+)\)') { $name = $Matches[1]; $address = ''; if ($_.InstanceId -match '^BTHENUM\\.*&([0-9A-F]{12})_' -and $Matches[1] -ne '000000000000') { $address = $Matches[1] }; [pscustomobject]@{ name = $name; label = $_.FriendlyName; address = $address } } } | ConvertTo-Json -Compress`
	output, err := exec.Command("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script).Output()
	if err != nil {
		return nil, err
	}
	output = bytes.TrimSpace(output)
	if len(output) == 0 {
		return nil, nil
	}
	if output[0] == '{' {
		output = append(append([]byte{'['}, output...), ']')
	}
	var ports []comPort
	return ports, json.Unmarshal(output, &ports)
}

type windowsMatter struct{}

func (windowsMatter) WindowsBuild() (int, error) {
	output, err := exec.Command("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "[Environment]::OSVersion.Version.Build").Output()
	if err != nil {
		return 0, err
	}
	var build int
	_, err = fmt.Sscan(strings.TrimSpace(string(output)), &build)
	return build, err
}

func (windowsMatter) ConfigPath() string {
	return filepath.Join(os.Getenv("USERPROFILE"), ".wslconfig")
}

// AllowFirewall lets mDNS answers and Matter traffic (UDP 5353 and 5540) reach WSL in the
// Hyper-V firewall: one administrator prompt.
func (windowsMatter) AllowFirewall() error {
	rule := "if (-not (Get-NetFirewallHyperVRule -Name 'RigHaven-Matter' -ErrorAction SilentlyContinue)) { " +
		"New-NetFirewallHyperVRule -Name 'RigHaven-Matter' -DisplayName 'RigHaven Matter (mDNS, Matter)' -Direction Inbound " +
		"-VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -Protocol UDP -LocalPorts 5353,5540 -Action Allow }"
	script := fmt.Sprintf("$p = Start-Process -FilePath powershell.exe -ArgumentList '-NoProfile','-Command',\"%s\" -Verb RunAs -Wait -PassThru -WindowStyle Hidden; exit $p.ExitCode",
		strings.ReplaceAll(rule, `"`, "`\""))
	return exec.Command("powershell.exe", "-NoProfile", "-Command", script).Run()
}

func (windowsMatter) ShutdownWSL() error {
	return exec.Command(newWSL().(execWSL).exe, "--shutdown").Run()
}

// scanWifi asks Windows for the visible Wi-Fi networks. Windows 11 may require location services
// to be on for this; its message is returned as the error.
var (
	wlanapi                = syscall.NewLazyDLL("wlanapi.dll")
	procWlanOpenHandle     = wlanapi.NewProc("WlanOpenHandle")
	procWlanEnumInterfaces = wlanapi.NewProc("WlanEnumInterfaces")
	procWlanScan           = wlanapi.NewProc("WlanScan")
	procWlanFreeMemory     = wlanapi.NewProc("WlanFreeMemory")
	procWlanCloseHandle    = wlanapi.NewProc("WlanCloseHandle")
)

// refreshWifi asks every Wi-Fi adapter for a new scan: netsh only shows what Windows remembers
// from the last scan, often just the network the PC is connected to.
func refreshWifi() bool {
	if wlanapi.Load() != nil {
		return false
	}
	var negotiated uint32
	var handle uintptr
	if r, _, _ := procWlanOpenHandle.Call(2, 0, uintptr(unsafe.Pointer(&negotiated)), uintptr(unsafe.Pointer(&handle))); r != 0 {
		return false
	}
	defer procWlanCloseHandle.Call(handle, 0)
	var list unsafe.Pointer
	if r, _, _ := procWlanEnumInterfaces.Call(handle, 0, uintptr(unsafe.Pointer(&list))); r != 0 || list == nil {
		return false
	}
	defer procWlanFreeMemory.Call(uintptr(list))
	// WLAN_INTERFACE_INFO_LIST: two DWORDs, then entries of a GUID, a 256-character description and a state.
	count := *(*uint32)(list)
	scanned := false
	for i := uintptr(0); i < uintptr(count) && i < 16; i++ {
		guid := unsafe.Add(list, 8+i*(16+512+4))
		if r, _, _ := procWlanScan.Call(handle, uintptr(guid), 0, 0, 0); r == 0 {
			scanned = true
		}
	}
	return scanned
}

func scanWifi() ([]wifiNetwork, error) {
	if refreshWifi() {
		time.Sleep(5 * time.Second) // Windows completes a scan within about four seconds
	}
	output, err := exec.Command("netsh", "wlan", "show", "networks", "mode=bssid").CombinedOutput()
	if err != nil {
		return nil, fmt.Errorf("%s", firstLine(strings.TrimSpace(string(output))))
	}
	return parseNetsh(string(output)), nil
}

// gattSource talks to one Bluetooth LE device with Windows Runtime types only (no extension
// methods, which the .NET Framework compiler cannot bind to the split Windows metadata).
const gattSource = `
using System; using System.Linq; using System.Threading;
using Windows.Foundation; using Windows.Devices.Bluetooth; using Windows.Devices.Bluetooth.GenericAttributeProfile; using Windows.Storage.Streams;
public static class Gatt {
  static T Wait<T>(IAsyncOperation<T> operation) {
    var started = DateTime.UtcNow;
    while (operation.Status == AsyncStatus.Started) {
      if ((DateTime.UtcNow - started).TotalSeconds > 10 || DateTime.UtcNow > Deadline) { try { operation.Cancel(); } catch (Exception) { } throw new TimeoutException("the device did not answer in time"); }
      Thread.Sleep(50); }
    if (operation.Status != AsyncStatus.Completed) throw operation.ErrorCode ?? new Exception(operation.Status.ToString());
    return operation.GetResults();
  }
  // The whole operation ends within 50 seconds, whatever the device does (a stream lasts until its input ends).
  static DateTime Deadline = DateTime.UtcNow.AddSeconds(50);
  static string Clean(object value) { return value == null ? "" : value.ToString().Replace("|", " ").Replace("\r", " ").Replace("\n", " "); }
  static string Hex(IBuffer buffer) { var bytes = new byte[buffer.Length]; DataReader.FromBuffer(buffer).ReadBytes(bytes); return String.Concat(bytes.Select(b => b.ToString("x2"))); }
  // Many Bluetooth LE devices use a random (static) address: try it as public, then as random.
  static BluetoothLEDevice Open(ulong address, out GattDeviceServicesResult services) {
    services = null; string last = "device not found or not in range";
    foreach (var type in new[] { BluetoothAddressType.Public, BluetoothAddressType.Random }) {
      BluetoothLEDevice device = null;
      try { device = Wait(BluetoothLEDevice.FromBluetoothAddressAsync(address, type)); } catch (Exception error) { last = Clean(error.Message); }
      if (device == null) continue;
      var result = Wait(device.GetGattServicesAsync(BluetoothCacheMode.Uncached));
      if (result.Status == GattCommunicationStatus.Success) { services = result; return device; }
      last = "services not readable: " + result.Status; device.Dispose();
    }
    throw new Exception(last);
  }
  static GattCharacteristic Find(GattDeviceServicesResult services, string service, string characteristic) {
    var wanted = Guid.Parse(service); GattDeviceService found = null;
    foreach (var item in services.Services) if (item.Uuid == wanted) found = item;
    if (found == null) throw new Exception("service not found: " + service);
    var characteristics = Wait(found.GetCharacteristicsForUuidAsync(Guid.Parse(characteristic), BluetoothCacheMode.Uncached));
    if (characteristics.Status != GattCommunicationStatus.Success || characteristics.Characteristics.Count == 0) throw new Exception("characteristic not found: " + characteristic);
    return characteristics.Characteristics[0];
  }
  // The first characteristic of the service that notifies (or indicates): where adapters answer.
  static GattCharacteristic Listener(GattDeviceServicesResult services, string service) {
    var wanted = Guid.Parse(service);
    foreach (var item in services.Services) {
      if (item.Uuid != wanted) continue;
      var characteristics = Wait(item.GetCharacteristicsAsync(BluetoothCacheMode.Uncached));
      if (characteristics.Status != GattCommunicationStatus.Success) break;
      foreach (var candidate in characteristics.Characteristics)
        if ((candidate.CharacteristicProperties & (GattCharacteristicProperties.Notify | GattCharacteristicProperties.Indicate)) != 0) return candidate;
    }
    throw new Exception("no characteristic of " + service + " notifies");
  }
  static byte[] Bytes(string hex) { return Enumerable.Range(0, hex.Length / 2).Select(i => Convert.ToByte(hex.Substring(i * 2, 2), 16)).ToArray(); }
  // exchange: listen to the notify characteristic, then write each command and collect what the
  // device notifies until the end byte (the ELM327 prompt is 3e) or until the wait is over.
  static void Exchange(GattDeviceServicesResult services, string[] args) {
    var target = Find(services, args[2], args[3]);
    var listen = args[4] == "" ? Listener(services, args[2]) : Find(services, args[2], args[4]);
    var received = new System.Collections.Generic.List<byte>(); var gate = new object();
    listen.ValueChanged += (sender, change) => {
      var chunk = new byte[change.CharacteristicValue.Length]; DataReader.FromBuffer(change.CharacteristicValue).ReadBytes(chunk);
      lock (gate) received.AddRange(chunk);
    };
    var mode = (listen.CharacteristicProperties & GattCharacteristicProperties.Notify) != 0 ? GattClientCharacteristicConfigurationDescriptorValue.Notify : GattClientCharacteristicConfigurationDescriptorValue.Indicate;
    var subscribed = Wait(listen.WriteClientCharacteristicConfigurationDescriptorAsync(mode));
    if (subscribed != GattCommunicationStatus.Success) throw new Exception("notifications refused: " + subscribed);
    var option = (target.CharacteristicProperties & GattCharacteristicProperties.Write) != 0 ? GattWriteOption.WriteWithResponse : GattWriteOption.WriteWithoutResponse;
    int end = args[6] == "" ? -1 : Convert.ToInt32(args[6], 16); int wait = int.Parse(args[7]); int index = 0;
    foreach (var command in args[5].Split(',')) {
      lock (gate) received.Clear();
      var writer = new DataWriter(); writer.WriteBytes(Bytes(command));
      var status = Wait(target.WriteValueAsync(writer.DetachBuffer(), option));
      if (status != GattCommunicationStatus.Success) throw new Exception("write refused: " + status);
      var started = DateTime.UtcNow; var last = DateTime.UtcNow; int seen = 0;
      while ((DateTime.UtcNow - started).TotalMilliseconds < wait && DateTime.UtcNow < Deadline) {
        Thread.Sleep(30);
        lock (gate) {
          if (received.Count != seen) { seen = received.Count; last = DateTime.UtcNow; }
          if (end >= 0 && received.Contains((byte)end)) break;
        }
        // Without an end byte the answer is over after a quiet half second.
        if (end < 0 && seen > 0 && (DateTime.UtcNow - last).TotalMilliseconds > 500) break;
      }
      string answer; lock (gate) answer = String.Concat(received.Select(b => b.ToString("x2")));
      Console.WriteLine("R|" + index + "|" + answer); index++;
    }
    try { Wait(listen.WriteClientCharacteristicConfigurationDescriptorAsync(GattClientCharacteristicConfigurationDescriptorValue.None)); } catch (Exception) { }
  }
  // Serial-over-BLE profiles of common modules and adapters: service, write, notify. Only where the
  // bytes go; what they mean is up to the tool that opens the channel.
  static readonly string[][] Profiles = {
    new[] { "0000fff0-0000-1000-8000-00805f9b34fb", "0000fff2-0000-1000-8000-00805f9b34fb", "0000fff1-0000-1000-8000-00805f9b34fb" },
    new[] { "0000ffe0-0000-1000-8000-00805f9b34fb", "0000ffe1-0000-1000-8000-00805f9b34fb", "0000ffe1-0000-1000-8000-00805f9b34fb" },
    new[] { "000018f0-0000-1000-8000-00805f9b34fb", "00002af1-0000-1000-8000-00805f9b34fb", "00002af0-0000-1000-8000-00805f9b34fb" },
    new[] { "6e400001-b5a3-f393-e0a9-e50e24dcca9e", "6e400002-b5a3-f393-e0a9-e50e24dcca9e", "6e400003-b5a3-f393-e0a9-e50e24dcca9e" },
    new[] { "e7810a71-73ae-499d-8c15-faa9aef0c3f2", "bef8d6c9-9c21-4c9e-b632-bd58c1009f9f", "bef8d6c9-9c21-4c9e-b632-bd58c1009f9f" },
  };
  // The channel of a device: the profile given, a known serial profile it has, or the first
  // service with a characteristic that takes writes and one that notifies.
  static GattCharacteristic[] Channel(GattDeviceServicesResult services, string service, string write, string notify) {
    if (service != "") return new[] { Find(services, service, write), Find(services, service, notify) };
    foreach (var profile in Profiles) {
      try { return new[] { Find(services, profile[0], profile[1]), Find(services, profile[0], profile[2]) }; } catch (Exception) { }
    }
    foreach (var item in services.Services) {
      if (item.Uuid.ToString().StartsWith("000018") && item.Uuid.ToString().EndsWith("-0000-1000-8000-00805f9b34fb") && !item.Uuid.ToString().StartsWith("000018f0")) continue;
      var characteristics = Wait(item.GetCharacteristicsAsync(BluetoothCacheMode.Uncached));
      if (characteristics.Status != GattCommunicationStatus.Success) continue;
      GattCharacteristic writer = null, listener = null;
      foreach (var candidate in characteristics.Characteristics) {
        if (writer == null && (candidate.CharacteristicProperties & (GattCharacteristicProperties.Write | GattCharacteristicProperties.WriteWithoutResponse)) != 0) writer = candidate;
        if (listener == null && (candidate.CharacteristicProperties & (GattCharacteristicProperties.Notify | GattCharacteristicProperties.Indicate)) != 0) listener = candidate;
      }
      if (writer != null && listener != null) return new[] { writer, listener };
    }
    throw new Exception("no service of this device takes writes and notifies: name the channel profile (service, write, notify)");
  }
  // stream: the device as a byte channel until the input ends. Input lines W|hex are written (in
  // pieces of 20 bytes, the smallest Bluetooth LE packet); notifications come out as R|hex.
  static void Stream(GattDeviceServicesResult services, string[] args) {
    var channel = Channel(services, args.Length > 2 ? args[2] : "", args.Length > 3 ? args[3] : "", args.Length > 4 ? args[4] : "");
    var target = channel[0]; var listen = channel[1]; var gate = new object();
    listen.ValueChanged += (sender, change) => {
      var chunk = new byte[change.CharacteristicValue.Length]; DataReader.FromBuffer(change.CharacteristicValue).ReadBytes(chunk);
      lock (gate) { Console.Out.WriteLine("R|" + String.Concat(chunk.Select(b => b.ToString("x2")))); Console.Out.Flush(); }
    };
    var mode = (listen.CharacteristicProperties & GattCharacteristicProperties.Notify) != 0 ? GattClientCharacteristicConfigurationDescriptorValue.Notify : GattClientCharacteristicConfigurationDescriptorValue.Indicate;
    var subscribed = Wait(listen.WriteClientCharacteristicConfigurationDescriptorAsync(mode));
    if (subscribed != GattCommunicationStatus.Success) throw new Exception("notifications refused: " + subscribed);
    var option = (target.CharacteristicProperties & GattCharacteristicProperties.Write) != 0 ? GattWriteOption.WriteWithResponse : GattWriteOption.WriteWithoutResponse;
    lock (gate) { Console.Out.WriteLine("S|" + target.Service.Uuid + "|" + target.Uuid + "|" + listen.Uuid); Console.Out.Flush(); }
    Deadline = DateTime.MaxValue;
    string line;
    while ((line = Console.In.ReadLine()) != null) {
      if (!line.StartsWith("W|")) continue;
      var data = Bytes(line.Substring(2).Trim());
      for (int at = 0; at < data.Length; at += 20) {
        var writer = new DataWriter(); writer.WriteBytes(data.Skip(at).Take(20).ToArray());
        var started = DateTime.UtcNow; Deadline = started.AddSeconds(15);
        var status = Wait(target.WriteValueAsync(writer.DetachBuffer(), option));
        Deadline = DateTime.MaxValue;
        if (status != GattCommunicationStatus.Success) throw new Exception("write refused: " + status);
      }
    }
    try { Deadline = DateTime.UtcNow.AddSeconds(5); Wait(listen.WriteClientCharacteristicConfigurationDescriptorAsync(GattClientCharacteristicConfigurationDescriptorValue.None)); } catch (Exception) { }
  }
  public static int Main(string[] args) {
    try {
      var address = Convert.ToUInt64(args[1].Replace(":", ""), 16);
      GattDeviceServicesResult services;
      var device = Open(address, out services);
      Console.WriteLine("N|" + Clean(device.Name));
      if (args[0] == "inspect") {
        foreach (var service in services.Services) {
          var characteristics = Wait(service.GetCharacteristicsAsync(BluetoothCacheMode.Uncached));
          if (characteristics.Status != GattCommunicationStatus.Success) { Console.WriteLine("C|" + service.Uuid + "|||" + "|" + characteristics.Status); continue; }
          foreach (var item in characteristics.Characteristics) {
            string value = "", problem = "";
            if ((item.CharacteristicProperties & GattCharacteristicProperties.Read) != 0 && DateTime.UtcNow > Deadline) problem = "not read: time limit";
            else if ((item.CharacteristicProperties & GattCharacteristicProperties.Read) != 0) {
              try { var read = Wait(item.ReadValueAsync(BluetoothCacheMode.Uncached)); if (read.Status == GattCommunicationStatus.Success) value = Hex(read.Value); else problem = read.Status.ToString(); }
              catch (Exception error) { problem = Clean(error.Message); }
            }
            Console.WriteLine("C|" + service.Uuid + "|" + item.Uuid + "|" + item.CharacteristicProperties.ToString().Replace(" ", "") + "|" + value + "|" + problem);
          }
        }
      } else if (args[0] == "read") {
        var read = Wait(Find(services, args[2], args[3]).ReadValueAsync(BluetoothCacheMode.Uncached));
        if (read.Status != GattCommunicationStatus.Success) throw new Exception("read refused: " + read.Status);
        Console.WriteLine("V|" + Hex(read.Value));
      } else if (args[0] == "write") {
        var target = Find(services, args[2], args[3]);
        var writer = new DataWriter(); var hex = args[4];
        writer.WriteBytes(Enumerable.Range(0, hex.Length / 2).Select(i => Convert.ToByte(hex.Substring(i * 2, 2), 16)).ToArray());
        var option = (target.CharacteristicProperties & GattCharacteristicProperties.Write) != 0 ? GattWriteOption.WriteWithResponse : GattWriteOption.WriteWithoutResponse;
        var status = Wait(target.WriteValueAsync(writer.DetachBuffer(), option));
        if (status != GattCommunicationStatus.Success) throw new Exception("write refused: " + status);
        Console.WriteLine("V|");
      } else if (args[0] == "exchange") {
        Exchange(services, args);
      } else if (args[0] == "stream") {
        Stream(services, args);
      }
      device.Dispose();
      return 0;
    } catch (Exception error) { Console.WriteLine("E|" + Clean(error.Message)); return 0; }
  }
}
`

// dotnetProgram builds a small helper with the .NET Framework compiler that ships with Windows,
// once per version of its source.
func dotnetProgram(name, source string) (string, error) {
	sum := sha256.Sum256([]byte(source))
	folder := filepath.Join(os.TempDir(), "righaven-ble")
	program := filepath.Join(folder, fmt.Sprintf("%s-%x.exe", name, sum[:6]))
	if _, err := os.Stat(program); err == nil {
		return program, nil
	}
	if err := os.MkdirAll(folder, 0o755); err != nil {
		return "", err
	}
	file := strings.TrimSuffix(program, ".exe") + ".cs"
	if err := os.WriteFile(file, []byte(source), 0o644); err != nil {
		return "", err
	}
	windows := os.Getenv("WINDIR")
	runtime := filepath.Join(windows, "Microsoft.NET", "Framework64", "v4.0.30319")
	metadata := filepath.Join(windows, "System32", "WinMetadata")
	arguments := []string{"/nologo", "/target:exe", "/out:" + program}
	for _, reference := range []string{"System.Runtime.dll", "System.Runtime.WindowsRuntime.dll", "System.Runtime.InteropServices.WindowsRuntime.dll", "System.Threading.Tasks.dll"} {
		if _, err := os.Stat(filepath.Join(runtime, reference)); err == nil {
			arguments = append(arguments, "/r:"+filepath.Join(runtime, reference))
		}
	}
	for _, reference := range []string{"Windows.Foundation.winmd", "Windows.Devices.winmd", "Windows.Storage.winmd"} {
		arguments = append(arguments, "/r:"+filepath.Join(metadata, reference))
	}
	output, err := exec.Command(filepath.Join(runtime, "csc.exe"), append(arguments, file)...).CombinedOutput()
	if err != nil {
		_ = os.Remove(program)
		var errorsOnly []string
		for _, line := range strings.Split(string(output), "\n") {
			if strings.Contains(line, "error") {
				errorsOnly = append(errorsOnly, strings.TrimSpace(line))
			}
		}
		return "", fmt.Errorf("Bluetooth helper not built: %s", strings.Join(errorsOnly, " "))
	}
	return program, nil
}

// startGATTStream runs the GATT helper in stream mode for one Bluetooth LE device: it keeps the
// connection, writes what the channel receives and returns what the device notifies.
func startGATTStream(channel bleChannel) (io.ReadWriteCloser, error) {
	program, err := dotnetProgram("gatt", gattSource)
	if err != nil {
		return nil, err
	}
	command := exec.Command(program, "stream", channel.Address, channel.Service, channel.Write, channel.Notify)
	in, err := command.StdinPipe()
	if err != nil {
		return nil, err
	}
	out, err := command.StdoutPipe()
	if err != nil {
		return nil, err
	}
	if err := command.Start(); err != nil {
		return nil, err
	}
	stop := func() error {
		done := make(chan error, 1)
		go func() { done <- command.Wait() }()
		select {
		case <-done:
		case <-time.After(3 * time.Second):
			_ = command.Process.Kill()
			<-done
		}
		return nil
	}
	return newHelperStream(in, out, stop)
}

func runGATT(args ...string) (string, error) {
	program, err := dotnetProgram("gatt", gattSource)
	if err != nil {
		return "", err
	}
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	output, err := exec.CommandContext(ctx, program, args...).Output()
	if ctx.Err() != nil {
		return "", errors.New("the Bluetooth device did not answer within a minute")
	}
	return string(output), err
}

// windowsWifi joins a device's open setup network with a temporary profile and goes back home.
type windowsWifi struct{}

var netshCurrent = regexp.MustCompile(`(?m)^\s*SSID\s*:\s?(.+?)\s*$`)

func (windowsWifi) Current() (string, error) {
	output, err := exec.Command("netsh", "wlan", "show", "interfaces").Output()
	if err != nil {
		return "", err
	}
	if match := netshCurrent.FindStringSubmatch(string(output)); match != nil {
		return match[1], nil
	}
	return "", nil
}

func waitWifi(ssid string) error {
	for i := 0; i < 30; i++ {
		if current, _ := (windowsWifi{}).Current(); current == ssid {
			time.Sleep(2 * time.Second) // address from the device's DHCP
			return nil
		}
		time.Sleep(time.Second)
	}
	return fmt.Errorf("not connected to %s", ssid)
}

func (windowsWifi) JoinSetup(ssid, key string) (bool, error) {
	// A network the PC already knows (the home Wi-Fi, a saved one) keeps its own profile.
	if exec.Command("netsh", "wlan", "show", "profiles", "name="+ssid).Run() == nil {
		if output, err := exec.Command("netsh", "wlan", "connect", "name="+ssid).CombinedOutput(); err != nil {
			return false, fmt.Errorf("%s", firstLine(strings.TrimSpace(string(output))))
		}
		return false, waitWifi(ssid)
	}
	return true, joinTemporary(ssid, key)
}

func joinTemporary(ssid, key string) error {
	var escaped bytes.Buffer
	_ = xml.EscapeText(&escaped, []byte(ssid))
	security := `<authEncryption><authentication>open</authentication><encryption>none</encryption><useOneX>false</useOneX></authEncryption>`
	if key != "" {
		var secret bytes.Buffer
		_ = xml.EscapeText(&secret, []byte(key))
		security = `<authEncryption><authentication>WPA2PSK</authentication><encryption>AES</encryption><useOneX>false</useOneX></authEncryption>` +
			`<sharedKey><keyType>passPhrase</keyType><protected>false</protected><keyMaterial>` + secret.String() + `</keyMaterial></sharedKey>`
	}
	profile := `<?xml version="1.0"?><WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1"><name>` + escaped.String() +
		`</name><SSIDConfig><SSID><name>` + escaped.String() + `</name></SSID></SSIDConfig><connectionType>ESS</connectionType><connectionMode>manual</connectionMode>` +
		`<MSM><security>` + security + `</security></MSM></WLANProfile>`
	file := filepath.Join(os.TempDir(), "righaven-setup-wifi.xml")
	if err := os.WriteFile(file, []byte(profile), 0o600); err != nil {
		return err
	}
	defer os.Remove(file)
	if output, err := exec.Command("netsh", "wlan", "add", "profile", "filename="+file, "user=current").CombinedOutput(); err != nil {
		return fmt.Errorf("%s", firstLine(strings.TrimSpace(string(output))))
	}
	if output, err := exec.Command("netsh", "wlan", "connect", "name="+ssid, "ssid="+ssid).CombinedOutput(); err != nil {
		return fmt.Errorf("%s", firstLine(strings.TrimSpace(string(output))))
	}
	return waitWifi(ssid)
}

func (windowsWifi) Rejoin(ssid string) error {
	if output, err := exec.Command("netsh", "wlan", "connect", "name="+ssid).CombinedOutput(); err != nil {
		return fmt.Errorf("%s", firstLine(strings.TrimSpace(string(output))))
	}
	return waitWifi(ssid)
}

// Gateway is the router of the Wi-Fi network the PC is on now.
func (windowsWifi) Gateway() (string, error) {
	script := "$r = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Where-Object { (Get-NetAdapter -InterfaceIndex $_.ifIndex -ErrorAction SilentlyContinue).PhysicalMediaType -match '802.11' } | Sort-Object RouteMetric | Select-Object -First 1; if ($r) { $r.NextHop }"
	output, err := exec.Command("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script).Output()
	if err != nil {
		return "", err
	}
	address := strings.TrimSpace(string(output))
	if net.ParseIP(address) == nil {
		return "", fmt.Errorf("no router on this network")
	}
	return address, nil
}

func (windowsWifi) Forget(ssid string) {
	_ = exec.Command("netsh", "wlan", "delete", "profile", "name="+ssid).Run()
}

// listPnPDevices reads Device Manager: the devices present now.
func listPnPDevices() ([]pnpDevice, error) {
	script := "Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | ForEach-Object { [pscustomobject]@{ class = [string]$_.Class; name = [string]$_.FriendlyName; instance_id = [string]$_.InstanceId; status = [string]$_.Status } } | ConvertTo-Json -Compress"
	output, err := exec.Command("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script).Output()
	if err != nil {
		return nil, err
	}
	output = bytes.TrimSpace(output)
	if len(output) == 0 {
		return nil, nil
	}
	if output[0] == '{' {
		output = append(append([]byte{'['}, output...), ']')
	}
	var devices []pnpDevice
	return devices, json.Unmarshal(output, &devices)
}

// recordTraffic runs pktmon (Windows' own packet monitor, administrator rights: one prompt) on the
// PC's network adapters for the given time and converts the recording to pcapng.
func recordTraffic(seconds int) (string, error) {
	folder := filepath.Join(os.TempDir(), "righaven-capture")
	if err := os.MkdirAll(folder, 0o755); err != nil {
		return "", err
	}
	etl, pcap := filepath.Join(folder, "capture.etl"), filepath.Join(folder, "capture.pcapng")
	_ = os.Remove(etl)
	_ = os.Remove(pcap)
	inner := fmt.Sprintf("pktmon stop *> $null; pktmon filter remove *> $null; pktmon start --capture --comp nics --pkt-size 0 -f '%s' *> $null; "+
		"Start-Sleep -Seconds %d; pktmon stop *> $null; pktmon etl2pcap '%s' --out '%s' *> $null; Remove-Item '%s' -ErrorAction SilentlyContinue", etl, seconds, etl, pcap, etl)
	script := fmt.Sprintf("$p = Start-Process -FilePath powershell.exe -ArgumentList '-NoProfile','-Command',\"%s\" -Verb RunAs -Wait -PassThru -WindowStyle Hidden; exit $p.ExitCode",
		strings.ReplaceAll(inner, `"`, "`\""))
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(seconds+120)*time.Second)
	defer cancel()
	if output, err := exec.CommandContext(ctx, "powershell.exe", "-NoProfile", "-Command", script).CombinedOutput(); err != nil {
		return "", fmt.Errorf("%v %s", err, firstLine(strings.TrimSpace(string(output))))
	}
	if _, err := os.Stat(pcap); err != nil {
		return "", errors.New("no recording: the administrator prompt was refused or pktmon is not available")
	}
	return pcap, nil
}

// readNeighbours reads Windows' neighbour (ARP) table: the devices that answered on the network.
func readNeighbours() ([]neighbour, error) {
	script := "Get-NetNeighbor -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.State -in 'Reachable','Stale','Delay','Probe','Permanent' } | " +
		"ForEach-Object { [pscustomobject]@{ address = [string]$_.IPAddress; mac = [string]$_.LinkLayerAddress } } | ConvertTo-Json -Compress"
	output, err := exec.Command("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script).Output()
	if err != nil {
		return nil, err
	}
	output = bytes.TrimSpace(output)
	if len(output) == 0 {
		return nil, nil
	}
	if output[0] == '{' {
		output = append(append([]byte{'['}, output...), ']')
	}
	var found []neighbour
	return found, json.Unmarshal(output, &found)
}

var (
	crypt32                = syscall.NewLazyDLL("crypt32.dll")
	procCryptProtectData   = crypt32.NewProc("CryptProtectData")
	procCryptUnprotectData = crypt32.NewProc("CryptUnprotectData")
	procLocalFree          = kernel32.NewProc("LocalFree")
)

type dataBlob struct {
	size uint32
	data *byte
}

func blob(data []byte) *dataBlob {
	if len(data) == 0 {
		return &dataBlob{}
	}
	return &dataBlob{size: uint32(len(data)), data: &data[0]}
}

func (b *dataBlob) bytes() []byte {
	return append([]byte(nil), unsafe.Slice(b.data, b.size)...)
}

// protectSecret encrypts the agent's token for this Windows account (DPAPI).
func protectSecret(secret string) (string, error) {
	var out dataBlob
	if r, _, err := procCryptProtectData.Call(uintptr(unsafe.Pointer(blob([]byte(secret)))), 0, 0, 0, 0, 0x1, uintptr(unsafe.Pointer(&out))); r == 0 {
		return "", err
	}
	defer procLocalFree.Call(uintptr(unsafe.Pointer(out.data)))
	return "dpapi:" + base64.StdEncoding.EncodeToString(out.bytes()), nil
}

func unprotectSecret(value string) (string, error) {
	data, err := base64.StdEncoding.DecodeString(strings.TrimPrefix(value, "dpapi:"))
	if err != nil {
		return "", err
	}
	var out dataBlob
	if r, _, err := procCryptUnprotectData.Call(uintptr(unsafe.Pointer(blob(data))), 0, 0, 0, 0, 0x1, uintptr(unsafe.Pointer(&out))); r == 0 {
		return "", err
	}
	defer procLocalFree.Call(uintptr(unsafe.Pointer(out.data)))
	return string(out.bytes()), nil
}

// setAutostart starts RigHaven Agent at the owner's sign-in (their own Run key, no administrator rights).
func setAutostart(on bool) error {
	key := `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
	if !on {
		_ = exec.Command("reg", "delete", key, "/v", "RigHaven Agent", "/f").Run()
		return nil
	}
	exe, err := os.Executable()
	if err != nil {
		return err
	}
	return exec.Command("reg", "add", key, "/v", "RigHaven Agent", "/t", "REG_SZ", "/d", `"`+exe+`" agent run`, "/f").Run()
}
