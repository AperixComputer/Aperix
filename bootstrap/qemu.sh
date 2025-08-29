#!/usr/bin/env sh
set -e

qemu-system-riscv64 -nographic -M virt -smp 4 -m 256 -bios none -kernel .build/boot.bin
