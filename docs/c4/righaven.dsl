workspace "RigHaven" "The Evolving Agent Harness & Open-Source CLI Environment Integrator" {

    model {
        user = person "Developer / Creator" "Uses RigHaven in Self-Hosted Community Edition or Multi-Tenant Cloud Portal."
        communityCreator = person "Community Pack Author" "Publishes Environment Rigs, Open-Source CLI Wrappers, and Agent Skills to RigHaven Hub."

        openaiCodex = softwareSystem "OpenAI Codex Provider" "Native app-server protocol LLM provider." "External"
        googleAntigravity = softwareSystem "Google Antigravity CLI (agy)" "Subscription-backed LLM provider via local IPC/pipe." "External"
        deepseekApi = softwareSystem "DeepSeek REST API" "HTTPS REST LLM provider." "External"
        oauthProviders = softwareSystem "GitHub & Google OAuth2" "Identity providers for RigHaven Cloud Portal." "External"

        righaven = softwareSystem "RigHaven Platform" "Hybrid Agent Harness & On-Demand Open-Source CLI Environment Integrator (Community & Cloud Editions)." {
            proxy = container "Edge Proxy (proxy)" "Terminates TLS, routes HTTP/HTTPS and SSE streams, and balances traffic across Frontend, Gateway, and Cloud Portal." "Caddy 2.10"
            frontend = container "Interactive Console (frontend)" "Multi-agent chat workspace, dynamic artifact viewer, Community Gallery UI, Cloud Portal UI, and native EN/IT i18n switcher." "Next.js / React 19 / TypeScript"
            gateway = container "Core Orchestrator & Hub API (gateway)" "Manages ask_clarification, harness_plan, dynamic role compilation, Gallery pack injection, harness_delegate, Cloud Multi-Tenant Auth/Vault, and Accept-Language i18n." "FastAPI / Python 3.12" {
                orchestrator = component "Harness Orchestrator" "Implements harness_plan, harness_delegate, surgical revision (revise_step_id), and reopen verification." "Python Module"
                galleryHub = component "Community Gallery Hub" "Validates righaven-pack.json manifests and serves /api/v1/gallery/packs." "Python Module"
                cloudAuth = component "Cloud Portal & Multi-Tenant Vault" "Handles JWT/OAuth2 auth, /mnt/user-data/tenants/<user_id> isolation, encrypted API key vault, and quotas." "Python Module"
                i18nEngine = component "Native i18n Engine" "Resolves Accept-Language (en default, it 100%) for notifications and ask_clarification." "Python Module"
            }
            redis = container "State & Event Broker (redis)" "FIFO execution queues, distributed locking (distlock), and real-time SSE Pub/Sub telemetry." "Redis 7.4"
            runtimeDocker = container "Sandbox Controller (runtime-docker)" "Security mediator over internal docker.sock; enforces cgroup CPU/RAM/PID limits and least-privilege volume mounts." "Docker-in-Docker / Python 3.12 Controller"
            workerSandbox = container "Ephemeral Worker Sandbox (worker-sandbox)" "Rootless, network-sealed Debian container running 37+ open-source CLIs and dynamically mounted Environment Packs." "Debian Bookworm / Rootless CLI Sandbox"
            righavenData = container "Workspace Volume (righaven-data)" "Stores /mnt/user-data (Read-Only for worker-sandbox, Read-Write for Gateway promotion) and outputs/workspace/rh-job-<id>." "Docker Volume" "Database"
            righavenState = container "State Volume (righaven-state)" "Stores .righaven-project/, encrypted credentials, Gallery packs, and tenant records." "Docker Volume" "Database"
        }

        user -> proxy "Interacts with Chat, Harness, Gallery, and Cloud Portal (HTTPS / SSE)"
        communityCreator -> proxy "Publishes and forks righaven-pack.json manifests (HTTPS)"
        proxy -> frontend "Routes UI requests"
        proxy -> gateway "Routes /api/*, /harness/*, /api/v1/gallery/*, /api/v1/cloud/*"
        frontend -> gateway "Calls REST & SSE APIs with Accept-Language (en | it)"
        gateway -> redis "Enqueues jobs, acquires distlock, and streams SSE events"
        gateway -> runtimeDocker "Spawns and reclaims isolated sandboxes via unix:///runtime/docker.sock"
        runtimeDocker -> workerSandbox "Instantiates with cgroup limits and mounts Environment Packs"
        workerSandbox -> righavenData "Reads /mnt/user-data (RO) and writes solely to RIGHAVEN_OUTPUT_DIR (outputs/workspace/rh-job-<id>)"
        gateway -> righavenData "Promotes verified handoff.json deliverables atomically (RW)"
        gateway -> righavenState "Persists config, Gallery activations, and encrypted Cloud Vault (RW)"
        gateway -> openaiCodex "Invokes via Codex app-server protocol"
        gateway -> googleAntigravity "Invokes via agy binary IPC/pipe"
        gateway -> deepseekApi "Invokes via HTTPS REST"
        gateway -> oauthProviders "Verifies OAuth2 identity in Cloud Edition"
    }

    views {
        systemContext righaven "SystemContext" {
            include *
            autoLayout lr
        }
        container righaven "Containers" {
            include *
            autoLayout tb
        }
        component gateway "GatewayComponents" {
            include *
            autoLayout lr
        }
    }
}
