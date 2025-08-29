import binascii, os, sys, time
from pathlib import Path
import serial

class BinaryWriter:
  def __init__(self) -> None:
    self.output = bytearray()
  def emit(self, n: int, *values: int) -> None:
    for value in values:
        self.output += value.to_bytes(n, byteorder="little")
  def db(self, *values: int) -> None: self.emit(1, *values)
  def dh(self, *values: int) -> None: self.emit(2, *values)
  def dw(self, *values: int) -> None: self.emit(4, *values)
  def dd(self, *values: int) -> None: self.emit(8, *values)

w = BinaryWriter()
payload = Path(".build/boot.bin").read_bytes().ljust(32, b"\x00") # >32 byte minimum payload
w.dw(64+256+256) # offset of SPL header?
w.dw(0x200000) # backup SBL offset?
for _ in range(636): w.db(0)
w.dw(0x01010101) # SPL version
w.dw(len(payload))
w.dw(0x400) # size of SPL header (equivalent to offset of payload)
w.dw(binascii.crc32(payload))
for _ in range(364): w.db(0)
w.output += payload
with open(".build/boot.spl", "wb") as f: f.write(w.output)

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
  send_xmodem1k(ser, Path(".build/boot.spl"), retry=16, block_timeout=8.0)
  ser.timeout = 0.1
  while True:
    data = ser.read(1024)
    if data:
      sys.stdout.write(data.decode("utf-8", errors="replace"))
      sys.stdout.flush()

if __name__ == "__main__":
  if len(sys.argv) > 1 and sys.argv[1] == "boot": serial_send_and_connect()
