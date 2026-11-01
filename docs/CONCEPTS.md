# How the pieces fit together

RigHaven has a few building blocks. Each one answers a single question; together they turn a
request into a result you approve.

```
Request (optionally with a recipe)
  └─ Project ── expected result, in your words
       └─ Team ── roles composed by the coordinator
            └─ each role works with  Skills (how)  +  Environment (with which programs)  +  Connections (if you allow them)
                 └─ Deliveries ── versions with checked files
                      └─ Quality review + Policies ── checks before the final delivery
                           └─ Result ── the version you approve
```

| Block | Answers | Who decides | Where |
|---|---|---|---|
| **Project** | What do I want? | You, in a conversation | Tasks & results (the card above the chat) |
| **Recipe** | Is there a ready path for this kind of work? | Optional: you pick it, or the coordinator proposes it | Recipes, Community Gallery |
| **Team** | Who does what? | The coordinator composes roles for the project | Project card → *Team* |
| **Skill** | How is the work done well? | Installed or enabled in your account | Tools & skills |
| **Environment** | With which programs? | Presets or your own; prepared on first use | Environments, Community Gallery |
| **Connection** | Which external data or accounts? | You, per project; no role receives it without your consent | Connections |
| **Policy** | Which organization rules must every delivery respect? | Administrators publish; projects pin a version | Policy Book |
| **Delivery / version** | What has been produced so far? | The team delivers; checks run on every version | Project card → *Result*, *Versions* |
| **Result** | Is it what I asked for? | You approve | Project card |

## How they connect

- A **project** exists for every request. Without a recipe it is a *free project*: the coordinator
  agrees the result with you, composes the team and asks you to confirm after each production step.
- A **recipe** adds a saved path of phases to a project: what to attach, which phases, where you
  approve. Your goal written at the start is the project's result. Phase approvals in the card
  replace the chat confirmations of free projects, and phases you do not need can be skipped.
  A recipe names its skills and its environment, so the team starts from a known method and toolset.
- The **team** is not fixed: the coordinator compiles roles for the project, each with the skills and
  programs it needs. A role receives a connection only if you assigned it to the project and the role
  declares it.
- **Skills** and **environments** are reusable across projects. Recipes combine them; the Community
  Gallery lets you find and share all three.
- **Policies** apply to every project of the organization. A recipe may pin its own release policy
  (the built-in data recipe does); user recipes carry phases and approvals, not policies.
- Each **delivery** is a version. The quality review and the policy checks run before the final
  delivery; the **result** is the version you approve.

The same map is available in the app under *How the pieces fit together* on the Recipes,
Environments, Connections and Policy Book pages and in the project's *Status* tab.
