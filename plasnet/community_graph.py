# TODO: refactor

from typing import Optional

import networkx as nx

from plasnet.ColorPicker import ColorPicker
from plasnet.hub_graph import HubGraph
from plasnet.subcommunities import Subcommunities
from plasnet.subcommunity_graph import SubcommunityGraph
from plasnet.utils import DistanceDict, DistanceTags

import itertools
from networkx import edge_betweenness_centrality as betweenness

class CommunityGraph(HubGraph):
    def __init__(
        self,
        graph: Optional[nx.Graph] = None,
        hub_connectivity_threshold: int = 0,
        edge_density: float = 0.0,
        label: str = "",
    ):
        super().__init__(graph, hub_connectivity_threshold, edge_density, label)
        self._node_to_colour: dict[str, str] = {}

    def _get_node_color(self, node: str) -> str:
        return self._node_to_colour.get(node, ColorPicker.get_default_color())

    @staticmethod
    def _get_node_to_subcommunity(subcommunities: list[set[str]]) -> dict[str, int]:
        node_to_subcommunity = {}
        for subcommunity_index, subcommunity in enumerate(subcommunities):
            for node in subcommunity:
                node_to_subcommunity[node] = subcommunity_index
        return node_to_subcommunity

    def _fix_small_subcommunities(
        self, subcommunities: list[set[str]], small_subcommunity_size_threshold: int
    ) -> list[set[str]]:
        # sort subcommunities by size so that we can safely move
        # smaller subcommunities into larger ones
        subcommunities = sorted(subcommunities, key=lambda subcommunity: len(subcommunity))
        node_to_subcommunity = self._get_node_to_subcommunity(subcommunities)

        for subcommunity_idx, subcommunity in enumerate(subcommunities):
            subcommunity_is_too_small = len(subcommunity) <= small_subcommunity_size_threshold
            if subcommunity_is_too_small:
                subcommunity_neighbours = set(
                    neighbor for node in subcommunity for neighbor in self.neighbors(node)
                ) - set(subcommunity)
                subcommunity_has_no_neighbors = len(subcommunity_neighbours) == 0
                if subcommunity_has_no_neighbors:
                    continue

                candidate_subcommunities = set(
                    node_to_subcommunity[neighbor] for neighbor in subcommunity_neighbours
                )
                largest_subcommunity_size = max(
                    len(subcommunities[subcommunity]) for subcommunity in candidate_subcommunities
                )
                small_will_be_integrated_into_large = largest_subcommunity_size >= len(subcommunity)
                if small_will_be_integrated_into_large:
                    largest_subcommunity_idx = next(
                        filter(
                            lambda idx: len(subcommunities[idx]) == largest_subcommunity_size,
                            candidate_subcommunities,
                        )
                    )
                    subcommunities[largest_subcommunity_idx].update(subcommunity)
                    subcommunities[subcommunity_idx] = set()
        return subcommunities

    # to be used in girvan_newman
    #def most_central_edge(G):
    #    centrality = betweenness(G, weight=None)
    #    return max(centrality, key=centrality.get)

    def split_graph_into_subcommunities(
        self, small_subcommunity_size_threshold: int
    ) -> Subcommunities:
        communities_iterator = nx.community.girvan_newman(G=self, most_valuable_edge=None)
        
        subcommunities_nodes: list[set[str]] = []
    
        # Check if there's only one node in the community 
        if len(self.nodes()) == 1:
            subcommunities_nodes = [set(self.nodes())]
        else:
            # Initialize the variable to store the best level of subcommunities based on modularity
            best_subcommunities_nodes: list[set[str]] = []
            best_subcommunities_nodes = list(nx.connected_components(self)) #some nodes are isolated and needs to be put into separate subcommunity
            if self.number_of_edges() == 0:
                best_modularity = 0
            else:
                best_modularity = nx.community.modularity(self, best_subcommunities_nodes)
                
            # Iterate through the communities iterator to find the best level based on modularity
            for communities in communities_iterator:
    
                # Convert the tuple of sets to a list of sets (though it seems automatically done within nx.modularity)
                community_list = [set(community) for community in communities]
                
                # Flatten the communities into a single list of nodes
                nodes_in_communities = set(node for community in community_list for node in community)                

                # Create the subgraph induced by the nodes in the communities
                subgraph = self.subgraph(nodes_in_communities)
                
                # Check if there are any edges in the subgraph
                if subgraph.number_of_edges() == 0:
                    current_modularity = 0  # Return 0 if the subgraph has no edges
                else:
                    current_modularity = nx.community.modularity(self, community_list)
                
                # Update the best subcommunities if the current modularity is better
                if current_modularity > best_modularity:
                    best_modularity = current_modularity
                    best_subcommunities_nodes = community_list
        
            subcommunities_nodes = best_subcommunities_nodes  
        
        subcommunities_nodes = self._fix_small_subcommunities(
            subcommunities_nodes, small_subcommunity_size_threshold
        )

        subcommunities = []
        for subcommunity_index, subcommunity_nodes in enumerate(subcommunities_nodes):
            colour = ColorPicker.get_color_given_index(subcommunity_index)

            subcommunity = SubcommunityGraph(
                self.subgraph(subcommunity_nodes),
                self._hub_connectivity_threshold,
                self._edge_density,
                label=f"{self.label}_subcommunity_{subcommunity_index}",
                colour=colour,
            )
            subcommunities.append(subcommunity)

            for node in subcommunity_nodes:
                self._node_to_colour[node] = colour

        return Subcommunities(subcommunities)

    def _get_libs_relative_path(self) -> str:
        return ".."

    def _get_samples_selectors_HTML(self) -> str:
        return ""

    def add_typing_distances(self, distance_dict: DistanceDict) -> None:
        for edge in self.edges:
            self.edges[edge][DistanceTags.TypeDistanceTag.value] = distance_dict.get(
                edge, float("inf")
            )

    def filter_by_distance(self, distance_threshold: float) -> None:
        edges_to_remove = []
        for edge in self.edges:
            edge_should_be_removed = (
                self.edges[edge][DistanceTags.TypeDistanceTag.value] > distance_threshold
            )
            if edge_should_be_removed:
                edges_to_remove.append(edge)

        self.remove_edges_from(edges_to_remove)

    def recolour_nodes(self, other_community: "CommunityGraph") -> None:
        for node in self.nodes:
            self._node_to_colour[node] = other_community._get_node_color(node)
