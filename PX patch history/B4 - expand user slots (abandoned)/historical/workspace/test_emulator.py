from unicorn import *
from unicorn.mips_const import *
from pathlib import Path
u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
u.mem_map(0x1d000000,0x90000);u.mem_write(0x1d000000,Path('pic.bin').read_bytes());u.mem_map(0,0x100000)
u.reg_write(UC_MIPS_REG_SP,0x800f0000);u.reg_write(UC_MIPS_REG_RA,0x9d081900)
u.reg_write(UC_MIPS_REG_A0,0);u.reg_write(UC_MIPS_REG_A1,0x22);u.reg_write(UC_MIPS_REG_A2,96)
u.emu_start(0x9d04d4fc,0x9d081900,count=1000)
print(u.reg_read(UC_MIPS_REG_V0))
