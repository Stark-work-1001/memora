//! Exact top-k inner-product search over a row-major f32 matrix.
//!
//! Why exact and not ANN: a single user's store holds thousands to low hundreds of thousands of
//! vectors. A multithreaded scan answers that in milliseconds with perfect recall, no index to
//! build or keep in sync, and nothing to tune. Python stays the orchestration layer; only this hot
//! loop is compiled. Results match the pure-Python kernel in memory_merge/vectors.py: products and
//! sums in f64, ties broken towards the lower row index.

use pyo3::buffer::PyBuffer;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::cmp::Ordering;
use std::collections::BinaryHeap;
use std::collections::HashMap;

#[derive(PartialEq, Clone, Copy)]
struct Hit {
    score: f64,
    idx: usize,
}

impl Eq for Hit {}

// "Greater" means "worse": lower score, or equal score and higher index. A max-heap of Hits
// therefore keeps the weakest retained hit on top, and an ascending sort lists the best first.
impl Ord for Hit {
    fn cmp(&self, other: &Self) -> Ordering {
        other
            .score
            .partial_cmp(&self.score)
            .unwrap_or(Ordering::Equal)
            .then(self.idx.cmp(&other.idx))
    }
}

impl PartialOrd for Hit {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

#[inline]
fn dot(a: &[f32], b: &[f32]) -> f64 {
    // Independent accumulators let the compiler vectorise without reassociating a single sum.
    let mut acc = [0f64; 4];
    let n = a.len() / 4 * 4;
    let mut i = 0;
    while i < n {
        for j in 0..4 {
            acc[j] += a[i + j] as f64 * b[i + j] as f64;
        }
        i += 4;
    }
    let mut s = (acc[0] + acc[1]) + (acc[2] + acc[3]);
    while i < a.len() {
        s += a[i] as f64 * b[i] as f64;
        i += 1;
    }
    s
}

fn scan(data: &[f32], q: &[f32], dim: usize, start: usize, end: usize, k: usize) -> Vec<Hit> {
    let mut heap: BinaryHeap<Hit> = BinaryHeap::with_capacity(k + 1);
    for row in start..end {
        let hit = Hit { score: dot(&data[row * dim..(row + 1) * dim], q), idx: row };
        if heap.len() < k {
            heap.push(hit);
        } else if let Some(worst) = heap.peek() {
            if hit < *worst {
                heap.pop();
                heap.push(hit);
            }
        }
    }
    heap.into_vec()
}

/// topk(data, query, dim, k) -> [(row, score)], best first.
///
/// `data` and `query` are any C-contiguous float32 buffers (array('f'), numpy, memoryview).
#[pyfunction]
fn topk(py: Python<'_>, data: &Bound<'_, PyAny>, query: &Bound<'_, PyAny>, dim: usize, k: usize) -> PyResult<Vec<(usize, f64)>> {
    let db = PyBuffer::<f32>::get_bound(data)?;
    let qb = PyBuffer::<f32>::get_bound(query)?;
    if !db.is_c_contiguous() || !qb.is_c_contiguous() {
        return Err(PyValueError::new_err("buffers must be C-contiguous float32"));
    }
    let n_items = db.item_count();
    if dim == 0 || qb.item_count() != dim || n_items % dim != 0 {
        return Err(PyValueError::new_err("dimension mismatch"));
    }
    let rows = n_items / dim;
    let k = k.min(rows);
    if k == 0 {
        return Ok(Vec::new());
    }
    // Snapshot writable Python buffers while holding the GIL. Exporting a buffer prevents
    // resizing, but does NOT prevent another Python thread from mutating its elements.
    // Native worker threads must never borrow mutable Python memory after releasing the GIL.
    let data = db.to_vec(py)?;
    let query = qb.to_vec(py)?;
    if data.iter().chain(query.iter()).any(|v| !v.is_finite()) {
        return Err(PyValueError::new_err("vectors must contain finite values"));
    }
    let d = data.as_slice();
    let q = query.as_slice();
    let out = py.allow_threads(|| {
        let threads = if n_items < (1 << 20) {
            1
        } else {
            std::thread::available_parallelism().map(|n| n.get()).unwrap_or(1).min(8)
        };
        let per = (rows + threads - 1) / threads;
        let mut all: Vec<Hit> = std::thread::scope(|s| {
            let handles: Vec<_> = (0..threads)
                .map(|t| {
                    let (start, end) = (t * per, ((t + 1) * per).min(rows));
                    s.spawn(move || if start < end { scan(d, q, dim, start, end, k) } else { Vec::new() })
                })
                .collect();
            handles.into_iter().flat_map(|h| h.join().expect("scan thread panicked")).collect()
        });
        all.sort();
        all.truncate(k);
        all.into_iter().map(|h| (h.idx, h.score)).collect::<Vec<_>>()
    });
    Ok(out)
}

/// Deterministic reciprocal-rank fusion. Metadata and eligibility remain in SQLite/Python.
#[pyfunction]
fn rrf(py: Python<'_>, lexical: Vec<String>, vector: Vec<String>, lexical_weight: f64,
       vector_weight: f64, constant: f64) -> PyResult<Vec<(String, f64)>> {
    if !constant.is_finite() || constant <= 0.0 ||
        [lexical_weight, vector_weight].iter().any(|w| !w.is_finite() || *w < 0.0) {
        return Err(PyValueError::new_err("invalid fusion weights or constant"));
    }
    Ok(py.allow_threads(move || {
        let mut entries: HashMap<String, (f64, usize, usize)> = HashMap::new();
        let mut order = 0;
        for (i, id) in lexical.into_iter().enumerate() {
            entries.insert(id, (lexical_weight / (constant + i as f64 + 1.0), i, order));
            order += 1;
        }
        for (i, id) in vector.into_iter().enumerate() {
            let e = entries.entry(id).or_insert_with(|| { order += 1; (0.0, usize::MAX, order) });
            e.0 += vector_weight / (constant + i as f64 + 1.0);
        }
        let mut ranked: Vec<_> = entries.into_iter().collect();
        ranked.sort_by(|a,b| b.1.0.total_cmp(&a.1.0).then(a.1.1.cmp(&b.1.1)).then(a.1.2.cmp(&b.1.2)));
        ranked.into_iter().map(|(id,(score,_,_))| (id,score)).collect()
    }))
}

#[pymodule]
fn memory_merge_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(topk, m)?)?;
    m.add_function(wrap_pyfunction!(rrf, m)?)?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
