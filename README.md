# Python RoRo 5G

Simulation and analysis framework for RoRo (roll-on/roll-off) terminal and ship operations.

## What this project does

The project models loading/unloading processes for cargo in terminal/ship layouts, evaluates decision policies, and generates result datasets and publication-style figures.

Core capabilities:
- Generate stochastic operation instances (layouts, cargo, travel/process times).
- Simulate realizations of decisions/events across epochs.
- Learn and test policy trees under different information levels.
- Aggregate results in Excel files and create visual analyses.

## Project structure

- `run.py`: Main entry point to execute configured compositions in parallel.
- `composition.py`: Learning/testing orchestration for policy trees and experiment runs.
- `model.py`: Core simulation domain model (trees, decisions, events, realization solver).
- `instance_generator.py`: Creation of terminal/ship instances, areas, positions, cargo, and tasks.
- `figures_paper.py`: Figure and table generation scripts for paper/report outputs.
- `playground.py`: Small sandbox for quick local experiments.
- `requirements.txt`: Python dependencies for pip-based setup.
- `results/`: Runtime learning/testing outputs.
- `results_paper/`: Processed outputs and figure artifacts for paper/reporting.

## Installation

1. Create and activate a virtual environment (recommended).
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## How to run

1. Prepare or update composition settings in `compositions.xlsx` (`runs` sheet).
2. Start the main run script. 

Info: You may want to use the compositions_input_example.xlsx file to see how it works for a small-scale example. 

## Outputs

- Learning/testing Excel files in `results/learning/` and `results/testing/`.
- Aggregated analysis tables and interactive HTML figures under `results_paper/`.

## Notes

- Excel I/O is used heavily (`pandas` + `openpyxl`).
- Plot generation uses Plotly and writes HTML (and optionally PDF depending on local setup).
