"""Run inside the pinned Gateway: native skill discovery and Agent references."""
import json
from pathlib import Path


def main():
    from righaven_core.config.agents_config import AgentConfig
    from righaven_core.skills.storage.local_skill_storage import LocalSkillStorage
    root = Path('/app/skills')
    store = LocalSkillStorage(host_path=str(root), container_path='/mnt/skills')
    found = {skill.name for skill in store.load_skills(enabled_only=False)}
    expected = {'skill-' + app['id'] for app in json.loads(Path('/app/backend/righaven/versions.lock.json').read_text())['applications']}
    expected |= {'skill-workspace', 'skill-harness','skill-problem-solving','skill-quality-review','skill-data-pipeline'}
    assert expected <= found, 'Native RigHaven discovery omitted: ' + str(sorted(expected - found))
    for name in expected:
        assert store.custom_skill_exists(name)
        store.validate_skill_markdown_content(name, store.read_custom_skill(name))
    profile = AgentConfig(name='skill-wiring-check', skills=sorted(expected))
    assert profile.skills == sorted(expected) and profile.model is None
    print('Native RigHaven skills + Agent references OK:', len(expected), 'skills; no duplicate model profile')


if __name__ == '__main__':main()
