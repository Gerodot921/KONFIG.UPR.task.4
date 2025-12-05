import subprocess
import tempfile
import os
import xml.etree.ElementTree as ET


MAIN = "main.py"   # путь к твоему main.py


def run(code: str) -> str:
    """Запускает программу с временным файлом и возвращает stdout."""
    with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as f:
        f.write(code)
        f_path = f.name

    try:
        out = subprocess.check_output(
            ["python", MAIN, "--input", f_path],
            stderr=subprocess.STDOUT,
            encoding="utf-8"
        )
        return out.strip()
    finally:
        os.remove(f_path)


def parse_xml(xml_str: str):
    """Парсит XML для удобства проверок."""
    return ET.fromstring(xml_str)


# =====================================================
# ТЕСТ 1 — числа, строки, массивы
# =====================================================

def test_basic_types():
    xml = run("[0o7; @" "hello" "; 0o10]")
    root = parse_xml(xml)

    arr = root.find("./item/array")
    assert arr is not None

    values = [x.text for x in arr]
    assert values == ["7", "hello", "8"]


# =====================================================
# ТЕСТ 2 — define и чтение констант
# =====================================================

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


# =====================================================
# ТЕСТ 3 — многострочный комментарий
# =====================================================

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


# =====================================================
# ТЕСТ 4 — NB. комментарии
# =====================================================

def test_singleline_comment():
    code = """
    NB. This is a comment
    0o12
    """

    xml = run(code)
    root = parse_xml(xml)
    n = root.find("./item/number").text
    assert n == "10"


# =====================================================
# ТЕСТ 5 — массивы с мусором, пробелами и лишними ;
# =====================================================

def test_arrays_with_garbage():
    code = """
    [ 0o1 ; 0o2 ; 0o3 ];;;;;
    """

    xml = run(code)
    root = parse_xml(xml)

    arr = root.find("./item/array")
    vals = [x.text for x in arr]

    assert vals == ["1", "2", "3"]


# =====================================================
# ТЕСТ 6 — поддержка кириллицы и PDF-мусора
# =====================================================

def test_ignore_garbage_symbols():
    code = """
    ООПППЖЖДЛФЫВФЫВПО
    ) ) ) // /л
    @"ok"
    """

    xml = run(code)
    root = parse_xml(xml)

    s = root.find("./item/string").text
    assert s == "ok"


# =====================================================
# ТЕСТ 7 — define + массив
# =====================================================

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


# =====================================================
# ТЕСТ 8 — XML форматирование
# =====================================================

def test_pretty_xml():
    code = "@\"ok\""
    xml = run(code)

    # Проверка, что есть табуляции
    assert "\t" in xml or "    " in xml  # таб или 4 пробела
