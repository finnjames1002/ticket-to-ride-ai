import networkx as nx
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import scipy as sp

import networkx as nx
import matplotlib.pyplot as plt
import random

def visualize_mcts_tree(root, max_depth=3, max_children_per_node=4, filename="mcts_tree.png"):
    """
    Visualize the MCTS tree starting from the given root node.
    
    Args:
        root: The root MCTS node
        max_depth: Maximum depth to visualize (to avoid overwhelming visuals)
        max_children_per_node: Maximum number of children to show per node
        filename: If provided, save the visualization to this file
    """
    G = nx.DiGraph()
    
    # Add root node
    value = root.value / root.visits if root.visits > 0 else 0.0
    G.add_node(id(root), 
               label=f"Root\nVisits: {root.visits}\nValue: {value:.2f}",
               color='lightblue')
    
    # Process nodes in breadth-first order
    nodes_to_process = [(root, 0)]  # (node, depth)
    
    while nodes_to_process:
        node, depth = nodes_to_process.pop(0)
        
        if depth >= max_depth:
            continue
            
        # Sort children by value and pick top N
        sorted_children = sorted(node.children, key=lambda n: n.value / n.visits if n.visits > 0 else 0.0, reverse=True)
        
        # If there are too many children, select some randomly
        if len(sorted_children) > max_children_per_node:
            # Always include top score children
            top_children = sorted_children[:3]
            # And randomly sample from the rest to reach max_children_per_node
            rest = random.sample(sorted_children[3:], min(max_children_per_node - 3, len(sorted_children) - 3))
            selected_children = top_children + rest
        else:
            selected_children = sorted_children
            
        # Add children and edges
        for child in selected_children:
            # Format the action for display
            if child.action:
                if child.action[0] == 'claim_route':
                    action_label = f"Claim {child.action[1]}-{child.action[2]}"
                elif child.action[0] == 'draw_two_train_cards':
                    action_label = "Draw Cards"
                else:
                    num_dest = sum(child.action[1:3])
                    action_label = f"Draw Dest {num_dest}"
            else:
                action_label = "No action"
                
            # Calculate node color based on value/visits ratio (exploitation value)
            if child.visits > 0:
                # Use named colors instead of RGB tuples
                value_ratio = min(1.0, max(0.0, child.value / max(1, child.visits)))
                if value_ratio > 0.8:
                    color = 'red'
                elif value_ratio > 0.6:
                    color = 'salmon'
                elif value_ratio > 0.4:
                    color = 'lightcoral'
                elif value_ratio > 0.2:
                    color = 'mistyrose'
                else:
                    color = 'white'
            else:
                color = 'white'
                
            child_value = child.value / child.visits if child.visits > 0 else 0.0
            # Add node and edge
            G.add_node(id(child),
                      label=f"Visits: {child.visits}\nValue: {child_value:.2f}",
                      color=color)
            G.add_edge(id(node), id(child), 
                      label=action_label)
            
            # Add child to processing queue
            nodes_to_process.append((child, depth + 1))
    
    # Create the visualization
    plt.figure(figsize=(16, 10))
    pos = nx.nx_agraph.graphviz_layout(G, prog='dot')
    
    # Draw nodes with colors
    node_colors = [G.nodes[n].get('color', 'lightblue') for n in G.nodes]
    nx.draw_networkx_nodes(G, pos, node_size=2000, node_color=node_colors, alpha=0.8)
    
    # Draw edges
    nx.draw_networkx_edges(G, pos, arrowsize=20)
    
    # Add node labels
    node_labels = {n: G.nodes[n].get('label', '') for n in G.nodes}
    nx.draw_networkx_labels(G, pos, labels=node_labels, font_size=8)
    
    # Add edge labels
    edge_labels = {(u, v): G.edges[u, v].get('label', '') for u, v in G.edges}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8)
    
    plt.title(f"MCTS Tree (Max Depth: {max_depth}, Nodes: {len(G.nodes)})")
    plt.axis('off')
    
    # Always save to file (never show interactively in worker processes)
    plt.savefig(filename, bbox_inches='tight', dpi=150)
    #plt.show()
    plt.close('all')  # Close all figures to prevent memory leaks

class TicketToRideVisualizer:
    def __init__(self, game_state):
        self.game_state = game_state

    def visualize_game_map(self):
        G = nx.Graph()

        # Add nodes (cities)
        for city in self.game_state.routes:
            G.add_node(city)

        # Add edges (routes)
        for city1, connections in self.game_state.routes.items():
            for city2, routes in connections.items():
                for route in routes:
                    cb = route.claimed_by if route.claimed_by else 'Unclaimed'
                    G.add_edge(city1, city2, color=route.color.value, length=route.length, claimed_by=cb)

        # Customize node and edge appearance
        pos = nx.kamada_kawai_layout(G)
        node_color = ["lightblue"] * len(G.nodes)
        edge_colors = [edge_attr["color"] for u,v,edge_attr in G.edges(data=True)]

        # Draw the graph
        fig, ax = plt.subplots(figsize=(12, 8))
        nx.draw(G, pos, with_labels=True, node_color=node_color, edge_color=edge_colors, ax=ax, node_size=500, font_size=8)

        # Add edge labels
        edge_labels = {(u, v): f"{edge_attr['length'], edge_attr['claimed_by']}" for u, v, edge_attr in G.edges(data=True)}
        # Adjust label positions to appear above the edges
        label_pos = {k: (v[0], v[1] + 0.03) for k, v in pos.items()}
        nx.draw_networkx_edge_labels(G, label_pos, edge_labels=edge_labels, ax=ax, font_size=6)


        # Save the plot
        plt.savefig("ticket_to_ride_map.png")
        plt.show()
        return 0
