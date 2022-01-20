#!/usr/bin/env python3
import CppHeaderParser
import argparse
import lark
from typing import List,Dict,Union
import json
import sys
from pathlib import Path
import gzip

class Register(int):
    def __new__(cls,value:str):
        return int.__new__(cls,value[1:])

class OneStep:
    def __init__(self,instruction,operands,is_placeholder=False):
        self.instruction=instruction
        self.operands=operands
        self.is_placeholder=is_placeholder

    def __repr__(self):
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

class PointerLike():
    def __init__(self,name:str,address:int):
        self.name=name
        self.address=address
    def __repr__(self):
        return f"{self.name}=>{self.address}"

class Label(PointerLike):
    pass

class Variable(PointerLike):
    pass

class MiddlecodeGenerator(lark.Transformer):
    instruction_enum:Dict[str,int]=dict()

    data_segment:List[int]=list()
    variables:List[Variable]=list()
    labels:List[Label]=list()
    global_labels:List[str]=list()
    external_labels:List[str]=list()
    num_steps:int=0
    steps:List[OneStep]

    def __repr__(self):
        return f"""
MiddlecodeGenerator{{
    data_segment_size:{len(self.data_segment)}
    data_segment:{self.data_segment}
    variables:{self.variables}
    labels:{self.labels}
    global_labels:{self.global_labels}
    external_labels:{self.external_labels}
    num_steps:{self.num_steps}
    steps:{self.steps}
}}
        """

    def __init__(self)->None:
        self.instruction_enum=dict()
        core_def=CppHeaderParser.CppHeader(Path(__file__).parent/"nyulan_vm/nyulan.hpp").enums
        for core_enum in core_def:
            if core_enum["name"] == "Instruction":
                for enum in core_enum["values"]:
                    self.instruction_enum[enum["name"]]=enum["value"]

    def from_tree(self,tree:lark.Tree)->None:
        super().transform(tree)

    def number(self,node:List[lark.Token])->int:
        assert len(node) == 1
        return int(node[0].value,0)

    def STRING(self,node:str)->List[int]:
        return list(map(ord,node.replace('"','').replace("'","")))

    def COMMENT(self,node:str):
        return lark.visitors.Discard

    def literal(self,node:List[int])->List[int]:
        assert len(node)==1,str(node)
        if isinstance(node[0],lark.Token):
            value=getattr(self,node[0].type)(node[0].value)
            return value
        return node[0]

    def literal_list(self,node:List[Union[List[str],int]])->List[Union[str,int]]:
        result=list()
        for item in node:
            if isinstance(item,list):
                result+=item
            else:
                result.append(item)
        return result

    def REGISTER(self,node:lark.Token)->Register:
        return Register(node.value)

    def operand(self,node):
        return node[0]

    def operands(self,node):
        return list(node)

    def step(self,node):
        if node[0].value in self.instruction_enum:
            instruction=self.instruction_enum[node[0].value]
            self.num_steps+=1
        else:
            instruction=node[0].value
            self.num_steps+=MACROS_LENGTH[node[0].value]
        operands=node[1]
        return OneStep(instruction,operands)

    def start(self,node):
        for item in node:
            if isinstance(item,OneStep) and isinstance(item.instruction,str):
                num_placeholder=MACROS_LENGTH[item.instruction]-1
                for i in range(num_placeholder):
                    node.insert(node.index(item)+1,OneStep(self.instruction_enum["NOP"],[],True))
        self.steps=node
        return lark.Discard

    def def_var(self,node):
        assert node[0].type=="IDENTIFIER"
        addr=len(self.data_segment)#序数は0始まりだが、基数は1始まり
        self.data_segment+=node[1]
        self.variables.append(Variable(node[0].value,addr))
        return lark.Discard

    def define_label(self,node):
        self.labels.append(Label(node[0].value,self.num_steps))
        return lark.Discard

    def export_label(self,node):
        self.global_labels.append(node[0].value)
        return lark.Discard

    def dump(self,outputfile)->None:
        outputfile.write(self.dumps())

    def dumps(self)->str:
        """
        data_segment:List[int]=list()
        variables:List[Variable]=list()
        labels:List[Label]=list()
        global_labels:List[str]=list()
        external_labels:List[str]=list()
        num_steps:int=0
        steps:List[OneStep]
        """
        result=dict()
        result["name"]="NYULAN_MIDDLECODE"
        self.add_member_to_dict(result,"data_segment")
        self.add_member_to_dict(result,"variables")
        self.add_member_to_dict(result,"labels")
        self.add_member_to_dict(result,"global_labels")
        self.add_member_to_dict(result,"external_labels")
        self.add_member_to_dict(result,"steps")
        return json.dumps(result,default=vars)

    def add_member_to_dict(self,dst,name):
        dst[name]=getattr(self,name)

def parse(source:str) ->lark.Tree:
    with open(Path(__file__).parent/"nyulan.lark") as larkfile:
        parser=lark.Lark(larkfile.read())
    return parser.parse(source)

def main()->None:
    parser=argparse.ArgumentParser(description="assemble nyulan assembly",prog="nyulan_asm.py")
    parser.add_argument("-s","--source",help="source file")
    parser.add_argument("-o","--output",help="output filename (in result folder)")
    args=parser.parse_args()

    if args.source == None :
        print("error: no sourcefile was given",file=sys.stderr)

    if args.output == None:
        args.output=Path(args.source).with_suffix(".nlib")

    with open(args.source) as sourcefile:
        parsed_data=parse(sourcefile.read())
    generator=MiddlecodeGenerator()
    generator.from_tree(parsed_data)

    with gzip.open(args.output,"wb") as outputfile:
        outputfile.write(generator.dumps().encode())

if __name__=="__main__":
    main()
