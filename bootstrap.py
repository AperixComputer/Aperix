import binascii, os, sys, time
from pathlib import Path
import serial

class BinaryWriter:
  def __init__(self) -> None:
    self.output = bytearray()
    self.origin = 0
    self.cursor = 0
    self.labels = {}
    self.fixups = []
  def org(self, at: int) -> None: self.origin, self.cursor = at, at
  def label(self, s: str) -> None: self.labels[s] = self.cursor
  def fixup(self) -> None:
    for fixup in self.fixups:
      self.output[fixup["at"]:fixup["at"]+fixup["n"]] = fixup["op"](*[arg if isinstance(arg, int) else arg(fixup["at"]) if callable(arg) else self.labels[arg] - fixup["at"] for arg in fixup["args"]]).to_bytes(fixup["n"], byteorder="little")
  def emit(self, n: int, *values: int | dict) -> None:
    for value in values:
      if isinstance(value, int):
        self.output += value.to_bytes(n, byteorder="little")
        self.cursor += n
      elif isinstance(value, dict):
        value.update({"at": len(self.output), "n": n})
        self.fixups.append(value)
        self.output += b"\xAA" * n
        self.cursor += n
      elif isinstance(value, str):
        value = value.encode().decode("unicode_escape").encode()
        self.output += b"".join(b.to_bytes(n, byteorder="little") for b in value)
        self.cursor += n * len(value)
  def db(self, *values: int | dict | str) -> None: self.emit(1, *values)
  def dh(self, *values: int | dict | str) -> None: self.emit(2, *values)
  def dw(self, *values: int | dict | str) -> None: self.emit(4, *values)
  def dd(self, *values: int | dict | str) -> None: self.emit(8, *values)

class RISCVWriter(BinaryWriter):
  def __init__(self) -> None:
    super().__init__()
    for i in range(32): setattr(self, f"x{i}", i)
    self.zero = self.x0
    self.ra = self.x1
    self.t0 = self.x5
    self.t1 = self.x6
    self.t2 = self.x7
    self.t3 = self.x28
    self.mhartid = 0b111100010100
  def I(self, opcode: int, funct3: int, rd: int, rs1: int, imm12: int) -> int:
    return (imm12 & 0xFFF) << 20 | (rs1 & 0x1F) << 15 | (funct3 & 0x7) << 12 | (rd & 0x1F) << 7 | (opcode & 0x7F) << 0
  def S(self, opcode: int, funct3: int, rs1: int, rs2: int, imm12: int) -> int:
    return (imm12 & 0xFE0) << 19 | (rs2 & 0x1F) << 20 | (rs1 & 0x1F) << 15 | (funct3 & 0x7) << 12 | (imm12 & 0x1F) << 7 | (opcode & 0x7F) << 0
  def J(self, opcode: int, rd: int, imm20: int) -> int:
    return (imm20 & 0x80000) << 12 | (imm20 & 0x7FE) << 20 | (imm20 & 0x800) << 9 | (imm20 & 0xFF000) << 0 | (rd & 0x1F) << 7 | (opcode & 0x7F) << 0
  def U(self, opcode: int, rd: int, imm20: int) -> int:
    return (imm20 & 0xFFFFF) << 12 | (rd & 0x1F) << 7 | (opcode & 0x7F) << 0
  def B(self, opcode: int, funct3: int, rs1: int, rs2: int, imm12: int) -> int:
    return (imm12 & 0x800) << 20 | (imm12 & 0x7E0) << 20 | (rs2 & 0x1F) << 20 | (rs1 & 0x1F) << 15 | (funct3 & 0x7) << 12 | (imm12 & 0x1E) << 7 | (imm12 & 0x800) >> 4 | (opcode & 0x7F) << 0
  def hi20(self, addr: int): return (addr + 0x800) >> 12
  def lo12(self, addr: int): return addr - (self.hi20(addr) << 12)
  def wfi(self) -> None: self.dw(self.I(0b1110011, 0b000, 0b00000, 0b00000, 0b000100000101))
  def addi(self, rd: int, rs1: int, imm12: int) -> None: self.dw({"op": self.I, "args": (0b0010011, 0b000, rd, rs1, imm12)})
  def andi(self, rd: int, rs1: int, imm12: int) -> None: self.dw(self.I(0b0010011, 0b111, rd, rs1, imm12))
  def jal(self, rd: int, imm20: int) -> None: self.dw({"op": self.J, "args": (0b1101111, rd, imm20)})
  def jalr(self, rd: int, rs1: int, imm12: int) -> None: self.dw({"op": self.I, "args": (0b1100111, 0b000, rd, rs1, imm12)})
  def lui(self, rd: int, imm20: int) -> None: self.dw({"op": self.U, "args": (0b0110111, rd, imm20)})
  def sb(self, rs2: int, rs1: int, imm12: int) -> None: self.dw({"op": self.S, "args": (0b0100011, 0b000, rs1, rs2, imm12)})
  def lb(self, rd: int, rs1: int, imm12: int) -> None: self.dw({"op": self.I, "args": (0b0000011, 0b000, rd, rs1, imm12)})
  def csrrs(self, rd: int, csr: int, rs1: int) -> None: self.dw({"op": self.I, "args": (0b1110011, 0b010, rd, rs1, csr)})
  def beq(self, rs1: int, rs2: int, imm12: int) -> None: self.dw({"op": self.B, "args": (0b1100011, 0b000, rs1, rs2, imm12)})
  def bne(self, rs1: int, rs2: int, imm12: int) -> None: self.dw({"op": self.B, "args": (0b1100011, 0b001, rs1, rs2, imm12)})

w = RISCVWriter()

UART_BASE = 0x10000000
UART_REG_SHIFT = 2
UART_THR = 0
UART_LSR = 5
UART_LSR_THRE = 1 << 5

w.org(0x08000000)

w.csrrs(w.t0, w.mhartid, w.x0)
w.bne(w.t0, w.x0, "halt")

w.lui(w.t2, lambda _: w.hi20(w.labels["hw"]))
w.addi(w.t2, w.t2, lambda _: w.lo12(w.labels["hw"]))
w.jal(w.ra, "uart_puts")

w.jal(w.x0, "halt")

w.label("uart_puts")

w.lui(w.t0, UART_BASE >> 12)

w.label("uart_puts.loop")
w.lb(w.t1, w.t2, 0)
w.beq(w.t1, w.x0, "uart_puts.end")

w.label("wait_for_uart_ready")
w.lb(w.t3, w.t0, UART_LSR << UART_REG_SHIFT)
w.andi(w.t3, w.t3, UART_LSR_THRE)
w.beq(w.t3, w.x0, "wait_for_uart_ready")

w.sb(w.t1, w.t0, UART_THR << UART_REG_SHIFT)

w.addi(w.t2, w.t2, 1)
w.jal(w.x0, "uart_puts.loop")

w.label("uart_puts.end")
w.jalr(w.x0, w.ra, 0)

w.label("halt")
w.wfi()
w.jal(w.x0, "halt")

w.label("hw")
w.db("Hello, world!\n\r\0")

w.fixup()
with open("boot.bin", "wb") as f: f.write(w.output)

w2 = BinaryWriter()
payload = w.output.ljust(32, b"\x00") # >32 byte minimum payload
w2.dw(64+256+256) # offset of SPL header?
w2.dw(0x200000) # backup SBL offset?
for _ in range(636): w2.db(0)
w2.dw(0x01010101) # SPL version
w2.dw(len(payload))
w2.dw(0x400) # size of SPL header (equivalent to offset of payload)
w2.dw(binascii.crc32(payload))
for _ in range(364): w2.db(0)
w2.output += payload
with open("boot.spl", "wb") as f: f.write(w2.output)

def serial_send_and_connect():
  STX = 0x02
  EOT = 0x04
  ACK = 0x06
  NAK = 0x15
  CAN = 0x18

  def crc16_xmodem(data: bytes) -> int:
    crc = 0x0000
    for b in data:
      crc ^= (b << 8) & 0xFFFF
      for _ in range(8):
        if crc & 0x8000: crc = ((crc << 1) ^ 0x1021) & 0xFFFF
        else: crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF

  def send_xmodem1k(ser: serial.Serial, path: Path, retry: int, block_timeout: float) -> bool:
    total = path.stat().st_size
    blknum = 1

    with open(path, "rb") as f:
      while True:
        chunk = f.read(1024)
        if chunk is None or len(chunk) == 0: break
        chunk = chunk.ljust(1024, b"\x1A")

        pkt = bytearray()
        pkt.append(STX)
        pkt.append(blknum)
        pkt.append(0xFF - blknum)
        pkt += chunk
        crc = crc16_xmodem(chunk)
        pkt.append((crc >> 8) & 0xFF)
        pkt.append(crc & 0xFF)

        ok = False
        for attempt in range(retry):
          ser.write(pkt)
          ser.flush()

          ser.timeout = block_timeout
          resp = ser.read(1)
          if resp and resp[0] == ACK: ok = True; break
          elif resp and resp[0] == NAK: continue
          elif resp and resp[0] == CAN: _ = ser.read(1); return False
        if not ok: return False

        blknum = (blknum + 1) & 0xFF
        if blknum == 0: blknum = 1

    for _ in range(retry):
      ser.write(bytes([EOT]))
      ser.flush()
      ser.timeout = block_timeout
      resp = ser.read(1)
      if resp and resp[0] == ACK: return True
      elif resp and resp[0] == CAN: return False
    return False

  ser = serial.Serial(
    port="/dev/ttyACM0",
    baudrate=115200,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=8.0,
    write_timeout=8.0,
    xonxoff=False,
    rtscts=False,
    dsrdtr=False,
  )
  send_xmodem1k(ser, Path("boot.spl"), retry=16, block_timeout=8.0)
  ser.timeout = 0.1
  while True:
    data = ser.read(1024)
    if data:
      sys.stdout.write(data.decode("utf-8", errors="replace"))
      sys.stdout.flush()

if __name__ == "__main__":
  if len(sys.argv) > 1 and sys.argv[1] == "boot": serial_send_and_connect()
