import json
import os
import sys
import csv
import typing
import pathlib
from functools import partial
import sanity_checks
from typing import Dict, List, Optional
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QCheckBox,
    QLabel,
    QLineEdit,
    QScrollArea,
    QPushButton,
    QMessageBox,
    QRadioButton,
    QButtonGroup,
    QComboBox,
    QFrame,
    QDialog,
    QListWidget,
    QListWidgetItem,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QCloseEvent
from PyQt6.QtGui import QWheelEvent


class NoScrollComboBox(QComboBox):
    """Custom QComboBox that ignores wheel events to prevent scrolling from changing selection."""

    def wheelEvent(self, e: Optional[QWheelEvent]) -> None:
        """Ignore wheel events to prevent scrolling from changing the selected value."""
        if e is not None:
            e.ignore()


class PaperSelectionDialog(QDialog):
    """Dialog for selecting previously finished papers to edit.

    Displays a list of papers that have been completed and allows the user
    to select one to return to for updating or reviewing data.
    """

    def __init__(self, finished_papers: List[tuple], parent=None) -> None:
        """Initialize the Paper Selection Dialog.

        Args:
            finished_papers (List[tuple]): List of tuples (paper_key, title, authors, year) for completed papers.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.finished_papers = finished_papers
        self.selected_paper_key: Optional[str] = None
        self.init_ui()

    def init_ui(self) -> None:
        """Initialize the dialog UI."""
        self.setWindowTitle("Go Back to Finished Papers")
        self.setGeometry(100, 100, 700, 400)

        layout = QVBoxLayout()

        title_label = QLabel("Select a paper to review or update:")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Create list widget for finished papers
        self.paper_list = QListWidget()
        self.paper_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        for paper_key, title, authors, year in self.finished_papers:
            item_text = (
                f"{title}\n  Authors: {authors}\n  Year: {year}\n  Key: {paper_key}"
            )
            item = QListWidgetItem(item_text)
            item.setData(
                Qt.ItemDataRole.UserRole, paper_key
            )  # Store paper_key for retrieval
            self.paper_list.addItem(item)

        layout.addWidget(self.paper_list)

        # Button layout
        button_layout = QHBoxLayout()

        select_btn = QPushButton("Select")
        select_btn.clicked.connect(self.on_select)
        button_layout.addWidget(select_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def on_select(self) -> None:
        """Handle selection button click."""
        current_item = self.paper_list.currentItem()
        if current_item is None:
            QMessageBox.warning(
                self, "No Selection", "Please select a paper from the list."
            )
            return

        self.selected_paper_key = current_item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def get_selected_paper_key(self) -> Optional[str]:
        """Get the key of the selected paper.

        Returns:
            Optional[str]: The paper key if a paper was selected, None Otherwise.
        """
        return self.selected_paper_key


class DataExtractionGUI(QMainWindow):
    """GUI application for extracting metadata for research papers.

    Reads a CSV file containing paper data and JSON configuration, displays one paper
    at a time with nested tabs for each research question. Provides multi-select
    options with support for custom text input when "Other" is selected.
    User must click "Finish" to move to the next paper.
    """

    def __init__(
        self,
        user: str,
        json_file: str = "data-items.json",
        csv_file: str = "2026-02-24_data-extraction-assignments(in).csv",
    ) -> None:
        """Initialize the Data Extraction GUI.

        Args:
            json_file (str): Path to the JSON file containing research question data.
            csv_file (str): Path to the CSV file containing paper data.
            user (str): The user performing the data extraction (filters papers by assignee).
                        Valid values: Moritz, Andreas, Stina, Shu, Amar, Tobias
        """
        super().__init__()
        self.json_file = json_file
        self.csv_file = csv_file
        self.user = user
        self.data: Dict[str, Dict[str, List[str]]] = {}
        self.papers: Dict[str, Dict[str, str]] = {}
        self.paper_keys: List[str] = []  # Ordered list of paper keys
        self.current_paper_index: int = 0  # Index of current paper being worked on
        self.selected_values: Dict[str, Dict[str, Dict[str, List[str]]]] = {}
        self.selected_Other_text: Dict[str, Dict[str, Dict[str, str]]] = {}
        self.checkboxes: Dict[str, QCheckBox] = {}
        self.text_inputs: Dict[str, QLineEdit] = {}
        self.radio_buttons: Dict[str, QRadioButton] = {}
        self.radio_button_groups: Dict[str, QButtonGroup] = {}
        self.comboboxes: Dict[str, QComboBox] = {}
        self.discussion_text_inputs: Dict[str, QLineEdit] = {}
        self.discussion_containers: Dict[str, QFrame] = {}
        self.discussion_texts: Dict[str, str] = {}
        self.toggle_buttons: Dict[str, QCheckBox] = (
            {}
        )  # Toggle buttons for special options
        self.toggle_line_edits: Dict[str, QLineEdit] = (
            {}
        )  # Line edits for toggle-associated text
        self.toggle_states: Dict[str, Dict[str, Dict[str, bool]]] = (
            {}
        )  # Track toggle states: entry_key -> question_key -> attribute -> bool
        self.toggle_texts: Dict[str, Dict[str, Dict[str, str]]] = (
            {}
        )  # Track toggle text: entry_key -> question_key -> attribute -> str
        self.mandatory_text_inputs: Dict[str, QLineEdit] = (
            {}
        )  # Line edits for mandatory text fields
        self.mandatory_texts: Dict[str, Dict[str, Dict[str, str]]] = (
            {}
        )  # Track mandatory text: entry_key -> question_key -> attribute -> str
        self.question_tabs: Optional[QTabWidget] = (
            None  # Reference to nested question tabs
        )
        self.excluded_papers: Dict[str, bool] = (
            {}
        )  # Track which papers are excluded from full text review
        self.excluded_reasons: Dict[str, str] = (
            {}
        )  # Track exclusion reasons for each paper
        self.exclude_checkbox: Optional[QCheckBox] = (
            None  # Reference to the exclude checkbox
        )
        self.exclude_reason_input: Optional[QLineEdit] = (
            None  # Reference to the exclusion reason text field
        )

        # Load data and initialize UI
        if self.load_json_data() and self.load_csv_data():
            self.init_ui()
        else:
            sys.exit(1)

    def load_json_data(self) -> bool:
        """Load research question data from JSON file.

        Returns:
            bool: True if loaded successfully, False Otherwise.
        """
        try:
            with open(self.json_file, "r") as f:
                self.data = json.load(f)
            return True
        except FileNotFoundError:
            print(f"Error: {self.json_file} not found", file=sys.stderr)
            return False
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in {self.json_file}", file=sys.stderr)
            return False

    def load_csv_data(self) -> bool:
        """Load paper entries from CSV file.

        Parses CSV entries and filters by the assigned user. Extracts key metadata
        (itemkey, title, authors, year). Uses itemkey as the unique identifier.

        Returns:
            bool: True if loaded successfully and papers found, False Otherwise.
        """
        try:
            with open(self.csv_file, "r", encoding="utf-8") as f:
                # The CSV uses semicolon as delimiter
                reader = csv.DictReader(f, delimiter=";")

                for row in reader:
                    # The header has 'assignee,,,', so we need to find the correct key
                    assignee_value = None
                    for key in row.keys():
                        if "assignee" in key.lower():
                            assignee_value = row[key]
                            break

                    if not assignee_value:
                        continue

                    # Extract the assignee name (remove trailing commas from the value)
                    assignee = assignee_value.strip().rstrip(",").strip()
                    if assignee != self.user:
                        continue

                    itemkey = row.get("itemkey", "").strip()
                    if not itemkey:
                        continue

                    self.papers[itemkey] = {
                        "itemkey": itemkey,
                        "title": row.get("title", "Unknown Title").strip(),
                        "authors": row.get("author", "Unknown Authors").strip(),
                        "year": row.get("year", "Unknown Year").strip(),
                    }
                    self.paper_keys.append(itemkey)

            if not self.papers:
                print(
                    f"Error: No papers assigned to user '{self.user}' in {self.csv_file}",
                    file=sys.stderr,
                )
                return False

            return True
        except FileNotFoundError:
            print(f"Error: {self.csv_file} not found", file=sys.stderr)
            return False
        except Exception as e:
            print(f"Error reading {self.csv_file}: {str(e)}", file=sys.stderr)
            return False

    def find_first_unprocessed_paper(self) -> int:
        """Find the index of the first paper without exported data.

        Checks the export.json file to see which papers have already been processed.
        Returns the index of the first paper that has no responses recorded and is not excluded.

        Also checks for a session file to resume incomplete work.

        Returns:
            int: Index of the first unprocessed paper, or 0 if no export file exists.
        """
        session_file = ".session.json"
        export_file = "export.json"

        # Check if there's a session file with incomplete work
        if os.path.exists(session_file):
            try:
                with open(session_file, "r") as f:
                    session_data = json.load(f)
                    # Only resume if the session is for the current user
                    if (
                        session_data.get("user") == self.user
                        and "current_paper_index" in session_data
                    ):
                        resume_index = session_data["current_paper_index"]
                        # Verify the paper index is valid
                        if 0 <= resume_index < len(self.paper_keys):
                            return resume_index
            except (json.JSONDecodeError, IOError):
                pass

        # If export file doesn't exist, start from the beginning
        if not os.path.exists(export_file):
            return 0

        try:
            with open(export_file, "r") as f:
                exported_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            # If file is corrupted or unreadable, start from the beginning
            return 0

        # Check each paper in order
        for index, paper_key in enumerate(self.paper_keys):
            # If paper is not in export file or has empty responses, it's unprocessed
            if paper_key not in exported_data:
                return index

            paper_data = exported_data[paper_key]

            # Check if paper is excluded - if so, it's already processed
            if paper_data.get("excluded_from_full_text_review", False):
                self.excluded_papers[paper_key] = True
                continue

            responses = paper_data.get("responses", {})

            # Check if responses are empty (paper has no data)
            is_empty = True
            for question_key in responses:
                for attribute_list in responses[question_key].values():
                    if attribute_list:  # If any attribute has selections
                        is_empty = False
                        break
                if not is_empty:
                    break

            if is_empty:
                return index

        # All papers have been processed, return last index to trigger completion
        return len(self.paper_keys)

    def get_finished_papers(self) -> List[tuple]:
        """Get list of papers that have been finished (have responses in export file).

        Returns:
            List[tuple]: List of tuples (paper_key, title, authors, year) for finished papers.
        """
        finished = []
        export_file = "export.json"

        if not os.path.exists(export_file):
            return finished

        try:
            with open(export_file, "r") as f:
                exported_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return finished

        # Iterate through papers to find those with responses
        for paper_key in self.paper_keys:
            if paper_key not in exported_data:
                continue

            paper_data = exported_data[paper_key]
            responses = paper_data.get("responses", {})

            # Check if paper has any responses (not empty)
            has_responses = False
            for question_key in responses:
                for attribute_list in responses[question_key].values():
                    if attribute_list:
                        has_responses = True
                        break
                if has_responses:
                    break

            # Add to finished list if it has responses
            if has_responses or paper_data.get("excluded_from_full_text_review", False):
                entry_data = self.papers.get(paper_key, {})
                finished.append(
                    (
                        paper_key,
                        entry_data.get("title", "Unknown"),
                        entry_data.get("authors", "Unknown"),
                        entry_data.get("year", "Unknown"),
                    )
                )

        return finished

    def on_go_back(self) -> None:
        """Handle the 'Go Back' button click to select a previously finished paper."""
        finished_papers = self.get_finished_papers()

        if not finished_papers:
            QMessageBox.information(
                self,
                "No Finished Papers",
                "There are no previously finished papers to go back to.",
            )
            return

        # Show dialog for selecting a paper
        dialog = PaperSelectionDialog(finished_papers, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_key = dialog.get_selected_paper_key()
            if selected_key:
                # Find index of selected paper
                try:
                    index = self.paper_keys.index(selected_key)
                    self.load_paper(index)
                except ValueError:
                    QMessageBox.warning(
                        self, "Error", "Could not find the selected paper."
                    )

    def init_ui(self) -> None:
        """Initialize the user interface."""
        self.setWindowTitle("Research Data Extraction Tool")
        self.setGeometry(100, 100, 1200, 800)

        main_widget = QWidget()
        main_layout = QVBoxLayout()

        title_label = QLabel("Research Data Extraction Tool")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        main_layout.addWidget(title_label)

        # Paper info section
        paper_info_container = QWidget()
        paper_info_layout = QVBoxLayout()
        paper_info_layout.setContentsMargins(0, 0, 0, 0)

        self.paper_info_label = QLabel()
        info_font = QFont()
        info_font.setPointSize(9)
        self.paper_info_label.setFont(info_font)
        self.paper_info_label.setStyleSheet(
            "background-color: #2c3e50; color: #ecf0f1; padding: 10px; border-radius: 5px; border: 1px solid #1a252f;"
        )
        self.paper_info_label.setWordWrap(True)
        self.paper_info_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        paper_info_layout.addWidget(self.paper_info_label)

        # Exclude checkbox
        self.exclude_checkbox = QCheckBox(
            "⚠️ Exclude from full text review (irrelevant for research questions)"
        )
        exclude_font = QFont()
        exclude_font.setPointSize(9)
        exclude_font.setBold(True)
        self.exclude_checkbox.setFont(exclude_font)
        self.exclude_checkbox.setStyleSheet(
            "QCheckBox { color: #d9534f; padding: 5px; }"
        )
        self.exclude_checkbox.stateChanged.connect(self.on_exclude_changed)
        paper_info_layout.addWidget(self.exclude_checkbox)

        # Exclusion reason text field
        reason_label = QLabel("Reason for exclusion:")
        reason_font = QFont()
        reason_font.setPointSize(8)
        reason_font.setItalic(True)
        reason_label.setFont(reason_font)
        reason_label.setStyleSheet("color: #666666; padding: 5px 0px 2px 20px;")
        reason_label.setVisible(False)
        paper_info_layout.addWidget(reason_label)

        self.exclude_reason_input = QLineEdit()
        self.exclude_reason_input.setPlaceholderText(
            "e.g., 'Out of scope', 'Duplicate', 'Irrelevant methodology'"
        )
        self.exclude_reason_input.setMaximumHeight(30)
        self.exclude_reason_input.setStyleSheet(
            "QLineEdit { background-color: #f9f9f9; color: #999999; border: 1px solid #d0d0d0; border-radius: 3px; padding: 5px; margin-left: 20px; }"
        )
        self.exclude_reason_input.setVisible(False)
        self.exclude_reason_input.setEnabled(False)
        self.exclude_reason_input.textChanged.connect(self.on_exclude_reason_changed)
        self.exclude_reason_label = (
            reason_label  # Store reference for toggling visibility
        )
        paper_info_layout.addWidget(self.exclude_reason_input)

        paper_info_container.setLayout(paper_info_layout)
        main_layout.addWidget(paper_info_container)

        # Nested tabs for research questions
        self.question_tabs = QTabWidget()
        main_layout.addWidget(self.question_tabs)

        # Create button layout
        button_layout = QHBoxLayout()

        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self.export_data)
        button_layout.addWidget(export_btn)

        self.go_back_btn = QPushButton("Go Back to Previous Paper")
        self.go_back_btn.clicked.connect(self.on_go_back)
        button_layout.addWidget(self.go_back_btn)

        self.finish_btn = QPushButton("Finish")
        self.finish_btn.clicked.connect(self.finish_paper)
        button_layout.addWidget(self.finish_btn)

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self.clear_all)
        button_layout.addWidget(clear_btn)

        exit_btn = QPushButton("Exit")
        exit_btn.clicked.connect(self.on_exit)
        button_layout.addWidget(exit_btn)

        main_layout.addLayout(button_layout)

        # Progress indicator
        self.progress_label = QLabel()
        progress_font = QFont()
        progress_font.setPointSize(9)
        progress_font.setItalic(True)
        self.progress_label.setFont(progress_font)
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        main_layout.addWidget(self.progress_label)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # Find and load the first unprocessed paper
        start_index = self.find_first_unprocessed_paper()
        self.load_paper(start_index)

    def on_exit(self) -> None:
        """Handle exit button click.

        Automatically exports data and saves session state before closing the application.
        """
        self._perform_export()
        self._save_session_state()
        self.close()

    def closeEvent(self, a0: Optional[QCloseEvent]) -> None:
        """Handle window close event.

        Automatically exports data and saves session state when the window is closed.
        """
        self._perform_export()
        self._save_session_state()
        if a0:
            a0.accept()

    def load_paper(self, index: int) -> None:
        """Load and display a specific paper.

        Args:
            index (int): Index of the paper to load.
        """
        if index >= len(self.paper_keys):
            QMessageBox.information(
                self, "Completed", "All papers have been processed!"
            )
            self.close()
            return

        self.current_paper_index = index
        entry_key = self.paper_keys[index]
        entry_data = self.papers[entry_key]

        paper_title = entry_data.get("title", "Unknown")
        paper_authors = entry_data.get("authors", "Unknown")
        paper_year = entry_data.get("year", "Unknown")

        # Update paper info label
        info_text = f"Title: {paper_title}\nAuthors: {paper_authors}\nYear: {paper_year}\nUser: {self.user}"
        self.paper_info_label.setText(info_text)

        # Update exclude checkbox state
        if self.exclude_checkbox is not None:
            is_excluded = self.excluded_papers.get(entry_key, False)
            self.exclude_checkbox.blockSignals(True)
            self.exclude_checkbox.setChecked(is_excluded)
            self.exclude_checkbox.blockSignals(False)

            # Enable/disable question tabs based on exclusion status
            if self.question_tabs is not None:
                self.question_tabs.setEnabled(not is_excluded)

            # Update reason field visibility and content
            if self.exclude_reason_input is not None:
                self.exclude_reason_input.setVisible(is_excluded)
                self.exclude_reason_label.setVisible(is_excluded)
                if is_excluded:
                    previous_reason = self.excluded_reasons.get(entry_key, "")
                    self.exclude_reason_input.blockSignals(True)
                    self.exclude_reason_input.setText(previous_reason)
                    self.exclude_reason_input.blockSignals(False)
                    self.exclude_reason_input.setEnabled(True)
                    self.exclude_reason_input.setStyleSheet(
                        "QLineEdit { background-color: white; color: #333333; border: 1px solid #d9534f; border-radius: 3px; padding: 5px; margin-left: 20px; }"
                    )
                else:
                    self.exclude_reason_input.setEnabled(False)
                    self.exclude_reason_input.setStyleSheet(
                        "QLineEdit { background-color: #f9f9f9; color: #999999; border: 1px solid #d0d0d0; border-radius: 3px; padding: 5px; margin-left: 20px; }"
                    )

        # Clear and recreate question tabs
        if self.question_tabs is not None:
            self.question_tabs.clear()
        self.checkboxes.clear()
        self.text_inputs.clear()
        self.radio_buttons.clear()
        self.radio_button_groups.clear()
        self.comboboxes.clear()
        self.discussion_text_inputs.clear()
        self.discussion_containers.clear()
        self.toggle_buttons.clear()
        self.toggle_line_edits.clear()
        self.mandatory_text_inputs.clear()

        # Initialize tracking for this paper if not already done
        if entry_key not in self.selected_values:
            self.selected_values[entry_key] = {}
            self.selected_Other_text[entry_key] = {}
            self.toggle_states[entry_key] = {}
            # Load previous progress from export file
            self._load_paper_progress(entry_key)

        # Create nested tabs for research questions
        if self.question_tabs is not None:
            for question_key, options_dict in self.data.items():
                question_tab = self.create_question_tab(
                    entry_key, question_key, options_dict
                )
                self.question_tabs.addTab(question_tab, question_key)

        # Update progress label
        progress_text = f"Paper {index + 1} of {len(self.paper_keys)}"
        self.progress_label.setText(progress_text)

        # Save current session state
        self._save_session_state()

    def _load_paper_progress(self, entry_key: str) -> None:
        """Load previously saved progress for a paper from the export file.

        Args:
            entry_key (str): The BIB entry key for the paper.
        """
        export_file = "export.json"
        if not os.path.exists(export_file):
            return

        try:
            with open(export_file, "r") as f:
                exported_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return

        if entry_key not in exported_data:
            return

        paper_data = exported_data[entry_key]

        # Restore exclusion status
        self.excluded_papers[entry_key] = paper_data.get(
            "excluded_from_full_text_review", False
        )

        # Restore exclusion reason
        self.excluded_reasons[entry_key] = paper_data.get("exclusion_reason", "")

        # Restore toggle states and texts (format in export: question_key -> attribute -> {"enabled": bool, "text": str})
        toggle_data = paper_data.get("toggle_states", {})
        if toggle_data:
            if entry_key not in self.toggle_states:
                self.toggle_states[entry_key] = {}
            if entry_key not in self.toggle_texts:
                self.toggle_texts[entry_key] = {}
            for question_key, attrs in toggle_data.items():
                if question_key not in self.toggle_states[entry_key]:
                    self.toggle_states[entry_key][question_key] = {}
                if question_key not in self.toggle_texts[entry_key]:
                    self.toggle_texts[entry_key][question_key] = {}
                for attribute, val in attrs.items():
                    # val can be a dict with enabled/text or a simple boolean (legacy)
                    if isinstance(val, dict):
                        enabled = bool(val.get("enabled", True))
                        text = str(val.get("text", ""))
                    else:
                        enabled = bool(val)
                        text = ""
                    self.toggle_states[entry_key][question_key][attribute] = enabled
                    self.toggle_texts[entry_key][question_key][attribute] = text

        # Restore mandatory texts (format in export: question_key -> attribute -> text)
        mandatory_data = paper_data.get("mandatory_texts", {})
        if mandatory_data:
            if entry_key not in self.mandatory_texts:
                self.mandatory_texts[entry_key] = {}
            for question_key, attrs in mandatory_data.items():
                if question_key not in self.mandatory_texts[entry_key]:
                    self.mandatory_texts[entry_key][question_key] = {}
                for attribute, text in attrs.items():
                    self.mandatory_texts[entry_key][question_key][attribute] = text

        responses = paper_data.get("responses", {})

        # Reconstruct the selections from the exported data
        for question_key in responses:
            if question_key not in self.selected_values[entry_key]:
                self.selected_values[entry_key][question_key] = {}
                self.selected_Other_text[entry_key][question_key] = {}

            for attribute, selections in responses[question_key].items():
                if attribute not in self.selected_values[entry_key][question_key]:
                    self.selected_values[entry_key][question_key][attribute] = []
                    self.selected_Other_text[entry_key][question_key][attribute] = ""

                # Parse selections and reconstruct them
                for selection in selections:
                    if selection.startswith("Other: "):
                        # Extract "Other" text
                        Other_text = selection[7:]  # Remove "Other: " prefix
                        self.selected_values[entry_key][question_key][attribute].append(
                            "Other"
                        )
                        self.selected_Other_text[entry_key][question_key][
                            attribute
                        ] = Other_text
                    elif selection.startswith("Discussion needed: "):
                        # Extract discussion text
                        discussion_text = selection[
                            19:
                        ]  # Remove "Discussion needed: " prefix
                        self.selected_values[entry_key][question_key][attribute].append(
                            "Discussion needed"
                        )
                        discussion_key = (
                            f"{entry_key}_{question_key}_{attribute}_discussion"
                        )
                        # Store in state (will be applied when widgets are created)
                        if (
                            attribute
                            not in self.selected_Other_text[entry_key][question_key]
                        ):
                            self.selected_Other_text[entry_key][question_key][
                                attribute
                            ] = ""
                        self.discussion_texts[discussion_key] = discussion_text
                    else:
                        self.selected_values[entry_key][question_key][attribute].append(
                            selection
                        )

    def _save_session_state(self) -> None:
        """Save the current session state to allow resuming incomplete work."""
        session_file = ".session.json"
        try:
            session_data = {
                "user": self.user,
                "current_paper_index": self.current_paper_index,
                "current_paper_key": (
                    self.paper_keys[self.current_paper_index]
                    if self.current_paper_index < len(self.paper_keys)
                    else None
                ),
            }
            with open(session_file, "w") as f:
                json.dump(session_data, f, indent=2)
        except IOError:
            pass  # Silently fail if we can't save session

    def finish_paper(self) -> None:
        """Mark current paper as finished and load the next one.

        Only allows moving to the next paper if the paper is excluded OR if all categories
        in all questions have at least one selection.
        """
        entry_key = self.paper_keys[self.current_paper_index]

        # If paper is excluded, we can skip validation and move to next
        if self.excluded_papers.get(entry_key, False):
            self.load_paper(self.current_paper_index + 1)
            return

        # Otherwise, validate that all categories have selections
        if not self.validate_all_required_fields():
            return

        # First, write current selections to export.json (silent)
        self._perform_export()

        # Load the just-exported paper data and run sanity checks defined in sanity_checks.json
        try:
            with open("export.json", "r") as f:
                exported = json.load(f)
        except (IOError, json.JSONDecodeError):
            exported = {}

        paper_entry = exported.get(entry_key, {})

        violations = []
        try:
            violations = sanity_checks.validate_paper(
                paper_entry, config_path=str(pathlib.Path("sanity_checks.json"))
            )
        except Exception as e:
            # If the validator fails unexpectedly, surface an error and abort finishing so user can investigate
            QMessageBox.critical(
                self,
                "Sanity Check Error",
                f"An error occurred while running sanity checks: {str(e)}",
            )
            return

        if violations:
            # Show violations and block finishing until they are resolved
            details = "\n".join([f"- {v}" for v in violations])
            QMessageBox.warning(
                self,
                "Sanity Checks Failed",
                f"The following sanity checks failed for this paper:\n\n{details}\n\nPlease review and correct before finishing.",
            )
            return

        # If we reach here, all sanity checks passed — proceed to next paper
        # Show success export box and move on
        QMessageBox.information(self, "Success", "Data exported to export.json")
        # Move to next paper
        self.load_paper(self.current_paper_index + 1)

    def validate_all_required_fields(self) -> bool:
        """Validate that every category in every research question has at least one selection.

        Also validates that if 'Discussion needed' is selected, a discussion text must be provided.

        If the paper is marked as excluded, validation is skipped.

        Returns:
            bool: True if all required fields are filled or paper is excluded, False Otherwise.
        """
        entry_key = self.paper_keys[self.current_paper_index]

        # Skip validation if paper is excluded
        if self.excluded_papers.get(entry_key, False):
            return True

        # Check each research question
        for question_key, options_dict in self.data.items():
            # Check each attribute (category) in the question
            for attribute in options_dict.keys():
                # Get selections for this attribute
                selections = (
                    self.selected_values[entry_key]
                    .get(question_key, {})
                    .get(attribute, [])
                )

                # Check if at least one item is selected
                if not selections:
                    # Show error message with details
                    missing_info = (
                        f"Research Question: {question_key}\nCategory: {attribute}"
                    )
                    QMessageBox.warning(
                        self,
                        "Incomplete Data",
                        f"Please select at least one item for:\n\n{missing_info}",
                    )
                    return False

                # If "Discussion needed" is selected, check that discussion text is provided
                if "Discussion needed" in selections:
                    discussion_key = (
                        f"{entry_key}_{question_key}_{attribute}_discussion"
                    )
                    if discussion_key in self.discussion_text_inputs:
                        discussion_text = (
                            self.discussion_text_inputs[discussion_key].text().strip()
                        )
                        if not discussion_text:
                            missing_info = f"Research Question: {question_key}\nCategory: {attribute}"
                            QMessageBox.warning(
                                self,
                                "Discussion Text Required",
                                f"Since 'Discussion needed' is selected for:\n\n{missing_info}\n\nPlease provide a discussion explanation in the text field.",
                            )
                            return False

                # Check if mandatory text field is required and filled
                options = options_dict.get(attribute)
                if isinstance(options, dict):
                    mandatory_text_config = options.get("mandatory_text_field", None)
                    if mandatory_text_config and mandatory_text_config.get(
                        "enabled", False
                    ):
                        # If any selection is made, mandatory text must be provided
                        if selections:  # There are selections
                            mandatory_text = (
                                self.mandatory_texts.get(entry_key, {})
                                .get(question_key, {})
                                .get(attribute, "")
                                .strip()
                            )
                            if not mandatory_text:
                                missing_info = f"Research Question: {question_key}\nCategory: {attribute}"
                                field_label = mandatory_text_config.get(
                                    "label", "Additional information"
                                )
                                QMessageBox.warning(
                                    self,
                                    "Required Text Missing",
                                    f"For:\n\n{missing_info}\n\nPlease provide: {field_label}",
                                )
                                return False

        return True

    def create_question_tab(
        self, entry_key: str, question_key: str, options_dict: Dict[str, List[str]]
    ) -> QWidget:
        """Create a tab for a single research question within a paper.

        Args:
            entry_key (str): The BIB entry key for the paper.
            question_key (str): The research question identifier.
            options_dict (Dict[str, List[str]]): Dictionary of attributes and their options.

        Returns:
            QWidget: The constructed tab widget.
        """
        # Initialize tracking for this question
        if question_key not in self.selected_values[entry_key]:
            self.selected_values[entry_key][question_key] = {}
            self.selected_Other_text[entry_key][question_key] = {}
            # Ensure toggle structures exist for this paper/question
            if entry_key not in self.toggle_states:
                self.toggle_states[entry_key] = {}
            if question_key not in self.toggle_states[entry_key]:
                self.toggle_states[entry_key][question_key] = {}
            if entry_key not in self.toggle_texts:
                self.toggle_texts[entry_key] = {}
            if question_key not in self.toggle_texts[entry_key]:
                self.toggle_texts[entry_key][question_key] = {}
            if entry_key not in self.mandatory_texts:
                self.mandatory_texts[entry_key] = {}
            if question_key not in self.mandatory_texts[entry_key]:
                self.mandatory_texts[entry_key][question_key] = {}

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background-color: white; }")

        container = QWidget()
        container.setStyleSheet("QWidget { background-color: white; }")
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Create grid for attributes
        for attribute, options in options_dict.items():
            # Initialize tracking for this attribute
            if attribute not in self.selected_values[entry_key][question_key]:
                self.selected_values[entry_key][question_key][attribute] = []
                self.selected_Other_text[entry_key][question_key][attribute] = ""

            # Initialize toggle state for this attribute if needed
            if question_key not in self.toggle_states[entry_key]:
                self.toggle_states[entry_key][question_key] = {}
            if attribute not in self.toggle_states[entry_key][question_key]:
                self.toggle_states[entry_key][question_key][attribute] = False

            # Parse options format - handle both old list format and new dict format
            toggle_config = None
            mandatory_text_config = None
            if isinstance(options, dict):
                # New format with "options" and optionally "toggle_option" or "mandatory_text_field"
                display_options_base = options.get("options", [])
                toggle_config = options.get("toggle_option", None)
                # Check if toggle_option is enabled
                if toggle_config and not toggle_config.get("enabled", False):
                    toggle_config = None
                mandatory_text_config = options.get("mandatory_text_field", None)
                # Check if mandatory_text_field is enabled
                if mandatory_text_config and not mandatory_text_config.get(
                    "enabled", False
                ):
                    mandatory_text_config = None
            else:
                # Old list format
                display_options_base = options if isinstance(options, list) else []

            # Attribute label
            attr_label = QLabel(f"{attribute}:")
            attr_font = QFont()
            attr_font.setBold(True)
            attr_font.setPointSize(10)
            attr_label.setFont(attr_font)
            attr_label.setStyleSheet("color: #1a1a1a; padding: 5px 0px;")
            layout.addWidget(attr_label)

            # Check if this is a single-choice item or multiple selection item
            is_single_choice = "single-choice" in display_options_base
            is_multiple = "Multiple" in display_options_base

            # Remove "single-choice" and "Multiple" markers from options list for display
            display_options = [
                opt
                for opt in display_options_base
                if opt not in ("single-choice", "Multiple")
            ]

            display_options.append("Underspecified")
            # Add "Discussion needed" as an option for all attributes
            if "Discussion needed" not in display_options:
                display_options.append("Discussion needed")

            # Choose widget type based on number of options and markers
            if is_multiple:
                # Use special multiple selection widget
                self._create_multiple_selection_widget(
                    layout, entry_key, question_key, attribute, display_options
                )
            elif len(display_options) > 10:
                # Use dropdown for large number of options
                self._create_dropdown_widget(
                    layout, entry_key, question_key, attribute, display_options
                )
            elif is_single_choice:
                # Use radio buttons for single-choice items
                self._create_radio_buttons(
                    layout, entry_key, question_key, attribute, display_options
                )
            else:
                # Use checkboxes for multi-selection items
                self._create_checkboxes(
                    layout, entry_key, question_key, attribute, display_options
                )

            # Text input for "Other" option if it exists in original options
            if "Other" in display_options_base:
                text_label = QLabel("Please specify:")
                text_label.setStyleSheet(
                    "color: #555555; font-weight: bold; padding: 5px 0px;"
                )
                layout.addWidget(text_label)

                text_input_key = f"{entry_key}_{question_key}_{attribute}_Other"
                text_input = QLineEdit()
                text_input.setEnabled(False)
                text_input.setStyleSheet(
                    "QLineEdit { background-color: #f5f5f5; border: 1px solid #d0d0d0; border-radius: 3px; padding: 5px; color: #999999; }"
                )
                text_input.textChanged.connect(
                    lambda text, e=entry_key, q=question_key, a=attribute: self.on_Other_text_changed(
                        e, q, a, text
                    )
                )
                self.text_inputs[text_input_key] = text_input
                layout.addWidget(text_input)
                layout.addSpacing(5)

            # Create toggle button if toggle_option is configured
            if toggle_config:
                toggle_label = toggle_config.get("label", "Toggle")
                toggle_key = f"{entry_key}_{question_key}_{attribute}_toggle"
                toggle_button = QCheckBox(toggle_label)
                toggle_button.setStyleSheet(
                    "QCheckBox { color: #1976d2; font-weight: bold; padding: 5px 0px; }"
                )
                toggle_button.stateChanged.connect(
                    lambda state, e=entry_key, q=question_key, a=attribute: self.on_toggle_changed(
                        e, q, a, state
                    )
                )
                self.toggle_buttons[toggle_key] = toggle_button
                layout.addWidget(toggle_button)

                # Associated text input for the toggle (only enabled when toggle is checked)
                toggle_text_key = f"{entry_key}_{question_key}_{attribute}_toggle_text"
                toggle_text_input = QLineEdit()
                toggle_text_input.setEnabled(False)
                toggle_text_input.setPlaceholderText("Enter additional info...")
                toggle_text_input.setStyleSheet(
                    "QLineEdit { background-color: #f5f5f5; border: 1px solid #d0d0d0; border-radius: 3px; padding: 5px; color: #999999; }"
                )
                toggle_text_input.textChanged.connect(
                    lambda text, e=entry_key, q=question_key, a=attribute: self.on_toggle_text_changed(
                        e, q, a, text
                    )
                )
                self.toggle_line_edits[toggle_text_key] = toggle_text_input
                layout.addWidget(toggle_text_input)
                layout.addSpacing(5)

            # Create mandatory text field if configured
            if mandatory_text_config:
                mandatory_label = mandatory_text_config.get(
                    "label", "Additional information"
                )
                mandatory_placeholder = mandatory_text_config.get(
                    "placeholder", "Enter text..."
                )

                # Label
                mandatory_field_label = QLabel(f"{mandatory_label}:")
                mandatory_field_label.setStyleSheet(
                    "color: #555555; font-weight: bold; padding: 5px 0px;"
                )
                layout.addWidget(mandatory_field_label)

                # Text input
                mandatory_text_key = f"{entry_key}_{question_key}_{attribute}_mandatory"
                mandatory_text_input = QLineEdit()
                mandatory_text_input.setPlaceholderText(mandatory_placeholder)
                mandatory_text_input.setStyleSheet(
                    "QLineEdit { background-color: white; border: 1px solid #d0d0d0; border-radius: 3px; padding: 5px; color: #333333; }"
                )
                mandatory_text_input.textChanged.connect(
                    lambda text, e=entry_key, q=question_key, a=attribute: self.on_mandatory_text_changed(
                        e, q, a, text
                    )
                )
                self.mandatory_text_inputs[mandatory_text_key] = mandatory_text_input
                layout.addWidget(mandatory_text_input)
                layout.addSpacing(5)

            # Add a horizontal separator
            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setFrameShadow(QFrame.Shadow.Plain)
            separator.setLineWidth(1)
            separator.setStyleSheet("QFrame { border: 1px solid #e0e0e0; }")
            layout.addWidget(separator)

            # Spacing
            layout.addSpacing(15)

        # Restore UI state from loaded progress
        self._restore_ui_state(layout, entry_key, question_key)

        layout.addStretch()
        container.setLayout(layout)
        scroll.setWidget(container)

        return scroll

    def _restore_ui_state(
        self, layout: QVBoxLayout, entry_key: str, question_key: str
    ) -> None:
        """Restore the UI state based on loaded progress data.

        Args:
            layout (QVBoxLayout): The layout containing the UI widgets.
            entry_key (str): The BIB entry key for the paper.
            question_key (str): The research question identifier.
        """
        if (
            entry_key not in self.selected_values
            or question_key not in self.selected_values[entry_key]
        ):
            return

        for attribute in self.selected_values[entry_key][question_key]:
            selections = self.selected_values[entry_key][question_key][attribute]

            # Restore checkbox state
            for selection in selections:
                checkbox_key = f"{entry_key}_{question_key}_{attribute}_{selection}"
                if checkbox_key in self.checkboxes:
                    self.checkboxes[checkbox_key].setChecked(True)

            # Restore multiple selection state
            multiple_combo_key = f"{entry_key}_{question_key}_{attribute}_multiple"
            if multiple_combo_key in self.comboboxes:
                # Update the display of selected values
                self._update_multiple_selection_display(
                    entry_key, question_key, attribute
                )

            # Restore radio button state
            group_key = f"{entry_key}_{question_key}_{attribute}"
            if group_key in self.radio_button_groups and selections:
                # For radio buttons, only the last selection is active
                selection = selections[0]
                radio_key = f"{entry_key}_{question_key}_{attribute}_{selection}"
                if radio_key in self.radio_buttons:
                    self.radio_buttons[radio_key].setChecked(True)

            # Restore dropdown state
            combo_key = f"{entry_key}_{question_key}_{attribute}"
            if combo_key in self.comboboxes and selections:
                combo = self.comboboxes[combo_key]
                combo.setCurrentText(selections[0])

            # Restore "Other" text if present
            if "Other" in selections:
                text_input_key = f"{entry_key}_{question_key}_{attribute}_Other"
                if text_input_key in self.text_inputs:
                    self.text_inputs[text_input_key].setText(
                        self.selected_Other_text[entry_key][question_key][attribute]
                    )
                    self.text_inputs[text_input_key].setEnabled(True)

            # Restore "Discussion needed" text if present
            if "Discussion needed" in selections:
                discussion_key = f"{entry_key}_{question_key}_{attribute}_discussion"
                if discussion_key in self.discussion_text_inputs:
                    self._set_discussion_field_state(
                        entry_key, question_key, attribute, True, clear_text=False
                    )
                    if discussion_key in self.discussion_texts:
                        self.discussion_text_inputs[discussion_key].setText(
                            self.discussion_texts[discussion_key]
                        )

            # Restore toggle state and its text if present
            toggle_key = f"{entry_key}_{question_key}_{attribute}_toggle"
            toggle_text_key = f"{entry_key}_{question_key}_{attribute}_toggle_text"
            # Set toggle checked state
            if (
                entry_key in self.toggle_states
                and question_key in self.toggle_states[entry_key]
            ):
                enabled = self.toggle_states[entry_key][question_key].get(
                    attribute, False
                )
                if toggle_key in self.toggle_buttons:
                    self.toggle_buttons[toggle_key].blockSignals(True)
                    self.toggle_buttons[toggle_key].setChecked(enabled)
                    self.toggle_buttons[toggle_key].blockSignals(False)
                # Restore text
                if toggle_text_key in self.toggle_line_edits:
                    text_input = self.toggle_line_edits[toggle_text_key]
                    existing_text = (
                        self.toggle_texts.get(entry_key, {})
                        .get(question_key, {})
                        .get(attribute, "")
                    )
                    if existing_text:
                        text_input.setText(existing_text)
                        text_input.setEnabled(enabled)
                        if enabled:
                            text_input.setStyleSheet(
                                "QLineEdit { background-color: white; border: 1px solid #4CAF50; border-radius: 3px; padding: 5px; color: #333333; }"
                            )
                        else:
                            text_input.setStyleSheet(
                                "QLineEdit { background-color: #f5f5f5; border: 1px solid #d0d0d0; border-radius: 3px; padding: 5px; color: #999999; }"
                            )

            # Restore mandatory text if present
            mandatory_text_key = f"{entry_key}_{question_key}_{attribute}_mandatory"
            if mandatory_text_key in self.mandatory_text_inputs:
                existing_text = (
                    self.mandatory_texts.get(entry_key, {})
                    .get(question_key, {})
                    .get(attribute, "")
                )
                if existing_text:
                    self.mandatory_text_inputs[mandatory_text_key].setText(
                        existing_text
                    )

    def _create_checkboxes(
        self,
        layout: QVBoxLayout,
        entry_key: str,
        question_key: str,
        attribute: str,
        options: List[str],
    ) -> None:
        """Create checkbox widgets for multi-selection options.

        Args:
            layout (QVBoxLayout): Parent layout to add checkboxes to.
            entry_key (str): The BIB entry key for the paper.
            question_key (str): The research question identifier.
            attribute (str): The attribute name.
            options (List[str]): List of options for this attribute.
        """
        checkbox_layout = QHBoxLayout()
        checkbox_layout.setSpacing(15)
        for option in options:
            checkbox_key = f"{entry_key}_{question_key}_{attribute}_{option}"
            checkbox = QCheckBox(option)
            checkbox.setStyleSheet("QCheckBox { color: #333333; font-size: 10pt; }")
            checkbox.stateChanged.connect(
                lambda state, e=entry_key, q=question_key, a=attribute, o=option: self.on_checkbox_changed(
                    e, q, a, o, state
                )
            )
            self.checkboxes[checkbox_key] = checkbox
            checkbox_layout.addWidget(checkbox)

        layout.addLayout(checkbox_layout)
        layout.addSpacing(5)

        # Add text field for "Discussion needed" option if present
        if "Discussion needed" in options:
            self._add_discussion_field(layout, entry_key, question_key, attribute)

    def _create_multiple_selection_widget(
        self,
        layout: QVBoxLayout,
        entry_key: str,
        question_key: str,
        attribute: str,
        options: List[str],
    ) -> None:
        """Create a dropdown with add button for multiple sequential selections.

        Allows users to select one value at a time from a dropdown and add it to a list
        of selected values. Each selected value can be removed individually with a delete button.

        Args:
            layout (QVBoxLayout): Parent layout to add the widget to.
            entry_key (str): The BIB entry key for the paper.
            question_key (str): The research question identifier.
            attribute (str): The attribute name.
            options (List[str]): List of options for this attribute.
        """
        # Create main container for the multiple selection widget
        container = QWidget()
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)

        # Create dropdown and add button row
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)

        # Dropdown for selecting options
        combo_key = f"{entry_key}_{question_key}_{attribute}_multiple"
        combo = NoScrollComboBox()
        combo.setStyleSheet(
            "QComboBox { background-color: white; color: #333333; border: 1px solid #cccccc; border-radius: 3px; padding: 5px; min-height: 25px; font-size: 10pt; }"
            "QComboBox::drop-down { border: none; }"
        )
        combo.addItem("-- Select an option --")
        combo.addItems(options)
        self.comboboxes[combo_key] = combo
        input_layout.addWidget(combo)

        # Add button
        add_btn = QPushButton("+")
        add_btn.setMaximumWidth(40)
        add_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; border: none; border-radius: 3px; padding: 5px; font-size: 12pt; }"
            "QPushButton:hover { background-color: #45a049; }"
            "QPushButton:pressed { background-color: #3d8b40; }"
        )
        add_btn.clicked.connect(
            lambda checked=False, e=entry_key, q=question_key, a=attribute: self.on_multiple_add_value(
                e, q, a
            )
        )
        input_layout.addWidget(add_btn)

        container_layout.addLayout(input_layout)
        container_layout.addSpacing(10)

        # Container for selected values
        selected_container = QWidget()
        selected_container.setStyleSheet(
            "QWidget { background-color: #f9f9f9; border: 1px solid #e0e0e0; border-radius: 3px; padding: 8px; }"
        )
        selected_layout = QVBoxLayout()
        selected_layout.setContentsMargins(5, 5, 5, 5)
        selected_layout.setSpacing(5)

        # Store reference to the selected layout for dynamic updates
        selected_values_key = f"{entry_key}_{question_key}_{attribute}_selected_layout"
        self._selected_values_layouts = getattr(self, "_selected_values_layouts", {})
        self._selected_values_layouts[selected_values_key] = selected_layout

        selected_container.setLayout(selected_layout)
        container_layout.addWidget(selected_container)

        container.setLayout(container_layout)
        layout.addWidget(container)
        layout.addSpacing(5)

        # Add text field for "Discussion needed" option if present
        if "Discussion needed" in options:
            self._add_discussion_field(layout, entry_key, question_key, attribute)

    def on_multiple_add_value(
        self, entry_key: str, question_key: str, attribute: str
    ) -> None:
        """Handle adding a value to the multiple selection list.

        Args:
            entry_key (str): The BIB entry key for the paper.
            question_key (str): The research question identifier.
            attribute (str): The attribute name.
        """
        combo_key = f"{entry_key}_{question_key}_{attribute}_multiple"
        if combo_key not in self.comboboxes:
            return

        combo = self.comboboxes[combo_key]
        selected_text = combo.currentText()

        # Validate selection
        if not selected_text or selected_text == "-- Select an option --":
            QMessageBox.warning(
                None, "No Selection", "Please select an option from the dropdown."
            )
            return

        # Add to selected values
        if entry_key not in self.selected_values:
            self.selected_values[entry_key] = {}
        if question_key not in self.selected_values[entry_key]:
            self.selected_values[entry_key][question_key] = {}
        if attribute not in self.selected_values[entry_key][question_key]:
            self.selected_values[entry_key][question_key][attribute] = []

        # Check if already selected
        if selected_text in self.selected_values[entry_key][question_key][attribute]:
            QMessageBox.information(
                None,
                "Already Selected",
                f"'{selected_text}' is already in your selection.",
            )
            return

        # Add the value
        self.selected_values[entry_key][question_key][attribute].append(selected_text)

        # Enable discussion input if "Discussion needed" was selected
        if selected_text == "Discussion needed":
            self._set_discussion_field_state(
                entry_key, question_key, attribute, True, clear_text=False
            )

        # Update the UI to show selected values
        self._update_multiple_selection_display(entry_key, question_key, attribute)

        # Reset dropdown
        combo.setCurrentIndex(0)

    def _update_multiple_selection_display(
        self, entry_key: str, question_key: str, attribute: str
    ) -> None:
        """Update the display of selected values for a multiple selection widget.

        Args:
            entry_key (str): The BIB entry key for the paper.
            question_key (str): The research question identifier.
            attribute (str): The attribute name.
        """
        selected_values_key = f"{entry_key}_{question_key}_{attribute}_selected_layout"
        self._selected_values_layouts = getattr(self, "_selected_values_layouts", {})

        if selected_values_key not in self._selected_values_layouts:
            return

        selected_layout = self._selected_values_layouts[selected_values_key]

        # Clear existing items from layout - properly handle nested layouts
        while selected_layout.count() > 0:
            item = selected_layout.takeAt(0)
            if item is not None:
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    # Clear any nested layouts
                    self._clear_layout(item.layout())

        # Get current selections
        selections = (
            self.selected_values.get(entry_key, {})
            .get(question_key, {})
            .get(attribute, [])
        )

        if not selections:
            empty_label = QLabel("No values selected yet")
            empty_label.setStyleSheet("color: #999999; font-style: italic;")
            selected_layout.addWidget(empty_label)
        else:
            for value in selections:
                # Create a row for each selected value with a delete button
                value_layout = QHBoxLayout()
                value_layout.setContentsMargins(0, 0, 0, 0)
                value_layout.setSpacing(10)

                # Value label
                value_label = QLabel(value)
                value_label.setStyleSheet("color: #1a1a1a; font-weight: 500;")
                value_layout.addWidget(value_label)

                # Delete button - use partial function to properly capture value
                delete_btn = QPushButton("✕")
                delete_btn.setMaximumWidth(30)
                delete_btn.setStyleSheet(
                    "QPushButton { background-color: #f44336; color: white; font-weight: bold; border: none; border-radius: 3px; padding: 3px; font-size: 11pt; }"
                    "QPushButton:hover { background-color: #da190b; }"
                    "QPushButton:pressed { background-color: #ba0000; }"
                )
                delete_btn.clicked.connect(
                    partial(
                        self.on_multiple_remove_value,
                        entry_key,
                        question_key,
                        attribute,
                        value,
                    )
                )
                value_layout.addWidget(delete_btn)

                value_layout.addStretch()

                # Add to main layout
                selected_layout.addLayout(value_layout)

        selected_layout.addStretch()

    def _clear_layout(self, layout) -> None:
        """Recursively clear all widgets and nested layouts.

        Args:
            layout: The layout to clear.
        """
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def on_multiple_remove_value(
        self, entry_key: str, question_key: str, attribute: str, value: str
    ) -> None:
        """Handle removing a value from the multiple selection list.

        Args:
            entry_key (str): The BIB entry key for the paper.
            question_key (str): The research question identifier.
            attribute (str): The attribute name.
            value (str): The value to remove.
        """
        if (
            entry_key in self.selected_values
            and question_key in self.selected_values[entry_key]
            and attribute in self.selected_values[entry_key][question_key]
            and value in self.selected_values[entry_key][question_key][attribute]
        ):

            self.selected_values[entry_key][question_key][attribute].remove(value)

            if value == "Discussion needed":
                self._set_discussion_field_state(
                    entry_key, question_key, attribute, False, clear_text=True
                )

            self._update_multiple_selection_display(entry_key, question_key, attribute)

    def _create_radio_buttons(
        self,
        layout: QVBoxLayout,
        entry_key: str,
        question_key: str,
        attribute: str,
        options: List[str],
    ) -> None:
        """Create radio button widgets for single-choice options.

        Args:
            layout (QVBoxLayout): Parent layout to add radio buttons to.
            entry_key (str): The BIB entry key for the paper.
            question_key (str): The research question identifier.
            attribute (str): The attribute name.
            options (List[str]): List of options for this attribute.
        """
        radio_layout = QHBoxLayout()
        radio_layout.setSpacing(15)
        group_key = f"{entry_key}_{question_key}_{attribute}"
        group = QButtonGroup()
        self.radio_button_groups[group_key] = group

        for idx, option in enumerate(options):
            radio_key = f"{entry_key}_{question_key}_{attribute}_{option}"
            radio = QRadioButton(option)
            radio.setStyleSheet("QRadioButton { color: #333333; font-size: 10pt; }")
            radio.toggled.connect(
                lambda checked, e=entry_key, q=question_key, a=attribute, o=option: self.on_radio_button_changed(
                    e, q, a, o, checked
                )
            )
            self.radio_buttons[radio_key] = radio
            group.addButton(radio, idx)
            radio_layout.addWidget(radio)

        layout.addLayout(radio_layout)
        layout.addSpacing(5)

        # Add text field for "Discussion needed" option if present
        if "Discussion needed" in options:
            self._add_discussion_field(layout, entry_key, question_key, attribute)

    def _create_dropdown_widget(
        self,
        layout: QVBoxLayout,
        entry_key: str,
        question_key: str,
        attribute: str,
        options: List[str],
    ) -> None:
        """Create dropdown menu for attributes with many options.

        Args:
            layout (QVBoxLayout): Parent layout to add dropdown to.
            entry_key (str): The BIB entry key for the paper.
            question_key (str): The research question identifier.
            attribute (str): The attribute name.
            options (List[str]): List of options for this attribute.
        """
        combo_key = f"{entry_key}_{question_key}_{attribute}"
        combo = NoScrollComboBox()
        combo.setStyleSheet(
            "QComboBox { background-color: white; color: #333333; border: 1px solid #cccccc; border-radius: 3px; padding: 5px; min-height: 25px; font-size: 10pt; }"
            "QComboBox::drop-down { border: none; }"
        )
        combo.addItem("-- Select an option --")
        combo.addItems(options)
        combo.currentTextChanged.connect(
            lambda text, e=entry_key, q=question_key, a=attribute: self.on_dropdown_changed(
                e, q, a, text
            )
        )
        self.comboboxes[combo_key] = combo
        layout.addWidget(combo)
        layout.addSpacing(5)

        # Add text field for "Discussion needed" option
        if "Discussion needed" in options:
            self._add_discussion_field(layout, entry_key, question_key, attribute)

    def _add_discussion_field(
        self, layout: QVBoxLayout, entry_key: str, question_key: str, attribute: str
    ) -> None:
        """Add a prominently styled discussion text field.

        Args:
            layout (QVBoxLayout): Parent layout to add the field to.
            entry_key (str): The BIB entry key for the paper.
            question_key (str): The research question identifier.
            attribute (str): The attribute name.
        """
        # Create a container frame for discussion field
        discussion_frame = QFrame()
        discussion_frame.setStyleSheet(
            "QFrame { background-color: #e8e8e8; border: 2px solid #999999; border-radius: 5px; padding: 10px; }"
        )
        discussion_layout = QVBoxLayout()

        # Label with enhanced styling
        discussion_label = QLabel("📝 Discussion needed - please describe:")
        label_font = QFont()
        label_font.setBold(True)
        label_font.setPointSize(9)
        discussion_label.setFont(label_font)
        discussion_label.setStyleSheet("color: #555555;")
        discussion_layout.addWidget(discussion_label)

        # Text input with enhanced styling
        discussion_key = f"{entry_key}_{question_key}_{attribute}_discussion"
        discussion_input = QLineEdit()
        discussion_input.setEnabled(False)
        discussion_input.setMinimumHeight(35)  # Make it taller
        discussion_input.setPlaceholderText("Enter detailed discussion notes here...")
        discussion_input.setStyleSheet(
            "QLineEdit { background-color: #f5f5f5; border: 1px solid #d0d0d0; border-radius: 3px; padding: 5px; font-size: 10pt; color: #999999; }"
        )
        discussion_input.textChanged.connect(
            lambda text, e=entry_key, q=question_key, a=attribute, k=discussion_key: self.on_discussion_text_changed(
                e, q, a, k, text
            )
        )
        self.discussion_text_inputs[discussion_key] = discussion_input
        self.discussion_containers[discussion_key] = discussion_frame
        discussion_layout.addWidget(discussion_input)

        discussion_frame.setLayout(discussion_layout)
        discussion_frame.setVisible(False)
        layout.addSpacing(10)  # Add spacing before discussion field
        layout.addWidget(discussion_frame)
        layout.addSpacing(10)  # Add spacing after discussion field

    def _set_discussion_field_state(
        self,
        entry_key: str,
        question_key: str,
        attribute: str,
        visible: bool,
        clear_text: bool,
    ) -> None:
        """Show/hide and enable/disable the discussion UI for one attribute."""
        discussion_key = f"{entry_key}_{question_key}_{attribute}_discussion"

        if discussion_key in self.discussion_containers:
            self.discussion_containers[discussion_key].setVisible(visible)

        if discussion_key not in self.discussion_text_inputs:
            return

        discussion_input = self.discussion_text_inputs[discussion_key]
        discussion_input.setEnabled(visible)

        if visible:
            discussion_input.setStyleSheet(
                "QLineEdit { background-color: white; border: 1px solid #ff9800; border-radius: 3px; padding: 5px; font-size: 10pt; color: #333333; }"
            )
        else:
            discussion_input.setStyleSheet(
                "QLineEdit { background-color: #f5f5f5; border: 1px solid #d0d0d0; border-radius: 3px; padding: 5px; font-size: 10pt; color: #999999; }"
            )
            if clear_text:
                discussion_input.clear()
                self.discussion_texts[discussion_key] = ""

    def on_checkbox_changed(
        self, entry_key: str, question_key: str, attribute: str, option: str, state: int
    ) -> None:
        """Handle checkbox state changes.

        Args:
            entry_key (str): The BIB entry key for the paper.
            question_key (str): The research question identifier.
            attribute (str): The attribute name.
            option (str): The option name.
            state (int): The new state of the checkbox (CheckState).
        """
        # Update selected values (state 2 = checked, 0 = unchecked)
        if state == 2:
            if option not in self.selected_values[entry_key][question_key][attribute]:
                self.selected_values[entry_key][question_key][attribute].append(option)
        else:
            if option in self.selected_values[entry_key][question_key][attribute]:
                self.selected_values[entry_key][question_key][attribute].remove(option)

        # Enable/disable text input for "Other" option
        if option == "Other":
            text_input_key = f"{entry_key}_{question_key}_{attribute}_Other"
            if text_input_key in self.text_inputs:
                if state == 2:  # checked
                    self.text_inputs[text_input_key].setEnabled(True)
                    self.text_inputs[text_input_key].setStyleSheet(
                        "QLineEdit { background-color: white; border: 1px solid #4CAF50; border-radius: 3px; padding: 5px; color: #333333; }"
                    )
                else:
                    self.text_inputs[text_input_key].setEnabled(False)
                    self.text_inputs[text_input_key].setStyleSheet(
                        "QLineEdit { background-color: #f5f5f5; border: 1px solid #d0d0d0; border-radius: 3px; padding: 5px; color: #999999; }"
                    )
                    self.text_inputs[text_input_key].clear()
                    self.selected_Other_text[entry_key][question_key][attribute] = ""

        # Enable/disable text input for "Discussion needed" option
        if option == "Discussion needed":
            self._set_discussion_field_state(
                entry_key,
                question_key,
                attribute,
                state == 2,
                clear_text=state != 2,
            )

    def on_radio_button_changed(
        self,
        entry_key: str,
        question_key: str,
        attribute: str,
        option: str,
        checked: bool,
    ) -> None:
        """Handle radio button state changes.

        Args:
            entry_key (str): The BIB entry key for the paper.
            question_key (str): The research question identifier.
            attribute (str): The attribute name.
            option (str): The option name.
            checked (bool): Whether the radio button is checked.
        """
        if checked:
            # For single-choice, replace the entire selection list with just this option
            self.selected_values[entry_key][question_key][attribute] = [option]

            # Enable/disable text input for "Other" option
            text_input_key = f"{entry_key}_{question_key}_{attribute}_Other"
            if text_input_key in self.text_inputs:
                if option == "Other":
                    self.text_inputs[text_input_key].setEnabled(True)
                    self.text_inputs[text_input_key].setStyleSheet(
                        "QLineEdit { background-color: white; border: 1px solid #4CAF50; border-radius: 3px; padding: 5px; color: #333333; }"
                    )
                else:
                    self.text_inputs[text_input_key].setEnabled(False)
                    self.text_inputs[text_input_key].setStyleSheet(
                        "QLineEdit { background-color: #f5f5f5; border: 1px solid #d0d0d0; border-radius: 3px; padding: 5px; color: #999999; }"
                    )
                    self.text_inputs[text_input_key].clear()
                    self.selected_Other_text[entry_key][question_key][attribute] = ""

            # Enable/disable discussion text field if this is "Discussion needed"
            discussion_key = f"{entry_key}_{question_key}_{attribute}_discussion"
            if discussion_key in self.discussion_text_inputs:
                self._set_discussion_field_state(
                    entry_key,
                    question_key,
                    attribute,
                    option == "Discussion needed",
                    clear_text=option != "Discussion needed",
                )

    def on_dropdown_changed(
        self, entry_key: str, question_key: str, attribute: str, text: str
    ) -> None:
        """Handle dropdown menu selection changes.

        Args:
            entry_key (str): The BIB entry key for the paper.
            question_key (str): The research question identifier.
            attribute (str): The attribute name.
            text (str): The selected option text.
        """
        if text and text != "-- Select an option --":
            # Replace selection with the chosen option
            self.selected_values[entry_key][question_key][attribute] = [text]

            # Enable/disable text input for "Other" option
            text_input_key = f"{entry_key}_{question_key}_{attribute}_Other"
            if text_input_key in self.text_inputs:
                if text == "Other":
                    self.text_inputs[text_input_key].setEnabled(True)
                    self.text_inputs[text_input_key].setStyleSheet(
                        "QLineEdit { background-color: white; border: 1px solid #4CAF50; border-radius: 3px; padding: 5px; color: #333333; }"
                    )
                else:
                    self.text_inputs[text_input_key].setEnabled(False)
                    self.text_inputs[text_input_key].setStyleSheet(
                        "QLineEdit { background-color: #f5f5f5; border: 1px solid #d0d0d0; border-radius: 3px; padding: 5px; color: #999999; }"
                    )
                    self.text_inputs[text_input_key].clear()
                    self.selected_Other_text[entry_key][question_key][attribute] = ""

            # Enable/disable discussion text field if this is "Discussion needed"
            discussion_key = f"{entry_key}_{question_key}_{attribute}_discussion"
            if discussion_key in self.discussion_text_inputs:
                self._set_discussion_field_state(
                    entry_key,
                    question_key,
                    attribute,
                    text == "Discussion needed",
                    clear_text=text != "Discussion needed",
                )
        else:
            # Clear selection if placeholder is selected
            self.selected_values[entry_key][question_key][attribute] = []

            # Disable text input for "Other" option
            text_input_key = f"{entry_key}_{question_key}_{attribute}_Other"
            if text_input_key in self.text_inputs:
                self.text_inputs[text_input_key].setEnabled(False)
                self.text_inputs[text_input_key].clear()
                self.selected_Other_text[entry_key][question_key][attribute] = ""

            # Disable discussion text field
            discussion_key = f"{entry_key}_{question_key}_{attribute}_discussion"
            if discussion_key in self.discussion_text_inputs:
                self._set_discussion_field_state(
                    entry_key, question_key, attribute, False, clear_text=True
                )

    def on_discussion_text_changed(
        self,
        entry_key: str,
        question_key: str,
        attribute: str,
        discussion_key: str,
        text: str,
    ) -> None:
        """Handle discussion text input changes.

        Args:
            entry_key (str): The BIB entry key for the paper.
            question_key (str): The research question identifier.
            attribute (str): The attribute name.
            discussion_key (str): The discussion field key.
            text (str): The new text value.
        """
        self.discussion_texts[discussion_key] = text

    def on_Other_text_changed(
        self, entry_key: str, question_key: str, attribute: str, text: str
    ) -> None:
        """Handle text input changes for "Other" fields.

        Args:
            entry_key (str): The BIB entry key for the paper.
            question_key (str): The research question identifier.
            attribute (str): The attribute name.
            text (str): The new text value.
        """
        self.selected_Other_text[entry_key][question_key][attribute] = text

    def on_toggle_changed(
        self, entry_key: str, question_key: str, attribute: str, state: int
    ) -> None:
        """Handle toggle button state changes.

        Args:
            entry_key (str): The BIB entry key for the paper.
            question_key (str): The research question identifier.
            attribute (str): The attribute name.
            state (int): The new state of the checkbox (CheckState).
        """
        is_checked = state == 2  # CheckState.Checked == 2
        self.toggle_states[entry_key][question_key][attribute] = is_checked

        # Enable/disable associated text input
        toggle_text_key = f"{entry_key}_{question_key}_{attribute}_toggle_text"
        if toggle_text_key in self.toggle_line_edits:
            text_input = self.toggle_line_edits[toggle_text_key]
            if is_checked:
                text_input.setEnabled(True)
                text_input.setStyleSheet(
                    "QLineEdit { background-color: white; border: 1px solid #4CAF50; border-radius: 3px; padding: 5px; color: #333333; }"
                )
                # restore existing text if present
                existing = (
                    self.toggle_texts.get(entry_key, {})
                    .get(question_key, {})
                    .get(attribute, "")
                )
                if existing:
                    text_input.blockSignals(True)
                    text_input.setText(existing)
                    text_input.blockSignals(False)
            else:
                text_input.setEnabled(False)
                text_input.setStyleSheet(
                    "QLineEdit { background-color: #f5f5f5; border: 1px solid #d0d0d0; border-radius: 3px; padding: 5px; color: #999999; }"
                )
                text_input.clear()
                # clear stored text
                if (
                    entry_key in self.toggle_texts
                    and question_key in self.toggle_texts[entry_key]
                ):
                    self.toggle_texts[entry_key][question_key][attribute] = ""

    def on_toggle_text_changed(
        self, entry_key: str, question_key: str, attribute: str, text: str
    ) -> None:
        """Handle changes to the toggle-associated text input."""
        if entry_key not in self.toggle_texts:
            self.toggle_texts[entry_key] = {}
        if question_key not in self.toggle_texts[entry_key]:
            self.toggle_texts[entry_key][question_key] = {}
        self.toggle_texts[entry_key][question_key][attribute] = text

    def on_mandatory_text_changed(
        self, entry_key: str, question_key: str, attribute: str, text: str
    ) -> None:
        """Handle changes to mandatory text input."""
        if entry_key not in self.mandatory_texts:
            self.mandatory_texts[entry_key] = {}
        if question_key not in self.mandatory_texts[entry_key]:
            self.mandatory_texts[entry_key][question_key] = {}
        self.mandatory_texts[entry_key][question_key][attribute] = text

    def on_exclude_changed(self, state: int) -> None:
        """Handle the exclude checkbox state change.

        Args:
            state (int): The new state of the checkbox (CheckState).
        """
        entry_key = self.paper_keys[self.current_paper_index]
        is_checked = state == 2  # CheckState.Checked == 2
        self.excluded_papers[entry_key] = is_checked

        # Enable/disable question tabs based on exclusion status
        if self.question_tabs is not None:
            self.question_tabs.setEnabled(not is_checked)

        # Show/hide reason text field based on exclusion status
        if self.exclude_reason_input is not None:
            self.exclude_reason_input.setVisible(is_checked)
            self.exclude_reason_label.setVisible(is_checked)

            if is_checked:
                # Load previous reason if available
                previous_reason = self.excluded_reasons.get(entry_key, "")
                self.exclude_reason_input.blockSignals(True)
                self.exclude_reason_input.setText(previous_reason)
                self.exclude_reason_input.blockSignals(False)
                self.exclude_reason_input.setEnabled(True)
                self.exclude_reason_input.setStyleSheet(
                    "QLineEdit { background-color: white; color: #333333; border: 1px solid #d9534f; border-radius: 3px; padding: 5px; margin-left: 20px; }"
                )
            else:
                self.exclude_reason_input.setEnabled(False)
                self.exclude_reason_input.setStyleSheet(
                    "QLineEdit { background-color: #f9f9f9; color: #999999; border: 1px solid #d0d0d0; border-radius: 3px; padding: 5px; margin-left: 20px; }"
                )

        # Show message if excluding
        if is_checked:
            QMessageBox.information(
                self,
                "Paper Excluded",
                "This paper will be marked as excluded from the full text review. Please provide a reason for exclusion in the text field below. You can click 'Finish' to proceed to the next paper.",
            )

    def on_exclude_reason_changed(self, text: str) -> None:
        """Handle changes to the exclusion reason text field.

        Args:
            text (str): The new text value.
        """
        entry_key = self.paper_keys[self.current_paper_index]
        self.excluded_reasons[entry_key] = text

    def export_data(self, show_box: bool = True) -> None:
        """Export selected values to a JSON file and show success message."""
        self._perform_export()
        if show_box:
            QMessageBox.information(self, "Success", "Data exported to export.json")

    def _perform_export(self) -> bool:
        """Perform the actual export to JSON file without showing messages.

        Preserves data from previously exported papers that aren't currently loaded in memory,
        and updates papers that have been re-edited.

        Returns:
            bool: True if export was successful, False Otherwise.
        """
        try:
            output = {}

            # First, load existing export data to preserve papers not in current session
            export_file = "export.json"
            if os.path.exists(export_file):
                try:
                    with open(export_file, "r") as f:
                        existing_export = json.load(f)
                        output.update(existing_export)
                except (json.JSONDecodeError, IOError):
                    pass  # If we can't read, just start fresh

            # Now update/add papers from current session (this handles re-edited papers)
            for entry_key in self.selected_values:
                entry_data = self.papers.get(entry_key, {})
                output[entry_key] = {
                    "paper": {
                        "title": entry_data.get("title", "Unknown"),
                        "authors": entry_data.get("authors", "Unknown"),
                        "year": entry_data.get("year", "Unknown"),
                    },
                    "excluded_from_full_text_review": self.excluded_papers.get(
                        entry_key, False
                    ),
                    "exclusion_reason": self.excluded_reasons.get(entry_key, ""),
                    "responses": {},
                }

                for question_key in self.selected_values[entry_key]:
                    output[entry_key]["responses"][question_key] = {}
                    for attribute in self.selected_values[entry_key][question_key]:
                        selections = self.selected_values[entry_key][question_key][
                            attribute
                        ].copy()

                        # Handle "Other" option
                        if (
                            "Other" in selections
                            and self.selected_Other_text[entry_key][question_key][
                                attribute
                            ]
                        ):
                            selections.remove("Other")
                            selections.append(
                                f"Other: {self.selected_Other_text[entry_key][question_key][attribute]}"
                            )

                        # Handle "Discussion needed" option
                        if "Discussion needed" in selections:
                            discussion_key = (
                                f"{entry_key}_{question_key}_{attribute}_discussion"
                            )
                            discussion_text = self.discussion_texts.get(discussion_key)
                            if (
                                discussion_text is None or discussion_text == ""
                            ) and discussion_key in self.discussion_text_inputs:
                                discussion_text = self.discussion_text_inputs[
                                    discussion_key
                                ].text()
                            if discussion_text:
                                selections.remove("Discussion needed")
                                selections.append(
                                    f"Discussion needed: {discussion_text}"
                                )

                        output[entry_key]["responses"][question_key][
                            attribute
                        ] = selections

                # Export toggle states (only include toggles that are enabled)
                toggle_out = {}
                if entry_key in self.toggle_states:
                    for qk, attrs in self.toggle_states[entry_key].items():
                        for attr, enabled in attrs.items():
                            if enabled:
                                if qk not in toggle_out:
                                    toggle_out[qk] = {}
                                text = (
                                    self.toggle_texts.get(entry_key, {})
                                    .get(qk, {})
                                    .get(attr, "")
                                )
                                toggle_out[qk][attr] = {"enabled": True, "text": text}

                if toggle_out:
                    output[entry_key]["toggle_states"] = toggle_out

                # Export mandatory texts (only include non-empty mandatory texts)
                mandatory_out = {}
                if entry_key in self.mandatory_texts:
                    for qk, attrs in self.mandatory_texts[entry_key].items():
                        for attr, text in attrs.items():
                            if text.strip():  # Only include if text is provided
                                if qk not in mandatory_out:
                                    mandatory_out[qk] = {}
                                mandatory_out[qk][attr] = text

                if mandatory_out:
                    output[entry_key]["mandatory_texts"] = mandatory_out

            with open("export.json", "w") as f:
                json.dump(output, f, indent=2)

            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error exporting data: {str(e)}")
            return False

    def clear_all(self) -> None:
        """Clear all selections and reset the interface."""
        for entry_key in self.selected_values:
            for question_key in self.selected_values[entry_key]:
                for attribute in self.selected_values[entry_key][question_key]:
                    self.selected_values[entry_key][question_key][attribute] = []
                    self.selected_Other_text[entry_key][question_key][attribute] = ""

        for checkbox in self.checkboxes.values():
            checkbox.setChecked(False)

        for radio in self.radio_buttons.values():
            radio.setChecked(False)

        for combo in self.comboboxes.values():
            combo.setCurrentIndex(0)

        for text_input in self.text_inputs.values():
            text_input.clear()
            text_input.setEnabled(False)

        for discussion_input in self.discussion_text_inputs.values():
            discussion_input.clear()
            discussion_input.setEnabled(False)

        for discussion_container in self.discussion_containers.values():
            discussion_container.setVisible(False)

        self.discussion_texts.clear()

        # Clear toggle buttons and their texts
        for toggle in self.toggle_buttons.values():
            toggle.setChecked(False)

        for t_edit in self.toggle_line_edits.values():
            t_edit.clear()
            t_edit.setEnabled(False)

        # Clear stored toggle state/text structures
        for entry_key in self.toggle_states:
            for qk in self.toggle_states[entry_key]:
                for attr in list(self.toggle_states[entry_key][qk].keys()):
                    self.toggle_states[entry_key][qk][attr] = False

        for entry_key in self.toggle_texts:
            for qk in self.toggle_texts[entry_key]:
                for attr in list(self.toggle_texts[entry_key][qk].keys()):
                    self.toggle_texts[entry_key][qk][attr] = ""

        # Clear mandatory text inputs and their texts
        for m_input in self.mandatory_text_inputs.values():
            m_input.clear()

        # Clear stored mandatory text structures
        for entry_key in self.mandatory_texts:
            for qk in self.mandatory_texts[entry_key]:
                for attr in list(self.mandatory_texts[entry_key][qk].keys()):
                    self.mandatory_texts[entry_key][qk][attr] = ""

        QMessageBox.information(self, "Cleared", "All selections cleared")


def main() -> None:
    """Main entry point for the application.

    Valid user values: Moritz, Andreas, Stina, Shu, Amar, Tobias
    """
    # Define the user performing the data extraction
    # Valid values: Moritz, Andreas, Stina, Shu, Amar, Tobias
    user: str = "Moritz"

    app = QApplication(sys.argv)
    window = DataExtractionGUI(user=user)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
