#!/usr/bin/python3
from Piraha import *
import sys
from random import randint

if sys.argv[1] == "--bw":
    sys.argv = sys.argv[1:]
    def colored(x,_):
        return x
else:
    from termcolor import colored

INDENT = "  "

threads = []

g = Grammar()
compileFile(g,"test.peg")
with open(sys.argv[1]) as fd:
    fc = fd.read()
m = Matcher(g,g.default_rule,fc)
if m.matches():
    pass #print(m.gr.dump())
else:
    m.showError()
    raise Exception()

class BadAddress:
    pass

class Var:
    def __init__(self,name,val,qual):
        self.name = name
        self.val = val
        self.oldval = None
        self.qual = qual
        self.finished = True
    def check(self):
        assert self.qual in ["atomic","const","regular","safe"]
    def set(self,v):
        self.finished = False
        self.oldval = self.val
        if self.val is None:
            self.val = v
        else:
            assert self.qual != "const", "Attempt to set a constant variable"
            self.val = v
    def get(self):
        if self.finished:
            return self.val
        elif self.qual == "atomic":
            if randint(1,3) == 1:
                self.oldval = self.val
            return self.oldval
        elif self.qual == "regular":
            if randint(1,2) == 1:
                return self.oldval
            else:
                return self.val
        elif self.qual == "safe":
            if type(self.val) == int:
                val = randint(-1000,1000)
            elif type(self.val) == float:
                val = 2000*(random()-.5)
            else:
                val = BadAddress()
            return val
        else:
            raise Exception(self.qual)
    def storeFinish(self):
        self.finished = True

thread_seq = 0
class Interp:
    def done(self):
        return len(self.stack) == 0

    def __init__(self,gr):
        global thread_seq

        self.id = thread_seq
        thread_seq += 1

        self.gr = gr
        self.pc = -1
        self.stack = []
        self.rets = []
        self.vars = [
            {"true":Var("true",True,"const"),
             "false":Var("false",False,"const")}]
        self.loads = [{}]
        self.inst = []
        self.indent = 0
        self.delay = 0
        for i in range(gr.groupCount()):
            self.load_instructions(gr.group(i))

        # Find functions
        for i in range(len(self.inst)):
            g = self.inst[i][0]
            nm = g.getPatternName() 
            if nm == "start_fn":
                fnm = g.group(0).substring()
                self.vars[0][fnm] = Var("fname",i+1,"const")

    def diag(self):
        # Diagnostic of the instruction set
        for i in range(len(self.inst)):
            print(colored(str(i)+":","yellow"),end=' ')
            nm = self.inst[i][0].getPatternName()
            if nm in ["load", "store", "assign"]:
                print(colored(nm,"red"),self.inst[i][0].substring(),end=' ')
            else:
                print(colored(nm,"red"),end=' ')
            for j in range(1,len(self.inst[i])):
                  print(colored(self.inst[i][j],"green"),end='')
            print()
        print('=====')

    def load_instructions(self,group):
        nm = group.getPatternName()
        if nm == "var" or nm == "fun":
            if nm == "fun":
                for i in range(group.groupCount()):
                    self.load_instructions(group.group(i))
            load = Group("load",group.text,group.start,group.end)
            load.children += [group]
            self.inst += [(load,)]
        elif nm == "ifstmt":
            prelist = []
            ilist = []
            glist = []
            for i in range(group.groupCount()):
                g = group.group(i)
                nm = g.getPatternName()
                if nm in ["else","elif"]:
                    glist += [len(self.inst)]
                    self.inst += [(Group("goto","",0,0),)]
                n1 = len(self.inst)
                self.load_instructions(group.group(i))
                if nm in ["if","elif","else","end"]:
                    n2 = len(self.inst)-1
                    prelist += [n1]
                    ilist += [n2]
                    print("adding:",nm,ilist[-1])
            for k in range(len(ilist)-1):
                k1 = ilist[k]
                k2 = prelist[k+1]
                self.inst[k1] = (self.inst[k1][0], k2)
            k1 = ilist[-1]
            k2 = ilist[0]
            self.inst[k1] = (self.inst[k1][0], k2)
            for g in glist:
                self.inst[g] = (self.inst[g][0], k1)
        elif nm == "assign" or nm == "def":
            self.load_instructions(group.group(2))
            self.inst += [(group,)]
            if nm == "assign":
                store = Group("store",group.text,group.start,group.end)
                store.children += [group.group(0)]
                self.inst += [(store,)]
        elif nm in ["expr", "val", "num", "op", "array", "str", "name", "args", "vals", "body", "real", "elem", "alloc", "qual"]:
            for i in range(group.groupCount()):
                self.load_instructions(group.group(i))
        elif nm in ["start_fn", "call", "end", "returnstmt", "for", "if", "elif", "else", "import", "while"]:
            for i in range(group.groupCount()):
                self.load_instructions(group.group(i))
            self.inst += [(group,)]
        elif nm in ["fun_def", "forstmt", "whilestmt"]:
            fstart = len(self.inst)
            for i in range(group.groupCount()):
                self.load_instructions(group.group(i))
                if i == 0:
                    i0 = len(self.inst)-1
            endptr = len(self.inst)-1
            assert self.inst[endptr][0].getPatternName() == "end"
            if nm == "whilestmt":
                self.inst[i0] = (self.inst[i0][0], endptr) # point to end
            else:
                self.inst[fstart] = (self.inst[fstart][0], endptr) # point to end
            self.inst[endptr] = (self.inst[endptr][0], fstart) # point to start
        else:
            raise Exception(nm)
    def getval(self,expr):
        nm = expr.getPatternName()
        if nm == "expr":
            if expr.groupCount() == 1:
                return self.getval(expr.group(0))
            elif expr.groupCount() == 3:
                val1 = self.getval(expr.group(0))
                t1 = type(val1)
                op = expr.group(1).substring()
                val2 = self.getval(expr.group(2))
                t2 = type(val2)
                if t1 == int and t2 == float:
                    val1 = float(val1)
                    t1 = float
                elif t1 == float and t2 == int:
                    val2 = float(val2)
                    t2 = float
                if op == "+":
                    return val1+val2
                elif op == "-":
                    return val1-val2
                elif op == "*":
                    return val1*val2
                elif op == "/":
                    if [t1,t2]==[int,int]:
                        return val1//val2
                    else:
                        return val1/val2
                elif op == "==":
                    return val1==val2
                elif op == "<":
                    return val1<val2
                elif op == ">":
                    return val1>val2
                elif op == "<=":
                    return val1<=val2
                elif op == ">=":
                    return val1>=val2
                elif op == "!=":
                    return val1!=val2
                elif op == "and":
                    return val1 and val2
                elif op == "or":
                    return val1 or val2
                elif op == "%":
                    return val1 % val2
                raise Exception("op="+op)
        elif nm == "val":
            return self.getval(expr.group(0))
        elif nm == "num":
            return int(expr.substring())
        elif nm == "str":
            sval = expr.substring()
            return sval[1:-1]
        elif nm == "var" or nm == "fun":
            return self.loads[-1][expr.start]
        elif nm == "real":
            return float(expr.substring())
        elif nm == "alloc":
            ar = []
            qual = expr.group(0).substring()
            vals = expr.group(1)
            for i in range(vals.groupCount()):
                ar += [Var("&",self.getval(vals.group(i)),qual)]
            return ar
        raise Exception(nm)
    def die(self,msg):
        print("Die:",msg)
        self.stack += [self.pc] # Add current location to the stack
        for k in range(len(self.stack)-1,-1,-1):
            pc = self.stack[k]
            if pc < len(self.inst):
                pg = self.inst[pc][0]
                print(" at line %d: %s" % (pg.linenum(), pg.substring()))
        exit(1)
    def start_call(self,expr,retkey):
        global threads
        ####
        fnm = expr.group(0).substring()
        if fnm == "print":
            vals = expr.group(1)
            for i in range(vals.groupCount()):
                print(self.getval(vals.group(i)),end='')
            print()
            self.pc += 1
            return True
        elif fnm == "assert":
            self.pc += 1
            vals = expr.group(1)
            val = self.getval(vals.group(0))
            if val != True:
                self.die("Assertion failure: "+vals.substring())
            return True
        elif fnm == "spawn":
            vals = expr.group(1)
            newthread = Interp(self.gr)
            newthread.indent = 0
            for k in self.vars[0].keys():
                newthread.vars[0][k] = self.vars[0][k]
            newthread.pc = len(self.inst)
            newthread.start_call(vals,expr.start)
            threads += [newthread]
            self.pc += 1
            vid = Var("id",newthread.id,"const")
            self.loads[-1][retkey] = newthread.id # vid
            return True
        elif fnm == "is_alive":
            self.pc += 1
            vals = expr.group(1)
            pid = self.getval(vals.group(0))
            found = False
            for th in threads:
                if pid == th.id:
                    found = True
                    break
            vid = found # Var("alive",found,"const")
            self.loads[-1][retkey] = vid
            return
        ####
        fname = expr.group(0).substring()
        print(INDENT * self.indent,colored(str(self.id)+": ","blue"),colored("start call: ","green"),colored(fname,"blue"),sep='')
        self.indent += 1
        funinst = self.vars[0][fname].get()
        funval = self.inst[funinst-1][0]
        argdefs = funval.group(1)
        argvals = expr.group(1)
        n1 = argdefs.groupCount()
        n2 = argvals.groupCount()
        assert n1 == n2,"Arity mismatch for "+fname+" %d != %d" % (n1,n2)
        self.vars += [{}]
        for i in range(argdefs.groupCount()):
            argname = argdefs.group(i).substring()
            argval = self.getval(argvals.group(i))
            argvar = Var(argname, argval, "const")
            self.vars[-1][argname] = argvar
        self.loads += [{}]
        self.stack += [self.pc]
        self.rets += [retkey]
        self.pc = funinst
    def end_call(self,retval):
        self.indent -= 1
        self.pc = self.stack[-1]+1
        retkey = self.rets[-1]

        self.stack = self.stack[:-1]
        self.vars = self.vars[:-1]
        self.loads = self.loads[:-1]
        self.rets = self.rets[:-1]

        self.loads[-1][retkey] = retval
        print(INDENT * self.indent,colored(str(self.id)+": ","blue"),colored("end call %d->%s" % (retkey, str(retval)),"green"),sep='')
    def step(self):
        global threads
        assert self.pc >= 0
        if self.pc >= len(self.inst):
            return False
        if self.delay > 0:
            print(INDENT*self.indent,colored("%d: " % self.id,"blue"),colored("delay","green"),sep='')
            self.delay -= 1
            return True
        s = self.inst[self.pc][0]
        nm = s.getPatternName()
        if nm == "load":
            print(INDENT*self.indent,colored(str(self.id)+": ","blue"),colored("step: "+str(self.pc),"green")," ",colored("load: "+s.substring(),"blue"),sep='',end=' ')
        elif nm == "start_fn":
            pass #print(colored("step: "+str(self.pc),"green"),colored("define function: "+s.substring(),"blue"))
        elif nm == "store":
            print(INDENT*self.indent,colored(str(self.id)+": ","blue"),colored("step: "+str(self.pc),"green")," ",colored("finish: "+s.substring(),"blue"),sep='')
        elif nm == "assign":
            print(INDENT*self.indent,colored(str(self.id)+": ","blue"),colored("step: "+str(self.pc),"green")," ",colored("start: "+s.substring(),"blue"),sep='')
        else:
            print(INDENT*self.indent,colored(str(self.id)+": ","blue"),colored("step: "+str(self.pc),"green")," ",colored(s.substring(),"blue"),sep='')
        if nm == "start_fn":
            self.pc = self.inst[self.pc][1]+1
            return True
        elif nm == "load":
            if s.group(0).getPatternName() == "var":
                vg = s.group(0)
                if vg.group(0).getPatternName() == "name":
                    vname = vg.substring()
                    elems = []
                else:
                    elg = vg.group(0)
                    vname = elg.group(0).substring()
                    elems = elg.group(1).children
                if vname in self.vars[-1]:
                    var = self.vars[-1][vname]
                elif vname in self.vars[0]:
                    var = self.vars[0][vname]
                else:
                    self.die('No variable named: '+vname)
                for ch in elems:
                    chv = self.getval(ch)
                    var = var.get()[chv]
                val = var.get()
                self.loads[-1][s.group(0).start] = val
                print(colored("-> "+str(val),"yellow"))
                self.pc += 1
                return True
            elif s.group(0).getPatternName() == "fun":
                expr = s.group(0)
                print()
                self.start_call(expr,s.start)
                return True
            else:
                raise Exception()
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
            self.delay = randint(0,2)
            nm = s.group(0).getPatternName()
            if nm == "var":
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
                    self.store_var = var
                    self.pc += 1
                    return True
                else:
                    raise Exception(op)
            elif nm == "elem":
                self.pc += 1
                lhs = s.group(0)
                vname = lhs.group(0).substring()
                if vname in self.vars[-1]:
                    var = self.vars[-1][vname]
                else:
                    var = self.vars[0][vname]
                for i in range(1,lhs.groupCount()):
                    ind = self.getval(lhs.group(i))
                    try:
                        var = var.get()[ind]
                    except IndexError as ie:
                        self.die(str(ie))
                rhs = self.getval(s.group(2))
                op = s.group(1).substring()
                if op == "=":
                    self.store_var = var
                    var.set(rhs)
                    return True
                raise Exception()
            else:
                raise Exception(nm)
        elif nm == "call":
            self.start_call(s,s.start)
            return True
        elif nm == "end":
            if len(self.stack) == 0:
                return False
            step_info = self.inst[self.pc]
            endix = step_info[1]
            start_info = self.inst[endix]
            ends = start_info[0].getPatternName()
            if ends == "start_fn":
                self.end_call(None)
            elif ends == "if":
                self.pc += 1
            elif ends == "for":
                loopvar = start_info[0].group(0).substring()
                startval = self.getval(start_info[0].group(1))
                endval = self.getval(start_info[0].group(2))
                oldval = self.vars[-1][loopvar].get()
                if oldval < endval:
                    self.vars[-1][loopvar] = Var(loopvar,oldval+1,"const")
                    self.pc = endix
                else:
                    del self.vars[-1][loopvar]
                self.pc += 1
            elif ends == "load":
                # This is a while statement
                self.pc = step_info[1]
            else:
                raise Exception(ends)
            return True
        elif nm == "returnstmt":
            retval = self.getval(s.group(0))
            self.end_call(retval)
            return True
        elif nm == "for":
            loopvar = s.group(0).substring()
            startval = self.getval(s.group(1))
            endval = self.getval(s.group(2))
            assert loopvar not in self.vars[-1],"Loop attempts to redefine "+loopvar
            self.vars[-1][loopvar] = Var(loopvar,startval,"const")
            self.pc += 1
            return True
        elif nm == "if" or nm == "elif":
            bval = self.getval(s.group(0))
            assert type(bval) == bool, "If expression does not evaluate to boolean "+s.substring()
            if bval:
                self.pc += 1
                return True
            else:
                self.pc = self.inst[self.pc][1]
                return True
        elif nm == "else":
            self.pc += 1
            return True
        elif nm == "goto":
            self.pc = self.inst[self.pc][1]
            return True
        elif nm == "import":
            fname = self.getval(s.group(0))
            funs = []
            for i in range(1,s.groupCount()):
                funs += [s.group(i).substring()]
            with open(fname,"r") as fd:
                fc = fd.read()
            m2 = Matcher(g,g.default_rule,fc)
            if not m2.matches():
                m2.showError()
            for k in range(m2.gr.groupCount()):
                elem = m2.gr.group(k) 
                nm = elem.getPatternName()
                if nm == "fun_def":
                    func = elem.group(0).group(0).substring()
                    if func in funs:
                        ind = len(self.inst)+1
                        self.vars[0][func] = Var("fun_def",ind,"const")
                        self.load_instructions(elem)
                        #print("fdef:",func,"->",ind,self.inst[ind][0].dump())
            self.pc += 1
            return True
        elif nm == "store":
            self.store_var.storeFinish()
            self.pc += 1
            return True
        elif nm == "while":
            val = self.getval(s.group(0))
            if val == True:
                self.pc += 1
            elif val == False:
                self.pc = self.inst[self.pc][1] + 1
            else:
                raise Exception(val)
            return True
        raise Exception(s.dump())
        return False

interp = Interp(m.gr)

threads += [interp]

interp.pc = 0

def run_step():
    while True:
        lo = 0
        hi = len(threads)-1
        if hi < 0:
            return False
        if lo == hi:
            tno = lo
        else:
            tno = randint(lo, hi)
        thread = threads[tno]
        if not thread.step():
            del threads[tno]
        else:
            return True

def addgr(gr,sgr,ss):
    g = Group(sgr,ss,0,len(ss))
    gr.children += [g]
    return g

while run_step():
    pass

if "main" in interp.vars[0]:

    # Need to re-add the thread before calling main
    threads += [interp]

    mainloc = interp.vars[0]["main"].get()
    maing = interp.inst[mainloc-1][0]
    main_arg_count = maing.group(1).groupCount()
    #interp.vars += [{}]
    expr = Group("call","",0,0)
    addgr(expr,"name","main")
    vals = addgr(expr,"vals","")
    if main_arg_count == 1:
        alloc = addgr(vals,"alloc","")
        addgr(alloc,"qual","const")
        array = addgr(alloc,"array","")
        for a in sys.argv:
            addgr(array,"str",'"'+a+'"')
    interp.start_call(expr,0)
    while run_step():
        pass
    retval = interp.loads[-1][0]
    if retval is None:
        exit(0)
    elif type(retval) == int:
        exit(retval)
    else:
        raise Exception("return from main not an int: "+str(retval))
