workspace "RigHaven" "Governed multi-agent harness and on-demand CLI environment integrator" {

    // Derived from the C4 model a RigHaven project produced about itself, checked against the code.

    model {
        user = person "Project owner" "Describes the objective, chooses among tool alternatives, discusses every phase with the coordinator and accepts deliveries."
        admin = person "Administrator" "Connects model providers, manages accounts, the Policy Book, capacity and trusted software images; reads machine usage for every user."
        packAuthor = person "Community pack author" "Publishes environment packs and skills through the Community Gallery (righaven-pack.json)."

        openaiCodex = softwareSystem "OpenAI Codex CLI" "Model provider run through the Codex app-server protocol." "External"
        antigravity = softwareSystem "Google Antigravity CLI (agy)" "Subscription-backed model provider." "External"
        claudeCode = softwareSystem "Claude Code CLI" "Optional model provider, prepared on demand." "External"
        apiProviders = softwareSystem "API model providers" "DeepSeek and OpenAI-compatible endpoints over HTTPS." "External"
        registries = softwareSystem "Upstream registries" "Docker, PyPI, npm and official release sources for locked tool versions." "External"

        righaven = softwareSystem "RigHaven" "Governed agent harness with a catalog of 62 managed CLI tools (Community and hosted editions)." {
            proxy = container "Edge proxy" "Terminates TLS and routes UI, API and SSE traffic." "Caddy"
            frontend = container "Workspace UI" "Chat with the coordinator, project details and Policy line, Environments, Policy Book, Machine usage and Gallery; Italian and English." "Next.js 16 / React 19 / TypeScript"
            gateway = container "Gateway and Harness" "Coordinator tools, project lifecycle, Policy Book, environments and delivery checks." "FastAPI / Python 3.12" {
                coordinatorTools = component "Coordinator tools" "harness_plan, harness_delegate, harness_delegate_batch, harness_validate, harness_skills and harness_read_context." "tools.py"
                projects = component "Project lifecycle" "Brief, Execution Plan, attempts, phase checkpoints, delivery gate and owner acceptance." "projects.py, project_brief.py"
                policyBook = component "Policy Book" "Declarative policy sheets with draft, active and retired states and immutable versions." "policy_book.py, policy_routes.py"
                policyWorkflow = component "Policy workflow" "Derives the governance phase, gates production, injects rules, checks handoff compliance and runs final multi-policy validation." "policy_workflow.py"
                acceptance = component "Acceptance and review engine" "Acceptance contract, independent review reports and verdicts per requirement." "acceptance.py, deliveries.py, handoff.py"
                capabilityPolicy = component "Capability policy" "Skills and tools authorized for each owner profile." "capability_policy.py, skill_composition.py"
                environments = component "Environment runtime" "Locked tool recipes, incremental images, profile reuse by role skills and tools, model CLI bundles." "environment_runtime.py, environment_selection.py, provider_bundle.py"
                dispatcher = component "Assignment dispatcher" "FIFO admission within CPU, RAM and worker limits; isolated staging per assignment." "docker_runtime.py, execution_queue.py, task_staging.py"
                audit = component "Audit and usage" "Conversation journal and per-assignment machine usage ledger." "audit_log.py, usage_ledger.py, progress.py"
            }
            broker = container "State and event broker" "Queues, locks and event streaming." "Redis 7.4" "Database"
            runtime = container "Internal container runtime" "Private Docker engine reached through unix:///runtime/docker.sock; the host Docker socket is never mounted." "Docker-in-Docker"
            worker = container "Assignment worker" "One container per assignment: capabilities dropped, no-new-privileges, PID, CPU and memory limits, bridge networking. Reads the project read-only and writes only to its staging folder." "Debian / prepared tool image"
            data = container "Project data" "Conversation workspaces, outputs and project state (.righaven-project)." "Docker volume" "Database"
            state = container "Installation state" "Policy Book, prepared images records, tool versions, usage ledger and settings." "Docker volume / SQLite" "Database"
        }

        user -> proxy "Uses the workspace" "HTTPS / SSE"
        admin -> proxy "Administers the installation" "HTTPS"
        packAuthor -> proxy "Publishes packs and skills" "HTTPS"
        proxy -> frontend "Routes UI requests"
        proxy -> gateway "Routes /api and SSE"
        frontend -> gateway "Calls REST and SSE APIs"
        gateway -> broker "Queues work and streams events"
        gateway -> runtime "Prepares images and starts assignment workers"
        runtime -> worker "Runs with resource limits and read-only project mounts"
        worker -> data "Reads the project; writes to its staging folder"
        gateway -> data "Validates handoffs and publishes verified deliveries"
        gateway -> state "Persists policies, versions, usage and settings"
        worker -> openaiCodex "Runs the configured model CLI from a read-only bundle"
        worker -> antigravity "Runs the configured model CLI from a read-only bundle"
        worker -> claudeCode "Runs the configured model CLI from a read-only bundle"
        gateway -> apiProviders "Calls API models"
        runtime -> registries "Fetches locked base images and tool releases"

        coordinatorTools -> projects "Records brief, plans and attempts"
        coordinatorTools -> policyWorkflow "Requests final validation"
        projects -> policyWorkflow "Enforces phases, checkpoints and the delivery gate"
        policyWorkflow -> policyBook "Pins applicable sheet versions in the Policy Plan"
        policyWorkflow -> acceptance "Evaluates review reports per sheet contract"
        coordinatorTools -> capabilityPolicy "Checks authorized skills and tools"
        coordinatorTools -> dispatcher "Delegates assignments"
        dispatcher -> environments "Selects a prepared profile or a dedicated image"
        environments -> runtime "Builds and reuses images"
        dispatcher -> runtime "Starts workers"
        dispatcher -> audit "Records progress and machine usage"
        projects -> audit "Records policy and phase events"
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
