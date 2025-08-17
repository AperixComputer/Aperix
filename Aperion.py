from dataclasses import dataclass

class Identifier(str): pass
class Number:
  def __init__(self, value: int | float) -> None:
    self.value = value
  def __str__(self) -> str: return str(self.value)
class String(str):
  def __str__(self) -> str: return '"' + self + '"'
class Tuple(list): pass
class Code:
  def __init__(self, location: int, value: Identifier | Number | String | Tuple) -> None:
    self.location = location
    self.value = value

def parse_code(s: str, p: int) -> tuple[Code | None, int]:
  level = 0
  stack = []
  while True:
    while p < len(s) and s[p] in " \t\n\r": p += 1
    if p >= len(s): break
    start = p
    if s[p] == "(":
      p += 1
      level += 1
      stack.append(Code(start, Tuple()))
    elif s[p] == ")":
      p += 1
      assert level > 0, "extraneous closing parenthesis"
      level -= 1
      if len(stack) > 1:
        popped = stack.pop()
        stack[-1].value.append(popped)
    elif s[p].isdigit():
      is_float = False
      while p < len(s) and s[p].isdigit(): p += 1
      if p < len(s) and s[p] == ".":
        p += 1
        is_float = True
        while p < len(s) and s[p].isdigit(): p += 1
      if p < len(s) and s[p] == "e":
        p += 1
        is_float = True
        if p < len(s) and s[p] in "+-": p += 1
        while p < len(s) and s[p].isdigit(): p += 1
      (stack[-1].value if len(stack) > 0 else stack).append(Code(start, Number((float if is_float else int)(s[start:p]))))
    elif s[p] == '"':
      p += 1
      while p < len(s) and (s[p - 1] == "\\" or s[p] != '"'): p += 1
      assert p < len(s) and s[p] == '"', "unterminated string literal"
      p += 1
      (stack[-1].value if len(stack) > 0 else stack).append(Code(start, String(s[start+1:p-1])))
    else:
      while p < len(s) and s[p] not in "() \t\n\r": p += 1
      (stack[-1].value if len(stack) > 0 else stack).append(Code(start, Identifier(s[start:p])))
    if level == 0: break
  return stack.pop() if len(stack) > 0 else None, p

def code_as_string(code: Code) -> str:
  if not isinstance(code.value, Tuple): return str(code.value)
  else: return "(" + " ".join(map(code_as_string, code.value)) + ")"

def code_as_debug_string(code: Code) -> str:
  if not isinstance(code.value, Tuple): return code.value.__class__.__name__ + "[" + str(code.value) + "]"
  else: return "Tuple[" + " ".join(map(code_as_debug_string, code.value)) + "]"

@dataclass(frozen=True, eq=True)
class Type: pass
@dataclass(frozen=True, eq=True)
class Type_Code(Type): pass
@dataclass(frozen=True, eq=True)
class Void(Type): pass
@dataclass(frozen=True, eq=True)
class ComptimeInteger(Type): pass
@dataclass(frozen=True, eq=True)
class Integer(Type):
  bits: int
  signed: bool
@dataclass(frozen=True, eq=True)
class Pointer(Type):
  child: Type
  constant: bool
@dataclass(frozen=True, eq=True)
class Array(Type):
  child: Type
  count: int
  sentinel: "Value | None"
@dataclass(frozen=True, eq=True)
class StructLiteral(Type): pass
@dataclass(frozen=True, eq=True)
class Macro(Type): pass

type_type = Type()
type_code = Type_Code()
type_void = Void()
type_comptime_integer = ComptimeInteger()
type_u8 = Integer(8, False)
type_struct_literal = StructLiteral()
type_macro = Macro()
type_pointers = {}
type_arrays = {}

def get_pointer_type(child: Type, constant: bool) -> Type:
  type_pointers.setdefault(Pointer(child, constant), Pointer(child, constant))
  return type_pointers[Pointer(child, constant)]

def get_array_type(child: Type, count: int, sentinel: "Value | None" = None) -> Type:
  type_arrays.setdefault(Array(child, count, sentinel), Array(child, count, sentinel))
  return type_arrays[Array(child, count, sentinel)]

def type_as_string(ty: Type) -> str:
  if ty == type_struct_literal: return "($type 'STRUCT-LITERAL)"
  if ty == type_comptime_integer: return "($type 'COMPTIME-INTEGER)"
  if ty in type_pointers: return f"($type 'POINTER #child {type_as_string(ty.child)} #constant {"1" if ty.constant else "0"})"
  if ty in type_arrays: return f"($type 'ARRAY #child {type_as_string(ty.child)} #count {ty.count} #sentinel {value_as_string(ty.sentinel)})"
  if ty == type_u8: return f"($type 'INTEGER #bits {8} #signed {0})"
  raise NotImplementedError(type(ty))

class Value:
  def __init__(self, ty: Type, contents: Code | None, constant: bool) -> None:
    self.ty = ty
    self.contents = contents
    self.constant = constant

value_void = Value(type_void, None, constant=True)

def value_as_string(value: Value, key: str | None = None) -> str:
  if value.ty == type_code: return code_as_string(value.contents)
  if value.ty == type_struct_literal:
    if value.contents == None: return "($cast ($type 'NULL) 0)"
    return "({} " + " ".join(f"#{key} {value_as_string(value, key)}" for key, value in value.contents.data.items()) + ")"
  if value.ty == type_macro:
    return key
  if value.ty == type_comptime_integer: return str(value.contents)
  if value.ty in type_pointers:
    if value.ty.child.child == type_u8: return str(value.contents)
    else: return str(id(value.contents))
  raise NotImplementedError(value.ty.__class__.__name__)

def infer_type(code: Code) -> Type:
  if isinstance(code.value, Number):
    if isinstance(code.value.value, int): return type_comptime_integer
  if isinstance(code.value, String): return get_pointer_type(get_array_type(type_u8, len(code.value), sentinel=Value(type_comptime_integer, Number(0), constant=True)), constant=True)
  raise NotImplementedError(type(code.value))

class Scope:
  def __init__(self, parent: "Scope | None") -> None:
    self.data = {
      Identifier("$^"): Value(type_struct_literal, parent, constant=True),
    }
  def find(self, key: Identifier) -> Value | None:
    if key in self.data: return self.data[key]
    if self.data["$^"].contents: return self.data["$^"].contents.find(key)
    return None

def eval_code(code: Code, scope: Scope) -> Value:
  if not isinstance(code.value, Tuple):
    if isinstance(code.value, Identifier):
      entry = scope.find(code.value)
      if entry is None: raise KeyError(code.value)
      return entry
    else: return Value(infer_type(code), code.value, constant=True)
  op, *args = code.value
  proc = eval_code(op, scope)
  pargs = [eval_code(arg, scope) if proc.ty != type_macro else arg for arg in args]
  return proc.contents(*pargs, calling_scope=scope)

def compiler_assign_constant(name: Code, value: Code, **kwargs) -> Value:
  assert isinstance(name.value, Identifier)
  assert name.value not in kwargs["calling_scope"].data
  kwargs["calling_scope"].data[name.value] = eval_code(value, kwargs["calling_scope"])
  kwargs["calling_scope"].data[name.value].constant = True
  return value_void

def compiler_assign_variable(name: Code, value: Code, **kwargs) -> Value:
  assert isinstance(name.value, Identifier)
  assert name.value not in kwargs["calling_scope"].data
  kwargs["calling_scope"].data[name.value] = eval_code(value, kwargs["calling_scope"])
  kwargs["calling_scope"].data[name.value].constant = False
  return value_void

compiler_scope = Scope(None)
compiler_scope.data.update({
  Identifier("::"): Value(type_macro, compiler_assign_constant, constant=True),
  Identifier(":="): Value(type_macro, compiler_assign_variable, constant=True),
})

with open("Aperion.aperi") as f: src = f.read()
pos = 0
file_scope = Scope(compiler_scope)
while True:
  code, next_pos = parse_code(src, pos)
  if code is None: break
  pos = next_pos
  result = eval_code(code, file_scope)
  if result != value_void: print(value_as_string(result))

for key, value in file_scope.data.items():
  print(f"({"::" if value.constant else ":="} {key} ($cast {type_as_string(value.ty)} {value_as_string(value, key)}))")
