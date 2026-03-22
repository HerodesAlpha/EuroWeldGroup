"""
Fillet weld group check according to EN 1993-1-8 directional method.

Features
--------
- Weld group defined as line segments in the y-z plane
- Loadcases with Fx, Fy, Fz
- Separate point of action for each force component:
    * Pfx for Fx
    * Pfy for Fy
    * Pfz for Fz
- Automatic calculation of resultant moments:
    M = r_x x F_x + r_y x F_y + r_z x F_z
- Direct force + My + Mz + torsion Mx
- Effective throat / effective length
- Minimum throat / minimum effective length checks
- Optional practical minimum fillet size check
- Multiple loadcases
- Governing loadcase
- Required weld size search for all loadcases

Coordinate system
-----------------
- Weld group lies in x = 0 plane, i.e. the y-z plane
- x is normal to the weld plane
- y and z are in-plane coordinates

Stress model
------------
For each weld segment:
- sigma_perp   : normal stress perpendicular to weld throat
- tau_perp     : shear stress perpendicular to weld axis, in weld plane
- tau_parallel : shear stress parallel to weld axis

Equivalent stress:
    sigma_eq = sqrt(sigma_perp^2 + 3*(tau_perp^2 + tau_parallel^2))

Criterion:
    sigma_eq <= fu / (beta_w * gamma_M2)

Units
-----
Forces:    N
Moments:   Nmm
Lengths:   mm
Stresses:  MPa = N/mm^2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt, isclose
from typing import List, Optional, Tuple, Dict, Any


# Typical beta_w values
BETA_W_DEFAULTS = {
    "S235": 0.80,
    "S275": 0.85,
    "S355": 0.90,
    "S420": 1.00,
    "S460": 1.00,
}


def throat_from_leg(z: float) -> float:
    """Equal-leg fillet weld: a = z / sqrt(2)."""
    return z / sqrt(2.0)


def leg_from_throat(a: float) -> float:
    return a * sqrt(2.0)


def get_beta_w(steel_grade: Optional[str] = None, beta_w: Optional[float] = None) -> float:
    if beta_w is not None:
        return beta_w
    if steel_grade is None:
        raise ValueError("Provide either beta_w or steel_grade.")
    steel_grade = steel_grade.upper().strip()
    if steel_grade not in BETA_W_DEFAULTS:
        raise ValueError(
            f"Unknown steel grade '{steel_grade}'. "
            f"Known grades: {', '.join(BETA_W_DEFAULTS.keys())}."
        )
    return BETA_W_DEFAULTS[steel_grade]


def recommended_min_leg_size(thicker_part_mm: float) -> float:
    """
    Practical stepped rule often used for minimum fillet size.
    Adjust if your project uses another rule.
    """
    t = thicker_part_mm
    if t <= 10:
        return 3.0
    elif t <= 20:
        return 4.0
    elif t <= 32:
        return 5.0
    elif t <= 50:
        return 6.0
    else:
        return 8.0


@dataclass
class WeldSegment:
    y1: float
    z1: float
    y2: float
    z2: float
    label: str = ""

    def length_gross(self) -> float:
        return sqrt((self.y2 - self.y1) ** 2 + (self.z2 - self.z1) ** 2)

    def unit_tangent(self) -> Tuple[float, float]:
        L = self.length_gross()
        if isclose(L, 0.0):
            raise ValueError("Weld segment length cannot be zero.")
        return ((self.y2 - self.y1) / L, (self.z2 - self.z1) / L)

    def midpoint(self) -> Tuple[float, float]:
        return ((self.y1 + self.y2) / 2.0, (self.z1 + self.z2) / 2.0)

    def effective_length(self, throat_a: float, reduce_ends: bool = True) -> float:
        """
        Common effective length assumption:
            l_eff = l_gross - 2a
        """
        L = self.length_gross()
        if not reduce_ends:
            return L
        return max(0.0, L - 2.0 * throat_a)

    def effective_midpoint(self) -> Tuple[float, float]:
        return self.midpoint()


@dataclass
class SegmentStressResult:
    label: str
    length_gross: float
    length_effective: float
    y_mid: float
    z_mid: float
    sigma_perp: float
    tau_perp: float
    tau_parallel: float
    sigma_eq: float
    utilization: float
    ok: bool


@dataclass
class WeldGroupResult:
    throat_a: float
    weld_size_z: float
    beta_w: float
    gamma_M2: float
    fu: float
    sigma_rd: float
    total_effective_length: float
    throat_area_total: float
    y_c: float
    z_c: float
    Iyy_line: float
    Izz_line: float
    Jx_line: float
    Mx: float
    My: float
    Mz: float
    segment_results: List[SegmentStressResult] = field(default_factory=list)
    max_sigma_eq: float = 0.0
    max_utilization: float = 0.0
    governing_segment_label: str = ""
    ok: bool = True
    detailing_messages: List[str] = field(default_factory=list)


@dataclass
class LoadCaseResult:
    name: str
    result: WeldGroupResult


@dataclass
class MultiLoadCaseResult:
    cases: List[LoadCaseResult]
    governing_case_name: str
    governing_utilization: float
    governing_sigma_eq: float
    governing_segment_label: str
    ok: bool


def line_centroid_and_second_moments(
    segments: List[WeldSegment],
    throat_a: float,
    reduce_ends: bool = True,
) -> Tuple[float, float, float, float, float]:
    """
    Returns:
        total_effective_length, y_c, z_c, Iyy_line, Izz_line

    Iyy_line = integral((z-zc)^2 ds)
    Izz_line = integral((y-yc)^2 ds)
    """
    data = []
    total_L = 0.0
    Sy = 0.0
    Sz = 0.0

    for seg in segments:
        Le = seg.effective_length(throat_a, reduce_ends=reduce_ends)
        if Le <= 0:
            continue
        ym, zm = seg.effective_midpoint()
        data.append((seg, Le, ym, zm))
        total_L += Le
        Sy += Le * ym
        Sz += Le * zm

    if total_L <= 0.0:
        raise ValueError("Total effective weld length is zero.")

    y_c = Sy / total_L
    z_c = Sz / total_L

    Iyy = 0.0
    Izz = 0.0

    for seg, Le, ym, zm in data:
        ty, tz = seg.unit_tangent()

        # Local line second moments about segment midpoint
        Iyy_local = (tz ** 2) * (Le ** 3) / 12.0
        Izz_local = (ty ** 2) * (Le ** 3) / 12.0

        # Parallel axis
        Iyy += Iyy_local + Le * (zm - z_c) ** 2
        Izz += Izz_local + Le * (ym - y_c) ** 2

    return total_L, y_c, z_c, Iyy, Izz


def moments_from_component_points(
    Fx: float,
    Fy: float,
    Fz: float,
    Pfx: Tuple[float, float, float],
    Pfy: Tuple[float, float, float],
    Pfz: Tuple[float, float, float],
) -> Tuple[float, float, float]:
    """
    Total moment from three force components, each with its own point of action.

    Force components:
        Fx acts through Pfx = (x, y, z)
        Fy acts through Pfy = (x, y, z)
        Fz acts through Pfz = (x, y, z)

    M = r_x x F_x + r_y x F_y + r_z x F_z
    """

    # Fx at Pfx
    x1, y1, z1 = Pfx
    Mx1 = 0.0
    My1 = z1 * Fx
    Mz1 = -y1 * Fx

    # Fy at Pfy
    x2, y2, z2 = Pfy
    Mx2 = -z2 * Fy
    My2 = 0.0
    Mz2 = x2 * Fy

    # Fz at Pfz
    x3, y3, z3 = Pfz
    Mx3 = y3 * Fz
    My3 = -x3 * Fz
    Mz3 = 0.0

    Mx = Mx1 + Mx2 + Mx3
    My = My1 + My2 + My3
    Mz = Mz1 + Mz2 + Mz3

    return Mx, My, Mz


def weld_group_check(
    *,
    segments: List[WeldSegment],
    fu: float,
    steel_grade: Optional[str] = None,
    beta_w: Optional[float] = None,
    gamma_M2: float = 1.25,
    weld_size_z: Optional[float] = None,
    throat_a: Optional[float] = None,
    reduce_ends: bool = True,
    min_throat_mm: float = 3.0,
    check_min_length: bool = True,
    thicker_part_mm: Optional[float] = None,
    Fx: float = 0.0,
    Fy: float = 0.0,
    Fz: float = 0.0,
    Mx: float = 0.0,
    My: float = 0.0,
    Mz: float = 0.0,
) -> WeldGroupResult:
    if fu <= 0:
        raise ValueError("fu must be > 0.")
    if not segments:
        raise ValueError("At least one weld segment is required.")

    if throat_a is None and weld_size_z is None:
        raise ValueError("Provide either weld_size_z or throat_a.")
    if throat_a is not None and weld_size_z is not None:
        raise ValueError("Provide only one of weld_size_z or throat_a.")

    if throat_a is None:
        throat_a = throat_from_leg(weld_size_z)
    else:
        weld_size_z = leg_from_throat(throat_a)

    if throat_a <= 0.0:
        raise ValueError("throat_a must be > 0.")

    beta_w_val = get_beta_w(steel_grade=steel_grade, beta_w=beta_w)
    sigma_rd = fu / (beta_w_val * gamma_M2)

    total_L, y_c, z_c, Iyy_line, Izz_line = line_centroid_and_second_moments(
        segments, throat_a, reduce_ends=reduce_ends
    )
    Jx_line = Iyy_line + Izz_line
    A_w = throat_a * total_L

    detailing_messages: List[str] = []

    if throat_a < min_throat_mm:
        detailing_messages.append(
            f"Effective throat a = {throat_a:.2f} mm is below minimum throat {min_throat_mm:.2f} mm."
        )

    if thicker_part_mm is not None:
        z_min_practical = recommended_min_leg_size(thicker_part_mm)
        if weld_size_z < z_min_practical:
            detailing_messages.append(
                f"Weld size z = {weld_size_z:.2f} mm is below practical minimum "
                f"{z_min_practical:.2f} mm for thicker part t = {thicker_part_mm:.1f} mm."
            )

    results: List[SegmentStressResult] = []
    max_sigma_eq = 0.0
    max_util = 0.0
    governing_segment_label = ""
    overall_ok = True

    # Direct stresses from resultant forces
    sigma_perp_direct = Fx / A_w
    qy_direct = Fy / total_L
    qz_direct = Fz / total_L

    for i, seg in enumerate(segments, start=1):
        Le = seg.effective_length(throat_a, reduce_ends=reduce_ends)
        label = seg.label or f"Seg{i}"

        if Le <= 0.0:
            results.append(
                SegmentStressResult(
                    label=label,
                    length_gross=seg.length_gross(),
                    length_effective=Le,
                    y_mid=seg.midpoint()[0],
                    z_mid=seg.midpoint()[1],
                    sigma_perp=0.0,
                    tau_perp=0.0,
                    tau_parallel=0.0,
                    sigma_eq=0.0,
                    utilization=0.0,
                    ok=False,
                )
            )
            detailing_messages.append(f"{label}: effective length is zero or negative.")
            overall_ok = False
            continue

        ym, zm = seg.effective_midpoint()
        yr = ym - y_c
        zr = zm - z_c
        r = sqrt(yr ** 2 + zr ** 2)

        # Moment-induced in-plane line forces
        qz_from_My = 0.0 if isclose(Iyy_line, 0.0) else (My * zr / Iyy_line)
        qy_from_Mz = 0.0 if isclose(Izz_line, 0.0) else (-Mz * yr / Izz_line)

        # Torsion about x-axis -> tangential line shear in yz plane
        if isclose(r, 0.0) or isclose(Jx_line, 0.0):
            qy_from_Mx = 0.0
            qz_from_Mx = 0.0
        else:
            q_t = Mx * r / Jx_line
            qy_from_Mx = q_t * (-zr / r)
            qz_from_Mx = q_t * (yr / r)

        qy_total = qy_direct + qy_from_Mz + qy_from_Mx
        qz_total = qz_direct + qz_from_My + qz_from_Mx

        ty, tz = seg.unit_tangent()

        # Resolve to local weld coordinates
        q_parallel = qy_total * ty + qz_total * tz
        q_perp = qy_total * (-tz) + qz_total * ty

        tau_parallel = q_parallel / throat_a
        tau_perp = q_perp / throat_a
        sigma_perp = sigma_perp_direct

        sigma_eq = sqrt(sigma_perp ** 2 + 3.0 * (tau_perp ** 2 + tau_parallel ** 2))
        util = sigma_eq / sigma_rd
        ok = util <= 1.0

        if check_min_length:
            min_len = max(30.0, 6.0 * throat_a)
            if Le < min_len:
                detailing_messages.append(
                    f"{label}: effective length {Le:.1f} mm is below minimum {min_len:.1f} mm."
                )
                ok = False

        if not ok:
            overall_ok = False

        if util > max_util:
            max_util = util
            max_sigma_eq = sigma_eq
            governing_segment_label = label

        results.append(
            SegmentStressResult(
                label=label,
                length_gross=seg.length_gross(),
                length_effective=Le,
                y_mid=ym,
                z_mid=zm,
                sigma_perp=sigma_perp,
                tau_perp=tau_perp,
                tau_parallel=tau_parallel,
                sigma_eq=sigma_eq,
                utilization=util,
                ok=ok,
            )
        )

    if detailing_messages:
        overall_ok = False

    return WeldGroupResult(
        throat_a=throat_a,
        weld_size_z=weld_size_z,
        beta_w=beta_w_val,
        gamma_M2=gamma_M2,
        fu=fu,
        sigma_rd=sigma_rd,
        total_effective_length=total_L,
        throat_area_total=A_w,
        y_c=y_c,
        z_c=z_c,
        Iyy_line=Iyy_line,
        Izz_line=Izz_line,
        Jx_line=Jx_line,
        Mx=Mx,
        My=My,
        Mz=Mz,
        segment_results=results,
        max_sigma_eq=max_sigma_eq,
        max_utilization=max_util,
        governing_segment_label=governing_segment_label,
        ok=overall_ok,
        detailing_messages=detailing_messages,
    )


def weld_group_check_from_component_points(
    *,
    segments: List[WeldSegment],
    fu: float,
    steel_grade: Optional[str] = None,
    beta_w: Optional[float] = None,
    gamma_M2: float = 1.25,
    weld_size_z: Optional[float] = None,
    throat_a: Optional[float] = None,
    reduce_ends: bool = True,
    min_throat_mm: float = 3.0,
    check_min_length: bool = True,
    thicker_part_mm: Optional[float] = None,
    Fx: float = 0.0,
    Fy: float = 0.0,
    Fz: float = 0.0,
    Pfx: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    Pfy: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    Pfz: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> WeldGroupResult:
    Mx, My, Mz = moments_from_component_points(
        Fx=Fx, Fy=Fy, Fz=Fz,
        Pfx=Pfx, Pfy=Pfy, Pfz=Pfz
    )

    return weld_group_check(
        segments=segments,
        fu=fu,
        steel_grade=steel_grade,
        beta_w=beta_w,
        gamma_M2=gamma_M2,
        weld_size_z=weld_size_z,
        throat_a=throat_a,
        reduce_ends=reduce_ends,
        min_throat_mm=min_throat_mm,
        check_min_length=check_min_length,
        thicker_part_mm=thicker_part_mm,
        Fx=Fx,
        Fy=Fy,
        Fz=Fz,
        Mx=Mx,
        My=My,
        Mz=Mz,
    )


def check_multiple_loadcases(
    *,
    segments: List[WeldSegment],
    loadcases: List[Dict[str, Any]],
    fu: float,
    steel_grade: Optional[str] = None,
    beta_w: Optional[float] = None,
    gamma_M2: float = 1.25,
    weld_size_z: Optional[float] = None,
    throat_a: Optional[float] = None,
    reduce_ends: bool = True,
    min_throat_mm: float = 3.0,
    check_min_length: bool = True,
    thicker_part_mm: Optional[float] = None,
) -> MultiLoadCaseResult:
    case_results: List[LoadCaseResult] = []

    for i, lc in enumerate(loadcases, start=1):
        name = lc.get("name", f"LC{i}")

        r = weld_group_check_from_component_points(
            segments=segments,
            fu=fu,
            steel_grade=steel_grade,
            beta_w=beta_w,
            gamma_M2=gamma_M2,
            weld_size_z=weld_size_z,
            throat_a=throat_a,
            reduce_ends=reduce_ends,
            min_throat_mm=min_throat_mm,
            check_min_length=check_min_length,
            thicker_part_mm=thicker_part_mm,
            Fx=lc.get("Fx", 0.0),
            Fy=lc.get("Fy", 0.0),
            Fz=lc.get("Fz", 0.0),
            Pfx=lc.get("Pfx", (0.0, 0.0, 0.0)),
            Pfy=lc.get("Pfy", (0.0, 0.0, 0.0)),
            Pfz=lc.get("Pfz", (0.0, 0.0, 0.0)),
        )

        case_results.append(LoadCaseResult(name=name, result=r))

    if not case_results:
        raise ValueError("No loadcases provided.")

    governing = max(case_results, key=lambda x: x.result.max_utilization)
    overall_ok = all(c.result.ok for c in case_results)

    return MultiLoadCaseResult(
        cases=case_results,
        governing_case_name=governing.name,
        governing_utilization=governing.result.max_utilization,
        governing_sigma_eq=governing.result.max_sigma_eq,
        governing_segment_label=governing.result.governing_segment_label,
        ok=overall_ok,
    )


def required_weld_size_for_multiple_loadcases(
    *,
    segments: List[WeldSegment],
    loadcases: List[Dict[str, Any]],
    fu: float,
    steel_grade: Optional[str] = None,
    beta_w: Optional[float] = None,
    gamma_M2: float = 1.25,
    reduce_ends: bool = True,
    min_throat_mm: float = 3.0,
    check_min_length: bool = True,
    thicker_part_mm: Optional[float] = None,
    z_min: float = 2.0,
    z_max: float = 25.0,
    tol: float = 1e-4,
    max_iter: int = 100,
) -> Dict[str, Any]:
    def max_util_for_z(z: float) -> Tuple[float, str, str]:
        mlc = check_multiple_loadcases(
            segments=segments,
            loadcases=loadcases,
            fu=fu,
            steel_grade=steel_grade,
            beta_w=beta_w,
            gamma_M2=gamma_M2,
            weld_size_z=z,
            reduce_ends=reduce_ends,
            min_throat_mm=min_throat_mm,
            check_min_length=check_min_length,
            thicker_part_mm=thicker_part_mm,
        )
        return mlc.governing_utilization, mlc.governing_case_name, mlc.governing_segment_label

    u_min, lc_min, seg_min = max_util_for_z(z_min)
    if u_min <= 1.0:
        return {
            "required_leg_size_z_mm": z_min,
            "required_throat_a_mm": throat_from_leg(z_min),
            "governing_case": lc_min,
            "governing_segment": seg_min,
            "note": "Lower bound already sufficient.",
        }

    u_max, _, _ = max_util_for_z(z_max)
    if u_max > 1.0:
        raise ValueError("z_max is too small. Increase search upper bound.")

    lo, hi = z_min, z_max
    gov_name = ""
    gov_seg = ""

    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        u_mid, gov_name, gov_seg = max_util_for_z(mid)

        if abs(u_mid - 1.0) < tol:
            lo = hi = mid
            break

        if u_mid > 1.0:
            lo = mid
        else:
            hi = mid

    z_req = hi
    u_req, gov_name, gov_seg = max_util_for_z(z_req)

    return {
        "required_leg_size_z_mm": z_req,
        "required_throat_a_mm": throat_from_leg(z_req),
        "governing_case": gov_name,
        "governing_segment": gov_seg,
        "utilization_at_z": u_req,
    }


def print_weld_group_result(r: WeldGroupResult) -> None:
    print("\nFILLET WELD GROUP CHECK")
    print("=" * 100)
    print(f"Weld size z                = {r.weld_size_z:.2f} mm")
    print(f"Throat a                   = {r.throat_a:.2f} mm")
    print(f"fu                         = {r.fu:.1f} MPa")
    print(f"beta_w                     = {r.beta_w:.3f}")
    print(f"gamma_M2                   = {r.gamma_M2:.3f}")
    print(f"Resistance stress          = {r.sigma_rd:.2f} MPa")
    print(f"Total effective length     = {r.total_effective_length:.2f} mm")
    print(f"Total throat area          = {r.throat_area_total:.2f} mm²")
    print(f"Centroid (y_c, z_c)        = ({r.y_c:.2f}, {r.z_c:.2f}) mm")
    print(f"Iyy_line                   = {r.Iyy_line:.2f} mm³")
    print(f"Izz_line                   = {r.Izz_line:.2f} mm³")
    print(f"Jx_line                    = {r.Jx_line:.2f} mm³")
    print(f"Mx                         = {r.Mx:.2f} Nmm")
    print(f"My                         = {r.My:.2f} Nmm")
    print(f"Mz                         = {r.Mz:.2f} Nmm")
    print(f"Max equivalent stress      = {r.max_sigma_eq:.2f} MPa")
    print(f"Max utilization            = {r.max_utilization:.3f}")
    print(f"Governing segment          = {r.governing_segment_label}")
    print(f"STATUS                     = {'OK' if r.ok else 'NOT OK'}")
    print("-" * 100)

    header = (
        f"{'Label':<12}{'L_gross':>10}{'L_eff':>10}{'y_mid':>10}{'z_mid':>10}"
        f"{'sig_perp':>12}{'tau_perp':>12}{'tau_par':>12}{'sig_eq':>12}{'util':>10}"
    )
    print(header)
    print("-" * len(header))

    for s in r.segment_results:
        print(
            f"{s.label:<12}{s.length_gross:>10.1f}{s.length_effective:>10.1f}"
            f"{s.y_mid:>10.1f}{s.z_mid:>10.1f}"
            f"{s.sigma_perp:>12.2f}{s.tau_perp:>12.2f}{s.tau_parallel:>12.2f}"
            f"{s.sigma_eq:>12.2f}{s.utilization:>10.3f}"
        )

    if r.detailing_messages:
        print("\nDETAILING / WARNINGS")
        print("-" * 100)
        for msg in r.detailing_messages:
            print(f"- {msg}")


def print_multiple_loadcases_result(r: MultiLoadCaseResult) -> None:
    print("\nMULTIPLE LOADCASE SUMMARY")
    print("=" * 100)
    print(f"{'Loadcase':<16}{'Utilization':>14}{'Sigma_eq [MPa]':>18}{'Gov. seg.':>16}{'Status':>12}")
    print("-" * 100)

    for case in r.cases:
        status = "OK" if case.result.ok else "NOT OK"
        print(
            f"{case.name:<16}"
            f"{case.result.max_utilization:>14.3f}"
            f"{case.result.max_sigma_eq:>18.2f}"
            f"{case.result.governing_segment_label:>16}"
            f"{status:>12}"
        )

    print("-" * 100)
    print(f"Governing case:      {r.governing_case_name}")
    print(f"Governing segment:   {r.governing_segment_label}")
    print(f"Governing utilization: {r.governing_utilization:.3f}")
    print(f"Overall status: {'OK' if r.ok else 'NOT OK'}")


if __name__ == "__main__":
    # ------------------------------------------------------------
    # Example weld geometry
    # ------------------------------------------------------------
    # Rectangle 200 x 100 mm in yz plane
    b = 200.0
    h = 100.0

    segments = [
        WeldSegment(-b / 2, -h / 2,  b / 2, -h / 2, "bot"),
        WeldSegment( b / 2, -h / 2,  b / 2,  h / 2, "rhs"),
        WeldSegment( b / 2,  h / 2, -b / 2,  h / 2, "top"),
        WeldSegment(-b / 2,  h / 2, -b / 2, -h / 2, "lhs"),
    ]

    # ------------------------------------------------------------
    # Example loadcases
    # Each force component has its own point of action
    # ------------------------------------------------------------
    loadcases = [
        {
            "name": "LC1",
            "Fx": 25000.0,
            "Fy": 40000.0,
            "Fz": 15000.0,
            "Pfx": (120.0, 0.0, 0.0),
            "Pfy": (120.0, 0.0, 35.0),
            "Pfz": (120.0, 25.0, 0.0),
        },
        {
            "name": "LC2",
            "Fx": 18000.0,
            "Fy": 10000.0,
            "Fz": 30000.0,
            "Pfx": (120.0, 0.0, 0.0),
            "Pfy": (120.0, 0.0, 35.0),
            "Pfz": (120.0, 25.0, 0.0),
        },
        {
            "name": "LC3",
            "Fx": -10000.0,
            "Fy": 25000.0,
            "Fz": 5000.0,
            "Pfx": (120.0, 0.0, 0.0),
            "Pfy": (120.0, 0.0, 35.0),
            "Pfz": (120.0, 25.0, 0.0),
        },
        {
            "name": "LC4",
            "Fx": 30000.0,
            "Fy": -5000.0,
            "Fz": 10000.0,
            "Pfx": (100.0, 0.0, 0.0),
            "Pfy": (100.0, 0.0, 30.0),
            "Pfz": (100.0, 20.0, 0.0),
        },
        {
            "name": "LC5",
            "Fx": 0.0,
            "Fy": 45000.0,
            "Fz": 0.0,
            "Pfx": (150.0, 0.0, 0.0),
            "Pfy": (150.0, 0.0, 40.0),
            "Pfz": (150.0, 0.0, 0.0),
        },
        {
            "name": "LC6",
            "Fx": 15000.0,
            "Fy": 15000.0,
            "Fz": 15000.0,
            "Pfx": (80.0, 0.0, 0.0),
            "Pfy": (80.0, 0.0, 25.0),
            "Pfz": (80.0, 25.0, 0.0),
        },
        {
            "name": "LC7",
            "Fx": -20000.0,
            "Fy": 10000.0,
            "Fz": -5000.0,
            "Pfx": (90.0, 0.0, 0.0),
            "Pfy": (90.0, 0.0, 15.0),
            "Pfz": (90.0, -15.0, 0.0),
        },
        {
            "name": "LC8",
            "Fx": 22000.0,
            "Fy": -20000.0,
            "Fz": 18000.0,
            "Pfx": (110.0, 0.0, 0.0),
            "Pfy": (110.0, 0.0, 20.0),
            "Pfz": (110.0, 5.0, 0.0),
        },
        {
            "name": "LC9",
            "Fx": 12000.0,
            "Fy": 5000.0,
            "Fz": 28000.0,
            "Pfx": (140.0, 0.0, 0.0),
            "Pfy": (140.0, 0.0, 10.0),
            "Pfz": (140.0, 10.0, 0.0),
        },
        {
            "name": "LC10",
            "Fx": 35000.0,
            "Fy": 12000.0,
            "Fz": -10000.0,
            "Pfx": (130.0, 0.0, 0.0),
            "Pfy": (130.0, 0.0, 18.0),
            "Pfz": (130.0, -20.0, 0.0),
        },
    ]

    # ------------------------------------------------------------
    # Single loadcase check example
    # ------------------------------------------------------------
    first_result = weld_group_check_from_component_points(
        segments=segments,
        fu=510.0,
        steel_grade="S355",
        gamma_M2=1.25,
        weld_size_z=6.0,
        reduce_ends=True,
        thicker_part_mm=16.0,
        Fx=loadcases[0]["Fx"],
        Fy=loadcases[0]["Fy"],
        Fz=loadcases[0]["Fz"],
        Pfx=loadcases[0]["Pfx"],
        Pfy=loadcases[0]["Pfy"],
        Pfz=loadcases[0]["Pfz"],
    )
    print_weld_group_result(first_result)

    # ------------------------------------------------------------
    # All loadcases
    # ------------------------------------------------------------
    multi_result = check_multiple_loadcases(
        segments=segments,
        loadcases=loadcases,
        fu=510.0,
        steel_grade="S355",
        gamma_M2=1.25,
        weld_size_z=6.0,
        reduce_ends=True,
        thicker_part_mm=16.0,
    )
    print_multiple_loadcases_result(multi_result)

    # ------------------------------------------------------------
    # Required weld size for all loadcases
    # ------------------------------------------------------------
    req = required_weld_size_for_multiple_loadcases(
        segments=segments,
        loadcases=loadcases,
        fu=510.0,
        steel_grade="S355",
        gamma_M2=1.25,
        reduce_ends=True,
        thicker_part_mm=16.0,
        z_min=3.0,
        z_max=16.0,
    )

    print("\nREQUIRED WELD SIZE FOR ALL LOADCASES")
    print("=" * 100)
    for k, v in req.items():
        if isinstance(v, float):
            print(f"{k:<28} = {v:.4f}")
        else:
            print(f"{k:<28} = {v}")

    from pathlib import Path

    from weld_plotting import plot_welds_and_loads_three_planes

    _plot_file = Path(__file__).resolve().parent / "weld_loads_three_views.png"
    plot_welds_and_loads_three_planes(segments, loadcases[0], save_path=_plot_file)
    print(f"Plot saved to {_plot_file}")