#!/usr/bin/env sh
set -e

riscv64-linux-gnu-objdump -m riscv:rv64 -b binary -D .build/boot.bin
