#!/usr/bin/env python3
from typing import Dict, Any, List, Tuple, Union, Optional, cast
from piraha import Grammar, compileFile, Matcher, Group
from piraha.colored import colored
from piraha.here import here
import sys, os
from random import randint, seed, random
import argparse

def print_debug_help():
    print("""
print var
    Print the value of variable var

step threadno
    Tell thread threadno to execute one step

pc
    Print the program counters for all threads

stack
    Print a stack trace for all threads

go or continue
    Resume normal execution""")

parser = argparse.ArgumentParser(description='The Mnemosyne Interpreter')
parser.add_argument('--seed', type=int, default=randint(0,1000000), help='set the random seed')
parser.add_argument('--bw', action='store_true', default=False, help='disable text coloring')
parser.add_argument('--dbg', action='store_true', default=False, help='turn on debugging')
parser.add_argument('--parse', action='store_true', default=False, help='parse only')
parser.add_argument('--inst', action='store_true', default=False, help='print instructions only')
parser.add_argument('file', type=str, help='A Mnemosyne source file',nargs='+')
pres=parser.parse_args(sys.argv[1:])

DIV = '::'
files : Dict[str,str] = {}
logfd = open("log.txt","w")
sval = pres.seed
print("seed=%d" % sval,file=logfd)
seed(sval)
debug = False

path_to_mnemo = os.path.dirname(os.path.realpath(sys.argv[0]))
mnemo_path = [path_to_mnemo, "."]
if "MNEMO_PATH" in os.environ:
    mnemo_path += os.environ["MNEMO_PATH"].split(":")

INDENT = "  "

threads = []

g = Grammar()
compileFile(g,os.path.join(mnemo_path[0],"mnemo.peg"))
with open(pres.file[0]) as fd:
    fc = fd.read()
k : str = fc
v : str = pres.file[0]
files[k] = v
m = Matcher(g,"prog",fc)
if m.matches():
    if pres.parse:
        exit(0)
else:
    m.showError()
    raise Exception()

def filename(group:Group)->str:
    return files[group.text]

def loadstr(item : Any)->str:
    if type(item) == list:
        return "Array[%d]" % len(item)
    elif type(item) == dict:
        return "Struct[]"
    else:
        return str(item)

class Func:
    def __init__(self,addr : int):
        self.addr = addr
    def __repr__(self)->str:
        return "Func(addr=%d)" % self.addr

class BadAddress:
    def __repr__(self):
        return "BadAddress"

class Var:
    def __init__(self,name : str,val : Any,qual : str):
        self.name = name
        self.val = val
        self.oldval = None
        self.qual = qual
        self.finished = True
    def show(self)->None:
        if self.finished:
            print(self.qual,": ",self.val,sep='')
        else:
            print(self.qual,": ",self.oldval," => ",self.val,sep='')
    def check(self):
        assert self.qual in ["atomic","const","regular","safe"]
    def set(self,v : Any)->None:
        self.finished = False
        self.oldval = self.val
        if self.val is None:
            self.val = v
        else:
            assert self.qual != "const", "Attempt to set a constant variable"
            self.val = v
    def get(self)->Any:
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
            val : Any = None
            if type(self.val) == int:
                val = randint(-1000,1000)
            elif type(self.val) == float:
                val = 2000*(random()-.5)
            elif type(self.val) == bool:
                val = randint(0,1) == 0
            else:
                val = BadAddress()
            return val
        else:
            raise Exception(self.qual)
    def __repr__(self)->str:
        return "Var(%s,%s)" % (self.qual, type(self.val).__name__ )
    def storeFinish(self)->None:
        self.finished = True

def groupint(v : Union[Tuple[Group,int],Tuple[Group]])->Tuple[Group,int]:
    """
    This is a specialized casting function.
    Without iit, mypy will assert that v[1] is invalid.
    """
    assert len(v) == 2
    # Note that cast will trust us regardless of the type we specify
    # so we need to make sure it's actually allowed
    return cast(Tuple[Group,int], v)

thread_seq = 0

class Interp:
    def getvar(self,vname : str)->Var:
        if vname in self.vars[-1]:
            return self.vars[-1][vname]
        elif vname in self.vars[0]:
            return self.vars[0][vname]
        else:
            self.die("Invalid variable: '%s'" % vname)
            raise Exception() # Cannot get here

    def addr(self,f : Func)->int:
        self.massert(hasattr(f,"addr"),"Not a function object: "+str(f))
        return f.addr
        
    def done(self)->bool:
        return len(self.stack) == 0

    def __init__(self,gr : Group)->None:
        global thread_seq

        self.id = thread_seq
        thread_seq += 1

        self.trace = True
        self.gr = gr
        self.pc = -1
        self.stack : List[int] = []
        self.rets : List[Union[str,int]] = []
        self.vars : List[Dict[str,Var]] = [
            {"true":Var("true",True,"const"),
             "false":Var("false",False,"const"),
             "none":Var("none",None,"const")}]
        self.loads : List[Dict[Union[int,str],Optional[Union[int,Var]]]] = [{}]
        self.inst : List[Union[Tuple[Group,int],Tuple[Group]]] = []
        self.indent = 0
        self.delay = 0
        for i in range(gr.groupCount()):
            self.load_instructions(gr.group(i))

        # Find functions
        for i in range(len(self.inst)):
            gm = self.inst[i][0]
            nm = gm.getPatternName() 
            if nm == "start_fn":
                fnm = gm.group(0).substring()
                self.vars[0][fnm] = Var("fname",Func(i+1),"const")

        self.load_sys_functions(os.path.join(mnemo_path[0],"lib/sys.mn"))

    def load_sys_functions(self,fname : str)->None:
        with open(fname,"r") as fd:
            fc = fd.read()
        files[fc] = fname
        m2 = Matcher(g,"prog",fc)
        if not m2.matches():
            m2.showError()
        for k in range(m2.gr.groupCount()):
            elem = m2.gr.group(k) 
            nm = elem.getPatternName()
            if nm == "fun_def":
                func = elem.group(0).group(0).substring()
                ind = len(self.inst)+1
                self.vars[0][func] = Var("fun_def",Func(ind),"const")
                self.load_instructions(elem)
        if pres.inst:
            self.diag()
            exit(0)

    def diag(self)->None:
        # Diagnostic of the instruction set
        for i in range(len(self.inst)):
            print(colored(str(i)+":","yellow"),end=' ')
            nm = self.inst[i][0].getPatternName()
            if True: #nm in ["load", "store", "assign"]:
                print(colored(nm,"red"),self.inst[i][0].substring(),end=' ')
            else:
                print(colored(nm,"red"),end=' ')
            for j in range(1,len(self.inst[i])):
                print(colored(self.inst[i][j],"green"),end=' ')
            print()
        print('=====')

    def load_instructions(self,group:Group):
        nm = group.getPatternName()
        if nm in ["var", "fun"]:
            for i in range(group.groupCount()):
                self.load_instructions(group.group(i))
            load = Group("load",group.text,group.start,group.end)
            load.children += [group]
            self.inst += [(load,)]
        elif nm == "breakstmt" or nm == "continue":
            self.inst += [(group,)]
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
            self.load_instructions(group.group(0))
            self.inst += [(group,)]
            if nm == "assign":
                store = Group("store",group.text,group.start,group.end)
                store.children += [group.group(0)]
                self.inst += [(store,)]
        elif nm in ["expr", "val", "num", "op", "array", "str", "name", "args", "vals", "body", "real", "elem", "alloc", "qual", "struct", "pairs", "pair", "sizer", "memcall"]:
            for i in range(group.groupCount()):
                self.load_instructions(group.group(i))
        elif nm in ["start_fn", "end", "returnstmt", "for", "if", "elif", "else", "import", "while"]:
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
            if nm == "forstmt":
                self.inst[endptr] = (self.inst[endptr][0], i0) # point to start
            else:
                self.inst[endptr] = (self.inst[endptr][0], fstart) # point to start
        else:
            raise Exception(nm)
    def getval(self,expr : Group)->Any:
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
                elif op == "**":
                    return val1 ** val2
                raise Exception("op="+op)
        elif nm == "val":
            return self.getval(expr.group(0))
        elif nm == "num":
            return int(expr.substring())
        elif nm == "str":
            sval = expr.substring()
            return sval[1:-1]
        elif nm == "var" or nm == "fun":
            if expr.start not in self.loads[-1]:
                print("loads:",self.id,self.loads)
            return self.loads[-1][expr.start]
        elif nm == "real":
            return float(expr.substring())
        elif nm == "alloc":
            qual = expr.group(0).substring()
            vals = expr.group(1)
            vnm  = expr.group(1).getPatternName()
            if vnm == "array":
                ar = []
                for i in range(vals.groupCount()):
                    ar += [Var("&",self.getval(vals.group(i)),qual)]
            elif vnm == "struct":
                d = {}
                hash = vals.group(0)
                for i in range(hash.groupCount()):
                    pair = self.getval(hash.group(i))
                    pair[1].qual = qual
                    d[pair[0]] = pair[1]
                return d
            elif vnm == "sizer":
                ar = []
                count = self.getval(vals.group(0))
                for i in range(count):
                    item = self.getval(vals.group(1))
                    ar += [Var("&",item,qual)]
                return ar
            else:
                raise Exception(vnm)
            return ar
        elif nm == "pair":
            v0 : str = self.getval(expr.group(0))
            v1 : Var = self.getval(expr.group(1))
            var1 = Var('&',v1,"const")
            return (v0, var1)
        elif nm == "memcall":
            dvar = self.getval(expr.group(0))
            return dvar[expr.group(1).substring()]
        elif nm == "pairs" or nm == "vals":
            ar = []
            for k in range(expr.groupCount()):
                ar += self.getval(expr.group(k))
            return ar

        print("expr:",expr.dump())
        print("line:",expr.linenum())
        raise Exception(nm)
    def massert(self,test : bool,msg : str)->None:
        if not test:
            self.die(msg)
    def stack_trace(self)->None:
        print("Stack for thread:",self.id)
        self.stack += [self.pc] # Add current location to the stack
        for k in range(len(self.stack)-1,-1,-1):
            pc = self.stack[k]
            if pc < len(self.inst):
                pg = self.inst[pc][0]
                print(" at file '%s' line %d: %s" % (filename(pg), pg.linenum(), pg.substring()))
        self.stack = self.stack[:-1]
    def die(self,msg : str)->None:
        print("Die:",msg)
        self.stack += [self.pc] # Add current location to the stack
        for k in range(len(self.stack)-1,-1,-1):
            pc = self.stack[k]
            if pc < len(self.inst):
                pg = self.inst[pc][0]
                print(" at file '%s' line %d: %s" % (filename(pg), pg.linenum(), pg.substring()))
        #raise Exception("die")
        exit(0)

    def start_call(self,expr : Group,retkey : Union[str,int])->None:
        vals = expr.group(1)
        args = []
        for k in range(vals.groupCount()):
            args += [ self.getval(vals.group(k)) ]
        self.start_call2(expr,retkey,args)

    def start_call2(self,expr : Group,retkey : Union[int,str],args : List[str])->None:
        global threads, debug
        ####
        fnm = expr.group(0).substring()
        if fnm == "print" or fnm == "println":
            for arg in args:
                print(arg,end='')
            if fnm == "println":
                print()
            self.pc += 1
            return
        elif fnm == "pyexec":
            self.pc += 1
            retval : Any = None
            eglobs = {"retval":None,"args":args,"Var":Var}
            exec(args[0],{},eglobs)
            retval = eglobs["retval"]
            if type(retval) == list:
                retval = [Var('&',di,'const') for di in retval]
            self.loads[-1][retkey] = retval
            return
        elif fnm == "trace":
            val = args[0]
            if val == True:
                self.trace = True
            elif val == False:
                self.trace = False
            else:
                raise Exception(val)
            self.pc += 1
            return
        elif fnm == "assert":
            self.pc += 1
            val = args[0]
            if val != True:
                self.die("Assertion failure: "+expr.substring())
            return
        elif fnm == "spawn":
            vals = expr.group(1)
            newthread = Interp(self.gr)
            newthread.trace = debug
            newthread.indent = 0
            for k in self.vars[0].keys():
                newthread.vars[0][k] = self.vars[0][k]
            newthread.pc = len(self.inst)

            # Prepare spawn return location
            if vals.groupCount()>1:
                newthread.loads[-1][vals.group(1).start] = newthread.id # vid

            newthread.start_call2(vals,expr.start,args[1:])
            threads += [newthread]
            self.pc += 1
            vid = Var("id",newthread.id,"const")
            self.loads[-1][retkey] = newthread.id # vid
            return
        elif fnm == "is_alive":
            self.pc += 1
            pid = args[0]
            found : bool = False
            for th in threads:
                if pid == th.id:
                    found = True
                    break
            vb = found # Var("alive",found,"const")
            self.loads[-1][retkey] = vb
            return
        elif fnm == "brk":
            self.pc += 1
            if pres.dbg:
                debug = True
            return
        elif fnm == "len":
            self.pc += 1
            vals = self.getval(expr.group(1))
            self.loads[-1][retkey] = len(vals)
            return
        elif fnm == "ThreadID":
            self.pc += 1
            self.loads[-1][retkey] = self.id
            return
        elif fnm == "NumThreads":
            self.pc += 1
            self.loads[-1][retkey] = len(threads)
            return
        elif fnm == "CAS":
            self.pc += 1
            vname = expr.group(1).group(0).substring()
            if vname in self.vars[-1]:
                var = self.vars[-1][vname]
            elif vname in self.vars[0]:
                var = self.vars[0][vname]
            else:
                self.die("CAS: No such variable: "+vname)
            self.massert(type(var.val) == list,"Arg 0 of CAS must be a list")
            self.massert(len(var.val) > 0,"Array arg of CAS must have length of 1 or more")
            self.massert(var.val[0].qual == "atomic","Arg 0 of CAS must be atomic")
            oldval = args[1]
            newval = args[2]
            if var.val[0].val == oldval:
                var.val[0].val = newval
                var.val[0].storeFinish()
                retval = True
            else:
                retval = False
            self.loads[-1][retkey] = retval
            return
        ####
        mfnm = expr.group(0).getPatternName()
        add_self = 0
        # If we come here through spawn, we'll see expr
        if mfnm == "expr" or mfnm == "name":
            fname = expr.group(0).substring()
            try:
                funinst = self.addr(self.vars[0][fname].get())
            except KeyError as ke:
                self.die(str(ke))
        elif mfnm == "memcall":
            add_self = 1
            fname = expr.group(0).substring()
            vname = expr.group(0).group(0).substring()
            funinst = self.addr(self.getval(expr.group(0)).get())
        else:
            raise Exception(mfnm)
        if self.trace:
            print(INDENT * self.indent,colored(str(self.id)+": ","blue"),colored("start call: ","green"),colored(fname,"blue"),sep='')
        if pres.dbg and fname == "main":
            debug = True
        print(str(self.id),DIV,"start call: ",fname,sep='',file=logfd)
        self.indent += 1
        funval = self.inst[funinst-1][0]
        argdefs = funval.group(1)
        if expr.groupCount() > 1:
            argvals = expr.group(1)
        else:
            # Handle no args
            argvals = Group("","",0,0)
        n1 = argdefs.groupCount()
        #n2 = argvals.groupCount()+add_self
        n2 = len(args)+add_self
        print("n2 args:",args)
        self.massert(n1 == n2,"Arity mismatch for '"+fname+"()' %d != %d" % (n1,n2))
        self.vars += [{}]
        for i in range(argdefs.groupCount()):
            argname = argdefs.group(i).substring()
            if add_self == 1 and i == 0:
                argval = self.getval(expr.group(0).group(0))
            else:
                argval = args[i-add_self] #self.getval(argvals.group(i-add_self))
            argvar = Var(argname, argval, "const")
            self.vars[-1][argname] = argvar
        self.loads += [{}]
        self.stack += [self.pc]
        self.rets += [retkey]
        self.pc = funinst
        return

    def end_call(self,retval : Optional[Var])->None:
        self.indent -= 1
        self.pc = self.stack[-1]+1
        retkey = self.rets[-1]

        self.stack = self.stack[:-1]
        self.vars = self.vars[:-1]
        self.loads = self.loads[:-1]
        self.rets = self.rets[:-1]

        self.loads[-1][retkey] = retval
        if self.trace:
            print(INDENT * self.indent,colored(str(self.id)+": ","blue"),colored("end call->%s" % (loadstr(retval)),"green"),sep='')
        print(str(self.id),DIV,"end call->%s" % (loadstr(retval)),sep='',file=logfd)

    def step(self,feedback : List[bool]):
        global threads
        assert self.pc >= 0,str(self.pc)
        feedback[0] = False
        if self.pc >= len(self.inst):
            return False
        if self.delay > 0:
            if self.trace:
                print(INDENT*self.indent,colored("%d: " % self.id,"blue"),colored("delay","green"),sep='')
            print("%d:: " % self.id,"delay",sep='',file=logfd)
            self.delay -= 1
            return True
        s = self.inst[self.pc][0]
        nm = s.getPatternName()
        if nm == "load":
            if self.trace:
                print(INDENT*self.indent,colored(str(self.id)+": ","blue"),colored("line: "+str(s.linenum()),"green")," ",colored("load: "+s.substring(),"blue"),sep='',end=' ')
            print(str(self.id),DIV,"line: "+str(s.linenum())," ","load: "+s.substring(),sep='',end=' ',file=logfd)
        elif nm == "start_fn":
            pass #print(colored("step: "+str(self.pc),"green"),colored("define function: "+s.substring(),"blue"))
            feedback[0] = True
        elif nm == "store":
            if self.trace:
                print(INDENT*self.indent,colored(str(self.id)+": ","blue"),colored("line: "+str(s.linenum()),"green")," ",colored("finish: "+s.substring(),"blue"),sep='')
            print(str(self.id)+":: ","line: "+str(s.linenum())," ","finish: "+s.substring(),sep='',file=logfd)
        elif nm == "assign":
            if self.trace:
                print(INDENT*self.indent,colored(str(self.id)+": ","blue"),colored("line: "+str(s.linenum()),"green")," ",colored("start: "+s.substring(),"blue"),sep='')
            print(str(self.id),DIV,"line: "+str(s.linenum())," ","start: "+s.substring(),sep='',file=logfd)
        else:
            if self.trace:
                print(INDENT*self.indent,colored(str(self.id)+": ","blue"),colored("line: "+str(s.linenum()),"green")," ",colored(s.substring(),"blue"),sep='')
            print(str(self.id),DIV,"line: "+str(s.linenum())," ",s.substring(),sep='',file=logfd)
        if nm == "start_fn":
            vv = groupint(self.inst[self.pc])
            self.pc = vv[1]+1
            return True
        elif nm == "load":
            if s.group(0).getPatternName() == "var":
                vg = s.group(0)
                elems : List[Group] = []
                if vg.group(0).getPatternName() == "name":
                    vname = vg.substring()
                else:
                    elg = vg.group(0)
                    vname = elg.group(0).substring()
                    if elg.group(1).getPatternName() == "expr":
                        elems = [elg.group(1)]
                    else:
                        elems = elg.group(1).children
                var : Var
                if vname in self.vars[-1]:
                    var = self.vars[-1][vname]
                elif vname in self.vars[0]:
                    var = self.vars[0][vname]
                else:
                    self.die('No variable named: '+vname)
                for ch in elems:
                    chv = self.getval(ch)
                    try:
                       var = var.get()[chv]
                    except TypeError as te:
                       self.die("Not subscriptable: "+str(chv))
                    except IndexError as ie:
                       self.die("Index error: "+str(chv))
                    except KeyError as ke:
                       self.die("Key Error: "+str(chv))
                val = var.get()
                self.loads[-1][s.group(0).start] = val
                if self.trace:
                    print(colored("-> "+loadstr(val),"yellow"))
                print("-> "+loadstr(val),file=logfd)
                self.pc += 1
                return True
            elif s.group(0).getPatternName() == "fun":
                expr = s.group(0)
                if self.trace:
                    print()
                print(file=logfd)
                self.start_call(expr,s.start)
                return True
            else:
                raise Exception()
        elif nm == "def":
            qual = s.group(0).substring()
            val = self.getval(s.group(2))
            if s.group(1).getPatternName() == "var":
                vname = s.group(1).substring()
                self.massert(vname not in self.vars[-1],"Redefinition of "+vname+" at line  "+str(s.linenum()))
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
                    self.massert(vname not in self.vars[-1],"Redefinition of "+vname+" at line  "+str(s.linenum()))
                    var = Var("&",vname,val)
                    self.vars[-1][vname] = var
                    self.pc += 1
                    return True
                elif op == "=":
                    self.massert((vname in self.vars[-1]) or (vname in self.vars[0]),"Undefined variable '"+vname+"' at line "+str(s.linenum()))
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
        elif nm == "end":
            if len(self.stack) == 0:
                return False
            step_info = self.inst[self.pc]
            assert len(step_info) == 2
            endix = groupint(step_info)[1]
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
                self.pc = groupint(step_info)[1]
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
            self.massert(loopvar not in self.vars[-1],"Loop attempts to redefine "+loopvar)
            self.vars[-1][loopvar] = Var(loopvar,startval,"const")
            self.pc += 1
            return True
        elif nm == "if" or nm == "elif":
            bval = self.getval(s.group(0))
            self.massert(type(bval) == bool, "If expression does not evaluate to boolean "+s.substring())
            if bval:
                self.pc += 1
                return True
            else:
                self.pc = groupint(self.inst[self.pc])[1]
                return True
        elif nm == "else":
            self.pc += 1
            return True
        elif nm == "goto":
            self.pc = groupint(self.inst[self.pc])[1]
            return True
        elif nm == "import":
            fname = self.getval(s.group(0))
            vals = s.group(1)
            funs = []
            for i in range(vals.groupCount()):
                funs += [vals.group(i).substring()]

            # Locate path
            for path in mnemo_path:
                ftemp = os.path.join(path, fname)
                if os.path.exists(ftemp):
                    fname = ftemp
                    break

            with open(fname,"r") as fd:
                fc = fd.read()

            # Import
            files[fc] = fname
            m2 = Matcher(g,"prog",fc)
            if not m2.matches():
                m2.showError()
            for k in range(m2.gr.groupCount()):
                elem = m2.gr.group(k) 
                nm = elem.getPatternName()
                if nm == "fun_def":
                    func = elem.group(0).group(0).substring()
                    if func in funs:
                        ind = len(self.inst)+1
                        self.vars[0][func] = Var("fun_def",Func(ind),"const")
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
                self.pc = groupint(self.inst[self.pc])[1] + 1
            else:
                raise Exception(val)
            return True
        elif nm == "breakstmt" or nm == "continue":
            while self.pc < len(self.inst):
                step_info = self.inst[self.pc]
                if step_info[0].getPatternName() == "end":
                    endix = groupint(step_info)[1]
                    start_info = self.inst[endix]
                    if start_info[0].getPatternName() == "for":
                        #ends = start_info[0].getPatternName()
                        if nm == "breakstmt":
                            loopvar = start_info[0].group(0).substring()
                            del self.vars[-1][loopvar]
                            self.pc += 1
                        return True
                    elif start_info[0].getPatternName() in ["load", "while"]:
                        if nm == "breakstmt":
                            self.pc += 1
                        return True
                self.pc += 1
            return True
        raise Exception(s.dump())
        return False

## BEGIN MAIN CODE

interp = Interp(m.gr)

threads += [interp]

interp.pc = 0

def run_step():
    global debug
    while True:
        lo = 0
        hi = len(threads)-1
        if hi < 0:
            return False
        if lo == hi:
            tno = lo
        else:
            tno = randint(lo, hi)

        # The debugger
        stack_wait = 0
        if debug:
            while True:
                print('$ ',end='')
                sys.stdout.flush()

                cmd = sys.stdin.readline()

                if cmd == "":
                    debug = False
                    break

                rm = re.match(r'\s*stack\b',cmd)
                if rm:
                    for th in threads:
                        th.stack_trace()
                    continue

                rm = re.match(r'\s*(continue|cont|go)\b',cmd)
                if rm:
                    debug = False
                    break

                rm = re.match(r'\s*print\s*(\w+)',cmd)
                if rm:
                    vname = rm.group(1)
                    for th in threads:
                        if vname in th.vars[0]:
                            print("thread:",th.id,"global:",vname,"=",end=' ')
                            th.vars[0][vname].show()
                        elif vname in th.vars[-1]:
                            print("thread:",th.id,"local:",vname,"=",end=' ')
                            th.vars[-1][vname].show()
                    continue

                rm = re.match(r'\s*pc\b',cmd)
                if rm:
                    for th in threads:
                        ex_item = th.inst[th.pc][0]
                        print("thread:",th.id,"line:",ex_item.linenum(),"->",ex_item.substring())
                    continue

                rm = re.match(r'\s*step\s+(\d+)',cmd)
                if rm:
                    tnum = int(rm.group(1))
                    tinp = None
                    for k in range(len(threads)):
                        if threads[k].id == tnum:
                            tinp = k
                    if tinp is None:
                        print(colored("No such thread: "+rm.group(1),"red"),end=' threads: ')
                        for t in threads:
                            print(t.id,end=' ')
                        print()
                    else:
                        tno = tinp
                        break
                    continue

                print_debug_help()
                print(colored("???","red"))

        thread = threads[tno]
        feedback = [False]
        if not thread.step(feedback):
            del threads[tno]
        else:
            while feedback[0]:
                if not thread.step(feedback):
                    break
            return True

def addgr(gr,sgr,ss):
    g = Group(sgr,ss,0,len(ss))
    gr.children += [g]
    return g

def main():
    global threads
    while run_step():
        pass

    if "main" in interp.vars[0]:

        # Need to re-add the thread before calling main
        threads += [interp]

        mainloc = interp.addr(interp.vars[0]["main"].get())
        maing = interp.inst[mainloc-1][0]
        main_arg_count = maing.group(1).groupCount()
        #interp.vars += [{}]
        expr = Group("fun","",0,0)
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

if __name__ == "__main__":
    main()
