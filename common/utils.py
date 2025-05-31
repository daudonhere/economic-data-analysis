from decimal import Decimal # Added for calculate_descriptive_stats
import numpy as np # Added for calculate_descriptive_stats
# Typing imports if needed for type hints, assuming Python 3.9+ for built-in types
from typing import List, Dict, Any, Union # More specific typing

def extract_text_from_json_content(data_content: Union[Dict[Any, Any], List[Any]]) -> List[str]:
    """
    Recursively extracts all string values from a nested JSON structure
    (composed of dicts and lists).
    """
    texts: List[str] = []
    if isinstance(data_content, dict):
        for _, value in data_content.items():
            if isinstance(value, str):
                texts.append(value)
            elif isinstance(value, (dict, list)):
                texts.extend(extract_text_from_json_content(value))
    elif isinstance(data_content, list):
        for item_element in data_content:
            if isinstance(item_element, str):
                texts.append(item_element)
            elif isinstance(item_element, (dict, list)):
                 texts.extend(extract_text_from_json_content(item_element))
    return texts

def extract_all_strings_from_json(data_content: Union[Dict[Any, Any], List[Any]]) -> List[str]:
    """
    Recursively extracts all string values from a nested JSON structure.
    Similar to extract_text_from_json_content but might have slightly different intent or usage.
    Keeping it separate as per instruction to move it.
    """
    strings: List[str] = []
    if isinstance(data_content, dict):
        for value in data_content.values(): # Key is not used
            if isinstance(value, str):
                strings.append(value)
            elif isinstance(value, (dict, list)):
                strings.extend(extract_all_strings_from_json(value))
    elif isinstance(data_content, list):
        for item_element in data_content:
            if isinstance(item_element, str):
                strings.append(item_element)
            elif isinstance(item_element, (dict, list)):
                strings.extend(extract_all_strings_from_json(item_element))
    return strings

def calculate_descriptive_stats(data_list: List[Union[int, float, Decimal, None]]) -> Dict[str, Any]:
    """
    Calculates descriptive statistics for a list of numerical data.
    Handles None values and ensures data is float for numpy operations.
    """
    if not data_list:
        return {"mean": None, "median": None, "std_dev": None, "variance": None, "count": 0, "min": None, "max": None, "sum": None}

    # Filter out None values and convert valid numerical types to float
    valid_data: List[float] = []
    for x in data_list:
        if x is not None:
            if isinstance(x, (int, float)):
                valid_data.append(float(x))
            elif isinstance(x, Decimal):
                valid_data.append(float(x))
            # Potentially add a case for strings that can be converted, or log/error if type is unexpected

    if not valid_data:
        return {"mean": None, "median": None, "std_dev": None, "variance": None, "count": 0, "min": None, "max": None, "sum": None}

    arr = np.array(valid_data, dtype=float)
    # Check if arr is empty after potential filtering, though previous check should cover this
    if arr.size == 0:
        return {"mean": None, "median": None, "std_dev": None, "variance": None, "count": 0, "min": None, "max": None, "sum": None}

    return {
        "mean": round(np.mean(arr), 4),
        "median": round(np.median(arr), 4),
        "std_dev": round(np.std(arr), 4),
        "variance": round(np.var(arr), 4),
        "count": len(valid_data), # Use len(valid_data) as arr might be further filtered by numpy if NaN were introduced
        "min": round(np.min(arr), 4),
        "max": round(np.max(arr), 4),
        "sum": round(np.sum(arr), 4),
    }
