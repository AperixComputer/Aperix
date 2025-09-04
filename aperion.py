import sys
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

class TokenKind(IntEnum):
  END_OF_INPUT = 128
  ERROR = 129
  IDENTIFIER = 130
  NUMBER = 131
  KEYWORD_IF = 148
  KEYWORD_ELSE = 149
  KEYWORD_RETURN = 150
  KEYWORD_CAST = 151
  KEYWORD_FOR = 152
  KEYWORD_TYPE = 153
  KEYWORD_ENUM = 154

  @staticmethod
  def as_str(kind: int) -> str: return TokenKind(kind).name if kind in TokenKind else f"'{chr(kind)}'"

@dataclass
class Token:
  kind: int
  location: int
  length: int

  def as_str(self, s: str) -> str: return s[self.location:self.location + self.length]

def token_at(s: str, p: int) -> Token:
  while True:
    while p < len(s) and s[p].isspace(): p += 1
    if p + 1 < len(s) and s[p] == '/' and s[p + 1] == '/':
      while p < len(s) and s[p] != '\n': p += 1
      continue
    break
  if p >= len(s): return Token(TokenKind.END_OF_INPUT, p, 0)
  start = p
  if s[p].isalpha() or s[p] == '_':
    while p < len(s) and (s[p].isalnum() or s[p] == '_'): p += 1
    if s[start:p] == "if": return Token(TokenKind.KEYWORD_IF, start, p - start)
    if s[start:p] == "else": return Token(TokenKind.KEYWORD_ELSE, start, p - start)
    if s[start:p] == "cast": return Token(TokenKind.KEYWORD_CAST, start, p - start)
    if s[start:p] == "return": return Token(TokenKind.KEYWORD_RETURN, start, p - start)
    if s[start:p] == "for": return Token(TokenKind.KEYWORD_FOR, start, p - start)
    if s[start:p] == "type": return Token(TokenKind.KEYWORD_TYPE, start, p - start)
    if s[start:p] == "enum": return Token(TokenKind.KEYWORD_ENUM, start, p - start)
    return Token(TokenKind.IDENTIFIER, start, p - start)
  if s[p].isdigit():
    while p < len(s) and s[p].isdigit(): p += 1
    return Token(TokenKind.NUMBER, start, p - start)
  if s[p] in "+-*/%&|~^:=;.,(){}": return Token(ord(s[p]), start, 1)
  return Token(TokenKind.ERROR, start, 1)

@dataclass
class Code: pass
@dataclass
class Variable(Code):
  token: Token
@dataclass
class Number(Code):
  token: Token
  value: int
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
class BinaryOperator(Code):
  lhs: Code
  op: Token
  rhs: Code
  wrapped: bool
@dataclass
class Call(Code):
  lhs: Code
  arguments: list[Code]
@dataclass
class Accessor(Code):
  lhs: Code
  rhs: Token
@dataclass
class Procedure(Code):
  lhs: Token
  parameters: list[Declaration]
  return_type: Code
  attributes: list[Declaration]
  body: Block
@dataclass
class Return(Code):
  rhs: Code | None
@dataclass
class If(Code):
  test: Code
  conseq: Code
  alt: Code | None
@dataclass
class Cast(Code):
  lhs: Code
  typespec: Code
@dataclass
class TypeInst(Code):
  kind: Code
@dataclass
class EnumLiteral(Code):
  token: Token

class ParseError(Exception):
  def __init__(self, message: str, location: int) -> None:
    self.message = message
    self.location  = location

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
    if expect != token.kind: raise ParseError(f"expected {TokenKind.as_str(expect)}, got {TokenKind.as_str(token.kind)}", token.location)
    self.p = token.location + token.length
    return token

  def parse_factor(self) -> Code:
    result: Code | None = None
    if self.peek().kind == ord('('):
      self.eat(ord('('))
      result = self.parse_expression(wrapped=True)
      self.eat(ord(')'))
    elif self.peek().kind == TokenKind.KEYWORD_CAST:
      self.eat(TokenKind.KEYWORD_CAST)
      self.eat(ord('.'))
      self.eat(ord('('))
      lhs = self.parse_expression()
      self.eat(ord(','))
      typespec = self.parse_expression()
      self.eat(ord(')'))
      result = Cast(lhs, typespec)
    elif self.peek().kind == TokenKind.KEYWORD_TYPE:
      self.eat(TokenKind.KEYWORD_TYPE)
      self.eat(ord('.'))
      self.eat(ord('('))
      kind = self.parse_expression()
      self.eat(ord(')'))
      result = TypeInst(kind)
    elif self.peek().kind == TokenKind.KEYWORD_ENUM:
      self.eat(TokenKind.KEYWORD_ENUM)
      self.eat(ord('.'))
      token = self.eat(TokenKind.IDENTIFIER)
      result = EnumLiteral(token)
    elif self.peek().kind == TokenKind.IDENTIFIER:
      token = self.eat(TokenKind.IDENTIFIER)
      result = Variable(token)
    elif self.peek().kind == TokenKind.NUMBER:
      token = self.eat(TokenKind.NUMBER)
      value = int(token.as_str(self.s), base=0)
      result = Number(token, value)
    if result is None: raise ParseError(f"unknown expression entrant {TokenKind.as_str(self.peek().kind)}", self.peek().location)
    while True:
      if self.peek().kind == ord('.'):
        self.eat(ord('.'))
        if self.peek().kind == ord('('):
          self.eat(ord('('))
          arguments: list[Code] = []
          while self.peek().kind != ord(')'):
            arguments.append(self.parse_statement_or_expression())
            if self.peek().kind == ord(','): self.eat(ord(','))
            else: break
          self.eat(ord(')'))
          result = Call(result, arguments)
        elif self.peek().kind == TokenKind.KEYWORD_CAST:
          self.eat(TokenKind.KEYWORD_CAST)
          self.eat(ord('.'))
          self.eat(ord('('))
          typespec = self.parse_expression()
          self.eat(ord(')'))
          result = Cast(result, typespec)
        else:
          rhs = self.eat(TokenKind.IDENTIFIER)
          result = Accessor(result, rhs)
        continue
      break
    return result

  def parse_term(self, wrapped: bool = False) -> Code:
    lhs = self.parse_factor()
    while self.peek().kind in [ord('*'), ord('/'), ord('%')]:
      op = self.eat(self.peek().kind)
      rhs = self.parse_factor()
      lhs = BinaryOperator(lhs, op, rhs, wrapped)
    return lhs

  def parse_expression(self, wrapped: bool = False) -> Code:
    lhs = self.parse_term(wrapped)
    while self.peek().kind in [ord('+'), ord('-')]:
      op = self.eat(self.peek().kind)
      rhs = self.parse_term()
      lhs = BinaryOperator(lhs, op, rhs, wrapped)
    return lhs

  def parse_procedure(self) -> Procedure:
    lhs = self.eat(TokenKind.IDENTIFIER)
    self.eat(ord('='))
    self.eat(ord('('))
    parameters: list[Declaration] = []
    while self.peek().kind != ord(')'):
      parameters.append(self.parse_declaration())
      if self.peek().kind == ord(','): self.eat(ord(','))
      else: break
    self.eat(ord(')'))
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
    return Procedure(lhs, parameters, return_type, attributes, body)

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
    if typespec is None and rhs is None: raise ParseError("declaration must have one of type or value", lhs.location)
    return Declaration(lhs, typespec, rhs)

  def parse_statement_or_expression(self) -> Code:
    if self.peek(2).kind == ord('=') and self.peek(3).kind == ord('(') and (self.peek(4).kind == ord(')') or self.peek(5).kind in [ord(':'), ord('=')]): return self.parse_procedure()
    if self.peek(2).kind in [ord(':'), ord('=')]: return self.parse_declaration()
    if self.peek().kind == TokenKind.KEYWORD_IF:
      self.eat(TokenKind.KEYWORD_IF)
      test = self.parse_expression()
      conseq = self.parse_statement_or_expression()
      alt: Code | None = None
      if self.peek().kind == TokenKind.KEYWORD_ELSE:
        self.eat(TokenKind.KEYWORD_ELSE)
        alt = self.parse_statement_or_expression()
      return If(test, conseq, alt)
    if self.peek().kind == TokenKind.KEYWORD_RETURN:
      self.eat(TokenKind.KEYWORD_RETURN)
      self.eat(ord('('))
      rhs: Code | None = None
      if self.peek().kind != ord(')'):
        rhs = self.parse_expression()
      self.eat(ord(')'))
      return Return(rhs)
    if self.peek().kind == ord('{'): return self.parse_block()
    return self.parse_expression()

  def parse_block(self, implicit: bool = False) -> Block:
    if not implicit: self.eat(ord('{'))
    children: list[Code] = []
    while (not implicit and self.peek().kind != ord('}')) or (implicit and self.peek().kind != TokenKind.END_OF_INPUT):
      children.append(self.parse_statement_or_expression())
    if not implicit: self.eat(ord('}'))
    return Block(children, implicit)

  def parse_file(self) -> Block:
    return self.parse_block(implicit=True)

def code_to_string(code: Code, s: str, level: int) -> str:
  if isinstance(code, Block):
    result = ""
    if not code.implicit: result += f"{"  " * (level - 1)}{{\n"
    result += "\n".join("  " * level + code_to_string(child, s, level + 1) for child in code.children)
    if not code.implicit: result += f"\n{"  " * (level - 1)}}}"
    return result
  if isinstance(code, Declaration):
    result = ""
    result += f"{code.lhs.as_str(s)}"
    if code.typespec is not None: result += f": {code_to_string(code.typespec, s, level)}"
    if code.rhs is not None: result += f" = {code_to_string(code.rhs, s, level)}"
    return result
  if isinstance(code, Number):
    return str(code.value)
  if isinstance(code, BinaryOperator):
    result = ""
    if code.wrapped: result += '('
    result += f"{code_to_string(code.lhs, s, level)} {code.op.as_str(s)} {code_to_string(code.rhs, s, level)}"
    if code.wrapped: result += ')'
    return result
  if isinstance(code, Variable):
    return f"{code.token.as_str(s)}"
  if isinstance(code, Procedure):
    result = ""
    result += f"{code.lhs.as_str(s)} = "
    result += f"({", ".join(code_to_string(parameter, s, level) for parameter in code.parameters)}) "
    result += f"{code_to_string(code.return_type, s, level)}"
    if len(code.attributes) > 0: result += f" #({", ".join(code_to_string(attribute, s, level) for attribute in code.attributes)})"
    result += "\n"
    result += code_to_string(code.body, s, level)
    return result
  if isinstance(code, Call):
    return f"{code_to_string(code.lhs, s, level)}.({", ".join(code_to_string(argument, s, level) for argument in code.arguments)})"
  if isinstance(code, If):
    result = ""
    result += f"if {code_to_string(code.test, s, level)}\n"
    result += "  " * level + f"{code_to_string(code.conseq, s, level + 1)}"
    if code.alt is not None:
      result += f"\n{"  " * (level - 1)}else\n"
      result += f"{code_to_string(code.alt, s, level)}"
    return result
  if isinstance(code, Return):
    return f"return({code_to_string(code.rhs, s, level) if code.rhs is not None else ""})"
  if isinstance(code, Cast):
    return f"cast.({code_to_string(code.lhs, s, level)}, {code_to_string(code.typespec, s, level)})"
  if isinstance(code, TypeInst):
    return f"type.({code_to_string(code.kind, s, level)})"
  if isinstance(code, EnumLiteral):
    return f"enum.{code.token.as_str(s)}"
  raise NotImplementedError(code.__class__.__name__)

if __name__ == "__main__":
  path = Path(sys.argv[1])
  src = path.read_text()

  parser = Parser(src)
  try:
    block = parser.parse_file()
    print(code_to_string(block, parser.s, 0))
  except ParseError as e: print(f"parse error @ {path.name}[{e.location}] near '{token_at(parser.s, e.location).as_str(parser.s)}': {e.message}")
