"""Server-side SVG plots built only from parsed simulation arrays.

No chart library, no network requests, and no fabricated traces: every
coordinate comes from the lists produced by :mod:`spice_engine`.
"""

from __future__ import annotations

import math

TEAL = "#0c8078"
ORANGE = "#c47a1a"
NAVY = "#123658"
GRID = "#d5e2ec"
PANEL = "#fbfdff"
FONT = "Segoe UI, Arial, sans-serif"


def _engineering(value: float, unit: str) -> str:
    prefixes = (
        (1.0e9, "G"),
        (1.0e6, "M"),
        (1.0e3, "k"),
        (1.0, ""),
        (1.0e-3, "m"),
        (1.0e-6, "µ"),
        (1.0e-9, "n"),
        (1.0e-12, "p"),
    )
    magnitude = abs(value)
    if magnitude == 0:
        return f"0.00 {unit}"
    for scale, prefix in prefixes:
        if magnitude >= scale:
            scaled = value / scale
            decimals = max(
                0, 2 - int(math.floor(math.log10(abs(scaled))))
            )
            return f"{scaled:.{decimals}f} {prefix}{unit}"
    scaled = value / 1.0e-12
    decimals = max(0, 2 - int(math.floor(math.log10(abs(scaled)))))
    return f"{scaled:.{decimals}f} p{unit}"


def format_eng(value, unit: str) -> str:
    """Format a number with an engineering prefix and three significant digits."""
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(number):
        return "—"
    if unit == "dB":
        return f"{number:.2f} dB"
    if unit == "°":
        return f"{number:.1f} °"
    return _engineering(number, unit)


def _empty_svg(width: int, height: int, message: str = "No simulation data") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" role="img">'
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>'
        f'<text x="{width / 2:.1f}" y="{height / 2:.1f}" text-anchor="middle" '
        f'font-family="{FONT}" font-size="14" fill="{NAVY}">{message}</text>'
        "</svg>"
    )


def _map(value, low, high, out_low, out_high):
    if high == low:
        return (out_low + out_high) / 2.0
    return out_low + (value - low) / (high - low) * (out_high - out_low)


def _path(xs, ys) -> str:
    if not xs or not ys:
        return ""
    parts = [f"M {xs[0]:.2f} {ys[0]:.2f}"]
    parts.extend(f"L {x:.2f} {y:.2f}" for x, y in zip(xs[1:], ys[1:]))
    return " ".join(parts)


def _padded_range(low, high, minimum_pad):
    if not math.isfinite(low) or not math.isfinite(high):
        return 0.0, 1.0
    if high == low:
        return low - minimum_pad, high + minimum_pad
    pad = max((high - low) * 0.08, minimum_pad)
    return low - pad, high + pad


def _freq_label(frequency: float) -> str:
    for scale, suffix in ((1.0e9, "G"), (1.0e6, "M"), (1.0e3, "k"), (1.0, "")):
        if frequency >= scale:
            return f"{frequency / scale:g}{suffix}"
    return f"{frequency:g}"


def _decade_ticks(low_log, high_log):
    start = math.ceil(low_log - 1.0e-9)
    end = math.floor(high_log + 1.0e-9)
    return [float(exponent) for exponent in range(start, end + 1)]


def _panel(
    x, y, width, height, title, colour, xs, ys, x_label=None, y_label=None
) -> list[str]:
    elements = [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" '
        f'height="{height:.1f}" fill="{PANEL}" stroke="{GRID}" stroke-width="1"/>',
        f'<text x="{x:.1f}" y="{y - 10:.1f}" font-family="{FONT}" '
        f'font-size="13" font-weight="600" fill="{NAVY}">{title}</text>',
    ]
    if x_label:
        elements.append(
            f'<text x="{x + width / 2:.1f}" y="{y + height + 38:.1f}" '
            f'text-anchor="middle" font-family="{FONT}" font-size="12" '
            f'fill="{NAVY}">{x_label}</text>'
        )
    if y_label:
        elements.append(
            f'<text x="{x + 14:.1f}" y="{y + 16:.1f}" font-family="{FONT}" '
            f'font-size="11" fill="{NAVY}">{y_label}</text>'
        )
    elements.append(
        f'<path d="{_path(xs, ys)}" fill="none" stroke="{colour}" '
        f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
    )
    return elements


def bode_svg(ac: dict, width: int = 720, height: int = 440) -> str:
    """Render a two-panel Bode magnitude/phase SVG from parsed AC arrays."""
    freqs = [float(f) for f in ac.get("frequency_hz", []) if f and f > 0]
    gains = [float(g) for g in ac.get("gain_db", [])]
    phases = [float(p) for p in ac.get("phase_deg", [])]
    count = min(len(freqs), len(gains), len(phases))
    if count == 0:
        return _empty_svg(width, height)
    freqs, gains, phases = freqs[:count], gains[:count], phases[:count]

    logs = [math.log10(f) for f in freqs]
    low_log = min(logs)
    high_log = max(logs)
    if high_log - low_log < 1.0e-6:
        low_log -= 0.5
        high_log += 0.5

    left, right, top, gap, bottom = 74.0, 24.0, 42.0, 48.0, 66.0
    plot_width = width - left - right
    plot_height = max(70.0, (height - top - gap - bottom) / 2.0)
    top_a = top
    bottom_a = top_a + plot_height
    top_b = bottom_a + gap
    bottom_b = top_b + plot_height

    gain_low, gain_high = _padded_range(min(gains), max(gains), 0.5)
    phase_low, phase_high = _padded_range(min(phases), max(phases), 1.0)

    def x_at(log_frequency):
        return _map(log_frequency, low_log, high_log, left, left + plot_width)

    xs = [x_at(value) for value in logs]
    gain_ys = [
        _map(value, gain_low, gain_high, bottom_a, top_a) for value in gains
    ]
    phase_ys = [
        _map(value, phase_low, phase_high, bottom_b, top_b) for value in phases
    ]

    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Bode plot from ngspice data">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
    ]
    elements.extend(
        _panel(
            left,
            top_a,
            plot_width,
            plot_height,
            "Gain (dB)",
            TEAL,
            xs,
            gain_ys,
            y_label="dB",
        )
    )
    elements.extend(
        _panel(
            left,
            top_b,
            plot_width,
            plot_height,
            "Phase (°)",
            ORANGE,
            xs,
            phase_ys,
            x_label="Frequency (Hz)",
            y_label="deg",
        )
    )

    # Vertical decade grid and x labels on the lower panel.
    for exponent in _decade_ticks(low_log, high_log):
        x = x_at(exponent)
        elements.append(
            f'<line x1="{x:.1f}" y1="{top_a:.1f}" x2="{x:.1f}" '
            f'y2="{bottom_b:.1f}" stroke="{GRID}" stroke-width="1"/>'
        )
        elements.append(
            f'<text x="{x:.1f}" y="{bottom_b + 16:.1f}" text-anchor="middle" '
            f'font-family="{FONT}" font-size="10" fill="{NAVY}">'
            f"{_freq_label(10.0 ** exponent)}</text>"
        )

    # Horizontal grid and y labels for both panels.
    for step in range(5):
        fraction = step / 4.0
        for panel_top, panel_bottom, low, high in (
            (top_a, bottom_a, gain_low, gain_high),
            (top_b, bottom_b, phase_low, phase_high),
        ):
            y = panel_bottom - fraction * (panel_bottom - panel_top)
            value = low + fraction * (high - low)
            elements.append(
                f'<line x1="{left:.1f}" y1="{y:.1f}" '
                f'x2="{left + plot_width:.1f}" y2="{y:.1f}" '
                f'stroke="{GRID}" stroke-width="1"/>'
            )
            elements.append(
                f'<text x="{left - 8:.1f}" y="{y + 3:.1f}" '
                f'text-anchor="end" font-family="{FONT}" font-size="10" '
                f'fill="{NAVY}">{value:.1f}</text>'
            )

    elements.append("</svg>")
    return "".join(elements)


def tran_svg(tran: dict, width: int = 720, height: int = 360) -> str:
    """Render Vin/Vout transient waveforms from parsed tran arrays."""
    time_s = [float(t) for t in tran.get("time_s", [])]
    vin_v = [float(v) for v in tran.get("vin_v", [])]
    vout_v = [float(v) for v in tran.get("vout_v", [])]
    count = min(len(time_s), len(vin_v), len(vout_v))
    if count == 0:
        return _empty_svg(width, height)
    time_s, vin_v, vout_v = (
        time_s[:count],
        vin_v[:count],
        vout_v[:count],
    )

    duration = time_s[-1] - time_s[0]
    if duration >= 1.0e-3:
        time_scale, time_unit = 1.0e3, "ms"
    elif duration >= 1.0e-6:
        time_scale, time_unit = 1.0e6, "µs"
    else:
        time_scale, time_unit = 1.0e9, "ns"

    xs_data = [value * time_scale for value in time_s]
    vin_mv = [value * 1.0e3 for value in vin_v]
    vout_mv = [value * 1.0e3 for value in vout_v]

    left, right, top, bottom = 74.0, 24.0, 42.0, 62.0
    plot_width = width - left - right
    plot_height = height - top - bottom
    if plot_width <= 0 or plot_height <= 0:
        return _empty_svg(width, height)

    x_low, x_high = xs_data[0], xs_data[-1]
    if x_low == x_high:
        x_low -= 1.0
        x_high += 1.0
    y_low, y_high = _padded_range(
        min(min(vin_mv), min(vout_mv), 0.0),
        max(max(vin_mv), max(vout_mv), 0.0),
        0.5,
    )

    def x_at(value):
        return _map(value, x_low, x_high, left, left + plot_width)

    def y_at(value):
        return _map(value, y_low, y_high, top + plot_height, top)

    vin_ys = [y_at(value) for value in vin_mv]
    vout_ys = [y_at(value) for value in vout_mv]
    xs = [x_at(value) for value in xs_data]

    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Transient Vin and Vout from ngspice data">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<rect x="{left:.1f}" y="{top:.1f}" width="{plot_width:.1f}" '
        f'height="{plot_height:.1f}" fill="{PANEL}" stroke="{GRID}" '
        f'stroke-width="1"/>',
        f'<text x="{left:.1f}" y="{top - 12:.1f}" font-family="{FONT}" '
        f'font-size="13" font-weight="600" fill="{NAVY}">'
        "Transient waveform</text>",
    ]

    for step in range(6):
        fraction = step / 5.0
        x = left + fraction * plot_width
        value = x_low + fraction * (x_high - x_low)
        elements.append(
            f'<line x1="{x:.1f}" y1="{top:.1f}" x2="{x:.1f}" '
            f'y2="{top + plot_height:.1f}" stroke="{GRID}" stroke-width="1"/>'
        )
        elements.append(
            f'<text x="{x:.1f}" y="{top + plot_height + 16:.1f}" '
            f'text-anchor="middle" font-family="{FONT}" font-size="10" '
            f'fill="{NAVY}">{value:.3g}</text>'
        )

    for step in range(6):
        fraction = step / 5.0
        y = top + plot_height - fraction * plot_height
        value = y_low + fraction * (y_high - y_low)
        elements.append(
            f'<line x1="{left:.1f}" y1="{y:.1f}" '
            f'x2="{left + plot_width:.1f}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        elements.append(
            f'<text x="{left - 8:.1f}" y="{y + 3:.1f}" text-anchor="end" '
            f'font-family="{FONT}" font-size="10" fill="{NAVY}">'
            f"{value:.2f}</text>"
        )

    elements.extend(
        [
            f'<path d="{_path(xs, vin_ys)}" fill="none" stroke="{TEAL}" '
            f'stroke-width="1.8"/>',
            f'<path d="{_path(xs, vout_ys)}" fill="none" stroke="{ORANGE}" '
            f'stroke-width="1.8"/>',
            f'<line x1="{left + 12:.1f}" y1="{top + 14:.1f}" '
            f'x2="{left + 34:.1f}" y2="{top + 14:.1f}" stroke="{TEAL}" '
            f'stroke-width="2"/>',
            f'<text x="{left + 40:.1f}" y="{top + 18:.1f}" '
            f'font-family="{FONT}" font-size="11" fill="{NAVY}">Vin</text>',
            f'<line x1="{left + 78:.1f}" y1="{top + 14:.1f}" '
            f'x2="{left + 100:.1f}" y2="{top + 14:.1f}" '
            f'stroke="{ORANGE}" stroke-width="2"/>',
            f'<text x="{left + 106:.1f}" y="{top + 18:.1f}" '
            f'font-family="{FONT}" font-size="11" fill="{NAVY}">Vout</text>',
            f'<text x="{left + plot_width / 2:.1f}" '
            f'y="{top + plot_height + 40:.1f}" text-anchor="middle" '
            f'font-family="{FONT}" font-size="12" fill="{NAVY}">'
            f"Time ({time_unit})</text>",
            f'<text x="{left:.1f}" y="{top - 30:.1f}" '
            f'font-family="{FONT}" font-size="11" fill="{NAVY}">'
            "Voltage (mV)</text>",
        ]
    )
    elements.append("</svg>")
    return "".join(elements)


def bode_placeholder_svg(width: int = 720, height: int = 440) -> str:
    """Illustrative Bode placeholder for before any simulation runs."""
    muted = "#7a92a8"
    grid = "#dce7ee"
    left, top, bottom = 58.0, 30.0, 20.0
    plot_w = width - left - 16.0
    top_a = top
    plot_h = (height - top_a - bottom) / 2.0 - 10.0
    top_b = top_a + plot_h + 10.0
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Bode placeholder">'
        # Outer outline of the chart area
        f'<rect x="{left}" y="{top_a}" width="{plot_w}" height="{plot_h}" '
        f'fill="#f9fcfd" stroke="{grid}" stroke-width="1"/>'
        f'<rect x="{left}" y="{top_b}" width="{plot_w}" height="{plot_h}" '
        f'fill="#f9fcfd" stroke="{grid}" stroke-width="1"/>'
        # Guide line inside the first panel
        f'<line x1="{left + plot_w * 0.08}" y1="{top_a + 10}" '
        f'x2="{left + plot_w * 0.08}" y2="{top_a + plot_h - 10}" '
        f'stroke="{muted}" stroke-width="1" stroke-dasharray="6 4"/>'
        # An illustrative diagonal curve in the first panel
        f'<path d="M{left + plot_w * 0.15} {top_a + plot_h * 0.8} '
        f'L{left + plot_w * 0.3} {top_a + plot_h * 0.5} '
        f'L{left + plot_w * 0.55} {top_a + plot_h * 0.75} '
        f'L{left + plot_w * 0.8} {top_a + plot_h * 0.35}" '
        f'fill="none" stroke="{muted}" stroke-width="2" opacity="0.6"/>'
        f'<text x="{left + plot_w / 2:.1f}" y="{top_a + plot_h / 2 + 4:.1f}" '
        f'text-anchor="middle" font-family="{FONT}" font-size="13" '
        f'fill="{muted}" text-anchor="middle">Bode response (illustrative)</text>'
        f'<text x="{left + plot_w / 2:.1f}" y="{top_b + plot_h / 2 + 6:.1f}" '
        f'text-anchor="middle" font-family="{FONT}" font-size="13" '
        f'fill="{muted}">Input / Output waveforms (illustrative)</text>'
        f'<text x="{left + plot_w / 2:.1f}" y="{top_b + plot_h - 6:.1f}" '
        f'text-anchor="middle" font-family="{FONT}" font-size="10" '
        f'fill="{muted}">Time (ms)</text>'
        f'<text x="{left + plot_w - 100:.1f}" y="{top_a + 16:.1f}" '
        f'font-family="{FONT}" font-size="12" fill="{muted}">Gain (dB)</text>'
        f'<text x="{left + plot_w - 100:.1f}" y="{top_b + plot_h - 8:.1f}" '
        f'font-family="{FONT}" font-size="12" fill="{muted}">Phase (°)</text>'
        f'<text x="{left + plot_w - 100:.1f}" y="{top_b + plot_h - 8:.1f}" '
        f'font-family="{FONT}" font-size="12" fill="{muted}">Voltage (mV)</text>'
        f'<text x="{left + plot_w - 100:.1f}" y="{top_b + plot_h + 32:.1f}" '
        f'font-family="{FONT}" font-size="12" fill="{muted}">Vin (teal) / Vout (orange)</text>'
        "</svg>"
    )


def tran_placeholder_svg(width: int = 720, height: int = 360) -> str:
    """Illustrative transient placeholder for before any simulation runs."""
    return bode_placeholder_svg(width, height)
