# Minimum core boundary

RigHaven ships one authenticated application, not an embedded product showcase.

## Included

- Authentication, permissions and user-scoped storage.
- Agent execution, durable runs, streaming, cancellation and checkpoints.
- Project documents, editable artifacts, revisions and task history.
- Native skill and agent configuration, consumed by the RigHaven runtime.
- Managed environment preparation and disposable execution workers.

## Removed from this distribution

- Editorial landing pages, blog, localized MDX site and their page components.
- Static demonstration routes, sample conversations, sample media and thumbnails.
- Nextra documentation compilation and unused animation dependencies.
- Duplicate backend documentation and standalone development/migration scripts.
- Development dependency groups and the unrelated Lark CLI from production images.

Frontend dependencies are resolved in the committed lockfile. The Gateway installs
only runtime dependencies plus configured extension groups and optional extras.

The engine still contains optional channel and sandbox adapters. They are not
primary RigHaven UI surfaces. Removing their Python modules requires separating
the configuration/import contracts first; their mere presence does not mean an
extra runtime, channel or dependency is enabled.

The application opens on an operational overview. Navigation groups tasks and
projects, the toolbox, and configuration. Personal account preferences do not
advertise disabled profile-memory learning or a second specialist registry.
Deployment information explicitly distinguishes Community from the hosted preview.
