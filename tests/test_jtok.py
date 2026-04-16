"""Unit tests for jtok.

Run from repo root:
    python -m unittest discover -s tests -v
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import jtok  # noqa: E402


# ---------------------------------------------------------------------------
# Primitive formatting + escaping
# ---------------------------------------------------------------------------

class TestFormatValue(unittest.TestCase):
    def test_none(self):
        self.assertEqual(jtok.format_value(None), "")

    def test_booleans(self):
        self.assertEqual(jtok.format_value(True), "T")
        self.assertEqual(jtok.format_value(False), "F")

    def test_trailing_zero_floats_collapse(self):
        self.assertEqual(jtok.format_value(25.0), "25")
        self.assertEqual(jtok.format_value(9.99), "9.99")
        self.assertEqual(jtok.format_value(3.140000), "3.14")

    def test_int(self):
        self.assertEqual(jtok.format_value(42), "42")


class TestCsvEscape(unittest.TestCase):
    def test_noop(self):
        self.assertEqual(jtok.csv_escape("hello"), "hello")

    def test_comma(self):
        self.assertEqual(jtok.csv_escape("a,b"), '"a,b"')

    def test_quote(self):
        self.assertEqual(jtok.csv_escape('he said "hi"'), '"he said ""hi"""')

    def test_newline(self):
        self.assertEqual(jtok.csv_escape("line1\nline2"), '"line1\nline2"')

    def test_empty(self):
        self.assertEqual(jtok.csv_escape(""), "")


class TestKvEscape(unittest.TestCase):
    def test_noop_simple(self):
        self.assertEqual(jtok.kv_escape("hello"), "hello")

    def test_noop_space_is_fine(self):
        # Spaces alone are unambiguous as long as no '=' follows
        self.assertEqual(jtok.kv_escape("node index.js"), "node index.js")

    def test_equals_in_value(self):
        self.assertEqual(jtok.kv_escape("key=val"), '"key=val"')

    def test_quote_in_value(self):
        self.assertEqual(jtok.kv_escape('he said "hi"'), '"he said \\"hi\\""')

    def test_newline(self):
        self.assertEqual(jtok.kv_escape("line1\nline2"), '"line1\nline2"')

    def test_leading_space_quoted(self):
        self.assertEqual(jtok.kv_escape(" leading"), '" leading"')

    def test_empty(self):
        self.assertEqual(jtok.kv_escape(""), "")


# ---------------------------------------------------------------------------
# README fixtures — these are the examples we promise in the README
# ---------------------------------------------------------------------------

class TestReadmeFixtures(unittest.TestCase):
    def test_homogeneous_csv(self):
        data = [
            {"name": "Alice", "age": 30, "city": "Paris", "active": True},
            {"name": "Bob", "age": 25, "city": "Tokyo", "active": False},
            {"name": "Carol", "age": 35, "city": "Lima", "active": True},
        ]
        expected = (
            "name,age,city,active\n"
            "Alice,30,Paris,T\n"
            "Bob,25,Tokyo,F\n"
            "Carol,35,Lima,T"
        )
        self.assertEqual(jtok.compress_json(data), expected)

    def test_wrapper_plus_array(self):
        data = {
            "total": 3,
            "page": 1,
            "results": [
                {"id": 1, "name": "Widget", "price": 9.99},
                {"id": 2, "name": "Gadget", "price": 24.50},
                {"id": 3, "name": "Gizmo", "price": 14.00},
            ],
        }
        expected = (
            "total=3\n"
            "page=1\n"
            "id,name,price\n"
            "1,Widget,9.99\n"
            "2,Gadget,24.5\n"
            "3,Gizmo,14"
        )
        self.assertEqual(jtok.compress_json(data), expected)

    def test_flat_kv_single_line(self):
        data = {
            "host": "localhost",
            "port": 8080,
            "debug": True,
            "workers": 4,
            "timeout": 30.0,
        }
        expected = "host=localhost port=8080 debug=T workers=4 timeout=30"
        self.assertEqual(jtok.compress_json(data), expected)

    def test_flat_kv_multiline(self):
        data = {
            "app_name": "myservice",
            "version": "2.1.0",
            "environment": "production",
            "database_url": "postgres://db.example.com:5432/main",
            "cache_ttl": 3600,
            "max_connections": 100,
            "log_level": "info",
            "feature_flags": ["dark_mode", "beta_api"],
        }
        out = jtok.compress_json(data)
        # Should wrap to multiple lines
        self.assertGreater(out.count("\n"), 0)
        # Sanity: all keys present
        for key in data:
            self.assertIn(key + "=", out)

    def test_toon_nested(self):
        data = {
            "name": "myproject",
            "version": "1.0.0",
            "private": True,
            "author": {"name": "Alice", "email": "alice@example.com"},
            "dependencies": {"express": "4.18.0", "lodash": "4.17.21"},
            "scripts": {"start": "node index.js", "test": "jest"},
        }
        expected = (
            "name=myproject version=1.0.0 private=T\n"
            "author: name=Alice email=alice@example.com\n"
            "dependencies: express=4.18.0 lodash=4.17.21\n"
            "scripts: start=node index.js test=jest"
        )
        self.assertEqual(jtok.compress_json(data), expected)

    def test_toon_with_nested_csv(self):
        data = {
            "store": "Downtown",
            "open": True,
            "location": {"lat": 48.8566, "lng": 2.3522, "country": "FR"},
            "inventory": [
                {"item": "Laptop", "qty": 15, "price": 999.00},
                {"item": "Mouse", "qty": 200, "price": 25.50},
                {"item": "Monitor", "qty": 42, "price": 350.00},
            ],
        }
        # detect_format routes dict+prominent-array to CSV; not TOON nested.
        out = jtok.compress_json(data)
        self.assertIn("item,qty,price", out)
        self.assertIn("Laptop,15,999", out)


# ---------------------------------------------------------------------------
# Escaping correctness within format conversions
# ---------------------------------------------------------------------------

class TestEscapeIntegration(unittest.TestCase):
    def test_csv_cell_with_comma(self):
        data = [{"name": "Alice, MD", "age": 30}, {"name": "Bob", "age": 25}]
        out = jtok.to_csv(data)
        self.assertIn('"Alice, MD"', out)
        # Bob has no comma — no quoting
        self.assertIn("Bob,25", out)

    def test_csv_cell_with_quote(self):
        data = [{"note": 'say "hi"', "id": 1}, {"note": "plain", "id": 2}]
        out = jtok.to_csv(data)
        self.assertIn('"say ""hi"""', out)

    def test_csv_cell_with_newline(self):
        data = [{"body": "line1\nline2", "id": 1}, {"body": "ok", "id": 2}]
        out = jtok.to_csv(data)
        self.assertIn('"line1\nline2"', out)

    def test_kv_value_with_equals(self):
        data = {"query": "a=1&b=2", "debug": True}
        out = jtok.to_kv(data)
        self.assertIn('query="a=1&b=2"', out)
        self.assertIn("debug=T", out)

    def test_kv_value_with_space_is_unquoted(self):
        # README example relies on this
        data = {"cmd": "node index.js"}
        self.assertEqual(jtok.to_kv(data), "cmd=node index.js")

    def test_csv_column_union_across_rows(self):
        # Second row has an extra key that shouldn't be silently dropped
        data = [{"a": 1}, {"a": 2, "b": 3}]
        out = jtok.to_csv(data)
        self.assertIn("a,b", out)
        self.assertIn("1,", out)
        self.assertIn("2,3", out)

    def test_scalar_list_element_with_comma_escaped(self):
        data = {"tags": ["a,b", "c"]}
        out = jtok.to_kv(data)
        # Inner element CSV-escaped; the outer KV layer then sees an embedded
        # `"` in the value and wraps-and-escapes for disambiguation.
        self.assertEqual(out, 'tags="\\"a,b\\",c"')


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

class TestDetectFormat(unittest.TestCase):
    def test_homogeneous_array_is_csv(self):
        self.assertEqual(
            jtok.detect_format([{"a": 1}, {"a": 2}]),
            "csv",
        )

    def test_flat_dict_is_kv(self):
        self.assertEqual(
            jtok.detect_format({"a": 1, "b": 2, "c": True}),
            "kv",
        )

    def test_dict_with_prominent_array_is_csv(self):
        data = {"total": 2, "results": [{"id": 1}, {"id": 2}]}
        self.assertEqual(jtok.detect_format(data), "csv")

    def test_nested_dict_is_toon(self):
        data = {"a": 1, "nested": {"x": 1, "y": 2}}
        self.assertEqual(jtok.detect_format(data), "toon")


# ---------------------------------------------------------------------------
# JSONL (newline-delimited JSON)
# ---------------------------------------------------------------------------

class TestJsonlParser(unittest.TestCase):
    def test_plain_json_still_works(self):
        self.assertEqual(jtok.parse_json_input('{"a": 1}'), {"a": 1})

    def test_jsonl_objects(self):
        text = '{"id":1,"name":"Alice"}\n{"id":2,"name":"Bob"}\n{"id":3,"name":"Carol"}'
        parsed = jtok.parse_json_input(text)
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0], {"id": 1, "name": "Alice"})

    def test_jsonl_compresses_to_csv(self):
        text = '{"id":1,"name":"Alice"}\n{"id":2,"name":"Bob"}\n{"id":3,"name":"Carol"}'
        parsed = jtok.parse_json_input(text)
        self.assertEqual(jtok.detect_format(parsed), "csv")

    def test_ignores_blank_lines(self):
        text = '{"a":1}\n\n{"a":2}\n'
        self.assertEqual(jtok.parse_json_input(text), [{"a": 1}, {"a": 2}])

    def test_bad_input_raises(self):
        with self.assertRaises(json.JSONDecodeError):
            jtok.parse_json_input("not json at all\nand still not json")


# ---------------------------------------------------------------------------
# Skip logic + sampling
# ---------------------------------------------------------------------------

class TestSkip(unittest.TestCase):
    def test_small_text_skipped(self):
        self.assertTrue(jtok.should_skip("x" * 100, {"a": 1}))

    def test_scalar_skipped(self):
        self.assertTrue(jtok.should_skip("x" * 1000, 42))

    def test_empty_collection_skipped(self):
        self.assertTrue(jtok.should_skip("x" * 1000, []))
        self.assertTrue(jtok.should_skip("x" * 1000, {}))

    def test_reasonable_dict_compressed(self):
        self.assertFalse(jtok.should_skip("x" * 1000, {"a": 1, "b": 2}))


class TestSampling(unittest.TestCase):
    def test_sample_list_endpoints(self):
        data = [{"i": i} for i in range(10)]
        sampled, omitted = jtok.apply_sampling(data, 2)
        self.assertEqual(len(sampled), 4)
        self.assertEqual(omitted, 6)
        self.assertEqual(sampled[0]["i"], 0)
        self.assertEqual(sampled[-1]["i"], 9)

    def test_no_sample_when_under_2n(self):
        data = [{"i": i} for i in range(3)]
        sampled, omitted = jtok.apply_sampling(data, 5)
        self.assertEqual(len(sampled), 3)
        self.assertEqual(omitted, 0)


if __name__ == "__main__":
    unittest.main()
