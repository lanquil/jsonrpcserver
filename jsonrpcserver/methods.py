"""
The "methods" object holds the list of functions that can be called by remote calls.

Add as many methods as needed.

Methods can take either positional or named arguments (but not both, this is a
limitation of JSON-RPC).
"""
from typing import Any, Callable, Optional

from inspect import signature

Method = Callable[..., Any]


def validate_args(func: Method, *args: Any, **kwargs: Any) -> str:
    """
    Check if the request's arguments match a function's signature.

    Args:
        func: The function to check.
        args: Positional arguments.
        kwargs: Keyword arguments.

    Returns:
        An empty string if arguments can be passed to a function, an error
        message otherwise.
    """
    try:
        signature(func).bind(*args, **kwargs)
    except TypeError as exc:
        return str(exc)
    return ""


class Methods:
    """Holds a list of methods that can be called by a JSON-RPC request."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.items = {}  # type: dict
        self.add(*args, **kwargs)

    def add(self, *args: Any, **kwargs: Any) -> Optional[Callable]:
        """
        Register a function to the list.

        Args:
            *args: Set/Sequence of positional arguments.
            **kwargs: Mapping of named arguments.

        Raises:
            AssertionError: Raised if the method is not callable.
            AttributeError: Will be raised if a method is passed as a positional
                argument but has no `__name__` property (so we have no key for the items
                dictionary).

        Examples:
            methods = Methods()
            @methods.add
            def subtract(minuend, subtrahend):
                return minuend - subtrahend

            @methods.add(name='divide')
            def division(dividend, divisor):
                return dividend / divisor
        """
        if "name" in kwargs and isinstance(kwargs["name"], str):
            return self._parameterized_add(*args, **kwargs)
        else:
            return self._batch_add(*args, **kwargs)

    def _parameterized_add(self, name: str) -> Callable:
        def decorator(method):
            assert callable(method)
            self.items[name] = method

            return method

        return decorator

    def _batch_add(self, *args: Any, **kwargs: Any) -> Optional[Callable]:
        # Multiple loops here, but due to changes in dictionary comprehension
        # evaluation order in Python 3.8 (PEP 572), we need to validate
        # separately from the dictionary comprehension. Otherwise different
        # exceptions will be raised in 3.8 vs earlier Pythons, depending on
        # evaluation order.
        for m in args:
            assert callable(m)
        for _, m in kwargs.items():
            assert callable(m)
        self.items = {
            **self.items,
            # Methods passed as positional args need a __name__ attribute,
            # raises AttributeError otherwise.
            **{m.__name__: m for m in args},
            **{k: v for k, v in kwargs.items()},
        }
        if len(args):
            return args[0]  # for the decorator to work
        return None


# A default Methods object which can be used, or user can create their own.
global_methods = Methods()


def add(*args: Any, **kwargs: Any) -> Optional[Callable]:
    return global_methods.add(*args, **kwargs)
