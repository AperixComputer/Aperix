#!/usr/bin/env python3

import sys
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

class TokenKind(IntEnum):
	END_OF_INPUT = 128
	ERROR = 129
	IDENTIFIER = 130
	INTEGER = 131
	FLOAT = 132
	STRING = 133

	EQEQ = 135
	BANGEQ = 136
	ANDAND = 137
	OROR = 138

	KEYWORD_RETURN = 148
	KEYWORD_BREAK = 149
	KEYWORD_CONTINUE = 150
	KEYWORD_IF = 151
	KEYWORD_ELSE = 152
	KEYWORD_FOR = 153
	KEYWORD_STRUCT = 154
	KEYWORD_UNION = 155
	KEYWORD_ENUM = 156

	@staticmethod
	def as_str(kind: int) -> str: return TokenKind(kind).name if kind in TokenKind else f"'{chr(kind)}'"

@dataclass
class Token:
	kind: int
	location: int
	length: int

	def as_str(self, s: str) -> str: return s[self.location:self.location + self.length]

def isbasedigit(c: str, base: int) -> bool:
	if base == 2: return '0' <= c <= '1'
	if base == 8: return '0' <= c <= '7'
	if base == 10: return '0' <= c <= '9'
	if base == 16: return '0' <= c <= '9' or 'a' <= c.lower() <= 'f'
	raise NotImplementedError(base)

def token_at(s: str, p: int) -> Token:
	while True:
		while p < len(s) and s[p].isspace(): p += 1
		if p + 1 < len(s) and s[p:p + 2] == "//":
			while p < len(s) and s[p] != '\n': p += 1
			continue
		break
	if p >= len(s): return Token(TokenKind.END_OF_INPUT, p, 0)
	start = p
	if s[p].isalpha() or s[p] == '_':
		while p < len(s) and (s[p].isalnum() or s[p] == '_'): p += 1
		if s[start:p] == "return": return Token(TokenKind.KEYWORD_RETURN, start, p - start)
		if s[start:p] == "break": return Token(TokenKind.KEYWORD_BREAK, start, p - start)
		if s[start:p] == "continue": return Token(TokenKind.KEYWORD_CONTINUE, start, p - start)
		if s[start:p] == "if": return Token(TokenKind.KEYWORD_IF, start, p - start)
		if s[start:p] == "else": return Token(TokenKind.KEYWORD_ELSE, start, p - start)
		if s[start:p] == "for": return Token(TokenKind.KEYWORD_FOR, start, p - start)
		if s[start:p] == "struct": return Token(TokenKind.KEYWORD_STRUCT, start, p - start)
		if s[start:p] == "union": return Token(TokenKind.KEYWORD_UNION, start, p - start)
		if s[start:p] == "enum": return Token(TokenKind.KEYWORD_ENUM, start, p - start)
		return Token(TokenKind.IDENTIFIER, start, p - start)
	if s[p].isdigit():
		is_float = False
		base = 10
		if p + 1 < len(s) and s[p] == '0' and s[p + 1] in "box":
			p += 1
			if s[p] == 'b': base = 2
			if s[p] == 'o': base = 8
			if s[p] == 'x': base = 16
			p += 1
			if p >= len(s) or not isbasedigit(s[p], base): return Token(TokenKind.ERROR, start, p - start)
		while p < len(s) and isbasedigit(s[p], base): p += 1
		if p + 1 < len(s) and s[p] == '.' and s[p + 1].isdigit():
			p += 1
			if base != 10: return Token(TokenKind.ERROR, start, p - start)
			is_float = True
			while p < len(s) and s[p].isdigit(): p += 1
		if p + 1 < len(s) and s[p].lower() == 'e' and s[p + 1].isdigit():
			p += 1
			if base != 10: return Token(TokenKind.ERROR, start, p - start)
			is_float = True
			while p < len(s) and s[p].isdigit(): p += 1
		return Token(TokenKind.FLOAT if is_float else TokenKind.INTEGER, start, p - start)
	if s[p] == '"':
		p += 1
		while p < len(s) and (s[p - 1] == '\\' or s[p] != '"'): p += 1
		if p >= len(s) or s[p] != '"': return Token(TokenKind.ERROR, start, p - start)
		p += 1
		return Token(TokenKind.STRING, start, p - start)
	if p + 1 < len(s):
		if s[p:p + 2] == "==": return Token(TokenKind.EQEQ, start, 2)
		if s[p:p + 2] == "!=": return Token(TokenKind.BANGEQ, start, 2)
		if s[p:p + 2] == "&&": return Token(TokenKind.ANDAND, start, 2)
		if s[p:p + 2] == "||": return Token(TokenKind.OROR, start, 2)
	if s[p] in "+-*/#%&|!~^:=.,;{}()": return Token(ord(s[p]), start, 1)
	return Token(TokenKind.ERROR, start, 1)

class ParseError(Exception):
	def __init__(self, message: str, token: Token) -> None:
		self.message = message
		self.token = token

class EnumLiteral(str): pass

@dataclass
class Code: pass
@dataclass
class Literal(Code):
	token: Token
	value: int | float | str | EnumLiteral
@dataclass
class Variable(Code):
	token: Token
@dataclass
class Block(Code):
	children: list[Code]
	implicit: bool
@dataclass
class Declaration(Code):
	lhs: Token
	typespec: Code | None
	rhs: Code | None
@dataclass
class Procedure(Code):
	token: Token
	parameters: list[Declaration]
	return_type: Code | None
	attributes: list[Declaration]
	body: Block
@dataclass
class BinaryOperator(Code):
	lhs: Code
	op: Token
	rhs: Code
@dataclass
class Call(Code):
	lhs: Code
	arguments: list[Code]
@dataclass
class Cast(Code):
	lhs: Code
	typespec: Code
@dataclass
class Return(Code):
	rhs: Code

@dataclass
class Parser:
	s: str
	p: int = 0

	def peek(self, n: int = 1) -> Token:
		assert n > 0
		token: Token | None = None
		p = self.p
		for _ in range(n):
			token = token_at(self.s, p)
			p = token.location + token.length
		assert token is not None
		return token

	def eat(self, expect: int) -> Token:
		token = token_at(self.s, self.p)
		if token.kind != expect: raise ParseError(f"expected {TokenKind.as_str(expect)}, got {TokenKind.as_str(token.kind)}", token)
		self.p = token.location + token.length
		return token

	def parse_single(self) -> Code | None:
		result: Code | None = None
		if self.peek().kind == TokenKind.IDENTIFIER:
			token = self.eat(TokenKind.IDENTIFIER)
			result = Variable(token)
		elif self.peek().kind in [TokenKind.INTEGER, TokenKind.FLOAT]:
			token = self.eat(self.peek().kind)
			value = int(token.as_str(self.s), base=0) if token.kind == TokenKind.INTEGER else float(token.as_str(self.s))
			result = Literal(token, value)
		elif self.peek().kind == TokenKind.STRING:
			token = self.eat(TokenKind.STRING)
			value = token.as_str(self.s)[1:-1]
			result = Literal(token, value)
		elif self.peek().kind == TokenKind.KEYWORD_ENUM and self.peek(2).kind == ord('.'):
			self.eat(TokenKind.KEYWORD_ENUM)
			self.eat(ord('.'))
			token = self.eat(TokenKind.IDENTIFIER)
			result = Literal(token, EnumLiteral(token.as_str(self.s)))
		return result

	def parse_factor(self) -> Code:
		result = self.parse_single()
		if result is None: raise ParseError("unknown factor", self.peek())
		while True:
			if self.peek().kind == ord('.'):
				self.eat(ord('.'))
				if self.peek().kind == TokenKind.IDENTIFIER and self.peek(2).kind == ord('!'):
					lhs = Variable(self.eat(TokenKind.IDENTIFIER))
					self.eat(ord('!'))
					arguments: list[Code] = [result]
					if self.peek().kind == ord('('):
						self.eat(ord('('))
						while self.peek().kind != ord(')'):
							if self.peek(2).kind == ord('='):
								arguments.append(self.parse_declaration())
							else:
								arguments.append(self.parse_expression())
							if self.peek().kind == ord(','): self.eat(ord(','))
							else: break
						self.eat(ord(')'))
					else:
						result = self.parse_single()
						if result is None: raise ParseError("chained call expects one argument", self.peek())
						arguments.append(result)
					result = Call(lhs, arguments)
					continue
				elif self.peek().kind == ord('('):
					self.eat(ord('('))
					typespec = self.parse_expression()
					self.eat(ord(')'))
					result = Cast(result, typespec)
				else: raise ParseError("unknown chain", self.peek())
			break
		return result

	def parse_term(self) -> Code:
		lhs = self.parse_factor()
		while self.peek().kind in [ord('*'), ord('/'), ord('%')]:
			op = self.eat(self.peek().kind)
			rhs = self.parse_factor()
			lhs = BinaryOperator(lhs, op, rhs)
		return lhs

	def parse_conjugate(self) -> Code:
		lhs = self.parse_term()
		while self.peek().kind in [ord('+'), ord('-')]:
			op = self.eat(self.peek().kind)
			rhs = self.parse_term()
			lhs = BinaryOperator(lhs, op, rhs)
		return lhs

	def parse_expression(self) -> Code:
		lhs = self.parse_conjugate()
		while self.peek().kind in [TokenKind.EQEQ, TokenKind.BANGEQ]:
			op = self.eat(self.peek().kind)
			rhs = self.parse_conjugate()
			lhs = BinaryOperator(lhs, op, rhs)
		return lhs

	def parse_procedure(self) -> Procedure:
		token = self.eat(TokenKind.IDENTIFIER)
		self.eat(ord('='))
		self.eat(ord('('))
		parameters: list[Declaration] = []
		while self.peek().kind != ord(')'):
			parameters.append(self.parse_declaration())
			if self.peek().kind == ord(','): self.eat(ord(','))
			else: break
		self.eat(ord(')'))
		return_type: Code | None = None
		if self.peek().kind not in [ord('#'), ord('{')]:
			return_type = self.parse_expression()
		attributes: list[Declaration] = []
		if self.peek().kind == ord('#'):
			self.eat(ord('#'))
			self.eat(ord('('))
			while self.peek().kind != ord(')'):
				attributes.append(self.parse_declaration())
				if self.peek().kind == ord(','): self.eat(ord(','))
				else: break
			self.eat(ord(')'))
		body = self.parse_block()
		return Procedure(token, parameters, return_type, attributes, body)

	def parse_declaration(self) -> Declaration:
		lhs = self.eat(TokenKind.IDENTIFIER)
		typespec: Code | None = None
		if self.peek().kind == ord(':'):
			self.eat(ord(':'))
			typespec = self.parse_expression()
		rhs: Code | None = None
		if self.peek().kind == ord('='):
			self.eat(ord('='))
			rhs = self.parse_expression()
		if typespec is None and rhs is None: raise ParseError("declaration must have type or value", lhs)
		return Declaration(lhs, typespec, rhs)

	def parse_statement_or_expression(self) -> Code:
		if self.peek(2).kind == ord('=') and self.peek(3).kind == ord('(') and (self.peek(4).kind == ord(')') or self.peek(5).kind in [ord(':'), ord('=')]): return self.parse_procedure()
		if self.peek(2).kind in [ord(':'), ord('=')]: return self.parse_declaration()
		if self.peek().kind == TokenKind.KEYWORD_RETURN:
			self.eat(TokenKind.KEYWORD_RETURN)
			rhs = self.parse_expression()
			return Return(rhs)
		return self.parse_expression()

	def parse_block(self, implicit: bool = False) -> Block:
		if not implicit: self.eat(ord('{'))
		children: list[Code] = []
		while (not implicit and self.peek().kind != ord('}')) or (implicit and self.peek().kind != TokenKind.END_OF_INPUT):
			children.append(self.parse_statement_or_expression())
		if not implicit: self.eat(ord('}'))
		return Block(children, implicit)

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
	if isinstance(code, Call):
		result = f"{code_as_string(code.lhs, s, level)}!({", ".join(code_as_string(argument, s, level) for argument in code.arguments)})"
		return result
	if isinstance(code, Cast):
		result = f"{code_as_string(code.lhs, s, level)}.({code_as_string(code.typespec, s, level)})"
		return result
	if isinstance(code, Return):
		return f"return {code_as_string(code.rhs, s, level)}"
	raise NotImplementedError(code.__class__.__name__)

if __name__ == "__main__":
	if len(sys.argv) < 2:
		print("usage: ./aperion.py file.aperion")
		sys.exit(1)

	path = Path(sys.argv[1])
	src = path.read_text()
	parser = Parser(src)
	try:
		module = parser.parse_block(implicit=True)
		print(code_as_string(module, parser.s, 0))
	except ParseError as e: print(f"parse error @ {path.name}[{e.token.location}] near '{e.token.as_str(parser.s)}': {e.message}")
