from dataclasses import dataclass
from enum import IntEnum

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
