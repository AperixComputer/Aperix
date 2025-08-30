import sys
from pathlib import Path

class Identifier(str): pass
class Tuple(list): pass
class Code:
  def __init__(self, location: int, data: Identifier | int | float | str | Tuple) -> None:
    self.location = location
    self.data = data

def isbasedigit(c: str, base: int) -> bool:
  if base == 2: return "0" <= c <= "1"
  if base == 8: return "0" <= c <= "7"
  if base == 10: return "0" <= c <= "9"
  if base == 16: return "0" <= c <= "9" or "a" <= c.lower() <= "f"
  raise NotImplementedError(base)

class ParseError(Exception):
  def __init__(self, message: str, location: int) -> None:
    self.message = message
    self.location = location
def parse_code(s: str, p: int) -> tuple[Code | None, int]:
  initial_p = p
  level = 0
  codes = []
  while True:
    while True:
      while p < len(s) and s[p].isspace(): p += 1
      if p < len(s) and s[p] == ";":
        while p < len(s) and s[p] != "\n": p += 1
        continue
      break
    if p >= len(s): break
    start = p
    if s[p] == "(":
      p += 1
      level += 1
      codes.append(Code(start, Tuple()))
    elif s[p] == ")":
      p += 1
      if level == 0: raise ParseError("extraneous closing parenthesis", start)
      level -= 1
      if len(codes) > 1:
        popped = codes.pop()
        codes[-1].data.append(popped)
    elif s[p] == '"':
      p += 1
      while p < len(s) and (s[p - 1] == "\\" or s[p] != '"'): p += 1
      if p >= len(s) or s[p] != '"': raise ParseError("unterminated string literal", start)
      p += 1
      (codes[-1].data if len(codes) > 0 else codes).append(Code(start, str(s[start:p])))
    elif s[p].isdigit():
      base = 10
      if p + 1 < len(s) and s[p] == "0" and s[p + 1] in "box":
        p += 1
        if s[p] == "b": base = 2
        if s[p] == "o": base = 8
        if s[p] == "x": base = 16
        p += 1
        if p >= len(s) or not isbasedigit(s[p], base): raise ParseError("invalid integer literal", start)
      while p < len(s) and isbasedigit(s[p], base): p += 1
      (codes[-1].data if len(codes) > 0 else codes).append(Code(start, int(s[start:p], base=base)))
    else:
      while p < len(s) and not s[p].isspace() and s[p] not in "()": p += 1
      (codes[-1].data if len(codes) > 0 else codes).append(Code(start, Identifier(s[start:p])))
    if level == 0: break
  assert len(codes) <= 1
  if level != 0: raise ParseError("missing closing parenthesis", initial_p)
  return codes.pop() if len(codes) > 0 else None, p

def code_as_string(code: Code) -> str:
  if isinstance(code.data, Identifier): return code.data
  elif isinstance(code.data, int | float): return str(code.data)
  elif isinstance(code.data, str): return '"' + code.data + '"'
  else:
    assert isinstance(code.data, Tuple)
    return "(" + " ".join(map(code_as_string, code.data)) + ")"

class Type: pass
class SimpleType(Type):
  def __init__(self, name: str) -> None:
    self.name = name
  def __repr__(self) -> str: return f"SimpleType({self.name})"
class IntegerType(Type):
  def __init__(self, bits: int, signed: bool) -> None:
    self.bits = bits
    self.signed = signed
class ProcedureType(Type):
  def __init__(self, is_macro: bool) -> None:
    self.is_macro = is_macro

type_type = SimpleType("type")
type_code = SimpleType("code")
type_noreturn = SimpleType("noreturn")
type_void = SimpleType("void")
type_bool = SimpleType("bool")
type_comptime_integer = SimpleType("comptime_integer")
type_comptime_float = SimpleType("comptime_float")
type_procedure = ProcedureType(is_macro=False)
type_macro = ProcedureType(is_macro=True)
type_u32 = IntegerType(32, False)

def type_as_string(ty: Type) -> str:
  if isinstance(ty, SimpleType): return ty.name
  if isinstance(ty, IntegerType): return f"{"s" if ty.signed else "u"}{ty.bits}"
  raise NotImplementedError(ty)

class Procedure:
  def __init__(self, name: Identifier, parameters: list[tuple["Value", "Value"]], returns: "Value", body_codes: list[Code]) -> None:
    self.name = name
    self.parameters = parameters
    self.returns = returns
    self.body_codes = body_codes
  def __call__(self, *args) -> "Value":
    return_value = value_void
    procedure_scope = Scope(compiler_scope)
    def return_stmt(value: "Value") -> "Value":
      nonlocal return_value; return_value = value; return value_void
    procedure_scope.entries.update({
      Identifier("return"): ScopeEntry(Value(type_procedure, return_stmt), constant=True)
    })
    for i, (name_value, type_value) in enumerate(self.parameters):
      procedure_scope.entries.update({Identifier(value_as_string(name_value)): ScopeEntry(args[i], constant=False)})
    for code in self.body_codes:
      result = evaluate_code(code, procedure_scope)
      # if result is not value_void: print("=>", value_as_string(result))
    return return_value

class Value:
  def __init__(self, ty: Type, contents: Type | Code | Procedure | None | int | float | str) -> None:
    self.ty = ty
    self.contents = contents

class ScopeEntry:
  def __init__(self, value: Value, constant: bool) -> None:
    self.value = value
    self.constant = constant
class Scope:
  def __init__(self, parent: "Scope | None") -> None:
    self.parent = parent
    self.entries = {}
  def find(self, key: Identifier) -> ScopeEntry | None:
    if key in self.entries: return self.entries[key]
    if self.parent is not None: return self.parent.find(key)
    return None

value_void = Value(type_void, None)

class EvaluationError(Exception):
  def __init__(self, message: str, code: int) -> None:
    self.message = message
    self.code = code
  def __str__(self) -> str: return f"file[{self.code.location}] {self.message}"

def get_identifier_possibly_from_string(code: Code, scope: Scope) -> Identifier:
  if isinstance(code.data, Identifier): result = code.data
  else:
    value = evaluate_code(code, scope)
    if isinstance(value.ty, type_string): result = Identifier(value.contents)
    elif isinstance(value.ty, type_code) and isinstance(value.contents.data, Identifier): result = value.contents.data
    else: raise EvaluationError(f"code evaluate to an identifier or string", code)
  return result

def infer_type(data: int | float | str) -> Type:
  if isinstance(data, int): return type_comptime_integer
  if isinstance(data, float): return type_comptime_float
  raise NotImplementedError(type(data))

def evaluate_code(code: Code, scope: Scope) -> Value:
  if not isinstance(code.data, Tuple):
    if isinstance(code.data, Identifier):
      entry = scope.find(code.data)
      if entry is None: raise EvaluationError(f"identifier '{code.data}' not in scope", code)
      return entry.value
    else:
      assert isinstance(code.data, int | float)
      return Value(infer_type(code.data), code.data)
  op_code, *arg_codes = code.data
  if isinstance(op_code.data, Identifier):
    if op_code.data == Identifier("|"):
      result = 0
      for arg in [evaluate_code(arg_code, scope) for arg_code in arg_codes]:
        if arg.ty != type_comptime_integer: raise NotImplementedError(arg.ty)
        result |= arg.contents
      return Value(type_comptime_integer, result)
    elif op_code.data == Identifier("proc"):
      name_code, parameter_codes, returns_code, *body_codes = arg_codes
      name = get_identifier_possibly_from_string(name_code, scope)
      if not isinstance(parameter_codes.data, Tuple): raise EvaluationError("parameter list must be a tuple", parameter_codes)
      parameters = []
      parameter_scope = Scope(scope)
      parameter_scope.entries.update({
        Identifier(":"): ScopeEntry(Value(type_macro, lambda name, value: parameters.append((name, value))), constant=True)
      })
      for parameter_code in parameter_codes.data: evaluate_code(parameter_code, parameter_scope)
      returns = evaluate_code(returns_code, scope)
      scope.entries[name] = ScopeEntry(Value(type_procedure, Procedure(name, parameters, returns, body_codes)), constant=True)
      return value_void
  proc = evaluate_code(op_code, scope)
  pargs = [evaluate_code(arg_code, scope) if not proc.ty.is_macro else Value(type_code, arg_code) for arg_code in arg_codes]
  return proc.contents(*pargs)

def value_as_string(value: Value) -> str:
  if value.ty == type_type: return type_as_string(value.contents)
  if value.ty == type_code: return code_as_string(value.contents)
  if value.ty == type_procedure: return f"(proc {value.contents.name} ({" ".join(f"(: {value_as_string(p[0])} {value_as_string(p[1])})" for p in value.contents.parameters)}) {value_as_string(value.contents.returns)})"
  if value.ty == type_comptime_integer: return str(value.contents)
  if value.ty == type_void: return "(cast (type 'VOID) 0)"
  raise NotImplementedError(value.ty)

compiler_scope = Scope(None)
compiler_scope.entries.update({
  Identifier("u32"): ScopeEntry(Value(type_type, type_u32), constant=True),
  Identifier("<<"): ScopeEntry(Value(type_procedure, lambda lhs, rhs: Value(type_comptime_integer, lhs.contents << rhs.contents)), constant=True),
  Identifier("&"): ScopeEntry(Value(type_procedure, lambda lhs, rhs: Value(type_comptime_integer, lhs.contents & rhs.contents)), constant=True),
})

def dostring(src: str, name: str) -> None:
  pos = 0
  scope = Scope(compiler_scope)
  while True:
    code, next_pos = parse_code(src, pos)
    if code is None: break
    print(code_as_string(code))
    pos = next_pos
    result = evaluate_code(code, scope)
    if result is not value_void: print("=>", value_as_string(result))

def dofile(path: str | Path) -> None:
  path = Path(path)
  with open(path) as f: src = f.read()
  dostring(src, name=path.name)

if __name__ == "__main__":
  if len(sys.argv) <= 1: raise Exception("usage: python aperion.py file.aperion")
  dofile(sys.argv[1])
