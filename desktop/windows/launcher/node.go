package main

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Compute node: this machine runs sandboxes of on-premise environments for the RigHaven server.
// Coordination, projects and data stay on the server: for each task it sends the worker's
// docker-run command and the folders it mounts; this machine checks the command against its own
// sandbox rules, runs it with its Docker, sends progress while it runs and the results at the end.

type nodeConfig struct {
	CPUs      float64 `json:"cpus"`       // at most this many CPUs for RigHaven's tasks, 0 = all
	MemoryMiB int     `json:"memory_mib"` // at most this much memory, 0 = all
	Jobs      int     `json:"jobs"`       // tasks at a time
	ImagesGiB float64 `json:"images_gib"` // disk for environment images, 0 = 40 GiB
}

// nodePrepare: the run prepares an environment image, saved with docker commit when it succeeds.
type nodePrepare struct {
	Tag         string `json:"tag"`
	Environment string `json:"environment"`
}

type nodeMount struct {
	Key    string `json:"key"`
	Mode   string `json:"mode"` // ro, rw, live (progress sent while running)
	Kind   string `json:"kind"` // dir or file
	Target string `json:"target"`
}

type nodeRun struct {
	ID      string       `json:"id"`
	Args    []string     `json:"args"`
	Image   string       `json:"image"`
	Timeout int          `json:"timeout"`
	Mounts  []nodeMount  `json:"mounts"`
	Prepare *nodePrepare `json:"prepare,omitempty"`
}

var (
	nodeJobName  = regexp.MustCompile(`^rh-job-[0-9a-f]{12}$`)
	nodePrepName = regexp.MustCompile(`^rh-env-[0-9a-f]{12}-[0-9a-f]{6}$`)
	nodeEnvTag   = regexp.MustCompile(`^skill-environment:[0-9a-f]{12}-[0-9a-f]{64}$`)
	nodeEnvKey   = regexp.MustCompile(`^[0-9a-f]{64}$`)
	nodeImageID  = regexp.MustCompile(`^sha256:[0-9a-f]{64}$`)
	// The only capabilities a preparation may add (package installers), never a task.
	nodePrepCaps = map[string]bool{"CHOWN": true, "FOWNER": true, "DAC_OVERRIDE": true, "SETUID": true, "SETGID": true}
	nodePrepCmd  = []string{"python3", "/opt/righaven/prepare_environment.py", "/environment-request.json"}
	nodeImagesMu sync.Mutex // the usage file of environment images and their pruning
	nodeMountArg = regexp.MustCompile(`^type=bind,src=\{(m[0-9]{1,3})\},dst=(/[^,{}]+)(,readonly)?$`)
	nodeEnvArg   = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*=`)
	nodeTmpfsArg = regexp.MustCompile(`^/[^,:]+(:[a-z0-9=,]+)?$`)
	nodeLabelArg = regexp.MustCompile(`^org\.righaven\.[a-z.]+=[A-Za-z0-9_.:/-]*$`)
	nodeLive     = 3 * time.Second
	nodeRunning  sync.Map // run id → container name
	nodeRunsDir  = func() string { return filepath.Join(filepath.Dir(agentConfigPath()), "runs") }
	// Docker of this machine: on Linux (or Windows with Docker Desktop) the docker command; on a
	// Windows PC with portable RigHaven, the Docker of its WSL distribution.
	nodeDockerCmd = func() []string {
		if _, err := exec.LookPath("docker"); err == nil || runtime.GOOS != "windows" {
			return []string{"docker"}
		}
		return []string{"wsl.exe", "-d", "RigHaven", "--", "docker"}
	}
)

// dockerCommand runs docker on this machine.
func dockerCommand(ctx context.Context, args ...string) *exec.Cmd {
	base := nodeDockerCmd()
	return exec.CommandContext(ctx, base[0], append(base[1:], args...)...)
}

// nodeCapacity is what this machine offers: Docker's own CPUs and memory, within the owner's limits.
func nodeCapacity(config *nodeConfig) (map[string]any, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	out, err := dockerCommand(ctx, "info", "--format", "{{.NCPU}} {{.MemTotal}} {{.ServerVersion}}").Output()
	if err != nil {
		return nil, fmt.Errorf("Docker does not answer on this machine: %v", err)
	}
	fields := strings.Fields(string(out))
	if len(fields) < 3 {
		return nil, errors.New("unexpected answer from docker info")
	}
	cpus, _ := strconv.ParseFloat(fields[0], 64)
	memory, _ := strconv.ParseInt(fields[1], 10, 64)
	mib := int(memory >> 20)
	if config.CPUs > 0 && config.CPUs < cpus {
		cpus = config.CPUs
	}
	if config.MemoryMiB > 0 && config.MemoryMiB < mib {
		mib = config.MemoryMiB
	}
	jobs := config.Jobs
	if jobs < 1 {
		jobs = 1
	}
	running := 0
	nodeRunning.Range(func(any, any) bool { running++; return true })
	return map[string]any{"cpus": cpus, "memory_mib": mib, "jobs": jobs, "docker": fields[2], "running": running, "images": nodeImages()}, nil
}

// validRunID: a task (rh-job-…) or the preparation of an environment (rh-env-…).
func validRunID(job nodeRun) bool {
	if job.Prepare != nil {
		return nodePrepName.MatchString(job.ID) && nodeEnvTag.MatchString(job.Prepare.Tag) && nodeEnvKey.MatchString(job.Prepare.Environment)
	}
	return nodeJobName.MatchString(job.ID)
}

// nodeArgs checks the server's command against this machine's sandbox rules and puts the local
// folders in place of the bundle keys. Anything not in the list below is refused.
func nodeArgs(job nodeRun, root string, limits map[string]any) ([]string, string, error) {
	if len(job.Args) < 2 || job.Args[0] != "run" {
		return nil, "", errors.New("not a docker run command")
	}
	mounts := map[string]nodeMount{}
	for _, m := range job.Mounts {
		mounts[m.Key] = m
	}
	out, name := []string{"run"}, ""
	i := 1
	value := func() (string, error) {
		if i+1 >= len(job.Args) {
			return "", fmt.Errorf("%s without a value", job.Args[i])
		}
		i++
		return job.Args[i], nil
	}
	for ; i < len(job.Args); i++ {
		item := job.Args[i]
		if !strings.HasPrefix(item, "-") {
			break
		}
		switch {
		case item == "--init" || item == "--cap-drop=ALL" || item == "--security-opt=no-new-privileges" || item == "--network=bridge":
			out = append(out, item)
		case strings.HasPrefix(item, "--memory=") || strings.HasPrefix(item, "--memory-swap="):
			mib, err := strconv.Atoi(strings.TrimSuffix(item[strings.Index(item, "=")+1:], "m"))
			if err != nil || mib < 64 || (limits != nil && mib > limits["memory_mib"].(int)) {
				return nil, "", fmt.Errorf("memory outside this machine's limits: %s", item)
			}
			out = append(out, item)
		case strings.HasPrefix(item, "--cpus="):
			cpus, err := strconv.ParseFloat(item[len("--cpus="):], 64)
			if err != nil || cpus <= 0 || (limits != nil && cpus > limits["cpus"].(float64)+0.001) {
				return nil, "", fmt.Errorf("CPUs outside this machine's limits: %s", item)
			}
			out = append(out, item)
		case item == "--cap-add" && job.Prepare != nil:
			v, err := value()
			if err != nil || !nodePrepCaps[v] {
				return nil, "", fmt.Errorf("capability not allowed: %s", v)
			}
			out = append(out, item, v)
		case item == "--name":
			v, err := value()
			if err != nil || v != job.ID || !validRunID(job) {
				return nil, "", errors.New("container name not valid")
			}
			name = v
			out = append(out, item, v)
		case item == "--pids-limit" || strings.HasPrefix(item, "--pids-limit="):
			// The server writes --pids-limit=256; both forms are the same limit.
			v, err := strings.TrimPrefix(item, "--pids-limit="), error(nil)
			if item == "--pids-limit" {
				v, err = value()
			}
			if n, convErr := strconv.Atoi(v); err != nil || convErr != nil || n < 16 || n > 4096 {
				return nil, "", errors.New("pids limit not valid")
			}
			out = append(out, "--pids-limit="+v)
		case item == "--label":
			v, err := value()
			if err != nil || !nodeLabelArg.MatchString(v) {
				return nil, "", fmt.Errorf("label not allowed: %s", v)
			}
			out = append(out, item, v)
		case item == "--env":
			v, err := value()
			if err != nil || !nodeEnvArg.MatchString(v) || strings.HasPrefix(v, "LD_") {
				return nil, "", fmt.Errorf("environment variable not allowed: %.40s", v)
			}
			out = append(out, item, v)
		case item == "--tmpfs":
			v, err := value()
			if err != nil || !nodeTmpfsArg.MatchString(v) {
				return nil, "", fmt.Errorf("tmpfs not allowed: %s", v)
			}
			out = append(out, item, v)
		case item == "--mount":
			v, err := value()
			matched := nodeMountArg.FindStringSubmatch(v)
			if err != nil || matched == nil {
				return nil, "", fmt.Errorf("mount not allowed: %.80s", v)
			}
			mount, ok := mounts[matched[1]]
			if !ok || (mount.Mode == "ro") != (matched[3] != "") || mount.Target != matched[2] {
				return nil, "", fmt.Errorf("mount not declared: %s", matched[1])
			}
			source := filepath.Join(root, matched[1])
			if strings.ContainsAny(source, ",\n") {
				return nil, "", errors.New("folder of the run not usable by Docker")
			}
			out = append(out, item, "type=bind,src="+dockerPath(source)+",dst="+matched[2]+matched[3])
		default:
			return nil, "", fmt.Errorf("option not allowed on this machine: %s", item)
		}
	}
	if name == "" || i >= len(job.Args) || job.Args[i] != job.Image {
		return nil, "", errors.New("container name or image missing")
	}
	if job.Prepare != nil { // a preparation runs only RigHaven's installer, nothing else
		command := job.Args[i+1:]
		if len(command) != len(nodePrepCmd) {
			return nil, "", errors.New("not RigHaven's environment preparation")
		}
		for k := range command {
			if command[k] != nodePrepCmd[k] {
				return nil, "", errors.New("not RigHaven's environment preparation")
			}
		}
		labelled := false
		for k := 0; k+1 < len(out); k++ {
			labelled = labelled || (out[k] == "--label" && out[k+1] == "org.righaven.environment="+job.Prepare.Environment)
		}
		if !labelled {
			return nil, "", errors.New("environment label missing")
		}
	}
	return append(out, job.Args[i:]...), name, nil
}

// dockerPath is a folder of this machine as its Docker sees it.
func dockerPath(path string) string {
	if runtime.GOOS == "windows" && len(nodeDockerCmd()) > 1 { // Docker inside the RigHaven WSL distribution
		path = filepath.ToSlash(path)
		if len(path) > 1 && path[1] == ':' {
			return "/mnt/" + strings.ToLower(path[:1]) + path[2:]
		}
	}
	return path
}

func (s *agentSession) nodeRequest(method, path string, body io.Reader) (*http.Response, error) {
	request, err := http.NewRequest(method, s.config.Server+path, body)
	if err != nil {
		return nil, err
	}
	request.Header.Set(agentHeader, s.config.Token)
	return (&http.Client{Timeout: 6 * time.Hour}).Do(request)
}

// runJob carries out one run asked by the server and sends its result back, even later.
func (s *agentSession) runJob(job nodeRun) {
	if !validRunID(job) {
		return
	}
	dir := filepath.Join(nodeRunsDir(), job.ID)
	result := s.executeJob(dir, job)
	s.uploadResult(dir, job, result)
}

func (s *agentSession) executeJob(dir string, job nodeRun) map[string]any {
	fail := func(err error) map[string]any {
		return map[string]any{"returncode": 125, "stdout": "", "stderr": "RigHaven node: " + err.Error(), "oom": false}
	}
	_ = os.RemoveAll(dir)
	root := filepath.Join(dir, "m")
	if err := os.MkdirAll(root, 0o700); err != nil {
		return fail(err)
	}
	spec, _ := json.Marshal(job)
	_ = os.WriteFile(filepath.Join(dir, "run.json"), spec, 0o600)
	response, err := s.nodeRequest("GET", "/api/webhooks/righaven-agent/runs/"+job.ID+"/bundle", nil)
	if err != nil {
		return fail(err)
	}
	err = untarRun(response.Body, root)
	response.Body.Close()
	if err != nil {
		return fail(fmt.Errorf("bundle: %v", err))
	}
	for _, m := range job.Mounts {
		path := filepath.Join(root, m.Key)
		if m.Kind == "dir" {
			_ = os.MkdirAll(path, 0o755)
		} else if _, err := os.Stat(path); err != nil {
			return fail(fmt.Errorf("file %s missing from the bundle", m.Key))
		}
		openForSandbox(path, m.Mode != "ro")
	}
	if err := s.ensureImage(job.Image); err != nil {
		return fail(err)
	}
	limits, _ := nodeCapacity(s.nodeConfig())
	args, name, err := nodeArgs(job, root, limits)
	if err != nil {
		return fail(err)
	}
	nodeRunning.Store(job.ID, name)
	defer nodeRunning.Delete(job.ID)
	_ = s.send(map[string]any{"type": "run-state", "id": job.ID, "state": "running"})
	timeout := time.Duration(job.Timeout+30) * time.Second
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	var stdout, stderr bytes.Buffer
	cmd := dockerCommand(ctx, args...)
	cmd.Stdout, cmd.Stderr = &limited{&stdout, 16 << 20}, &limited{&stderr, 1 << 20}
	done := make(chan struct{})
	go func() { // progress of the task, while it runs
		ticker := time.NewTicker(nodeLive)
		defer ticker.Stop()
		for {
			select {
			case <-done:
				return
			case <-ticker.C:
				s.uploadLive(job, root)
			}
		}
	}()
	runErr := cmd.Run()
	close(done)
	code := 0
	var exit *exec.ExitError
	switch {
	case ctx.Err() != nil:
		code = 124
	case errors.As(runErr, &exit):
		code = exit.ExitCode()
	case runErr != nil:
		return fail(runErr)
	}
	inspect, _ := dockerCommand(context.Background(), "inspect", "--format", "{{.State.OOMKilled}}", name).Output()
	result := map[string]any{"returncode": code, "stdout": stdout.String(), "stderr": stderr.String(), "oom": strings.TrimSpace(string(inspect)) == "true"}
	if job.Prepare != nil && code == 0 {
		if err := commitEnvironment(name, job, args, result); err != nil {
			result["returncode"], result["stderr"] = 125, stderr.String()+"\nRigHaven node: "+err.Error()
		}
	}
	_ = dockerCommand(context.Background(), "rm", "-f", name).Run()
	if nodeImageID.MatchString(job.Image) {
		touchImage(job.Image)
	}
	pruneImages(s.nodeConfig())
	return result
}

// commitEnvironment saves the prepared container as the environment image, on this machine only.
func commitEnvironment(name string, job nodeRun, args []string, result map[string]any) error {
	installation := ""
	for k := 0; k+1 < len(args); k++ {
		if args[k] == "--label" && strings.HasPrefix(args[k+1], "org.righaven.harness.installation=") {
			installation = args[k+1]
		}
	}
	changes := []string{"commit", "--change", "LABEL org.righaven.environment=" + job.Prepare.Environment}
	if installation != "" {
		changes = append(changes, "--change", "LABEL "+installation)
	}
	changes = append(changes, "--change", `CMD ["python3","-c","print(\"Ambiente RigHaven pronto\")"]`, name, job.Prepare.Tag)
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Minute)
	defer cancel()
	if out, err := dockerCommand(ctx, changes...).CombinedOutput(); err != nil {
		return fmt.Errorf("docker commit: %v %s", err, strings.TrimSpace(string(out)))
	}
	out, err := dockerCommand(context.Background(), "image", "inspect", "--format", "{{.Id}} {{.Size}}", job.Prepare.Tag).Output()
	fields := strings.Fields(string(out))
	if err != nil || len(fields) != 2 || !nodeImageID.MatchString(fields[0]) {
		return errors.New("prepared image not readable")
	}
	size, _ := strconv.ParseInt(fields[1], 10, 64)
	result["image_id"], result["size_bytes"] = fields[0], size
	touchImage(fields[0])
	return nil
}

// --- Environment images kept on this machine ---------------------------------------------

func nodeImagesFile() string {
	return filepath.Join(filepath.Dir(agentConfigPath()), "environment-images.json")
}

// nodeImages lists the environment images on this machine (prepared here by RigHaven).
func nodeImages() []string {
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	out, err := dockerCommand(ctx, "image", "ls", "-q", "--no-trunc", "--filter", "label=org.righaven.environment").Output()
	images := []string{}
	if err != nil {
		return images
	}
	seen := map[string]bool{}
	for _, id := range strings.Fields(string(out)) {
		if nodeImageID.MatchString(id) && !seen[id] {
			seen[id] = true
			images = append(images, id)
		}
	}
	return images
}

func readImageUse() map[string]int64 {
	use := map[string]int64{}
	if data, err := os.ReadFile(nodeImagesFile()); err == nil {
		_ = json.Unmarshal(data, &use)
	}
	return use
}

// touchImage records that an environment image was just used (prepared or run).
func touchImage(id string) {
	nodeImagesMu.Lock()
	defer nodeImagesMu.Unlock()
	use := readImageUse()
	use[id] = time.Now().Unix()
	data, _ := json.Marshal(use)
	_ = os.WriteFile(nodeImagesFile(), data, 0o600)
}

// pruneImages removes the least recently used environment images while they take more disk than
// the owner allows; images of running tasks stay (Docker refuses to remove them anyway).
func pruneImages(config *nodeConfig) {
	limit := int64(40) << 30
	if config != nil && config.ImagesGiB > 0 {
		limit = int64(config.ImagesGiB * float64(1<<30))
	}
	nodeImagesMu.Lock()
	defer nodeImagesMu.Unlock()
	images := nodeImages()
	if len(images) == 0 {
		return
	}
	out, err := dockerCommand(context.Background(), append([]string{"image", "inspect", "--format", "{{.Id}} {{.Size}}"}, images...)...).Output()
	if err != nil {
		return
	}
	type entry struct {
		id   string
		size int64
	}
	var list []entry
	var total int64
	for _, line := range strings.Split(strings.TrimSpace(string(out)), "\n") {
		fields := strings.Fields(line)
		if len(fields) != 2 {
			continue
		}
		size, _ := strconv.ParseInt(fields[1], 10, 64)
		list = append(list, entry{fields[0], size})
		total += size
	}
	use := readImageUse()
	inUse := map[string]bool{}
	nodeRunning.Range(func(key, _ any) bool {
		if data, err := os.ReadFile(filepath.Join(nodeRunsDir(), key.(string), "run.json")); err == nil {
			var job nodeRun
			if json.Unmarshal(data, &job) == nil {
				inUse[job.Image] = true
			}
		}
		return true
	})
	sortByUse(list, func(e entry) int64 { return use[e.id] })
	for _, item := range list {
		if total <= limit {
			break
		}
		if inUse[item.id] {
			continue
		}
		if dockerCommand(context.Background(), "image", "rm", item.id).Run() == nil {
			total -= item.size
			delete(use, item.id)
		}
	}
	data, _ := json.Marshal(use)
	_ = os.WriteFile(nodeImagesFile(), data, 0o600)
}

// sortByUse orders the least recently used first.
func sortByUse[T any](list []T, used func(T) int64) {
	sort.SliceStable(list, func(a, b int) bool { return used(list[a]) < used(list[b]) })
}

func (s *agentSession) nodeConfig() *nodeConfig {
	if s.config.Node == nil {
		return &nodeConfig{Jobs: 1}
	}
	return s.config.Node
}

// ensureImage: the environment image is downloaded once from the server (or from its registry).
func (s *agentSession) ensureImage(image string) error {
	if dockerCommand(context.Background(), "image", "inspect", image).Run() == nil {
		return nil
	}
	if strings.Contains(image, "/") && !strings.HasPrefix(image, "sha256:") {
		if dockerCommand(context.Background(), "pull", image).Run() == nil {
			return nil
		}
	}
	response, err := s.nodeRequest("GET", "/api/webhooks/righaven-agent/images/"+image, nil)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return fmt.Errorf("the server did not send the image (HTTP %d)", response.StatusCode)
	}
	load := dockerCommand(context.Background(), "load")
	load.Stdin = response.Body
	if out, err := load.CombinedOutput(); err != nil {
		return fmt.Errorf("docker load: %v %s", err, strings.TrimSpace(string(out)))
	}
	return nil
}

func (s *agentSession) uploadLive(job nodeRun, root string) {
	var buffer bytes.Buffer
	if packMounts(&buffer, job, root, map[string]bool{"live": true}, nil) != nil {
		return
	}
	if response, err := s.nodeRequest("PUT", "/api/webhooks/righaven-agent/runs/"+job.ID+"/live", &buffer); err == nil {
		response.Body.Close()
	}
}

// uploadResult sends the end of a run; it keeps trying while the server is not reachable.
func (s *agentSession) uploadResult(dir string, job nodeRun, result map[string]any) {
	path := filepath.Join(dir, "result.tar.gz")
	if result != nil { // nil: packed by a previous start of the agent, only to be sent
		file, err := os.Create(path)
		if err == nil {
			err = packMounts(file, job, filepath.Join(dir, "m"), map[string]bool{"rw": true, "live": true}, result)
			file.Close()
		}
		if err != nil {
			fmt.Fprintf(s.out, "RigHaven node: result of %s not packed: %v\n", job.ID, err)
			return
		}
	}
	pause := agentRetry
	for attempt := 0; attempt < 400; attempt++ {
		file, err := os.Open(path)
		if err != nil {
			return
		}
		response, err := s.nodeRequest("PUT", "/api/webhooks/righaven-agent/runs/"+job.ID+"/result", file)
		file.Close()
		if err == nil {
			response.Body.Close()
			if response.StatusCode == http.StatusOK || response.StatusCode == http.StatusGone || response.StatusCode == http.StatusNotFound {
				removeRun(dir, job.Image)
				return
			}
		}
		time.Sleep(pause)
		if pause *= 2; pause > time.Minute {
			pause = time.Minute
		}
	}
}

// openForSandbox: the sandbox runs as root without capabilities, so it reads and writes only what
// the permissions allow; the run's folder itself stays private to this account (0700).
func openForSandbox(path string, writable bool) {
	_ = filepath.Walk(path, func(item string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}
		mode := os.FileMode(0o644)
		if info.IsDir() {
			mode = 0o755
		}
		if writable {
			mode |= 0o022
		}
		return os.Chmod(item, mode)
	})
}

// removeRun deletes a run's folder; files the sandbox created as root are removed by a container.
func removeRun(dir, image string) {
	if os.RemoveAll(dir) == nil {
		return
	}
	_ = dockerCommand(context.Background(), "run", "--rm", "--network=none", "--entrypoint", "sh", "--mount",
		"type=bind,src="+dockerPath(dir)+",dst=/run-folder", image, "-c", "rm -rf /run-folder/* /run-folder/.[!.]*").Run()
	_ = os.RemoveAll(dir)
}

// resumeRuns: results left by a previous start of the agent are sent, runs cut short are ended.
func (s *agentSession) resumeRuns() {
	entries, _ := os.ReadDir(nodeRunsDir())
	for _, entry := range entries {
		dir := filepath.Join(nodeRunsDir(), entry.Name())
		if !nodeJobName.MatchString(entry.Name()) && !nodePrepName.MatchString(entry.Name()) {
			continue
		}
		if _, running := nodeRunning.Load(entry.Name()); running {
			continue
		}
		var job nodeRun
		data, err := os.ReadFile(filepath.Join(dir, "run.json"))
		if err != nil || json.Unmarshal(data, &job) != nil {
			_ = os.RemoveAll(dir)
			continue
		}
		if _, err := os.Stat(filepath.Join(dir, "result.tar.gz")); err != nil {
			_ = dockerCommand(context.Background(), "rm", "-f", job.ID).Run()
			go s.uploadResult(dir, job, map[string]any{"returncode": 125, "stdout": "", "stderr": "RigHaven node restarted during the task", "oom": false})
			continue
		}
		go s.uploadResult(dir, job, nil)
	}
}

func (s *agentSession) stopJob(id string) {
	if name, ok := nodeRunning.Load(id); ok {
		_ = dockerCommand(context.Background(), "stop", "--time", "10", name.(string)).Run()
	}
}

// packMounts writes the chosen folders of a run (and result.json) as tar.gz.
func packMounts(w io.Writer, job nodeRun, root string, modes map[string]bool, result map[string]any) error {
	gz := gzip.NewWriter(w)
	archive := tar.NewWriter(gz)
	if result != nil {
		data, _ := json.Marshal(result)
		if err := archive.WriteHeader(&tar.Header{Name: "result.json", Mode: 0o600, Size: int64(len(data)), ModTime: time.Now()}); err != nil {
			return err
		}
		if _, err := archive.Write(data); err != nil {
			return err
		}
	}
	for _, m := range job.Mounts {
		if !modes[m.Mode] {
			continue
		}
		base := filepath.Join(root, m.Key)
		err := filepath.Walk(base, func(path string, info os.FileInfo, err error) error {
			if err != nil {
				return err
			}
			if !info.Mode().IsRegular() && !info.IsDir() {
				return nil // links and devices stay on this machine
			}
			relative, _ := filepath.Rel(root, path)
			header := &tar.Header{Name: filepath.ToSlash(relative), Mode: int64(info.Mode().Perm()), ModTime: info.ModTime()}
			if info.IsDir() {
				header.Typeflag, header.Name = tar.TypeDir, header.Name+"/"
				return archive.WriteHeader(header)
			}
			header.Typeflag, header.Size = tar.TypeReg, info.Size()
			if err := archive.WriteHeader(header); err != nil {
				return err
			}
			file, err := os.Open(path)
			if err != nil {
				return err
			}
			defer file.Close()
			_, err = io.Copy(archive, file)
			return err
		})
		if err != nil && !os.IsNotExist(err) {
			return err
		}
	}
	if err := archive.Close(); err != nil {
		return err
	}
	return gz.Close()
}

// untar extracts a bundle: regular files and folders only, never outside root.
func untarRun(r io.Reader, root string) error {
	gz, err := gzip.NewReader(r)
	if err != nil {
		return err
	}
	archive := tar.NewReader(gz)
	for {
		header, err := archive.Next()
		if errors.Is(err, io.EOF) {
			return nil
		}
		if err != nil {
			return err
		}
		clean := filepath.Clean(filepath.FromSlash(header.Name))
		if filepath.IsAbs(clean) || clean == ".." || strings.HasPrefix(clean, ".."+string(filepath.Separator)) {
			return fmt.Errorf("path outside the bundle: %s", header.Name)
		}
		target := filepath.Join(root, clean)
		switch header.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(target, 0o755); err != nil {
				return err
			}
		case tar.TypeReg:
			if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
				return err
			}
			mode := os.FileMode(header.Mode).Perm() | 0o600
			file, err := os.OpenFile(target, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, mode)
			if err != nil {
				return err
			}
			_, err = io.Copy(file, archive)
			file.Close()
			if err != nil {
				return err
			}
		default:
			// links and special files are not part of a run
		}
	}
}

type limited struct {
	buffer *bytes.Buffer
	max    int
}

func (l *limited) Write(p []byte) (int, error) {
	if room := l.max - l.buffer.Len(); room > 0 {
		if len(p) > room {
			l.buffer.Write(p[:room])
		} else {
			l.buffer.Write(p)
		}
	}
	return len(p), nil
}

// nodeCommand: agent node on [--cpus N] [--memory GiB] [--jobs N] [--images GiB] | off | status
func nodeCommand(a *App, args []string, out io.Writer) error {
	config, err := loadAgentConfig()
	if err != nil {
		return errors.New(a.T("agent_not_linked"))
	}
	if len(args) == 0 || args[0] == "status" {
		if config.Node == nil {
			fmt.Fprintln(out, a.T("node_off"))
			return nil
		}
		offered, err := nodeCapacity(config.Node)
		if err != nil {
			return err
		}
		fmt.Fprintf(out, a.T("node_status")+"\n", offered["cpus"], offered["memory_mib"].(int)/1024, offered["jobs"], offered["docker"])
		return nil
	}
	switch args[0] {
	case "off":
		config.Node = nil
	case "on":
		node := &nodeConfig{Jobs: 1}
		for i := 1; i+1 < len(args); i += 2 {
			number, err := strconv.ParseFloat(args[i+1], 64)
			if err != nil || number < 0 {
				return fmt.Errorf("%s: not a number", args[i])
			}
			switch args[i] {
			case "--cpus":
				node.CPUs = number
			case "--memory":
				node.MemoryMiB = int(number * 1024)
			case "--jobs":
				node.Jobs = int(number)
			case "--images":
				node.ImagesGiB = number
			default:
				return fmt.Errorf("unknown option %s", args[i])
			}
		}
		if _, err := nodeCapacity(node); err != nil {
			return err
		}
		config.Node = node
	default:
		return errors.New("agent node on [--cpus N] [--memory GiB] [--jobs N] [--images GiB] | off | status")
	}
	if err := saveAgentConfig(config); err != nil {
		return err
	}
	fmt.Fprintln(out, map[bool]string{true: a.T("node_on"), false: a.T("node_off")}[config.Node != nil])
	return nil
}
