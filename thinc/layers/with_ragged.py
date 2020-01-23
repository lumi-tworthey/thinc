from typing import Tuple, Callable, List, Optional, TypeVar, Union, cast

from ..types import Padded, Ragged, Array1d, Array2d
from ..model import Model
from ..config import registry


RaggedData = Tuple[Array2d, Array1d]
ValT = TypeVar("ValT", bound=Array2d)
SeqT = TypeVar("SeqT", bound=Union[Padded, Ragged, List[Array2d], RaggedData])


@registry.layers("with_ragged.v0")
def with_ragged(layer: Model[Ragged, Ragged]) -> Model[SeqT, SeqT]:
    return Model(f"with_ragged-{layer.name}", forward, init=init, layers=[layer])


def forward(
    model: Model[SeqT, SeqT], Xseq: SeqT, is_train: bool
) -> Tuple[SeqT, Callable]:
    layer: Model[Ragged, Ragged] = model.layers[0]
    Y: Union[Padded, Ragged, List[Array2d], RaggedData]
    if isinstance(Xseq, Ragged):
        Y, backprop = layer(Xseq, is_train)
    elif isinstance(Xseq, Padded):
        Y, backprop = _padded_forward(layer, cast(Padded, Xseq), is_train)
    elif _is_ragged_data(Xseq):
        Y, backprop = _tuple_forward(layer, cast(RaggedData, Xseq), is_train)
    else:
        Y, backprop = _list_forward(layer, cast(List[Array2d], Xseq), is_train)
    return cast(Tuple[SeqT, Callable], (Y, backprop))


def init(
    model: Model[SeqT, SeqT], X: Optional[SeqT] = None, Y: Optional[SeqT] = None
) -> Model[SeqT, SeqT]:
    model.layers[0].initialize(
        X=_get_ragged(model, X) if X is not None else None,
        Y=_get_ragged(model, Y) if Y is not None else None,
    )
    return model


def _is_ragged_data(seq):
    return isinstance(seq, tuple) and len(seq) == 2


def _get_ragged(model: Model, seq: SeqT) -> Ragged:
    if isinstance(seq, Ragged):
        return seq
    elif isinstance(seq, Padded):
        lists = model.ops.padded2list(seq)
        lengths: Array1d = model.ops.asarray([len(x) for x in lists], dtype="i")
        return Ragged(model.ops.flatten(lists), lengths)
    elif _is_ragged_data(seq):
        return Ragged(*cast(RaggedData, seq))
    else:
        lengths = model.ops.asarray([len(x) for x in seq], dtype="i")
        return Ragged(model.ops.flatten(cast(List[Array2d], seq)), lengths)


def _tuple_forward(layer: Model[Ragged, Ragged], X: RaggedData, is_train: bool):
    Yr, get_dXr = layer(Ragged(*X), is_train)

    def backprop(dY: RaggedData) -> RaggedData:
        dXr = get_dXr(Ragged(*dY))
        return (dXr.data, dXr.lengths)

    return (Yr.data, Yr.lengths), backprop


def _padded_forward(
    layer: Model[Ragged, Ragged], Xp: Padded, is_train: bool
) -> Tuple[Padded, Callable]:
    # Assign these to locals, to keep code a bit shorter.
    list2padded = layer.ops.list2padded
    padded2list = layer.ops.padded2list
    unflatten = layer.ops.unflatten
    flatten = layer.ops.flatten
    # It's worth being a bit careful about memory here, as the activations
    # are potentially large on GPU. So we make nested function calls instead
    # of assigning to temporaries where possible, so memory can be reclaimed
    # sooner.
    Xs = padded2list(Xp)
    # Bit annoying here: padded is in a different order, so we need to make new
    # lengths.
    lengths: Array1d = layer.ops.asarray([len(x) for x in Xs], dtype="i")
    Yr, get_dXr = layer(Ragged(flatten(Xs), lengths), is_train)

    def backprop(dYp: Padded):
        return list2padded(
            unflatten(get_dXr(Ragged(flatten(padded2list(dYp)), lengths)).data, lengths)
        )

    return list2padded(unflatten(Yr.data, Yr.lengths)), backprop


def _list_forward(
    layer: Model[Ragged, Ragged], Xs: List[Array2d], is_train: bool
) -> Tuple[List[Array2d], Callable]:
    # Assign these to locals, to keep code a bit shorter.
    flatten = layer.ops.flatten
    unflatten = layer.ops.unflatten

    lengths: Array1d = layer.ops.asarray([len(x) for x in Xs], dtype="i")
    Yr, get_dXr = layer(Ragged(flatten(Xs), lengths), is_train)

    def backprop(dYs: List[Array2d]) -> List[Array2d]:
        return unflatten(get_dXr(Ragged(flatten(dYs), lengths)).data, lengths)

    return unflatten(Yr.data, Yr.lengths), backprop
