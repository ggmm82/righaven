import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('craft', Path(__file__).resolve().parents[1] / 'scripts/craft.py')
craft = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(craft)

# A real subprocess fixture: state disappears on exit, like the native MCP servers.
SERVER = '''
import json, sys
state = None
for line in sys.stdin:
    req = json.loads(line)
    if 'id' not in req:
        continue
    method = req['method']
    result = {}
    if method == 'tools/call':
        args = req['params']['arguments']
        name = req['params']['name']
        if name == 'open':
            state = {'document_id': 'document-1', 'text': args['text']}
            result = {'structuredContent': state}
        elif name == 'save':
            assert args['document_id'] == state['document_id']
            with open(args['path'], 'w') as output:
                output.write(state['text'])
            result = {'content': []}
        else:
            result = {'isError': True, 'content': [{'type': 'text', 'text': 'failure'}]}
    print(json.dumps({'jsonrpc': '2.0', 'id': req['id'], 'result': result}), flush=True)
'''


class CraftTests(unittest.TestCase):
    def test_mcp_text_json_ids_remain_typed_inside_a_stateful_batch(self):
        results = [{'content': [{'type': 'text', 'text': '{"id": 42, "items": [1, 2]}'}]}]
        value = craft.resolve_references({'parent': {'$result': '0.content.0.text.$json.id'},
                                         'items': {'$result': '0.content.0.text.$json.items'}}, results)
        self.assertEqual(value, {'parent': 42, 'items': [1, 2]})
        with self.assertRaises(ValueError):
            craft.resolve_references({'$result': '0.content.$json'}, results)
        with self.assertRaises(ValueError):
            craft.resolve_references({'$result': '0.content.0.text.$json'}, [{'content': [{'text': 'not JSON'}]}])

    def test_nested_references_keep_json_types(self):
        results = [{'structuredContent': {'items': [{'id': 7}]}}]
        self.assertEqual(craft.resolve_references({'ids': [{'$result': '0.structuredContent.items.0.id'}]}, results), {'ids': [7]})

    def test_invalid_reference_indices_and_paths_are_rejected(self):
        for reference in ('-1', '1', 'x', '0.items.-1', '0.items.1', '0.items.x', '0.missing', '0.items.0.foo'):
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                craft.resolve_references({'$result': reference}, [{'items': [7]}])

    def test_batch_preserves_state_and_saves_partial_failure_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            server = root / 'server.py'
            server.write_text(SERVER)
            (root / 'versions.lock.json').write_text(json.dumps({'applications': [
                {'id': 'fixture', 'executable': sys.executable, 'mcp_args': [str(server)]}]}))
            saved, report, batch = root / 'saved.txt', root / 'report.json', root / 'batch.json'
            batch.write_text(json.dumps([
                {'name': 'open', 'arguments': {'text': 'persisted'}},
                {'name': 'save', 'arguments': {'document_id': {'$result': '0.structuredContent.document_id'}, 'path': str(saved)}},
                {'name': 'fail'},
                {'name': 'save', 'arguments': {'path': str(root / 'must-not-exist')}}]))
            with patch.object(craft, 'ROOT', root), patch.object(sys, 'argv', ['craft', 'batch', 'fixture', str(batch), '--out', str(report)]):
                with self.assertRaises(RuntimeError):
                    craft.main()
            self.assertEqual(saved.read_text(), 'persisted')
            result = json.loads(report.read_text())
            self.assertEqual(result['completed'], 2)
            self.assertEqual(result['failed_index'], 2)
            self.assertFalse((root / 'must-not-exist').exists())


if __name__ == '__main__':
    unittest.main()
