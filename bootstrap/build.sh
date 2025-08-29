#!/usr/bin/env sh
set -e

mkdir -p .build
../fasm2/fasmg.x64 boot.asm .build/boot.bin
