from Piraha import *
from termcolor import colored
import sys

INDENT = "  "

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
        self.ends = []
        self.stack = []
        self.rets = []
        self.funs = {}
        self.vars = [{}]
        self.loads = [{}]
        self.inst = []
        self.indent = 0
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
        elif nm == "array":
            ar = []
            for i in range(expr.groupCount()):
                ar += [self.getval(expr.group(i))]
            return ar
        print(expr.dump())
        raise Exception(nm)
    def start_call(self,expr,retkey):
        fname = expr.group(0).substring()
        print(INDENT * self.indent,colored("start call: ","green"),colored(fname,"blue"),sep='')
        self.indent += 1
        funinst = self.funs[fname]
        funval = self.inst[funinst-1]
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
        self.rets += [retkey]
        self.pc = funinst
        self.ends += [("fun",)]
    def end_call(self,retval):
        self.indent -= 1
        print(INDENT * self.indent,colored("end call","green"),sep='')
        self.pc = self.stack[-1]
        retkey = self.rets[-1]

        self.stack = self.stack[:-1]
        self.vars = self.vars[:-1]
        self.loads = self.loads[:-1]
        self.rets = self.rets[:-1]

        self.loads[-1][retkey] = retval
    def step(self):
        assert self.pc >= 0
        if self.pc >= len(self.inst):
            return False
        s = self.inst[self.pc]
        nm = s.getPatternName()
        if nm == "load":
            print(INDENT*self.indent,colored("step: "+str(self.pc),"green")," ",colored("load: "+s.substring(),"blue"),sep='')
        elif nm == "start_fn":
            print(colored("step: "+str(self.pc),"green"),colored("define function: "+s.substring(),"blue"))
        else:
            print(INDENT*self.indent,colored("step: "+str(self.pc),"green")," ",colored(s.substring(),"blue"),sep='')
        if nm == "start_fn":
            end_count = 1
            while True:
                nm = s.getPatternName()
                if nm == "for":
                    end_count += 1
                elif nm == "end":
                    end_count -= 1
                if end_count > 0:
                    self.pc += 1
                    s = self.inst[self.pc]
                else:
                    break
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
                self.start_call(expr,s.start)
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
            val = self.getval(s.group(2))
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
                self.start_call(s,s.start)
                return True
        elif nm == "end":
            if len(self.stack) == 0:
                return False
            ends = self.ends[-1]
            if ends[0] == "fun":
                self.end_call(None)
                self.ends = self.ends[:-1]
            elif ends[0] == "for":
                _, loopvar, startval, endval, fpc = ends
                oldval = self.vars[-1][loopvar].get()
                if oldval < endval:
                    self.vars[-1][loopvar] = Var(loopvar,oldval+1,"const")
                    self.pc = fpc
                else:
                    self.ends = self.ends[:-1]
                self.pc += 1
            return True
        elif nm == "returnstmt":
            self.ends = self.ends[:-1]
            retval = self.getval(s.group(0))
            self.end_call(retval)
            return True
        elif nm == "for":
            loopvar = s.group(0).substring()
            startval = self.getval(s.group(1))
            endval = self.getval(s.group(2))
            self.vars[-1][loopvar] = Var(loopvar,startval,"const")
            self.ends += [("for",loopvar,startval,endval,self.pc)]
            self.pc += 1
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
    mainloc = interp.funs["main"]
    maing = interp.inst[mainloc-1]
    main_arg_count = maing.group(1).groupCount()
    #interp.vars += [{}]
    expr = Group("_start",m.gr.text,m.gr.start,m.gr.end)
    fun = Group("fun","main",0,4)
    args = Group("args","",0,0)
    if main_arg_count == 1:
        argv = Group("array","",0,0)
        for a in sys.argv:
            argv.children += [Group("str",'"'+a+'"',0,2+len(a))]
        args.children += [argv]
    expr.children += [fun,args]
    interp.start_call(expr,0)
    while interp.step():
        pass
    retval = interp.loads[-1][0]
    if retval is None:
        exit(0)
    elif type(retval) == int:
        exit(retval)
    else:
        raise Exception("return from main not an int: "+str(retval))
