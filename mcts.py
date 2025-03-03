from concurrent.futures import ProcessPoolExecutor
import math
import random
import time
from multiprocessing import Pipe
import threading
from graph import visualize_mcts_tree as viz_mcts

class MCTSNode:
    def __init__(self, state, parent=None, action=None):
        self.state = state
        self.parent = parent
        self.action = action
        self.action_type = action[0] if action else None
        self.children = []
        self.visits = 0
        self.value = 0.0

    def is_fully_expanded(self):
        possible_actions = self.state.get_legal_actions()

        const = 1.5 # TODO modify exploration constant
        max_children = int(math.ceil(const * math.sqrt(self.visits)))
        return len(self.children) >= min(len(possible_actions), max_children)
        """ full expansion
        tried_actions = [child.action for child in self.children]
        expanded = len(tried_actions) >= len(possible_actions)
        if expanded:
            # Check if all possible actions have been tried
            for action in possible_actions:
                if action not in tried_actions:
                    expanded = False
                    break
        # A node is fully expanded only when ALL possible actions have been tried
        return expanded
        """

    def expand(self):
        # Get all possible actions from the current state
        possible_actions = self.state.get_legal_actions()
        if len(possible_actions) == 0:
            return None
        # Filter out actions that have already been tried (i.e., have corresponding child nodes)
        untried_actions = [action for action in possible_actions if action not in [child.action for child in self.children]]
        if len(untried_actions) == 0:
            return None
        
        # Split actions into their respective types to make random selection fair
        random_type = random.choice(['draw_two_train_cards', 'claim_route', 'draw_destination_tickets'])
        action_type = [action for action in untried_actions if action[0] == random_type]
        if not action_type:
            action_type = untried_actions
        # MCTS agent plays a move
        action = random.choice(action_type)
        child_state = self.state.copy()
        child_state.apply_action(action)

        # Opponent plays immediately after
        child_state.switch_turn()
        opponent_actions = child_state.get_legal_actions()
        if opponent_actions:
            opponent_action = random.choice(opponent_actions)  # TODO - Could make this more advanced
            child_state.apply_action(opponent_action)
            
        # Back to MCTS agent's turn
        child_state.switch_turn()        
        child_node = MCTSNode(child_state, parent=self, action=action)
        self.children.append(child_node)
        return child_node

    def best_child(self, c_param=2.5):
        if not self.children:
            return None
        choices_weights = []
        for child in self.children:
            if child.visits == 0:
                choices_weights.append(float('inf'))
            else:
                #one_off_bonus = 2 if child.state.one_off() else 0 # TODO test without this ofc
                weight = (child.value / child.visits) + \
                         c_param * math.sqrt((2 * math.log(self.visits) / child.visits))
                choices_weights.append(weight)
        return self.children[choices_weights.index(max(choices_weights))]

    def rollout(self, sim_num):
        current_rollout_state = self.state.copy()
        depth = 0
        max_depth = 100
        while not current_rollout_state.is_end() and depth < max_depth:
            possible_moves = current_rollout_state.get_legal_actions()
            if not possible_moves:
                break
            action = self.rollout_policy(possible_moves)
            current_rollout_state.apply_action(action)
            # Opponent plays immediately after
            current_rollout_state.switch_turn()
            opponent_actions = current_rollout_state.get_legal_actions()
            if not opponent_actions:
                break
            opponent_action = random.choice(opponent_actions)  # TODO - Could make this more advanced
            current_rollout_state.apply_action(opponent_action)
            # Back to MCTS agent's turn
            current_rollout_state.switch_turn()    
            depth += 1  
        return current_rollout_state

    def rollout_policy(self, possible_moves):
        # Split actions into their respective types to make random selection fair
        random_type = random.choice(['draw_two_train_cards', 'claim_route', 'draw_destination_tickets'])
        action_type = [action for action in possible_moves if action[0] == random_type]
        if not action_type:
            return random.choice(possible_moves)
        return random.choice(action_type)

    def backpropagate(self, result):
        self.visits += 1
        self.value += result
        if self.parent:
            self.parent.backpropagate(result)

class MCTS:
    def __init__(self, game_state, update_queue=None):
        self.root = MCTSNode(game_state)
        self.update_queue = update_queue

    def best_action(self, simulations_number):
        for sim_num in range(simulations_number):
            v = self.tree_policy()
            state = v.rollout(sim_num)
            player = state.players[state.current_player_idx]
            reward = state.game_result(sim_num)
            v.backpropagate(reward)
        viz_mcts(self.root, max_depth=4, 
                       filename=f"mcts_tree_turn_{self.root.state.current_player.turn}.png")
        return self.root.best_child().action
    
    def best_action_multi(self, update_callback, simulations_number, num_processes=8):
        if not self.root.state.get_legal_actions():
            return None

        simulations_per_process = simulations_number // num_processes
        
        # create pipes for each worker process
        pipes = [Pipe() for _ in range(num_processes)]
        parent_connections = [p[0] for p in pipes]
        child_connections = [p[1] for p in pipes]
        
        # start monitoring thread if update_callback is given
        monitor_running = threading.Event()
        if update_callback:
            monitor_thread = threading.Thread(
                target=monitor_pipes, 
                args=(parent_connections, update_callback, monitor_running)
            )
            monitor_thread.daemon = True
            monitor_running.set()
            monitor_thread.start()

        with ProcessPoolExecutor(max_workers=num_processes) as executor:
            # pass child connection to each worker
            futures = [
                executor.submit(
                    run_simulation, 
                    self.root.state, 
                    simulations_per_process, 
                    child_connections[i],
                    i
                ) for i in range(num_processes)
            ]
            
            # collect results - these are now MCTS objects
            mcts_results = [future.result() for future in futures]
        
        # stop monitoring thread
        monitor_running.clear()
        if update_callback:
            # close parents
            for conn in parent_connections:
                conn.close()
        
        # close children (incase)
        for conn in child_connections:
            conn.close()

        if not mcts_results:
            return None
        
        # Get best actions from each MCTS instance
        valid_actions = []
        for mcts in mcts_results:
            best_child = mcts.root.best_child() if mcts and mcts.root and mcts.root.children else None
            if best_child:
                valid_actions.append((best_child.action, mcts))
        
        if not valid_actions:
            return None
                
        # Find the most common action
        actions = [a[0] for a in valid_actions]
        best_action = max(set(actions), key=actions.count)
        
        # Find a MCTS instance that chose this action
        for action, mcts in valid_actions:
            if action == best_action:
                # Visualize the tree from this instance
                viz_mcts(mcts.root, max_depth=3, 
                        filename=f"mcts_tree_turn_{mcts.root.state.current_player.turn}.png")
                mcts.root.state.print_score()
                return best_action
        
        # Fallback (shouldn't reach here)
        return valid_actions[0][0] if valid_actions else None

    def tree_policy(self):
        current_node = self.root
        while not current_node.state.is_end():
            if not current_node.is_fully_expanded():
                new_node = current_node.expand()
                if new_node is not None:
                    return new_node
                elif current_node.children:
                    current_node = current_node.best_child()
                    if current_node is None:
                        return None
                else:
                    return None
            else:
                next_node = current_node.best_child()
                if next_node is None:
                    return current_node
                current_node = next_node
        return current_node


def monitor_pipes(connections, update_callback, running_event):
    """Monitor all pipe connections for updates and call the update callback"""
    total_games = 0

    try:
        while running_event.is_set():
            for conn in connections:
                try:
                    # Check if there's data available without blocking
                    if conn.poll():
                        # Get update data from pipe
                        update = conn.recv()
                        if update and 'player' in update:
                            total_games += 1
                            # Call the callback with update data
                            player_info = update['player']
                            game_num = update['game_num']
                            worker_id = update['worker_id']
                            update_callback(game_num, player_info, worker_id, total_games)
                except EOFError:
                    # Connection closed
                    continue
                except Exception as e:
                    print(f"Error receiving from pipe: {e}")
            
            # Small sleep to prevent CPU spinning
            time.sleep(0.05)
    except Exception as e:
        print(f"Monitor thread exiting with error: {e}")


def run_simulation(game_state, simulations_number, pipe_connection, worker_id):
    """ Runs an independent MCTS simulation for multiprocessing """
    local_mcts = MCTS(game_state)
    
    local_sim_count = 0
    
    try:
        for i in range(simulations_number):
            v = local_mcts.tree_policy()
            if v:
                state = v.rollout(i)
                player = state.players[state.current_player_idx]
                reward = state.game_result(i)
                v.backpropagate(reward)
                
                # update pipe every 10 simulations
                local_sim_count += 1
                if local_sim_count % 10 == 0:
                    try:
                        update_data = {
                            'game_num': local_sim_count,
                            'worker_id': worker_id,
                            'player': {
                                'name': player.name,
                                'points': reward
                            }
                        }
                        pipe_connection.send(update_data)
                    except Exception as e:
                        print(f"Error sending update: {e}")
    finally:
        # must close pipe
        pipe_connection.close()
    
    # Return the entire MCTS object instead of just the best child
    return local_mcts