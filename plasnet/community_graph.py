# TODO: refactor

from plasnet.blackhole_graph import BlackholeGraph
from plasnet.subcommunities import Subcommunities
from plasnet.subcommunity_graph import SubcommunityGraph
import networkx as nx
from utils import DistanceDict


class CommunityGraph(BlackholeGraph):
    @staticmethod
    def _get_node_to_subcommunity(subcommunities):
        node_to_subcommunity = {}
        for subcommunity_index, subcommunity in enumerate(subcommunities):
            for node in subcommunity:
                node_to_subcommunity[node] = subcommunity_index
        return node_to_subcommunity

    def _fix_small_subcommunities(self, subcommunities, small_subcommunity_size_threshold) -> list[SubcommunityGraph]:
        # sort subcommunities by size so that we can safely move smaller subcommunities into larger ones
        subcommunities = sorted(subcommunities, key=lambda subcommunity: len(subcommunity))
        node_to_subcommunity = self._get_node_to_subcommunity(subcommunities)

        for subcommunity_idx, subcommunity in enumerate(subcommunities):
            subcommunity_is_too_small = len(subcommunity) <= small_subcommunity_size_threshold
            if subcommunity_is_too_small:
                subcommunity_neighbours = set(
                    neighbor for node in subcommunity for neighbor in self.neighbors(node)) - set(subcommunity)
                subcommunity_has_no_neighbors = len(subcommunity_neighbours) == 0
                if subcommunity_has_no_neighbors:
                    continue

                candidate_subcommunities = set(node_to_subcommunity[neighbor] for neighbor in subcommunity_neighbours)
                largest_subcommunity_size = max(
                    len(subcommunities[subcommunity]) for subcommunity in candidate_subcommunities)
                small_will_be_integrated_into_large = largest_subcommunity_size >= len(subcommunity)
                if small_will_be_integrated_into_large:
                    largest_subcommunity_idx = next(
                        filter(lambda idx: len(subcommunities[idx]) == largest_subcommunity_size,
                               candidate_subcommunities))
                    subcommunities[largest_subcommunity_idx].update(subcommunity)
                    subcommunities[subcommunity_idx] = set()
        return subcommunities


    def split_graph_into_subcommunities(self, small_subcommunity_size_threshold: int) -> Subcommunities:
        subcommunities_nodes = list(nx.community.asyn_lpa_communities(G=self, weight='weight', seed=42))
        subcommunities_nodes = self._fix_small_subcommunities(subcommunities_nodes, small_subcommunity_size_threshold)
        subcommunities = [SubcommunityGraph(self._original_graph.subgraph(subcommunity_nodes),
                                            self._blackhole_connectivity_threshold,
                                            self._edge_density)
                          for subcommunity_nodes in subcommunities_nodes]
        return Subcommunities(subcommunities)

    def _get_libs_relative_path(self) -> str:
        return ".."

    def _get_samples_selectors_HTML(self) -> str:
        return ""

    def filter_by_distance(self, distance_dict: DistanceDict, distance_threshold: float) -> None:
        # go through each edge and remove it if the distance is above the threshold
        edges_to_remove = []
        for edge in self.edges:
            u, v = edge
            distance = distance_dict[(u, v)]
            if distance > distance_threshold:
                edges_to_remove.append(edge)
            else:
                # update the the weight of the edge to the distance
                self.edges[u, v]["weight"] = distance

        self.remove_edges_from(edges_to_remove)
