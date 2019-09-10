# Mnemosyne
A programming language designed for CSC4585 http://csc.lsu.edu/csc4585/

<img align='right' width='150' alt='Image of the goddess Mnemosyne' src="https://upload.wikimedia.org/wikipedia/commons/6/6d/Mnemosyne_%28color%29_Rossetti.jpg">

This language supports the constructs of Chapter 4 of "The Art of Multiprocessor Programming"

* Safe memory - If a safe memory location is read while it is being written, a random number is obtained
* Regular memory - If a regular memory location is read while it is being written, either the new or old value will be obtained at random.
* Atomic memory - If an atomic memory location is read while it is being written, it will return either the new or old value, but once it returns the new value it will always do so.

Mnemoysne is written using Python 3 and the Piraha parser.

Mnemosyne supports...

Function definitions with `fun` / `end`. The function
named `main`, if present, is always executed.
```
# functions and a special function named main
fun main(args)
   println("Hello, world") 
end
```

Declaration of varialbes with `:=`

```
atomic a := 0 # an int
safe s := "hello" # a string
const pi := 3.14 # constant memory
```

Allocation of arrays and structs with operator new...

```
# a regular reference to an array of regluar
# memory references
regular r := new regular [0, 1, 3]

# a two-dimensional memory declaration
atomic a := new atomic 5 of (new atomic 8 of "$")
```

Control flow including `for`, `while`, `if`, `elif` (for else if), and `else`.
```
fun main()
  for i in 0 to 3
    println(i)
  end
  atomic j := 0
  while j < 10
     if j == 5
       break
     elif j < 5
       continue
     end
  end
end
```
