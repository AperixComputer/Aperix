from parser import *

def code_as_string(code: Code, s: str, level: int) -> str:
	if isinstance(code, Literal):
		if isinstance(code.value, EnumLiteral): return f"enum.{code.value}"
		elif isinstance(code.value, str): return '"' + code.value + '"'
		else: return f"{code.value}"
	if isinstance(code, Variable):
		return f"{code.token.as_str(s)}"
	if isinstance(code, Block):
		result = ""
		if not code.implicit: result += "  " * level + "{\n"
		result += "\n".join("  " * (level + 1 if not code.implicit else level) + code_as_string(child, s, level + 1 if not code.implicit else level) for child in code.children)
		if not code.implicit: result += "\n" + "  " * level + "}"
		return result
	if isinstance(code, Declaration):
		result = f"{code.lhs.as_str(s)}"
		if code.typespec is not None: result += f": {code_as_string(code.typespec, s, level)}"
		if code.rhs is not None: result += f" = {code_as_string(code.rhs, s, level)}"
		return result
	if isinstance(code, Procedure):
		result = f"{code.token.as_str(s)} = "
		result += "(" + ", ".join(code_as_string(parameter, s, level) for parameter in code.parameters) + ")"
		if code.return_type is not None: result += f" {code_as_string(code.return_type, s, level)}"
		if len(code.attributes) > 0: result += " #(" + ", ".join(code_as_string(parameter, s, level) for parameter in code.parameters) + ")"
		result += "\n" + code_as_string(code.body, s, level)
		return result
	if isinstance(code, BinaryOperator):
		def precedence_of(kind: int) -> int:
			if kind in [TokenKind.EQEQ, TokenKind.BANGEQ]: return 0
			if kind in [TokenKind.OROR]: return 1
			if kind in [TokenKind.ANDAND]: return 2
			if kind in [ord('+'), ord('-')]: return 3
			if kind in [ord('*'), ord('/'), ord('%')]: return 4
			raise NotImplementedError(TokenKind.as_str(kind))
		precedence = precedence_of(code.op.kind)
		lhs = code_as_string(code.lhs, s, level)
		if isinstance(code.lhs, BinaryOperator) and precedence_of(code.lhs.op.kind) < precedence: lhs = f"({lhs})"
		rhs = code_as_string(code.rhs, s, level)
		if isinstance(code.rhs, BinaryOperator) and precedence_of(code.rhs.op.kind) < precedence: rhs = f"({rhs})"
		return f"{lhs} {code.op.as_str(s)} {rhs}"
	if isinstance(code, Call):
		result = f"{code_as_string(code.lhs, s, level)}!({", ".join(code_as_string(argument, s, level) for argument in code.arguments)})"
		return result
	if isinstance(code, Cast):
		result = f"{code_as_string(code.lhs, s, level)}.({code_as_string(code.typespec, s, level)})"
		return result
	if isinstance(code, Return):
		return f"return {code_as_string(code.rhs, s, level)}"
	raise NotImplementedError(code.__class__.__name__)
