"""
Orthographic plots of weld geometry and component forces (Fx, Fy, Fz) at Pfx, Pfy, Pfz.

Weld segments lie in the plane x = 0; endpoints are (0, y, z). Load points are full (x, y, z).
The same scale factor (mm per N) is used in all three views so relative force magnitudes match.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _segment_xyz(seg: Any) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    return (0.0, float(seg.y1), float(seg.z1)), (0.0, float(seg.y2), float(seg.z2))


def _parse_loadcase(loadcase: Dict[str, Any]) -> Tuple[float, float, float, Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]:
    Fx = float(loadcase["Fx"])
    Fy = float(loadcase["Fy"])
    Fz = float(loadcase["Fz"])
    def _p(key: str) -> Tuple[float, float, float]:
        t = loadcase.get(key, (0.0, 0.0, 0.0))
        return float(t[0]), float(t[1]), float(t[2])

    Pfx, Pfy, Pfz = _p("Pfx"), _p("Pfy"), _p("Pfz")
    return Fx, Fy, Fz, Pfx, Pfy, Pfz


def _bbox_and_scale(
    segments: List[Any],
    Pfx: Tuple[float, float, float],
    Pfy: Tuple[float, float, float],
    Pfz: Tuple[float, float, float],
    Fx: float,
    Fy: float,
    Fz: float,
    force_scale: Optional[float],
) -> Tuple[float, float, float, float, float, float, float]:
    xs: List[float] = [Pfx[0], Pfy[0], Pfz[0]]
    ys: List[float] = [Pfx[1], Pfy[1], Pfz[1]]
    zs: List[float] = [Pfx[2], Pfy[2], Pfz[2]]
    for seg in segments:
        (x1, y1, z1), (x2, y2, z2) = _segment_xyz(seg)
        xs.extend([x1, x2])
        ys.extend([y1, y2])
        zs.extend([z1, z2])
    span_x = max(xs) - min(xs) if xs else 1.0
    span_y = max(ys) - min(ys) if ys else 1.0
    span_z = max(zs) - min(zs) if zs else 1.0
    Lref = max(span_x, span_y, span_z, 1.0)
    Fabs = max(abs(Fx), abs(Fy), abs(Fz), 1e-9)
    scale = (0.28 * Lref / Fabs) if force_scale is None else force_scale
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs), scale


def _arrow(ax: Any, x0: float, y0: float, dx: float, dy: float, color: str, lw: float = 2.0) -> None:
    ax.annotate(
        "",
        xy=(x0 + dx, y0 + dy),
        xytext=(x0, y0),
        arrowprops=dict(arrowstyle="->", color=color, lw=lw),
        zorder=4,
    )


def _perp_marker(ax: Any, x: float, y: float, text: str, color: str) -> None:
    ax.scatter([x], [y], s=70, c=color, zorder=5, edgecolors="white", linewidths=1.2)
    ax.annotate(
        text,
        (x, y),
        textcoords="offset points",
        xytext=(6, 6),
        fontsize=8,
        color=color,
        zorder=6,
    )


def plot_welds_and_loads_three_planes(
    segments: List[Any],
    loadcase: Dict[str, Any],
    *,
    figsize: Tuple[float, float] = (12.0, 4.2),
    force_scale: Optional[float] = None,
    show_segment_labels: bool = True,
    title: Optional[str] = None,
    save_path: str | Path | None = None,
    dpi: float = 150.0,
) -> Any:
    """
    Three orthographic views: XY (x horizontal, y vertical), XZ (x horizontal, z vertical),
    YZ (y horizontal, z vertical).

    Force arrows use vector (Fx,0,0), (0,Fy,0), (0,0,Fz) at Pfx, Pfy, Pfz with length |F| * scale.
    Components normal to a view are shown as a marker and annotation.

    If ``save_path`` is set, the figure is written there and closed (no interactive window).
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError as e:
        raise ImportError(
            "Plotting needs matplotlib. Install with: pip install -r requirements.txt"
        ) from e

    Fx, Fy, Fz, Pfx, Pfy, Pfz = _parse_loadcase(loadcase)
    x_fx, y_fx, z_fx = Pfx
    x_fy, y_fy, z_fy = Pfy
    x_fz, y_fz, z_fz = Pfz

    x_min, x_max, y_min, y_max, z_min, z_max, scale = _bbox_and_scale(
        segments, Pfx, Pfy, Pfz, Fx, Fy, Fz, force_scale
    )

    fig, axes = plt.subplots(1, 3, figsize=figsize)
    ax_xy, ax_xz, ax_yz = axes[0], axes[1], axes[2]

    # --- Welds in each projection ---
    for seg in segments:
        (x1, y1, z1), (x2, y2, z2) = _segment_xyz(seg)
        ax_xy.plot([x1, x2], [y1, y2], color="#2c5282", lw=3.0, solid_capstyle="round", zorder=2)
        ax_xz.plot([x1, x2], [z1, z2], color="#2c5282", lw=3.0, solid_capstyle="round", zorder=2)
        ax_yz.plot([y1, y2], [z1, z2], color="#2c5282", lw=3.0, solid_capstyle="round", zorder=2)
        if show_segment_labels and getattr(seg, "label", ""):
            ym, zm = (y1 + y2) / 2, (z1 + z2) / 2
            xm = (x1 + x2) / 2
            ax_xy.annotate(seg.label, (xm, ym), textcoords="offset points", xytext=(3, 3), fontsize=8, color="#2c5282")
            ax_xz.annotate(seg.label, (xm, (z1 + z2) / 2), textcoords="offset points", xytext=(3, 3), fontsize=8, color="#2c5282")
            ax_yz.annotate(seg.label, (ym, zm), textcoords="offset points", xytext=(3, 3), fontsize=8, color="#2c5282")

    c_fx, c_fy, c_fz = "#805ad5", "#c53030", "#2f855a"

    # --- XY: horizontal x, vertical y ---
    if abs(Fx) > 1e-12:
        _arrow(ax_xy, x_fx, y_fx, Fx * scale, 0.0, c_fx)
        ax_xy.text(x_fx + Fx * scale * 1.03, y_fx, f"Fx={Fx:.0f} N", fontsize=8, color=c_fx, va="center")
    if abs(Fy) > 1e-12:
        _arrow(ax_xy, x_fy, y_fy, 0.0, Fy * scale, c_fy)
        ax_xy.text(x_fy, y_fy + Fy * scale * 1.05, f"Fy={Fy:.0f} N", fontsize=8, color=c_fy, ha="center")
    if abs(Fz) > 1e-12:
        _perp_marker(ax_xy, x_fz, y_fz, f"Fz={Fz:.0f} N (out of plane)", c_fz)

    # --- XZ: horizontal x, vertical z ---
    if abs(Fx) > 1e-12:
        _arrow(ax_xz, x_fx, z_fx, Fx * scale, 0.0, c_fx)
        ax_xz.text(x_fx + Fx * scale * 1.03, z_fx, f"Fx={Fx:.0f} N", fontsize=8, color=c_fx, va="center")
    if abs(Fz) > 1e-12:
        _arrow(ax_xz, x_fz, z_fz, 0.0, Fz * scale, c_fz)
        ax_xz.text(x_fz, z_fz + Fz * scale * 1.05, f"Fz={Fz:.0f} N", fontsize=8, color=c_fz, ha="center")
    if abs(Fy) > 1e-12:
        _perp_marker(ax_xz, x_fy, z_fy, f"Fy={Fy:.0f} N (out of plane)", c_fy)

    # --- YZ: horizontal y, vertical z (weld plane) ---
    if abs(Fy) > 1e-12:
        _arrow(ax_yz, y_fy, z_fy, Fy * scale, 0.0, c_fy)
        ax_yz.text(y_fy + Fy * scale * 1.05, z_fy, f"Fy={Fy:.0f} N", fontsize=8, color=c_fy, va="center", ha="left" if Fy >= 0 else "right")
    if abs(Fz) > 1e-12:
        _arrow(ax_yz, y_fz, z_fz, 0.0, Fz * scale, c_fz)
        ax_yz.text(y_fz, z_fz + Fz * scale * 1.06, f"Fz={Fz:.0f} N", fontsize=8, color=c_fz, ha="center")
    if abs(Fx) > 1e-12:
        sym = "⊙" if Fx >= 0 else "⊗"
        _perp_marker(ax_yz, y_fx, z_fx, f"{sym} Fx={Fx:.0f} N (out of plane)", c_fx)

    def _pad_limits(ax: Any, horiz: List[float], vert: List[float], pad: float) -> None:
        ax.set_xlim(min(horiz) - pad, max(horiz) + pad)
        ax.set_ylim(min(vert) - pad, max(vert) + pad)
        ax.set_aspect("equal", adjustable="box")
        ax.grid(True, alpha=0.35, linestyle=":")

    pad = 0.12 * max(x_max - x_min, y_max - y_min, z_max - z_min, 1.0)

    xh_xy = [x_min, x_max, x_fx, x_fy, x_fz]
    yv_xy = [y_min, y_max, y_fx, y_fy, y_fz]
    if abs(Fx) > 1e-12:
        xh_xy.append(x_fx + Fx * scale)
    if abs(Fy) > 1e-12:
        yv_xy.append(y_fy + Fy * scale)

    xh_xz = [x_min, x_max, x_fx, x_fy, x_fz]
    zv_xz = [z_min, z_max, z_fx, z_fy, z_fz]
    if abs(Fx) > 1e-12:
        xh_xz.append(x_fx + Fx * scale)
    if abs(Fz) > 1e-12:
        zv_xz.append(z_fz + Fz * scale)

    yh_yz = [y_min, y_max, y_fx, y_fy, y_fz]
    zv_yz = [z_min, z_max, z_fx, z_fy, z_fz]
    if abs(Fy) > 1e-12:
        yh_yz.append(y_fy + Fy * scale)
    if abs(Fz) > 1e-12:
        zv_yz.append(z_fz + Fz * scale)

    _pad_limits(ax_xy, xh_xy, yv_xy, pad)
    _pad_limits(ax_xz, xh_xz, zv_xz, pad)
    _pad_limits(ax_yz, yh_yz, zv_yz, pad)

    ax_xy.set_xlabel("x [mm]")
    ax_xy.set_ylabel("y [mm]")
    ax_xy.set_title("XY (look along −z)")

    ax_xz.set_xlabel("x [mm]")
    ax_xz.set_ylabel("z [mm]")
    ax_xz.set_title("XZ (look along −y)")

    ax_yz.set_xlabel("y [mm]")
    ax_yz.set_ylabel("z [mm]")
    ax_yz.set_title("YZ (look along −x, weld plane)")

    lc_name = loadcase.get("name", "")
    fig.suptitle(
        title
        if title is not None
        else (f"Weld + loads — {lc_name}" if lc_name else "Weld + loads (three views)"),
        fontsize=11,
        y=1.02,
    )
    fig.text(
        0.5,
        0.02,
        f"Arrow length = |F| × scale,  scale = {scale:.6g} mm/N  (same in all panels)",
        ha="center",
        fontsize=9,
        style="italic",
    )

    plt.tight_layout(rect=(0, 0.06, 1, 0.96))
    if save_path is not None:
        p = Path(save_path)
        fig.savefig(p, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
    return fig
