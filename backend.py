#!/usr/bin/env python3

import CppHeaderParser
import json
import gzip
import argparse
import sys
from typing import List,Dict,Union
import pprint
import re
from pathlib import Path
def direct_assign(container,content,newvalue):
    container[container.index(content)]=newvalue

u8=8//8
u16=16//8
u32=32//8
u64=64//8

class BytecodeGenerator:
    instruction_enum:Dict[str,int]=dict()
    data_segment:List[int]=list()
    steps:List=list()
    variables=list()
    labels=list()
    global_labels:[List[str]]=list()
    def __init__(self):
        core_def=CppHeaderParser.CppHeader(Path(__file__).parent/"nyulan_vm/nyulan.hpp").enums
        for core_enum in core_def:
            if core_enum["name"] == "Instruction":
                for enum in core_enum["values"]:
                    self.instruction_enum[enum["name"]]=enum["value"]
    def from_middle(self,sources:List[Dict]):
        for source in sources:
            assert source["name"]=="NYULAN_MIDDLECODE","given data is not nyulan middlecode"
            data_segment_offset=len(self.data_segment)
            for i in range(len(source["variables"])):
                source["variables"][i]["address"]+=data_segment_offset
            self.variables+=source["variables"]
            self.data_segment+=source["data_segment"]

            step_offset=len(self.steps)
            for i in range(len(source["labels"])):
                source["labels"][i]["address"]+=step_offset
            self.labels+=source["labels"]
            self.global_labels+=source["global_labels"]
            self.steps+=source["steps"]
            self.__func_code()
    def __func_code(self):
        self.__expand_variables()
        self.__expand_labels()
        self.__expand_macros()
        self.__add_meta()
    def __expand_variables(self):
        regex=re.compile(r"\${(.+)}")
        for step in self.steps:
            for operand in filter(lambda o:isinstance(o,str),step["operands"]):
                match=regex.fullmatch(operand)
                if match:
                    var=list(filter(lambda v:v["name"]==match.group(1),self.variables))
                    assert len(var) == 1,"error: variable name collision"
                    direct_assign(step["operands"],operand,(var[0]["address"] | (0b1<<63)).to_bytes(8,"little"))
    def __expand_labels(self):
        pass
    def __expand_macros(self):
        regex_PUSHLs=re.compile(r"PUSHL.*")
        for step in filter(lambda o:isinstance(o["instruction"],str),self.steps):
            match=regex_PUSHLs.match(step["instruction"])
            if match and isinstance(step["operands"][0],int):
                step["operands"][0]=step["operands"][0].to_bytes(u64,"little") #上から取れば,16bitとかしか使わなくても0k
                pass
            plain_steps=list()
            if step["instruction"] == "PUSHL8":
                plain_step=dict()
                plain_step["instruction"]=self.instruction_enum["PUSHL"]
                plain_step["operands"]=step["operands"][0]
                plain_step["is_placeholder"]=False
                plain_steps.append(plain_step)
            elif step["instruction"] == "PUSHL16":
                for byte in step["operands"][0]:
                    plain_step=dict()
                    plain_step["instruction"]=self.instruction_enum["PUSHL"]
                    plain_step["operands"]=[byte]
                    plain_step["is_placeholder"]=False
                    plain_steps.append(plain_step)
            elif step["instruction"] == "PUSHL32":
                for byte in step["operands"][0]:
                    plain_step=dict()
                    plain_step["instruction"]=self.instruction_enum["PUSHL"]
                    plain_step["operands"]=[byte]
                    plain_step["is_placeholder"]=False
                    plain_steps.append(plain_step)
            elif step["instruction"] == "PUSHL64":
                for byte in step["operands"][0]:
                    plain_step=dict()
                    plain_step["instruction"]=self.instruction_enum["PUSHL"]
                    plain_step["operands"]=[byte]
                    plain_step["is_placeholder"]=False
                    plain_steps.append(plain_step)
            index=self.steps.index(step)
            del self.steps[index]
            self.steps=self.steps[:index]+plain_steps+self.steps[index:]
        self.steps=list(filter(lambda s:s["is_placeholder"]==False,self.steps))
    def __add_meta(self):
        for step in self.steps:
            instruction=keys_from_value(self.instruction_enum,step["instruction"])[0]
            if instruction == "PUSHL":
                operand=step["operands"][0]
                step["operands"]=[(operand&0b11110000)>>4,operand&0b00001111]
    def dump(self,filename):
        with open(filename,"wb") as outputfile:
            outputfile.write(b"NYU") #magic
            outputfile.write(0x1100.to_bytes(u16,sys.byteorder)) #bom
            outputfile.write(0x01.to_bytes(u64,sys.byteorder)) #ver
            outputfile.write(len(self.data_segment).to_bytes(u16,sys.byteorder)) #lit_size
            outputfile.write(bytes(self.data_segment)) #lit
            global_labels=list(filter(lambda l:l["name"] in self.global_labels,self.labels))
            outputfile.write(len(global_labels).to_bytes(u16,sys.byteorder)) #gl_num
            for label in global_labels: #gls
                outputfile.write(encode_Pointerlike(label))
            outputfile.write(len(self.steps).to_bytes(u64,sys.byteorder)) #code_len
            for step in self.steps: #code
                outputfile.write(encode_Step(step))

def encode_Pointerlike(ptr):
    result=bytes()
    result+=ptr["name"].encode()+b"\x00"
    result+=ptr["address"].to_bytes(u64,sys.byteorder)
    return result

def encode_Step(step):
    result=step["instruction"]<<8
    for i in range(len(step["operands"])):
        result|=step["operands"][i]<<(4*(1-i)) #0番目のオペランドは4bit,1番目のオペランドは0bitシフト
    return result.to_bytes(u16,sys.byteorder)

def keys_from_value(src_dict,value):
    result=list()
    for key in src_dict:
        if src_dict[key] == value:
            result.append(key)
    return result

def main():
    parser=argparse.ArgumentParser(description="backend of nyulan_asm :convert nyulan middlecodes into nyulan bytecode",prog="nyulan_linker.py")
    parser.add_argument("-s","--sources",nargs="+",help="source files")
    parser.add_argument("-o","--output",help="output filename (in result folder)")
    args=parser.parse_args()

    if args.sources == None :
        print("error: no sourcefile was given",file=sys.stderr)

    if args.output == None:
        args.output="a.no"

    sources=list()
    for source in args.sources:
        with gzip.open(source) as sourcefile:
            sources.append(json.load(sourcefile))
    generator=BytecodeGenerator()
    generator.from_middle(sources)
    generator.dump(args.output)

if __name__=="__main__":
    main()
