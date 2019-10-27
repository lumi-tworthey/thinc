from thinc.neural._classes.multiheaded_attention import AttentionInputs
from thinc.neural._classes.multiheaded_attention import PaddedAttentionInputs
import numpy
import numpy.random
import plac
from timebudget import timebudget
timebudget.report_atexit()  # Generate report when the program exits


def get_lengths(nr_length, mean=50, scale=10):
    lengths = numpy.random.normal(loc=mean, scale=scale, size=nr_length)
    lengths = lengths.astype("i")
    lengths = numpy.clip(lengths, a_min=1, a_max=None)
    return [length for length in lengths]


def get_attn_inputs(lengths, nH, nD):
    nN = sum(lengths)
    data = numpy.random.uniform(-1, 1, (sum(lengths), 3, nH, nD))
    data = data.astype("f")
    return AttentionInputs(data, lengths)


def get_padded_attn_inputs(lengths, nH, nD, values=None):
    if values is None:
        values = numpy.random.uniform(-1, 1, (sum(lengths), 3, nH, nD))
    data = numpy.zeros((len(lengths), max(lengths), 3, nH, nD), dtype="f")
    start = 0
    for i, length in enumerate(lengths):
        data[i, :length] = values[start:start+length]
        start += length
    return PaddedAttentionInputs(data, lengths)


@timebudget
def get_attn_ragged(batch):
    attn, backprop_attn = batch.get_attn()
    return attn


@timebudget
def get_attn_padded(batch):
    attn, backprop_attn = batch.get_attn()
    return attn


def main(nr_batch=100, nr_length=30, nH=4, nD=128//4):
    numpy.random.seed(0)
    unpadded = []
    padded = []
    for batch in range(nr_batch):
        lengths = get_lengths(nr_length)
        unpadded.append(get_attn_inputs(lengths, nH, nD))
        padded.append(get_padded_attn_inputs(lengths, nH, nD, values=unpadded[-1].QKV))
    unpadded_pow = 0.
    for batch in unpadded:
        attn = get_attn_ragged(batch)
        unpadded_pow += (attn*attn).sum()
    padded_pow = 0.
    for batch in padded:
        attn = get_attn_padded(batch)
        padded_pow += (attn*attn).sum()
    print(unpadded_pow, padded_pow)
    total_words = sum(batch.nN for batch in unpadded)
    print(total_words)

if __name__ == "__main__":
    plac.call(main)
