import unittest
from nova.providers.resolver import ProviderResolver

class TestResolver(unittest.TestCase):
    def test_ranking_prefers_scripting(self):
        r = ProviderResolver()
        self.assertEqual(r.resolve("application.inspect", ["gui", "scripting"], ["gui", "scripting"]), "scripting")
    def test_capability_override_filesystem(self):
        r = ProviderResolver()
        self.assertEqual(r.resolve("document.read", ["gui", "filesystem"], ["gui", "filesystem"]), "filesystem")
    def test_no_candidate(self):
        r = ProviderResolver()
        self.assertIsNone(r.resolve("x", ["gui"], ["scripting"]))
    def test_fallback(self):
        r = ProviderResolver()
        self.assertEqual(r.fallback("scripting", ["gui", "cli"]), "cli")