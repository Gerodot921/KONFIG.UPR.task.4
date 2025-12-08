#!/usr/bin/env python3
import argparse
from xml.etree.ElementTree import Element, tostring

from lark import Lark, Transformer


# ----------------------
# Убираем комментарии
# ----------------------
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

        if text.startswith("NB.", i) or text.startswith("//", i):
            while i < n and text[i] not in "\r\n":
                i += 1
            continue

        out.append(text[i])
        i += 1

    if in_multi:
        raise SyntaxError("Unclosed multi-line comment")
    return "".join(out)


# ----------------------
# Грамматика
# ----------------------
GRAMMAR = r"""
start: stmt*

stmt: define
    | assign
    | value_stmt

define: "(" "define" NAME value ")"
assign: NAME "=" value ";"?

value_stmt: value ";"*

?value: const_read
      | NUMBER
      | STRING
      | NAME
      | array

const_read: "." "(" NAME ")" "."
array: "[" [value (";" value)* ";"?] "]"

// --- ИГНОРИРУЕМЫЕ СИМВОЛЫ ---

_WHITESPACE: /[\s\t\n\r\u00A0\uFEFF\u2000-\u200A\u202F\u205F\u3000]+/ 
%ignore _WHITESPACE

GARBAGE: /[^\[\]\(\);=@\.\"A-Za-z0-9_\u0400-\u04FF\)]+/
%ignore GARBAGE


NUMBER: /0[oO][0-7]+/
STRING: /@\"(?:\\.|[^"\\])*\"/
NAME: /[a-zA-Z][_a-zA-Z0-9]*/

"""


# ----------------------
# Transformer
# ----------------------
class ToAST(Transformer):
    def NUMBER(self, tok):
        return ("number", int(str(tok), 8))

    def STRING(self, tok):
        inner = str(tok)[2:-1]
        try:
            inner = bytes(inner, "utf-8").decode("unicode_escape")
        except Exception:
            pass
        return ("string", inner)

    def NAME(self, tok):
        return ("ident", str(tok))

    def const_read(self, children):
        return ("const", children[0][1])

    def array(self, children):
        return ("array", children)

    def define(self, children):
        if len(children) < 2:
            raise SyntaxError("Invalid define: missing name or value")
        name_node = children[0]
        value_node = children[1]
        return ("define", name_node[1], value_node)

    def assign(self, children):
        name_node = children[0]
        value_node = children[1]
        return ("assign", name_node[1], value_node)

    def value_stmt(self, children):
        return children[0]

    def stmt(self, children):
        return children[0]

    def start(self, children):
        return children


# ----------------------
# Evaluator
# ----------------------
class Evaluator:
    def __init__(self):
        self.consts = {}

    def eval(self, node):
        if node is None:
            return None
        t = node[0]
        if t == "number":
            return node[1]
        if t == "string":
            return node[1]
        if t == "ident":
            return node[1]
        if t == "array":
            return [self.eval(x) for x in node[1]]
        if t == "const":
            name = node[1]
            if name not in self.consts:
                raise NameError(f"Unknown constant {name}")
            return self.eval(self.consts[name])
        return None


# ----------------------
# XML
# ----------------------
def xml_value(v):
    if isinstance(v, int):
        e = Element("number");
        e.text = str(v);
        return e
    if isinstance(v, str):
        e = Element("string");
        e.text = v;
        return e
    if isinstance(v, list):
        e = Element("array")
        for x in v:
            e.append(xml_value(x))
        return e
    e = Element("null");
    return e


def indent(elem, level=0):
    nl = "\n"
    pad = "\t" * level
    i = nl + pad
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "\t"
        for child in elem:
            indent(child, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def xml_out(values):
    root = Element("root")
    for v in values:
        item = Element("item")
        if isinstance(v, tuple) and v[0] == "assign":
            _, name, val = v
            assign_el = Element("assign")
            n_el = Element("name");
            n_el.text = str(name)
            assign_el.append(n_el)
            assign_el.append(xml_value(val))
            item.append(assign_el)
        else:
            item.append(xml_value(v))
        root.append(item)
    indent(root)
    return tostring(root, encoding="unicode")


# ----------------------
# MAIN
# ----------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    args = ap.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        text = remove_comments(f.read())

    parser = Lark(GRAMMAR, start="start", parser="lalr")
    tree = parser.parse(text)
    ast = ToAST().transform(tree)

    evaluator = Evaluator()
    out_list = []

    for node in ast:
        if not isinstance(node, tuple):
            continue
        if node[0] == "define":
            _, name, val_node = node
            evaluator.consts[name] = val_node
            out_list.append(evaluator.eval(val_node))
        elif node[0] == "assign":
            _, name, val_node = node
            val = evaluator.eval(val_node)
            out_list.append(("assign", name, val))
        else:
            out_list.append(evaluator.eval(node))

    print(xml_out(out_list))


if __name__ == "__main__":
    main()
