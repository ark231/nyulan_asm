#!/usr/bin/env python3
import CppHeaderParser
import argparse
import lark
from typing import List,Dict,Union

class Register(int):
    def __new__(cls,value:str):
        return int.__new__(cls,value[1:])

class OneStep:
    def __init__(self,instruction,operands,is_placeholder=False):
        self.instruction=instruction
        self.operands=operands
        self.is_placeholder=is_placeholder

    def __str__(self):
        if self.is_placeholder:
            return "placeholder"
        else:
            return f"{self.instruction}:{self.operands}"

MACROS_LENGTH={
        "PUSHL8":1,
        "PUSHL16":2,
        "PUSHL32":4,
        "PUSHL64":8
        }

class Label:
    def __init__(self,name:str,address:int):
        self.name=name
        self.address=address

class Flattener(lark.Transformer):
    instruction_enum:Dict[str,int]
    global_labels:Dict[str,Label]
    external_labels:Dict[str,Label]
    num_steps:int

    def __init__(self)->None:
        self.instruction_enum=dict()
        core_def=CppHeaderParser.CppHeader("nyulan_vm/nyulan.hpp").enums
        for core_enum in core_def:
            if core_enum["name"] == "Instruction":
                for enum in core_enum["values"]:
                    self.instruction_enum[enum["name"]]=enum["value"]

    def number(self,node:List[lark.Token])->int:
        assert len(node) == 1
        return int(node[0].value,0)

    def STRING(self,node:str)->str:
        return node.replace('"','').replace("'","")

    def COMMENT(self,node:str):
        return lark.visitors.Discard

    def literal(self,node:List[Union[str,int]])->Union[str,int]:
        assert len(node)==1,str(node)
        if isinstance(node[0],lark.Token):
            value=getattr(self,node[0].type)(node[0].value)
            return value
        return node[0]

    def literal_list(self,node:List[Union[str,int]])->List[Union[str,int]]:
        return list(node)

    def REGISTER(self,node:lark.Token)->Register:
        return Register(node.value)

    def operand(self,node):
        return node[0]

    def operands(self,node):
        return list(node)

    def step(self,node):
        if node[0].value in self.instruction_enum:
            instruction=self.instruction_enum[node[0].value]
        else:
            instruction=node[0].value
        operands=node[1]
        return OneStep(instruction,operands)

    def start(self,node):
        for item in node:
            if isinstance(item,OneStep) and isinstance(item.instruction,str):
                num_placeholder=MACROS_LENGTH[item.instruction]-1
                for i in range(num_placeholder):
                    node.insert(node.index(item)+1,OneStep(self.instruction_enum["NOP"],[],True))
        return lark.Tree("start",node)

def parse(source:str) ->lark.Tree:
    with open("nyulan.lark") as larkfile:
        parser=lark.Lark(larkfile.read())
    return parser.parse(source)

def main()->None:
    parser=argparse.ArgumentParser(description="assemble nyulan assembly",prog="nyulan_asm.py")
    parser.add_argument("-s","--source",help="source file")
    parser.add_argument("-o","--output",help="output filename (in result folder)")
    args=parser.parse_args()

    source_filename=args.source
    with open(source_filename) as sourcefile:
        parsed_data=parse(sourcefile.read())
    generator=Flattener()
    transformed=generator.transform(parsed_data)
    print(transformed.pretty())

if __name__=="__main__":
    main()
