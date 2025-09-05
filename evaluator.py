from dataclasses import dataclass
from parser import *
from printer import code_as_string

@dataclass(frozen=True)
class Type: pass
@dataclass(frozen=True)
class CodeType(Type): pass
@dataclass(frozen=True)
class VoidType(Type): pass
@dataclass(frozen=True)
class IntegerType(Type):
	bits: int

type_type = Type()
type_code = CodeType()
type_void = VoidType()
type_i32 = IntegerType(32)

@dataclass
class Value:
	ty: Type
	contents: Type | Code | int | None

	@property
	def as_type(self) -> Type: assert self.ty is type_type and isinstance(self.contents, Type); return self.contents
	@property
	def as_code(self) -> Code: assert self.ty is type_code and isinstance(self.contents, Code); return self.contents
	@property
	def as_int(self) -> int: assert self.ty is type_i32 and isinstance(self.contents, int); return self.contents

value_void = Value(type_void, None)

def value_as_string(value: Value, s: str) -> str:
	if value.ty is type_code: return code_as_string(value.as_code, s, 0)
	if value.ty is type_i32: return str(value.as_int)
	raise NotImplementedError(value.ty.__class__.__name__)

@dataclass
class ScopeEntry:
	value: Value

class Scope:
	def __init__(self, parent: "Scope | None") -> None:
		self.parent = parent
		self.entries: dict[str, ScopeEntry] = {}
	def find(self, key: str) -> ScopeEntry | None:
		if key in self.entries: return self.entries[key]
		if self.parent is None: return None
		return self.parent.find(key)

def evaluate_code(code: Code, s: str, scope: Scope, echo_results: bool) -> Value:
	if isinstance(code, Block):
		block_scope = Scope(scope)
		for child in code.children:
			result = evaluate_code(child, s, block_scope, echo_results)
			if code.implicit and echo_results and result.ty is not type_void:
				print("=>", value_as_string(result, s))
		return value_void
	if isinstance(code, Declaration):
		name = code.lhs.as_str(s)
		ty: Value | None = None
		if code.typespec is not None: ty = evaluate_code(code.typespec, s, scope, echo_results)
		rhs: Value | None = None
		if code.rhs is not None: rhs = evaluate_code(code.rhs, s, scope, echo_results)
		if ty is not None:
			if rhs is not None: assert ty.as_type is rhs.ty
		else:
			assert rhs is not None
			ty = Value(type_type, rhs.ty)
		scope.entries[name] = ScopeEntry(Value(ty.as_type, rhs.contents if rhs is not None else None))
		return value_void
	if isinstance(code, PrefixOperator):
		return Value(type_i32, int(eval(f"not bool({evaluate_code(code.rhs, s, scope, echo_results).as_int})")))
	if isinstance(code, BinaryOperator):
		lhs = evaluate_code(code.lhs, s, scope, echo_results).as_int
		rhs2 = evaluate_code(code.rhs, s, scope, echo_results).as_int
		return Value(type_i32, eval(f"{lhs} {code.op.as_str(s)} {rhs2}"))
	if isinstance(code, Literal):
		if isinstance(code.value, int): return Value(type_i32, code.value)
		raise NotImplementedError(type(code.value))
	raise NotImplementedError(code.__class__.__name__)
