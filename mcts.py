from concurrent.futures import ProcessPoolExecutor
import math
import random
import time
from multiprocessing import Pipe
import threading

class MCTSNode:
    def __init__(self, state, parent=None, action=None):
        self.state = state
        self.next_state = state.copy()
        self.parent = parent
        self.action = action
        self.children = []
        self.visits = 0
        self.value = 0.0

    def is_fully_expanded(self):
        possible_actions = self.state.get_legal_actions()
        max_children = int(math.ceil(math.sqrt(self.visits)))  # Progressive widening
        return len(self.children) >= min(len(possible_actions), max_children)

    def expand(self):
        # Get all possible actions from the current state
        possible_actions = self.next_state.get_legal_actions()
        if len(possible_actions) == 0:
            return None
        # Filter out actions that have already been tried (i.e., have corresponding child nodes)
        untried_actions = [action for action in possible_actions if action not in [child.action for child in self.children]]
        if len(untried_actions) == 0:
            return None
        
        # MCTS agent plays a move
        action = random.choice(untried_actions)
        self.next_state = self.state.copy()
        self.next_state.apply_action(action)

        # Opponent plays immediately after
        self.next_state.switch_turn()
        opponent_actions = self.next_state.get_legal_actions()
        if opponent_actions:
            opponent_action = random.choice(opponent_actions)  # TODO - Could make this more advanced
            self.next_state.apply_action(opponent_action)
            
        # Back to MCTS agent's turn
        self.next_state.switch_turn()        
        child_node = MCTSNode(self.next_state, parent=self, action=action)
        self.children.append(child_node)
        return child_node

    def best_child(self, c_param=1.5):
        if not self.children:
            return None

        choices_weights = []
        for child in self.children:
            if child.visits == 0:
                choices_weights.append(float('inf'))
            else:
                one_off_bonus = 2 if child.state.one_off() else 0 # TODO test without this ofc
                weight = (child.value / child.visits) + \
                         c_param * math.sqrt((2 * math.log(self.visits) / child.visits)) + \
                         one_off_bonus
                choices_weights.append(weight)
        return self.children[choices_weights.index(max(choices_weights))]

    def rollout(self, sim_num):
        current_rollout_state = self.state.copy()
        while not current_rollout_state.is_end():
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
        return current_rollout_state

    def rollout_policy(self, possible_moves):
        return random.choice(possible_moves)

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
            reward = v.rollout(sim_num)
            v.backpropagate(reward)
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
            
            # collect results
            results = [future.result() for future in futures]
        # stop monitoring thread
        monitor_running.clear()
        if update_callback:
            # close parents
            for conn in parent_connections:
                conn.close()
        
        # close children (incase)
        for conn in child_connections:
            conn.close()

        if not results:
            return None
        
        valid_results = [r for r in results if r is not None]
        if not valid_results:
            return None
            
        best = max(set(valid_results), key=valid_results.count)
        best.state.print_score()
        return best.action

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
    
    return local_mcts.root.best_child()