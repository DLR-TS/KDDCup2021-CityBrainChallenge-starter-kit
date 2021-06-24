import heapq

class Edge:
    def __init__(self, id, length):
        self.id = id
        self.length = length
        self.out = []

    def addOut(self, another):
        self.out.append(another)

    def getShortestPath(self, toEdge):
        q = [(0, self.id, self, ())]
        seen = set()
        dist = {self: self.length}
        while q:
            cost, _, e1, path = heapq.heappop(q)
            if e1 in seen:
                continue
            seen.add(e1)
            path += (e1,)
            if e1 == toEdge:
                return path, cost

            for e2 in e1.out:
                if e2 not in seen:
                    newCost = cost + e2.length
                    if e2 not in dist or newCost < dist[e2]:
                        dist[e2] = newCost
                        heapq.heappush(q, (newCost, e2.id, e2, path))
        return None, 1e400
