import sys
import typing
from dataclasses import dataclass
from pathlib import Path

class Identifier(str): pass
class Keyword(str): pass
class Tuple(list["Code"]): pass
class Code:
  def __init__(self, location: int, data: Identifier | Keyword | int | str | Tuple):
    self.location = location
    self.data = data

  @property
  def as_tuple(self) -> Tuple: assert isinstance(self.data, Tuple); return self.data

class ParseError(Exception):
  def __init__(self, message: str, location: int) -> None:
    self.message = message
    self.location = location

def isbasedigit(c: str, base: int) -> bool:
  if base == 2: return '0' <= c <= '1'
  if base == 8: return '0' <= c <= '7'
  if base == 10: return '0' <= c <= '9'
  if base == 16: return '0' <= c <= '9' or 'a' <= c.lower() <= 'f'
  raise NotImplementedError(base)

def parse_code(s: str, p: int) -> tuple[Code | None, int]:
  initial_p = p
  level = 0
  codes: list[Code] = []
  while True:
    while True:
      while p < len(s) and s[p].isspace(): p += 1
      if p < len(s) and s[p] == ';':
        while p < len(s) and s[p] != '\n': p += 1
        continue
      break
    if p >= len(s): break
    start = p
    if s[p] == '(':
      p += 1
      level += 1
      codes.append(Code(start, Tuple()))
    elif s[p] == ')':
      p += 1
      if level == 0: raise ParseError("extraneous closing parenthesis", start)
      level -= 1
      if len(codes) > 1:
        popped = codes.pop()
        codes[-1].as_tuple.append(popped)
    elif s[p] == '"':
      p += 1
      while p < len(s) and (s[p - 1] == '\\' or s[p] != '"'): p += 1
      if p >= len(s) or s[p] != '"': raise ParseError("unterminated string literal", start)
      p += 1
      (codes[-1].as_tuple if len(codes) > 0 else codes).append(Code(start, s[start + 1:p - 1]))
    elif s[p].isdigit():
      base = 10
      if p + 1 < len(s) and s[p] == '0' and s[p + 1] in "box":
        p += 1
        if s[p] == 'b': base = 2
        if s[p] == 'o': base = 8
        if s[p] == 'x': base = 16
        p += 1
        if p >= len(s) or not isbasedigit(s[p], base): raise ParseError("invalid integer literal", start)
      while p < len(s) and isbasedigit(s[p], base): p += 1
      (codes[-1].as_tuple if len(codes) > 0 else codes).append(Code(start, int(s[start:p], base=0)))
    else:
      while p < len(s) and not s[p].isspace() and s[p] not in "()": p += 1
      if s[start] == '#':
        if p - start == 1: raise ParseError("invalid keyword", start)
        (codes[-1].as_tuple if len(codes) > 0 else codes).append(Code(start, Keyword(s[start + 1:p])))
      else:
        (codes[-1].as_tuple if len(codes) > 0 else codes).append(Code(start, Identifier(s[start:p])))
    if level == 0: break
  if level != 0: raise ParseError("missing closing parenthesis", initial_p)
  assert len(codes) <= 1
  return codes.pop() if len(codes) > 0 else None, p

def code_as_string(code: Code) -> str:
  if isinstance(code.data, Identifier): return str(code.data)
  elif isinstance(code.data, Keyword): return '#' + str(code.data)
  elif isinstance(code.data, int): return str(code.data)
  elif isinstance(code.data, str): return '"' + code.data + '"'
  else:
    assert isinstance(code.data, Tuple)
    return '(' + ' '.join(map(code_as_string, code.data)) + ')'

@dataclass(frozen=True)
class Type: pass
@dataclass(frozen=True)
class ProcedureType(Type):
  parameter_types: list[Type]
  return_type: Type
  varargs_type: Type | None = None
  is_macro: bool = False

named_types = {
  "TYPE": Type(),
  "CODE": Type(),
  "ANYTYPE": Type(),
  "COMPTIME_INTEGER": Type(),
  "COMPTIME_STRING": Type(),
  "VOID": Type(),
}

def type_as_string(ty: Type) -> str:
  for ty_name, ty_value in named_types.items():
    if ty is ty_value: return ty_name
  raise NotImplementedError(ty.__class__.__name__)

class Procedure:
  def __init__(self) -> None:
    pass
  def __call__(self, *args: "Value", **kwargs) -> "Value":
    return value_void

BuiltinProcedure = typing.Callable[..., "Value"]

class Value:
  def __init__(self, ty: Type, contents: Type | Code | int | str | Procedure | BuiltinProcedure | None) -> None:
    self.ty = ty
    self.contents = contents

value_void = Value(named_types["VOID"], None)

class ScopeEntry:
  def __init__(self, value: Value) -> None:
    self.value = value

class Scope:
  def __init__(self, parent: "Scope | None") -> None:
    self.parent = parent
    self.entries: dict[Identifier, ScopeEntry] = {}
  def find(self, key: Identifier) -> ScopeEntry | None:
    if key in self.entries: return self.entries[key]
    if self.parent is None: return None
    return self.parent.find(key)

class EvaluationError(Exception):
  def __init__(self, message: str, code: Code) -> None:
    self.message = message
    self.code = code

def evaluate_code(code: Code, scope: Scope) -> Value:
  if isinstance(code.data, Identifier):
    entry = scope.find(code.data)
    if entry is None: raise EvaluationError("not in scope", code)
    return entry.value
  elif isinstance(code.data, Keyword): raise EvaluationError("invalid usage of keyword", code)
  elif isinstance(code.data, int): return Value(named_types["COMPTIME_INTEGER"], code.data)
  elif isinstance(code.data, str): return Value(named_types["COMPTIME_STRING"], code.data)
  assert isinstance(code.data, Tuple)
  if len(code.data) == 0: raise EvaluationError("attempted call with a name", code)
  op_code, *arg_codes = code.data
  proc = evaluate_code(op_code, scope)
  if not isinstance(proc.ty, ProcedureType): raise EvaluationError("attempted call of non-procedure", op_code)
  assert callable(proc.contents)
  # TODO: there are two sets of namedargs, those which match Procedure, and those which are variadic.
  parg_codes, namedargs = [], {}
  i = 0
  while i < len(arg_codes):
    if isinstance(arg_codes[i].data, Keyword):
      kw = arg_codes[i].data
      i += 1
      if i > len(arg_codes): raise EvaluationError("keyword without arg", arg_codes[i - 1])
      namedargs[kw] = arg_codes[i]
    else:
      parg_codes.append(arg_codes[i])
    i += 1
  if proc.ty.varargs_type is None and len(arg_codes) != len(proc.ty.parameter_types):
    raise EvaluationError(f"expected {len(proc.ty.parameter_types)} argument{"s" if len(proc.ty.parameter_types) != 1 else ""}, got {len(arg_codes)}", op_code)
  if len(arg_codes) < len(proc.ty.parameter_types):
    raise EvaluationError(f"expected at least {len(proc.ty.parameter_types)} argument{"s" if len(proc.ty.parameter_types) != 1 else ""}, got {len(arg_codes)}", op_code)
  pargs = [evaluate_code(arg_code, scope) if not proc.ty.is_macro or (proc.ty.parameter_types[i] if i < len(proc.ty.parameter_types) else proc.ty.varargs_type) is not named_types["CODE"] else Value(named_types["CODE"], arg_code) for i, arg_code in enumerate(arg_codes)]
  result = proc.contents(*pargs, ty=proc.ty, calling_scope=scope, op_code=op_code)
  if result.ty is not proc.ty.return_type: raise EvaluationError("returned type differs from stated type", op_code)
  return result

def value_as_string(value: Value) -> str:
  if value.ty is named_types["TYPE"]: assert isinstance(value.contents, Type); return type_as_string(value.contents)
  if value.ty is named_types["CODE"]: assert isinstance(value.contents, Code); return code_as_string(value.contents)
  if value.ty is named_types["COMPTIME_INTEGER"]: assert isinstance(value.contents, int); return str(value.contents)
  if value.ty is named_types["COMPTIME_STRING"]: assert isinstance(value.contents, str); return value.contents
  raise NotImplementedError(value.ty.__class__.__name__)

def dostring(s: str, scope: Scope, echo_results: bool = False) -> None:
  pos = 0
  while True:
    try: code, next_pos = parse_code(s, pos)
    except ParseError as e: print(f"parse error @ {path.name}[{e.location}]: {e.message}"); break
    if code is None: break
    pos = next_pos
    # print(code_as_string(code))
    try: result = evaluate_code(code, scope)
    except EvaluationError as e: print(f"evaluation error @ {path.name}[{e.code.location}] near '{code_as_string(e.code)}': {e.message}"); break
    if echo_results and result is not value_void: print(value_as_string(result))

def compiler_type(kind_code: Value, **kwargs) -> Value:
  assert isinstance(kind_code.contents, Code)
  kind = kind_code.contents.data
  assert isinstance(kind, Identifier)

  ty: Type | None = None
  if kind in named_types: ty = named_types[kind]
  if ty is None: raise EvaluationError("unknown type kind", kind_code.contents)
  return Value(named_types["TYPE"], ty)

def compiler_define(name_code: Value, contents_value: Value, **kwargs) -> Value:
  assert isinstance(name_code.contents, Code)
  name = name_code.contents.data
  assert isinstance(name, Identifier)
  kwargs["calling_scope"].entries[name] = ScopeEntry(contents_value)
  return value_void

def compiler_operator(operator_code: Value, *varargs: Value, **kwargs) -> Value:
  assert isinstance(operator_code.contents, Code)
  operator = operator_code.contents.data
  assert isinstance(operator, Identifier)
  if operator not in [Identifier("+"), Identifier("*")]: raise EvaluationError("only + and * are supported currently", operator_code.contents)
  result: int = 0 if operator == Identifier("+") else 1
  for arg in varargs:
    if arg.ty is not named_types["COMPTIME_INTEGER"]: raise EvaluationError("only comptime integers are supported currently", operator_code.contents)
    assert isinstance(arg.contents, int)
    result = eval(f"result {operator} {arg.contents}")
  return Value(named_types["COMPTIME_INTEGER"], result)

compiler_scope = Scope(None)
compiler_scope.entries.update({
  Identifier("$type"): ScopeEntry(Value(ProcedureType([named_types["CODE"]], named_types["TYPE"], is_macro=True), compiler_type)),
  Identifier("$define"): ScopeEntry(Value(ProcedureType([named_types["CODE"], named_types["ANYTYPE"]], named_types["VOID"], is_macro=True), compiler_define)),
  Identifier("$operator"): ScopeEntry(Value(ProcedureType([named_types["CODE"]], named_types["COMPTIME_INTEGER"], varargs_type=named_types["CODE"], is_macro=True), compiler_operator))
})

if __name__ == "__main__":
  if len(sys.argv) > 1:
    path = Path(sys.argv[1])
    src = path.read_text()
    file_scope = Scope(compiler_scope)
    dostring(src, file_scope)
  else:
    repl_scope = Scope(compiler_scope)
    while True:
      src = input("> ")
      dostring(src, repl_scope, True)
