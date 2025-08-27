import binascii

def add_spl_header(payload: bytes) -> bytes:
  payload = payload.ljust(33, b"\x00") # weird minimum payload >32 bytes
  output = bytearray()
  def db(*values: int) -> None: nonlocal output; output += b"".join(value.to_bytes(1, byteorder="little") for value in values)
  def dw(*values: int) -> None: nonlocal output; output += b"".join(value.to_bytes(4, byteorder="little") for value in values)
  dw(64+256+256) # offset of this header in memory?
  dw(0x200000) # backup SBL offset?
  for _ in range(636): db(0)
  dw(0x01010101) # version
  dw(len(payload))
  dw(0x400) # size of this header (equivalent to offset of payload)
  dw(binascii.crc32(payload))
  for _ in range(364): db(0)
  output += payload
  return bytes(output)

if __name__ == "__main__":
  import sys
  from pathlib import Path
  with open(sys.argv[1], "rb") as f: payload = f.read()
  output = add_spl_header(payload)
  with open(Path(sys.argv[1]).with_suffix(".spl"), "wb") as f: f.write(output)
