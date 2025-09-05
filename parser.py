from dataclasses import dataclass
from lexer import *

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
class PrefixOperator(Code):
	op: Token
	rhs: Code
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
		if result is None:
			if self.peek().kind == ord('('):
				self.eat(ord('('))
				result = self.parse_expression()
				self.eat(ord(')'))
			elif self.peek().kind == ord('!'):
				op = self.eat(ord('!'))
				rhs = self.parse_factor()
				result = PrefixOperator(op, rhs)
			else: raise ParseError("unknown factor", self.peek())
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
