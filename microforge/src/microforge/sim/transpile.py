"""Transpilation de la logique d'un projet (C++ Arduino) vers du JavaScript exécutable par l'atelier.

La logique des modèles (``globals_extra``, ``setup_extra``, ``logic``) n'utilise qu'un sous-ensemble du
C++ Arduino : déclarations typées, tableaux, ``String``, ``if``/``for``/``while``, ternaires, transtypages,
``Serial``, ``millis``/``delay``/``map``/``constrain``/``random`` et les fonctions ``<instance>_<fonction>()``
des composants. Ce module l'analyse (analyseur à descente récursive) et produit du JavaScript :

* ``delay()`` devient ``await __delay()`` : le temps est **virtuel**, la simulation peut tourner ×60 ;
* les types sont suivis pour respecter l'arithmétique du C : division entière tronquée, débordement des
  ``uint8_t``/``int8_t`` (``teinte++`` repasse à 0 après 255), ``unsigned long`` modulo 2³², formatage des
  ``float`` à 2 décimales par ``Serial.print`` et ``String`` ;
* les appels ``oled_print(...)`` deviennent ``__P.oled.print(...)`` : le modèle de comportement JavaScript
  du composant (``sim/static/mfsim.js``) les reçoit ;
* toute construction inconnue lève :class:`TranspileError` (un test transpile tous les modèles).

L'``int`` est simulé sur 32 bits (ESP32, RP2040, ARM) ; sur Arduino Uno il fait 16 bits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from microforge.core.catalog import Catalog
from microforge.core.models import ProjectSpec


class TranspileError(ValueError):
    """Construction C++ hors du sous-ensemble pris en charge par l'atelier."""


# ------------------------------------------------------------------------------------------- lexique
_TOKEN = re.compile(
    r"""
    (?P<ws>\s+|//[^\n]*|/\*.*?\*/)
  | (?P<num>0[xX][0-9a-fA-F]+[uUlL]*|0[bB][01]+[uUlL]*
        |(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?[fFuUlL]*)
  | (?P<str>"(?:\\.|[^"\\\n])*")
  | (?P<chr>'(?:\\.|[^'\\\n])')
  | (?P<id>[A-Za-z_]\w*)
  | (?P<op><<=|>>=|\+\+|--|->|::|&&|\|\||==|!=|<=|>=|<<|>>|\+=|-=|\*=|/=|%=|&=|\|=|\^=
        |[-+*/%<>=!&|^~?:;,.(){}\[\]])
    """,
    re.VERBOSE | re.DOTALL,
)


@dataclass
class Tok:
    kind: str  # num, str, chr, id, op, eof
    text: str
    line: int


def tokenize(src: str) -> list[Tok]:
    toks: list[Tok] = []
    pos, line = 0, 1
    while pos < len(src):
        m = _TOKEN.match(src, pos)
        if not m:
            raise TranspileError(f"ligne {line} : caractère inattendu {src[pos]!r}")
        kind = m.lastgroup or ""
        text = m.group()
        if kind != "ws":
            if kind == "str" and toks and toks[-1].kind == "str":  # "a" "b" -> "ab"
                toks[-1].text = toks[-1].text[:-1] + text[1:]
            else:
                toks.append(Tok(kind, text, line))
        line += text.count("\n")
        pos = m.end()
    toks.append(Tok("eof", "", line))
    return toks


# ------------------------------------------------------------------------------------------- types
INT_TYPES = {"u8", "i8", "u16", "i16", "i32", "u32", "char", "bool"}
_TYPE_WORDS = {
    "void", "bool", "boolean", "char", "byte", "int", "long", "short", "unsigned", "signed",
    "float", "double", "uint8_t", "int8_t", "uint16_t", "int16_t", "uint32_t", "int32_t",
    "size_t", "String", "word",
}  # fmt: skip
_QUALIFIERS = {"const", "static", "volatile"}
OBJECT_TYPES = {"MFWebServer": "WebServer"}
_JS_RESERVED = {
    "arguments", "await", "class", "debugger", "delete", "enum", "eval", "export", "extends",
    "function", "implements", "import", "in", "instanceof", "interface", "let", "new", "of",
    "package", "private", "protected", "public", "super", "this", "typeof", "undefined", "var",
    "with", "yield", "NaN", "Infinity", "Math", "Number", "Object", "Array", "Promise",
    "map", "abs", "min", "max", "random", "isnan", "millis", "micros", "constrain", "Serial",
    "WiFi", "setup", "loop",
}  # fmt: skip


def canonical_type(words: list[str]) -> str:
    """Mots-clés C++ -> type canonique (u8, i8, u16, i16, i32, u32, char, bool, float, String, void)."""
    w = [x for x in words if x not in _QUALIFIERS]
    s = " ".join(w)
    if s in {"bool", "boolean"}:
        return "bool"
    if s in {"byte", "uint8_t", "unsigned char"}:
        return "u8"
    if s in {"int8_t", "signed char"}:
        return "i8"
    if s == "char":
        return "char"
    if s in {"uint16_t", "word", "unsigned short", "unsigned short int"}:
        return "u16"
    if s in {"int16_t", "short", "short int", "signed short"}:
        return "i16"
    if s in {"float", "double"}:
        return "float"
    if s in {"String", "void"}:
        return s
    if s.startswith("unsigned") or s in {"uint32_t", "size_t"}:
        return "u32"
    if s in {
        "int",
        "long",
        "long int",
        "long long",
        "int32_t",
        "signed",
        "signed int",
        "signed long",
    }:
        return "i32"
    raise TranspileError(f"type non pris en charge : {s!r}")


def _arith(a: str, b: str) -> str:
    if "float" in (a, b):
        return "float"
    if "u32" in (a, b):
        return "u32"
    return "i32"


def conv(code: str, src: str, dst: str) -> str:
    """Convertit une valeur JS de type C ``src`` vers ``dst`` (troncature, débordement, texte)."""
    if dst == src or dst in {"void", "any"} or src == "any":
        return code
    if dst == "bool":
        return code if src == "bool" else f"!!({code})"
    if dst == "float":
        return f"({code} ? 1 : 0)" if src == "bool" else code
    if dst == "String":
        return to_str(code, src)
    if dst == "cstr":
        return code
    if dst in INT_TYPES:
        if src == "bool":
            return f"({code} ? 1 : 0)"
        if src == "float":
            code = f"Math.trunc({code})"
        elif src in {"String", "cstr"}:
            raise TranspileError(f"conversion texte -> {dst} non prise en charge")
        if re.fullmatch(r"-?\d+", code) and _fits(int(code), dst):
            return code
        contained = {
            "u8": {"u16", "i16", "i32", "u32"},
            "i8": {"i16", "i32"},
            "char": {"i16", "i32"},
            "u16": {"i32", "u32"},
            "i16": {"i32"},
        }
        if src in contained and dst in contained[src]:
            return code
        wrap = {
            "u8": "(({}) & 255)",
            "i8": "(({}) << 24 >> 24)",
            "char": "(({}) << 24 >> 24)",
            "u16": "(({}) & 65535)",
            "i16": "(({}) << 16 >> 16)",
            "i32": "(({}) | 0)",
            "u32": "(({}) >>> 0)",
        }[dst]
        return wrap.format(code)
    if dst.startswith("arr:") or dst.startswith("obj:"):
        return code
    raise TranspileError(f"conversion {src} -> {dst} non prise en charge")


_RANGES = {
    "u8": (0, 255),
    "i8": (-128, 127),
    "char": (-128, 127),
    "u16": (0, 65535),
    "i16": (-32768, 32767),
    "i32": (-(2**31), 2**31 - 1),
    "u32": (0, 2**32 - 1),
    "bool": (0, 1),
}


def _fits(value: int, typ: str) -> bool:
    lo, hi = _RANGES[typ]
    return lo <= value <= hi


def to_str(code: str, src: str, digits: str | None = None) -> str:
    """Texte produit par ``String(x)`` / ``Serial.print(x)`` (float : 2 décimales par défaut)."""
    if src in {"String", "cstr"}:
        return code
    if src == "char":
        return f"String.fromCharCode({code})"
    if src == "float":
        return f"__ffmt({code}, {digits or 2})"
    if src == "bool":
        return f"({code} ? '1' : '0')"
    if src in INT_TYPES:
        return f"__ifmt({code}, {digits})" if digits else f"String({code})"
    raise TranspileError(f"impossible d'afficher une valeur de type {src}")


# ------------------------------------------------------------------------------------------- API
@dataclass
class ApiFn:
    ret: str
    params: list[str]  # types canoniques (les tableaux sont "arr:u8")


_SIG = re.compile(r"^\s*([A-Za-z_][\w\s\*&:<>]*?)\s+\$\{name\}_(\w+)\s*\(([^)]*)\)", re.M)


def _param_type(decl: str) -> str:
    decl = decl.split("=")[0].strip()
    if not decl:
        return "void"
    is_array = "[" in decl
    decl = re.sub(r"\[.*?\]", "", decl).replace("&", " ").replace("*", " * ")
    words = decl.split()[:-1]  # retire le nom du paramètre
    if "*" in words:
        return (
            "cstr" if "char" in words else "arr:" + canonical_type([w for w in words if w != "*"])
        )
    t = canonical_type(words)
    return f"arr:{t}" if is_array else t


def component_api(api_code: str) -> dict[str, ApiFn]:
    """Signatures ``<type> ${name}_<fn>(<params>)`` d'un bloc ``api`` de composant."""
    out = {}
    for m in _SIG.finditer(api_code or ""):
        ret = canonical_type(m.group(1).replace("const", "").split())
        params = [p for p in m.group(3).split(",") if p.strip()]
        out[m.group(2)] = ApiFn(ret, [_param_type(p) for p in params])
    return out


@dataclass
class _Fn:
    js: str
    ret: str
    awaits: bool = False


_RUNTIME_FNS = {
    "millis": _Fn("millis", "u32"),
    "micros": _Fn("micros", "u32"),
    "random": _Fn("__random", "i32"),
    "randomSeed": _Fn("__randomSeed", "void"),
    "isnan": _Fn("Number.isNaN", "bool"),
    "isinf": _Fn("__isinf", "bool"),
    "sqrt": _Fn("Math.sqrt", "float"),
    "pow": _Fn("Math.pow", "float"),
    "sin": _Fn("Math.sin", "float"),
    "cos": _Fn("Math.cos", "float"),
    "fabs": _Fn("Math.abs", "float"),
    "floor": _Fn("Math.floor", "float"),
    "ceil": _Fn("Math.ceil", "float"),
    "mf_time_hhmm": _Fn("__timeHHMM", "String"),
}
_CONSTANTS = {
    "HIGH": ("1", "i32"),
    "LOW": ("0", "i32"),
    "true": ("true", "bool"),
    "false": ("false", "bool"),
    "NAN": ("NaN", "float"),
    "PI": ("Math.PI", "float"),
    "DEC": ("10", "i32"),
    "HEX": ("16", "i32"),
    "BIN": ("2", "i32"),
    "WL_CONNECTED": ("3", "i32"),
}


# ------------------------------------------------------------------------------------------- analyse
@dataclass
class _Ctx:
    parts: dict[str, dict[str, ApiFn]]
    scopes: list[dict[str, str]] = field(default_factory=lambda: [{}])
    temps: int = 0
    in_lambda: int = 0

    def lookup(self, name: str) -> str | None:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def declare(self, name: str, typ: str) -> None:
        self.scopes[-1][name] = typ

    def temp(self) -> str:
        self.temps += 1
        return f"__t{self.temps}"


def js_name(name: str) -> str:
    return f"{name}_" if name in _JS_RESERVED else name


_BINARY_PREC = [
    {"||"},
    {"&&"},
    {"|"},
    {"^"},
    {"&"},
    {"==", "!="},
    {"<", ">", "<=", ">="},
    {"<<", ">>"},
    {"+", "-"},
    {"*", "/", "%"},
]
_ASSIGN = {"=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="}


class _Parser:
    def __init__(self, src: str, ctx: _Ctx) -> None:
        self.toks = tokenize(src)
        self.i = 0
        self.ctx = ctx

    # -- outils
    @property
    def tok(self) -> Tok:
        return self.toks[self.i]

    def peek(self, k: int = 1) -> Tok:
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def next(self) -> Tok:
        t = self.tok
        self.i += 1
        return t

    def accept(self, text: str) -> bool:
        if self.tok.text == text and self.tok.kind in {"op", "id"}:
            self.i += 1
            return True
        return False

    def expect(self, text: str) -> None:
        if not self.accept(text):
            self.fail(f"« {text} » attendu, « {self.tok.text or 'fin'} » trouvé")

    def fail(self, msg: str) -> None:
        raise TranspileError(f"ligne {self.tok.line} : {msg}")

    def at_type(self) -> bool:
        t = self.tok
        if t.kind != "id":
            return False
        if t.text in _QUALIFIERS or t.text in OBJECT_TYPES:
            return True
        if t.text not in _TYPE_WORDS:
            return False
        # « String(x) » en début d'instruction est une expression, « String s » une déclaration
        k = 1
        while self.peek(k).kind == "id" and self.peek(k).text in _TYPE_WORDS:
            k += 1
        return self.peek(k).kind == "id"

    def read_type(self) -> str:
        words = []
        while self.tok.kind == "id" and (
            self.tok.text in _TYPE_WORDS or self.tok.text in _QUALIFIERS
        ):
            words.append(self.next().text)
        return canonical_type(words)

    # -- instructions
    def program(self) -> list[str]:
        out: list[str] = []
        while self.tok.kind != "eof":
            out += self.statement()
        return out

    def block(self) -> list[str]:
        self.expect("{")
        self.ctx.scopes.append({})
        out: list[str] = []
        while not self.accept("}"):
            if self.tok.kind == "eof":
                self.fail("« } » manquant")
            out += self.statement()
        self.ctx.scopes.pop()
        return out

    def body(self, spin: bool = False) -> list[str]:
        """Corps d'un if/for/while : bloc ou instruction seule ; ``spin`` = fait avancer le temps."""
        head = ["await __spin();"] if spin else []
        if self.tok.text == "{":
            return head + self.block()
        self.ctx.scopes.append({})
        out = self.statement()
        self.ctx.scopes.pop()
        return head + out

    def statement(self) -> list[str]:
        t = self.tok
        if t.text == "{" and t.kind == "op":
            return ["{", *_indent(self.block()), "}"]
        if t.text == ";":
            self.next()
            return []
        if t.kind == "id":
            kw = t.text
            if kw == "if":
                return self.if_stmt()
            if kw == "for":
                return self.for_stmt()
            if kw == "while":
                self.next()
                self.expect("(")
                cond = self.cond()
                self.expect(")")
                return [f"while ({cond}) {{", *_indent(self.body(spin=True)), "}"]
            if kw == "do":
                self.next()
                body = self.body(spin=True)
                self.expect("while")
                self.expect("(")
                cond = self.cond()
                self.expect(")")
                self.expect(";")
                return ["do {", *_indent(body), f"}} while ({cond});"]
            if kw in {"break", "continue"}:
                self.next()
                self.expect(";")
                return [f"{kw};"]
            if kw == "return":
                self.next()
                if self.accept(";"):
                    return ["return;"]
                code, _ = self.expr()
                self.expect(";")
                return [f"return {code};"]
            if self.at_type():
                out = self.declaration()
                self.expect(";")
                return out
        code, _ = self.expr(statement=True)
        self.expect(";")
        return [f"{code};"]

    def if_stmt(self) -> list[str]:
        self.expect("if")
        self.expect("(")
        cond = self.cond()
        self.expect(")")
        out = [f"if ({cond}) {{", *_indent(self.body()), "}"]
        if self.accept("else"):
            if self.tok.text == "if":
                nested = self.if_stmt()
                out[-1] = "} else " + nested[0]
                out += nested[1:]
            else:
                out[-1] = "} else {"
                out += [*_indent(self.body()), "}"]
        return out

    def for_stmt(self) -> list[str]:
        self.expect("for")
        self.expect("(")
        self.ctx.scopes.append({})
        init = ""
        if not self.accept(";"):
            if self.at_type():
                init = " ".join(self.declaration(single_line=True)).rstrip(";")
            else:
                init, _ = self.expr(statement=True)
            self.expect(";")
        cond = "" if self.tok.text == ";" else self.cond()
        self.expect(";")
        step = "" if self.tok.text == ")" else self.expr(statement=True)[0]
        self.expect(")")
        body = self.body()
        self.ctx.scopes.pop()
        return [f"for ({init}; {cond}; {step}) {{", *_indent(body), "}"]

    def declaration(self, single_line: bool = False) -> list[str]:
        is_const = self.tok.text == "const"
        if self.tok.text in OBJECT_TYPES:
            cls = OBJECT_TYPES[self.next().text]
            name = self.next().text
            args = []
            if self.accept("("):
                args = self.args()
            self.ctx.declare(name, f"obj:{cls}")
            return [f"const {js_name(name)} = new __rt.{cls}({', '.join(a for a, _ in args)});"]
        typ = self.read_type()
        decls = []
        while True:
            if self.tok.kind != "id":
                self.fail("nom de variable attendu")
            name = self.next().text
            vtype = typ
            init: str | None = None
            if self.accept("["):
                size = None
                if not self.accept("]"):
                    size, _ = self.expr()
                    self.expect("]")
                vtype = f"arr:{typ}"
                if self.accept("="):
                    self.expect("{")
                    items = []
                    while not self.accept("}"):
                        code, t = self.expr(no_comma=True)
                        items.append(conv(code, t, typ))
                        self.accept(",")
                    if size is not None and len(items) < int(_int_value(size)):
                        items += ["0"] * (int(_int_value(size)) - len(items))
                    init = "[" + ", ".join(items) + "]"
                else:
                    if size is None:
                        self.fail("taille de tableau manquante")
                    fill = '""' if typ == "String" else ("false" if typ == "bool" else "0")
                    init = f"new Array({size}).fill({fill})"
            elif self.accept("="):
                code, t = self.expr(no_comma=True)
                init = conv(code, t, typ)
            else:
                init = {"String": '""', "bool": "false"}.get(typ, "0")
            self.ctx.declare(name, vtype)
            decls.append(f"{js_name(name)} = {init}")
            if not self.accept(","):
                break
        kw = "const" if is_const else "let"
        if single_line:
            return [f"{kw} {', '.join(decls)};"]
        return [f"{kw} {d};" for d in decls]

    def cond(self) -> str:
        return self.expr()[0]  # la véracité JS des nombres est celle du C

    # -- expressions
    def expr(self, statement: bool = False, no_comma: bool = False) -> tuple[str, str]:
        nxt = self.peek(2)
        if (
            statement
            and self.tok.kind == "id"
            and self.peek().text in {"++", "--"}
            and nxt.text in {";", ")", ","}
            and self.ctx.lookup(self.tok.text) is not None
        ):
            name = self.next().text
            delta = "+ 1" if self.next().text == "++" else "- 1"
            t = self.ctx.lookup(name) or "i32"
            js = js_name(name)
            return f"{js} = {conv(f'{js} {delta}', _promote(t), t)}", t
        code, t = self.assignment(statement)
        if not no_comma and self.tok.text == ",":
            parts = [code]
            while self.accept(","):
                c, t = self.assignment(statement)
                parts.append(c)
            return "(" + ", ".join(parts) + ")", t
        return code, t

    def assignment(self, statement: bool = False) -> tuple[str, str]:
        start = self.i
        left, ltype = self.ternary()
        op = self.tok.text
        if self.tok.kind == "op" and op in _ASSIGN:
            if not _is_lvalue(self.toks, start, self.i):
                self.fail("affectation vers une expression non modifiable")
            self.next()
            right, rtype = self.assignment()
            if op == "=":
                value = conv(right, rtype, ltype)
            elif ltype == "String" and op == "+=":
                value = f"{left} + {to_str(right, rtype)}"
            else:
                value, vtype = self.binary(left, ltype, op[:-1], right, rtype)
                value = conv(value, vtype, ltype)
            code = f"{left} = {value}"
            return (code if statement else f"({code})"), ltype
        return left, ltype

    def ternary(self) -> tuple[str, str]:
        cond, ctype = self.binary_level(0)
        if self.accept("?"):
            a, at = self.assignment()
            self.expect(":")
            b, bt = self.assignment()
            if "String" in (at, bt) or "cstr" in (at, bt):
                t = "String" if "String" in (at, bt) else "cstr"
                return f"({cond} ? {conv(a, at, t)} : {conv(b, bt, t)})", t
            if at == bt:
                return f"({cond} ? {a} : {b})", at
            t = _arith(at, bt)
            return f"({cond} ? {conv(a, at, t)} : {conv(b, bt, t)})", t
        return cond, ctype

    def binary_level(self, level: int) -> tuple[str, str]:
        if level == len(_BINARY_PREC):
            return self.unary()
        left, lt = self.binary_level(level + 1)
        while self.tok.kind == "op" and self.tok.text in _BINARY_PREC[level]:
            op = self.next().text
            right, rt = self.binary_level(level + 1)
            left, lt = self.binary(left, lt, op, right, rt)
        return left, lt

    def binary(self, a: str, at: str, op: str, b: str, bt: str) -> tuple[str, str]:
        texts = {"String", "cstr"}
        if op == "+" and (at in texts or bt in texts):
            return f"({to_str(a, at)} + {to_str(b, bt)})", "String"
        if op in {"&&", "||"}:
            a2 = a if at == "bool" else f"!!({a})"
            b2 = b if bt == "bool" else f"!!({b})"
            return f"({a2} {op} {b2})", "bool"
        if op in {"==", "!=", "<", ">", "<=", ">="}:
            js = {"==": "===", "!=": "!=="}.get(op, op)
            if (at == "bool") != (bt == "bool") and at not in texts and bt not in texts:
                a, b = conv(a, at, "i32"), conv(b, bt, "i32")
            return f"({a} {js} {b})", "bool"
        if at in texts or bt in texts or at.startswith(("arr:", "obj:")):
            raise TranspileError(f"opération « {op} » impossible sur {at} et {bt}")
        if op in {"<<", ">>"}:
            lt = "u32" if at == "u32" else "i32"
            a, b = conv(a, at, "i32" if at != "u32" else "u32"), conv(b, bt, "i32")
            if op == "<<":
                return (f"(({a} << {b}) >>> 0)" if lt == "u32" else f"({a} << {b})"), lt
            return (f"({a} >>> {b})" if lt == "u32" else f"({a} >> {b})"), lt
        t = _arith(at, bt)
        if t == "float":
            return f"({conv(a, at, 'float')} {op} {conv(b, bt, 'float')})", "float"
        a, b = conv(a, at, t), conv(b, bt, t)
        if op in {"&", "|", "^"}:
            return (f"(({a} {op} {b}) >>> 0)" if t == "u32" else f"({a} {op} {b})"), t
        if op == "*":
            return (f"(Math.imul({a}, {b}) >>> 0)" if t == "u32" else f"Math.imul({a}, {b})"), t
        if op == "/":
            return f"__idiv({a}, {b}, {'true' if t == 'u32' else 'false'})", t
        if op == "%":
            return f"__imod({a}, {b}, {'true' if t == 'u32' else 'false'})", t
        wrap = ">>> 0" if t == "u32" else "| 0"
        return f"(({a} {op} {b}) {wrap})", t

    def unary(self) -> tuple[str, str]:
        t = self.tok
        if t.kind == "op":
            if t.text == "!":
                self.next()
                code, ct = self.unary()
                return f"!({code})", "bool"
            if t.text == "-":
                self.next()
                code, ct = self.unary()
                if ct == "float":
                    return f"(-{code})", "float"
                if re.fullmatch(r"\d+", code):
                    return f"-{code}", "i32"
                if ct == "u32":
                    return f"((-{code}) >>> 0)", "u32"
                return f"((-{conv(code, ct, 'i32')}) | 0)", "i32"
            if t.text == "+":
                self.next()
                return self.unary()
            if t.text == "~":
                self.next()
                code, ct = self.unary()
                return (f"(~{code} >>> 0)" if ct == "u32" else f"(~{code})"), (
                    "u32" if ct == "u32" else "i32"
                )
            if t.text in {"++", "--"}:
                self.next()
                start = self.i
                code, ct = self.unary()
                if not _is_lvalue(self.toks, start, self.i):
                    self.fail("++/-- sur une expression non modifiable")
                delta = "+ 1" if t.text == "++" else "- 1"
                return f"({code} = {conv(f'{code} {delta}', _promote(ct), ct)})", ct
            if t.text == "(" and self._is_cast():
                self.next()
                typ = self.read_type()
                self.expect(")")
                code, ct = self.unary()
                return conv(code, ct, typ), typ
        return self.postfix()

    def _is_cast(self) -> bool:
        k = 1
        if not (self.peek(k).kind == "id" and self.peek(k).text in _TYPE_WORDS | _QUALIFIERS):
            return False
        while self.peek(k).kind == "id" and self.peek(k).text in _TYPE_WORDS | _QUALIFIERS:
            k += 1
        return self.peek(k).text == ")"

    def postfix(self) -> tuple[str, str]:
        start = self.i
        code, t = self.primary()
        while True:
            if self.accept("["):
                idx, _ = self.expr()
                self.expect("]")
                if not t.startswith("arr:"):
                    self.fail("indexation d'une valeur qui n'est pas un tableau")
                code, t = f"{code}[{idx}]", t[4:]
            elif self.tok.text in {"++", "--"} and self.tok.kind == "op":
                if not _is_lvalue(self.toks, start, self.i):
                    self.fail("++/-- sur une expression non modifiable")
                op = self.next().text
                delta = "+ 1" if op == "++" else "- 1"
                tmp = self.ctx.temp()
                code = f"({tmp} = {code}, {code} = {conv(f'{tmp} {delta}', _promote(t), t)}, {tmp})"
            else:
                return code, t

    def args(self) -> list[tuple[str, str]]:
        out = []
        if self.accept(")"):
            return out
        while True:
            out.append(self.assignment())
            if self.accept(")"):
                return out
            self.expect(",")

    def primary(self) -> tuple[str, str]:
        t = self.next()
        if t.kind == "num":
            return _number(t.text)
        if t.kind == "str":
            return t.text, "cstr"
        if t.kind == "chr":
            return str(ord(_unescape(t.text[1:-1]))), "char"
        if t.kind == "op" and t.text == "(":
            code, ct = self.expr()
            self.expect(")")
            return f"({code})", ct
        if t.kind == "op" and t.text == "[":
            return self.lambda_()
        if t.kind != "id":
            self.i -= 1
            self.fail(f"expression attendue, « {t.text} » trouvé")
        name = t.text
        if self.tok.text == "." and self.tok.kind == "op":
            return self.member(name)
        if self.tok.text == "(":
            self.next()
            return self.call(name, self.args())
        if name in _CONSTANTS:
            return _CONSTANTS[name]
        typ = self.ctx.lookup(name)
        if typ is None:
            self.i -= 1
            self.fail(f"identifiant inconnu « {name} »")
        return js_name(name), typ

    def lambda_(self) -> tuple[str, str]:
        while not self.accept("]"):
            self.next()
        self.expect("(")
        self.expect(")")
        self.ctx.in_lambda += 1
        body = self.block()
        self.ctx.in_lambda -= 1
        return "(async () => {\n" + "\n".join(_indent(body)) + "\n})", "fn"

    def member(self, obj: str) -> tuple[str, str]:
        self.expect(".")
        meth = self.next().text
        self.expect("(")
        args = self.args()
        if obj == "Serial":
            if meth in {"begin", "flush", "setTimeout"}:
                return "undefined", "void"
            if meth in {"print", "println"}:
                if not args:
                    return f"Serial.{meth}('')", "void"
                code, ct = args[0]
                digits = args[1][0] if len(args) > 1 else None
                return f"Serial.{meth}({to_str(code, ct, digits)})", "void"
            if meth == "available":
                return "0", "i32"
        if obj == "WiFi":
            if meth == "status":
                return "WiFi.status()", "i32"
            if meth == "localIP":
                return "WiFi.localIP()", "String"
        typ = self.ctx.lookup(obj)
        if typ == "String":
            if meth == "length" and not args:
                return f"{js_name(obj)}.length", "i32"
            if meth == "toInt" and not args:
                return f"__toInt({js_name(obj)})", "i32"
        if typ == "obj:WebServer":
            js = ", ".join(conv(c, ct, "any") for c, ct in args)
            call = f"{js_name(obj)}.{meth}({js})"
            if meth == "handleClient":
                return f"(await {call})", "void"
            return call, "void"
        self.fail(f"méthode non prise en charge : {obj}.{meth}()")
        raise AssertionError  # pragma: no cover

    def call(self, name: str, args: list[tuple[str, str]]) -> tuple[str, str]:
        if name == "delay":
            return f"(await __delay({args[0][0]}))", "void"
        if name == "delayMicroseconds":
            return f"(await __delay(({args[0][0]}) / 1000))", "void"
        if name in {"F", "PSTR"}:
            return args[0]
        if name == "String":
            if not args:
                return '""', "String"
            code, ct = args[0]
            return to_str(code, ct, args[1][0] if len(args) > 1 else None), "String"
        if name in _TYPE_WORDS and name != "void":  # transtypage fonctionnel : int(x), byte(x)
            typ = canonical_type([name])
            return conv(args[0][0], args[0][1], typ), typ
        if name == "map":
            return f"__map({', '.join(conv(c, t, 'i32') for c, t in args)})", "i32"
        if name in {"constrain", "min", "max", "abs"}:
            types = [t for _, t in args]
            rt = types[0]
            for other in types[1:]:
                rt = _arith(rt, other) if rt != other else rt
            if rt in {"u8", "i8", "u16", "i16", "char", "bool"}:
                rt = "i32"
            js = {
                "constrain": "__constrain",
                "min": "Math.min",
                "max": "Math.max",
                "abs": "Math.abs",
            }
            return f"{js[name]}({', '.join(conv(c, t, rt) for c, t in args)})", rt
        if name in _RUNTIME_FNS:
            fn = _RUNTIME_FNS[name]
            return f"{fn.js}({', '.join(c for c, _ in args)})", fn.ret
        for part, api in self.ctx.parts.items():
            prefix = part + "_"
            if name.startswith(prefix) and name[len(prefix) :] in api:
                meth = name[len(prefix) :]
                fn = api[meth]
                js_args = [
                    conv(c, t, fn.params[i]) if i < len(fn.params) else c
                    for i, (c, t) in enumerate(args)
                ]
                return f"__P.{part}.{meth}({', '.join(js_args)})", fn.ret
        self.i -= 1
        self.fail(f"fonction inconnue « {name}() »")
        raise AssertionError  # pragma: no cover


def _promote(t: str) -> str:
    return "float" if t == "float" else ("u32" if t == "u32" else "i32")


def _is_lvalue(toks: list[Tok], start: int, end: int) -> bool:
    """Variable ou élément de tableau (« a », « a[i] ») : seules cibles d'affectation admises."""
    seg = toks[start:end]
    return bool(seg) and seg[0].kind == "id" and (len(seg) == 1 or seg[1].text == "[")


def _unescape(s: str) -> str:
    return s.encode("utf-8").decode("unicode_escape") if "\\" in s else s


def _int_value(code: str) -> int:
    return int(code, 0)


def _number(text: str) -> tuple[str, str]:
    low = text.lower()
    if low.startswith(("0x", "0b")):
        digits = low.rstrip("ul")
        value = int(digits, 0)
        unsigned = "u" in low[2:].lstrip("0123456789abcdef") or value > 0x7FFFFFFF
        return str(value), ("u32" if unsigned else "i32")
    if any(c in low for c in ".e") or low.endswith("f"):
        return low.rstrip("f"), "float"
    digits = low.rstrip("ul")
    unsigned = "u" in low[len(digits) :] or int(digits) > 0x7FFFFFFF
    return str(int(digits)), ("u32" if unsigned else "i32")


def _indent(lines: list[str]) -> list[str]:
    return ["  " + line for line in lines]


# ------------------------------------------------------------------------------------------- API
def part_apis(catalog: Catalog, spec: ProjectSpec) -> dict[str, dict[str, ApiFn]]:
    """Fonctions disponibles pour chaque instance du projet (variante de code ``default``)."""
    out = {}
    for part in spec.parts:
        comp = catalog.components.get(part.component)
        code = comp.code.get("default") if comp and comp.code else None
        if code is None and comp and comp.code:
            code = next(iter(comp.code.values()))
        out[part.name] = component_api(code.api if code else "")
    return out


def transpile(catalog: Catalog, spec: ProjectSpec) -> str:
    """JavaScript du projet : corps d'une fonction ``(__rt) => {setup, loop}``."""
    ctx = _Ctx(parts=part_apis(catalog, spec))
    globals_js = _Parser(spec.globals_extra, ctx).program()
    ctx.scopes.append({})
    setup_js = _Parser(spec.setup_extra, ctx).program()
    ctx.scopes.pop()
    ctx.scopes.append({})
    loop_js = _Parser(spec.logic, ctx).program()
    ctx.scopes.pop()
    temps = [f"__t{i}" for i in range(1, ctx.temps + 1)]
    lines = [
        f"// « {spec.title} » : logique C++ transpilée par MicroForge pour l'atelier.",
        '"use strict";',
        "const {__delay, __spin, __ffmt, __ifmt, __idiv, __imod, __map, __constrain, __random,",
        "  __randomSeed, __isinf, __toInt, __timeHHMM, millis, micros, Serial, WiFi} = __rt;",
        "const __P = __rt.parts;",
    ]
    if temps:
        lines.append(f"let {', '.join(temps)};")
    lines += globals_js
    lines += ["async function setup() {", *_indent(setup_js), "}"]
    lines += ["async function loop() {", *_indent(loop_js), "}"]
    lines.append("return { setup, loop };")
    return "\n".join(lines) + "\n"
