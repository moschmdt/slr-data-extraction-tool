"""Pytest tests for multiple selection configuration and list behavior."""

import json
import pathlib


def _load_data_items() -> dict:
    project_root = pathlib.Path(__file__).resolve().parents[1]
    data_items_path = project_root / "data-items.json"
    with data_items_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def test_type_of_evaluation_contains_multiple_marker() -> None:
    data = _load_data_items()
    evaluation_section = data.get("Evaluation (RQ5)", {})
    type_of_evaluation = evaluation_section.get("Type of evaluation", [])

    assert isinstance(type_of_evaluation, list)
    assert "Multiple" in type_of_evaluation


def test_multiple_selection_add_and_remove_values() -> None:
    selected_values = []
    test_values = ["Technical (Benchmark), Quantitative", "User study, Qualitative"]

    for value in test_values:
        if value not in selected_values:
            selected_values.append(value)

    assert selected_values == test_values

    value_to_remove = "Technical (Benchmark), Quantitative"
    if value_to_remove in selected_values:
        selected_values.remove(value_to_remove)

    assert selected_values == ["User study, Qualitative"]
