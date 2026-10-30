"""Prepared owner profiles are the base of assignment environments, with a recorded reason."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from righaven import environment_runtime as runtime, environment_selection as selection, state


def profile(identifier, tools, size=1, versions=None, skills=()):
    return {'id': identifier * 64, 'tools': tools, 'size_bytes': size, 'versions': versions or {}, 'skills': set(skills)}


class ProfileSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        replacement = patch.object(state, 'STATE', self.root); replacement.start(); self.addCleanup(replacement.stop)
        (self.root / 'installation-id').write_text('fixture')
        self.policy = {'allowed': ['d2', 'poppler', 'typst', 'qpdf', 'pandoc', 'calibre']}

    def choose(self, needed, profiles, skills=()):
        rows = [(name, record, set(record['tools']) & set(self.policy['allowed']), record['skills']) for name, record in profiles]
        with patch.object(selection, 'profiles', return_value=iter(rows)):
            return selection.choose('owner', needed, self.policy, skills)

    def test_the_profile_covering_most_tools_wins_and_records_its_reason(self):
        documents = ('documenti', profile('a', ['typst', 'pandoc', 'calibre'], versions={'typst': 'rev-typst', 'provider-codex': 'cli'}))
        design = ('progettazione', profile('b', ['d2', 'poppler', 'qpdf']))
        base = self.choose(['d2', 'poppler', 'typst'], [documents, design])
        self.assertEqual((base['name'], base['covered'], base['missing']), ('progettazione', ['d2', 'poppler'], ['typst']))
        self.assertEqual(base['wanted'], 3)
        base = self.choose(['typst', 'pandoc'], [documents, design])
        self.assertEqual(base['name'], 'documenti')
        # Model CLIs are mounted separately and never pinned through a profile.
        self.assertEqual(base['versions'], {'typst': 'rev-typst'})

    def test_role_skills_present_in_a_profile_win_over_tool_coverage(self):
        writing = ('scrittura', profile('a', ['pandoc'], skills=['skill-copywriting', 'skill-typst']))
        tools = ('strumenti', profile('b', ['d2', 'poppler', 'typst']))
        base = self.choose(['d2', 'poppler', 'typst'], [tools, writing], skills=['skill-copywriting', 'skill-harness'])
        self.assertEqual((base['name'], base['skills'], base['role_skills']), ('scrittura', ['skill-copywriting'], ['skill-copywriting']))
        self.assertEqual(base['missing'], ['d2', 'poppler', 'typst'])  # extended with every program it lacks
        # A profile sharing only a skill is still a base when no program overlaps.
        self.assertEqual(self.choose(['d2'], [writing], skills=['skill-typst'])['name'], 'scrittura')
        # Coordination skills present in every profile do not count as a match.
        self.assertIsNone(self.choose(['d2'], [('base', profile('c', ['typst'], skills=['skill-harness']))], skills=['skill-harness']))

    def test_ties_prefer_fewer_unrequested_tools_then_the_smaller_image(self):
        lean = ('lean', profile('c', ['d2', 'poppler'], size=9))
        wide = ('wide', profile('d', ['d2', 'poppler', 'calibre'], size=1))
        self.assertEqual(self.choose(['d2', 'poppler'], [wide, lean])['name'], 'lean')
        small = ('small', profile('e', ['d2', 'poppler'], size=1))
        self.assertEqual(self.choose(['d2', 'poppler'], [lean, small])['name'], 'small')

    def test_no_profile_is_selected_without_overlap_or_tools(self):
        self.assertIsNone(self.choose(['d2'], [('documenti', profile('a', ['typst']))]))
        self.assertIsNone(self.choose([], [('documenti', profile('a', ['typst']))]))
        # Unauthorized tools of a profile do not count as coverage.
        self.policy['allowed'] = ['typst']
        self.assertIsNone(self.choose(['d2'], [('progettazione', profile('b', ['d2']))]))

    def test_assignment_adopts_profile_versions_only_for_covered_tools(self):
        base = {'covered': ['typst'], 'versions': {'typst': 'profile-rev'}}
        chosen = {'typst': 'default-rev', 'd2': 'default-d2'}
        self.assertEqual(selection.versions(chosen, base), {'typst': 'profile-rev', 'd2': 'default-d2'})
        # A covered tool the profile left on the built-in version drops the default pin too.
        self.assertEqual(selection.versions({'typst': 'pin'}, {'covered': ['typst'], 'versions': {}}), {})
        self.assertIs(selection.versions(chosen, None), chosen)

    def test_outcome_states_how_the_profile_was_used(self):
        base = {'name': 'documenti', 'id': 'a' * 64, 'covered': ['typst'], 'missing': ['d2'], 'versions': {},
                'skills': ['skill-typst'], 'role_skills': ['skill-typst'], 'wanted': 2}
        self.assertEqual(selection.outcome(base, {'id': 'a' * 64})['mode'], 'reused')
        extended = selection.outcome(base, {'id': 'x' * 64, 'base_environment_id': 'a' * 64, 'install_tools': ['d2']})
        self.assertEqual((extended['mode'], extended['added'], extended['skills']), ('extended', ['d2'], ['skill-typst']))
        self.assertNotIn('reason', extended)  # codes only: the interface words them per language
        self.assertEqual(selection.outcome(base, {'id': 'y' * 64})['mode'], 'not_reused')
        self.assertEqual(selection.outcome(None, {'id': 'z' * 64})['mode'], 'none')

    def test_usage_is_counted_per_profile(self):
        selection.record_use('owner', 'documenti', 'Impaginatore', 'extended')
        selection.record_use('owner', 'documenti', 'Revisore', 'reused')
        value = selection.usage('owner', 'documenti')
        self.assertEqual((value['jobs'], value['last_role'], value['last_mode']), (2, 'Revisore', 'reused'))
        self.assertEqual(selection.usage('owner', 'grafica'), {'jobs': 0})

    def test_the_preferred_profile_is_the_build_base_and_the_reused_image(self):
        key, spec = runtime.recipe(['d2', 'poppler', 'typst'], identity='sha256:base')
        fingerprints = spec['tool_fingerprints']
        for identifier, size in (('a', 9), ('b', 1)):
            runtime.save(identifier * 64, status='ready', core=spec['core'], tools=['d2', 'poppler'],
                         tool_fingerprints=fingerprints, image_id='sha256:' + identifier, size_bytes=size)
        with patch.object(runtime, 'image_exists', return_value=True):
            self.assertEqual(runtime.subset(spec)['id'], 'a' * 64)  # equal reuse: existing size tie-break
            self.assertEqual(runtime.subset(spec, 'b' * 64)['id'], 'b' * 64)  # the selected profile wins the tie
        _, partial = runtime.recipe(['d2'], identity='sha256:base')
        with patch.object(runtime, 'image_exists', return_value=True):
            self.assertEqual(runtime.candidates(partial, prefer='b' * 64)[0]['id'], 'b' * 64)


if __name__ == '__main__':
    unittest.main()
