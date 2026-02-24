# GUI Data Extraction Tool

A PyQt6-based GUI application for extracting and analyzing metadata from research papers using BibTeX citations and structured research question data.

## Features

- **Paper-Based Workflow**: Process papers one at a time with automatic progression to unprocessed papers
- **Multi-Select Interface**: Answer structured research questions with multiple-choice options for each paper
- **Citation Management**: Reads BibTeX files with automatic extraction of title, authors, year, and DOI
- **Flexible Data Input**: Support for custom text input when "Other" options are selected
- **Bibliography Display**: View all loaded citation entries in an organized list
- **Data Export**:
  - **Export**: Creates human-readable `export.json` file
  - **Clear All**: Resets all selections for the current paper
  - **Exit**: Closes the application

## Requirements

- Python 3.7+
- PyQt5 >= 5.15

## Installation

1. Install dependencies:
```bash
pip install PyQt5
```

2. Ensure you have the required data files in the application directory:
   - `data-items.json`: Contains research question definitions with attributes and options
   - `papers.bib`: Contains BibTeX citations for papers to be analyzed

## Usage

Run the application with:
```bash
python3 data-extraction-gui.py
```

Make sure that you have the correct user specified in the main function of the script!!!

### Workflow

1. **Load Paper**: The application automatically loads the first unprocessed paper from the CSV file
2. **Answer Questions**: Navigate through the research questions and select appropriate options
3. **Specify Custom Data**: If "Other" is available and selected, enter custom text in the text field
4. **Save Progress**: Click "Save" to export your responses to `export.json`
5. **Export Summary**: Click "Export" to create a human-readable `export.txt` summary
6. **Next Paper**: After completing a paper, click the "Next Paper" button to proceed to the next unprocessed paper

## Data Format

### Input Files

- **data-items.json**: Structured questions with multiple choice options
- **review_set_with_assignees(in).csv**: CSV with papers assigned to the authors

### Output Files

- **export.json**: Structured JSON file containing paper metadata and user responses

## Sanity Checks

The application includes validation rules to ensure data consistency. These rules are defined in `sanity_checks.json` and can be run against exported paper data.

### Running Sanity Checks

To validate an exported paper entry:
```bash
python3 sanity_checks.py <exported_paper_json> [config.json]
```

Example:
```bash
python3 sanity_checks.py export.json sanity_checks.json
```

### Validation Rules

The sanity checks validate conditional dependencies between research questions:

- **Code Availability & Explainability**: If code is unavailable, explainability must be "Pseudo-code"; if available, it must not be
- **Evaluation Type**: If explainability is marked as "Evaluated", an evaluation type must be specified
- **Adaptation**: If no adaptation is present, the goal of adaptation must be "Not applicable"
- **Deployment & Simulation**: Different deployment types (real robot, robot simulation, other simulation) have specific requirements for simulation environment specifications
- **Location Requirements**: Simulation deployments cannot be tested "In the wild", and if use case is "Not applicable", location must also be "Not applicable"

The validator is lightweight, dependency-free, and provides clear violation messages when rules are not met.

## Troubleshooting

- Check that JSON file is properly formatted before loading
- Unprocessed papers are identified based on absence in `export.json`
