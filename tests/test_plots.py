from plots import format_eng, bode_svg, tran_svg


def test_format_eng():
    assert format_eng(0.00146, "A") == "1.46 mA"
    assert format_eng(0.010, "V") == "10.0 mV"
    assert format_eng(1000, "Hz") == "1.00 kHz"
    assert format_eng(2200, "Ω") == "2.20 kΩ"
    assert format_eng(-179.87, "°") == "-179.9 °"
    assert format_eng(None, "V") == "—"


def test_bode_svg_contains_axes_and_changes_with_data():
    a = {
        "frequency_hz": [1, 10, 100],
        "gain_db": [-10, 0, 5],
        "phase_deg": [-90, -120, -150],
        "vout_mag": [0.1, 1, 2],
        "vin_mag": [1, 1, 1],
    }
    b = {**a, "gain_db": [-20, -10, -5]}
    svg = bode_svg(a)
    assert "<svg" in svg
    assert "Frequency (Hz)" in svg
    assert "Gain (dB)" in svg
    assert "Phase (°)" in svg
    assert bode_svg(a) != bode_svg(b)


def test_tran_svg_contains_two_series_and_units():
    d = {
        "time_s": [0, 0.001, 0.002],
        "vin_v": [0, 0.01, 0],
        "vout_v": [0, -0.017, 0],
    }
    svg = tran_svg(d)
    assert "<svg" in svg
    assert "Vin" in svg and "Vout" in svg
    assert "Time (ms)" in svg
    assert "mV" in svg


def test_empty_plots_show_message():
    assert "No simulation data" in bode_svg({})
    assert "No simulation data" in tran_svg({})
