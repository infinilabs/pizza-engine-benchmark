import fileinput
import re
from client import SearchClient

ACCEPTED = re.compile("^[a-z ]+$")
PTN = re.compile("\s+")

search_client = SearchClient("lucene")
for line in fileinput.input():
    line = line.strip()
    if ACCEPTED.match(line):
        words = PTN.split(line.decode("utf-8"))
        words = [word.lower() for word in words]
        query = " ".join("+" + word for word in words)
        count = search_client.query(query)
        if count > 10:
            print count, " ".join(words)
