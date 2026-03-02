# Quick Start Guide

## Installation

1. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application:**

   ```bash
   python data-extraction-gui.py
   ```

3. **Run all tests:**

   ```bash
   pytest
   ```

## Key Features

### 📋 Session Recovery

- **Auto-Resume:** If you close the app without finishing a paper, the tool will resume from that paper next time
- **Progress Restoration:** All your previous selections are automatically restored
- **Files:** Uses `.session.json` to track the current work state

### 💬 Discussion Field

- **Prominent Styling:** Highlighted in yellow with a warning icon for easy visibility
- **Required When Selected:** If you select "Discussion needed", you must provide discussion text
- **Large Input:** 40px tall input field for comfortable typing

### 📤 Export

- **Auto-Export on Exit:** Data is automatically exported to `export.json` when you click "Exit"
- **Manual Export:** Use the "Export" button to save at any time
- **Incremental:** Only new/modified papers are saved

## Workflow

1. **Start:** `python data-extraction-gui.py`
2. **Work:** Fill in the form for the current paper
3. **Save Progress:** Click "Export" to save your work
4. **Next Paper:** Click "Finish" to move to the next paper
5. **Exit:** Click "Exit" to close (data is auto-exported)

## Important Notes

- **Discussion Field:** Only shown when "Discussion needed" is selected
- **Session File:** `.session.json` is created automatically and tracks your current work
- **Export File:** `export.json` contains all completed and in-progress papers
- **Validation:** You cannot finish a paper without filling all required fields

## Troubleshooting

**App won't start:**

- Ensure PyQt6 is installed: `pip install -r requirements.txt`
- Check Python version: Python 3.7+

**Lost my progress:**

- Check for `.session.json` file - it contains your current state
- Check `export.json` - it contains saved data

**Discussion field not showing:**

- Select the "Discussion needed" checkbox/radio button for that field
- The field should appear with a yellow highlight

## Files Overview

- `data-extraction-gui.py` - Main application (PyQt6 based)
- `data-items.json` - Research question definitions
- `review_set_with_assignees(in).csv` - Paper data
- `export.json` - Exported responses (auto-created)
- `.session.json` - Session state (auto-created)
- `requirements.txt` - Python dependencies
