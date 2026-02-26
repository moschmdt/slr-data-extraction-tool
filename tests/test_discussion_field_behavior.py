import csv
import importlib.util
import json
import os
import pathlib
import tempfile
import unittest
from contextlib import contextmanager

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication


def _load_gui_module():
    module_path = pathlib.Path(__file__).resolve().parents[1] / "data-extraction-gui.py"
    spec = importlib.util.spec_from_file_location("data_extraction_gui", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load data-extraction-gui.py")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def _working_directory(path: pathlib.Path):
    previous = pathlib.Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class TestDiscussionFieldBehavior(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.gui_module = _load_gui_module()

    def _write_test_files(self, root: pathlib.Path):
        data_items_path = root / "data-items.json"
        csv_path = root / "assignments.csv"

        data_items = {"RQ1": {"Category": ["Option A", "Other"]}}

        with data_items_path.open("w", encoding="utf-8") as f:
            json.dump(data_items, f)

        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["itemkey", "title", "author", "year", "assignee"],
                delimiter=";",
            )
            writer.writeheader()
            writer.writerow(
                {
                    "itemkey": "P1",
                    "title": "Paper 1",
                    "author": "Author A",
                    "year": "2024",
                    "assignee": "Moritz",
                }
            )
            writer.writerow(
                {
                    "itemkey": "P2",
                    "title": "Paper 2",
                    "author": "Author B",
                    "year": "2025",
                    "assignee": "Moritz",
                }
            )

        return data_items_path, csv_path

    def _create_window(self, root: pathlib.Path):
        data_items_path, csv_path = self._write_test_files(root)
        window = self.gui_module.DataExtractionGUI(
            user="Moritz",
            json_file=str(data_items_path),
            csv_file=str(csv_path),
        )
        return window

    def test_discussion_field_restores_after_switching_papers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            with _working_directory(root):
                window = self._create_window(root)
                try:
                    entry_key = "P1"
                    question_key = "RQ1"
                    attribute = "Category"
                    discussion_key = (
                        f"{entry_key}_{question_key}_{attribute}_discussion"
                    )
                    discussion_checkbox_key = (
                        f"{entry_key}_{question_key}_{attribute}_Discussion needed"
                    )

                    discussion_input = window.discussion_text_inputs[discussion_key]
                    discussion_container = window.discussion_containers[discussion_key]
                    self.assertFalse(discussion_input.isEnabled())
                    self.assertTrue(discussion_container.isHidden())

                    window.checkboxes[discussion_checkbox_key].setChecked(True)
                    self.assertTrue(discussion_input.isEnabled())
                    self.assertFalse(discussion_container.isHidden())

                    typed_text = "Needs team calibration"
                    discussion_input.setText(typed_text)
                    self.assertEqual(
                        window.discussion_texts.get(discussion_key), typed_text
                    )

                    window.load_paper(1)
                    window.load_paper(0)

                    restored_input = window.discussion_text_inputs[discussion_key]
                    restored_container = window.discussion_containers[discussion_key]
                    self.assertTrue(restored_input.isEnabled())
                    self.assertFalse(restored_container.isHidden())
                    self.assertEqual(restored_input.text(), typed_text)
                finally:
                    window.close()

    def test_discussion_field_enabled_only_when_discussion_selected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            with _working_directory(root):
                window = self._create_window(root)
                try:
                    entry_key = "P1"
                    question_key = "RQ1"
                    attribute = "Category"

                    discussion_key = (
                        f"{entry_key}_{question_key}_{attribute}_discussion"
                    )
                    discussion_checkbox_key = (
                        f"{entry_key}_{question_key}_{attribute}_Discussion needed"
                    )
                    option_a_checkbox_key = (
                        f"{entry_key}_{question_key}_{attribute}_Option A"
                    )

                    discussion_input = window.discussion_text_inputs[discussion_key]
                    discussion_container = window.discussion_containers[discussion_key]
                    self.assertFalse(discussion_input.isEnabled())
                    self.assertTrue(discussion_container.isHidden())

                    window.checkboxes[option_a_checkbox_key].setChecked(True)
                    self.assertFalse(discussion_input.isEnabled())
                    self.assertTrue(discussion_container.isHidden())

                    window.checkboxes[discussion_checkbox_key].setChecked(True)
                    self.assertTrue(discussion_input.isEnabled())
                    self.assertFalse(discussion_container.isHidden())

                    discussion_input.setText("Temporary note")
                    window.checkboxes[discussion_checkbox_key].setChecked(False)

                    self.assertFalse(discussion_input.isEnabled())
                    self.assertTrue(discussion_container.isHidden())
                    self.assertEqual(discussion_input.text(), "")
                finally:
                    window.close()


if __name__ == "__main__":
    unittest.main()
