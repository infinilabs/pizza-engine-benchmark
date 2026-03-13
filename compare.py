#!/usr/bin/env python3
import json, sys

def load(path):
    with open(path) as f:
        data = json.load(f)
    d = {}
    for entry in data:
        q = entry['query']
        dur = min(entry['duration'])
        d[q] = dur
    return d

for cmd in ["TOP_10", "TOP_100", "COUNT"]:
    try:
        pizza = load(f"results/pizza-engine-0.1#{cmd}_results.json")
        lucene = load(f"results/lucene-10.4-bp#{cmd}_results.json")
    except FileNotFoundError:
        continue
    wins = losses = ties = 0
    for q in pizza:
        if q in lucene:
            p, l = pizza[q], lucene[q]
            if p < l: wins += 1
            elif p > l: losses += 1
            else: ties += 1
    total = wins + losses + ties
    if total > 0:
        print(f"{cmd:8s}: pizza {wins}/{total} ({100*wins/total:.1f}%) | lucene {losses}/{total} ({100*losses/total:.1f}%) | ties {ties}")
