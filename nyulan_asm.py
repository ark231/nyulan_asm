#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path
def main():
    parser=argparse.ArgumentParser(description="assemble nyulan assembly",prog="nyulan_asm.py")
    parser.add_argument("-s","--sources",nargs="+",help="source files")
    parser.add_argument("-o","--output",help="output filename (in result folder)")
    parser.add_argument("--reserve_tmps",action="store_true",help="reserve temporary nlib files")
    args=parser.parse_args()
    if args.sources is None :
        print("error: no sourcefile was given",file=sys.stderr)
    middle_codepathes=list()
    for source in args.sources:
        subprocess.run([Path(__file__).parent/"frontend.py","-s",source])
        middle_codepathes.append(Path(source).with_suffix(".nlib"))
    output = ["-o",args.output] if not args.output is None  else []
    subprocess.run([Path(__file__).parent/"backend.py"]+output+["-s"]+middle_codepathes)
    if not args.reserve_tmps :
        for middle_codepath in middle_codepathes:
            middle_codepath.unlink()

if __name__=="__main__":
    main()
