; registers

element gpr
element x0 : gpr + 0
element x1 : gpr + 1
element x2 : gpr + 2
element x3 : gpr + 3
element x4 : gpr + 4
element x5 : gpr + 5
element x6 : gpr + 6
element x7 : gpr + 7
element x8 : gpr + 8
element x9 : gpr + 9
element x10 : gpr + 10
element x11 : gpr + 11
element x12 : gpr + 12
element x13 : gpr + 13
element x14 : gpr + 14
element x15 : gpr + 15
element x16 : gpr + 16
element x17 : gpr + 17
element x18 : gpr + 18
element x19 : gpr + 19

element zero : x0 metadata 1
element ra : x1 metadata 1
element t0 : x5 metadata 1
element t1 : x6 metadata 1
element s0 : x8 metadata 1
element s1 : x9 metadata 1
element a0 : x10 metadata 1
element s2 : x18 metadata 1

element csr
element mhartid : csr + 111100010100b

; encodings

macro I opcode*, funct3*, rd*, rs1*, imm12*
  assert rd metadata 1 relativeto gpr
  assert rs1 metadata 1 relativeto gpr

  local imm
  if imm12 metadata 1 relativeto csr
    imm = imm12 metadata 1 - csr
  else
    imm = imm12 and 0FFFh
  end if

  dd imm shl 20 or ((rs1 metadata 1 - gpr) and 1Fh) shl 15 or (funct3 and 7h) shl 12 or ((rd metadata 1 - gpr) and 1Fh) shl 7 or (opcode and 7Fh) shl 0
end macro

macro J opcode*, rd*, imm20*
  assert rd metadata 1 relativeto gpr

  local imm
  imm = imm20 - $

  dd (imm and 100000h) shl 11 or (imm and 7FEh) shl 20 or (imm and 800h) shl 9 or (imm and 0FF000h) shl 0 or ((rd metadata 1 - gpr) and 1Fh) shl 7 or (opcode and 7Fh) shl 0
end macro

macro B opcode*, funct3*, rs1*, rs2*, imm12*
  assert rs1 metadata 1 relativeto gpr
  assert rs2 metadata 1 relativeto gpr

  local imm
  imm = imm12 - $

  dd (imm and 1000h) shl 19 or (imm and 7E0h) shl 20 or ((rs2 metadata 1 - gpr) and 1Fh) shl 20 or ((rs1 metadata 1 - gpr) and 1Fh) shl 15 or (funct3 and 7h) shl 12 or (imm and 1Eh) shl 7 or (imm and 800h) shr 4 or (opcode and 7Fh) shl 0
end macro

macro U opcode*, rd*, imm20*
  assert rd metadata 1 relativeto gpr

  dd (imm20 and 0FFFFFh) shl 12 or ((rd metadata 1 - gpr) and 1Fh) shl 7 or (opcode and 7Fh) shl 0
end macro

macro S opcode*, funct3*, rs1*, rs2*, imm12*
  assert rs1 metadata 1 relativeto gpr
  assert rs2 metadata 1 relativeto gpr

  dd (imm12 and 0FE0h) shl 20 or ((rs2 metadata 1 - gpr) and 1Fh) shl 20 or ((rs1 metadata 1 - gpr) and 1Fh) shl 15 or (funct3 and 7h) shl 12 or (imm12 and 1Fh) shl 7 or (opcode and 7Fh) shl 0
end macro

macro R opcode*, funct7*, funct3*, rd*, rs1*, rs2*
  assert rd metadata 1 relativeto gpr
  assert rs1 metadata 1 relativeto gpr
  assert rs2 metadata 1 relativeto gpr

  dd (funct7 and 7Fh) shl 25 or ((rs2 metadata 1 - gpr) and 1Fh) shl 20 or ((rs1 metadata 1 - gpr) and 1Fh) shl 15 or (funct3 and 7h) shl 12 or ((rd metadata 1 - gpr) and 1Fh) shl 7 or (opcode and 7Fh) shl 0
end macro

; instructions

macro csrrs rd*, rcsr*, rs1*
  I 1110011b, 010b, rd, rs1, rcsr
end macro

macro wfi
  I 1110011b, 000b, x0, x0, 000100000101b
end macro

macro jal rd*, imm20*
  J 1101111b, rd, imm20
end macro

macro jalr rd*, rs1*, imm12*
  I 1100111b, 000b, rd, rs1, imm12
end macro

macro beq rs1*, rs2*, imm12*
  B 1100011b, 000b, rs1, rs2, imm12
end macro

macro bne rs1*, rs2*, imm12*
  B 1100011b, 001b, rs1, rs2, imm12
end macro

macro auipc rd*, imm20*
  U 0010111b, rd, imm20
end macro

macro lui rd*, imm20*
  U 0110111b, rd, imm20
end macro

macro add rd*, rs1*, rs2*
  R 0110011b, 0000000b, 000b, rd, rs1, rs2
end macro

macro addi rd*, rs1*, imm12*
  I 0010011b, 000b, rd, rs1, imm12
end macro

macro andi rd*, rs1*, imm12*
  I 0010011b, 111b, rd, rs1, imm12
end macro

macro sb rs2*, rs1*, imm12*
  S 0100011b, 000b, rs1, rs2, imm12
end macro

macro lb rd*, rs1*, imm12*
  I 0000011b, 000b, rd, rs1, imm12
end macro

; pseudo-instructions

macro csrr rd*, rcsr*
  csrrs rd, rcsr, x0
end macro

macro call addr*
  jal ra, addr
end macro

macro ret
  jalr x0, ra, 0
end macro

macro j addr*
  jal x0, addr
end macro

macro beqz rs1*, imm12*
  beq rs1, x0, imm12
end macro

macro bnez rs1*, imm12*
  bne rs1, x0, imm12
end macro

macro li rd*, imm*
  assert imm <= 0FFFFFFFFh

  if (imm shr 12) and 0FFFFFh
    lui rd, (imm shr 12) and 0FFFFFh
    if imm and 0FFFh
      addi rd, rd, imm and 0FFFh
    end if
  else
    addi rd, x0, imm and 0FFFh
  end if
end macro

macro la rd*, imm*
  local imm2
  imm2 = imm - $
  assert imm2 <= 0FFFFFFFFh

  auipc rd, (imm2 shr 12) and 0FFFFFh
  if imm2 and 0FFFh
    addi rd, rd, imm2 and 0FFFh
  end if
end macro

macro mv rd*, rs1*
  addi rd, rs1, 0
end macro
