#!/usr/bin/python3
import os, re, sys
import subprocess as s

output = {
    "SafeBoolMRSW.mn":(["id:3 val: True"],[]),
    "arr.mn":(["CAS!"],[]),
    "array2d.mn":(["$ $ $ $ $ $ $ $","len(a)=5"],[]),
    "break.mn":(["Success 11 6"],[]),
    "die.mn":(["at file 'die.mn' line 3: end",
               "at file 'die.mn' line 6: foo()",
               "at file 'die.mn' line 10: bar()"],[]),
    "fib.mn":(["load: v -> 5"],[]),
    "file.mn":(["line: root","5:","-0.95892"],[]),
    "hello.mn":(["n=55"],[]),
    "imp.mn":(["answer=<3>"],[]),
    "life.mn":(["life=42"],[]),
    "math.mn":(["atan2=0.785398"],[]),
    "mem.mn":(["msg: bad value of val:"],[]),
    "mem2.mn":(["msg: bad value of val:"],[]),
    "mem3.mn":(["msg: bad value of val:"],[]),
    "obj.mn":(["a=3"],[]),
    "vec.mn":(["a.size()=1"],[]),
    "while.mn":(["i=9"],[]),
}

for f in os.listdir("."):
    if re.match(r'.*\.mn$',f):
        print("Running:",f)
        p = s.Popen(["mnemo","--bw",f], stdout=s.PIPE, stderr=s.PIPE, universal_newlines=True)
        o, e = p.communicate(0)
        has, hasnot = output[f]
        for h in has:
            if h not in o:
                raise Exception(h+" was not in output")
        for h in hasnot:
            if h in o:
                raise Exception(h+" was in output")
    
