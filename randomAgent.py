import random

class RandomAgent:
    def __init__(self, game_state):
        self.game_state = game_state

    def get_action(self):
        possible_actions = self.game_state.get_legal_actions()
        if not possible_actions:
            return None
        return random.choice(possible_actions)

# Example usage:
# game_state = ...  # Initialize your game state here
# agent = RandomAgent(game_state)
# result = agent.play()
# print("Game result:", result)