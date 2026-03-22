"""
PDF report: characteristic (specified) inputs, EN 1993-1-8 check results,
coordinate-system sketch, and orthographic weld + load plots (governing case).
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from main import MultiLoadCaseResult, WeldGroupResult, WeldSegment, check_multiple_loadcases
from weld_plotting import plot_welds_and_loads_three_planes

# ISO 216 A4 portrait: 210 mm × 297 mm (exact figure size for PDF pages)
A4_W_IN = 210.0 / 25.4
A4_H_IN = 297.0 / 25.4
A4_FIGSIZE: Tuple[float, float] = (A4_W_IN, A4_H_IN)


def _save_pdf_page_a4(pdf: Any, fig: Any, *, dpi: Optional[float] = None) -> None:
    """Write one PDF page at full A4 size (no tight crop — avoids variable page formats)."""
    kw: Dict[str, Any] = {}
    if dpi is not None:
        kw["dpi"] = dpi
    pdf.savefig(fig, bbox_inches=None, **kw)


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    return str(v)


def _governing_loadcase(
    loadcases: List[Dict[str, Any]], multi: MultiLoadCaseResult
) -> Dict[str, Any]:
    name = multi.governing_case_name
    for lc in loadcases:
        if lc.get("name") == name:
            return lc
    return loadcases[0]


def _governing_result(multi: MultiLoadCaseResult) -> WeldGroupResult:
    for c in multi.cases:
        if c.name == multi.governing_case_name:
            return c.result
    return multi.cases[0].result


def plot_coordinate_system_figure(
    segments: List[WeldSegment],
    *,
    figsize: Tuple[float, float] = A4_FIGSIZE,
) -> Any:
    """3D sketch: right-handed x–y–z and weld polyline in the plane x = 0 (portrait, axes inside limits)."""
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(111, projection="3d")

    ys: List[float] = []
    zs: List[float] = []
    for seg in segments:
        ys.extend([seg.y1, seg.y2])
        zs.extend([seg.z1, seg.z2])
    ry = max((abs(y) for y in ys), default=50.0)
    rz = max((abs(z) for z in zs), default=50.0)
    R = max(ry, rz, 40.0) * 1.06

    # Axis length: shorter than half-span so arrowheads + labels stay inside set limits
    L = min(0.38 * max(R, 90.0), 0.48 * R)
    L = max(L, 32.0)

    q_kw = dict(linewidth=2.0, arrow_length_ratio=0.18)
    ax.quiver(0, 0, 0, L, 0, 0, color="#c53030", **q_kw)
    ax.text(L * 0.78, 0, 0, "x", fontsize=12, color="#c53030", weight="bold", ha="center", va="center")
    ax.quiver(0, 0, 0, 0, L, 0, color="#2f855a", **q_kw)
    ax.text(0, L * 0.78, 0, "y", fontsize=12, color="#2f855a", weight="bold", ha="center", va="center")
    ax.quiver(0, 0, 0, 0, 0, L, color="#2c5282", **q_kw)
    ax.text(0, 0, L * 0.78, "z", fontsize=12, color="#2c5282", weight="bold", ha="center", va="center")

    for seg in segments:
        ax.plot(
            [0.0, 0.0],
            [seg.y1, seg.y2],
            [seg.z1, seg.z2],
            color="#744210",
            lw=4.0,
            solid_capstyle="round",
        )

    pad_yz = 0.12 * R
    pad_x = 0.32 * L
    ax.set_xlim(-0.06 * L, L + pad_x)
    ax.set_ylim(-R - pad_yz, R + pad_yz)
    ax.set_zlim(-R - pad_yz, R + pad_yz)

    ax.set_xlabel("x [mm]  (normal to weld plane)", labelpad=8)
    ax.set_ylabel("y [mm]  (in-plane)", labelpad=8)
    ax.set_zlabel("z [mm]  (in-plane)", labelpad=8)
    ax.set_title("Global coordinate system and weld group (x = 0)", fontsize=11, pad=10)
    ax.view_init(elev=22, azim=-56)
    try:
        ax.set_box_aspect((1, 1, 1))
    except AttributeError:
        pass
    from matplotlib.lines import Line2D

    ax.legend(
        handles=[
            Line2D([0], [0], color="#744210", lw=4, label="Weld segments (x = 0)"),
        ],
        loc="upper right",
        fontsize=8,
        framealpha=0.92,
    )

    fig.text(
        0.5,
        0.055,
        "x is normal to the weld plane; y and z lie in the weld plane (EN 1993-1-8 model in EuroWeldGroup).",
        ha="center",
        fontsize=7,
        style="italic",
    )
    ax.set_position([0.06, 0.14, 0.88, 0.78])
    return fig


def _table_on_axes(
    ax: Any,
    cell_text: List[List[str]],
    col_labels: Sequence[str],
    title: str,
    *,
    fontsize: Optional[float] = None,
    title_fontsize: float = 10.0,
    row_scale: Optional[float] = None,
) -> None:
    ax.axis("off")
    ax.set_title(title, fontsize=title_fontsize, fontweight="bold", loc="left", pad=4)
    nrows = len(cell_text)
    if fontsize is None:
        if nrows > 28:
            fontsize = 5.5
        elif nrows > 18:
            fontsize = 6.5
        else:
            fontsize = 7.5
    if row_scale is None:
        if nrows > 28:
            row_scale = 0.62
        elif nrows > 18:
            row_scale = 0.78
        elif nrows > 12:
            row_scale = 0.9
        else:
            row_scale = 1.0
    tbl = ax.table(
        cellText=cell_text,
        colLabels=list(col_labels),
        loc="upper left",
        cellLoc="left",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(fontsize)
    tbl.scale(1.0, row_scale)
    for (row, col), cell in tbl.get_celld().items():
        if row == 0:
            cell.set_facecolor("#e2e8f0")
            cell.set_text_props(weight="bold")


def _page_inputs_material_and_settings(
    *,
    report_title: str,
    check_kw: Dict[str, Any],
    sample_result: WeldGroupResult,
    extra_settings: Optional[Dict[str, Any]] = None,
) -> Any:
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=A4_FIGSIZE)
    fig.text(0.5, 0.965, report_title, ha="center", fontsize=14, fontweight="bold")
    fig.text(
        0.5,
        0.935,
        f"Generated {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        ha="center",
        fontsize=8,
        color="#4a5568",
    )
    fig.text(
        0.06,
        0.905,
        "Input data are reported as supplied (characteristic or design values per your project).",
        fontsize=7.5,
        style="italic",
        color="#2d3748",
    )

    mat_rows = [
        ["fu [MPa]", _fmt(check_kw.get("fu"))],
        ["Steel grade", _fmt(check_kw.get("steel_grade"))],
        ["βw (used)", _fmt(sample_result.beta_w)],
        ["γM2", _fmt(sample_result.gamma_M2)],
        ["σRd = fu/(βw·γM2) [MPa]", f"{sample_result.sigma_rd:.2f}"],
    ]
    ax1 = fig.add_axes([0.07, 0.62, 0.86, 0.26])
    _table_on_axes(
        ax1,
        mat_rows,
        ["Parameter", "Value"],
        "Material and resistance",
        row_scale=1.05,
    )

    wz = check_kw.get("weld_size_z")
    ta = check_kw.get("throat_a")
    weld_rows = [
        ["Leg size z [mm]", _fmt(wz) if wz is not None else "—"],
        ["Throat a [mm]", _fmt(ta) if ta is not None else f"{sample_result.throat_a:.3f}"],
        ["Reduce ends (leff = L − 2a)", _fmt(check_kw.get("reduce_ends", True))],
        ["Minimum throat check [mm]", _fmt(check_kw.get("min_throat_mm", 3.0))],
        ["Check minimum length", _fmt(check_kw.get("check_min_length", True))],
        ["Thicker part (practical min.) [mm]", _fmt(check_kw.get("thicker_part_mm"))],
    ]
    if extra_settings:
        for k in ("search_z_min", "search_z_max"):
            if k in extra_settings:
                weld_rows.append([k, _fmt(extra_settings[k])])

    ax2 = fig.add_axes([0.07, 0.10, 0.86, 0.48])
    _table_on_axes(
        ax2,
        weld_rows,
        ["Parameter", "Value"],
        "Weld geometry and detailing",
        row_scale=1.05,
    )
    return fig


def _page_weld_segments_only(segments: List[WeldSegment]) -> Any:
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=A4_FIGSIZE)
    fig.text(
        0.5,
        0.965,
        "Weld segment geometry (y–z plane, mm)",
        ha="center",
        fontsize=13,
        fontweight="bold",
    )
    geo = [
        [
            s.label or "—",
            f"{s.y1:.2f}",
            f"{s.z1:.2f}",
            f"{s.y2:.2f}",
            f"{s.z2:.2f}",
            f"{s.length_gross():.2f}",
        ]
        for s in segments
    ]
    ax = fig.add_axes([0.07, 0.045, 0.86, 0.88])
    _table_on_axes(
        ax,
        geo,
        ["Label", "y1", "z1", "y2", "z2", "L gross [mm]"],
        "Segments",
    )
    return fig


def _page_loadcases_chunk(
    chunk: List[Dict[str, Any]],
    page_index: int,
    total_pages: int,
) -> Any:
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=A4_FIGSIZE)
    head = "Load cases — actions and points of application"
    if total_pages > 1:
        head += f"  (page {page_index}/{total_pages})"
    fig.text(0.5, 0.965, head, ha="center", fontsize=11, fontweight="bold")

    rows: List[List[str]] = []
    for lc in chunk:
        pfx, pfy, pfz = lc["Pfx"], lc["Pfy"], lc["Pfz"]
        rows.append(
            [
                str(lc.get("name", "")),
                f"{lc['Fx']:.0f}",
                f"{lc['Fy']:.0f}",
                f"{lc['Fz']:.0f}",
                f"{pfx[0]:.0f},{pfx[1]:.0f},{pfx[2]:.0f}",
                f"{pfy[0]:.0f},{pfy[1]:.0f},{pfy[2]:.0f}",
                f"{pfz[0]:.0f},{pfz[1]:.0f},{pfz[2]:.0f}",
            ]
        )

    ax = fig.add_axes([0.05, 0.04, 0.9, 0.89])
    ax.axis("off")
    n = len(rows)
    fs = 7.0 if n > 12 else 7.5
    rs = 0.72 if n > 16 else (0.85 if n > 10 else 1.0)
    tbl = ax.table(
        cellText=rows,
        colLabels=[
            "Name",
            "Fx [N]",
            "Fy [N]",
            "Fz [N]",
            "Pfx [mm]",
            "Pfy [mm]",
            "Pfz [mm]",
        ],
        loc="upper center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(fs)
    tbl.scale(1.0, rs)
    for (row, col), cell in tbl.get_celld().items():
        if row == 0:
            cell.set_facecolor("#e2e8f0")
            cell.set_text_props(weight="bold")
    return fig


def _loadcase_page_chunks(
    loadcases: List[Dict[str, Any]], rows_per_page: int = 14
) -> List[Any]:
    import matplotlib.pyplot as plt

    if not loadcases:
        fig = plt.figure(figsize=A4_FIGSIZE)
        fig.text(0.5, 0.5, "No load cases defined.", ha="center", fontsize=11)
        return [fig]
    n = len(loadcases)
    total = (n + rows_per_page - 1) // rows_per_page
    out: List[Any] = []
    for p in range(total):
        start = p * rows_per_page
        chunk = loadcases[start : start + rows_per_page]
        out.append(_page_loadcases_chunk(chunk, p + 1, total))
    return out


def _page_results_overview(
    multi: MultiLoadCaseResult,
    gov: WeldGroupResult,
    required_size: Optional[Dict[str, Any]],
) -> Any:
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=A4_FIGSIZE)
    fig.text(
        0.5,
        0.965,
        "Results — EN 1993-1-8 (summary)",
        ha="center",
        fontsize=12,
        fontweight="bold",
    )

    sum_rows = []
    for c in multi.cases:
        sum_rows.append(
            [
                c.name,
                f"{c.result.max_utilization:.3f}",
                f"{c.result.max_sigma_eq:.2f}",
                c.result.governing_segment_label,
                "OK" if c.result.ok else "NOT OK",
            ]
        )
    n_lc = len(sum_rows)
    gap = 0.018
    top_band = 0.905
    h_gov = 0.23
    h_req = 0.21
    reserve = h_gov + h_req + 2 * gap + 0.04
    h_util = min(0.44, max(0.18, 0.038 * (n_lc + 2)))
    h_util = min(h_util, max(0.15, top_band - reserve - 0.04))
    bottom1 = top_band - h_util
    ax1 = fig.add_axes([0.07, bottom1, 0.86, h_util])
    _table_on_axes(
        ax1,
        sum_rows,
        ["Load case", "Max util.", "σeq [MPa]", "Governing seg.", "Status"],
        "Utilization by load case",
    )

    gov_rows = [
        ["Governing load case", multi.governing_case_name],
        ["Governing utilization", f"{multi.governing_utilization:.3f}"],
        ["Governing σeq [MPa]", f"{multi.governing_sigma_eq:.2f}"],
        ["Governing segment", multi.governing_segment_label],
        ["Overall status", "OK" if multi.ok else "NOT OK"],
        ["Weld z [mm]", f"{gov.weld_size_z:.2f}"],
        ["Throat a [mm]", f"{gov.throat_a:.2f}"],
        ["Total leff [mm]", f"{gov.total_effective_length:.2f}"],
        ["Throat area Σ(a·leff) [mm²]", f"{gov.throat_area_total:.2f}"],
        ["Centroid yc, zc [mm]", f"({gov.y_c:.2f}, {gov.z_c:.2f})"],
        ["Mx, My, Mz [Nmm]", f"{gov.Mx:.0f}, {gov.My:.0f}, {gov.Mz:.0f}"],
    ]
    bottom2 = bottom1 - gap - h_gov
    ax2 = fig.add_axes([0.07, bottom2, 0.86, h_gov])
    _table_on_axes(
        ax2,
        gov_rows,
        ["Item", "Value"],
        "Governing case — global results",
        row_scale=0.9,
    )

    bottom3 = bottom2 - gap - h_req
    if bottom3 < 0.03:
        h_req = max(0.12, bottom2 - 0.045)
        bottom3 = bottom2 - gap - h_req
    ax4 = fig.add_axes([0.07, bottom3, 0.86, h_req])
    ax4.axis("off")
    ax4.set_title("Required weld size (search bounds from input)", fontsize=9, fontweight="bold", loc="left", pad=2)
    if required_size and "_error" not in required_size:
        rs_rows = [
            [str(k), f"{v:.4f}" if isinstance(v, float) else str(v)]
            for k, v in required_size.items()
        ]
        tbl = ax4.table(cellText=rs_rows, colLabels=["Quantity", "Value"], loc="upper left", cellLoc="left")
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(7.0)
        tbl.scale(1.0, 0.95)
        for (row, col), cell in tbl.get_celld().items():
            if row == 0:
                cell.set_facecolor("#e2e8f0")
                cell.set_text_props(weight="bold")
    elif required_size and "_error" in required_size:
        ax4.text(0.0, 0.9, required_size["_error"], fontsize=7.5, color="#c53030", transform=ax4.transAxes)
    else:
        ax4.text(0.0, 0.9, "—", fontsize=8, transform=ax4.transAxes)

    return fig


def _segment_stress_rows(gov: WeldGroupResult) -> List[List[str]]:
    return [
        [
            s.label,
            f"{s.length_gross:.1f}",
            f"{s.length_effective:.1f}",
            f"{s.sigma_perp:.2f}",
            f"{s.tau_perp:.2f}",
            f"{s.tau_parallel:.2f}",
            f"{s.sigma_eq:.2f}",
            f"{s.utilization:.3f}",
            "OK" if s.ok else "NO",
        ]
        for s in gov.segment_results
    ]


def _page_results_segments_chunk(
    multi: MultiLoadCaseResult,
    seg_rows: List[List[str]],
    page_index: int,
    total_pages: int,
) -> Any:
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=A4_FIGSIZE)
    head = "Results — per-segment stresses (governing case)"
    if total_pages > 1:
        head += f"  (page {page_index}/{total_pages})"
    fig.text(0.5, 0.965, head, ha="center", fontsize=12, fontweight="bold")
    ax = fig.add_axes([0.06, 0.035, 0.88, 0.90])
    _table_on_axes(
        ax,
        seg_rows,
        [
            "Seg.",
            "Lg",
            "Leff",
            "σ⊥",
            "τ⊥",
            "τ∥",
            "σeq",
            "η",
            "OK",
        ],
        f"Governing: {multi.governing_case_name}",
    )
    return fig


def _segment_stress_pages(
    multi: MultiLoadCaseResult,
    gov: WeldGroupResult,
    rows_per_page: int = 22,
) -> List[Any]:
    seg_rows = _segment_stress_rows(gov)
    n = len(seg_rows)
    if n == 0:
        return [_page_results_segments_chunk(multi, [], 1, 1)]
    total = (n + rows_per_page - 1) // rows_per_page
    out: List[Any] = []
    for p in range(total):
        chunk = seg_rows[p * rows_per_page : (p + 1) * rows_per_page]
        out.append(_page_results_segments_chunk(multi, chunk, p + 1, total))
    return out


def write_weld_sizing_pdf(
    path: str | Path,
    *,
    segments: List[WeldSegment],
    loadcases: List[Dict[str, Any]],
    check_kw: Dict[str, Any],
    multi_result: Optional[MultiLoadCaseResult] = None,
    required_size: Optional[Dict[str, Any]] = None,
    extra_settings: Optional[Dict[str, Any]] = None,
    report_title: str = "Fillet weld group check — EN 1993-1-8 (directional method)",
) -> None:
    """Build a multi-page PDF (inputs, loads, axes, plots, results)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    if multi_result is None:
        multi_result = check_multiple_loadcases(
            segments=segments, loadcases=loadcases, **check_kw
        )

    gov_lc = _governing_loadcase(loadcases, multi_result)
    gov_res = _governing_result(multi_result)

    out = Path(path)
    with PdfPages(
        out,
        metadata={
            "Title": report_title,
            "Creator": "EuroWeldGroup",
        },
    ) as pdf:
        fig_a = _page_inputs_material_and_settings(
            report_title=report_title,
            check_kw=check_kw,
            sample_result=gov_res,
            extra_settings=extra_settings,
        )
        _save_pdf_page_a4(pdf, fig_a)
        plt.close(fig_a)

        fig_b = _page_weld_segments_only(segments)
        _save_pdf_page_a4(pdf, fig_b)
        plt.close(fig_b)

        for fig_l in _loadcase_page_chunks(loadcases):
            _save_pdf_page_a4(pdf, fig_l)
            plt.close(fig_l)

        fig_ax = plot_coordinate_system_figure(segments, figsize=A4_FIGSIZE)
        _save_pdf_page_a4(pdf, fig_ax)
        plt.close(fig_ax)

        fig_w = plot_welds_and_loads_three_planes(
            segments,
            gov_lc,
            figsize=A4_FIGSIZE,
            vertical=True,
            pdf_page=True,
            title=f"Weld geometry and actions — governing: {gov_lc.get('name', '')}",
            save_path=None,
        )
        _save_pdf_page_a4(pdf, fig_w, dpi=150)
        plt.close(fig_w)

        fig_r1 = _page_results_overview(multi_result, gov_res, required_size)
        _save_pdf_page_a4(pdf, fig_r1)
        plt.close(fig_r1)

        for fig_r2 in _segment_stress_pages(multi_result, gov_res):
            _save_pdf_page_a4(pdf, fig_r2)
            plt.close(fig_r2)


def write_sizing_pdf_from_analysis(
    a: Any,
    pdf_path: str | Path,
    *,
    report_title: str = "Fillet weld group check — EN 1993-1-8 (directional method)",
) -> None:
    # Duck-type: script run as `python weld_excel.py` uses __main__, not weld_excel module class.
    for attr in ("model", "check_kw", "multi_result"):
        if not hasattr(a, attr):
            raise TypeError(f"Expected analysis object with '.{attr}' (ExcelAnalysis).")
    write_weld_sizing_pdf(
        pdf_path,
        segments=a.model.segments,
        loadcases=a.model.loadcases,
        check_kw=a.check_kw,
        multi_result=a.multi_result,
        required_size=a.required_size,
        extra_settings=a.model.settings,
        report_title=report_title,
    )


def write_sizing_pdf_from_excel(
    xlsx_path: str | Path,
    pdf_path: str | Path,
    *,
    required_size: bool = True,
    report_title: str = "Fillet weld group check — EN 1993-1-8 (directional method)",
) -> None:
    from weld_excel import analyze_excel_workbook

    a = analyze_excel_workbook(xlsx_path, required_size=required_size)
    write_sizing_pdf_from_analysis(a, pdf_path, report_title=report_title)


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Create weld sizing PDF from Excel input.")
    p.add_argument("workbook", help="Input .xlsx")
    p.add_argument("pdf", help="Output .pdf")
    p.add_argument("--no-required-size", action="store_true", help="Skip required-size block in PDF")
    p.add_argument("--title", default="Fillet weld group check — EN 1993-1-8 (directional method)")
    args = p.parse_args()
    write_sizing_pdf_from_excel(
        args.workbook,
        args.pdf,
        required_size=not args.no_required_size,
        report_title=args.title,
    )
    print(f"PDF written to {args.pdf}")


if __name__ == "__main__":
    main()
