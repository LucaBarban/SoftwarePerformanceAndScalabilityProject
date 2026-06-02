# Software Performance and Scalability Project

This repository contains the code for the Software Performance and Scalability Project.

> ⚠️ **Prerequisite:** This project requires **Python 3.13** to be installed on your system to work correctly

---

## Getting Started
Follow these steps to set up your local environment and prepare to run the simulations.

### 1. Environment Setup
Create and activate a virtual environment to cleanly isolate your project dependencies:

```bash
# Create the virtual environment
python3.13 -m venv .venv

# Activate the environment
# On Linux/macOS:
source .venv/bin/activate

# On Windows (Command Prompt):
.venv\Scripts\activate

# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
```


### 2. Install Dependencies
Install the required libraries using the `requirements.txt` file:
```bash
pip install -r requirements.txt
```

## Usage
### Running Simulations
To execute the simulations, run the main entry point:
```bash
python3.13 main.py
```

### Visualizing Results
Once a simulation run completes, its raw data results are saved directly into the `simulations/` directory. To process this data and visualize the plots, pass the target file to the `plotter.py` file:
```bash
python3.13 plotter.py simulations/sim_name.txt
```