# Contribution guidelines

Following the contribution guidelines saves everyone time, requires less back
and forth during the review process, and helps to ensures a consistent codebase.
I use PyCharm for all of my programming, and these are what I use for my settings, adapt to your editor of choice.

## A few general rules first:

- Open any pull request against the `master` branch
- Keep code to 80 characters or less.
- Comment your code
- Pull request description should clearly show what the change is including output if relevant.
- Squash commits before opening a pull request.
- Test and then test again! Make sure it works with the latest changes in `master`.
- If adding a function, it must have a type signature. Examples can be found [here](https://www.python.org/dev/peps/pep-0484/) and [here](https://www.python.org/dev/peps/pep-3107/)
- Spaces instead of Tabs
- 4 spaces for first indent and each from then on.
- Spaces around Assignment `(=, +=, …)`, Equality `(==, !=)`, Relational `(<, >, <=, >=)`, Bitwise `(*, |,^)`, Additive  `(+, -)`, Multiplicative `(*, @, /, %)`, Shift `(<<, >>, >>>)` and Power operators `(**)`.
- Spaces after:

```python
,
:
#
```

- Spaces before:

```python
\
#
```

- Align multiline method call arguments and method declaration parameters
- New line after a colon
- Align multiline import statements
- Align multiline collections and comprehensions
- Place `}` on a new line after a dictionary assignment
- 1 line between declarations and code
- 1 line after top level `imports`
- 1 line around `class`
- 1 line around `method`
- 2 lines around top-level `classes` and `functions`
- 1 line before and after `if` statements
- 1 line before and after `for` loops
- 1 line before and after `while` loops
- Run isort on `import` statements, including `from imports`.
- Keep `from imports` within their own group:

```python
import bar
import foo

from baz import foo
from foobar import morefoo
```

- Join `from imports` with the same source
- Align dictionaries on colons:

```python
x = max(
    1,
    2,
    3)

{
    “green”       : 42,
    "eggs and ham": -0.0e0
}
```

- Add a linefeed at the end of the file

## Running Tests

Please run our Test suit before submitting a pull request.
To do this you can run

```sh
make install-dev  # install dependencies needed to run check
make check
```

The linters and static code analysis tools run in `check ` can be executed on _any_ system.
For regression tests, you'll need a \*BSD system with a ZFS pool you can give `ioc` access to:

```sh
setenv ZPOOL=jails
make test
```
