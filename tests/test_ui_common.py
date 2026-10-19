import pytest
from agy_dash.ui import common


def test_fmt_tokens():
    assert common.fmt_tokens(0) == "0"
    assert common.fmt_tokens(999) == "999"
    assert common.fmt_tokens(1_500) == "1.5K"
    assert common.fmt_tokens(2_450_000) == "2.45M"
    assert common.fmt_tokens(3_100_000_000) == "3.10B"


def test_fmt_money():
    assert common.fmt_money(0, "INR") == "₹0.00"
    assert common.fmt_money(1250.5, "INR") == "₹1,250.50"
    assert common.fmt_money(12.34, "USD") == "$12.34"
    assert common.fmt_money(12.34, "EUR") == "€12.34"
    assert common.fmt_money(12.34, "GBP") == "£12.34"


def test_fmt_pct():
    assert common.fmt_pct(0.1234) == "12.3%"
    assert common.fmt_pct(0.1234, decimals=0) == "12%"
    assert common.fmt_pct(None) == "-"


def test_colors_palette():
    dark = common.colors("dark")
    light = common.colors("light")
    assert dark["bg"] == "#090A0F"
    assert light["bg"] == "#F6F7F9"
    assert "fresh" in dark and "cached" in dark and "cost" in dark
