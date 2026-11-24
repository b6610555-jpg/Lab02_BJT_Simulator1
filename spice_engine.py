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
import subprocess
import time
import uuid
from datetime import datetime
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


_AC_HEADER = re.compile(r"^\s*Index\s+frequency\s+(.+?)\s*$")
_AC_ROW = re.compile(
    r"^\s*(\d+)\s+([-+0-9.eE]+)((?:\s+[-+0-9.eE]+)*)\s*$"
)


def _parse_ac_tables(text: str) -> dict[int, dict]:
    """Merge every AC print table (ngspice paginates them) by row index."""
    series: dict[int, dict] = {}
    columns = None
    for line in text.splitlines():
        header = _AC_HEADER.match(line)
        if header:
            columns = header.group(1).split()
            continue
        if columns is None:
            continue
        row = _AC_ROW.match(line)
        if row:
            index = int(row.group(1))
            values = [float(value) for value in row.group(3).split()]
            record = series.setdefault(index, {"frequency": float(row.group(2))})
            for name, value in zip(columns, values):
                record[name] = value
        elif not line.strip():
            columns = None
    return series


def _unwrap_degrees(phases) -> list[float]:
    unwrapped: list[float] = []
    for phase in phases:
        value = phase
        if unwrapped:
            previous = unwrapped[-1]
            while value - previous > 180.0:
                value -= 360.0
            while value - previous < -180.0:
                value += 360.0
        unwrapped.append(value)
    return unwrapped


def parse_ac(log: str) -> dict:
    """Parse a real ngspice ``.ac`` log into Bode-ready arrays.

    ngspice prints magnitude/phase in separate, page-broken tables and the
    phase is in radians.  This returns sorted frequency, magnitude, gain in
    dB, and unwrapped phase in degrees relative to ``vin``.
    """
    if not log or not log.strip():
        raise ParseError("ngspice .ac output ว่าง ไม่มีข้อมูลให้ parse")

    series = _parse_ac_tables(log)
    if not series:
        raise ParseError("ไม่พบ AC table ใน ngspice .ac output")

    records = []
    for index in sorted(series):
        record = series[index]
        missing = [
            key
            for key in ("frequency", "vm(out)", "vp(out)", "vm(vin)", "vp(vin)")
            if key not in record
        ]
        if missing:
            raise ParseError(
                f"AC row {index} ไม่ครบ: ขาด {', '.join(missing)}"
            )
        if record["vm(vin)"] <= 0:
            raise ParseError(f"AC row {index}: |V(vin)| ต้องมากกว่า 0")
        records.append(record)

    frequency_hz = [record["frequency"] for record in records]
    vout_mag = [record["vm(out)"] for record in records]
    vin_mag = [record["vm(vin)"] for record in records]
    gain_db = [
        20.0 * math.log10(out / vin)
        for out, vin in zip(vout_mag, vin_mag)
    ]
    raw_phase = [
        math.degrees(record["vp(out)"] - record["vp(vin)"])
        for record in records
    ]
    phase_deg = _unwrap_degrees(raw_phase)

    return {
        "frequency_hz": frequency_hz,
        "vout_mag": vout_mag,
        "vin_mag": vin_mag,
        "gain_db": gain_db,
        "phase_deg": phase_deg,
        "source": "ngspice .ac",
    }


def interpolate_at(freqs, values, target):
    """Linearly interpolate ``values`` versus ``log10(frequency)``.

    Returns ``None`` for an empty series or a target outside the sweep, and
    the exact value when ``target`` matches a sample.
    """
    if not freqs or len(freqs) != len(values) or target is None:
        return None
    target = float(target)
    if target <= 0 or target < freqs[0] or target > freqs[-1]:
        return None
    if target == freqs[0]:
        return values[0]
    for index in range(1, len(freqs)):
        f1 = freqs[index]
        if target == f1:
            return values[index]
        if f1 > target:
            f0 = freqs[index - 1]
            v0 = values[index - 1]
            v1 = values[index]
            t = (math.log10(target) - math.log10(f0)) / (
                math.log10(f1) - math.log10(f0)
            )
            return v0 + t * (v1 - v0)
    return None


def find_cutoff(freqs, gain_db, side: str):
    """Find the first -3 dB crossing relative to the midband gain.

    ``side="low"`` looks for the first rising crossing; ``side="high"`` the
    first falling crossing.  Returns ``None`` when no crossing exists in the
    sweep.
    """
    if not freqs or len(freqs) != len(gain_db) or len(freqs) < 2:
        return None
    target = max(gain_db) - 3.0
    for index in range(1, len(gain_db)):
        previous = gain_db[index - 1]
        current = gain_db[index]
        crossed = (
            previous < target <= current
            if side == "low"
            else previous >= target > current
        )
        if crossed:
            f0, f1 = freqs[index - 1], freqs[index]
            g0, g1 = previous, current
            t = (target - g0) / (g1 - g0)
            return 10.0 ** (
                math.log10(f0) + t * (math.log10(f1) - math.log10(f0))
            )
    return None


def ac_metrics(data: dict, frequency_hz: float) -> dict:
    """Summarize parsed AC data at the user's frequency plus cutoffs."""
    freqs = data.get("frequency_hz", [])
    gains = data.get("gain_db", [])
    phases = data.get("phase_deg", [])

    gain_at = interpolate_at(freqs, gains, frequency_hz)
    phase_at = interpolate_at(freqs, phases, frequency_hz)
    gain_vv = 10.0 ** (gain_at / 20.0) if gain_at is not None else None

    return {
        "gain_db_at_frequency": gain_at,
        "gain_vv_at_frequency": gain_vv,
        "phase_deg_at_frequency": phase_at,
        "midband_gain_db": max(gains) if gains else None,
        "cutoff_low_hz": find_cutoff(freqs, gains, "low"),
        "cutoff_high_hz": find_cutoff(freqs, gains, "high"),
        "sweep_hz": {
            "min": freqs[0] if freqs else None,
            "max": freqs[-1] if freqs else None,
        },
    }


_TRAN_HEADER = re.compile(r"^\s*Index\s+time\s+(.+?)\s*$")
_TRAN_ROW = re.compile(
    r"^\s*(\d+)\s+([-+0-9.eE]+)((?:\s+[-+0-9.eE]+)*)\s*$"
)


def parse_tran(log: str) -> dict:
    """Parse a real ngspice ``.tran`` log into time-domain arrays."""
    if not log or not log.strip():
        raise ParseError("ngspice .tran output ว่าง ไม่มีข้อมูลให้ parse")

    records: dict[int, dict] = {}
    columns = None
    for line in log.splitlines():
        header = _TRAN_HEADER.match(line)
        if header:
            columns = header.group(1).split()
            continue
        if columns is None:
            continue
        row = _TRAN_ROW.match(line)
        if row:
            index = int(row.group(1))
            values = [float(value) for value in row.group(3).split()]
            record = records.setdefault(index, {"time": float(row.group(2))})
            for name, value in zip(columns, values):
                record[name] = value
        elif not line.strip():
            columns = None

    if not records:
        raise ParseError("ไม่พบ transient table ใน ngspice .tran output")

    time_s = []
    vin_v = []
    vout_v = []
    for index in sorted(records):
        record = records[index]
        missing = [
            key for key in ("time", "v(vin)", "v(out)") if key not in record
        ]
        if missing:
            raise ParseError(
                f"tran row {index} ไม่ครบ: ขาด {', '.join(missing)}"
            )
        time_s.append(record["time"])
        vin_v.append(record["v(vin)"])
        vout_v.append(record["v(out)"])

    return {
        "time_s": time_s,
        "vin_v": vin_v,
        "vout_v": vout_v,
        "source": "ngspice .tran",
    }


def tran_metrics(data: dict) -> dict:
    """Summarize parsed transient data using only the real arrays."""
    time_s = data.get("time_s") or []
    vin_v = data.get("vin_v") or []
    vout_v = data.get("vout_v") or []
    if not time_s or len(vin_v) != len(time_s) or len(vout_v) != len(time_s):
        raise ParseError("transient data ไม่ครบสำหรับคำนวณ metrics")

    vin_peak = max(abs(value) for value in vin_v)
    vout_peak = max(abs(value) for value in vout_v)
    index = max(range(len(vin_v)), key=lambda i: abs(vin_v[i]))
    phase_inverted = vin_v[index] * vout_v[index] < 0

    return {
        "vin_peak_v": vin_peak,
        "vout_peak_v": vout_peak,
        "vin_pp_v": max(vin_v) - min(vin_v),
        "vout_pp_v": max(vout_v) - min(vout_v),
        "gain_vv_peak": vout_peak / vin_peak if vin_peak else None,
        "peak_index": index,
        "phase_inverted": phase_inverted,
        "samples": len(time_s),
        "duration_s": time_s[-1] - time_s[0],
    }


def _log_excerpt(log_text: str, limit: int = 4000) -> str:
    return (log_text or "")[-limit:]


def _engine_name(exe: Path, text: str) -> str:
    match = re.search(r"ngspice-([0-9][0-9A-Za-z.]*)", text)
    if not match:
        match = re.search(r"ngspice-([0-9][0-9A-Za-z.]*)", str(exe))
    return f"ngspice-{match.group(1)}" if match else "ngspice"


def _run_ngspice(exe: Path, netlist: str, run_dir: Path, stem: str):
    """Write one netlist, run ngspice batch, and return its outputs."""
    netlist_path = run_dir / f"{stem}.cir"
    log_path = run_dir / f"{stem}.log"
    netlist_path.write_text(netlist, encoding="utf-8")

    try:
        completed = subprocess.run(
            [str(exe), "-b", "-o", str(log_path), str(netlist_path)],
            cwd=run_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=SIM_TIMEOUT_S,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SimulationError(
            f"ngspice ใช้เวลาเกิน {SIM_TIMEOUT_S:.0f} วินาที (timeout) "
            f"สำหรับ {netlist_path.name}"
        ) from exc

    log_text = ""
    if log_path.exists():
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
    excerpt = _log_excerpt(log_text)

    if completed.returncode != 0:
        raise SimulationError(
            f"ngspice exit code {completed.returncode}\n{excerpt}"
        )

    combined = f"{log_text}\n{completed.stdout or ''}"
    for marker in ("error", "fatal", "singular matrix", "timestep too small"):
        if marker in combined.lower():
            raise SimulationError(
                f"ngspice รายงาน '{marker}' ใน output\n{excerpt}"
            )

    if not log_text.strip():
        raise ParseError(f"ngspice ไม่ได้สร้าง log output ({log_path.name})")

    return netlist_path, log_path, log_text, completed.stdout or ""


def run_simulation(params: dict, analysis: str) -> dict:
    """Validate inputs, run the real ngspice analysis, and parse its output.

    Transient runs first execute and parse a ``.op`` netlist, then precharge
    the coupling capacitors from those operating-point voltages before the
    ``.tran ... UIC`` run.  No result is returned unless ngspice ran cleanly
    and its output parsed.
    """
    normalized = validate_simulation_input(params, analysis)
    exe = find_ngspice()
    started = time.perf_counter()

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
    run_dir = (
        Path(__file__).resolve().parent / "instance" / "sim_runs" / run_id
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    warnings = list(normalized["warnings"])
    stdout_parts: list[str] = []
    op_data = None

    if analysis == "tran":
        op_netlist = build_netlist(normalized, "dc")
        _, _, op_log, op_stdout = _run_ngspice(
            exe, op_netlist, run_dir, "op"
        )
        stdout_parts.append(op_stdout)
        op_data = parse_op(op_log)
        warnings.extend(op_data.get("warnings", []))

    netlist = build_netlist(normalized, analysis, op_result=op_data)
    _, log_path, log_text, stdout = _run_ngspice(
        exe, netlist, run_dir, "circuit"
    )
    stdout_parts.append(stdout)

    if analysis == "dc":
        data = parse_op(log_text)
        metrics = None
        warnings.extend(data.get("warnings", []))
    elif analysis == "ac":
        data = parse_ac(log_text)
        metrics = ac_metrics(data, normalized["frequency_hz"])
    else:
        data = parse_tran(log_text)
        metrics = tran_metrics(data)

    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 1)
    engine = _engine_name(exe, "\n".join([log_text, *stdout_parts, str(exe)]))

    return {
        "analysis": analysis,
        "engine": engine,
        "model": DEFAULT_MODEL_NAME,
        "model_card": BJT_MODEL_CARD,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "netlist": netlist,
        "log_excerpt": _log_excerpt(log_text),
        "log_path": str(log_path),
        "elapsed_ms": elapsed_ms,
        "warnings": warnings,
        "params": normalized,
        "data": data,
        "metrics": metrics,
        "op": op_data,
    }
