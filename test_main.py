import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET

MAIN = "main.py"

def run(code: str) -> str:
    f_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as f:
            f.write(code.strip())
            f_path = f.name

        out = subprocess.check_output(
            ["python", MAIN, "--input", f_path],
            stderr=subprocess.STDOUT,
            encoding="utf-8", errors="ignore"
        )
        return out.strip()

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Программа вернула ошибку:\n{e.output}") from e
    finally:
        if f_path:
            os.unlink(f_path)

def parse_xml(xml_str: str):
    if not xml_str:
        raise ValueError("Received empty string instead of XML.")
    return ET.fromstring(xml_str)

# =====================================================
# ТЕСТЫ
# =====================================================

def test_basic_types():
    xml = run("[0o7; @\"hello\"; 0o10]")
    root = parse_xml(xml)
    arr = root.find("./item/array")
    assert arr is not None
    values = [x.text for x in arr]
    assert values == ["7", "hello", "8"]

def test_define_and_const_read():
    code = """
    (define a 0o77)
    (define b @"hi")
    .(a).
    .(b).
    """
    xml = run(code)
    root = parse_xml(xml)
    nums = root.findall("./item/number")
    strs = root.findall("./item/string")
    assert nums[0].text == "63"
    assert strs[0].text == "hi"

def test_multiline_comment():
    code = """
    /+
        (define c 0o1)
        мусор внутри
    +/
    @"ok"
    """
    xml = run(code)
    root = parse_xml(xml)
    s = root.find("./item/string").text
    assert s == "ok"

def test_singleline_comment():
    code = """
    NB. This is a comment
    0o12
    """
    xml = run(code)
    root = parse_xml(xml)
    n = root.find("./item/number").text
    assert n == "10"

def test_arrays_with_garbage():
    code = "[ 0o1 ; 0o2 ; 0o3 ];;;;;"
    xml = run(code)
    root = parse_xml(xml)
    arr = root.find("./item/array")
    values = [x.text for x in arr]
    assert values == ["1", "2", "3"]


def test_define_array():
    code = """
    (define arr [0o1;0o2;0o3])
    .(arr).
    """
    xml = run(code)
    root = parse_xml(xml)
    arr = root.find("./item/array")
    vals = [x.text for x in arr]
    assert vals == ["1", "2", "3"]

def test_pretty_xml():
    code = "@\"ok\""
    xml = run(code)
    # Проверка наличия табов или пробелов в выводе XML
    assert "\t" in xml or "    " in xml
