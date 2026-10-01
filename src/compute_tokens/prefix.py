"""Completion-ordered, same-model WEKA cache reconstruction."""
from bisect import bisect_left, insort
from collections import defaultdict
import heapq
ALIASES = {'claude-sonnet-4-5-20250929': 'claude-sonnet-4-5'}


def canonical(model):
    return ALIASES.get(model, model)


def common_prefix_tokens(prompt, candidate, block, total):
    n = 0
    for a, b in zip(prompt, candidate):
        if a != b:
            break
        n += 1
    return min(total, n * block)


def cache_reads(events, block):
    """Events sorted by start/stream; only completed same-model prompts can be reused."""
    recent_model, recent_stream = {}, {}
    history = defaultdict(list)
    pending = []
    for index, e in enumerate(events):
        while pending and pending[0][0] <= e.t:
            _, _, past = heapq.heappop(pending)
            recent_model[past.model] = past
            recent_stream[past.stream, past.model] = past
            insort(history[past.model], tuple(past.hashes))
        candidates = [c for c in (recent_model.get(e.model), recent_stream.get((e.stream,e.model)))
                      if c is not None]
        retained = max((common_prefix_tokens(e.hashes,c.hashes,block,e.input_tokens)
                        for c in candidates), default=0)
        ttl = max((common_prefix_tokens(e.hashes,c.hashes,block,e.input_tokens)
                   for c in candidates if e.t-c.end <= 300), default=0)
        prompt = tuple(e.hashes)
        pool = history[e.model]
        p = bisect_left(pool,prompt)
        ideal = max((common_prefix_tokens(prompt,c,block,e.input_tokens)
                     for c in pool[max(0,p-1):p+1]), default=0)
        assert 0 <= ttl <= retained <= ideal <= e.input_tokens
        heapq.heappush(pending,(e.end,index,e))
        yield e, retained, ttl, ideal
