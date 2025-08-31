import sys
from pathlib import Path

class Identifier(str): pass
class Tuple(list): pass
class Code:
  def __init__(self, location: int, data: Identifier | int | str | Tuple) -> None:
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
      (codes[-1].data if len(codes) > 0 else codes).append(Code(start, s[start + 1:p - 1]))
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
    if level == 0: break
  if level != 0: raise ParseError("missing closing parenthesis", initial_p)
  assert len(codes) <= 1
  return codes.pop() if len(codes) > 0 else None, p

def code_as_string(code: Code) -> str:
  if isinstance(code.data, Identifier): return code.data
  elif isinstance(code.data, int): return str(code.data)
  elif isinstance(code.data, str): return '"' + code.data + '"'
  else:
    assert isinstance(code.data, Tuple)
    return "(" + " ".join(map(code_as_string, code.data)) + ")"

class Type: pass
class SimpleType(Type):
  def __init__(self, name: str) -> None:
    self.name = name
class IntegerType(Type):
  def __init__(self, bits: int, signed: bool) -> None:
    self.bits = bits
    self.signed = signed
class ProcedureType(Type):
  def __init__(self, parameter_types: list[Type], return_type: Type, varargs_type: Type | None, is_macro: bool) -> None:
    self.parameter_types = parameter_types
    self.return_type = return_type
    self.varargs_type = varargs_type
    self.is_macro = is_macro

type_type = SimpleType("TYPE")
type_code = SimpleType("CODE")
type_anytype = SimpleType("ANYTYPE")
type_noreturn = SimpleType("NORETURN")
type_void = SimpleType("VOID")
type_comptime_integer = SimpleType("COMPTIME_INTEGER")
type_integers = {}
type_procedures = {}

def get_integer_type(bits: int, signed: bool) -> IntegerType:
  for ty in type_integers:
    if all([ty.bits == bits, ty.signed == signed]):
      return ty
  key = IntegerType(bits, signed)
  return type_integers.setdefault(key, key)

def get_procedure_type(parameter_types: list[Type], return_type: Type, varargs_type: Type | None = None, is_macro: bool = False) -> ProcedureType:
  for ty in type_procedures:
    if all([*[a is b for a, b in zip(ty.parameter_types, parameter_types)], ty.return_type is return_type, ty.varargs_type is varargs_type, ty.is_macro == is_macro]):
      return ty
  key = ProcedureType(parameter_types, return_type, varargs_type, is_macro)
  return type_procedures.setdefault(key, key)

def type_as_string(ty: Type) -> str:
  if isinstance(ty, SimpleType): return f"($type {ty.name})"
  if isinstance(ty, ProcedureType): return f"($type PROCEDURE #parameter_types ({" ".join(map(type_as_string, ty.parameter_types))}) #return_type {type_as_string(ty.return_type)} #varargs_type {type_as_string(ty.varargs_type) if ty.varargs_type is not None else "null"} #is_macro {"true" if ty.is_macro else "false"})"
  raise NotImplementedError(ty)

class Value:
  def __init__(self, ty: Type, contents: Type | Code | None) -> None:
    self.ty = ty
    self.contents = contents

value_void = Value(type_void, None)

def value_as_string(value: Value) -> str:
  if value.ty is type_type: return type_as_string(value.contents)
  if value.ty is type_code: return code_as_string(value.contents)
  if value.ty is type_anytype: return f"($cast {type_as_string(type_anytype)} {value.contents})"
  if value.ty is type_noreturn: return f"($cast {type_as_string(type_noreturn)} 0)"
  if value.ty is type_void: return f"($cast {type_as_string(type_void)} 0)"
  if value.ty is type_comptime_integer: return str(value.contents)
  if value.ty in type_procedures: return f"($cast {type_as_string(value.ty)} {value.contents.name})"
  raise NotImplementedError(value.ty)

class Procedure:
  def __init__(self, name: Identifier, parameter_names: list[Identifier], body_codes: list[Code], defining_scope: "Scope") -> None:
    self.name = name
    self.parameter_names = parameter_names
    self.body_codes = body_codes
    self.defining_scope = defining_scope
  def __call__(self, *args: "Value", **kwargs) -> Value:
    result = None
    def compiler_return(*args: "Value", **kwargs) -> Value:
      if len(args) > 1: raise EvaluationError("return takes a maximum of one value", kwargs["nearest_code"])
      nonlocal result; result = args[0] if len(args) > 0 else value_void; return value_void
    compiler_return.name = "return"

    procedure_scope = Scope(self.defining_scope)
    procedure_scope.entries.update({
      Identifier("return"): ScopeEntry(value=Value(get_procedure_type([], type_void, varargs_type=kwargs["ty"].return_type), compiler_return), constant=True),
    })

    namedargs, varargs = args[:len(self.parameter_names)], args[len(self.parameter_names):]
    for i, namedarg in enumerate(namedargs):
      procedure_scope.entries.update({self.parameter_names[i]: namedarg})

    for body_code in self.body_codes:
      evaluate_code(body_code, procedure_scope)
      if result is not None: break
    if result is None: raise EvaluationError("procedure did not return a value", kwargs["nearest_code"])
    return result

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

class EvaluationError(Exception):
  def __init__(self, message: str, code: Code) -> None:
    self.message = message
    self.code = code

def evaluate_code(code: Code, scope: Scope) -> Value:
  if isinstance(code.data, Identifier):
    entry = scope.find(code.data)
    if entry is None: raise EvaluationError(f"'{code.data}' not in scope", code)
    return entry.value
  if isinstance(code.data, int): return Value(type_comptime_integer, code.data)
  if isinstance(code.data, str): raise NotImplementedError()
  assert isinstance(code.data, Tuple)
  if len(code.data) == 0: raise EvaluationError("procedure call without name", code)
  op_code, *arg_codes = code.data
  proc = evaluate_code(op_code, scope)
  if proc.ty not in type_procedures: raise EvaluationError(f"'{code_as_string(op_code)}' is not a procedure", op_code)
  if len(arg_codes) != len(proc.ty.parameter_types):
    if proc.ty.varargs_type is None: raise EvaluationError(f"incorrect arity, expected {len(proc.ty.parameter_types)}", op_code)
    if len(arg_codes) < len(proc.ty.parameter_types): raise EvaluationError("expected more arguments", op_code)
  pargs = [evaluate_code(arg_code, scope) if not proc.ty.is_macro or (proc.ty.parameter_types[i] if i < len(proc.ty.parameter_types) else proc.ty.varargs_type) is not type_code else arg_code for i, arg_code in enumerate(arg_codes)]
  return proc.contents(*pargs, ty=proc.ty, calling_scope=scope, nearest_code=op_code)

def compiler_define_constant(name_code: Code, value: Value, **kwargs) -> Value:
  if not isinstance(name_code.data, Identifier): raise EvaluationError("argument 'name' expects an identifier", name_code)
  name = name_code.data
  if name in kwargs["calling_scope"].entries: raise EvaluationError(f"attempted redefinition of '{name}'", name_code)
  kwargs["calling_scope"].entries[name] = ScopeEntry(value=value, constant=True)
  return value_void
compiler_define_constant.name = Identifier("::")

def compiler_define_variable(name_code: Code, value: Value, **kwargs) -> Value:
  if not isinstance(name_code.data, Identifier): raise EvaluationError("argument 'name' expects an identifier", name_code)
  name = name_code.data
  if name in kwargs["calling_scope"].entries: raise EvaluationError(f"attempted redefinition of '{name}'", name_code)
  kwargs["calling_scope"].entries[name] = ScopeEntry(value=value, constant=False)
  return value_void
compiler_define_variable.name = Identifier(":=")

def compiler_define_procedure(name_code: Code, parameters_code: Code, return_type_value: Value, *body_codes: Code, **kwargs) -> Value:
  if not isinstance(name_code.data, Identifier): raise EvaluationError("argument 'name' expects an identifier", name_code)
  name = name_code.data
  if name in kwargs["calling_scope"].entries: raise EvaluationError(f"attempted redefinition of '{name}'", name_code)
  if not isinstance(parameters_code.data, Tuple): raise EvaluationError("parameter tuple was not a tuple", name_code)
  if return_type_value.ty is not type_type: raise EvaluationError("return type was not a type", name_code)
  parameter_scope = Scope(kwargs["calling_scope"])
  for parameter_code in parameters_code.data:
    evaluate_code(parameter_code, parameter_scope)
  parameter_types = []
  parameter_names = []
  for ident, value in parameter_scope.entries.items():
    parameter_names.append(ident)
    parameter_types.append(value.ty)
  kwargs["calling_scope"].entries[name] = ScopeEntry(value=Value(get_procedure_type(parameter_types, return_type_value.contents), Procedure(name, parameter_names, body_codes, kwargs["calling_scope"])), constant=True)
  return value_void
compiler_define_procedure.name = Identifier("proc")

def compiler_add(*args: Value, **kwargs) -> Value:
  result = 0
  for arg in args:
    if arg.ty is not kwargs["ty"].varargs_type: raise EvaluationError("add only supports comptime integers for now")
    result += arg.contents
  return Value(kwargs["ty"].return_type, result)
compiler_add.name = Identifier("+")

compiler_scope = Scope(None)
compiler_scope.entries.update({
  Identifier("comptime-int"): ScopeEntry(Value(type_type, type_comptime_integer), constant=True),
  compiler_define_constant.name: ScopeEntry(value=Value(get_procedure_type([type_code, type_anytype], type_void, is_macro=True), compiler_define_constant), constant=True),
  compiler_define_variable.name: ScopeEntry(value=Value(get_procedure_type([type_code, type_anytype], type_void, is_macro=True), compiler_define_variable), constant=True),
  compiler_define_procedure.name: ScopeEntry(value=Value(get_procedure_type([type_code, type_code, type_type], type_void, varargs_type=type_code, is_macro=True), compiler_define_procedure), constant=True),
  compiler_add.name: ScopeEntry(value=Value(get_procedure_type([], type_comptime_integer, varargs_type=type_comptime_integer), compiler_add), constant=True),
})

def dostring(src: str, scope: Scope, silence: bool = True) -> None:
  pos = 0
  while True:
    code, next_pos = parse_code(src, pos)
    if code is None: break
    pos = next_pos
    # print(code_as_string(code))
    result = evaluate_code(code, scope)
    if not silence and result is not value_void: print("=>", value_as_string(result))

def dofile(path: Path) -> None:
  file_scope = Scope(compiler_scope)
  try: dostring(path.read_text(), file_scope)
  except ParseError as e: print(f"parse error @ {path.name}[{e.location}]: {e.message}")
  except EvaluationError as e: print(f"evaluation error @ {path.name}[{e.code.location}]: {e.message}")

def repl() -> None:
  repl_scope = Scope(compiler_scope)
  while True:
    try: i = input("> ")
    except (KeyboardInterrupt, EOFError): print(""); break
    try: dostring(i, repl_scope, silence=False)
    except ParseError as e: print(f"parse error @ repl[{e.location}]: {e.message}")
    except EvaluationError as e: print(f"evaluation error @ repl[{e.code.location}]: {e.message}")

if __name__ == "__main__":
  if len(sys.argv) <= 1: repl()
  else: dofile(Path(sys.argv[1]))
