#include "stdio.h"
#include "stdlib.h"
#include "stdint.h"

enum RVRegister {
	RV_REG_X0, RV_REG_X1, RV_REG_X2, RV_REG_X3, RV_REG_X4, RV_REG_X5, RV_REG_X6, RV_REG_X7,
	RV_REG_X8, RV_REG_X9, RV_REG_X10, RV_REG_X11, RV_REG_X12, RV_REG_X13, RV_REG_X14, RV_REG_X15,
	RV_REG_X16, RV_REG_X17, RV_REG_X18, RV_REG_X19, RV_REG_X20, RV_REG_X21, RV_REG_X22, RV_REG_X23,
	RV_REG_X24, RV_REG_X25, RV_REG_X26, RV_REG_X27, RV_REG_X28, RV_REG_X29, RV_REG_X30, RV_REG_X31,
	RV_REG_ZERO = RV_REG_X0,
	RV_REG_RA = RV_REG_X1,
};

uint32_t rv_encode_R(uint32_t opcode, uint32_t funct7, uint32_t funct3, uint32_t rd, uint32_t rs1, uint32_t rs2) {
	return
		((funct7 & 0x7F) << 25) |
		((rs2 & 0x1F) << 20) |
		((rs1 & 0x1F) << 15) |
		((funct3 & 0x7) << 12) |
		((rd & 0x1F) << 7) |
		((opcode & 0x7F) << 0);
}

uint32_t rv_encode_I(uint32_t opcode, uint32_t funct3, uint32_t rd, uint32_t rs1, uint32_t imm12) {
	return
		((imm12 & 0xFFF) << 20) |
		((rs1 & 0x1F) << 15) |
		((funct3 & 0x7) << 12) |
		((rd & 0x1F) << 7) |
		((opcode & 0x7F) << 0);
}

#define rv_add(rd, rs1, rs2) rv_encode_R(0x33, 0x00, 0x0, (rd), (rs1), (rs2))
#define rv_addi(rd, rs1, imm12) rv_encode_I(0x13, 0x0, (rd), (rs1), (imm12))

#if !defined(APERIX_NO_MAIN)
int main(void) {
	printf("add x1, x2, x3:   0x%08X [R-type]\n", rv_add(RV_REG_X1, RV_REG_X2, RV_REG_X3));
	printf("addi x1, x2, 512: 0x%08X [I-type]\n", rv_addi(RV_REG_X1, RV_REG_X2, 512));
	return EXIT_SUCCESS;
}
#endif /* !defined(APERIX_NO_MAIN) */
