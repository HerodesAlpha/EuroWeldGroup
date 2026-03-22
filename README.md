# EuroWeldGroup

Python utilities for checking **fillet weld groups** with the **directional method** in **EN 1993-1-8**: line welds in the **y–z** plane, global forces **Fx, Fy, Fz** with separate points of action **Pfx, Pfy, Pfz**, and resistance using **f<sub>u</sub> / (β<sub>w</sub> γ<sub>M2</sub>)**.

This is a calculation aid. **Verify assumptions, detailing rules, and results** against your national annex, project specification, and responsible engineer.

## Features

- Weld geometry as **`WeldSegment`** polylines in the plane **x = 0** (coordinates **y, z** in mm).
- Load cases with **Fx, Fy, Fz** (N) and **Pfx, Pfy, Pfz** as **(x, y, z)** in mm.
- Resultant moments from **r × F** for each component; direct forces plus **Mx, My, Mz** on the group.
- Effective length **l<sub>eff</sub> = l<sub>gross</sub> − 2a** (optional), throat area, line centroid and second moments, torsion about the weld centroid axis.
- Stress components **σ<sub>⊥</sub>, τ<sub>⊥</sub>, τ<sub>∥</sub>**, von Mises-style equivalent **σ<sub>eq</sub>**, utilization per segment.
- Multiple load cases, governing case, and **required weld size** search over load cases.
- Optional **matplotlib** figure: three orthographic views (XY, XZ, YZ) of welds and force vectors.

## Requirements

- **Python 3.10+** (tested with 3.14).
- **matplotlib** only if you use plotting (see `requirements.txt`).

## Setup

```text
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On Windows, if `python` is not on `PATH`, use `py -3 -m venv .venv` and `.venv\Scripts\pip install -r requirements.txt`.

This workspace includes **`.vscode/settings.json`** so Cursor/VS Code uses `.venv` as the default interpreter.

## Run the example

```text
python main.py
```

This prints a single-loadcase report, a multi-loadcase summary, required weld size output, and saves **`weld_loads_three_views.png`** next to `main.py` (no interactive plot window).

## Project layout

| File | Role |
|------|------|
| `main.py` | Models, EN 1993-1-8 directional checks, CLI example |
| `weld_plotting.py` | `plot_welds_and_loads_three_planes()` — save or return figure |
| `requirements.txt` | `matplotlib` |

## Units

| Quantity | Unit |
|----------|------|
| Forces | N |
| Moments | Nmm |
| Lengths | mm |
| Stresses | MPa (N/mm²) |

## Coordinate system

- Weld segments lie in **x = 0**; segment endpoints are **(y, z)**.
- **x** is normal to the weld plane; **y** and **z** are in-plane.
- Each force acts at its own point **(x, y, z)** in the same global system.

## API overview (import from `main`)

- **`weld_group_check_from_component_points(...)`** — single load case with **Pfx, Pfy, Pfz**.
- **`check_multiple_loadcases(segments, loadcases, ...)`** — list of dicts with keys **`name`, `Fx`, `Fy`, `Fz`, `Pfx`, `Pfy`, `Pfz`**.
- **`required_weld_size_for_multiple_loadcases(...)`** — required throat / leg over all cases.
- **`print_weld_group_result`**, **`print_multiple_loadcases_result`** — text output helpers.

Steel grades **S235, S275, S355, S420, S460** map to **β<sub>w</sub>** via **`BETA_W_DEFAULTS`**; you can pass **`beta_w`** explicitly instead.

## Plotting

```python
from pathlib import Path
from weld_plotting import plot_welds_and_loads_three_planes

plot_welds_and_loads_three_planes(segments, loadcase_dict, save_path=Path("out.png"), dpi=150)
```

Optional arguments include **`force_scale`** (mm/N), **`show_segment_labels`**, and **`title`**. With **`save_path`**, the figure is saved and closed.
