import re
import argparse
from xml.etree.ElementTree import Element, tostring

# ==========================================
# ПРЕТТИ-ПРИНТ XML (ТАБУЛЯЦИЯ)
# ==========================================

def indent(elem, level=0):
    """
    Рекурсивно вставляет табуляцию в ElementTree.
    """
    i = "\n" + "\t" * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "\t"
        for child in elem:
            indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


# ==========================================
# УДАЛЕНИЕ КОММЕНТАРИЕВ
# ==========================================

def remove_comments(text: str) -> str:
    out = []
    i = 0
    n = len(text)
    in_multi = False

    while i < n:
        if not in_multi and text.startswith("/+", i):
            in_multi = True
            i += 2
            continue
        if in_multi and text.startswith("+/", i):
            in_multi = False
            i += 2
            continue
        if in_multi:
            i += 1
            continue

        if text.startswith("NB.", i):
            while i < n and text[i] not in "\r\n":
                i += 1
            continue

        out.append(text[i])
        i += 1

    if in_multi:
        raise SyntaxError("Unclosed multi-line comment")

    return "".join(out)


# ==========================================
# ЛЕКСЕР
# ==========================================

TOKEN_PATTERNS = [
    ("CONST_READ", r"\.\([a-zA-Z][_a-zA-Z0-9]*\)\."),
    ("DEFINE", r"\(define\b"),
    ("NUMBER", r"0[oO][0-7]+"),
    ("STRING", r'@"(?:\\.|[^"\\])*"'),
    ("LBRACK", r"\["),
    ("RBRACK", r"\]"),
    ("SEMICOL", r";"),
    ("ENDPAREN", r"\)"),
    ("IDENT", r"[a-zA-Z][_a-zA-Z0-9]*"),
    ("SKIP", r"[ \t\r\n]+"),
]

TOKEN_REGEX = [(name, re.compile("^" + pat)) for name, pat in TOKEN_PATTERNS]


class Lexer:
    def __init__(self, text):
        self.text = remove_comments(text)
        self.pos = 0
        self.n = len(self.text)
        self.tokens = []

    def tokenize(self):
        while self.pos < self.n:
            part = self.text[self.pos:]
            matched = False

            for name, cre in TOKEN_REGEX:
                m = cre.match(part)
                if m:
                    value = m.group(0)

                    if name == "SKIP":
                        self.pos += len(value)
                        matched = True
                        break

                    if name == "CONST_READ":
                        self.tokens.append(("CONST_READ", value[2:-2]))
                        self.pos += len(value)
                        matched = True
                        break

                    self.tokens.append((name, value))
                    self.pos += len(value)
                    matched = True
                    break

            if matched:
                continue

            self.pos += 1

        self.tokens.append(("EOF", ""))
        return self.tokens


# ==========================================
# ПАРСЕР
# ==========================================

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.i = 0
        self.constants = {}

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else ("EOF", "")

    def next(self):
        tok = self.peek()
        self.i += 1
        return tok

    def expect(self, kind):
        tok = self.peek()
        if tok[0] != kind:
            raise SyntaxError(f"Expected {kind}, got {tok}")
        self.i += 1
        return tok[1]

    def parse_all(self):
        out = []
        while True:
            kind, _ = self.peek()
            if kind == "EOF":
                break

            if kind in ("SEMICOL", "ENDPAREN"):
                self.next()
                continue

            if kind == "DEFINE":
                out.append(self.parse_define())
            else:
                out.append(self.parse_value())

        return out

    def parse_define(self):
        self.expect("DEFINE")
        name = self.expect("IDENT")
        value = self.parse_value()
        self.expect("ENDPAREN")
        self.constants[name] = value
        return ("define", name, value)

    def parse_value(self):
        kind, val = self.peek()

        if kind in ("SEMICOL", "ENDPAREN"):
            self.next()
            return self.parse_value()

        if kind == "CONST_READ":
            self.next()
            return ("const", val)

        if kind == "NUMBER":
            self.next()
            return ("number", int(val, 8))

        if kind == "STRING":
            self.next()
            return ("string", val[2:-1])

        if kind == "IDENT":
            self.next()
            return ("ident", val)

        if kind == "LBRACK":
            return self.parse_array()

        raise SyntaxError(f"Unexpected token: {self.peek()}")

    def parse_array(self):
        self.expect("LBRACK")
        arr = []
        while self.peek()[0] != "RBRACK":
            arr.append(self.parse_value())
            if self.peek()[0] == "SEMICOL":
                self.next()
        self.expect("RBRACK")
        return ("array", arr)


# ==========================================
# EVALUATOR
# ==========================================

class Evaluator:
    def __init__(self, consts):
        self.consts = consts

    def eval(self, node):
        t = node[0]

        if t == "number": return node[1]
        if t == "string": return node[1]
        if t == "ident": return node[1]
        if t == "array": return [self.eval(x) for x in node[1]]

        if t == "const":
            name = node[1]
            if name not in self.consts:
                raise NameError(f"Unknown constant {name}")
            return self.eval(self.consts[name])

        return None


# ==========================================
# XML
# ==========================================

def xml_value(v):
    if isinstance(v, int):
        e = Element("number"); e.text = str(v); return e
    if isinstance(v, str):
        e = Element("string"); e.text = v; return e
    if isinstance(v, list):
        e = Element("array")
        for x in v: e.append(xml_value(x))
        return e
    e = Element("null"); return e


def xml_out(values):
    root = Element("root")
    for v in values:
        item = Element("item")
        item.append(xml_value(v))
        root.append(item)

    # === вот тут вставляем табуляцию ===
    indent(root, 0)

    return tostring(root, encoding="unicode")


# ==========================================
# MAIN
# ==========================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    args = ap.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        text = f.read()

    tokens = Lexer(text).tokenize()
    parser = Parser(tokens)
    ast = parser.parse_all()

    evaluator = Evaluator(parser.constants)
    values = []

    for node in ast:
        if node[0] != "define":
            values.append(evaluator.eval(node))

    print(xml_out(values))


if __name__ == "__main__":
    main()
