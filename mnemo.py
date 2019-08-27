from Piraha import *

g = Grammar()
compileFile(g,"test.peg")
with open("hello.in") as fd:
    fc = fd.read()
m = Matcher(g,g.default_rule,fc)
if m.matches():
    print(m.gr.dump())
else:
    m.showError()

def feval(s):
    pre = []
    vals = []
    nm = s.getPatternName()
    if nm == "vals":
        for i in range(s.groupCount()):
            vals += [feval(s.group(i))]
        return (pre, vals)
    if nm in ["expr", "val"]:
        if s.groupCount()==1:
            return feval(s.group(0))
        else:
            ty1, arg1 = feval(s.group(0))
            op = feval(s.group(1))
            ty2, arg2 = feval(s.group(2))
            etxt = ty1+op+ty2
            if etxt == "num+num":
                return int(arg1)+int(arg2)
            elif etxt == "num-num":
                return int(arg1)-int(arg2)
            elif etxt == "num*num":
                return int(arg1)*int(arg2)
            elif etxt == "num/num":
                return int(arg1)//int(arg2)
            raise Exception(etxt)
    if nm == "str":
        stxt = s.substring()
        return stxt[1:-1]
    if nm == "op":
        return s.substring()
    if nm in ["real", "num"]:
        return [nm, s.substring()]
    raise Exception(nm)

class Interp:
    def __init__(self,gr):
        self.gr = gr
        self.pc = -1
        self.funs = {}
        self.globs = {}
    def step(self):
        assert self.pc >= 0
        print("step:",self.pc)
        s = self.gr.group(self.pc)
        nm = s.getPatternName()
        if nm == "start_fn":
            self.pc += 1
            return True
        if nm == "call":
            fnm = s.group(0).substring()
            if fnm == "print":
                for i in range(1,s.groupCount()):
                    pre, vals = feval(s.group(i))
                    for v in vals:
                        print(v,end='')
                print()
        return False

interp = Interp(m.gr)

# Find functions
for i in range(m.groupCount()):
    g = m.group(i)
    nm = g.getPatternName() 
    if nm == "start_fn":
        fnm = g.group(0).substring()
        if fnm == "main":
            interp.pc = i
        interp.funs[fnm] = i

while interp.step():
    pass
