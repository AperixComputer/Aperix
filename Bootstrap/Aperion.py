from dataclasses import dataclass

class Identifier(str): pass
@dataclass(frozen=True, eq=True)
class Number:
	value: int | float
	base: int
class String(str): pass
class Tuple(list): pass
@dataclass(frozen=True, eq=True)
class Code:
	location: int
	data: Identifier | Number | String | Tuple

class ParseException(Exception): pass

def parse_code(s: str, p: int) -> tuple[Code | None, int]:
	level = 0
	stack = []
	while True:
		while True:
			while p < len(s) and s[p] in " \t\n\r": p += 1
			if p < len(s) and s[p] == ";":
				while p < len(s) and s[p] != "\n": p += 1
				continue
			break
		if p >= len(s): break
		start = p
		if s[p] == "(":
			p += 1
			level += 1
			stack.append(Code(start, Tuple()))
		elif s[p] == ")":
			p += 1
			if level == 0: raise ParseException("unmatched closing parenthesis")
			level -= 1
			if len(stack) > 1:
				popped = stack.pop()
				stack[-1].data.append(popped)
		elif s[p] == "'":
			p += 1
			code, next_pos = parse_code(s, p)
			if code is None: raise ParseException("quoted nothing")
			p = next_pos
			(stack[-1].data if len(stack) > 0 else stack).append(Code(start, Tuple([Code(start, Identifier("$code")), code])))
		elif s[p].isdigit():
			is_float = False
			base = 10
			while p < len(s) and s[p].isdigit(): p += 1
			if p < len(s) and s[p] == ".":
				p += 1
				is_float = True
				while p < len(s) and s[p].isdigit(): p += 1
			if p < len(s) and s[p].lower() == "e":
				p += 1
				is_float = True
				if p < len(s) and s[p] in "+-": p += 1
				if p >= len(s) or not s[p].isdigit(): raise ParseException("invalid float literal")
				while p < len(s) and s[p].isdigit(): p += 1
			(stack[-1].data if len(stack) > 0 else stack).append(Code(start, Number((float if is_float else int)(s[start:p]), base)))
		elif s[p] == '"':
			p += 1
			while p < len(s) and (s[p - 1] == "\\" or s[p] != '"'): p += 1
			if p >= len(s) or s[p] != '"': raise ParseException("unterminated string literal")
			p += 1
			(stack[-1].data if len(stack) > 0 else stack).append(Code(start, String(s[start+1:p-1])))
		else:
			while p < len(s) and s[p] not in "() \t\n\r": p += 1
			(stack[-1].data if len(stack) > 0 else stack).append(Code(start, Identifier(s[start:p])))
		if p < len(s) and s[p - 1] not in "()" and s[p] not in "() \t\n\r": raise ParseException("conjoined expressions")
		if level == 0: break
	if level != 0: raise ParseException("missing closing parenthesis")
	return stack.pop() if len(stack) > 0 else None, p

def code_as_string(code: Code) -> str:
	if not isinstance(code.data, Tuple): return str(code.data)
	else: return "(" + " ".join(map(code_as_string, code.data)) + ")"

@dataclass(frozen=True, eq=True)
class Type: pass
@dataclass(frozen=True, eq=True)
class Integer(Type):
	bits: int
	signed: bool
@dataclass(frozen=True, eq=True)
class Float(Type):
	bits: int
@dataclass(frozen=True, eq=True)
class Procedure(Type):
	parameters: tuple[Type]
	returns: Type
	calling_convention: int
	is_macro: bool
@dataclass(frozen=True, eq=True)
class Pointer(Type):
	child: Type
	constant: bool
@dataclass(frozen=True, eq=True)
class Array(Type):
	child: Type
	count: int
	sentinel: "Value | None"

type_type = Type()
type_code = Type()
type_anytype = Type()
type_noreturn = Type()
type_void = Type()
type_bool = Type()
type_struct_literal = Type()
type_comptime_integer = Type()
type_comptime_float = Type()
type_integers = {}
type_floats = {}
type_arrays = {}
type_pointers = {}
type_structs = {}
type_enums = {}
type_enum_flags = {}
type_unions = {}
type_procedures = {}

def get_proc_type(parameters: list[Type], returns: Type, calling_convention: int, is_macro: bool) -> Procedure:
	key = Procedure(tuple(parameters), returns, calling_convention, is_macro)
	if key not in type_procedures: type_procedures[key] = key
	return type_procedures[key]

def get_integer_type(bits: int, signed: bool) -> Integer:
	key = Integer(bits, signed)
	if key not in type_integers: type_integers[key] = key
	return type_integers[key]

def get_pointer_type(child: Type, constant: bool) -> Pointer:
	key = Pointer(child, constant)
	if key not in type_pointers: type_pointers[key] = key
	return type_pointers[key]

def get_array_type(child: Type, count: int, sentinel: "Value | None") -> Array:
	key = Array(child, count, sentinel)
	if key not in type_arrays: type_arrays[key] = key
	return type_arrays[key]

def type_as_string(ty: Type) -> str:
	if ty is type_type: return "($type 'TYPE)"
	if ty is type_code: return "($type 'CODE)"
	if ty is type_anytype: return "($type 'ANYTYPE)"
	if ty is type_noreturn: return "($type 'NORETURN)"
	if ty is type_void: return "($type 'VOID)"
	if ty is type_bool: return "($type 'BOOL)"
	raise NotImplementedError(ty)

def infer_type(code: Code) -> Type:
	if isinstance(code.data, String): return get_pointer_type(get_array_type(get_integer_type(8, False), len(code.data), sentinel=Value(get_integer_type(8, False), Number(0, 10))), constant=True)
	if isinstance(code.data, Number): return type_comptime_integer if isinstance(code.data, int) else type_comptime_float
	raise NotImplementedError(type(code.data))

@dataclass(frozen=True, eq=True)
class Value:
	ty: Type
	contents: Code | None

value_void = Value(type_void, None)

def value_as_string(value: Value) -> str:
	if value.ty is type_code: return code_as_string(value.contents)
	if value.ty in type_procedures:
		return f"($cast ($type 'PROCEDURE #parameters ($tuple {" ".join(map(type_as_string, value.ty.parameters))}) #returns {type_as_string(value.ty.returns)} #is_macro {value.ty.is_macro}) 0x{id(value.contents):08X})"
	if value.ty is type_comptime_integer or value.ty is type_comptime_float: return str(value.contents.value)
	raise NotImplementedError(value)

@dataclass(frozen=True, eq=True)
class ScopeEntry(Value):
	constant: bool

class Scope:
	def __init__(self, parent: "Scope | None") -> None:
		self.parent = parent
		self.entries: dict[Identifier, ScopeEntry] = {}
	def find(self, key: Identifier) -> ScopeEntry | None:
		if key in self.entries: return self.entries[key]
		if self.parent is not None: return self.parent.find(key)
		return None

def compiler_assign_constant(identifier: Code, value: Value, **kwargs) -> Value:
	if not isinstance(identifier.data, Identifier): raise EvaluationError("argument 1 must be an identifier")
	if identifier.data in kwargs["calling_scope"].entries: raise EvaluationError(f"attempted to redefine {identifier.data}")
	kwargs["calling_scope"].entries[identifier.data] = ScopeEntry(value.ty, value.contents, constant=True)
	return value_void

def compiler_assign_variable(identifier: Code, value: Value, **kwargs) -> Value:
	if not isinstance(identifier.data, Identifier): raise EvaluationError("argument 1 must be an identifier")
	if identifier.data in kwargs["calling_scope"]: raise EvaluationError(f"attempted to redefine {identifier.data}")
	kwargs["calling_scope"].entries[identifier.data] = ScopeEntry(value.ty, value.contents, constant=False)
	return value_void

def compiler_get_code_of(code: Code, **kwargs) -> Value:
	return Value(type_code, code)

compiler_scope = Scope(None)
compiler_scope.entries.update({
	Identifier("::"): ScopeEntry(get_proc_type([type_code, type_anytype], type_void, 0, True), compiler_assign_constant, constant=True),
	Identifier(":="): ScopeEntry(get_proc_type([type_code, type_anytype], type_void, 0, True), compiler_assign_variable, constant=True),
	Identifier("$code"): ScopeEntry(get_proc_type([type_code], type_code, 0, True), compiler_get_code_of, constant=True)
})

class EvaluationError(Exception): pass

def eval_code(code: Code, scope: Scope) -> Value:
	if not isinstance(code.data, Tuple):
		if isinstance(code.data, Identifier):
			entry = scope.find(code.data)
			if entry is None: raise EvaluationError(f"'{code.data}' not in scope")
			return entry
		else: return Value(infer_type(code), code.data)
	op, *args = code.data
	proc = eval_code(op, scope)
	pargs = [eval_code(arg, scope) if not proc.ty.is_macro or proc.ty.parameters[i] is not type_code else arg for i, arg in enumerate(args)]
	result = proc.contents(*pargs, calling_scope=scope)
	return result
	# return cast_value(result, proc.ty.returns)

def dofile(file: str, scope: Scope) -> None:
	with open(file) as f: src = f.read()
	pos = 0
	while True:
		code, next_pos = parse_code(src, pos)
		if code is None: break
		pos = next_pos
		# print(code_as_string(code))
		result = eval_code(code, scope)
		if result is not value_void: print(value_as_string(result))

def dostring(src: str, scope: Scope) -> None:
	pos = 0
	while True:
		code, next_pos = parse_code(src, pos)
		if code is None: break
		pos = next_pos
		# print(code_as_string(code))
		result = eval_code(code, scope)
		if result is not value_void: print(value_as_string(result))

def repl(scope: Scope) -> None:
	while True:
		try: src = input("> ")
		except (KeyboardInterrupt, EOFError): print(""); break
		try: dostring(src, scope)
		except ParseException as e: print("parse error:", e)
		except EvaluationError as e: print("eval error:", e)

if __name__ == "__main__":
	import sys
	file_scope = Scope(compiler_scope)
	if len(sys.argv) <= 1: repl(file_scope)
	else: dofile(sys.argv[1], file_scope)
