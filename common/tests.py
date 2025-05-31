import json
from django.test import TestCase
from decimal import Decimal
import numpy as np

from common.utils import (
    extract_text_from_json_content,
    extract_all_strings_from_json,
    calculate_descriptive_stats,
)

class TestExtractTextFromJsonContent(TestCase):
    def test_simple_dictionary(self):
        data = {"key1": "text1", "key2": "text2"}
        self.assertEqual(sorted(extract_text_from_json_content(data)), sorted(["text1", "text2"]))

    def test_nested_dictionary(self):
        data = {"key1": "text1", "key2": {"subkey1": "text3", "subkey2": "text4"}}
        self.assertEqual(sorted(extract_text_from_json_content(data)), sorted(["text1", "text3", "text4"]))

    def test_list_of_strings(self):
        data = ["text1", "text2", "text3"]
        self.assertEqual(sorted(extract_text_from_json_content(data)), sorted(["text1", "text2", "text3"]))

    def test_list_of_dictionaries(self):
        data = [{"key1": "text1"}, {"key2": "text2", "key3": "text3"}]
        self.assertEqual(sorted(extract_text_from_json_content(data)), sorted(["text1", "text2", "text3"]))

    def test_mixed_content(self):
        data = {"key1": "text1", "key2": ["text2", {"subkey1": "text3"}], "key4": "text4"}
        self.assertEqual(sorted(extract_text_from_json_content(data)), sorted(["text1", "text2", "text3", "text4"]))

    def test_empty_input(self):
        self.assertEqual(extract_text_from_json_content({}), [])
        self.assertEqual(extract_text_from_json_content([]), [])

    def test_non_string_values(self):
        data = {"key1": "text1", "key2": 123, "key3": True, "key4": ["text2", 456]}
        self.assertEqual(sorted(extract_text_from_json_content(data)), sorted(["text1", "text2"]))


class TestExtractAllStringsFromJson(TestCase):
    # Assuming behavior is identical to extract_text_from_json_content
    def test_simple_dictionary(self):
        data = {"key1": "text1", "key2": "text2"}
        self.assertEqual(sorted(extract_all_strings_from_json(data)), sorted(["text1", "text2"]))

    def test_nested_dictionary(self):
        data = {"key1": "text1", "key2": {"subkey1": "text3", "subkey2": "text4"}}
        self.assertEqual(sorted(extract_all_strings_from_json(data)), sorted(["text1", "text3", "text4"]))

    def test_list_of_strings(self):
        data = ["text1", "text2", "text3"]
        self.assertEqual(sorted(extract_all_strings_from_json(data)), sorted(["text1", "text2", "text3"]))

    def test_list_of_dictionaries(self):
        data = [{"key1": "text1"}, {"key2": "text2", "key3": "text3"}]
        self.assertEqual(sorted(extract_all_strings_from_json(data)), sorted(["text1", "text2", "text3"]))

    def test_mixed_content(self):
        data = {"key1": "text1", "key2": ["text2", {"subkey1": "text3"}], "key4": "text4"}
        self.assertEqual(sorted(extract_all_strings_from_json(data)), sorted(["text1", "text2", "text3", "text4"]))

    def test_empty_input(self):
        self.assertEqual(extract_all_strings_from_json({}), [])
        self.assertEqual(extract_all_strings_from_json([]), [])

    def test_non_string_values(self):
        data = {"key1": "text1", "key2": 123, "key3": True, "key4": ["text2", 456]}
        self.assertEqual(sorted(extract_all_strings_from_json(data)), sorted(["text1", "text2"]))


class TestCalculateDescriptiveStats(TestCase):
    def test_list_of_integers(self):
        data = [1, 2, 3, 4, 5]
        stats = calculate_descriptive_stats(data)
        self.assertEqual(stats["count"], 5)
        self.assertAlmostEqual(stats["mean"], 3.0)
        self.assertAlmostEqual(stats["median"], 3.0)
        self.assertAlmostEqual(stats["std_dev"], np.std(data, ddof=0)) # ddof=0 for population std dev
        self.assertAlmostEqual(stats["variance"], np.var(data, ddof=0)) # ddof=0 for population variance
        self.assertEqual(stats["min"], 1)
        self.assertEqual(stats["max"], 5)
        self.assertEqual(stats["sum"], 15)

    def test_list_of_floats_and_decimals(self):
        data = [Decimal("1.5"), 2.5, Decimal("3.5")]
        stats = calculate_descriptive_stats(data)
        self.assertEqual(stats["count"], 3)
        self.assertAlmostEqual(stats["mean"], 2.5)
        self.assertAlmostEqual(stats["median"], 2.5)
        float_data = [float(x) for x in data]
        self.assertAlmostEqual(stats["std_dev"], np.std(float_data, ddof=0))
        self.assertAlmostEqual(stats["variance"], np.var(float_data, ddof=0))
        self.assertAlmostEqual(stats["min"], 1.5)
        self.assertAlmostEqual(stats["max"], 3.5)
        self.assertAlmostEqual(stats["sum"], 7.5)

    def test_list_including_none_values(self):
        data = [1, None, 3, None, 5]
        stats = calculate_descriptive_stats(data)
        self.assertEqual(stats["count"], 3)
        valid_data_float = [1.0, 3.0, 5.0]
        self.assertAlmostEqual(stats["mean"], 3.0)
        self.assertAlmostEqual(stats["median"], 3.0)
        self.assertAlmostEqual(stats["std_dev"], np.std(valid_data_float, ddof=0))
        self.assertAlmostEqual(stats["variance"], np.var(valid_data_float, ddof=0))
        self.assertEqual(stats["min"], 1)
        self.assertEqual(stats["max"], 5)
        self.assertEqual(stats["sum"], 9)

    def test_empty_list(self):
        data = []
        stats = calculate_descriptive_stats(data)
        self.assertEqual(stats["count"], 0)
        self.assertIsNone(stats["mean"])
        self.assertIsNone(stats["median"])
        self.assertIsNone(stats["std_dev"])
        self.assertIsNone(stats["variance"])
        self.assertIsNone(stats["min"])
        self.assertIsNone(stats["max"])
        self.assertIsNone(stats["sum"])


    def test_list_with_all_none_values(self):
        data = [None, None, None]
        stats = calculate_descriptive_stats(data)
        self.assertEqual(stats["count"], 0)
        self.assertIsNone(stats["mean"])

    def test_list_with_single_number(self):
        data = [10]
        stats = calculate_descriptive_stats(data)
        self.assertEqual(stats["count"], 1)
        self.assertAlmostEqual(stats["mean"], 10.0)
        self.assertAlmostEqual(stats["median"], 10.0)
        self.assertAlmostEqual(stats["std_dev"], 0.0)
        self.assertAlmostEqual(stats["variance"], 0.0)
        self.assertEqual(stats["min"], 10)
        self.assertEqual(stats["max"], 10)
        self.assertEqual(stats["sum"], 10)

    def test_list_with_non_numeric_strings_filtered_out(self):
        data = [1, "apple", 3, "banana", 5, None, Decimal("7.5")]
        stats = calculate_descriptive_stats(data)
        self.assertEqual(stats["count"], 4)
        valid_data_floats = [1.0, 3.0, 5.0, 7.5]
        self.assertAlmostEqual(stats["mean"], np.mean(valid_data_floats))
        self.assertAlmostEqual(stats["median"], np.median(valid_data_floats))
        self.assertAlmostEqual(stats["std_dev"], np.std(valid_data_floats, ddof=0))
        self.assertAlmostEqual(stats["variance"], np.var(valid_data_floats, ddof=0))
        self.assertEqual(stats["min"], 1.0)
        self.assertEqual(stats["max"], 7.5)
        self.assertAlmostEqual(stats["sum"], sum(valid_data_floats))
