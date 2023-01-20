#!/usr/bin/python3
import os, re, sys
import subprocess as s
from termcolor import colored

output = {
    "SafeBoolMRSW.mn":(["id:3 val: True"],["Assertion failure"]),
    "arr.mn":(["CAS!"],["Assertion failure"]),
    "array2d.mn":(["0 1 2 3 4 5","7 8 9 10 11","len(a)=5"],["Assertion failure"]),
    "break.mn":(["Success 11 6"],["Assertion failure"]),
    "die.mn":(["at file 'die.mn' line 3: end",
               "at file 'die.mn' line 6: foo()",
               "at file 'die.mn' line 10: bar()",
               "Assertion failure"],[]),
    "fib.mn":(["load: v -> 5"],["Assertion failure"]),
    "file.mn":(["line: root","5:","-0.95892"],["Assertion failure"]),
    "hello.mn":(["n=55"],["Assertion failure"]),
    "imp.mn":(["answer=<3>"],["Assertion failure"]),
    "life.mn":(["life=42"],["Assertion failure"]),
    "math.mn":(["atan2=0.785398"],["Assertion failure"]),
    "mem.mn":(["msg: bad value of val:"],["Assertion failure"]),
    "mem2.mn":(["msg: bad value of val:"],["Assertion failure"]),
    "mem3.mn":(["msg: bad value of val:"],["Assertion failure"]),
    "obj.mn":(["a=3"],["Assertion failure"]),
    "vec.mn":(["a.size()=1"],["Assertion failure"]),
    "while.mn":(["i=9"],["Assertion failure"]),
    "RegIntMRSW.mn":([],["Assertion failure"]),
    "Race.mn":(["val=550"],["Assertion failure"]),
    "Stack.mn":(["s=20"],["Assertion failure"]),
    "sp.mn":(["len: 3","a: 8"],["Assertion failure"]),
}

for f in os.listdir("."):
    if re.match(r'.*\.mn$',f):
        if f not in output:
            print(colored("Skipping:","red"),f)
            continue
        print(colored("Running:","blue"),f)
        p = s.Popen(["./mnemo","--bw",f], stdout=s.PIPE, stderr=s.PIPE, universal_newlines=True)
        o, e = p.communicate(0)
        has, hasnot = output[f]
        for h in has:
            if h not in o:
                raise Exception(h+" was not in output")
        for h in hasnot:
            if h in o:
                raise Exception(h+" was in output")
    
print(colored("Success","green"))
