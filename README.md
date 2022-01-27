# Liftoff

<img align="right" src="./assets/icon.png" height="150px" alt="the Liftoff icon">

`liftoff` is a tree-walking interpreter for the toy language Rocket, built as the final project for a CS class.

## Table of Contents

- [Try Liftoff](#try-liftoff)
  - [Sample Programs](#sample-programs)
- [Rocket: The Language](#rocket-the-language)
- [Built-ins](#built-ins)
- [Known Issues](#known-issues)
- [Architecture](#architecture)
- [Author](#author)

## Try Liftoff

**Prerequisites:** Python 3.9 or higher and Git.

1. Clone the repository onto your local machine:

   ```
   $ git clone https://github.com/jo3-l/liftoff
   ```

2. Change your working directory:

   ```
   $ cd liftoff
   ```

3. Run `cli.py`, passing the path of the Rocket file to run:

   ```
   $ py src/cli.py examples/fib.rk
   ```

### Sample Programs

A small collection of representative Rocket programs are available under the [examples](./examples/) directory.

## Rocket: The Language

Rocket is a toy language, but it should suffice for building simple programs. Below is an overview of the Rocket language syntax:

### Statements and Expressions

A statement is a line of code that typically has some side effect, whereas an expression evaluates to something.

Statements must be followed by a semicolon.

### Blocks

Multiple statements can be grouped together using braces, which form a block. Blocks introduce a new scope.

```
{
	let x = 1;
	let y = 2;
}
```

### Variables

Variables are introduced by the `let` keyword:

```
let x = 1;
```

### Literal values

Simple integer and float literals are supported (no fancy features like separators or hex), in addition to string, list, and dictionary literals. The `null` literal is also supported, being the equivalent of Python's `None`.

```
let int_lit = 1;
let float_lit = 3.14;
let str_lit = "hello,\nworld!";
let list_lit = [[1, 2], 3.4, "five"];

let foo = "foo";
let dict_lit = {foo: 1};
let null_lit = null;
```

### Conditionals

Conditionals are formed using the `if`, `else if`, and `else` statements.

```
if (cond) {
	// ...
} else if (other_cnd) {
	// ...
} else {
	// ...
}
```

### Loops

There are three forms of loops in Rocket: for loops, iterator-based for loops, and while loops.

**`for` loops**

All elements of the loop are optional, so `for (;;) {}` is a valid statement (resulting in an infinite loop.)

```
for (init_stmt; cond_expr; post_expr) {
	// ...
}
```

**Iterator-based for-loops**

```
for (let item of iterable) {
	// ...
}
```

**`while` loops**

```
while (loop_cond) {
	// ...
}
```

The `break` and `continue` statements may be used within the body of loops to appropriate effect.

### Functions and Methods

Function definitions can appear anywhere in the global scope. As a special case, functions may call other functions regardless of their position in the source, unlike variables which must be declared before usage.

```
fn f() {
	return 1;
}

print(f());
```

They may also accept a fixed number of parameters and return values:

```
fn my_add(a, b) {
	return add(a, b);
}
```

Methods are a kind of function that are called on a receiver. Though they cannot be created in Rocket (which does not support user-defined objects beyond dictionaries), they are accessible via built-ins and are callable using the same syntax as functions:

```
let nums = [1, 2, 3, 4];
print(nums.index(2));
```

Function values are first-class, meaning they can be stored in variables for later use. More generally, they are no different from any other value.

```
let my_print = print;
my_add("hello world!");
```

### Attributes and Items

Attributes are properties belonging to values; items are key-value pairs of dictionary-like objects.

Again, though Rocket does not support user-defined objects, attributes and items can appear through usage of built-ins and go by syntax akin to Python (`a.b` and `a[b]`):

```
let people = ["joe", "bob"];
print(people[0]); // joe
```

### Comments

Line comments use the `//` token, while multiline comments use `/*` and `*/`. Multiline comments do not nest.

```
// I'm a line comment
/* and I
   am a
   multiline comment */
```

A semi-formal specification of the Rocket language in extended Backus-Naur form is also available in the comments of the [parser](./src/parse/parser.py) implementation.

## Built-ins

- **print**: print value(s) to standard output with a trailing newline
- **input**: take input from standard input with an optional prompt
- **range**: create an half-closed interval that can be iterated over
- **format**: perform string interpolation; `format("{} = {}", "x", 5)` yields `x = 5`. `{}` represents a placeholder
- **lt/le/eq/ne/ge/gt/...**: comparison operators (`lt` is less than, `le` is less than or equal to, ...)
- **abs/add/sub/mul/div/pow/...**: math operators
- **or/and/not**: logical operators (no short circuiting!)
- **parse_int/parse_float**: parse strings into numerical types

## Known Issues

> **Note:** Most of these are a consequence of the short time in which this project was written; thus, one may view this as a to-do list of sorts instead.

- No classes
- No operators (unary or otherwise); instead, operators are functions
- No modules / packages
- Errors are not very user-friendly
- Functions interact strangely with their environment in certain edge cases

## Architecture

The [lexer](./src/parse/lexer.py) and [parser](./src/parse/parser.py) are handwritten, using recursive descent.
The [interpreter](./src/runtime/interpreter.py) is of the tree-walking type, simply descending the tree and evaluating as it goes.

## Author

**Liftoff** is authored and maintained by [Joe L.](https://github.com/jo3-l/) under the [MIT License](./LICENSE.md).
