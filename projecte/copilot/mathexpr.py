"""Exact arithmetic for the solver: read option values, and evaluate an expression safely.

The model is bad at computing ("2 + 3 x 4" -> 24) but can often write the
right expression. It writes one (a grammar allows nothing else), Python
computes it here, and the value is matched against the options.

Only the standard library. Nothing here calls eval(): the expression is
parsed into a tree and only numbers and + - * / ^ are allowed, with limits.
"""
import ast
import operator
import re

# Only these characters can come out of the grammar
GRAMMAR = r'''root ::= expr
expr ::= term (" "? [-+] " "? term){0,12}
term ::= factor (" "? [*/^] " "? factor){0,12}
factor ::= "-"? (num | "(" " "? expr " "? ")")
num ::= [0-9]{1,7} ("." [0-9]{1,4})?'''

MAX_CHARS = 120
MAX_ABS = 1e12
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow}


def evaluate(text):
    """The value of an arithmetic expression, or None if it's not one we accept."""
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_CHARS:
        return None
    text = normalize(text).replace("^", "**")
    if re.search(r"[^0-9.+\-*/() ]", text):
        return None
    try:
        tree = ast.parse(text, mode="eval")
        value = _value(tree.body)
    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError, RecursionError, TypeError):
        return None
    if value is None or isinstance(value, complex) or abs(value) > MAX_ABS:
        return None
    return float(value)


def _value(node):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        inner = _value(node.operand)
        return -inner if isinstance(node.op, ast.USub) else inner
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _value(node.left), _value(node.right)
        if isinstance(node.op, ast.Pow) and (abs(right) > 12 or abs(left) > 1e6):
            raise ValueError("power too large")
        result = _OPS[type(node.op)](left, right)
        if isinstance(result, complex) or abs(result) > MAX_ABS:
            raise ValueError("too large")
        return result
    raise ValueError("not allowed")


def normalize(text):
    """Unicode maths signs to ASCII: x and middle dot to *, the minus sign to -, : and ÷ to /."""
    text = (text.replace("−", "-").replace("–", "-").replace("×", "*")
            .replace("⋅", "*").replace("·", "*").replace("÷", "/"))
    return text


_NUMBER = r"-?\d+(?:[.,]\d+)?"


def option_value(text):
    """The number an option stands for, or None: "12", "3,5", "1/2", "25%", "12 cm²", "-3", "1 000"."""
    if text is None:
        return None
    text = normalize(str(text)).strip()
    text = re.sub(r"(?<=\d)[   ](?=\d{3}\b)", "", text)   # 1 000 -> 1000
    text = re.sub(r"^[=≈~]\s*", "", text)
    match = re.fullmatch(rf"({_NUMBER})\s*/\s*({_NUMBER})", text)
    if match:
        top, bottom = (float(x.replace(",", ".")) for x in match.groups())
        return top / bottom if bottom else None
    # a number followed only by a unit or a sign: letters, ², °, %, €, $, .
    match = re.fullmatch(rf"({_NUMBER})\s*[^\d\s=+*/()]*\.?", text)
    if match and not re.search(r"\d", text[match.end(1):]):
        return float(match.group(1).replace(",", "."))
    return None


def option_values(options):
    """{"A": 12.0, ...} for the options that are plain numbers."""
    values = {}
    for letter, text in (options or {}).items():
        value = option_value(text)
        if value is not None:
            values[letter] = value
    return values


def numeric(options, at_least=4):
    """True when at least 4 options are distinct numbers: worth asking for an expression."""
    values = option_values(options)
    return len(values) >= at_least and len(set(values.values())) == len(values)


def match(value, options):
    """The one letter whose number equals value, or None (no match, or more than one)."""
    if value is None:
        return None
    hits = [letter for letter, v in option_values(options).items()
            if abs(v - value) <= 1e-6 * max(1.0, abs(v))]
    return hits[0] if len(hits) == 1 else None
