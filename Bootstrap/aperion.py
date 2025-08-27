from dataclasses import dataclass

class Identifier(str): pass
class Tuple(list): pass
class Number(int): pass
class String(str): pass
@dataclass
class Code:
  location: int
  data: Identifier | Tuple | Number | String

def parse(s: str, p: int) -> tuple[Code | None, int]:
  level = 0
  stack = []
  while True:
    while p < len(s) and s[p].isspace(): p += 1
    if p >= len(s): break
    start = p
    if s[p] == "(":
      p += 1
      level += 1
      stack.append(Code(start, Tuple()))
    elif s[p] == ")":
      p += 1
      assert level > 0
      level -= 1
      if len(stack) > 1:
        popped = stack.pop()
        stack[-1].data.append(popped)
    elif s[p].isdigit():
      while p < len(s) and s[p].isdigit(): p += 1
      (stack[-1].data if len(stack) > 0 else stack).append(Code(start, Number(s[start:p], base=0)))
    else:
      while p < len(s) and s[p] not in "() \t\n\r": p += 1
      (stack[-1].data if len(stack) > 0 else stack).append(Code(start, Identifier(s[start:p])))
    assert p >= len(s) or (p > 0 and s[p - 1] == "(") or s[p] in ") \t\n\r"
    if level == 0: break
  assert level == 0
  assert len(stack) <= 1
  return stack.pop() if len(stack) > 0 else None, p

class Label(str): pass
class RISCVWriter:
  def __init__(self) -> None:
    self.output = bytearray()
    self.origin = 0
    self.cursor = 0
    self.labels = {}
    self.fixups = []
    for i in range(32): setattr(self, f"x{i}", i)
  def eval(self, code: Code) -> None:
    if not isinstance(code.data, Tuple):
      if isinstance(code.data, Identifier): return getattr(self, code.data) if hasattr(self, code.data) else Label(code.data)
      else: return code.data
    op, *args = code.data
    if op.data == Identifier("label"):
      name, = args
      assert isinstance(name.data, Identifier)
      self.labels[name.data] = self.cursor
    else:
      proc = self.eval(op)
      pargs = [self.eval(arg) for arg in args]
      return proc(*pargs)
  def fixup(self) -> None:
    for fixup in self.fixups:
      self.output[fixup["at"]:fixup["at"]+fixup["n"]] = fixup["op"](*[(self.labels[arg] if fixup["mode"] != "relative" else self.labels[arg] - fixup["at"]) if isinstance(arg, Label) else arg for arg in fixup["args"]]).to_bytes(fixup["n"], byteorder="little")

  def J(self, opcode: int, rd: int, imm20: int) -> int: return (imm20 & 0x80000) << 12 | (imm20 & 0x7FE) << 20 | (imm20 & 0x800) << 9 | (imm20 & 0xFF000) << 0 | (rd & 0x1F) << 7 | (opcode & 0x7F) << 0
  def I(self, opcode: int, funct3: int, rd: int, rs1: int, imm12: int) -> int:
    return (imm12 & 0xFFF) << 20 | (rs1 & 0x1F) << 15 | (funct3 & 0x7) << 12 | (rd & 0x1F) << 7 | (opcode & 0x7F) << 0

  def emit(self, n: int, *values: int | dict) -> None:
    for value in values:
      if isinstance(value, int):
        self.output += value.to_bytes(n, byteorder="little")
        self.cursor += n
      else:
        value.update({"at": self.cursor, "n": n})
        self.fixups.append(value)
        self.output += b"\xAA" * n
        self.cursor += n
  def dw(self, *values: int | dict) -> None: self.emit(4, *values)

  def wfi(self) -> None: self.dw(self.I(0b1110011, 0b000, 0b00000, 0b00000, 0b000100000101))
  def jal(self, rd: int, imm20: int | Label) -> None: self.dw({"op": self.J, "args": (0b1101111, rd, imm20), "mode": "relative"})

def dostring(s: str, visitor) -> None:
  p = 0
  while True:
    code, next_pos = parse(s, p)
    if code is None: break
    p = next_pos
    visitor(code)

if __name__ == "__main__":
  import sys
  from pathlib import Path
  with open(sys.argv[1]) as f: src = f.read()
  w = RISCVWriter()
  dostring(src, w.eval)
  w.fixup()
  with open(Path(sys.argv[1]).with_suffix(".bin"), "wb") as f: f.write(w.output)
