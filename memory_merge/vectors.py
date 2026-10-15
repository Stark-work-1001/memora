"""Vector codec and exact top-k search.

Vectors are stored as little-endian float32 BLOBs (0.1 stored JSON text: ~4x larger, and decoding
it dominated query time). Search is exact (brute force), not approximate: for a single user's store
an exact scan over a contiguous matrix is fast enough with the optional native kernel and avoids the
recall loss, index maintenance and tuning of an ANN structure. See docs/NATIVE.md for measurements.

`memory_merge_native` (Rust, PyO3) is optional. Both kernels must return the same ranking; the
tests compare them.
"""
import heapq
import math
import sys
from array import array

try:  # optional compiled kernel, built from native/
    import memory_merge_native as _native
except ImportError:  # pragma: no cover - depends on the environment
    _native = None

_sumprod = getattr(math, 'sumprod', None)  # C implementation on Python >= 3.12
_SWAP = sys.byteorder == 'big'


def kernel():
    return 'native' if _native is not None else ('python-sumprod' if _sumprod else 'python')


def fusion(lexical, vector, weights=(0.01, 1.0), constant=60):
    """Native stable RRF with an equivalent compatibility fallback."""
    if _native is not None and hasattr(_native, 'rrf'):
        return _native.rrf(lexical, vector, weights[0], weights[1], constant)
    ranks = {}
    for i, ident in enumerate(lexical, 1): ranks[ident] = [weights[0] / (constant + i), i]
    for i, ident in enumerate(vector, 1):
        ranks.setdefault(ident, [0, 10 ** 6])[0] += weights[1] / (constant + i)
    return [(ident, data[0]) for ident, data in sorted(ranks.items(), key=lambda item: (-item[1][0], item[1][1]))]


def normalize(vec, dim=None):
    """Validate, optionally truncate (Matryoshka), then L2-normalise. Truncation must come first:
    normalising the full vector and then cutting it leaves a vector that is no longer unit length."""
    if not isinstance(vec, (list, tuple, array)) or not 1 <= len(vec) <= 8192:
        raise ValueError('invalid vector')
    for x in vec:
        if isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x):
            raise ValueError('invalid vector')
    if dim is not None:
        if dim > len(vec): raise ValueError(f'requested dimension {dim} exceeds model output {len(vec)}')
        vec = vec[:dim]
    norm = math.sqrt(math.fsum(x * x for x in vec))
    if not norm or not math.isfinite(norm): raise ValueError('invalid norm')
    return [x / norm for x in vec]


def pack(vec):
    a = array('f', vec)
    if _SWAP: a.byteswap()
    return a.tobytes()


def unpack(blob):
    a = array('f')
    a.frombytes(blob)
    if _SWAP: a.byteswap()
    return a


def dot(a, b):
    return _sumprod(a, b) if _sumprod else math.fsum(x * y for x, y in zip(a, b))


class Matrix:
    """Row-major float32 matrix of unit vectors with their ids."""

    def __init__(self, dim):
        self.dim = dim
        self.ids = []
        self.data = array('f')

    def add(self, id, blob):
        if len(blob) != self.dim * 4: raise ValueError('vector dimension mismatch')
        self.ids.append(id)
        row = unpack(blob)
        self.data.extend(row)

    def __len__(self):
        return len(self.ids)

    def topk(self, query, k):
        """Return [(score, id)] for the k highest dot products, best first."""
        if not self.ids or k <= 0: return []
        q = array('f', query)
        if len(q) != self.dim: raise ValueError('query dimension mismatch')
        k = min(k, len(self.ids))
        if _native is not None:
            pairs = _native.topk(self.data, q, self.dim, k)
        else:
            d, data = self.dim, memoryview(self.data)
            # Ties break towards the lower row index; the native kernel does the same.
            pairs = heapq.nlargest(k, ((dot(q, data[i * d:(i + 1) * d]), -i) for i in range(len(self.ids))))
            pairs = [(-n, s) for s, n in pairs]
        return [(float(s), self.ids[i]) for i, s in pairs]
