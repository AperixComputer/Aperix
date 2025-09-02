import sys
from pathlib import Path

class Identifier(str): pass
class Keyword(str): pass
class Tuple(list): pass
class Code:
  def __init__(self, location: int, data: Identifier | Keyword | int | str | Tuple) -> None:
    self.location = location
    self.data = data

class ParseError(Exception):
  def __init__(self, message: str, location: int) -> None:
    self.message = message
    self.location = location

def isbasedigit(c: str, base: int) -> bool:
  if base == 2: return "0" <= c <= "1"
  if base == 8: return "0" <= c <= "7"
  if base == 10: return "0" <= c <= "9"
  if base == 16: return "0" <= c <= "9" or "a" <= c.lower() <= "f"
  raise NotImplementedError(base)

def parse_code(s: str, p: int) -> tuple[Code | None, int]:
  initial_p = p
  codes = []
  indents = []
  implicitnesses = []
  while True:
    start = p
    newline_was_skipped = False
    beginning_of_line = start
    while True:
      while p < len(s) and s[p].isspace():
        if s[p] == "\n": newline_was_skipped = True; beginning_of_line = p + 1
        p += 1
      if p < len(s) and s[p] == ";":
        while p < len(s) and s[p] != "\n": p += 1
        continue
      break
    if p >= len(s): break
    first_code_of_line = start == 0 or newline_was_skipped
    indent = p - beginning_of_line
    start = p
    if first_code_of_line:
      if len(indents) == 0 or indent > indents[-1]: indents.append(indent)
      if s[p] not in "()":
        codes.append(Code(start, Tuple()))
        implicitnesses.append(True)
    if s[p] == "(":
      p += 1
      codes.append(Code(start, Tuple()))
      implicitnesses.append(False)
    elif s[p] == ")":
      p += 1
      if len(implicitnesses) == 0 or implicitnesses[-1]: raise ParseError("extraneous closing parenthesis", start)
      implicitnesses.pop()
      if len(codes) > 1:
        popped = codes.pop()
        codes[-1].data.append(popped)
    elif s[p] == '"':
      p += 1
      while p < len(s) and (s[p - 1] == "\\" or s[p] != '"'): p += 1
      if p >= len(s) or s[p] != '"': raise ParseError("unterminated string literal", start)
      p += 1
      (codes[-1].data if len(codes) > 0 else codes).append(Code(start, s[start + 1:p - 1]))
    elif s[p] == "'":
      p += 1
      code, next_pos = parse_code(s, p)
      if code is None: raise ParseError("$code of nothing", start)
      p = next_pos
      (codes[-1].data if len(codes) > 0 else codes).append(Code(start, Tuple([Code(start, Identifier("$code")), code])))
    elif s[p] == ",":
      p += 1
      code, next_pos = parse_code(s, p)
      if code is None: raise ParseError("$insert of nothing", start)
      p = next_pos
      (codes[-1].data if len(codes) > 0 else codes).append(Code(start, Tuple([Code(start, Identifier("$insert")), code])))
    elif s[p] == "#":
      p += 1
      if p >= len(s) or s[p].isspace() or s[p] in "()": raise ParseError("invalid keyword", start)
      while p < len(s) and not s[p].isspace() and s[p] not in "()": p += 1
      (codes[-1].data if len(codes) > 0 else codes).append(Code(start, Keyword(s[start + 1:p])))
    elif s[p].isdigit():
      base = 10
      if p + 1 < len(s) and s[p] == "0" and s[p + 1] in "box":
        p += 1
        if s[p] == "b": base = 2
        if s[p] == "o": base = 8
        if s[p] == "x": base = 16
        p += 1
        if p >= len(s) or not isbasedigit(s[p], base): raise ParseError("invalid integer literal")
      while p < len(s) and isbasedigit(s[p], base): p += 1
      (codes[-1].data if len(codes) > 0 else codes).append(Code(start, int(s[start:p], base=base)))
    else:
      while p < len(s) and not s[p].isspace() and s[p] not in "()": p += 1
      (codes[-1].data if len(codes) > 0 else codes).append(Code(start, Identifier(s[start:p])))
    peek = p
    while peek < len(s) and s[peek].isspace() and s[peek] not in "\n;": peek += 1
    last_code_of_line = peek >= len(s) or s[peek] in "\n;"
    beginning_of_next_line = peek
    while True:
      while peek < len(s) and s[peek].isspace():
        if s[peek] == "\n": beginning_of_next_line = peek + 1
        peek += 1
      if peek < len(s) and s[peek] == ";":
        while peek < len(s) and s[peek] != "\n": peek += 1
        continue
      break
    next_indent = peek - beginning_of_next_line if peek < len(s) else 0
    if last_code_of_line:
      while len(indents) > 0 and next_indent <= indents[-1]:
        indents.pop()
        if len(codes) > 1:
          popped = codes.pop()
          codes[-1].data.append(popped)
      if len(implicitnesses) > 0 and implicitnesses[-1]: implicitnesses.pop()
    if len(implicitnesses) == 0 and (len(indents) == 0 or next_indent <= indents[0]): break
  if len(implicitnesses) != 0: raise ParseError("missing closing parenthesis", initial_p)
  assert len(codes) <= 1
  return codes.pop() if len(codes) > 0 else None, p

def code_as_string(code: Code) -> str:
  if isinstance(code.data, Identifier): return code.data
  elif isinstance(code.data, Keyword): return "#" + code.data
  elif isinstance(code.data, int): return str(code.data)
  elif isinstance(code.data, str): return '"' + code.data + '"'
  else:
    assert isinstance(code.data, Tuple)
    return "(" + " ".join(map(code_as_string, code.data)) + ")"

class Type: pass
class ProcedureType(Type):
  def __init__(self, parameter_types: list[Type], return_type: Type, varargs_type: Type | None, is_macro: bool) -> None:
    self.parameter_types = parameter_types
    self.return_type = return_type
    self.varargs_type = varargs_type
    self.is_macro = is_macro

class ScopeEntry:
  pass

class Scope:
  def __init__(self, parent: "Scope | None") -> None:
    self.parent = parent
    self.entries = {}
  def find(self, key: Identifier) -> ScopeEntry | None:
    if key in self.entries: return self.entries[key]
    if self.parent is not None: return self.parent.find(key)
    return None

if __name__ == "__main__":
  path = Path(sys.argv[1])
  src = path.read_text()
  pos = 0
  while True:
    code, next_pos = parse_code(src, pos)
    if code is None: break
    pos = next_pos
    print(code_as_string(code))
