"""Browser recipe pins cover code/data/cache while tolerating guide-only edits."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS=Path(__file__).resolve().parents[1]/'tools'
sys.path.insert(0,str(TOOLS))
from browser_sources import source_paths
spec=importlib.util.spec_from_file_location('browser_recipe_check',TOOLS/'check_browser_recipe.py')
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
sha=lambda data:hashlib.sha256(data).hexdigest()


class BrowserSourceTests(unittest.TestCase):
    def fixture(self,root):
        direct=root/'firmware_builder/direct';direct.mkdir(parents=True)
        for name,text in (('build.py','authored code'),('recipe.json','{}'),('README.md','guide')):
            (direct/name).write_text(text)
        cache=direct/'cache';cache.mkdir();(cache/'blob').write_bytes(b'synthetic cached input')
        site=root/'website';site.mkdir()
        sources={str(p.relative_to(root)):sha(p.read_bytes()) for p in source_paths(root)}
        payload=json.dumps({'sources':sources,'components':[]})
        (site/'recipe.js').write_text('globalThis.PX_RECIPE_JSON = '+json.dumps(payload)+';\n')
        (site/'recipe-pin.js').write_text('globalThis.PX_RECIPE_SHA256 = "'+sha(payload.encode())+'";\n')
        return direct

    def check(self,root):
        with patch.object(checker,'ROOT',root),contextlib.redirect_stdout(io.StringIO()):checker.main()

    def test_documentation_changes_do_not_invalidate_recipe(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);direct=self.fixture(root);self.check(root)
            (direct/'README.md').write_text('edited documentation link')
            (direct/'NEW_GUIDE.MD').write_text('new guide')
            (direct/'__pycache__').mkdir();(direct/'__pycache__/ignored.pyc').write_bytes(b'cache')
            self.check(root)

    def test_runtime_code_and_cached_data_edits_still_fail(self):
        for name in ('build.py','recipe.json','cache/blob'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);direct=self.fixture(root)
                (direct/name).write_text('changed input')
                with self.assertRaisesRegex(SystemExit,'Direct builder changed'):self.check(root)

    def test_new_runtime_source_still_requires_regeneration(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);direct=self.fixture(root)
            (direct/'new_helper.py').write_text('new authored code')
            with self.assertRaisesRegex(SystemExit,'source inventory changed'):self.check(root)


if __name__=='__main__':unittest.main()
