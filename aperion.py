import sys
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

class TokenKind(IntEnum):
  END_OF_INPUT = 128
  ERROR = 129
  IDENTIFIER = 130
  NUMBER = 131
  STRING = 132

  EQEQ = 138
  BANGEQ = 139
  COLONEQ = 140
  ANDAND = 141
  OROR = 142

  KEYWORD_IF = 148
  KEYWORD_ELSE = 149
  KEYWORD_FOR = 150
  KEYWORD_RETURN = 151
  KEYWORD_BREAK = 152
  KEYWORD_CONTINUE = 153
  KEYWORD_ENUM = 154
  KEYWORD_STRUCT = 155
  KEYWORD_UNION = 156

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
  while p < len(s) and s[p].isspace(): p += 1
  if p >= len(s): return Token(TokenKind.END_OF_INPUT, p, 0)
  start = p
  if s[p].isalpha() or s[p] == '_':
    while p < len(s) and (s[p].isalnum() or s[p] == '_'): p += 1
    if s[start:p] == "if": return Token(TokenKind.KEYWORD_IF, start, p - start)
    if s[start:p] == "else": return Token(TokenKind.KEYWORD_ELSE, start, p - start)
    if s[start:p] == "for": return Token(TokenKind.KEYWORD_FOR, start, p - start)
    if s[start:p] == "return": return Token(TokenKind.KEYWORD_RETURN, start, p - start)
    if s[start:p] == "break": return Token(TokenKind.KEYWORD_BREAK, start, p - start)
    if s[start:p] == "continue": return Token(TokenKind.KEYWORD_CONTINUE, start, p - start)
    if s[start:p] == "enum": return Token(TokenKind.KEYWORD_ENUM, start, p - start)
    if s[start:p] == "struct": return Token(TokenKind.KEYWORD_STRUCT, start, p - start)
    if s[start:p] == "union": return Token(TokenKind.KEYWORD_UNION, start, p - start)
    return Token(TokenKind.IDENTIFIER, start, p - start)
  if s[p].isdigit() or (p + 1 < len(s) and s[p] in "+-" and s[p + 1].isdigit()):
    base = 10
    if s[p] in "+-": p += 1
    if p + 1 < len(s) and s[p] == '0' and s[p + 1] in "box":
      p += 1
      if s[p] == 'b': base = 2
      if s[p] == 'o': base = 8
      if s[p] == 'x': base = 16
      p += 1
      if p >= len(s) or not isbasedigit(s[p], base): return Token(TokenKind.ERROR, start, p - start)
    while p < len(s) and isbasedigit(s[p], base): p += 1
    if p < len(s) and s[p] == '.':
      p += 1
      if base != 10 or p >= len(s) or not s[p].isdigit(): return Token(TokenKind.ERROR, start, p - start)
      while p < len(s) and s[p].isdigit(): p += 1
    if p < len(s) and s[p].lower() == 'e':
      p += 1
      if p < len(s) and s[p] in "+-": p += 1
      if base != 10 or p >= len(s) or not s[p].isdigit(): return Token(TokenKind.ERROR, start, p - start)
      while p < len(s) and s[p].isdigit(): p += 1
    return Token(TokenKind.NUMBER, start, p - start)
  if p + 1 < len(s):
    if s[p:p + 2] == "==": return Token(TokenKind.EQEQ, start, 2)
    if s[p:p + 2] == "!=": return Token(TokenKind.BANGEQ, start, 2)
    if s[p:p + 2] == ":=": return Token(TokenKind.COLONEQ, start, 2)
    if s[p:p + 2] == "&&": return Token(TokenKind.ANDAND, start, 2)
    if s[p:p + 2] == "||": return Token(TokenKind.OROR, start, 2)
  if s[p] in "+-*/%&|~^:=.,;!(){}[]": return Token(ord(s[p]), start, 1)
  return Token(TokenKind.ERROR, p, 1)

class ParseError(Exception):
  def __init__(self, message: str, token: Token) -> None:
    self.message = message
    self.token = token

@dataclass
class Code: pass
@dataclass
class Block(Code):
  children: list[Code]
  implicit: bool
@dataclass
class Number(Code):
  token: Token
  value: int
  wrapped: bool
@dataclass
class Variable(Code):
  identifier: Token
  wrapped: bool
@dataclass
class Declaration(Code):
  lhs: Token
  type_expr: Code | None
  rhs: Code | None
@dataclass
class Reassignment(Code):
  lhs: Code
  rhs: Code
@dataclass
class Accessor(Code):
  lhs: Code
  rhs: Token
@dataclass
class Call(Code):
  lhs: Code
  arguments: list[Code]
@dataclass
class BinaryOperator(Code):
  lhs: Code
  op: Token
  rhs: Code
  wrapped: bool
@dataclass
class PostfixOperator(Code):
  lhs: Code
  op: Token
@dataclass
class Procedure(Code):
  identifier: Token
  parameters: list[Declaration]
  return_type: Code | None
  attributes: list[Declaration]
  body: Block
@dataclass
class If(Code):
  test: Code
  conseq: Code
  alt: Code | None
@dataclass
class Return(Code):
  expression: Code
@dataclass
class VoidExpr(Code): pass
@dataclass
class EnumLiteral(Code):
  identifier: Token

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

  def parse_factor(self, wrapped: bool = False) -> Code:
    result: Code | None = None
    if self.peek().kind == TokenKind.IDENTIFIER:
      identifier = self.eat(TokenKind.IDENTIFIER)
      result = Variable(identifier, wrapped)
    elif self.peek().kind == TokenKind.NUMBER:
      token = self.eat(TokenKind.NUMBER)
      value = int(token.as_str(self.s), base=0)
      result = Number(token, value, wrapped)
    elif self.peek().kind == ord('('):
      self.eat(ord('('))
      result = self.parse_expression(wrapped=True)
      self.eat(ord(')'))
    elif self.peek().kind == ord("{"):
      self.eat(ord('{'))
      self.eat(ord('}'))
      return VoidExpr()
    elif self.peek().kind == TokenKind.KEYWORD_ENUM:
      self.eat(TokenKind.KEYWORD_ENUM)
      self.eat(ord('.'))
      identifier = self.eat(TokenKind.IDENTIFIER)
      result = EnumLiteral(identifier)
    if result is None: raise ParseError(f"unknown factor entrant: {TokenKind.as_str(self.peek().kind)}", self.peek())
    if self.peek().kind == TokenKind.COLONEQ:
      self.eat(TokenKind.COLONEQ)
      rhs = self.parse_expression()
      return Reassignment(result, rhs)
    while True:
      if self.peek().kind == ord('.'):
        self.eat(ord('.'))
        if self.peek().kind == TokenKind.IDENTIFIER:
          rhs = self.eat(TokenKind.IDENTIFIER)
          result = Accessor(result, rhs)
          continue
        elif self.peek().kind in [ord('!'), ord('&'), ord('^'), ord('-'), ord('~')]:
          op = self.eat(self.peek().kind)
          result = PostfixOperator(result, op)
          continue
        raise ParseError(f"unknown chain factor: {TokenKind.as_str(self.peek().kind)}", self.peek())
      if self.peek().kind == ord('!'):
        self.eat(ord('!'))
        self.eat(ord('('))
        arguments: list[Code] = []
        while self.peek().kind != ord(')'):
          if self.peek(2).kind == ord('='):
            arguments.append(self.parse_declaration())
          else:
            arguments.append(self.parse_expression())
          if self.peek().kind == ord(','): self.eat(ord(','))
          else: break
        self.eat(ord(')'))
        result = Call(result, arguments)
        continue
      break
    return result

  def parse_term(self, wrapped: bool = False) -> Code:
    lhs = self.parse_factor(wrapped)
    while self.peek().kind in [ord('*'), ord('/'), ord('%')]:
      op = self.eat(self.peek().kind)
      rhs = self.parse_factor()
      lhs = BinaryOperator(lhs, op, rhs, wrapped)
    return lhs

  def parse_conjugate(self, wrapped: bool = False) -> Code:
    lhs = self.parse_term(wrapped)
    while self.peek().kind in [ord('+'), ord('-')]:
      op = self.eat(self.peek().kind)
      rhs = self.parse_term()
      lhs = BinaryOperator(lhs, op, rhs, wrapped)
    return lhs

  def parse_expression(self, wrapped: bool = False) -> Code:
    lhs = self.parse_conjugate(wrapped)
    while self.peek().kind in [TokenKind.EQEQ, TokenKind.BANGEQ]:
      op = self.eat(self.peek().kind)
      rhs = self.parse_conjugate()
      lhs = BinaryOperator(lhs, op, rhs, wrapped)
    return lhs

  def parse_declaration(self) -> Declaration:
    lhs = self.eat(TokenKind.IDENTIFIER)
    type_expr: Code | None = None
    if self.peek().kind == ord(':'):
      self.eat(ord(':'))
      type_expr = self.parse_expression()
    rhs: Code | None = None
    if self.peek().kind == ord('='):
      self.eat(ord('='))
      rhs = self.parse_expression()
    if type_expr is None and rhs is None: raise ParseError("invalid declaration", lhs)
    return Declaration(lhs, type_expr, rhs)

  def parse_procedure(self) -> Procedure:
    identifier = self.eat(TokenKind.IDENTIFIER)
    self.eat(ord('='))
    self.eat(ord('('))
    parameters: list[Declaration] = []
    while self.peek().kind != ord(')'):
      parameters.append(self.parse_declaration())
    self.eat(ord(')'))
    return_type: Code | None = None
    if self.peek().kind not in [ord('#'), ord('{')]:
      return_type = self.parse_expression()
    attributes: list[Declaration] = []
    if self.peek().kind == ord('#'):
      self.eat(ord('#'))
      while self.peek().kind != ord(')'):
        attributes.append(self.parse_declaration())
      self.eat(ord(')'))
    body = self.parse_block()
    return Procedure(identifier, parameters, return_type, attributes, body)

  def parse_statement_or_expression(self) -> Code:
    if self.peek(2).kind == ord('=') and self.peek(3).kind == ord('(') and (self.peek(4).kind == ord(')') or self.peek(5).kind in [ord(':'), ord('=')]): return self.parse_procedure()
    if self.peek(2).kind in [ord(':'), ord('=')]: return self.parse_declaration()
    if self.peek().kind == ord('{'): return self.parse_block()
    if self.peek().kind == TokenKind.KEYWORD_RETURN:
      self.eat(TokenKind.KEYWORD_RETURN)
      expression = self.parse_expression()
      return Return(expression)
    if self.peek().kind == TokenKind.KEYWORD_IF:
      self.eat(TokenKind.KEYWORD_IF)
      test = self.parse_expression()
      conseq = self.parse_statement_or_expression()
      alt: Code | None = None
      if self.peek().kind == TokenKind.KEYWORD_ELSE:
        self.eat(TokenKind.KEYWORD_ELSE)
        alt = self.parse_statement_or_expression()
      return If(test, conseq, alt)
    return self.parse_expression()

  def parse_block(self, implicit: bool = False) -> Block:
    if not implicit: self.eat(ord('{'))
    children = []
    while (not implicit and self.peek().kind != ord('}')) or (implicit and self.peek().kind != TokenKind.END_OF_INPUT):
      children.append(self.parse_statement_or_expression())
    if not implicit: self.eat(ord('}'))
    return Block(children, implicit)

def code_as_string(code: Code, s: str, level: int) -> str:
  if isinstance(code, Block):
    result = ""
    if not code.implicit: result += "{\n"
    result += "\n".join("  " * (level + 1 if not code.implicit else level) + code_as_string(child, s, level + 1 if not code.implicit else level) for child in code.children)
    if not code.implicit: result += f"\n{"  " * level}}}"
    return result
  if isinstance(code, Number):
    return f"{'(' if code.wrapped else ""}{code.value}{')' if code.wrapped else ""}"
  if isinstance(code, Variable):
    return f"{'(' if code.wrapped else ""}{code.identifier.as_str(s)}{')' if code.wrapped else ""}"
  if isinstance(code, Declaration):
    result = f"{code.lhs.as_str(s)}"
    if code.type_expr is not None: result += f": {code_as_string(code.type_expr, s, level)}"
    if code.rhs is not None: result += f" = {code_as_string(code.rhs, s, level)}"
    return result
  if isinstance(code, Reassignment):
    return f"{code_as_string(code.lhs, s, level)} := {code_as_string(code.rhs, s, level)}"
  if isinstance(code, Accessor):
    return f"{code_as_string(code.lhs, s, level)}.{code.rhs.as_str(s)}"
  if isinstance(code, Call):
    return f"{code_as_string(code.lhs, s, level)}!({", ".join(code_as_string(argument, s, level) for argument in code.arguments)})"
  if isinstance(code, BinaryOperator):
    return f"{'(' if code.wrapped else ""}{code_as_string(code.lhs, s, level)} {code.op.as_str(s)} {code_as_string(code.rhs, s, level)}{')' if code.wrapped else ""}"
  if isinstance(code, PostfixOperator):
    return f"{code_as_string(code.lhs, s, level)}.{code.op.as_str(s)}"
  if isinstance(code, Procedure):
    result = f"{code.identifier.as_str(s)} = "
    result += f"({", ".join(code_as_string(parameter, s, level) for parameter in code.parameters)})"
    if code.return_type is not None: result += f" {code_as_string(code.return_type, s, level)}"
    if len(code.attributes) != 0: result += f" #({", ".join(code_as_string(attribute, s, level) for attribute in code.attributes)})"
    result += "\n"
    result += code_as_string(code.body, s, level)
    return result
  if isinstance(code, Return):
    return f"return {code_as_string(code.expression, s, level)}"
  if isinstance(code, If):
    result = "if "
    result += code_as_string(code.test, s, level) + "\n"
    if not isinstance(code.conseq, Block): result += "  " * (level + 1)
    result += code_as_string(code.conseq, s, level)
    if code.alt is not None:
      result += "\n" + "  " * level + "else" + "\n"
      if not isinstance(code.alt, Block): result += "  " * (level + 1)
      result += code_as_string(code.alt, s, level)
    return result
  if isinstance(code, VoidExpr):
    return "{}"
  if isinstance(code, EnumLiteral):
    return f"enum.{code.identifier.as_str(s)}"
  raise NotImplementedError(code.__class__.__name__)

def dostring(s: str, echo_parse_tree: bool = False) -> None:
  try:
    parser = Parser(s)
    block = parser.parse_block(implicit=True)
    if echo_parse_tree: print(code_as_string(block, parser.s, 0))
  except ParseError as e: print(f"parse error @ {path.name}[{e.token.location}] near '{e.token.as_str(src)}': {e.message}")

def dofile(path: Path, echo_parse_tree: bool = False) -> None:
  dostring(path.read_text(), echo_parse_tree=echo_parse_tree)

if __name__ == "__main__":
  DEBUG = 0
  if DEBUG >= 1:
    path = Path("./aperion_tests")
    for i, file in enumerate(path.iterdir()):
      print(f"running test {i}: {file.name}... ", end="")
      dofile(file, echo_parse_tree=DEBUG >= 2)
      print(f"success")

  if len(sys.argv) > 1:
    path = Path(sys.argv[1])
    dofile(path, echo_parse_tree=True)
