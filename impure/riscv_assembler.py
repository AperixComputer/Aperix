class BinaryWriter:
  def __init__(self) -> None:
    self.output = bytearray()
  def emit(self, size: int, *values: int) -> None:
    self.output += b"".join([x.to_bytes(size, byteorder="little") for x in values])

# registers
x0=0; x1=1; x2=2; x3=3; x4=4; x5=5; x6=6; x7=7; x8=8; x9=9; x10=10; x11=11; x12=12; x13=13; x14=14; x15=15
x16=16; x17=17; x18=18; x19=19; x20=20; x21=21; x22=22; x23=23; x24=24; x25=25; x26=26; x27=27; x28=28; x29=29; x30=30; x31=31
zero=x0; ra=x1; sp=x2; gp=x3; tp=x4; t0=x5; t1=x6; t2=x7; s0=x8; s1=x9; a0=x10; a1=x11; a2=x12; a3=x13; a4=x14; a5=x15
a6=x16; a7=x17; s2=x18; s3=x19; s4=x20; s5=x21; s6=x22; s7=x23; s8=x24; s9=x25; s10=x26; s11=x27; t3=x28; t4=x29; t5=x30; t6=x31

# encodings
def R(opcode: int, funct7: int, funct3: int, rd: int, rs1: int, rs2: int) -> int:
  return (funct7 & 0x7F) << 25 | (rs2 & 0x1F) << 20 | (rs1 & 0x1F) << 15 | (funct3 & 0x7) << 12 | (rd & 0x1F) << 7 | (opcode & 0x7F) << 0
def I(opcode: int, funct3: int, rd: int, rs1: int, imm12: int) -> int:
  return (imm12 & 0xFFF) << 20 | (rs1 & 0x1F) << 15 | (funct3 & 0x7) << 12 | (rd & 0x1F) << 7 | (opcode & 0x7F) << 0
def U(opcode: int, rd: int, imm20: int) -> int:
  return (imm20 & 0xFFFFF) << 12 | (rd & 0x1F) << 7 | (opcode & 0x7F) << 0
def J(opcode: int, rd: int, imm20: int) -> int:
  return (imm20 & 0x80000) << 12 | (imm20 & 0x7FE) << 20 | (imm20 & 0x800) << 9 | (imm20 & 0xFF000) << 0 | (rd & 0x1F) << 7 | (opcode & 0x7F) << 0
def B(opcode: int, funct3: int, rs1: int, rs2: int, imm12: int) -> int:
  return (imm12 & 0x800) << 20 | (imm12 & 0x7E0) << 20 | (rs2 & 0x1F) << 20 | (rs1 & 0x1F) << 15 | (funct3 & 0x7) << 12 | (imm12 & 0x1E) << 7 | (imm12 & 0x800) >> 4 | (opcode & 0x7F) << 0
def S(opcode: int, funct3: int, rs1: int, rs2: int, imm12: int) -> int:
  return (imm12 & 0xFE) << 24 | (rs2 & 0x1F) << 20 | (rs1 & 0x1F) << 15 | (funct3 & 0x7) << 12 | (imm12 & 0x1F) << 7 | (opcode & 0x7F) << 0

class RISCVWriter(BinaryWriter):
  def db(self, *values: int) -> None: self.emit(1, *values)
  def dh(self, *values: int) -> None: self.emit(2, *values)
  def dw(self, *values: int) -> None: self.emit(4, *values)
  def dd(self, *values: int) -> None: self.emit(8, *values)

  def add(self, rd: int, rs1: int, rs2: int) -> None: self.dw(R(0b0110011, 0b0000000, 0b000, rd, rs1, rs2))
  def addi(self, rd: int, rs1: int, imm12: int) -> None: self.dw(I(0b0010011, 0b000, rd, rs1, imm12))
  def auipc(self, rd: int, imm20: int) -> None: self.dw(U(0b0010111, rd, imm20))
  def jal(self, rd: int, imm20: int) -> None: self.dw(J(0b1101111, rd, imm20))
  def beq(self, rs1: int, rs2: int, imm12: int) -> None: self.dw(B(0b1100011, 0b000, rs1, rs2, imm12))
  def sb(self, rs1: int, rs2: int, imm12: int) -> None: self.dw(S(0b0100011, 0b000, rs1, rs2, imm12))

asm = RISCVWriter()
asm.add(x1, x2, x3)
asm.addi(x1, x2, 512)
asm.auipc(x5, 0x12345)
asm.jal(x10, 0x12344)
asm.beq(x1, x2, 0x556)
asm.sb(x2, x3, -0x555)

for n in range(0, len(asm.output), 4):
  print(f"0x{int.from_bytes(asm.output[n:n+4], byteorder="little"):08X}")
