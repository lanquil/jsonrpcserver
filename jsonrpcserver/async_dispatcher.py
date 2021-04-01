"""Asynchronous dispatch"""
import asyncio
import collections.abc
from json import JSONDecodeError
from json import dumps as default_serialize, loads as default_deserialize
from typing import Any, Iterable, Optional, Union, Callable

from apply_defaults import apply_config  # type: ignore
from jsonschema import ValidationError  # type: ignore

from .dispatcher import (
    Context,
    add_handlers,
    config,
    create_requests,
    handle_exceptions,
    log_request,
    log_response,
    remove_handlers,
    schema,
    validate,
)
from .methods import Method, Methods, global_methods, validate_args, lookup
from .request import Request
from .response import (
    BatchResponse,
    InvalidJSONResponse,
    InvalidJSONRPCResponse,
    Response,
    SuccessResponse,
)


async def call(method: Method, *args: Any, **kwargs: Any) -> Any:
    return await validate_args(method, *args, **kwargs)(*args, **kwargs)


async def safe_call(
    request: Request, methods: Methods, *, extra: Any, serialize: Callable
) -> Response:
    with handle_exceptions(request) as handler:
        if isinstance(request.params, list):
            result = await call(
                lookup(methods, request.method),
                *([Context(request=request, extra=extra)] + request.params),
            )
        else:
            result = await call(
                lookup(methods, request.method),
                Context(request=request, extra=extra),
                **request.params,
            )
        # Ensure value returned from the method is JSON-serializable. If not,
        # handle_exception will set handler.response to an ExceptionResponse
        serialize(result)
        handler.response = SuccessResponse(
            result=result, id=request.id, serialize_func=serialize
        )
    return handler.response


async def call_requests(
    requests: Union[Request, Iterable[Request]],
    methods: Methods,
    extra: Any,
    serialize: Callable,
) -> Response:
    if isinstance(requests, collections.abc.Iterable):
        responses = (
            safe_call(r, methods, extra=extra, serialize=serialize) for r in requests
        )
        return BatchResponse(await asyncio.gather(*responses), serialize_func=serialize)
    return await safe_call(requests, methods, extra=extra, serialize=serialize)


async def dispatch_pure(
    request: str,
    methods: Methods,
    *,
    extra: Any,
    serialize: Callable,
    deserialize: Callable,
) -> Response:
    try:
        deserialized = validate(deserialize(request), schema)
    except JSONDecodeError as exc:
        return InvalidJSONResponse(data=str(exc))
    except ValidationError as exc:
        return InvalidJSONRPCResponse(data=None)
    return await call_requests(
        create_requests(deserialized),
        methods,
        extra=extra,
        serialize=serialize,
    )


@apply_config(config)
async def dispatch(
    request: str,
    methods: Optional[Methods] = None,
    *,
    basic_logging: bool = False,
    extra: Optional[Any] = None,
    trim_log_values: bool = False,
    serialize: Callable = default_serialize,
    deserialize: Callable = default_deserialize,
    **kwargs: Any,
) -> Response:
    # Use the global methods object if no methods object was passed.
    methods = global_methods if methods is None else methods
    # Add temporary stream handlers for this request, and remove them later
    if basic_logging:
        request_handler, response_handler = add_handlers()
    log_request(request, trim_log_values=trim_log_values)
    response = await dispatch_pure(
        request,
        methods,
        extra=extra,
        serialize=serialize,
        deserialize=deserialize,
    )
    log_response(str(response), trim_log_values=trim_log_values)
    # Remove the temporary stream handlers
    if basic_logging:
        remove_handlers(request_handler, response_handler)
    return response
