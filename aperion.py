#!/usr/bin/env python3

import sys
from pathlib import Path
from parser import ParseError, Parser
from printer import code_as_string
from evaluator import evaluate_code, Scope

if __name__ == "__main__":
	if len(sys.argv) < 2:
		print(f"usage: {sys.argv[0] if len(sys.argv) > 0 else "./aperion.py"} file.aperion")
		sys.exit(1)

	path = Path(sys.argv[1])
	src = path.read_text()
	parser = Parser(src)
	file_scope = Scope(None)
	try:
		module = parser.parse_block(implicit=True)
		print(code_as_string(module, parser.s, 0))
		evaluate_code(module, parser.s, file_scope, True)
	except ParseError as e: print(f"parse error @ {path.name}[{e.token.location}] near '{e.token.as_str(parser.s)}': {e.message}")
