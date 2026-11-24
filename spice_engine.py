"""ngspice adapter for the Lab 04 common-emitter amplifier simulator.

This module never imports Flask.  It builds netlists, validates simulator
inputs, invokes ngspice as an external batch process, and parses the real
text output.  Every value returned to the web layer must come from either
validation or parsed ngspice output -- never from a hard-coded result.
"""

from __future__ import annotations

import math
import os
import re
import shutil
from pathlib import Path

DEFAULT_MODEL_NAME = "QEDU"
BJT_MODEL_CARD = (
    "NPN(IS=1e-14 BF=100 VAF=100 RB=10 RC=1 CJE=10p CJC=5p TF=0.3n TR=10n)"
)
AC_FMIN_HZ = 1.0
AC_FMAX_HZ = 1.0e6
SIM_TIMEOUT_S = 20.0

ANALYSES = ("dc", "ac", "tran")

# field -> (minimum, maximum), both inclusive
RANGES = {
    "vcc_v": (1.0, 60.0),
    "r1_ohm": (100.0, 10.0e6),
    "r2_ohm": (100.0, 10.0e6),
    "rc_ohm": (1.0, 1.0e6),
    "re_ohm": (1.0, 1.0e6),
    "rl_ohm": (1.0, 1.0e6),
    "cin_f": (1.0e-9, 1.0e-2),
    "cout_f": (1.0e-9, 1.0e-2),
    "amplitude_v": (1.0e-6, 2.0),
    "frequency_hz": (1.0, 1.0e6),
    "beta": (1.0, 1000.0),
    "vbe": (0.1, 1.0),
}


class SimulationError(RuntimeError):
    """ngspice could not complete a simulation run."""


class NgspiceNotFound(SimulationError):
    """No usable ngspice executable was found."""


class ValidationError(ValueError):
    """Simulator input failed validation before a netlist was built."""


class ParseError(SimulationError):
    """ngspice ran but its output could not be parsed."""


def _candidate_paths():
    """Yield candidate ngspice executables in discovery order."""
    env = os.environ.get("NGSPICE_BIN")
    if env:
        yield Path(env)
    for name in ("ngspice_con", "ngspice"):
        found = shutil.which(name)
        if found:
            yield Path(found)
    yield Path.home() / "AppData/Local/ngspice-47/Spice64/bin/ngspice_con.exe"
    yield Path("C:/Spice64/bin/ngspice_con.exe")
    yield Path("C:/Program Files/ngspice/Spice64/bin/ngspice_con.exe")


def find_ngspice() -> Path:
    """Return the first existing ngspice executable, or raise.

    Search order: ``NGSPICE_BIN``, ``PATH`` (``ngspice_con`` then
    ``ngspice``), then the portable and system install locations used in
    this course.
    """
    for candidate in _candidate_paths():
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    raise NgspiceNotFound(
        "ไม่พบ ngspice: ติดตั้ง ngspice 47 แล้วตั้งค่า environment variable "
        "NGSPICE_BIN ให้ชี้ไปที่ ngspice_con.exe"
    )


def ngspice_available() -> bool:
    """True when :func:`find_ngspice` can locate an executable."""
    try:
        find_ngspice()
    except NgspiceNotFound:
        return False
    return True


def _to_float(field: str, value) -> float:
    if isinstance(value, bool):
        raise ValidationError(f"{field} ต้องเป็นตัวเลข")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} ต้องเป็นตัวเลข") from None
    if not math.isfinite(number):
        raise ValidationError(f"{field} ต้องเป็นจำนวนจำกัด (ไม่ใช่ NaN/infinity)")
    return number


def validate_simulation_input(params: dict, analysis: str = "dc") -> dict:
    """Validate simulator parameters and return a normalized float copy.

    Raises :class:`ValidationError` for an unknown analysis, a missing or
    non-numeric field, NaN/infinity, or a value outside its allowed range.
    The returned dict also carries ``analysis`` and ``warnings``.
    """
    if analysis not in ANALYSES:
        raise ValidationError(
            f"analysis ต้องเป็นหนึ่งใน {', '.join(ANALYSES)} (ได้รับ {analysis!r})"
        )
    if not isinstance(params, dict):
        raise ValidationError("พารามิเตอร์ต้องเป็น dict")

    normalized = dict(params)
    for field in RANGES:
        if field not in normalized:
            raise ValidationError(f"ไม่พบค่า {field}")
        normalized[field] = _to_float(field, normalized[field])

    for field, (low, high) in RANGES.items():
        value = normalized[field]
        if value < low or value > high:
            if low > 0 and value <= 0:
                raise ValidationError(f"{field} ต้องมากกว่า 0")
            raise ValidationError(
                f"{field} ต้องอยู่ระหว่าง {low:g} ถึง {high:g} (ได้รับ {value:g})"
            )

    warnings = []
    if normalized["amplitude_v"] > 0.2:
        warnings.append(
            "amplitude มากกว่า 0.2 V: ผลอาจไม่อยู่ในย่าน small-signal "
            "และ waveform อาจ clipping"
        )

    normalized["analysis"] = analysis
    normalized["warnings"] = warnings
    return normalized


def _spice_num(value: float) -> str:
    """Format a number for a netlist without scientific padding noise."""
    return f"{float(value):.12g}"


def build_netlist(params: dict, analysis: str, op_result: dict | None = None) -> str:
    """Build the CE voltage-divider netlist for one analysis.

    ``analysis`` is one of ``dc``, ``ac`` or ``tran``.  Transient runs
    require ``op_result`` so the coupling capacitors can be precharged from
    the DC operating point; without it the run raises ``ValidationError``.
    """
    p = validate_simulation_input(params, analysis)

    ic_cin = ""
    ic_cout = ""
    ic_directive = None

    if analysis == "tran":
        if not op_result:
            raise ValidationError("tran ต้องมี op_result สำหรับ precharge")
        vb = float(op_result.get("vb", 0.0))
        ve = float(op_result.get("ve", 0.0))
        vc = float(op_result.get("vc", 0.0))
        vout = float(op_result.get("vout", 0.0))
        vin = float(op_result.get("vin", 0.0))
        vcc = float(op_result.get("vcc", p["vcc_v"]))

        # CIN spans vin-base, COUT spans coll-out; charge both to their
        # DC operating-point voltages so the transient starts settled.
        ic_cin = f" IC={_spice_num(vin - vb)}"
        ic_cout = f" IC={_spice_num(vc - vout)}"
        ic_directive = (
            f".ic V(vin)={_spice_num(vin)} V(base)={_spice_num(vb)} "
            f"V(emit)={_spice_num(ve)} V(coll)={_spice_num(vc)} "
            f"V(out)={_spice_num(vout)} V(vcc)={_spice_num(vcc)}"
        )

    lines = [
        "* ENG29 2121 Lab 04 - CE voltage divider reference",
        ".options noacct",
        f"VCC vcc 0 {_spice_num(p['vcc_v'])}",
        (
            f"VIN vin 0 DC 0 AC 1 SIN(0 {_spice_num(p['amplitude_v'])} "
            f"{_spice_num(p['frequency_hz'])})"
        ),
        f"R1 vcc base {_spice_num(p['r1_ohm'])}",
        f"R2 base 0 {_spice_num(p['r2_ohm'])}",
        f"RC vcc coll {_spice_num(p['rc_ohm'])}",
        f"RE emit 0 {_spice_num(p['re_ohm'])}",
        f"Q1 coll base emit {DEFAULT_MODEL_NAME}",
        f"CIN vin base {_spice_num(p['cin_f'])}{ic_cin}",
        f"COUT coll out {_spice_num(p['cout_f'])}{ic_cout}",
        f"RL out 0 {_spice_num(p['rl_ohm'])}",
        f".model {DEFAULT_MODEL_NAME} {BJT_MODEL_CARD}",
    ]

    if analysis == "dc":
        lines.append(".op")
        lines.append(".print op @q1[ic] @q1[ib] @q1[ie]")
    elif analysis == "ac":
        lines.append(".ac dec 20 1 1meg")
        lines.append(".print ac vm(out) vp(out) vm(vin) vp(vin)")
    else:  # tran
        step = 1.0 / (p["frequency_hz"] * 200.0)
        stop = 5.0 / p["frequency_hz"]
        lines.append(ic_directive)
        lines.append(f".tran {_spice_num(step)} {_spice_num(stop)} UIC")
        lines.append(".print tran v(vin) v(out)")

    lines.append(".end")
    return "\n".join(lines) + "\n"


_NODE_ROW = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s+([-+0-9.eE]+)\s*$")
_Q1_CURRENT = re.compile(
    r"@q1\[(ic|ib|ie)\]\s+([-+0-9.eE]+)", re.IGNORECASE
)
_DEVICE_CURRENT = re.compile(r"^\s*(ic|ib|ie)\s+([-+0-9.eE]+)\s*$")


def _parse_node_table(lines) -> dict[str, float]:
    nodes: dict[str, float] = {}
    for index, line in enumerate(lines):
        if re.match(r"^\s*Node\s+Voltage\s*$", line):
            for row in lines[index + 1:]:
                if not row.strip():
                    break
                match = _NODE_ROW.match(row)
                if match:
                    nodes[match.group(1).lower()] = float(match.group(2))
            break
    return nodes


def _parse_q1_currents(lines) -> dict[str, float]:
    currents: dict[str, float] = {}
    for line in lines:
        match = _Q1_CURRENT.search(line)
        if match:
            currents[match.group(1).lower()] = float(match.group(2))
    return currents


def _parse_bjt_device_currents(lines) -> dict[str, float]:
    """Read ic/ib/ie from the ngspice BJT device table."""
    start = None
    for index, line in enumerate(lines):
        if line.strip() == "BJT: Bipolar Junction Transistor":
            start = index + 1
            break
    if start is None:
        return {}
    currents: dict[str, float] = {}
    for line in lines[start:]:
        if not line.strip():
            break
        match = _DEVICE_CURRENT.match(line)
        if match:
            currents[match.group(1).lower()] = float(match.group(2))
    return currents


def parse_op(log: str) -> dict:
    """Parse a real ngspice ``.op`` log into node voltages and currents.

    ``ic``, ``ib`` and ``ie`` are reported as positive magnitudes.  If the
    ``@q1[...]`` print table is missing, the values are taken from the
    ngspice BJT device table and a warning records that fallback.
    """
    if not log or not log.strip():
        raise ParseError("ngspice .op output ว่าง ไม่มีข้อมูลให้ parse")

    lines = log.splitlines()
    nodes = _parse_node_table(lines)
    if not nodes:
        raise ParseError("ไม่พบ node voltage table ใน ngspice .op output")

    warnings: list[str] = []
    currents = _parse_q1_currents(lines)
    if not all(key in currents for key in ("ic", "ib", "ie")):
        device = _parse_bjt_device_currents(lines)
        for key, value in device.items():
            currents.setdefault(key, value)
        if all(key in currents for key in ("ic", "ib", "ie")):
            warnings.append(
                "ไม่พบ @q1[...] ใน .op output: ใช้ค่ากระแสจาก BJT device table "
                "ของ ngspice แทน"
            )
    if not all(key in currents for key in ("ic", "ib", "ie")):
        raise ParseError("ไม่พบกระแส @q1[ic/ib/ie] ใน ngspice .op output")

    vb = nodes.get("base", 0.0)
    ve = nodes.get("emit", 0.0)
    vc = nodes.get("coll", 0.0)
    if "vin" in nodes:
        vin = nodes["vin"]
    else:
        vin = nodes.get("in", 0.0)
    vcc = nodes.get("vcc", 0.0)
    vout = nodes.get("out", 0.0)

    ic = abs(currents["ic"])
    ib = abs(currents["ib"])
    ie = abs(currents["ie"])
    vce = vc - ve

    if ic < 1e-9 or vb < 0.4:
        region = "cutoff"
    elif vce < 0.2:
        region = "saturation"
    else:
        region = "active"

    return {
        "nodes": nodes,
        "vb": vb,
        "ve": ve,
        "vc": vc,
        "vout": vout,
        "vin": vin,
        "vcc": vcc,
        "vce": vce,
        "ic": ic,
        "ib": ib,
        "ie": ie,
        "region": region,
        "warnings": warnings,
        "source": "ngspice .op",
    }
