#!/usr/bin/env python3

import binascii, subprocess, sys
from pathlib import Path

class BinaryWriter:
  def __init__(self) -> None:
    self.output = bytearray()
  def emit(self, n: int, *values: int) -> None:
    self.output += b"".join(value.to_bytes(n, byteorder="little") for value in values)

build_path = Path(".build")
tio_path = Path("../tio")
qemu_path = Path("qemu-system-riscv64")

if __name__ == "__main__":
  build_path.mkdir(exist_ok=True)
  with open(build_path / "aperix.bin", "wb") as f: f.write(b"\x6f\x00\x00\x00")

  payload = (build_path / "aperix.bin").read_bytes().ljust(33, b"\x00") # payload >32 bytes minimum
  w = BinaryWriter()
  w.emit(4, 64+256+256) # offset of spl header?
  w.emit(4, 0x200000)   # backup SBL offset?
  for _ in range(636): w.emit(1, 0)
  w.emit(4, 0x01010101) # version
  w.emit(4, len(payload))
  w.emit(4, 0x400)      # size of this header (equivalent to offset of payload)
  w.emit(4, binascii.crc32(payload))
  for _ in range(364): w.emit(1, 0)
  w.output += payload
  with open(build_path / "aperix.spl", "wb") as f: f.write(w.output)

  if len(sys.argv) > 1:
    match sys.argv[1]:
      case "tio": subprocess.run([tio_path, "/dev/ttyACM0"], check=True)
      case "qemu": subprocess.run([qemu_path, "-nographic", "-M", "virt", "-smp", "4", "-m", "256", "-bios", "none", "-kernel", build_path / "aperix.bin"], check=True)
      case _: print("usage: ./build.py [qemu]")
