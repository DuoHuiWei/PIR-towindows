
import sys
from pathlib import Path


lib_path = Path("src/libs.rs")
util_path = Path("utils/helper.cpp")


def replace_prefixed_line(lines, prefix, replacement):
    replaced = 0

    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = replacement
            replaced += 1

    if replaced != 1:
        raise RuntimeError(f"expected exactly one line starting with {prefix!r}, found {replaced}")


def front_mask(psize):
    raw = bin(pow(2, psize // 2) - 1)
    if psize // 2 > 8:
        return raw[:-8]
    return raw


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: python config.py <bsize> <psize>")

    bsize = int(sys.argv[1])
    psize = int(sys.argv[2])

    libs_lines = lib_path.read_text(encoding="utf-8").splitlines(keepends=True)
    helper_lines = util_path.read_text(encoding="utf-8").splitlines(keepends=True)

    replace_prefixed_line(libs_lines, "pub const BUNIT: usize =", f"pub const BUNIT: usize = {bsize}; // one block has __ chunks\n")
    replace_prefixed_line(libs_lines, "pub const NSIZE: usize =", f"pub const NSIZE: usize = {pow(2, psize)}; // dbase size\n")
    replace_prefixed_line(libs_lines, "pub const LSIZE: usize =", f"pub const LSIZE: usize = {psize // 2}; // logarithm sqrt\n")
    replace_prefixed_line(libs_lines, "pub const HSIZE: usize =", f"pub const HSIZE: usize = SSIZE * {psize}; // hint size\n")
    replace_prefixed_line(libs_lines, "pub const FRONT: u8 =", f"pub const FRONT: u8 = {front_mask(psize)};\n")

    if psize // 2 > 8:
        replace_prefixed_line(libs_lines, "pub const ISIZE: usize =", "pub const ISIZE: usize = 0004; // one indice has __ bytes\n")
        replace_prefixed_line(libs_lines, "pub const ISQRT: usize =", "pub const ISQRT: usize = 0002; // one offset has __ bytes\n")
        replace_prefixed_line(libs_lines, "pub type SQRT =", "pub type SQRT = u16;\n")
        replace_prefixed_line(libs_lines, "pub type INDX =", "pub type INDX = u32;\n")
    else:
        replace_prefixed_line(libs_lines, "pub const ISIZE: usize =", "pub const ISIZE: usize = 0002; // one indice has __ bytes\n")
        replace_prefixed_line(libs_lines, "pub const ISQRT: usize =", "pub const ISQRT: usize = 0001; // one offset has __ bytes\n")
        replace_prefixed_line(libs_lines, "pub type SQRT =", "pub type SQRT = u8;\n")
        replace_prefixed_line(libs_lines, "pub type INDX =", "pub type INDX = u16;\n")

    replace_prefixed_line(helper_lines, "const size_t N_CHUNK =", f"const size_t N_CHUNK = {bsize * 16}; // script auto change this\n")

    lib_path.write_text("".join(libs_lines), encoding="utf-8")
    util_path.write_text("".join(helper_lines), encoding="utf-8")

    print(f"updated config: BUNIT={bsize}, NSIZE=2^{psize}, helper N_CHUNK={bsize * 16}")


if __name__ == "__main__":
    main()
