from Piraha import *

g = Grammar()
compileFile(g,"test.peg")
with open("hello.in") as fd:
    fc = fd.read()
m = Matcher(g,g.default_rule,fc)
if m.matches():
    pass #print(m.gr.dump())
else:
    m.showError()
    raise Exception()

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

class Var:
    def __init__(self,name,val,qual):
        self.name = name
        self.val = val
        self.qual = qual
    def check(self):
        assert self.qual in ["atomic","const","regular","safe"]
    def set(self,v):
        if self.val is None:
            self.val = v
        else:
            assert self.qual != "const", "Attempt to set a constant variable"
            self.val = v
    def get(self):
        return self.val

class Interp:
    def __init__(self,gr):
        self.gr = gr
        self.pc = -1
        self.stack = []
        self.rets = []
        self.funs = {}
        self.vars = [{}]
        self.loads = [{}]
        self.inst = []
        for i in range(gr.groupCount()):
            self.load_instructions(gr.group(i))
            self.inst += [gr.group(i)]
    def load_instructions(self,group):
        nm = group.getPatternName()
        if nm == "var" or nm == "fun":
            load = Group("load",group.text,group.start,group.end)
            load.children += [group]
            self.inst += [load]
        elif nm == "assign" or nm == "def":
            self.load_instructions(group.group(2))
        else:
            for i in range(group.groupCount()):
                self.load_instructions(group.group(i))
    def getval(self,expr):
        nm = expr.getPatternName()
        if nm == "expr":
            if expr.groupCount() == 1:
                return self.getval(expr.group(0))
            elif expr.groupCount() == 3:
                val1 = self.getval(expr.group(0))
                op = expr.group(1).substring()
                val2 = self.getval(expr.group(2))
                sw = type(val1).__name__+op+type(val2).__name__
                if sw == "int+int":
                    return val1+val2
                elif sw == "int-int":
                    return val1-val2
                elif sw == "int*int":
                    return val1*val2
                elif sw == "int/int":
                    return val1//val2
                raise Exception("sw="+sw)
        elif nm == "val":
            return self.getval(expr.group(0))
        elif nm == "num":
            return int(expr.substring())
        elif nm == "str":
            sval = expr.substring()
            return sval[1:-1]
        elif nm == "var" or nm == "fun":
            return self.loads[-1][expr.start]
        print(expr.dump())
        raise Exception(nm)
    def step(self):
        assert self.pc >= 0
        if self.pc >= len(self.inst):
            return False
        s = self.inst[self.pc]
        print("step:",self.pc) #,s.dump())
        nm = s.getPatternName()
        if nm == "start_fn":
            while s.getPatternName() != "end":
                self.pc += 1
                s = self.inst[self.pc]
            self.pc += 1
            return True
        elif nm == "load":
            if s.group(0).getPatternName() == "var":
                vname = s.group(0).substring()
                if vname in self.vars[-1]:
                    var = self.vars[-1][vname]
                else:
                    var = self.vars[0][vname]
                self.loads[-1][s.group(0).start] = var.get()
                self.pc += 1
                return True
            if s.group(0).getPatternName() == "fun":
                expr = s.group(0)
                fname = expr.group(0).substring()
                funinst = self.funs[fname]
                funval = self.inst[funinst-1]
                print(funval.dump())
                argdefs = funval.group(1)
                argvals = expr.group(1)
                assert argdefs.groupCount() == argvals.groupCount(),"Arity mismatch for "+expr.substring()
                self.vars += [{}]
                for i in range(argdefs.groupCount()):
                    argname = argdefs.group(i).substring()
                    argval = self.getval(argvals.group(i))
                    argvar = Var(argname, argval, "const")
                    self.vars[-1][argname] = argvar
                self.loads += [{}]
                self.stack += [self.pc+1]
                self.rets += [s.start]
                self.pc = funinst
                return True
        elif nm == "def":
            qual = s.group(0).substring()
            val = self.getval(s.group(2))
            if s.group(1).getPatternName() == "var":
                vname = s.group(1).substring()
                assert vname not in self.vars[-1],"Redefinition of "+vname+" at line  "+str(s.linenum())
                var = Var(vname,val,qual)
                self.vars[-1][vname] = var
                self.pc += 1
                return True
        elif nm == "assign":
            op = s.group(1).substring()
            val = getval(s.group(2))
            if s.group(0).getPatternName() == "var":
                vname = s.group(0).substring()
                if op == ":=":
                    assert vname not in self.vars[-1],"Redefinition of "+vname+" at line  "+str(s.linenum())
                    var = Var(vname,val)
                    self.vars[-1][vname] = var
                    self.pc += 1
                    return True
                elif op == "=":
                    assert (vname in self.vars[-1]) or (vname in self.vars[0]),"Undefined variable "+vname+" at line "+str(s.linenum())
                    if vname in self.vars[-1]:
                        var = self.vars[-1][vname]
                    else:
                        var = self.vars[0][vname]
                    var.set(val)
                    self.pc += 1
                    return True
                else:
                    raise Exception(op)
        elif nm == "call":
            fnm = s.group(0).substring()
            if fnm == "print":
                vals = s.group(1)
                for i in range(vals.groupCount()):
                    print(self.getval(vals.group(i)),end='')
                print()
                self.pc += 1
                return True
            elif fnm in self.funs:
                self.stack += [self.pc+1]
                self.pc = self.funs[fnm]
                self.vars += [{}]
                self.loads += [{}]
                return True
        elif nm == "end":
            if len(self.stack) == 0:
                return False
            self.pc = self.stack[-1]
            self.stack = self.stack[:-1]
            self.vars = self.vars[:-1]
            self.loads = self.loads[:-1]
            return True
        elif nm == "returnstmt":
            retval = self.getval(s.group(0))

            self.pc = self.stack[-1]
            retkey = self.rets[-1]

            self.stack = self.stack[:-1]
            self.vars = self.vars[:-1]
            self.loads = self.loads[:-1]
            self.rets = self.rets[:-1]

            self.loads[-1][retkey] = retval
            return True
        raise Exception(s.dump())
        return False

interp = Interp(m.gr)

# Find functions
for i in range(len(interp.inst)):
    g = interp.inst[i]
    nm = g.getPatternName() 
    if nm == "start_fn":
        fnm = g.group(0).substring()
        interp.funs[fnm] = i+1

interp.pc = 0

while interp.step():
    pass

if "main" in interp.funs:
    interp.pc = interp.funs["main"]
    interp.vars += [{}]
    while interp.step():
        pass
